# Phase 3 implementation and completion report

Verified on 13 November 2026 (Asia/Kolkata; container logs use UTC). Phase 3 is implemented and verified in the explicitly permitted **mock-Gemini demonstration mode**. A live Gemini response was not verified because no API key was available. No Phase 4 publication or next-phase services were started.

## Repository inspection and preserved architecture

Before edits, the actual running Compose stack, complete backend/frontend tree, datasets, migrations, rule schemas, models, repository/service/API conventions and tests were inspected. All three existing services were healthy. The baseline PostgreSQL regression suite executed **230 tests successfully**. The actual database had **283 schemes: 282 government records and one fictional fixture**, not an assumed 300 government schemes.

The existing six domain tables were Scheme, SchemeSource, DocumentVersion, RuleSet, RuleCondition and RuleEvidence. DocumentVersion already owned immutable source-version hashes, sizes, storage keys, dates and supersession. RuleSet/conditions/evidence already owned immutable executable policy, approved-version selection and deterministic expression schemas. These representations were reused; the pipeline does not duplicate approved rules into another executable engine.

The existing engine's comparison/AND/OR/exclusion/conditional schema, Pydantic adapter, Decimal/date semantics and PASS/FAIL/UNKNOWN behavior remain unchanged. Public scheme APIs retain pagination, search, facets, state/category filters, details, evidence and `eligibility_available`. The category datasets remain 282 government records across 23 JSON files. No government threshold, deadline, scheme record or application URL was added to those datasets.

Next.js remains the existing App Router/TypeScript/Tailwind application with its public explorer, details, questionnaire, report and visual design. An `/admin` subtree and fixed same-origin administrator API proxy extend it. Docker remains exactly frontend/API/PostgreSQL, with non-root application users and development hot reload. No Celery, Redis, pgvector, OCR service, notifications or monitoring container was introduced.

## Implemented functionality

- Exact official-source authorization tied to an existing government scheme, recorded verification notes and administrator audit identity. Pre-existing source URLs require explicit authorization before acquisition; source authorization does not approve eligibility rules.
- Authenticated raw-PDF upload with a matching-source attestation, or approved-source download. File-content validation, bounded size/page count, timeouts, private-IP/DNS rejection, pinned TLS connections, no redirects/proxies, safe filenames and content-addressed private storage.
- Existing DocumentVersion registration, SHA-256, raw PDF metadata, retrieval timestamp, optional known publication date, same-source versioning/supersession and idempotent duplicate detection. Unknown publication dates remain null.
- PyMuPDF text/block/heading/table extraction in a bounded subprocess. Per-page methods, issues, section tags, source text and bounding boxes are preserved. Blank/image-only/corrupted content is reported for manual review without invented text.
- Stable page-aware chunks with hashes, offsets, section/method/bounding-box metadata and job input manifests, ready for later retrieval integration. No similarity-based eligibility decision is introduced.
- Official Google GenAI SDK provider abstraction, structured Pydantic output, bounded requests/output/retries/timeouts, safe errors, missing-key handling and mocked-provider testing. SDK tools, function calling and automatic continuation are disabled.
- Candidate graph mapping into the existing engine schema; supported vocabulary/types/operators/units/date checks; located evidence for every comparison; simple conflict detection; uncertainty and unsupported conditions retained for review. Per-batch logical scope is preserved, while relationships across separate batches remain unverified.
- Pending-only candidate/evidence storage isolated from RuleSet/RuleCondition/RuleEvidence. VALIDATED is a technical check, never approval. Database checks and append-only guards prevent publication or mutation of candidate/evidence history through this phase.
- CLI-only administrator provisioning/reset, Argon2id passwords, hashed high-entropy sessions, HttpOnly/SameSite cookies, production Secure cookies/HTTPS origins, CSRF and origin checks, SQL rate limits, administrator authorization, bounded expensive-operation concurrency and audit events. Future account rows default to citizen; there is no public account registration route.
- Protected overview, source management, upload, document/page evidence, extraction history, candidate preview, uncertainty/errors, original download and sign-out screens. Loading/error/retry/responsive states preserve the established design. No approve/publish UI or API exists.

## Incremental migrations and storage

