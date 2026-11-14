import asyncio
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

import asyncpg  # type: ignore[import-untyped]
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import async_sessionmaker
from starlette.exceptions import HTTPException
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.agents.graph import WorkflowRunner
from app.api.health import router as health_router
from app.api.v1.router import router as v1_router
from app.core.body_limit import AdminBodyLimit
from app.core.config import Settings, get_settings
from app.core.database import make_engine
from app.core.logging import configure_logging
from app.ingestion.validation import IngestionError
from app.schemas.error import ErrorInfo, ErrorResponse, ValidationDetail

logger = logging.getLogger("schemeguard")


class RequestLoggingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = str(uuid4())
        scope.setdefault("state", {})["request_id"] = request_id
        started = time.monotonic()
        status_code = 500

        async def send_with_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = [
                    (key, value)
                    for key, value in message.get("headers", [])
                    if key.lower() != b"x-request-id"
                ]
                message["headers"] = [*headers, (b"x-request-id", request_id.encode())]
                if scope.get("path", "").startswith(
                    (
                        "/api/v1/admin/",
                        "/api/v1/auth/",
                        "/api/v1/me",
                        "/api/v1/profiles",
                        "/api/v1/assessments",
                        "/api/v1/notifications",
                        "/api/v1/notification-preferences",
                        "/api/v1/dashboard",
                        "/api/v1/recommendations",
                    )
                ):
                    message["headers"] = [
                        (k, v)
                        for k, v in message["headers"]
                        if k.lower() not in {b"cache-control", b"x-content-type-options"}
                    ]
                    message["headers"].extend(
                        [(b"cache-control", b"no-store"), (b"x-content-type-options", b"nosniff")]
                    )
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            route = scope.get("route")
            logger.info(
                "http_request",
                extra={
                    "request_id": request_id,
                    "method": scope["method"],
                    "route": getattr(route, "path", "unmatched"),
                    "status_code": status_code,
                    "duration_ms": round((time.monotonic() - started) * 1000, 2),
                },
            )


def error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: list[ValidationDetail] | None = None,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", str(uuid4()))
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(
            error=ErrorInfo(code=code, message=message, details=details), request_id=request_id
        ).model_dump(mode="json", exclude_none=True),
        headers={"X-Request-ID": request_id, "Cache-Control": "no-store"},
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = make_engine(settings)
        app.state.settings = settings
        app.state.engine = engine
        app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
        app.state.workflow_runner = WorkflowRunner(settings, app.state.session_factory)
        app.state.document_slots = asyncio.Semaphore(2)
        app.state.password_slots = asyncio.Semaphore(2)
        logger.info("application_started")
        try:
            yield
        finally:
            await engine.dispose()
            logger.info("application_stopped")

    app = FastAPI(
        title="SchemeGuard AI",
        version="0.7.0",
        description="Source-grounded discovery, deterministic eligibility, and administrator-only document intelligence. AI candidates always remain pending review.",
        lifespan=lifespan,
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
    app.add_middleware(AdminBodyLimit, pdf_max_bytes=settings.pdf_max_bytes)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Accept", "Content-Type"],
        expose_headers=["X-Request-ID"],
    )

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        response = error_response(request, exc.status_code, "http_error", str(exc.detail))
        response.headers.update(exc.headers or {})
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Do not echo raw inputs or exception contexts into errors or logs.
        details = [
            ValidationDetail(location=list(error["loc"]), type=error["type"], message=error["msg"])
            for error in exc.errors()
        ]
        return error_response(request, 422, "validation_error", "Invalid request parameters", details)

    @app.exception_handler(IngestionError)
    async def ingestion_error(request: Request, exc: IngestionError) -> JSONResponse:
        return error_response(request, exc.status, exc.code, exc.message)

    async def database_error(request: Request, exc: Exception) -> JSONResponse:
        logger.warning(
            "database_unavailable",
            extra={
                "error_type": type(exc).__name__,
                "request_id": getattr(request.state, "request_id", "unavailable"),
            },
        )
        return error_response(request, 503, "database_unavailable", "Database temporarily unavailable")

    app.add_exception_handler(SQLAlchemyError, database_error)
    app.add_exception_handler(OSError, database_error)
    app.add_exception_handler(TimeoutError, database_error)
    app.add_exception_handler(asyncpg.PostgresError, database_error)
    app.add_exception_handler(asyncpg.InterfaceError, database_error)

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            "unexpected_error",
            extra={
                "error_type": type(exc).__name__,
                "request_id": getattr(request.state, "request_id", "unavailable"),
            },
        )
        return error_response(request, 500, "internal_error", "An unexpected error occurred")

    app.include_router(health_router)
    app.include_router(v1_router)
    return app
