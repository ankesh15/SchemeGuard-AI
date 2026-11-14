# SchemeGuard AI

**Profile-first government scheme discovery, explainable assessments, and evidence-backed policy review.**

SchemeGuard AI is a final-year B.Tech project that helps people discover Indian government schemes based on their interests and profile. It combines a Next.js frontend, a modular FastAPI backend, deterministic eligibility evaluation, AI-assisted document processing, and human-reviewed policy updates.

Recommendations and illustrative assessments are informational demonstrations, not government eligibility determinations, application submissions, or approval guarantees.

## Main user journey

**Home → Enter details → Find relevant schemes → Personalized results → Scheme details → Available assessment**

1. Select **Find My Schemes** on the homepage. No scheme grid loads automatically.
2. Complete any of five optional steps: age/state, education, employment, annual family income, and interests. Unknown answers are allowed; no name, Aadhaar number, or identity document is required for recommendations.
3. Explore ranked recommendations with matching reasons, missing information, category filters, and pagination.
4. Open a scheme to inspect its official sources and assessment options. Compatible questionnaire answers are prefilled.
5. Review the explainable result, return to recommendations, or edit your details.

Guests can use this flow without registering. Their answers and public reports remain in React memory; reloading clears them. Citizens can prefill their own encrypted profile and explicitly save updates. Approved-policy assessments support private saving, historical reports, and reproducibility.

The primary `/schemes` route follows this personalized flow. Manual search and browsing remain available at `/schemes/all`.

[Homepage screenshot](docs/verification/profile-first/home-desktop.png) · [Recommended schemes on desktop](docs/verification/profile-first/results-desktop.png) · [Mobile results](docs/verification/profile-first/results-mobile.png)

## Features

- **Personalized discovery:** one deterministic recommendation service for guests, citizens, and the dashboard. Ranking considers category interests, occupation/student/employment signals, verified geography, and applicable approved rules. Relevance is not an eligibility percentage.
- **Deterministic assessments:** typed comparisons, nested AND/OR, exclusions, date comparisons, and conditional requirements produce PASS, FAIL, or UNKNOWN with decision traces. Missing information never defaults to PASS.
- **Citizen workspace:** shared secure authentication, encrypted optional profiles, saved assessments, version-pinned history, notification preferences, and in-app notifications.
- **Document intelligence:** approved-source PDF ingestion, original preservation, SHA-256 checksums, page-aware PyMuPDF extraction, stable chunks, and Gemini structured candidate extraction.
- **Human review and RAG:** checkpointed LangGraph workflows, evidence validation, administrator revisions, immutable rule publication, and source-citing retrieval through pgvector.
- **Policy monitoring:** selected official-source checks, document/version comparison, structured rule differences, human-reviewed policy changes, and background reassessment of affected saved reports.
- **Operational foundations:** Docker development and production configurations, health/readiness checks, structured logs, audit events, CI checks, and documented backup/recovery procedures.

AI-extracted rules remain pending until human approval. An LLM never makes or overrides the final deterministic eligibility decision. Illustrative category templates remain separate from approved government policies and do not supply numerical recommendation thresholds.

## Technology stack

| Area | Technologies |
|---|---|
| Frontend | Next.js, React, TypeScript, Tailwind CSS |
| Backend | Python, FastAPI, Pydantic, SQLAlchemy, Alembic |
| Data | PostgreSQL, pgvector, encrypted private profile/report payloads |
| AI and documents | Google GenAI SDK/Gemini, LangGraph, PyMuPDF |
| Background processing | Celery workers, Redis broker, singleton Celery Beat scheduler |
| Infrastructure and testing | Docker Compose, GitHub Actions, pytest, HTTPX, Vitest, Testing Library, Playwright |

## Run locally

Prerequisites: Docker Engine, Docker Compose v2+, and Python 3 for the environment helper. From the repository root:

```bash
python3 scripts/init_env.py
docker compose up --build -d --wait --wait-timeout 120
docker compose ps
```

The helper creates a private, ignored `.env` with generated local credentials and a profile-encryption key. It preserves existing values. An existing PostgreSQL volume and application records are retained. Alternatively, configure `.env` from [.env.example](.env.example) with your own private values.

