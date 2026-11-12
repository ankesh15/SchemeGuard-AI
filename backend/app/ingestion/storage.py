"""Private, content-addressed originals. User filenames never become paths."""

import hashlib
import os
from pathlib import Path
from uuid import UUID

from app.ingestion.validation import IngestionError


class DocumentStorage:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)

    def path(self, key: str) -> Path:
        candidate = self.root / key
        resolved = candidate.resolve()
        if (
            not resolved.is_relative_to(self.root)
            or candidate.is_symlink()
            or not key.startswith("pdf/")
            or any(part in {"..", "."} for part in key.split("/"))
        ):
            raise IngestionError("unsafe_storage_key", "Invalid document storage location.")
        return resolved

    def put(self, source_id: UUID, content: bytes) -> tuple[str, str]:
        checksum = hashlib.sha256(content).hexdigest()
        key = f"pdf/{source_id.hex}/{checksum}.pdf"
        target = self.path(key)
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        if target.exists():
            if hashlib.sha256(target.read_bytes()).hexdigest() != checksum:
                raise IngestionError(
                    "storage_integrity", "Stored original failed its checksum verification.", 503
                )
            return key, checksum
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
        except BaseException:
            target.unlink(missing_ok=True)
            raise
        return key, checksum

    def read(self, key: str, checksum: str, maximum: int) -> bytes:
        path = self.path(key)
        if not path.is_file():
            raise IngestionError(
                "storage_missing",
                "Preserved original is unavailable; operator reconciliation is required.",
                503,
            )
        if path.stat().st_size > maximum:
            raise IngestionError(
                "storage_integrity", "Stored original exceeds its configured size limit.", 503
            )
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != checksum:
            raise IngestionError(
                "storage_integrity", "Stored original failed its checksum verification.", 503
            )
        return content