| Revision | Changes |
| --- | --- |
| `0003_ai_ingestion` | Adds 12 processing/authentication tables, FKs/composite provenance constraints, unique/index/check constraints, pending-only candidate state, RUNNING-job uniqueness and append-only evidence/audit guards |
| `0004_least_privilege` | Changes only the default role for future user rows to citizen; existing roles remain unchanged |

The current head is `0004_least_privilege`. Earlier migrations 0001/0002 were not edited. New tables: users, login_sessions, rate_limits, audit_events, source_authorizations, document_assets, document_pages, document_chunks, document_processing_jobs, extracted_rule_candidates, candidate_evidence and extraction_errors. The existing PostgreSQL volume was retained. The new private `document_data` volume preserves original PDFs at `/var/lib/schemeguard/documents`.

Registration commits a document/asset/audit transaction; candidate/evidence writes commit together only after all provider batches pass schema/provenance checks. Parsing is a separate durable stage so a provider failure preserves source text. Failed provider batches store no partial candidates. A failed SQL commit can leave an unreferenced private content-addressed blob for operator reconciliation; it never overwrites an old version.

## APIs added

All management routes use `/api/v1/admin` and administrator authorization. Login has explicit origin/rate checks; all other mutations also require CSRF. Full request/status contracts are in [document-processing.md](document-processing.md).

| Method | Path |
| --- | --- |
| POST | `/api/v1/admin/auth/login` |
| GET | `/api/v1/admin/auth/session` |
| POST | `/api/v1/admin/auth/logout` |
| GET | `/api/v1/admin/overview` |
| POST / GET | `/api/v1/admin/sources` |
| POST | `/api/v1/admin/sources/{id}/revoke` |
| POST / GET | `/api/v1/admin/documents` |
| GET | `/api/v1/admin/documents/{id}` |
| GET | `/api/v1/admin/documents/{id}/original` |
| GET | `/api/v1/admin/documents/{id}/pages/{number}` |
| POST | `/api/v1/admin/documents/{id}/extract` |
| GET | `/api/v1/admin/extractions/{id}` |
| GET | `/api/v1/admin/extractions/{id}/candidates` |
| GET | `/api/v1/admin/audit` |

Next.js `/api/admin/*` is a fixed-upstream same-origin proxy, not an alternative authorization boundary. The API still validates every administrator request independently. Public Phase 1/2 contracts are unchanged.

## Supervised official-document demonstration

