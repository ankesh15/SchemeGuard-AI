import asyncio
import hashlib
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4, uuid5

from fastapi import HTTPException
from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.provider import GeminiProvider, LLMProvider, ProviderError
from app.ai.validation import mark_conflicts, validate_batch
from app.auth.security import Administrator, audit
from app.core.config import Settings
from app.ingestion.chunker import chunk_pages
from app.ingestion.pdf_parser import ParsedPage, parse_pdf
from app.ingestion.storage import DocumentStorage
from app.ingestion.validation import IngestionError, filename, official_url, pdf_bytes
from app.models import (
    CandidateEvidence,
    DocumentAsset,
    DocumentChunk,
    DocumentPage,
    DocumentVersion,
    ExtractionError,
    ProcessingJob,
    RuleCandidate,
    Scheme,
    SchemeSource,
    SourceAuthorization,
)
from app.schemas.processing import DocumentRead, SourceApprovalRead, SourceApprovalRequest


async def approve_source(
    session: AsyncSession, administrator: Administrator, body: SourceApprovalRequest
) -> SourceApprovalRead:
    if not body.authorized_public_document:
        raise HTTPException(422, "Confirm that this is an authorized public official policy document")
    url = official_url(body.url)
    scheme = await session.get(Scheme, body.scheme_id)
    if not scheme or scheme.is_demo:
        raise HTTPException(422, "Select an existing government scheme for an official document")
    # Serialize approvals for the same scheme without modifying scheme metadata.
    await session.execute(select(Scheme.id).where(Scheme.id == scheme.id).with_for_update())
    source = await session.scalar(
        select(SchemeSource).where(SchemeSource.scheme_id == scheme.id, SchemeSource.url == url)
    )
    if source is None:
        source = SchemeSource(
            scheme_id=scheme.id,
            url=url,
            title=body.title,
            publisher=body.publisher,
            is_primary=False,
            supported_fields=["official_document_reference"],
            verification_notes=body.notes,
            verified_on=datetime.now(UTC).date(),
        )
        session.add(source)
        await session.flush()
    authorization = await session.get(SourceAuthorization, source.id)
    if authorization is not None:
        if authorization.revoked_at:
            raise HTTPException(409, "This source authorization was revoked; use a reviewed new source")
        if authorization.url_sha256 != hashlib.sha256(url.encode()).hexdigest():
            raise HTTPException(409, "Source URL changed after approval")
    else:
        authorization = SourceAuthorization(
            source_id=source.id,
            approved_by=administrator.id,
            url_sha256=hashlib.sha256(url.encode()).hexdigest(),
            notes=body.notes,
        )
        session.add(authorization)
        audit(session, "document_source_approved", administrator.id, str(source.id), scheme_id=str(scheme.id))
    await session.commit()
    return SourceApprovalRead(
        source_id=source.id,
        scheme_id=scheme.id,
        scheme_name=scheme.name,
        url=source.url,
        title=source.title,
        publisher=source.publisher,
        approved_at=authorization.approved_at,
        revoked_at=authorization.revoked_at,
    )


async def approved_source(session: AsyncSession, source_id: UUID) -> SchemeSource:
    source = await session.get(SchemeSource, source_id)
    approval = await session.get(SourceAuthorization, source_id)
    if (
        not source
        or not approval
        or approval.revoked_at
        or hashlib.sha256(source.url.encode()).hexdigest() != approval.url_sha256
    ):
        raise HTTPException(
            403, "This exact official source URL requires current administrator authorization"
        )
    official_url(source.url)
    return source


