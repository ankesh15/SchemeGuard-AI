# SchemeGuard AI — evidence-backed policies and private assessments

A Docker-first government scheme discovery project with a deterministic, explainable eligibility engine and a responsive Next.js interface. The backend is a modular monolith. PostgreSQL stores public scheme metadata and immutable policy/rule history; citizen profiles and explicitly saved reports use encrypted private storage. Public synthetic requests remain stateless.

Phase 3 adds an authenticated administrator workspace for official PDFs, page-aware PyMuPDF extraction, stable chunks, Gemini structured candidate extraction, evidence validation, and pending review. Phase 4 adds checkpointed LangGraph workflows, authenticated human revisions and decisions, immutable publication, pgvector retrieval and grounded explanations. See the [Phase 3 implementation report](docs/phase3-ai-ingestion.md), [processing guide](docs/document-processing.md), and [Gemini integration guide](docs/gemini-integration.md).

**The working assessment uses an explicitly fictional development scholarship.** The catalog contains 282 government schemes across 23 categories, but none has approved government eligibility rules. The fictional policy offers no award and has no official application portal.

See the [Phase 4 implementation report](docs/phase4-langgraph.md), [workflow guide](docs/agent-workflows.md), [human review guide](docs/human-review.md) and [RAG architecture](docs/rag-architecture.md). The live official document remains pending actual human review. No real government policy approval is claimed.

## Start the application

Prerequisites: Docker Engine, Docker Compose v2+, and Python 3 for the optional environment helper. From the project root:

```bash
python3 scripts/init_env.py
docker compose up --build -d
docker compose up -d --wait --wait-timeout 120
```

