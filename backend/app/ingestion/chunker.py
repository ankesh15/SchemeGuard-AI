"""Deterministic block-aware chunks. Every chunk belongs to one page/document."""

import hashlib
from typing import Any
from uuid import UUID, uuid5

from app.ingestion.pdf_parser import ParsedPage


def chunk_pages(document_id: UUID, pages: list[ParsedPage], size: int, overlap: int) -> list[dict[str, Any]]:
    if size < 1 or not 0 <= overlap < size:
        raise ValueError("Invalid chunk size/overlap")
    chunks: list[dict[str, Any]] = []
    for page in pages:
        for block in page.blocks:
            content = block["text"]
            start = 0
            while start < len(content):
                end = min(start + size, len(content))
                if end < len(content):
                    # Prefer full sentences/lines. Long indivisible conditions
                    # still split at bounded size with overlap and a visible tag.
                    boundary = max(
                        content.rfind("\n", start + size // 2, end),
                        content.rfind(". ", start + size // 2, end),
                    )
                    if boundary > start:
                        end = boundary + 1
                text = content[start:end]
                checksum = hashlib.sha256(text.encode()).hexdigest()
                section = block["section_identifier"]
                chunks.append(
                    {
                        "id": uuid5(
                            document_id, f"chunk-v1:{page.page_number}:{section}:{start}:{end}:{checksum}"
                        ),
                        "page_id": uuid5(document_id, f"page:{page.page_number}"),
                        "page_number": page.page_number,
                        "ordinal": len(chunks),
                        "section_identifier": section,
                        "text_content": text,
                        "content_sha256": checksum,
                        "char_start": start,
                        "char_end": end,
                        "extraction_method": block["extraction_method"],
                        "bounding_box": block.get("bbox"),
                    }
                )
                if end == len(content):
                    break
                start = max(start + 1, end - overlap)
    return chunks