async def register_document(
    session: AsyncSession,
    settings: Settings,
    administrator: Administrator,
    source_id: UUID,
    content: bytes,
    original_filename: str,
    acquisition_method: str,
    published_on: date | None,
) -> tuple[DocumentRead, bool]:
    name = filename(original_filename)
    pdf_bytes(content, settings.pdf_max_bytes)
    source = await approved_source(session, source_id)
    if published_on and published_on > datetime.now(UTC).date():
        raise HTTPException(422, "Publication date cannot be in the future")
    checksum = hashlib.sha256(content).hexdigest()
    inspected = await parse_pdf(
        content,
        max_pages=settings.pdf_max_pages,
        max_chars=settings.pdf_max_text_chars,
        timeout_seconds=settings.pdf_parse_timeout,
        inspect_only=True,
    )
    lock = int.from_bytes(hashlib.sha256(source.id.bytes).digest()[:8], "big", signed=True)
    await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock})
    previous = await session.scalar(
        select(DocumentVersion).where(
            DocumentVersion.source_id == source.id, DocumentVersion.content_sha256 == checksum
        )
    )
    if previous:
        asset = await session.get(DocumentAsset, previous.id)
        if not asset:
            raise HTTPException(
                409, "This content is already registered in legacy immutable document history"
            )
        # A missing or altered original never silently counts as a valid duplicate.
        await asyncio.to_thread(
            DocumentStorage(settings.document_storage_root).read,
            previous.storage_key,
            previous.content_sha256,
            settings.pdf_max_bytes,
        )
        await session.commit()
        return await get_document(session, previous.id), True
    latest = await session.scalar(
        select(DocumentVersion)
        .where(DocumentVersion.source_id == source.id)
        .order_by(DocumentVersion.version_number.desc())
        .limit(1)
    )
    identifier = uuid4()
    version = DocumentVersion(
        id=identifier,
        source_id=source.id,
        version_number=latest.version_number + 1 if latest else 1,
        content_sha256=checksum,
        content_length_bytes=len(content),
        media_type="application/pdf",
        storage_key=f"pdf/{source.id.hex}/{checksum}.pdf",
        retrieved_at=datetime.now(UTC),
        published_on=published_on,
        supersedes_id=latest.id if latest else None,
    )
    session.add(version)
    await session.flush()
    session.add(
        DocumentAsset(
            document_version_id=identifier,
            created_by=administrator.id,
            original_filename=name,
            acquisition_method=acquisition_method,
            page_count=inspected.page_count,
            pdf_metadata=inspected.metadata,
        )
    )
    audit(
        session,
        "document_registered",
        administrator.id,
        str(identifier),
        scheme_id=str(source.scheme_id),
        acquisition=acquisition_method,
    )
    # Bytes are immutable and private. A failed SQL commit can leave an unreferenced
    # original for operator reconciliation, never a partially registered version.
    await asyncio.to_thread(DocumentStorage(settings.document_storage_root).put, source.id, content)
    await session.commit()
    return await get_document(session, identifier), False


async def get_document(session: AsyncSession, identifier: UUID) -> DocumentRead:
    row = (
        await session.execute(
            select(DocumentVersion, DocumentAsset, SchemeSource, Scheme)
            .join(DocumentAsset, DocumentAsset.document_version_id == DocumentVersion.id)
            .join(SchemeSource, SchemeSource.id == DocumentVersion.source_id)
            .join(Scheme, Scheme.id == SchemeSource.scheme_id)
            .where(DocumentVersion.id == identifier)
        )
    ).first()
    if not row:
        raise HTTPException(404, "Ingested PDF document not found")
    version, asset, source, scheme = row
    return DocumentRead(
        id=version.id,
        scheme_id=scheme.id,
        scheme_name=scheme.name,
        source_id=source.id,
        source_url=source.url,
        original_filename=asset.original_filename,
        checksum=version.content_sha256,
        content_type=version.media_type,
        file_size=version.content_length_bytes,
        retrieved_at=version.retrieved_at,
        publication_date=version.published_on,
        version_number=version.version_number,
        supersedes_id=version.supersedes_id,
        storage_key=version.storage_key,
        page_count=asset.page_count,
        processing_status=asset.processing_status,
        acquisition_method=asset.acquisition_method,
        pdf_metadata=asset.pdf_metadata,
    )


async def recover_stale_jobs(session: AsyncSession, lease_seconds: float) -> int:
    jobs = list(
        await session.scalars(
            select(ProcessingJob)
            .where(
                ProcessingJob.status == "RUNNING",
                ProcessingJob.started_at < datetime.now(UTC) - timedelta(seconds=lease_seconds + 60),
            )
            .with_for_update()
        )
    )
    for job in jobs:
        job.status, job.finished_at = "FAILED", datetime.now(UTC)
        session.add(
            ExtractionError(
                job_id=job.id,
                code="processing_interrupted",
                message="Processing was interrupted or exceeded its lease. Start a new extraction; original history is preserved.",
            )
        )
    await session.commit()
    return len(jobs)


