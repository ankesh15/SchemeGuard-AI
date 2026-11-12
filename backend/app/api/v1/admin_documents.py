import asyncio
from datetime import UTC, date, datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.provider import GeminiProvider, LLMProvider
from app.ai.validation import FIELDS
from app.auth.security import Administrator, audit, limit, require_admin
from app.core.database import get_session
from app.ingestion.fetcher import fetch_pdf
from app.ingestion.storage import DocumentStorage
from app.models import (
    AgentWorkflow,
    AuditEvent,
    CandidateEvidence,
    DocumentAsset,
    DocumentChunk,
    DocumentPage,
    ExtractionError,
    PolicyReview,
    ProcessingJob,
    RuleCandidate,
    Scheme,
    SchemeSource,
    SourceAuthorization,
)
from app.schemas.processing import (
    DocumentPageResponse,
    DocumentRead,
    ExtractRequest,
    JobRead,
    RemoteDocumentRequest,
    SourceApprovalRead,
    SourceApprovalRequest,
)
from app.services.ingestion import (
    approve_source,
    approved_source,
    get_document,
    process_document,
    register_document,
)

router = APIRouter(prefix="/admin", tags=["administrator document processing"])
DB = Annotated[AsyncSession, Depends(get_session)]
Admin = Annotated[Administrator, Depends(require_admin)]


def llm_provider(request: Request) -> LLMProvider:
    return GeminiProvider(request.app.state.settings)


Provider = Annotated[LLMProvider, Depends(llm_provider)]


async def bounded_body(request: Request, maximum: int) -> bytes:
    content = bytearray()
    async for part in request.stream():
        if len(content) + len(part) > maximum:
            raise HTTPException(413, "Request exceeds the configured byte limit")
        content.extend(part)
    return bytes(content)


@router.get("/overview")
async def overview(request: Request, administrator: Admin, session: DB) -> dict[str, Any]:
    settings = request.app.state.settings
    return {
        "documents": await session.scalar(select(func.count()).select_from(DocumentAsset)),
        "pending_reviews": await session.scalar(
            select(func.count()).select_from(PolicyReview).where(PolicyReview.status == "PENDING_REVIEW")
        ),
        "workflows": await session.scalar(select(func.count()).select_from(AgentWorkflow)),
        "pending_candidates": await session.scalar(select(func.count()).select_from(RuleCandidate)),
        "failed_jobs": await session.scalar(
            select(func.count()).select_from(ProcessingJob).where(ProcessingJob.status == "FAILED")
        ),
        "gemini_configured": bool(
            settings.gemini_api_key and settings.gemini_api_key.get_secret_value().strip()
        ),
        "gemini_model": settings.gemini_model,
        "pdf_max_bytes": settings.pdf_max_bytes,
        "pdf_max_pages": settings.pdf_max_pages,
        "supported_fields": [
            {"key": key, "label": value[0], "value_type": value[1], "units": value[2]}
            for key, value in FIELDS.items()
        ],
        "notice": "Candidates remain pending human review. Publication requires an explicit authenticated human decision on the complete saved proposal.",
    }


@router.post("/sources", response_model=SourceApprovalRead, status_code=201)
async def create_source(body: SourceApprovalRequest, administrator: Admin, session: DB) -> SourceApprovalRead:
    return await approve_source(session, administrator, body)


@router.get("/sources", response_model=list[SourceApprovalRead])
async def sources(
    administrator: Admin, session: DB, scheme_id: UUID | None = None
) -> list[SourceApprovalRead]:
    statement = (
        select(SourceAuthorization, SchemeSource, Scheme)
        .join(SchemeSource, SchemeSource.id == SourceAuthorization.source_id)
        .join(Scheme, Scheme.id == SchemeSource.scheme_id)
    )
    if scheme_id:
        statement = statement.where(Scheme.id == scheme_id)
    rows = await session.execute(statement.order_by(SourceAuthorization.approved_at.desc()).limit(100))
    return [
        SourceApprovalRead(
            source_id=source.id,
            scheme_id=scheme.id,
            scheme_name=scheme.name,
            url=source.url,
            title=source.title,
            publisher=source.publisher,
            approved_at=authorization.approved_at,
            revoked_at=authorization.revoked_at,
        )
        for authorization, source, scheme in rows
    ]