- Frontend: [localhost:3000](http://localhost:3000)
- Backend: [localhost:8000](http://localhost:8000)
- FastAPI documentation: [localhost:8000/docs](http://localhost:8000/docs)
- Administrator workspace: [localhost:3000/admin](http://localhost:3000/admin)

The helper creates an ignored `.env` with a generated local password and preserves an existing file. Alternatively, copy `.env.example` and replace its password placeholder. The API applies migrations before startup and, by default in this development Compose configuration, runs the insert-only government metadata seed and the fictional fixture seed. An existing PostgreSQL volume and its records are preserved.

```bash
# These commands are also safe to repeat explicitly:
docker compose exec api alembic upgrade head
docker compose exec api python -m app.seed
docker compose exec api python -m app.seed_demo
```

`SEED_DEMO_DATA=false` disables automatic development seeding; it does not delete existing immutable history. Synthetic fixture seeding is rejected outside development/test environments. PostgreSQL credentials in an existing volume must be rotated in PostgreSQL as well as in `.env`; changing the environment alone does not change its stored password.

## Try the complete user journey

1. Open the frontend, explore schemes, search **Fictional**, and select **SchemeGuard Learning Scholarship (Fictional)**.
2. Open its eligibility questionnaire. Select **Use a synthetic example** and submit.
3. The report shows **Known conditions satisfied**, six requirement results, decision traces, policy evidence, and rule version 1.
4. Change the synthetic age to `17` to see **Requirements not satisfied**.
5. Leave household income blank, or request disability support without a percentage, to see **More information required** and the specific missing field.

Blank answers remain unknown. Form validation checks valid input types and domains, rather than preventing profiles that fail an eligibility condition. The questionnaire uses the approved policy's field definitions and reveals dependent inputs when applicable. A report exists only in React memory; refreshing the page clears it. No citizen names, Aadhaar numbers, contact details, personal document uploads, or profile-storage APIs are introduced.

## Curated multi-category dataset

`data/schemes/` contains 23 validated JSON manifests with **282 government schemes**: the original five, 224 additional central-directory records, and 53 Goa records. PostgreSQL has **283 scheme rows** including the separately labeled fictional fixture. The target of 250–300 government records is met. The seed format supports arbitrary counts and a 300-record PostgreSQL capacity test passes.

The new records were manually reviewed against the [official DBT Bharat directory](https://dbtbharat.gov.in/central-scheme/list) and [Goa government scheme catalog](https://www.goa.gov.in/government/schemes/). Verification establishes identity/listing metadata, not active enrollment, financial benefits, eligibility or deadlines. Department and geographic fields remain unknown where not supported by those sources. No scraper or live synchronization runs.

```bash
# Validate all category files; no database connection:
docker compose exec api python -m app.seed --validate-only
# Import missing rows transactionally; existing rows/sources are preserved:
docker compose exec api python -m app.seed
```

Repeat imports insert zero duplicates. The default `SEED_DATA_PATH=/app/data/schemes` can select a different directory or the compatible legacy `data/scholarships.json` file. Detailed provenance, deduplication decisions, how to add schemes and static-data limits are in the [dataset guide](docs/datasets.md); results are in the [expansion report](docs/dataset-expansion-report.md). The frontend loads categories from the API and labels metadata-only schemes. Its approved-policy selector no longer depends on finding a scheme in the first 100 catalog results.

## Government sources and the fictional fallback

The original five scholarship records and their eleven official evidence relationships are preserved. Their metadata was checked on 11 November 2026. Scheme status `listed` means directory presence on that date, not an application-window or eligibility guarantee. The expanded catalog adds 277 official directory records, including 53 verified Goa state programmes. Unknown geography is excluded from state filters.

Phase 2 reviewed the [Saksham guideline linked by NSP](https://scholarships.gov.in/public/schemeGuidelines/AICTE/AICTE_2012_G.pdf) and its [linked FAQ](https://scholarships.gov.in/public/schemeGuidelines/AICTE/AICTE_2012_F.pdf). The guideline uses an inclusive INR 8 lakh income boundary, whereas the FAQ describes a strict boundary. The documents also require review alongside current [NSP notices](https://scholarships.gov.in/Students) before a coherent current policy can be approved. The implementation therefore uses the fallback permitted in the Phase 2 brief, rather than selecting an uncertain interpretation or claiming human review.

The authored [fictional policy](data/policies/demo-policy-v1.md) is the sole executable fixture. All its values are invented and labeled accordingly. Its exact bytes are hashed into an immutable document version; the frontend serves an identical copy. The reserved `example.invalid` source address is explicitly synthetic. It is never presented as an official application URL.

## APIs

| Method | Path | Behavior |
| --- | --- | --- |
| GET | `/health` | Process health |
| GET | `/ready` | Live database connectivity; 503 when unavailable |
| GET | `/api/v1/schemes` | Discovery with `page`, `page_size`, `search`, `category`, verified `state`, and `eligibility_available` filters |
| GET | `/api/v1/schemes/filters` | Categories and verified state choices from PostgreSQL |
| GET | `/api/v1/schemes/{id}` | Scheme detail and source metadata |
| GET | `/api/v1/schemes/{id}/requirements` | Currently effective approved version, questionnaire fields, requirement labels, and evidence; `available: false` when absent |
| POST | `/api/v1/eligibility/check` | Stateless deterministic evaluation of the effective approved version |

Pagination remains bounded (`page` 1–100000, `page_size` 1–100). Search is a case-insensitive name/description substring; SQL wildcard characters are treated literally. Category tokens and Indian state/UT names are validated. Filters combine with AND. Valid filters with no matches return 200 and an empty page. Malformed IDs/inputs return 422, absent schemes return 404, and database/configuration failures fail closed. Errors and assessment responses carry request IDs and safe messages; assessment responses use `Cache-Control: no-store`.

```bash
curl --fail 'http://localhost:8000/api/v1/schemes?search=Fictional'
# Copy its UUID into the request:
curl --fail http://localhost:8000/api/v1/eligibility/check \
  -H 'Content-Type: application/json' \
  -d '{"scheme_id":"REPLACE_WITH_DEMO_UUID","synthetic_profile":true,"profile":{"age":21,"annual_income_inr":"240000","course":"engineering","study_mode":"full_time","enrollment_date":"2026-08-01","receives_other_scholarship":false,"requests_disability_support":false}}'
```

The response contains `result`, the required assessment wording, `requirements`, the full nested `trace`, `missing_fields`, evidence references, and the evaluated `rule_set` version/document hash. It never returns or stores the raw profile. No approved policy produces UNKNOWN with `reason: NO_APPROVED_RULE_SET` and no evaluated version. Government requirements are never inferred from metadata alone. Only the original five NSP-backed scholarship records retain the reviewed NSP application link. Other metadata-only schemes show their official source references without an invented application portal.

## Rule semantics and approval

The standalone `app/eligibility` package uses typed, discriminated expressions. It supports `==`, `!=`, `>`, `<`, `>=`, `<=`, `IN`, `NOT IN`, ISO calendar dates, nested AND/OR, exclusions, and conditional branches. Stored rules never use Python `eval` or `exec`. Numbers use Decimal for comparisons; booleans are not coerced into numbers. Invalid expressions, fields, types, empty groups, duplicate keys, and excessive tree complexity are rejected.

- AND: any FAIL wins; otherwise UNKNOWN wins; otherwise PASS.
- OR: any PASS wins; otherwise UNKNOWN wins; otherwise FAIL.
- Exclusion: invert PASS/FAIL and preserve UNKNOWN.
- Conditional: an unknown guard yields UNKNOWN. A known guard selects the relevant branch; an absent otherwise branch means the additional requirement does not apply.

Every missing/null comparison is UNKNOWN. A satisfied OR alternative can still establish the OR result, without requiring unrelated alternative fields. All relevant branch traces remain available for inspection.

Rule sets begin as DRAFT. Version content, condition expressions, and evidence are immutable; approval is a one-way DRAFT → APPROVED/REJECTED transition. PostgreSQL requires evidence for every condition, same-scheme source documents, same-set condition/evidence links, and approval metadata. Synthetic approval is allowed only for a scheme classified as a demo. Government rules require the separate `human_review` basis. There is no public rule-authoring/approval endpoint, and this phase publishes no government rule set. An LLM is never involved in evaluation.

## Docker and environment

Compose runs exactly `frontend`, `api`, and `db`. The database and API share an internal database network; an ingress network connects the frontend and API. Only loopback ports 3000 and 8000 are published. PostgreSQL has no host port. Both application containers run as non-root users and use development hot reload.

`INTERNAL_API_URL=http://api:8000` is used by Next.js server rendering. `NEXT_PUBLIC_API_URL=http://localhost:8000` is used by the browser; never set it to the Docker-only hostname. CORS permits configured explicit origins and GET/POST, without credentials. If you change host ports, update the public API URL and allowed frontend origin together. No database secret is passed to the frontend. The local `.env` is excluded from image contexts.

PostgreSQL uses the existing persistent volume. Frontend node_modules and Next.js development output use separate named volumes. When intentionally changing frontend dependencies, rebuild and refresh the mounted dependency volume with `docker compose exec frontend npm ci` before verification. Do not recreate application containers while their integration-test runner is active.

`docker compose down` preserves volumes. **`docker compose down -v` deletes persistent data** and is not required for normal development.

## Verification commands

```bash
# Actual PostgreSQL tests, including isolated migration and preservation checks:
docker compose exec -T api python -m tests.run
docker compose exec -T api alembic check
docker compose exec -T api ruff check --no-cache app tests alembic
docker compose exec -T api ruff format --check --no-cache app tests alembic
docker compose exec -T api mypy --cache-dir=/tmp/schemeguard-mypy app
# Frontend validation and components:
docker compose exec -T frontend npm test
docker compose exec -T frontend npm run typecheck
docker compose exec -T frontend npm run format:check
# Regression flows and persistence across all discovered public/checkpoint tables plus original PDFs:
python3 scripts/verify_phase2.py
python3 scripts/verify_catalog.py
python3 scripts/verify_persistence.py
```

`tests.run` creates randomly named PostgreSQL databases, applies real migrations, and removes its test databases after completion. Missing test configuration is an error, not a skipped or SQLite-only suite. The local development database role needs CREATE DATABASE permission; production role separation is deferred.

Checked-in frontend test responses and example inputs contain only authored synthetic data. Public synthetic questionnaire submissions and reports remain stateless. Citizen workspace submissions are saved privately with explicit reassessment consent.

Backend dependencies retain hash-locked Python requirements. Frontend versions are pinned in `package.json` and `package-lock.json`; Docker installs them with `npm ci`. A clean-container `NODE_ENV=production npm run build` verifies frontend compilation without sharing the dev server's `.next` directory.

See [Phase 2 report](docs/phase2-report.md), [architecture](docs/architecture.md), [database](docs/database.md), and [rule authoring/semantics](docs/rules.md). The [Phase 1 report](docs/phase1-report.md) is retained as historical verification. Phase 3 adds administration and LLM candidate extraction only. Phases 4–6 add reviewed publication, monitoring, background jobs and private citizen accounts as described below. Phase 7 adds separate production images, CI, security hardening and verified local release/recovery procedures; no live cloud deployment is claimed.


## Administrator setup

```bash
# Interactive hidden password prompt; no public registration endpoint:
docker compose exec api python -m app.auth.provision --username reviewer
# Explicit password rotation also revokes existing sessions:
docker compose exec api python -m app.auth.provision --username reviewer --reset-password
```

Use a unique password of at least 12 characters. Sign in at `/admin/login`, authorize the exact official PDF URL for its government scheme, then upload a matching PDF or request an approved-source download. Use **Extract text only** without Gemini credentials. To enable real candidate extraction, set backend-only `GEMINI_API_KEY` in `.env` and run `docker compose up -d --force-recreate api`. Keep `GEMINI_MODEL` configurable. No key is sent to Next.js.

The administrator browser uses a same-origin Next.js proxy with HttpOnly sessions, origin checks, and CSRF tokens. `ADMIN_ALLOWED_ORIGINS` must match the frontend origin. Original PDFs persist in the private `document_data` volume and are served to authenticated administrators as downloads. Do not remove that volume. Bounded processing is synchronous over async HTTP; PDF parsing runs in a resource-limited subprocess and password verification/downloads run outside the event loop. Phase 5 adds independently running Celery workers for monitoring and verified policy reassessment; supervised administrator document processing remains bounded as described above.

The supervised Phase 3 demonstration uses a real historical official PDF and a clearly labeled operator-only mock provider because Gemini credentials were unavailable. It never creates executable government rules. Generated local demonstration account credentials, if present, are in ignored `.local/phase3-demo-credentials.json` with mode 0600; provision your own reviewer for regular use. Never commit that file.

## Phase 4 operations

1. Provision an administrator with `docker compose exec api python -m app.auth.provision --username reviewer`.
2. Open `/admin/documents`, authorize an exact official source and register its PDF as in Phase 3.
3. Start a workflow from document details. A new extraction uses Gemini; reusing an existing extraction keeps its original provider label.
4. Open `/admin/reviews`, inspect every original page and evidence finding, revise the complete typed policy, and save notes.
5. Only an actual human may confirm completeness/applicability and approve the exact saved revision. Approval publishes a new immutable RuleSet; rejection creates no executable rule.
6. Index parsed chunks with the configured embedding provider. Approved versions become available to existing deterministic assessments; public questions/retrieval use only their exact source documents.

| Method | Added API | Purpose |
| --- | --- | --- |
| POST / GET | `/api/v1/admin/workflows` | Idempotent creation / paginated workflow list |
| GET | `/api/v1/admin/workflows/{id}` | Stage, status, history and errors |
| POST | `/api/v1/admin/workflows/{id}/resume` or `/cancel` | Recover saved execution / safely cancel undecided work |
| GET | `/api/v1/admin/reviews` or `/reviews/{id}` | Pending queue / original, current revision, findings, evidence |
| POST | `/api/v1/admin/reviews/{id}/revisions` | Append a noted administrator revision |
| POST | `/api/v1/admin/reviews/{id}/approve` or `/reject` | Single exact-revision human decision and graph resume |
| POST | `/api/v1/admin/documents/{id}/index` | Atomic, idempotent chunk embeddings |
| GET | `/api/v1/schemes/{id}/rule-history` | Approved policy history only |
| POST | `/api/v1/schemes/{id}/questions` | Constrained source quotations |
| POST | `/api/v1/eligibility/explain` | Existing server assessment plus immutable-result explanation |

Configure `GEMINI_API_KEY` only in ignored backend environment. `EMBEDDING_PROVIDER=gemini`, `EMBEDDING_MODEL=gemini-embedding-001` and dimension 768 are defaults. Without credentials, extraction fails clearly, indexing returns 503, and explanations use approved rule evidence plus bounded lexical retrieval/templates. `local_hash` is an explicit development lexical fixture, not a semantic model.

The database image builds pgvector 0.8.7 from a SHA-pinned official archive on **the same PostgreSQL 16 Alpine base**. It reuses `postgres_data`. Before the first upgrade of an existing installation, make a private backup and test restoration; this was performed for the implementation verification. Do not remove existing volumes. Alembic 0005–0007 add workflow/review/vector data, the official checkpoint schema and provenance guards without modifying old policy rows.

```bash
docker compose up --build -d
docker compose exec api alembic upgrade head
docker compose exec api alembic check
docker compose exec api python -m tests.run -q
docker compose exec frontend npm test
docker compose exec frontend npm run typecheck
# Requires the Phase 3 official demo PDF and a private local administrator login:
python3 scripts/verify_phase4.py --credentials .local/phase3-demo-credentials.json
# Recreates services while preserving volumes and checks all rows/checkpoints/PDFs:
python3 scripts/verify_persistence.py
```

Supervised administrator processing remains bounded synchronous API work with durable checkpoints and explicit operator resume after interruption. Scheduled monitoring and reassessment use the Phase 5–6 queues described below.

## Phase 5 policy monitoring

Opt-in monitoring, PostgreSQL durable jobs, Redis/Celery workers and a singleton Beat scheduler extend the existing ingestion/review pipeline. No catalog URL is automatically monitored. Approve the exact official PDF source, verify its access conditions, then configure `/admin/monitors`. Inspect proposed old/new policy differences at `/admin/policy-changes`; publication still requires the complete Phase 4 human review. `/api/v1/policy-updates` exposes only approved published changes.

```bash
docker compose up --build -d
docker compose exec api alembic upgrade head
docker compose logs -f worker scheduler
python3 scripts/verify_workers.py
```

The six services are frontend, api, db, redis, worker and scheduler. Redis has persistent AOF and no public port. PostgreSQL remains authoritative for jobs/history; Redis loss does not erase policy or job records. Restart worker/scheduler after Python edits. See [Phase 5 report](docs/phase5-policy-monitoring.md), [Celery architecture](docs/celery-architecture.md), and [version selection](docs/policy-versioning.md).

## Phase 6 citizen workspace

Citizens can register at `/register`, sign in at `/login`, and use `/dashboard` for encrypted profiles, saved versioned assessments, policy updates, notification preferences and account settings. Public synthetic assessment endpoints retain their existing behavior. Only approved policies can support decisions; the catalog still includes discovery-only schemes. A reviewed material policy publication can reassess explicitly authorized saved schemes through Celery, preserving original reports and notifying only affected accounts.

Before upgrading, run `python3 scripts/init_env.py` to append a private-storage key to the existing ignored `.env` without replacing its credentials. Preserve and separately back up this key: replacing it makes existing encrypted private records unreadable. Run `docker compose up --build -d`; migrations apply incrementally. API and worker share the key; frontend does not. There is no configured email/password recovery service. Read [Phase 6 report](docs/phase6-user-system.md), [authentication](docs/authentication.md), [notifications](docs/notifications.md) and [reassessment](docs/reassessment.md) for endpoints, exact commands, consent and deletion/backup limitations. `python3 scripts/verify_phase6.py` exercises a synthetic private account through the real Next.js proxy, saves a fictional assessment, reproduces it and logs out.

## Phase 7 production readiness and demonstration

The existing application now has separate production images/Compose configuration, restricted runtime DB roles, private S3 document-storage support, nonce CSP/same-origin browser API boundaries, CI checks, Chromium end-to-end tests, a synthetic A/B/C workflow demonstration, measured reference evaluation/performance and a tested local recovery procedure. Existing data, rule/history semantics and six development services remain.

Start development as before with `python3 scripts/init_env.py` and `docker compose up --build -d`. Browser APIs now use same-origin fixed proxies; a NEXT_PUBLIC_API_URL is unnecessary. Production migration is an explicit owner-only release step rather than an API startup side effect. See [Docker](docs/docker.md), [deployment/recovery](docs/deployment.md), [security](docs/security.md), [testing](docs/testing.md), [API inventory](docs/api.md) and the [final project report](docs/final-project-report.md).

Actual catalog: 283 records (282 government discovery records plus one fictional demonstration), one approved fictional rule set and zero approved government rule sets. The historical official PDF remains pending real human/current-policy review. Gemini and real cloud/S3 connections remain unverified without configured access. Local production-profile verification is not a live cloud deployment. The report separates completed implementation, measured fixture results and remaining release prerequisites.
