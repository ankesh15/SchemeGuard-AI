import re
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import (
    ChunkEmbedding,
    DocumentChunk,
    DocumentPage,
    DocumentVersion,
    RuleSet,
    SchemeSource,
)
from app.rag.citations import SourceCitation, page_url
from app.rag.embeddings import EmbeddingError, EmbeddingProvider, normalized_vector
from app.rag.grounding import query_terms


async def retrieve_for_rule(
    session: AsyncSession,
    settings: Settings,
    provider: EmbeddingProvider,
    scheme_id: UUID,
    rule_set_id: UUID,
    question: str,
    *,
    document_version_id: UUID | None = None,
) -> tuple[list[SourceCitation], str]:
    # Rule/document/scheme restrictions are SQL predicates, never LLM prompts.
    rule = await session.get(RuleSet, rule_set_id)
    if (
        not rule
        or rule.scheme_id != scheme_id
        or rule.approval_status != "APPROVED"
        or (document_version_id and document_version_id != rule.source_document_version_id)
    ):
        return [], "no_approved_source"
    document = await session.get(DocumentVersion, rule.source_document_version_id)
    assert document is not None
    source = await session.get(SchemeSource, document.source_id)
    if not source or source.scheme_id != scheme_id:
        return [], "source_scope_mismatch"
    base = (
        select(DocumentChunk)
        .join(DocumentVersion, DocumentVersion.id == DocumentChunk.document_version_id)
        .join(SchemeSource, SchemeSource.id == DocumentVersion.source_id)
        .where(DocumentChunk.document_version_id == document.id, SchemeSource.scheme_id == scheme_id)
    )
    mode = "vector"
    chunks = []
    try:
        vectors = await provider.embed([question], query=True)
        if len(vectors) != 1:
            raise EmbeddingError("embedding_invalid_response")
        distance = ChunkEmbedding.embedding.cosine_distance(normalized_vector(vectors[0]))
        ranked = (
            base.join(ChunkEmbedding, ChunkEmbedding.chunk_id == DocumentChunk.id)
            .where(
                ChunkEmbedding.provider == provider.name,
                ChunkEmbedding.model == provider.model,
                ChunkEmbedding.content_sha256 == DocumentChunk.content_sha256,
            )
            .add_columns(distance.label("distance"))
            .order_by(distance, DocumentChunk.ordinal)
            .limit(settings.rag_top_k)
        )
        rows = (await session.execute(ranked)).all()
        threshold = 0.0 if provider.name == "local_hash" else settings.rag_min_similarity
        chunks = [chunk for chunk, score in rows if score is not None and 1 - float(score) >= threshold]
        if provider.name == "local_hash":
            mode = "local_fixture_vector"
        if not chunks:
            mode = "lexical_fallback"
    except (EmbeddingError, TimeoutError):
        mode = "lexical_fallback"
    if not chunks:
        # Bounded fallback uses only this approved document, without inventing a
        # semantic embedding or calling an unrelated scheme authoritative.
        all_chunks = list(
            await session.scalars(base.order_by(DocumentChunk.ordinal).limit(settings.rag_max_chunks))
        )
        terms = query_terms(question)
        scored = [
            (len(terms & set(re.findall(r"\w+", chunk.text_content.casefold()))), chunk)
            for chunk in all_chunks
        ]
        chunks = [
            chunk
            for score, chunk in sorted(scored, key=lambda pair: (-pair[0], pair[1].ordinal))
            if score > 0
        ][: settings.rag_top_k]
    citations = []
    for chunk in chunks:
        page = await session.get(DocumentPage, chunk.page_id)
        if not page or page.document_version_id != document.id or page.page_number != chunk.page_number:
            continue
        if not any(
            chunk.text_content in value
            for value in [page.text_content, *[str(block["text"]) for block in page.blocks]]
        ):
            continue
        excerpt = chunk.text_content[:1200]
        citations.append(
            SourceCitation(
                id=f"chunk:{chunk.id}",
                scheme_id=scheme_id,
                document_version_id=document.id,
                document_sha256=document.content_sha256,
                chunk_id=chunk.id,
                page_number=chunk.page_number,
                locator=chunk.section_identifier,
                excerpt=excerpt,
                source_title=source.title,
                publisher=source.publisher,
                source_url=source.url,
                url=page_url(source.url, chunk.page_number),
                approved_rule_set_id=rule.id,
            )
        )
    return citations, mode
