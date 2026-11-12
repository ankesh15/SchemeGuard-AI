# Official document processing — Phase 3

The pipeline accepts public official scheme PDFs through authenticated administration. It stores originals and traceable text, then proposes rules for future human review. It does not process citizen identity documents or publish government rules.

## Run and provision

```bash
python3 scripts/init_env.py
docker compose up --build -d
docker compose up -d --wait --wait-timeout 120
docker compose exec api alembic upgrade head
docker compose exec api python -m app.auth.provision --username reviewer
```

The provisioning command prompts for a hidden password of 12–1024 characters. It has no default password. The optional `--password-stdin` supports an operator's secret manager; never put passwords in command arguments. Use `--reset-password` explicitly to rotate an administrator password and revoke all its sessions. Existing citizen-role accounts cannot be promoted through this command. There is no registration HTTP endpoint.

Open [the workspace](http://localhost:3000/admin). The operator must verify the source's identity, correct scheme association, authorized public availability and exact final official PDF URL. Authorizing a source does **not** approve its policy rules. The source form records publisher/title and verification notes, preserving pre-existing scheme metadata and primary sources.

## Workflow

1. Select an existing government scheme and authorize its exact official URL. Fictional schemes are rejected for official ingestion. Existing directory sources alone do not authorize arbitrary downloads.
2. Upload a matching PDF with an explicit attestation, or download from the approved URL. The server accepts raw `application/pdf`, not multipart. JSON registration contains only the approved source ID and optional known publication date; it cannot override the URL.
3. Check signature, complete-file marker, byte/page limits, native parser recognition and encryption. Invalid files create no document version. Inspect metadata without assuming that PDF creation/modification dates equal policy publication dates.
4. Compute SHA-256 and register an existing `DocumentVersion`. Same source plus same bytes returns the existing ID and HTTP 200. New content creates the next version with same-source supersession; originals and prior versions remain intact.
5. Choose **Extract text only**. A bounded PyMuPDF subprocess extracts page text, blocks, identifiable headings, table text where detected, bounding boxes and conservative section tags for eligibility, exclusion, documents, deadlines and benefits. It does not infer policy values.
6. Preserve pages and deterministic, block-aware chunks in PostgreSQL. Chunk UUIDs include document identity, page/section/offsets, content hash and chunk algorithm version. Chunks never cross a page or document; overlap is configurable. Long indivisible conditions may still split and require review. No vector search or similarity-based eligibility is implemented.
7. Choose **Generate pending candidates** with configured Gemini credentials. Bounded chunk batches produce structured proposals mapped through the existing typed expression adapter. Validate fields, types, units, literal values, dates, logic, source pages, exact normalized excerpts and simple contradictions. Unknown semantics remain pending with issues.
8. Inspect status, processing errors, candidate nodes, uncertainties, expression previews and source-page evidence. Original PDFs download as authenticated attachments, never unsandboxed embedded HTML. No approve/publish control exists in Phase 3.

## Authenticated API contracts

All routes use `/api/v1/admin`. Every data/management route requires an active administrator session. Login itself requires an allowed Origin. Mutations require Origin plus `X-CSRF-Token`, returned by login/session. Cookies are HttpOnly, SameSite=Strict, eight-hour defaults, and Secure in production. Browser administration uses the fixed same-origin Next.js `/api/admin/*` proxy; public API contracts are unchanged.

| Method | Suffix | Behavior |
| --- | --- | --- |
| POST | `/auth/login` | Argon2id password verification, SQL-backed rate limit, rotated hashed-token session |
| GET | `/auth/session` | Current administrator and CSRF token; never password/hash |
| POST | `/auth/logout` | Revoke current session and expire cookie; 204 |
| GET | `/overview` | Counts, limits, supported extraction fields, Gemini configured boolean |
| POST / GET | `/sources` | Authorize exact official URL / list latest 100 authorizations; optional scheme filter |
| POST | `/sources/{id}/revoke` | Revoke future acquisition permission; 204; preserve source/history |
| POST | `/documents` | PDF upload or approved-source JSON download; 201 or duplicate 200 |
| GET | `/documents` | Paginated ingested PDF versions (`page`, `page_size` 1–100) |
| GET | `/documents/{id}` | Metadata, parsed-page summaries and recent processing history |
| GET | `/documents/{id}/original` | Checksum-verified original attachment with audit event |
| GET | `/documents/{id}/pages/{number}` | Text, blocks, chunks, methods, bounds and issues |
| POST | `/documents/{id}/extract` | `{"mode":"parse_only"}` or `{"mode":"gemini"}`; 201 processing job |
| GET | `/extractions/{id}` | Status, provider/model, counts and safe errors |
| GET | `/extractions/{id}/candidates` | Paginated pending proposals, mapped expressions, uncertainty and located page evidence |
| GET | `/audit` | Latest 100 safe administrator audit events |

Extraction is synchronous: HTTP 201 means a recorded job, including a job whose **status is FAILED**. Inspect the job status/errors; it does not imply successful generation. One RUNNING job per document is enforced in PostgreSQL; a concurrent request returns 409. Interrupted jobs past a bounded lease are marked FAILED before the next extraction request. Prior jobs/pages/candidates are retained. Retrying creates another job and reuses original parsed pages/chunks. A server restart has no autonomous job resumption in this phase.

Upload request example, using an existing session cookie jar and the returned CSRF token:

```bash
curl --fail 'http://localhost:8000/api/v1/admin/documents?source_id=SOURCE_UUID&original_filename=policy.pdf&attested=true' \
  -b /path/to/private-cookie-jar -H 'Origin: http://localhost:3000' \
  -H 'X-CSRF-Token: SESSION_CSRF_TOKEN' -H 'Content-Type: application/pdf' \
  --data-binary @/path/to/official-policy.pdf
```

Keep cookie files and shell inputs private. The interactive frontend is the preferred manual operating flow. Authentication failures use 401/403, invalid inputs 422/415, size limits 413, rate limits 429, unavailable services 502/503/504, unknown resources 404, and provenance/version conflicts 409. Error envelopes omit raw inputs and internal exception messages. Administrator responses use no-store.

## Configuration and persistence

Defaults: 10 MiB, 50 pages, 200,000 extracted characters, 25-second parser deadline, 15-second download deadline, 1,800-character chunks/160 overlap, 90-second processing deadline. Two concurrent document operations and two password verifications per API process limit expensive work. SQL limits bound login attempts per username/IP, ingestion per administrator and extraction per administrator. The proxy independently caps PDFs at 10 MiB and JSON at 16,000 bytes; raising the backend PDF limit alone does not raise the browser proxy limit.

All settings are in `.env.example` and Compose. Original PDF storage is `/var/lib/schemeguard/documents`, backed by named volume `document_data`. Paths are source UUID/hash based, never user filenames; originals are created with mode 0600 inside private directories. Database rows store paths, content hashes and lengths. Storage reads verify checksums. A failed SQL commit can leave an unreferenced private blob; an operator reconciliation tool is deferred. A failed parser/provider never overwrites old history. No volume reset is required or supported by this workflow.

## Security boundaries and limits

- Official allowlist validation requires HTTPS, recognized government/AICTE hosts, no credentials/custom ports/fragments. Source authorization pins the exact URL hash. Every resolved DNS answer must be public; TLS connects to the vetted IP with original hostname/SNI and certificate verification. No proxy environment, redirects or arbitrary user URL fetching is used by the application.
- This development environment resolves the NSP host to a non-public address. The downloader correctly rejects it; the supervised demonstration used an operator-downloaded official PDF through authenticated upload. No SSRF protection was disabled. Real public-origin download success remains environment dependent; mocked public-DNS/redirect behavior is tested.
- Byte/page/text/time/memory/CPU/file-descriptor/output limits defend against malformed PDFs. Parsing occurs outside the event loop and excludes application secrets from its environment. This subprocess is **not a complete OS sandbox against native-library exploits**. Production network/process isolation and continuous dependency patching remain necessary deployment work.
- Embedded attachments/scripts are not executed; PDF contents and model output are untrusted. Source text is rendered as escaped plain text. Image-only/blank/corrupted pages create explicit issues; no OCR or missing text is invented. Table extraction is best effort and requires visual comparison with the original.
- PostgreSQL stores hashed high-entropy session tokens and Argon2id password hashes. CSRF/origin checks complement HttpOnly cookies. Successful sensitive operations and authentication events are audited without passwords, cookies, API keys or applicant data. The development database owner remains privileged; role separation, distributed/edge rate limits, session cleanup and backup restore procedures are deferred.
- Processing is bounded synchronous async HTTP. Native parsing uses a subprocess; downloads and password hashing use thread offload; Gemini uses its async client. Large-scale work will need durable workers later. No Celery/Redis service or monitoring scheduler is introduced here.

See [the Phase 3 report](phase3-ai-ingestion.md) for actual demonstration IDs, counts, tests and remaining verification limits.

`0004_least_privilege` changes only the default role for future user rows to citizen. Existing administrator roles are preserved; the provisioning CLI explicitly assigns admin. This avoids accidental privilege grants when citizen accounts are introduced later. The current migration head is `0004_least_privilege`.
