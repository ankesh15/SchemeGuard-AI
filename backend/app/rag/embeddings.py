import asyncio
import hashlib
import math
import re
from typing import Protocol
from uuid import UUID, uuid5

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models import ChunkEmbedding, DocumentChunk


class EmbeddingError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class EmbeddingProvider(Protocol):
    name: str
    model: str

    async def embed(self, texts: list[str], *, query: bool = False) -> list[list[float]]: ...


def normalized_vector(value: list[float]) -> list[float]:
    if len(value) != 768 or any(type(item) not in {int, float} or not math.isfinite(item) for item in value):
        raise EmbeddingError("embedding_invalid_vector")
    norm = math.sqrt(sum(item * item for item in value))
    if not math.isfinite(norm) or norm <= 0:
        raise EmbeddingError("embedding_zero_vector")
    return [float(item / norm) for item in value]


class GeminiEmbeddings:
    name = "gemini"

    def __init__(self, settings: Settings):
        self.settings, self.model = settings, settings.embedding_model

    async def embed(self, texts: list[str], *, query: bool = False) -> list[list[float]]:
        from google import genai
        from google.genai import types

        if not self.settings.gemini_api_key or not self.settings.gemini_api_key.get_secret_value().strip():
            raise EmbeddingError("embedding_credentials_missing")
        if not 1 <= len(texts) <= 32 or sum(len(text) for text in texts) > 32_000:
            raise EmbeddingError("embedding_input_limit")
        for attempt in range(self.settings.embedding_max_retries + 1):
            try:
                async with asyncio.timeout(self.settings.embedding_timeout):
                    client = genai.Client(
                        api_key=self.settings.gemini_api_key.get_secret_value(),
                        http_options=types.HttpOptions(
                            timeout=int(self.settings.embedding_timeout * 1000),
                            retry_options=types.HttpRetryOptions(attempts=1),
                        ),
                    )
                    async with client.aio as asynchronous:
                        response = await asynchronous.models.embed_content(
                            model=self.model,
                            contents=texts,
                            config=types.EmbedContentConfig(
                                output_dimensionality=768,
                                task_type="RETRIEVAL_QUERY" if query else "RETRIEVAL_DOCUMENT",
                            ),
                        )
                    vectors = [normalized_vector(item.values or []) for item in response.embeddings or []]
                    if len(vectors) != len(texts):
                        raise EmbeddingError("embedding_invalid_response")
                    return vectors
            except EmbeddingError:
                raise
            except Exception as error:
                transient = (
                    isinstance(error, TimeoutError)
                    or "timeout" in type(error).__name__.lower()
                    or getattr(error, "code", None) in {429, 500, 502, 503, 504}
                )
                if transient and attempt < self.settings.embedding_max_retries:
                    await asyncio.sleep(min(0.5 * 2**attempt, 2))
                    continue
                raise EmbeddingError("embedding_provider_unavailable") from error
        raise EmbeddingError("embedding_provider_unavailable")


class LocalHashEmbeddings:
    """Explicit offline fixture: lexical feature hashing, NOT a semantic model."""

    name = "local_hash"
    model = "local-hash-v1"

    async def embed(self, texts: list[str], *, query: bool = False) -> list[list[float]]:
        result = []
        for text in texts:
            values = [0.0] * 768
            for word in re.findall(r"\w+", text.casefold()):
                digest = hashlib.sha256(word.encode()).digest()
                values[int.from_bytes(digest[:4], "big") % 768] += 1.0
            result.append(normalized_vector(values))
        return result


def embedding_provider(settings: Settings) -> EmbeddingProvider:
    if settings.embedding_provider == "local_hash":
        if settings.app_env == "production":
            raise EmbeddingError("fixture_provider_forbidden")
        return LocalHashEmbeddings()
    return GeminiEmbeddings(settings)


async def index_document(
    session: AsyncSession, document_id: UUID, provider: EmbeddingProvider, settings: Settings
) -> dict[str, int | str]:
    chunks = list(
        await session.scalars(
            select(DocumentChunk)
            .where(DocumentChunk.document_version_id == document_id)
            .order_by(DocumentChunk.ordinal)
        )
    )
    if not chunks or len(chunks) > settings.rag_max_chunks:
        raise EmbeddingError("embedding_chunk_limit_or_missing_text")
    existing = set(
        await session.scalars(
            select(ChunkEmbedding.chunk_id).where(
                ChunkEmbedding.chunk_id.in_([chunk.id for chunk in chunks]),
                ChunkEmbedding.provider == provider.name,
                ChunkEmbedding.model == provider.model,
            )
        )
    )
    pending = [chunk for chunk in chunks if chunk.id not in existing]
    try:
        # All embedding writes for this index operation commit together. No
        # partially indexed document is reported as a successful operation.
        batches = []
        current: list[DocumentChunk] = []
        size = 0
        for chunk in pending:
            if current and (len(current) >= 16 or size + len(chunk.text_content) > 30_000):
                batches.append(current)
                current = []
                size = 0
            current.append(chunk)
            size += len(chunk.text_content)
        if current:
            batches.append(current)
        async with asyncio.timeout(min(120, settings.workflow_timeout)):
            for batch in batches:
                vectors = await provider.embed([chunk.text_content for chunk in batch])
                if len(vectors) != len(batch):
                    raise EmbeddingError("embedding_invalid_response")
                for chunk, vector in zip(batch, vectors, strict=True):
                    vector = normalized_vector(vector)
                    await session.execute(
                        insert(ChunkEmbedding)
                        .values(
                            id=uuid5(chunk.id, f"{provider.name}:{provider.model}:768"),
                            chunk_id=chunk.id,
                            provider=provider.name,
                            model=provider.model,
                            dimensions=768,
                            content_sha256=chunk.content_sha256,
                            embedding=vector,
                        )
                        .on_conflict_do_nothing(
                            index_elements=[
                                ChunkEmbedding.chunk_id,
                                ChunkEmbedding.provider,
                                ChunkEmbedding.model,
                            ]
                        )
                    )
        await session.commit()
    except BaseException:
        await session.rollback()
        raise
    return {
        "document_version_id": str(document_id),
        "indexed": len(pending),
        "preserved": len(existing),
        "provider": provider.name,
        "model": provider.model,
        "dimensions": 768,
    }
