# Phase 2 implementation report

**Phase 2 is complete. All acceptance criteria passed using the permitted, clearly labeled fictional-policy fallback.** Date: 12 November 2026 (Asia/Kolkata). All three services remain running and healthy.

## Phase 1 baseline and preservation

Before proceeding, the existing API/database containers were healthy, health/readiness/discovery endpoints returned 200, Alembic was at `0001_initial_metadata` with no schema drift, and all **49 Phase 1 tests passed**. Inspection found a valid Git repository and clean working tree.

The running containers initially referenced an older checkout under `Documents`. They were rebound to the requested workspace with the same Compose project and PostgreSQL volume. An empty, unapplied migration generated in that old checkout was removed before creating the actual Phase 2 migration. No existing application records were deleted or reset. Migration tests explicitly verify retention of Phase 1 scheme/source/document rows, IDs, and creation timestamps.

## Features implemented

- Standalone deterministic Python engine using validated typed expressions, Decimal numeric comparisons, strict ISO calendar dates, all eight requested operators, nested AND/OR, exclusions, and conditional branches.
- Correct PASS/FAIL/UNKNOWN truth tables, missing-field reporting, complete relevant decision traces, and no Python execution of stored rules.
- Versioned rule sets, immutable conditions/evidence, approval metadata and effective dates, same-scheme source-document association, and evidence references.
- Approved/effective version selection only. Draft/rejected/future/expired versions cannot be evaluated; malformed approved configuration fails closed.
- Eligibility service with required assessment wording, exact evaluated version/document hash, evidence, and no official approval claims.
- Responsive Next.js/TypeScript/Tailwind frontend: landing, scheme explorer, scheme details, dynamic questionnaire, and report. Shared navigation/cards/components, conditional fields, validation, loading/error/empty states, and accessible labels/focus controls are included.
- Synthetic inputs and reports remain in memory. No applicant/profile/report persistence, browser storage, uploaded documents, account system, or real personal identifiers are introduced.

## Policy verification and permitted fictional fallback

