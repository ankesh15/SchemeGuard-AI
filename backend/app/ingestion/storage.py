"""Private, content-addressed originals. User filenames never become paths."""

import hashlib
import os
from functools import cached_property
from pathlib import Path
from typing import Any
from uuid import UUID

from app.core.config import Settings
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


class S3DocumentStorage:
    """Private content-addressed objects; no public ACLs, presigned URLs or overwrites."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.bucket = settings.s3_bucket
        self.prefix = settings.s3_prefix

    @cached_property
    def client(self) -> Any:
        import boto3
        from botocore.config import Config

        return boto3.client(
            "s3",
            region_name=self.settings.s3_region,
            endpoint_url=self.settings.s3_endpoint_url,
            config=Config(
                connect_timeout=5, read_timeout=20, retries={"max_attempts": 2, "mode": "standard"}
            ),
        )

    def object_key(self, key: str) -> str:
        import re

        if not re.fullmatch(r"pdf/[a-f0-9]{32}/[a-f0-9]{64}\.pdf", key):
            raise IngestionError("unsafe_storage_key", "Invalid document storage location.")
        return f"{self.prefix}/{key}"

    def put(self, source_id: UUID, content: bytes) -> tuple[str, str]:
        from botocore.exceptions import BotoCoreError, ClientError

        checksum = hashlib.sha256(content).hexdigest()
        key = f"pdf/{source_id.hex}/{checksum}.pdf"
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=self.object_key(key),
                Body=content,
                ContentType="application/pdf",
                IfNoneMatch="*",
                ServerSideEncryption="AES256",
                Metadata={"sha256": checksum},
            )
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") in {
                "PreconditionFailed",
                "412",
                "ConditionalRequestConflict",
                "409",
            }:
                self.read(key, checksum, len(content))
            else:
                raise IngestionError(
                    "object_storage_unavailable", "Private object storage is unavailable.", 503
                ) from error
        except BotoCoreError as error:
            raise IngestionError(
                "object_storage_unavailable", "Private object storage is unavailable.", 503
            ) from error
        return key, checksum

    def read(self, key: str, checksum: str, maximum: int) -> bytes:
        from botocore.exceptions import BotoCoreError, ClientError

        try:
            response = self.client.get_object(Bucket=self.bucket, Key=self.object_key(key))
            stream = response["Body"]
            try:
                if response.get("ContentLength", maximum + 1) > maximum:
                    raise IngestionError("storage_integrity", "Stored original exceeds its byte limit.", 503)
                content: bytes = stream.read(maximum + 1)
            finally:
                stream.close()
        except (BotoCoreError, ClientError) as error:
            raise IngestionError(
                "object_storage_unavailable", "Private object storage is unavailable.", 503
            ) from error
        if len(content) > maximum or hashlib.sha256(content).hexdigest() != checksum:
            raise IngestionError("storage_integrity", "Stored original failed checksum verification.", 503)
        return content


def document_storage(settings: Settings) -> DocumentStorage | S3DocumentStorage:
    return (
        S3DocumentStorage(settings)
        if settings.document_storage_backend == "s3"
        else DocumentStorage(settings.document_storage_root)
    )