async def process_document(
    session: AsyncSession,
    settings: Settings,
    administrator: Administrator,
    identifier: UUID,
    mode: str,
    provider: LLMProvider | None = None,
) -> ProcessingJob:
    document = await get_document(session, identifier)
    await recover_stale_jobs(session, settings.processing_timeout)
    provider = provider or GeminiProvider(settings)
    job = ProcessingJob(
        document_version_id=identifier,
        requested_by=administrator.id,
        provider="none" if mode == "parse_only" else provider.name,
        model=None if mode == "parse_only" else provider.model,
    )
    session.add(job)
    audit(session, "document_extraction_started", administrator.id, str(identifier), provider=job.provider)
    try:
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(409, "A processing job is already running for this document") from error
    identifier_job = job.id
    try:
        async with asyncio.timeout(settings.processing_timeout):
            stored_pages = list(
                await session.scalars(
                    select(DocumentPage)
                    .where(DocumentPage.document_version_id == identifier)
                    .order_by(DocumentPage.page_number)
                )
            )
            issues = []
            if stored_pages:
                pages = [
                    ParsedPage(
                        page_number=item.page_number,
                        text_content=item.text_content,
                        blocks=item.blocks,
                        issues=item.issues,
                    )
                    for item in stored_pages
                ]
                issues = [issue for page in pages for issue in page.issues]
                if document.processing_status == "INCOMPLETE":
                    issues.append(
                        "An earlier parsing pass was incomplete; inspect its processing history and original PDF."
                    )
            else:
                content = await asyncio.to_thread(
                    DocumentStorage(settings.document_storage_root).read,
                    document.storage_key,
                    document.checksum,
                    settings.pdf_max_bytes,
                )
                parsed = await parse_pdf(
                    content,
                    max_pages=settings.pdf_max_pages,
                    max_chars=settings.pdf_max_text_chars,
                    timeout_seconds=settings.pdf_parse_timeout,
                )
                pages = parsed.pages
                issues = parsed.issues + [issue for page in pages for issue in page.issues]
                for page in pages:
                    session.add(
                        DocumentPage(
                            id=uuid5(identifier, f"page:{page.page_number}"),
                            document_version_id=identifier,
                            **page.model_dump(),
                        )
                    )
                await session.flush()
                for chunk_value in chunk_pages(
                    identifier, pages, settings.chunk_size, settings.chunk_overlap
                ):
                    session.add(DocumentChunk(document_version_id=identifier, **chunk_value))
                await session.execute(
                    update(DocumentAsset)
                    .where(DocumentAsset.document_version_id == identifier)
                    .values(processing_status="INCOMPLETE" if issues else "PARSED")
                )
                await session.commit()
            for issue in issues:
                session.add(ExtractionError(job_id=job.id, code="incomplete_extraction", message=issue))
            chunks = list(
                await session.scalars(
                    select(DocumentChunk)
                    .where(DocumentChunk.document_version_id == identifier)
                    .order_by(DocumentChunk.ordinal)
                )
            )
            await session.commit()
            if mode == "parse_only":
                job.status = "INCOMPLETE" if issues else "PARSED"
            elif not chunks:
                raise ProviderError(
                    "no_document_text",
                    "No extractable source text. Manual review/OCR is required before AI extraction.",
                )
            else:
                # Send page-aware chunk batches without ever crossing document or
                # scheme boundaries. Bounded budget omissions remain visible.
                batches: list[list[dict[str, Any]]] = []
                current: list[dict[str, Any]] = []
                size, total = 0, 0
                for chunk in chunks:
                    text_value = chunk.text_content
                    if total + len(text_value) > settings.gemini_max_input_chars:
                        issues.append(
                            "AI text budget exhausted; some chunks were not sent. Manual review is required."
                        )
                        break
                    if size + len(text_value) > 6500 and current:
                        batches.append(current)
                        current, size = [], 0
                    current.append(
                        {
                            "chunk_id": str(chunk.id),
                            "page_number": chunk.page_number,
                            "section_identifier": chunk.section_identifier,
                            "text": text_value,
                        }
                    )
                    size += len(text_value)
                    total += len(text_value)
                if current:
                    batches.append(current)
                if len(batches) > settings.gemini_max_requests:
                    issues.append("AI request count limit reached; extraction is incomplete.")
                    batches = batches[: settings.gemini_max_requests]
                validated = []
                relationships: list[str] = []
                seen = set()
                job.input_chunk_count = sum(len(batch) for batch in batches)
                job.input_manifest = [
                    {"batch_number": number + 1, "chunk_ids": [part["chunk_id"] for part in batch]}
                    for number, batch in enumerate(batches)
                ]
                await session.commit()
                for index, batch in enumerate(batches):
                    result = await provider.extract(
                        {
                            "scheme_id": str(document.scheme_id),
                            "source_document_version": str(identifier),
                            "batch_number": index + 1,
                            "document_page_count": document.page_count,
                            "sections": batch,
                        }
                    )
                    if result.scheme_id != document.scheme_id or result.source_document_version != identifier:
                        raise ProviderError(
                            "candidate_provenance_mismatch",
                            "AI output referenced a different scheme or document; no candidates were accepted.",
                        )
                    relationships.append(result.logical_relationship)
                    for item in validate_batch(result, pages):
                        item.source_batch_number = index + 1
                        # Cross-batch repeated labels need human consolidation;
                        # retain the distinct batch ID without overwriting history.
                        key = item.candidate.condition_identifier
                        if key in seen:
                            item.candidate.condition_identifier = f"b{index + 1}_{uuid4().hex[:8]}_{key}"[:64]
                            item.status = "NEEDS_REVIEW" if item.status == "VALIDATED" else item.status
                            item.issues.append(
                                "Repeated identifier across AI batches; review for duplicate conditions."
                            )
                        seen.add(item.candidate.condition_identifier)
                        validated.append(item)
                combined_logic = relationships[0] if len(relationships) == 1 else "unspecified"
                if len(relationships) > 1:
                    for item in validated:
                        item.issues.append(
                            "Logical scope across separate extraction batches is unverified; review against the complete policy."
                        )
                        if item.status == "VALIDATED":
                            item.status = "NEEDS_REVIEW"
                mark_conflicts(validated, combined_logic)
                if len(validated) > 128:
                    raise ProviderError("candidate_limit", "Candidate output exceeds the extraction limit.")
                # Candidates/evidence/errors commit together after all responses
                # are schema/provenance-validated. They never touch rule_sets.
                for item in validated:
                    record = RuleCandidate(
                        job_id=job.id,
                        document_version_id=identifier,
                        condition_identifier=item.candidate.condition_identifier,
                        label=item.candidate.label,
                        logical_relationship=item.logical_relationship,
                        payload=item.candidate.model_dump(mode="json")
                        | {
                            "source_batch_number": item.source_batch_number,
                            "cross_batch_logical_relationship": combined_logic,
                        },
                        mapped_expression=item.expression,
                        validation_status=item.status,
                        validation_issues=item.issues,
                    )
                    session.add(record)
                    await session.flush()
                    for node_key, number, excerpt in item.evidence:
                        session.add(
                            CandidateEvidence(
                                candidate_id=record.id,
                                document_version_id=identifier,
                                page_id=uuid5(identifier, f"page:{number}"),
                                node_key=node_key,
                                excerpt=excerpt,
                            )
                        )
                job.candidate_count = len(validated)
                if not validated:
                    issues.append(
                        "No structured eligibility candidates were extracted; manual review is required."
                    )
                for issue in issues:
                    session.add(ExtractionError(job_id=job.id, code="manual_review_required", message=issue))
                job.status = "INCOMPLETE" if issues else "PENDING_REVIEW"
            job.finished_at = datetime.now(UTC)
            audit(
                session,
                "document_extraction_finished",
                administrator.id,
                str(identifier),
                job_id=str(job.id),
                status=job.status,
                candidates=job.candidate_count,
            )
            await session.commit()
    except BaseException as error:
        await session.rollback()
        current_job = await session.get(ProcessingJob, identifier_job)
        assert current_job is not None
        current_job.status, current_job.finished_at = "FAILED", datetime.now(UTC)
        code = (
            error.code
            if isinstance(error, (ProviderError, IngestionError))
            else "processing_timeout"
            if isinstance(error, TimeoutError)
            else "processing_interrupted"
            if isinstance(error, asyncio.CancelledError)
            else "processing_failed"
        )
        message = (
            error.message
            if isinstance(error, (ProviderError, IngestionError))
            else "Processing could not finish safely. Original document and earlier history are preserved."
        )
        session.add(ExtractionError(job_id=identifier_job, code=code, message=message))
        audit(
            session,
            "document_extraction_failed",
            administrator.id,
            str(identifier),
            job_id=str(identifier_job),
            code=code,
        )
        await session.commit()
        job = current_job
        if isinstance(error, asyncio.CancelledError):
            raise
    return job
