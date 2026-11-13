"""No redirects/proxies. Resolve once, reject non-public IPs, pin TLS to that IP."""

import asyncio
import http.client
import socket
import ssl
import time
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit

from app.ingestion.validation import IngestionError, filename, official_url, pdf_bytes, public_address


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, address: str, timeout: float):
        self.tls_context = ssl.create_default_context()
        super().__init__(host, timeout=timeout, context=self.tls_context)
        self.address = address

    def connect(self) -> None:
        sock = socket.create_connection((self.address, 443), timeout=self.timeout)
        try:
            self.sock = self.tls_context.wrap_socket(sock, server_hostname=self.host)
        except BaseException:
            sock.close()
            raise


@dataclass(frozen=True)
class FetchResponse:
    status: int
    content: bytes
    filename: str
    etag: str | None = None
    last_modified: str | None = None


def safe_validator(value: str | None) -> str | None:
    return (
        value
        if value and len(value) <= 512 and all(32 <= ord(character) < 127 for character in value)
        else None
    )


def download_response(
    url: str, maximum: int, timeout: float, etag: str | None = None, last_modified: str | None = None
) -> FetchResponse:
    parsed = urlsplit(official_url(url))
    host = parsed.hostname or ""
    started = time.monotonic()
    try:
        answers = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        addresses = list(dict.fromkeys(str(answer[4][0]) for answer in answers))
        if not addresses or len(addresses) > 16 or any(not public_address(address) for address in addresses):
            raise IngestionError(
                "unsafe_destination", "The approved host resolves to a non-public destination."
            )
        addresses.sort(key=lambda address: ":" in address)
        # Every resolved answer was checked; the socket never resolves host again.
        connection = PinnedHTTPSConnection(
            host, addresses[0], max(0.1, timeout - (time.monotonic() - started))
        )
        try:
            conditional: dict[str, str] = {}
            if safe_validator(etag):
                conditional["If-None-Match"] = str(etag)
            if safe_validator(last_modified):
                conditional["If-Modified-Since"] = str(last_modified)
            connection.request(
                "GET",
                parsed.path + ("?" + parsed.query if parsed.query else ""),
                headers={
                    "Accept": "application/pdf",
                    "User-Agent": "SchemeGuard-AI/0.3 supervised-document-ingestion",
                    "Accept-Encoding": "identity",
                    **conditional,
                },
            )
            response = connection.getresponse()
            if 300 <= response.status < 400 and response.status != 304:
                raise IngestionError(
                    "redirect_rejected",
                    "Redirects are not followed. Approve the final official URL separately.",
                )
            response_etag = safe_validator(response.getheader("ETag"))
            response_modified = safe_validator(response.getheader("Last-Modified"))
            if response.status == 304 and conditional:
                return FetchResponse(304, b"", "official-document.pdf", response_etag, response_modified)
            if 300 <= response.status < 400:
                raise IngestionError(
                    "redirect_rejected",
                    "Redirects are not followed. Approve the final official URL separately.",
                )
            if response.status != 200:
                raise IngestionError(
                    "source_unavailable", "The approved official document could not be downloaded.", 502
                )
            if response.getheader("Content-Type", "").split(";")[0].strip().lower() != "application/pdf":
                raise IngestionError(
                    "not_pdf_content_type", "The official source did not return application/pdf."
                )
            length = response.getheader("Content-Length")
            if length and (not length.isdecimal() or int(length) > maximum):
                raise IngestionError(
                    "pdf_too_large", "The remote PDF exceeds the configured byte limit.", 413
                )
            parts, size = [], 0
            while True:
                if time.monotonic() - started > timeout:
                    raise IngestionError("download_timeout", "Official document download timed out.", 504)
                part = response.read(min(65536, maximum + 1 - size))
                if not part:
                    break
                size += len(part)
                if size > maximum:
                    raise IngestionError(
                        "pdf_too_large", "The remote PDF exceeds the configured byte limit.", 413
                    )
                parts.append(part)
            content = b"".join(parts)
            pdf_bytes(content, maximum)
            basename = unquote(parsed.path.rsplit("/", 1)[-1]) or "official-document.pdf"
            if not basename.lower().endswith(".pdf"):
                basename = "official-document.pdf"
            return FetchResponse(200, content, filename(basename), response_etag, response_modified)
        finally:
            connection.close()
    except IngestionError:
        raise
    except (OSError, http.client.HTTPException, ValueError) as error:
        raise IngestionError("download_failed", "Official document download failed securely.", 502) from error


def download(url: str, maximum: int, timeout: float) -> tuple[bytes, str]:
    response = download_response(url, maximum, timeout)
    return response.content, response.filename


async def fetch_pdf_response(
    url: str, maximum: int, timeout_seconds: float, etag: str | None = None, last_modified: str | None = None
) -> FetchResponse:
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(download_response, url, maximum, timeout_seconds, etag, last_modified),
            timeout=timeout_seconds + 1,
        )
    except TimeoutError as error:
        raise IngestionError("download_timeout", "Official document download timed out.", 504) from error


async def fetch_pdf(url: str, maximum: int, timeout_seconds: float) -> tuple[bytes, str]:
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(download, url, maximum, timeout_seconds), timeout=timeout_seconds + 1
        )
    except TimeoutError as error:
        raise IngestionError("download_timeout", "Official document download timed out.", 504) from error
