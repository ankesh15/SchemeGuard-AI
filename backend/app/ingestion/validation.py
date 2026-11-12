import ipaddress
from pathlib import PurePosixPath

from pydantic import HttpUrl, TypeAdapter

from app.schemas.seed import SourceSeed


class IngestionError(ValueError):
    def __init__(self, code: str, message: str, status: int = 422):
        self.code, self.message, self.status = code, message, status
        super().__init__(message)


def official_url(value: str) -> str:
    try:
        url = SourceSeed.official_https_source(TypeAdapter(HttpUrl).validate_python(value))
        if url.fragment:
            raise ValueError("URL fragments are not permitted")
        return str(url)
    except ValueError as error:
        raise IngestionError(
            "unsafe_source_url", "Use an official HTTPS URL without credentials, fragments, or custom ports."
        ) from error


def public_address(value: str) -> bool:
    address = ipaddress.ip_address(value.split("%", 1)[0])
    return address.is_global and not (
        address.is_multicast
        or address.is_reserved
        or address.is_unspecified
        or address.is_loopback
        or address.is_link_local
        or address.is_private
    )


def filename(value: str) -> str:
    if (
        not value
        or len(value) > 255
        or any(ord(char) < 32 for char in value)
        or any(char in value for char in ("/", "\\", "\x00"))
        or PurePosixPath(value).name != value
        or value in {".", ".."}
        or not value.lower().endswith(".pdf")
    ):
        raise IngestionError("invalid_filename", "Use a plain PDF filename without directory components.")
    return value


def pdf_bytes(content: bytes, limit: int) -> None:
    if len(content) > limit:
        raise IngestionError("pdf_too_large", "PDF exceeds the configured byte limit.", 413)
    if len(content) < 20 or not content.startswith(b"%PDF-") or b"%%EOF" not in content[-2048:]:
        raise IngestionError("invalid_pdf", "The file does not contain a complete PDF document.")