@router.post("/sources/{identifier}/revoke", status_code=204)
async def revoke_source(identifier: UUID, administrator: Admin, session: DB) -> None:
    approval = await session.get(SourceAuthorization, identifier)
    if not approval:
        raise HTTPException(404, "Source authorization not found")
    if approval.revoked_at is None:
        approval.revoked_at = datetime.now(UTC)
        audit(session, "document_source_revoked", administrator.id, str(identifier))
        await session.commit()


@router.post(
    "/documents",
    response_model=DocumentRead,
    status_code=201,
    openapi_extra={
        "requestBody": {
            "content": {
                "application/pdf": {"schema": {"type": "string", "format": "binary"}},
                "application/json": {"schema": RemoteDocumentRequest.model_json_schema()},
            }
        }
    },
)
async def ingest(
    request: Request,
    response: Response,
    administrator: Admin,
    session: DB,
    source_id: UUID | None = None,
    original_filename: str | None = Query(default=None, max_length=255),
    published_on: date | None = None,
    attested: bool = False,
) -> DocumentRead:
    settings = request.app.state.settings
    await limit(session, f"document-ingestion:{administrator.id}", 20, 900)
    async with request.app.state.document_slots:
        async with asyncio.timeout(settings.processing_timeout):
            content_type = request.headers.get("content-type", "").split(";")[0].lower()
            if content_type == "application/pdf":
                if not attested:
                    raise HTTPException(
                        422, "Confirm that the uploaded PDF matches the selected scheme and approved source"
                    )
                if source_id is None or original_filename is None:
                    raise HTTPException(
                        422, "PDF uploads require source_id and original_filename query parameters"
                    )
                await approved_source(session, source_id)
                content = await bounded_body(request, settings.pdf_max_bytes)
                acquisition = "upload"
            elif content_type == "application/json":
                try:
                    remote = RemoteDocumentRequest.model_validate_json(await bounded_body(request, 16000))
                except ValidationError as error:
                    raise HTTPException(422, "Invalid official-document registration request") from error
                source = await approved_source(session, remote.source_id)
                content, original_filename = await fetch_pdf(
                    source.url, settings.pdf_max_bytes, settings.document_download_timeout
                )
                source_id, published_on, acquisition = source.id, remote.published_on, "download"
            else:
                raise HTTPException(
                    415,
                    "Use application/pdf for an upload or application/json for an approved-source download",
                )
            result, duplicate = await register_document(
                session,
                settings,
                administrator,
                source_id,
                content,
                original_filename,
                acquisition,
                published_on,
            )
    response.status_code = 200 if duplicate else 201
    response.headers["X-Document-Duplicate"] = str(duplicate).lower()
    return result


@router.get("/documents", response_model=DocumentPageResponse)
async def documents(
    administrator: Admin,
    session: DB,
    page: int = Query(default=1, ge=1, le=100000),
    page_size: int = Query(default=20, ge=1, le=100),
) -> DocumentPageResponse:
    total = await session.scalar(select(func.count()).select_from(DocumentAsset)) or 0
    identifiers = await session.scalars(
        select(DocumentAsset.document_version_id)
        .order_by(DocumentAsset.created_at.desc(), DocumentAsset.document_version_id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return DocumentPageResponse(
        items=[await get_document(session, identifier) for identifier in identifiers],
        page=page,
        page_size=page_size,
        total=total,
    )


@router.get("/documents/{identifier}")
async def document(identifier: UUID, administrator: Admin, session: DB) -> dict[str, Any]:
    result = await get_document(session, identifier)
    jobs = await session.scalars(
        select(ProcessingJob)
        .where(ProcessingJob.document_version_id == identifier)
        .order_by(ProcessingJob.started_at.desc())
        .limit(100)
    )
    pages = await session.execute(
        select(DocumentPage.page_number, DocumentPage.issues)
        .where(DocumentPage.document_version_id == identifier)
        .order_by(DocumentPage.page_number)
    )
    return {
        **result.model_dump(mode="json"),
        "jobs": [JobRead.model_validate(job).model_dump(mode="json") for job in jobs],
        "pages": [{"page_number": number, "issues": issues} for number, issues in pages],
    }


@router.get("/documents/{identifier}/original")
async def original(identifier: UUID, request: Request, administrator: Admin, session: DB) -> Response:
    item = await get_document(session, identifier)
    settings = request.app.state.settings
    content = await asyncio.to_thread(
        DocumentStorage(settings.document_storage_root).read,
        item.storage_key,
        item.checksum,
        settings.pdf_max_bytes,
    )
    audit(session, "document_original_downloaded", administrator.id, str(identifier))
    await session.commit()
    from urllib.parse import quote

    return Response(
        content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(item.original_filename, safe='')}",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox; default-src 'none'",
            "Cache-Control": "no-store",
        },
    )


