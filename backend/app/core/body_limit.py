"""Bound administrator request bodies before JSON decoding or route execution."""

from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class AdminBodyLimit:
    def __init__(self, app: ASGIApp, pdf_max_bytes: int):
        self.app, self.pdf_max_bytes = app, pdf_max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not scope.get("path", "").startswith("/api/v1/admin/"):
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers", []))
        maximum = (
            self.pdf_max_bytes
            if headers.get(b"content-type", b"").split(b";")[0] == b"application/pdf"
            else 131_072
            if scope["path"].startswith("/api/v1/admin/reviews/")
            else 16_000
        )
        declared = headers.get(b"content-length", b"0")
        if not declared.isdigit() or int(declared) > maximum:
            response = JSONResponse(
                {
                    "request_id": scope.get("state", {}).get("request_id"),
                    "error": {
                        "code": "request_too_large",
                        "message": "Administrator request exceeds its byte limit",
                    },
                },
                status_code=413,
                headers={"Cache-Control": "no-store"},
            )
            await response(scope, receive, send)
            return
        total = 0

        async def bounded_receive() -> Message:
            nonlocal total
            message = await receive()
            if message["type"] == "http.request":
                total += len(message.get("body", b""))
                if total > maximum:
                    raise HTTPException(413, "Administrator request exceeds its byte limit")
            return message

        await self.app(scope, bounded_receive, send)
