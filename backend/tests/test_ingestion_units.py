import asyncio
import socket
from uuid import uuid4

import pytest

from app.ingestion.chunker import chunk_pages
from app.ingestion.fetcher import download
from app.ingestion.pdf_parser import parse_pdf
from app.ingestion.storage import DocumentStorage
from app.ingestion.validation import IngestionError, filename, official_url, pdf_bytes, public_address
from tests.ingestion_support import TEXT, pdf_content


async def parse(content, **options):
    return await parse_pdf(
        content,
        max_pages=options.get("max_pages", 50),
        max_chars=options.get("max_chars", 200000),
        timeout_seconds=25,
    )


async def test_real_parser_preserves_blocks_pages_and_stable_chunks():
    result = await parse(pdf_content(pages=2))
    assert result.page_count == 2 and not result.issues
    assert [page.page_number for page in result.pages] == [1, 2]
    assert result.pages[0].text_content == TEXT
    identifier = uuid4()
    chunks = chunk_pages(identifier, result.pages, 30, 5)
    assert chunks == chunk_pages(identifier, result.pages, 30, 5)
    assert all(len(chunk["text_content"]) <= 30 for chunk in chunks)
    assert len({chunk["id"] for chunk in chunks}) == len(chunks)
    assert chunks != chunk_pages(uuid4(), result.pages, 30, 5)
    assert {chunk["page_number"] for chunk in chunks} == {1, 2}
    assert all(chunk["bounding_box"] for chunk in chunks)


async def test_missing_text_is_incomplete_never_invented():
    result = await parse(pdf_content(text=""))
    assert result.pages[0].text_content == ""
    assert result.pages[0].issues
    assert chunk_pages(uuid4(), result.pages, 100, 10) == []


@pytest.mark.parametrize("content", [b"not a pdf", b"%PDF-1.7\ninvalid broken object\n%%EOF"])
async def test_malformed_pdf_fails_closed(content):
    with pytest.raises(IngestionError):
        await parse(content)


async def test_pdf_page_and_text_limits():
    with pytest.raises(IngestionError, match="page count"):
        await parse(pdf_content(pages=2), max_pages=1)
    with pytest.raises(IngestionError, match="text exceeds"):
        await parse(pdf_content(), max_chars=10)


def test_byte_limit_and_file_signature():
    with pytest.raises(IngestionError) as error:
        pdf_bytes(pdf_content(), 10)
    assert error.value.status == 413
    with pytest.raises(IngestionError):
        pdf_bytes(b"<html>fake.pdf</html>", 10000)


@pytest.mark.parametrize("value", ["../test.pdf", "a\\b.pdf", "evil\x00.pdf", "x.txt", ".", "a\n.pdf"])
def test_path_traversal_and_bad_filenames(value):
    with pytest.raises(IngestionError):
        filename(value)


@pytest.mark.parametrize(
    "value",
    [
        "http://gov.in/a.pdf",
        "https://127.0.0.1/a.pdf",
        "https://evil.example/gov.in/a.pdf",
        "https://a.gov.in.evil.example/a.pdf",
        "https://user:pwd@a.gov.in/a.pdf",
        "https://a.gov.in:444/a.pdf",
        "https://a.gov.in/a.pdf#x",
        "file:///tmp/a.pdf",
    ],
)
def test_unsafe_source_urls(value):
    with pytest.raises(IngestionError):
        official_url(value)


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "::1",
        "10.1.0.1",
        "169.254.169.254",
        "192.168.1.1",
        "100.64.0.1",
        "0.0.0.0",
        "224.0.0.1",
        "fc00::1",
        "::ffff:127.0.0.1",
    ],
)
def test_nonpublic_addresses(address):
    assert not public_address(address)


def test_dns_private_answer_is_rejected_even_with_public_answer(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(2, 1, 6, "", ("8.8.8.8", 443)), (2, 1, 6, "", ("127.0.0.1", 443))],
    )
    with pytest.raises(IngestionError) as error:
        download("https://a.gov.in/doc.pdf", 10000, 2)
    assert error.value.code == "unsafe_destination"


def test_redirects_are_never_followed(monkeypatch):
    from app.ingestion import fetcher

    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [(2, 1, 6, "", ("8.8.8.8", 443))])

    class Connection:
        def __init__(self, host, address, timeout):
            assert host == "a.gov.in" and address == "8.8.8.8"

        def request(self, *args, **kwargs):
            pass

        def getresponse(self):
            return type("Redirect", (), {"status": 302})()

        def close(self):
            pass

    monkeypatch.setattr(fetcher, "PinnedHTTPSConnection", Connection)
    with pytest.raises(IngestionError) as error:
        download("https://a.gov.in/doc.pdf", 10000, 2)
    assert error.value.code == "redirect_rejected"


@pytest.mark.parametrize(
    "content_type,maximum,expected_error",
    [
        ("application/pdf", 10000, None),
        ("text/html", 10000, "not_pdf_content_type"),
        ("application/pdf", 10, "pdf_too_large"),
    ],
)
def test_pinned_download_checks_response_type_and_byte_budget(
    monkeypatch, content_type, maximum, expected_error
):
    import io

    from app.ingestion import fetcher

    content = pdf_content()
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: [(2, 1, 6, "", ("8.8.8.8", 443))])

    class Response(io.BytesIO):
        status = 200

        def getheader(self, key, default=None):
            return {"Content-Type": content_type, "Content-Length": str(len(content))}.get(key, default)

    class Connection:
        def __init__(self, host, address, timeout):
            assert host == "a.gov.in" and address == "8.8.8.8"

        def request(self, method, path, headers):
            assert method == "GET" and path == "/doc.pdf?version=1"

        def getresponse(self):
            return Response(content)

        def close(self):
            pass

    monkeypatch.setattr(fetcher, "PinnedHTTPSConnection", Connection)
    if expected_error:
        with pytest.raises(IngestionError) as error:
            download("https://a.gov.in/doc.pdf?version=1", maximum, 2)
        assert error.value.code == expected_error
    else:
        assert download("https://a.gov.in/doc.pdf?version=1", maximum, 2) == (content, "doc.pdf")


def test_storage_is_immutable_private_and_checksum_verified(tmp_path):
    storage = DocumentStorage(tmp_path)
    source = uuid4()
    content = pdf_content()
    key, checksum = storage.put(source, content)
    import hashlib

    checksum = hashlib.sha256(content).hexdigest()
    assert storage.put(source, content) == (key, checksum)
    assert storage.read(key, checksum, len(content)) == content
    assert (tmp_path / key).stat().st_mode & 0o777 == 0o600
    with pytest.raises(IngestionError):
        storage.read("../outside.pdf", checksum, 10000)
    (tmp_path / key).write_bytes(b"tampered")
    with pytest.raises(IngestionError):
        storage.read(key, checksum, 10000)


async def test_parse_timeout_kills_subprocess(monkeypatch):
    from app.ingestion import pdf_parser

    class Process:
        killed = False

        async def wait(self):
            if not self.killed:
                await asyncio.sleep(1)

        def kill(self):
            self.killed = True

    process = Process()

    async def spawn(*args, **kwargs):
        return process

    monkeypatch.setattr(pdf_parser.asyncio, "create_subprocess_exec", spawn)
    with pytest.raises(IngestionError) as error:
        await parse_pdf(pdf_content(), max_pages=1, max_chars=1000, timeout_seconds=0.01)
    assert error.value.code == "pdf_parse_timeout" and process.killed
