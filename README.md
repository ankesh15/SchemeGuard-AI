# SchemeGuard AI — Curated catalog on the Phase 2 foundation

A Docker-first government scheme discovery project with a deterministic, explainable eligibility engine and a responsive Next.js interface. The backend is a modular monolith. PostgreSQL stores public scheme metadata and immutable policy/rule history; applicant profiles and reports are **not persisted**.

**The working assessment uses an explicitly fictional development scholarship.** The catalog contains 282 government schemes across 23 categories, but none has approved government eligibility rules. The fictional policy offers no award and has no official application portal.

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

Blank answers remain unknown. Form validation checks valid input types and domains, rather than preventing profiles that fail an eligibility condition. The questionnaire uses the approved policy's field definitions and reveals dependent inputs when applicable. A report exists only in React memory; refreshing the page clears it. No names, Aadhaar numbers, contact details, document uploads, or profile-storage APIs are introduced.

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
# Recreates all three services; compares every row in all six domain tables:
python3 scripts/verify_phase2.py
python3 scripts/verify_catalog.py
python3 scripts/verify_persistence.py
```

`tests.run` creates randomly named PostgreSQL databases, applies real migrations, and removes its test databases after completion. Missing test configuration is an error, not a skipped or SQLite-only suite. The local development database role needs CREATE DATABASE permission; production role separation is deferred.

Checked-in frontend test responses and example inputs contain only authored synthetic data. Runtime questionnaire submissions and their reports are not persisted.

Backend dependencies retain hash-locked Python requirements. Frontend versions are pinned in `package.json` and `package-lock.json`; Docker installs them with `npm ci`. A clean-container `npm run build` verifies frontend compilation without sharing the dev server's `.next` directory.

See [Phase 2 report](docs/phase2-report.md), [architecture](docs/architecture.md), [database](docs/database.md), and [rule authoring/semantics](docs/rules.md). The [Phase 1 report](docs/phase1-report.md) is retained as historical verification. Phase 3, LLM processing, policy monitoring, notifications, Redis, Celery, authentication workflows, and production deployment configuration are not implemented.