The [NSP-linked Saksham guideline](https://scholarships.gov.in/public/schemeGuidelines/AICTE/AICTE_2012_G.pdf), section 2, gives an inclusive income boundary. Its [linked FAQ](https://scholarships.gov.in/public/schemeGuidelines/AICTE/AICTE_2012_F.pdf), question 1, uses a strict boundary. Their historical dates and other-aid restrictions also require review alongside the [current NSP notices](https://scholarships.gov.in/Students). A coherent current rule set could not be verified without choosing an uncertain interpretation. No real government rule was approved or published.

The implementation uses the explicitly permitted fallback: **SchemeGuard Learning Scholarship (Fictional)**. Its authored policy states that all thresholds/dates are invented software fixtures, no financial award exists, and no official application portal applies. The exact policy bytes are captured in an immutable document version. Six top-level requirements and eight questionnaire fields cover nested alternatives, boundary comparisons, date ranges, exclusion, and conditional support.

The fixture's approval basis is `synthetic_fixture` and its actor is `development-fixture`, not a fabricated human/government reviewer. Database guards prevent this basis from approving a non-demo scheme. The five real scholarship metadata records and their eleven source relationships remain present, with unavailable eligibility rules yielding UNKNOWN.

## Changed files

| Area | Files |
| --- | --- |
| Database | `backend/app/models/rule.py`, scheme/model exports, migration `0002_eligibility_rules_versioned_eligibility_rules.py` |
| Engine | `backend/app/eligibility/{__init__,expressions,engine}.py` |
| Eligibility HTTP/service | `backend/app/api/v1/eligibility.py`, router wiring, `schemas/eligibility.py`, `repositories/rule.py`, `services/eligibility.py` |
| Existing API/config | `main.py` version/CORS/no-store errors, `schemas/scheme.py` demo flag, `core/config.py`, `bootstrap.py` |
| Fictional policy | `backend/app/demo_policy.py`, `seed_demo.py`, `data/policies/demo-policy-v1.md`, identical frontend public policy |
| Backend tests | New engine/API/approval tests; migration preservation and existing immutable-truncate regressions adapted to new FKs |
| Frontend | Dockerfile/ignore, pinned package manifests, Next/TypeScript/Tailwind/Vitest configuration; `src/app`, `src/components`, `src/lib`, tests and public/synthetic response fixtures |
| Infrastructure | `docker-compose.yml`, `.env.example`, root ignore files |
| Verification | `scripts/verify_phase2.py`, expanded six-table/three-service `verify_persistence.py` |
| Documentation | README, architecture/database updates, `docs/rules.md`, this report |

No applied Phase 1 migration was edited. The Phase 1 implementation report is retained as historical documentation. No Git commit or pull request was created.

## Database migration

`0002_eligibility_rules` adds `rule_sets`, `rule_conditions`, `rule_evidence`, and `schemes.is_demo` (false default). It adds keys, indexes, date/status/approval checks, immutable-history guards, draft-only child insertion with parent locking, approval/evidence checks, and scheme-classification protection.

New rule sets start DRAFT. Only approval metadata can transition them to APPROVED/REJECTED, once. Conditions and evidence remain immutable. Document versions retain the Phase 1 immutability protections. No user/applicant table exists. Seed commands are transactional, repeatable, and preserve existing records.

Expected seeded development counts: **6 schemes** (5 government + 1 fictional), **12 sources**, **1 authored document version**, **1 approved synthetic rule set**, **6 conditions**, **6 evidence references**. Government rule-set count: **0**.

## APIs added

- `GET /api/v1/schemes/{id}/requirements`: approved effective version, questionnaire fields, requirement evidence, notices, and application link where appropriate. Unavailable approved rules return `available=false` without inventing requirements.
- `POST /api/v1/eligibility/check`: validates the scheme ID, explicit synthetic flag, and scalar profile; returns result, required wording, traces, missing fields, evidence, and actual evaluated version. No approved rules return UNKNOWN with no version. Raw profiles are neither returned nor stored.

Existing health/readiness and discovery/detail APIs are preserved. Invalid inputs return 422; absent schemes 404; database or unsafe configuration failures 503. GET/POST browser CORS and no-store assessment headers are verified.

## Docker changes

Services are now exactly `frontend`, `api`, and `db`. Frontend uses Node 24, Next.js 16, React 19, TypeScript, Tailwind, a non-root runtime, hot reload, and dependency/cache volumes. API retains non-root execution and hot reload, adds optional development seed bootstrap, and applies the new migration on startup. PostgreSQL keeps its existing named volume.

Only loopback ports 3000/8000 are published. PostgreSQL has no host port. Next.js server rendering uses `http://api:8000`; the browser uses `http://localhost:8000`. No backend database secret is supplied to the frontend. Both apps have health checks and startup dependencies.

## Test and verification results

| Check | Result |
| --- | --- |
| Phase 1 baseline | PASS — 49 existing tests, healthy containers, APIs, no schema drift |
| Backend full suite | **PASS — 210 tests**: 138 pure engine cases, 22 eligibility/API/approval cases, 2 migration cases, and existing regressions |
| Frontend suite | **PASS — 21 tests** across form validation, dynamic questionnaire, privacy/loading/errors, and report rendering |
| Backend strict typing | PASS — 36 application source files |
| Backend Ruff lint/format | PASS — 51 Python files |
| Frontend TypeScript | PASS |
| Frontend Prettier | PASS |
| Dependency consistency | PASS — Python `pip check`; frontend installs from pinned npm lock |
| Clean Next.js build | PASS — optimized compile, TypeScript, static generation, and route collection in an isolated container |
| Live HTTP smoke | PASS — five frontend pages, public API, CORS preflight, PASS/FAIL/UNKNOWN, unapproved-government fallback, and exact served policy hash |
| Docker networking/users | PASS — frontend resolves API by service name; frontend UID 1000 and API non-root UID 10001 |
| Desktop browser journey | PASS — explorer/state filter/search/detail/questionnaire/report and expanded evidence |
| Browser validation | PASS — invalid age rejected before submission; synthetic example submits successfully |
| Mobile browser journey | PASS — mobile menu, responsive form/report, failed age assessment, conditional field, missing-percentage UNKNOWN result |
| Mobile overflow | PASS — content width equals viewport content width |
| Report refresh privacy | PASS — refresh clears in-memory report and renders empty state |
| Final one-command startup | PASS — `docker compose up --build -d`; frontend/API/database healthy on the expected local URLs |
| Six-table container persistence | PASS — all rows in all six tables unchanged after recreating all three services; repeat bootstrap seeds preserve existing records |

The original truncation test was strengthened to use CASCADE so it exercises the immutable trigger despite new foreign-key references. A test run interrupted during service recreation was rerun successfully; its two inactive disposable test databases were removed. No application database reset occurred.

## Issues fixed

- Corrected the existing container bind path so tests/hot reload use the requested checkout.
- Adapted the document immutability regression to the new FK graph while retaining protection.
- Fixed landing-page JSX syntax before frontend type/build checks.
- Fixed a singular scheme count, input-hint contrast, Next.js smooth-scroll annotation, ESM test configuration warning, and formatting findings during frontend QA.
- Confirmed synthetic boolean false is preserved, numeric precision reaches Decimal intact, hidden conditional inputs are omitted, and blank answers are not forced into PASS.
- Hardened numeric range validation so extremely large decimal exponents are rejected with 422 rather than triggering Decimal context overflow; added API and positive/negative exponent regressions.

## Known limitations and explicit scope boundaries

Government eligibility rules are intentionally unavailable pending source reconciliation and actual human approval; the accepted development journey uses the labeled fictional fallback. A synthetic-profile flag is a development guard, not identity verification or consent for real data. No personal profiles should be entered.

This is a local development stack. Production deployment configuration, authenticated administration/reviewer identity, database role separation, edge request limits/rate limits, backup restoration, load testing, and a comprehensive external accessibility/security audit are not provided. Database-owner privileges can bypass triggers. Reports are memory-only and cannot be reopened after refresh. Government application links are external NSP links; this app submits no official application.

No LLM integration, LangGraph, extraction pipeline, policy-change monitoring, reassessment jobs, notifications, Celery, Redis, or next-phase functionality is implemented.

## Exact run and check commands

```bash
python3 scripts/init_env.py
docker compose up --build -d
docker compose up -d --wait --wait-timeout 120
docker compose exec api alembic upgrade head
docker compose exec -T api python -m tests.run
docker compose exec -T frontend npm test
python3 scripts/verify_phase2.py
python3 scripts/verify_persistence.py
```

Open `http://localhost:3000`, choose the fictional scholarship, and use the synthetic example. API/docs remain available at `http://localhost:8000` and `http://localhost:8000/docs`.

## Acceptance criteria

| Criterion | Result |
| --- | --- |
| Phase 1 verified before Phase 2 | PASS — healthy containers, existing APIs, migrations, 49 baseline tests |
| Safe deterministic comparisons, three-valued groups, exclusions, conditions | PASS |
| Only approved effective immutable rule versions evaluated | PASS |
| Real scholarship rules or permitted fictional fallback | PASS — conflicts documented; fictional policy labeled throughout; no government rules published |
| Frontend selection → synthetic questionnaire → explainable report | PASS — desktop and mobile browser checks, including all three outcomes |
| Version, evidence, missing information, and appropriate application link behavior | PASS — fictional scheme correctly has no official application link |
| Full stack starts with one Compose command | PASS |
| Tests and relevant build/static checks pass | PASS — 210 backend tests, 21 frontend tests, frontend build and type checks |
| Existing records and immutable policy history persist | PASS — additive migration preservation and six-table recreation snapshots |

No required Phase 2 work remains. No Phase 3 implementation was started.