| Page or service | Local URL |
|---|---|
| Homepage | [localhost:3000](http://localhost:3000) |
| Questionnaire | [localhost:3000/find-schemes](http://localhost:3000/find-schemes) |
| Manual scheme catalog | [localhost:3000/schemes/all](http://localhost:3000/schemes/all) |
| Citizen workspace | [localhost:3000/dashboard](http://localhost:3000/dashboard) |
| Administrator login | [localhost:3000/admin/login](http://localhost:3000/admin/login) |
| Backend API documentation | [localhost:8000/docs](http://localhost:8000/docs) |
| API health / database readiness | [localhost:8000/health](http://localhost:8000/health) / [localhost:8000/ready](http://localhost:8000/ready) |

Development startup applies incremental Alembic migrations. With `SEED_DEMO_DATA=true`, it also runs insert-only catalog and legacy demonstration seeding. Setting this flag to `false` disables automatic seeding without deleting existing records. The demonstration seed is restricted to development/test environments.

```bash
# Inspect migrations and schema drift:
docker compose exec api alembic current
docker compose exec api alembic check

# Apply migrations explicitly when needed:
docker compose exec api alembic upgrade head

# Restart without removing persistent data:
docker compose restart

# Inspect application and background-job logs:
docker compose logs --tail=100 api worker scheduler

# Stop services while retaining volumes:
docker compose stop
```

Preserve the PostgreSQL/document volumes and `PROFILE_ENCRYPTION_KEY`. Replacing the encryption key makes existing encrypted records unreadable. Changing a password in `.env` does not rotate the password stored in an existing PostgreSQL volume.

## Administrator setup

Administrator accounts are provisioned through the CLI, not public registration. Choose your own username and enter the password at the hidden prompt:

```bash
docker compose exec api python -m app.auth.provision --username reviewer
```

Use a password of at least 12 characters, then open [the administrator login](http://localhost:3000/admin/login). Existing accounts can sign in directly; provisioning does not overwrite them. Explicit password rotation revokes that administrator's existing sessions:

```bash
docker compose exec api python -m app.auth.provision --username reviewer --reset-password
```

Passwords are hashed with Argon2id. Browser sessions use HttpOnly cookies; private writes require CSRF and exact-origin checks. Citizen registration cannot select or grant an administrator role. Login credentials, API keys, and private `.env` files must not be committed.

For document processing, authorize the exact official source for the correct scheme, register/upload its PDF, and inspect extracted pages and evidence. Text extraction can run without Gemini. To enable real AI extraction, configure backend-only `GEMINI_API_KEY` and `GEMINI_MODEL` in `.env`, then recreate the relevant backend services:

```bash
docker compose up -d --force-recreate api worker scheduler
```

Candidates are reviewed in the protected workspace before publication. Source monitoring is enabled individually by administrators; it does not automatically fetch the entire catalog. See [document processing](docs/document-processing.md), [Gemini configuration](docs/gemini-integration.md), and [human review](docs/human-review.md).

## Catalog and assessment coverage

The recorded verification snapshot contains **282 government scheme records** across **23 category manifests** in `data/schemes/`. PostgreSQL has **283 scheme rows** including one separately marked legacy demonstration scheme.

Each curated record includes an official-source reference and verification metadata. Directory presence establishes discovery metadata, not current enrollment, financial benefits, deadlines, or complete eligibility. Unverified fields remain unknown; there is no automated catalog scraping or live synchronization.

```bash
# Validate all manifests without importing records:
docker compose exec api python -m app.seed --validate-only

# Transactionally insert missing records and preserve existing IDs/data:
docker compose exec api python -m app.seed
```

The seed command supports arbitrary record counts, validates category files, detects duplicate slugs, maintains source relationships, and skips existing records. Its default path is `/app/data/schemes`; the legacy `data/scholarships.json` format remains supported. See [dataset organization and provenance](docs/datasets.md) and the [expansion report](docs/dataset-expansion-report.md).

At the last recorded verification, **no government rule set was approved**. One approved rule set belongs to the legacy demonstration only. Nine project-authored templates provide clearly identified illustrative assessments for 225 government discovery records across 14 populated categories; 57 records have no supported assessment. These templates are not government policy and are not published or saved as approved-policy assessments. Applicable human-reviewed policies take precedence when available.

Recommendations use unknown geography conservatively: unverified coverage remains discoverable, while an explicitly verified state mismatch can exclude a result. The manual catalog's state filter returns only verified coverage. Precise age/income/course restrictions are never inferred from catalog descriptions.

## Architecture and Docker services

The backend is a **modular monolith with independently running workers**. PostgreSQL holds durable job status, policy history, accounts, and encrypted private data. Redis delivers background tasks; it is not the authoritative policy store.

| Service | Responsibility |
|---|---|
| `frontend` | Next.js interface and fixed same-origin API proxies |
| `api` | FastAPI routes, authentication, discovery, assessment, and document/review services |
| `db` | PostgreSQL with pgvector and persistent data |
| `redis` | Internal Celery message broker |
| `worker` | Bounded monitoring/document/reassessment background execution |
| `scheduler` | Celery Beat scheduling with singleton leadership |

Only frontend/API loopback ports 3000 and 8000 are published. PostgreSQL and Redis have no public host ports. API/worker share persistent original-document storage. The development frontend and backend support hot reload; application containers run as non-root users.

Browser requests use same-origin Next.js proxies. `INTERNAL_API_URL` is server-only; a public browser API URL is unnecessary. Set `ADMIN_ALLOWED_ORIGINS` to the exact frontend origin, and keep database, Gemini, storage, and encryption credentials out of frontend environment variables.

```text
backend/
  app/
    api/v1/                 # HTTP contracts and authorization
    auth/                   # Shared authentication and encrypted storage
    assessment/             # Separate illustrative assessment templates
    eligibility/            # Typed deterministic rule engine
    ingestion/              # Secure PDF ingestion, parsing, and chunks
    ai/ agents/ rag/         # Providers, LangGraph workflows, retrieval
    models/ schemas/        # Database and validated API contracts
    repositories/ services/ # Data access and application behavior
    workers/                # Celery tasks and scheduler
  alembic/                  # Incremental database migrations
  tests/                    # Unit and PostgreSQL integration tests
frontend/
  src/app/                  # Public, citizen, and administrator routes
  src/components/           # Reusable forms, reports, cards, workspaces
  e2e/                      # Browser journeys
  tests/                    # Component and request-boundary tests
data/schemes/               # Curated category-based manifests
docs/                       # Architecture, operations, phase reports, evidence
scripts/                    # Environment, verification, release, recovery tools
```

## Main APIs

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health`, `/ready` | Process health and live database readiness |
| POST | `/api/v1/recommendations` | Transient profile-based recommendations, paging, and filtering |
| GET | `/api/v1/recommendations/options` | Catalog-derived interests/categories and state input choices |
| POST | `/api/v1/me/recommendations` | Recommendations from the authenticated citizen's own saved profile |
| GET | `/api/v1/schemes`, `/api/v1/schemes/filters` | Manual catalog search, pagination, and filters |
| GET | `/api/v1/schemes/{id}` | Scheme metadata and source references |
| GET | `/api/v1/schemes/{id}/assessment-requirements` | Available assessment basis and typed questionnaire |
| POST | `/api/v1/assessment/check` | Explainable approved-policy or explicitly illustrative assessment |
| GET | `/api/v1/schemes/{id}/requirements` | Strict approved-policy requirements |
| POST | `/api/v1/eligibility/check` | Existing strict, approved-rule evaluation contract |

Private profile, assessment history, notification, document, workflow, review, and monitoring endpoints are listed in [the API inventory](docs/api.md) and live [OpenAPI documentation](http://localhost:8000/docs). Existing API contracts remain available.

Recommendation profile inputs belong in POST bodies, never URL query parameters. The public proxy does not forward account cookies or persist guest profiles. For example, using sample data:

```bash
curl --fail http://localhost:3000/api/v1/recommendations \
  -H 'Content-Type: application/json' \
  -d '{"age_years":21,"state":"Assam","course_level":"undergraduate","current_student":true,"occupation":"student","interests":["education"],"page":1,"page_size":9}'
```

Results include scheme metadata, relevance labels, matching reasons, missing information, assessment availability/basis, and pagination. A high relevance label does not mean the applicant is eligible.

## Testing and recorded verification

```bash
# Disposable PostgreSQL integration database; existing application data is preserved:
docker compose exec api python -m tests.run

# Backend checks:
docker compose exec api ruff check --no-cache app tests alembic
docker compose exec api ruff format --check --no-cache app tests alembic
docker compose exec api mypy --cache-dir=/tmp/schemeguard-mypy app

# Frontend checks:
docker compose exec frontend npm test
docker compose exec frontend npm run typecheck
docker compose exec frontend npm run lint
```

The backend runner requires PostgreSQL and creates/removes only its own randomly named test databases. The development database role needs permission to create databases; production uses separate restricted runtime credentials.

Browser journeys are under `frontend/e2e/`. On a host with frontend dependencies and the matching Playwright Chromium installed, run `npm run e2e` from `frontend/`. Local verification also used installed Chrome with the project's pinned Playwright packages. Repeated account-registration tests should use isolated test databases so existing authentication rate limits remain enabled.

Last recorded implementation verification, **14 November 2026**:

| Check | Recorded result |
|---|---|
| Backend regression, including PostgreSQL integration | 491 passed |
| Frontend regression | 84 passed across 13 files |
| Browser regression | 9 passed; final desktop/mobile journeys rerun with 4 passed |
| Ruff, mypy, TypeScript, frontend lint | Passed |
| Alembic | `0009_citizen_system`; no detected schema drift |
| Development and production images | Built successfully |
| Development Compose services | All six healthy at verification |

These are recorded results, not a claim that every test was rerun for this README edit. Full details, sample results, screenshots, and limitations are in the [profile-first implementation report](docs/profile-first-recommendations.md) and [machine-readable verification](docs/verification/profile-first-verification.json).

## Production and limitations

Production uses the separate `docker-compose.production.yml` with production Dockerfile targets. It includes Next.js standalone output, non-root containers, restricted runtime database roles, health checks, and explicit migration/release procedures. Prepare a private production environment, HTTPS origins, a stable encryption key, and durable document storage before release. Never reuse development credentials or reset existing deployment volumes.

Follow [Docker operations](docs/docker.md), [deployment and recovery](docs/deployment.md), and [security](docs/security.md). The [GitHub Actions workflow](.github/workflows/ci.yml) runs configured build/test/security checks; it does not automatically deploy to production.

Current limitations:

- Most schemes have discovery metadata rather than complete approved eligibility policies. Relevance matching cannot determine every individual or institutional target group.
- Static source metadata can become outdated. Monitoring is opt-in for approved sources, and material changes require human review.
- Real Gemini processing requires configured credentials. Mocked AI regressions do not establish live-model accuracy or current government-policy approval.
- In-app notifications are implemented; email delivery, password-reset delivery, MFA, and identity verification are not provided by this MVP.
- Guest answers are intentionally lost on reload. Saved private data requires the stable encryption key and a separate backup/recovery procedure.
- Local production-profile verification is not a live cloud deployment. Real cloud/S3 connectivity and any deployment must be verified separately.

## Documentation

| Topic | Guides |
|---|---|
| Current user flow | [Profile-first recommendations](docs/profile-first-recommendations.md), [illustrative assessments](docs/demonstration-assessments.md) |
| System and data | [Architecture](docs/architecture.md), [database](docs/database.md), [datasets](docs/datasets.md), [API](docs/api.md) |
| Rules and evidence | [Eligibility engine](docs/eligibility-engine.md), [rule semantics](docs/rules.md), [human review](docs/human-review.md) |
| AI and documents | [Document processing](docs/document-processing.md), [Gemini](docs/gemini-integration.md), [AI agents](docs/ai-agents.md), [RAG](docs/rag.md) |
| Policies and users | [Policy monitoring](docs/policy-monitoring.md), [versioning](docs/policy-versioning.md), [authentication](docs/authentication.md), [reassessment](docs/reassessment.md), [notifications](docs/notifications.md) |
| Verification and release | [Testing](docs/testing.md), [Docker](docs/docker.md), [deployment/recovery](docs/deployment.md), [security](docs/security.md), [final project report](docs/final-project-report.md) |

Historical phase reports remain under `docs/`; the current user flow and verification reports supersede their older descriptions where behavior has changed.