@router.get("/documents/{identifier}/pages/{page_number}")
async def page_content(
    identifier: UUID, page_number: int, administrator: Admin, session: DB
) -> dict[str, Any]:
    page = await session.scalar(
        select(DocumentPage).where(
            DocumentPage.document_version_id == identifier, DocumentPage.page_number == page_number
        )
    )
    if not page:
        raise HTTPException(404, "Parsed document page not found")
    chunks = await session.scalars(
        select(DocumentChunk)
        .where(DocumentChunk.document_version_id == identifier, DocumentChunk.page_number == page_number)
        .order_by(DocumentChunk.ordinal)
    )
    return {
        "document_version_id": str(identifier),
        "page_number": page.page_number,
        "text_content": page.text_content,
        "blocks": page.blocks,
        "issues": page.issues,
        "extraction_method": page.extraction_method,
        "chunks": [
            {
                "id": str(chunk.id),
                "section_identifier": chunk.section_identifier,
                "text": chunk.text_content,
                "bounding_box": chunk.bounding_box,
                "extraction_method": chunk.extraction_method,
            }
            for chunk in chunks
        ],
    }


@router.post("/documents/{identifier}/extract", response_model=JobRead, status_code=201)
async def extract(
    identifier: UUID,
    body: ExtractRequest,
    request: Request,
    administrator: Admin,
    session: DB,
    provider: Provider,
) -> JobRead:
    await limit(session, f"extraction:{administrator.id}", 10, 900)
    async with request.app.state.document_slots:
        job = await process_document(
            session, request.app.state.settings, administrator, identifier, body.mode, provider
        )
    return JobRead.model_validate(job)


@router.get("/extractions/{identifier}")
async def extraction(identifier: UUID, administrator: Admin, session: DB) -> dict[str, Any]:
    job = await session.get(ProcessingJob, identifier)
    if not job:
        raise HTTPException(404, "Extraction job not found")
    errors = await session.scalars(
        select(ExtractionError)
        .where(ExtractionError.job_id == identifier)
        .order_by(ExtractionError.created_at)
    )
    return {
        **JobRead.model_validate(job).model_dump(mode="json"),
        "errors": [
            {"code": error.code, "message": error.message, "page_number": error.page_number}
            for error in errors
        ],
    }


@router.get("/extractions/{identifier}/candidates")
async def candidates(
    identifier: UUID,
    administrator: Admin,
    session: DB,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    if not await session.get(ProcessingJob, identifier):
        raise HTTPException(404, "Extraction job not found")
    total = (
        await session.scalar(
            select(func.count()).select_from(RuleCandidate).where(RuleCandidate.job_id == identifier)
        )
        or 0
    )
    records = await session.scalars(
        select(RuleCandidate)
        .where(RuleCandidate.job_id == identifier)
        .order_by(RuleCandidate.created_at, RuleCandidate.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = []
    for record in records:
        evidence = await session.execute(
            select(CandidateEvidence, DocumentPage.page_number)
            .join(DocumentPage, DocumentPage.id == CandidateEvidence.page_id)
            .where(CandidateEvidence.candidate_id == record.id)
        )
        items.append(
            {
                "id": str(record.id),
                "document_version_id": str(record.document_version_id),
                "condition_identifier": record.condition_identifier,
                "label": record.label,
                "logical_relationship": record.logical_relationship,
                "payload": record.payload,
                "mapped_expression": record.mapped_expression,
                "validation_status": record.validation_status,
                "validation_issues": record.validation_issues,
                "review_status": record.review_status,
                "evidence": [
                    {"node_key": item.node_key, "page_number": number, "excerpt": item.excerpt}
                    for item, number in evidence
                ],
            }
        )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/audit")
async def audit_events(administrator: Admin, session: DB) -> list[dict[str, Any]]:
    events = await session.scalars(select(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(100))
    return [
        {
            "id": str(event.id),
            "actor_id": str(event.actor_id) if event.actor_id else None,
            "action": event.action,
            "target_id": event.target_id,
            "details": event.details,
            "created_at": event.created_at.isoformat(),
        }
        for event in events
    ]
