# Architecture — Phase 2

SchemeGuard AI is a modular monolith with a separate Next.js frontend and PostgreSQL. Only three Docker services run: frontend, API, and database. Background workers, LLMs, policy monitoring, and notifications are deferred.

## User and data flow

`Browser → Next.js pages → FastAPI v1 → services → repositories → async SQLAlchemy → PostgreSQL`

Public discovery uses the existing scheme service and repository. Details and questionnaire pages use server-rendered reads through `INTERNAL_API_URL=http://api:8000`; explorer filtering and the questionnaire POST use the browser-reachable `NEXT_PUBLIC_API_URL=http://localhost:8000`. The frontend and API share the ingress network; only the API and database share the internal database network. PostgreSQL exposes no host port.

`Synthetic questionnaire → eligibility/check → approved effective rule version → typed program → pure engine → traces/evidence → in-memory React report`

The eligibility service owns version selection, validates the loaded configuration, maps each top-level condition to its immutable evidence, and invokes the standalone engine. The engine imports no FastAPI, SQLAlchemy, filesystem, or external service client. Pydantic discriminated unions validate the safe expression tree. Decimal and ISO date comparisons, three-valued groups, exclusions, and conditional branches are deterministic. A malformed approved program fails closed; missing values and unavailable approved rules never become an assumed pass.

## Module boundaries

- `app/api/v1`: HTTP validation, dependency injection, typed responses, request headers.
- `app/services`: discovery behavior and eligibility orchestration/version selection.
- `app/repositories`: bound SQL queries and eager evidence loading.
- `app/models`: typed SQLAlchemy tables and relationships.
- `app/schemas`: API and seed contracts.
- `app/eligibility`: pure typed expressions, profile validation, three-valued evaluation, and traces.
- `app/demo_policy.py` and `seed_demo.py`: the explicitly authored development fixture and its repeatable seed.
- `frontend/src/components`: reusable navigation, scheme cards, explorer, questionnaire, report, and memory-only report context.
- `frontend/src/lib`: API contract types, server/browser URL selection, and form-domain validation.

## Approval, provenance, and interpretation

The five government scheme records are unchanged discovery metadata with an added `is_demo=false` classification. No government rule set is approved. The fictional example is marked at every stage and has no official application link or award. Its source bytes, content hash, version, and section excerpts support every test condition.

Rule content and evidence are immutable. Database guards enforce draft assembly, one-way approval, evidence coverage, and distinct human-review/synthetic-fixture bases. The public HTTP API cannot create or approve rules. In future phases an authenticated reviewer must approve any government rules before publication. Neither the engine nor an LLM can declare official government approval.

The reports use exactly: Known conditions satisfied, Requirements not satisfied, and More information required. Top-level requirement outcomes are distinct from nested alternative/conditional guard traces. See rules.md for truth tables and missing-field behavior.

## Privacy and security

The public eligibility request requires an explicit synthetic-profile flag and validates a bounded mapping of scalar/null inputs. Dynamic validation rejects unknown fields, invalid types, non-finite values, invalid calendar dates, and unsupported choices. Missing inputs are permitted so that the engine can report UNKNOWN. The questionnaire requests no names, contact details, Aadhaar identifiers, uploaded documents, or accounts.

Runtime submissions are never written to SQL, a queue, files, browser storage, URLs, or logs. Report state lives only in the client React provider and clears on refresh. Authored synthetic examples and synthetic-only API response fixtures are checked in solely for development tests. Eligibility responses use no-store caching headers and do not include raw applicant values. JSON request logs contain route templates, request IDs, statuses, duration, and safe error types, without request bodies, query strings, or raw exception messages. Validation errors omit raw inputs.

The backend factory owns the async connection pool and disposes it on shutdown. Sessions are injected per request; eligibility handlers perform reads only. Explicit CORS origins allow GET/POST without credentials. Backend secrets remain in ignored local configuration/environment and are never passed to the frontend. Both application containers run as non-root users.

## Startup and development

Compose first waits for PostgreSQL health. The API applies Alembic migrations and the optional insert-only development seeds before starting. Existing records and the database volume are preserved. The frontend waits for API readiness. API and frontend have hot reload, and the frontend has dedicated dependency/cache volumes.

The API readiness check performs a live bounded database query; its process-health endpoint does not require PostgreSQL. The frontend has its own lightweight health route. Image builds use locked dependencies. A frontend production-mode compile is tested in an isolated disposable container so its output cannot interfere with the running development server. This is build verification, not a production deployment configuration.

## Verification boundaries and limits

PostgreSQL integration tests cover migrations, relationships, immutable history, approval/version selection, discovery, eligibility, and preservation of existing Phase 1 rows. Pure engine tests cover every supported operator and AND/OR truth table. Frontend tests use captured public/synthetic API contracts and exercise dynamic inputs, validation, conditional visibility, loading/errors, report rendering, and absence of browser-storage writes. Browser QA verifies the complete desktop/mobile journey, PASS/FAIL/UNKNOWN results, evidence disclosure, filtering, and refresh privacy behavior.

Authentication workflows, production database role separation, rate limits/edge body limits, backup restoration, large-data performance, official-policy reconciliation, AI document processing, and production deployment are outside this phase. A database owner can bypass triggers and must be treated as privileged. No personal-profile persistence or administrative publication interface is introduced.