The [official NSP-hosted AICTE Saksham degree guideline](https://scholarships.gov.in/public/schemeGuidelines/AICTE/AICTE_2012_G.pdf) is a historical July 2020 document. Its original cover and page 2 were visually checked. This demonstration does not reconcile it with current notices/FAQs and does not approve its rules.

| Property | Actual result |
| --- | --- |
| Scheme | AICTE Saksham Scholarship for Specially Abled Students (Technical Degree) |
| Scheme UUID | `557ae037-9b67-5eb1-9b1f-9ca68888c570` |
| Document version UUID | `fb71dd58-7e39-4f21-92f3-b11dbf6e9386` |
| Document version | 1 for this newly authorized official source |
| Original size | 510,568 bytes |
| SHA-256 | `06ebed9e50a47ae76cba985ddde78cd65f19f2193b0e4c9c164fff529580474c` |
| Parsed content | 4 pages, 26 stable chunks |
| Publication date | null; the cover gives a month/year, not an exact calendar date |
| Acquisition | Operator downloaded the official public PDF, then uploaded through authenticated Next.js proxy/API |
| Duplicate upload | Existing document UUID preserved; no extra version |
| Text-only job | PARSED |
| Real Gemini request path | FAILED with visible `gemini_credentials_missing`; zero candidates |
| Mock extraction job | `ae7902f8-f58d-4469-8c23-fffeddcc8d74`, provider `fixture`, model `supervised-mock-historical-saksham` |
| Mock candidate | One historical disability-percentage condition grounded on page 2; NEEDS_REVIEW and PENDING |
| Executable government rules created | **0** |

The demonstration excerpt is “Specially-abled student, having disability of not less than 40%.” It was located in the stored original page, mapped to a candidate preview only, and accompanied by historical/current-applicability uncertainty. No broader eligibility conclusion is inferred from this single condition. The mock adapter is operator-only, source/scheme-restricted, disabled in production, and never an HTTP mode or automatic fallback.

This environment resolves the official NSP host to a non-public destination when using application DNS. The application's downloader correctly rejected that address. The demonstration used the separate administrator upload flow; SSRF checks were not bypassed or weakened. Successful public-IP download behavior is tested with deterministic network fixtures; a live download through the restricted application network was not verified.

## Actual database state and preservation

| Table / classification | Before Phase 3 | After demonstration |
| --- | ---: | ---: |
| Schemes, total | 283 | 283 |
| Government schemes | 282 | 282 |
| Scheme sources | 289 | 290 |
| Document versions | 1 | 2 |
| Rule sets | 1 | 1 |
| Rule conditions / rule evidence | 6 / 6 | 6 / 6 |
| Approved government rule sets | 0 | 0 |
| Authorized document sources / PDF assets | 0 / 0 | 1 / 1 |
| Parsed pages / chunks | 0 / 0 | 4 / 26 |
| Processing jobs | 0 | 3 |
| Candidate rules / located candidate evidence | 0 / 0 | 1 / 1 |
| Processing errors | 0 | 1 (expected missing Gemini key) |

A complete snapshot comparison verified that **every pre-Phase 3 row in the original six tables remained identical by ID**, including timestamps and historical policy content. The one extra source and document are additive. An explicit container recreation then verified aggregate row hashes/counts in **all 18 tables** and original PDF lengths/checksums. No database reset, record deletion, destructive downgrade or volume removal occurred.

## Tests and verification executed

| Check | Actual result |
| --- | --- |
| Pre-change PostgreSQL/backend baseline | 230 passed |
| Final backend unit + real PostgreSQL integration suite | **321 passed in 28.37s** |
| Frontend Vitest regression/component/proxy suite | **40 passed across 6 files** |
| Strict mypy | Passed, 59 application modules |
| Ruff lint and format checks | Passed |
| TypeScript | Passed |
| Prettier | Passed |
| Alembic upgrade/current/model drift | Head `0004_least_privilege`; `alembic check` reports no new upgrade operations |
| Isolated upgrade/downgrade/re-upgrade | Passed in disposable PostgreSQL databases only |
| Backend and frontend Docker image builds | Passed |
| Clean isolated Next.js production compilation | Passed with `NODE_ENV=production` |
| Existing live Phase 2 synthetic flow | PASS, FAIL and UNKNOWN results; frontend routes, CORS/source hash and missing-approved-rule fallback passed |
| Existing catalog verification | 282 government / 283 total; all source relationships, pagination/search/category/state filters and metadata-only behavior passed |
| Authenticated Phase 3 live proxy/API/SSR checks | Passed: sign-in, anonymous denial, CSRF denial, upload/duplicate, original checksum, pages/chunks, pending mock candidate, protected routes and no published government rules |
| Persistence across all container recreations | Passed, all 18 tables and preserved PDF checksum |
| Browser visual check | Administrator sign-in rendered correctly; authenticated pages additionally checked through live SSR/proxy and component tests |
| Live Gemini model invocation | **Not executed: no credentials**; mocks and missing-key behavior verified |

Backend coverage includes valid/malformed/blank PDFs, size/page/text/time bounds, path traversal, private/mixed DNS answers, redirect rejection, MIME/response budgets, private checksum-verified storage, stable chunks, structured output/schema errors, graph/operators/date/unit/missing-value grounding, absent/invented evidence, conflicting and equivalent numeric conditions, exclusions/conditionals, bounded retry/timeout/rate failures, administrator roles/sessions/login limits/origin/CSRF/logout, duplicate and superseding versions, source revocation, pending-only guards, cross-document FK protection, later-batch failure atomicity and storage rollback. Frontend tests cover credentials, upload attestation/size, literal untrusted text, evidence references, pending/mock labeling, failure states and proxy origin/path/body/cookie protections alongside existing discovery/questionnaire/report tests.

Issues found during verification were corrected: least-privilege account defaults, equivalent-number conflict normalization, invalid date review without crashing, blank evidence rejection, misleading cross-batch logic assumptions, durable input manifests before provider failure, original-file integrity errors, missing upload attestation enforcement, bounded parser environment/concurrency and asynchronous UI stale-response/error handling. Initial tooling/build attempts with unwritable formatter caches, transient package download timeouts or a development-mode production build were corrected; final checks above were actually executed successfully.

## Docker service status

| Service | Status | Host exposure |
| --- | --- | --- |
| frontend | Running, healthy | `127.0.0.1:3000` |
| api | Running, healthy | `127.0.0.1:8000` |
| db | Running, healthy | No published host database port |

Services were rebuilt and recreated using the existing persistent volumes. Only `document_data` was added. Gemini and ingestion limits are backend environment settings; the frontend receives no API key. Processing is bounded synchronous async HTTP with subprocess/thread offload; durable background execution remains future work.

## Run and verify

```bash
python3 scripts/init_env.py
docker compose up --build -d
docker compose up -d --wait --wait-timeout 120
docker compose exec api alembic upgrade head
docker compose exec api python -m app.seed
docker compose exec api python -m app.auth.provision --username reviewer

docker compose exec -T api python -m tests.run
docker compose exec -T api alembic check
docker compose exec -T api ruff check --no-cache app tests alembic
docker compose exec -T api ruff format --check --no-cache app tests alembic
docker compose exec -T api mypy --cache-dir=/tmp/schemeguard-mypy app
docker compose exec -T frontend npm test
docker compose exec -T frontend npm run typecheck
docker compose exec -T frontend npm run format:check
python3 scripts/verify_phase2.py
python3 scripts/verify_catalog.py
# Requires the registered supervised demo and a reviewer account; prompts for password:
python3 scripts/verify_phase3.py --username reviewer
# Recreates services, preserving and checking both database and original-document volumes:
python3 scripts/verify_persistence.py
docker compose ps
```

Frontend: [localhost:3000](http://localhost:3000). Admin: [localhost:3000/admin](http://localhost:3000/admin). API: [localhost:8000](http://localhost:8000). Docs: [localhost:8000/docs](http://localhost:8000/docs). Set `GEMINI_API_KEY` privately and recreate the API to enable real extraction. The generated local demonstration administrator password is stored only in ignored mode-0600 `.local/phase3-demo-credentials.json`; no password is in Git or this report. Provision an individual reviewer for normal use.

For a clean build without affecting the development `.next` directory:

```bash
docker compose run --rm --no-deps -e NODE_ENV=production --entrypoint sh frontend \
  -c 'cp -a /app /tmp/schemeguard-build && cd /tmp/schemeguard-build && rm -rf .next && npm run build'
```

## Limitations and acceptance

All ten acceptance criteria are met in the user-authorized mock-provider mode: the existing application works; an administrator ingests a real PDF; extraction preserves page evidence; structured mock output passes Pydantic/engine-shape validation; pending candidates are stored with evidence; no rules publish; Docker and relevant tests pass. **Live Gemini output quality, provider schema compatibility/model availability and account quotas remain unverified without credentials.** This limitation is not represented as a successful live invocation.

Source association is an authenticated human attestation, not automatic proof that uploaded bytes came from the URL. The historical demonstration is incomplete/current-policy-unreconciled. Text/table/heading extraction is best effort, with no OCR. The supported field vocabulary is intentionally narrow; unsupported/ambiguous conditions need review. Excerpt/value checks do not establish legal correctness or resolve policy precedence. Cross-batch logic is unverified. Large jobs need later durable workers. A resource-limited parser process is not a complete OS sandbox against native-library exploits. Production database roles, backup restore procedures, edge/distributed throttling, session/blob cleanup and production deployment hardening remain deferred. Candidate approval/publication belongs to Phase 4 and is not implemented.

Suggested Git commit message: `feat: add secure document ingestion and pending AI rule extraction`

The exact created/modified file inventory follows. Existing eligibility engine, catalog manifests, seed implementation and migrations 0001/0002 are unchanged.

<!-- phase3-file-inventory -->

| Change | File |
| --- | --- |
| Modified | `.dockerignore` |
| Modified | `.env.example` |
| Modified | `.gitignore` |
| Modified | `README.md` |
| Modified | `backend/Dockerfile` |
| Modified | `backend/app/api/v1/router.py` |
| Modified | `backend/app/core/config.py` |
| Modified | `backend/app/main.py` |
| Modified | `backend/app/models/__init__.py` |
| Modified | `backend/pyproject.toml` |
| Modified | `backend/requirements-dev.lock` |
| Modified | `backend/requirements.lock` |
| Modified | `backend/tests/test_migrations.py` |
| Modified | `docker-compose.yml` |
| Modified | `docs/architecture.md` |
| Modified | `docs/database.md` |
| Modified | `frontend/next.config.ts` |
| Modified | `frontend/src/app/globals.css` |
| Modified | `frontend/src/components/header.tsx` |
| Modified | `scripts/verify_persistence.py` |
| Created | `backend/alembic/versions/0003_ai_ingestion_admin_authentication_and_document_.py` |
| Created | `backend/alembic/versions/0004_least_privilege_user_default.py` |
| Created | `backend/app/ai/__init__.py` |
| Created | `backend/app/ai/provider.py` |
| Created | `backend/app/ai/schemas.py` |
| Created | `backend/app/ai/validation.py` |
| Created | `backend/app/api/v1/admin_auth.py` |
| Created | `backend/app/api/v1/admin_documents.py` |
| Created | `backend/app/auth/__init__.py` |
| Created | `backend/app/auth/provision.py` |
| Created | `backend/app/auth/security.py` |
| Created | `backend/app/core/body_limit.py` |
| Created | `backend/app/ingestion/__init__.py` |
| Created | `backend/app/ingestion/chunker.py` |
| Created | `backend/app/ingestion/demo.py` |
| Created | `backend/app/ingestion/fetcher.py` |
| Created | `backend/app/ingestion/pdf_parser.py` |
| Created | `backend/app/ingestion/pdf_worker.py` |
| Created | `backend/app/ingestion/storage.py` |
| Created | `backend/app/ingestion/text_processor.py` |
| Created | `backend/app/ingestion/validation.py` |
| Created | `backend/app/models/admin.py` |
| Created | `backend/app/models/processing.py` |
| Created | `backend/app/schemas/processing.py` |
| Created | `backend/app/services/ingestion.py` |
| Created | `backend/tests/ingestion_support.py` |
| Created | `backend/tests/test_admin_ingestion.py` |
| Created | `backend/tests/test_ai_candidates.py` |
| Created | `backend/tests/test_ingestion_units.py` |
| Created | `docs/document-processing.md` |
| Created | `docs/gemini-integration.md` |
| Created | `docs/phase3-ai-ingestion.md` |
| Created | `frontend/src/app/admin/(workspace)/documents/[id]/page.tsx` |
| Created | `frontend/src/app/admin/(workspace)/documents/page.tsx` |
| Created | `frontend/src/app/admin/(workspace)/extractions/[id]/page.tsx` |
| Created | `frontend/src/app/admin/(workspace)/layout.tsx` |
| Created | `frontend/src/app/admin/(workspace)/page.tsx` |
| Created | `frontend/src/app/admin/error.tsx` |
| Created | `frontend/src/app/admin/loading.tsx` |
| Created | `frontend/src/app/admin/login/page.tsx` |
| Created | `frontend/src/app/api/admin/[...path]/route.ts` |
| Created | `frontend/src/components/admin/document-detail.tsx` |
| Created | `frontend/src/components/admin/documents.tsx` |
| Created | `frontend/src/components/admin/evidence.tsx` |
| Created | `frontend/src/components/admin/extraction-detail.tsx` |
| Created | `frontend/src/components/admin/login.tsx` |
| Created | `frontend/src/components/admin/overview.tsx` |
| Created | `frontend/src/components/admin/session.tsx` |
| Created | `frontend/src/lib/admin-server.ts` |
| Created | `frontend/src/lib/admin.ts` |
| Created | `frontend/tests/admin-proxy.test.ts` |
| Created | `frontend/tests/admin.test.tsx` |
| Created | `scripts/verify_phase3.py` |
