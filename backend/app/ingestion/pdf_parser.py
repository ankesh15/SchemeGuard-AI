"""PyMuPDF runs only in a bounded subprocess; never render PDF HTML or scripts."""

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.ingestion.validation import IngestionError


class ParsedPage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page_number: int
    text_content: str
    blocks: list[dict[str, Any]]
    issues: list[str]


class ParsedPDF(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page_count: int
    metadata: dict[str, str]
    pages: list[ParsedPage]
    issues: list[str]


async def parse_pdf(
    content: bytes, *, max_pages: int, max_chars: int, timeout_seconds: float, inspect_only: bool = False
) -> ParsedPDF:
    # A separate process limits CPU/memory and isolates PyMuPDF's native parser.
    with tempfile.TemporaryDirectory(prefix="schemeguard-pdf-") as directory:
        source, output = Path(directory) / "input.pdf", Path(directory) / "parsed.json"
        source.write_bytes(content)
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "app.ingestion.pdf_worker",
            str(source),
            str(output),
            str(max_pages),
            str(max_chars),
            "inspect" if inspect_only else "parse",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            env={"PATH": os.defpath, "LANG": "C.UTF-8", "PYTHONHASHSEED": "0", "PYTHONNOUSERSITE": "1"},
        )
        try:
            await asyncio.wait_for(process.wait(), timeout_seconds)
        except (TimeoutError, asyncio.CancelledError):
            process.kill()
            await process.wait()
            task = asyncio.current_task()
            if task and task.cancelling():
                raise
            raise IngestionError("pdf_parse_timeout", "PDF parsing exceeded the time limit.") from None
        if not output.exists() or output.stat().st_size > max_chars * 12 + 2_000_000:
            raise IngestionError("malformed_pdf", "PDF could not be safely parsed within resource limits.")
        value = json.loads(output.read_text())
        if "error" in value:
            raise IngestionError(value["error"], value["message"])
        return ParsedPDF.model_validate(value)
