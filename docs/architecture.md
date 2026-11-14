> Current public journey: Home → optional five-step details → shared recommendation service → personalized results → source-backed scheme details → existing assessment engine. The original phase descriptions below are historical; [profile-first recommendations](profile-first-recommendations.md) describes the latest discovery integration.

# Architecture — Phase 3

SchemeGuard AI is a modular monolith with a separate Next.js frontend and PostgreSQL. Only three Docker services run: frontend, API, and database. Gemini performs administrator-requested candidate extraction. Background workers, policy monitoring, and notifications remain deferred.

## User and data flow

`Browser → Next.js pages → FastAPI v1 → services → repositories → async SQLAlchemy → PostgreSQL`

Public discovery uses the existing scheme service and repository. Details and questionnaire pages use server-rendered reads through `INTERNAL_API_URL=http://api:8000`; explorer filtering and the questionnaire POST use the browser-reachable `NEXT_PUBLIC_API_URL=http://localhost:8000`. The frontend and API share the ingress network; only the API and database share the internal database network. PostgreSQL exposes no host port.

`Synthetic questionnaire → eligibility/explain (or compatibility eligibility/check) → approved effective rule version → typed program → pure engine → traces/evidence → in-memory React report`

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

The original five government records are unchanged; 277 additional curated records expand discovery to 282 government schemes with `is_demo=false`. No government rule set is approved. The fictional example is marked at every stage and has no official application link or award. Its source bytes, content hash, version, and section excerpts support every test condition.

Rule content and evidence are immutable. Database guards enforce draft assembly, one-way approval, evidence coverage, and distinct human-review/synthetic-fixture bases. The public HTTP API cannot create or approve rules. Phase 4 requires an authenticated human reviewer to approve the complete saved proposal before publication. Neither the engine nor an LLM can declare official government approval.

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

Production database role separation, external edge protection, large-data performance, official-policy reconciliation and production deployment remain deferred. A database owner can bypass triggers and must be treated as privileged. Phase 6 adds encrypted private profile/assessment storage through the shared authentication system. The Phase 4 administrator publication interface is described below.

## Curated catalog import

`data/schemes/*.json → load_catalog → complete Pydantic validation/deduplication → advisory-locked transaction → insert missing schemes/sources → committed import statistics`.

The command performs no network IO. It supports any record count, direct category-file discovery, and legacy single-file input. Existing matching slugs and their source relationships are skipped rather than overwritten. Rules, documents, profiles and reports are outside this import path. See [datasets.md](datasets.md) for provenance and operating limits.

Discovery exposes computed `eligibility_available` flags and an optional availability filter, based on approved effective policy presence and scheme status. Dynamic category/state facets use actual database metadata. No rule engine logic or approval workflow changed. The frontend retains its visual design, fetches direct scheme IDs independently of catalog pagination, and guards stale success/error callbacks when filters change quickly.


## Phase 3 integration

`Admin browser → same-origin Next.js proxy → authenticated FastAPI admin routes → exact-URL authorization → immutable DocumentVersion + private PDF → bounded parser subprocess → page/block records → stable chunks → Gemini structured output → typed validation and located evidence → pending-only candidates`.

`app/ingestion` owns acquisition, private originals, parsing, normalization and chunking. `app/ai` owns provider abstraction, bounded structured-output schemas, safe engine mapping and grounding checks. `app/auth` owns Argon2id verification, hashed cookie sessions, CSRF/origin checks, SQL rate limits and CLI-only provisioning. The ingestion service orchestrates transactions without writing RuleSet, RuleCondition or RuleEvidence. Those existing tables remain the only executable eligibility representation. Candidates remain immutable proposals; Phase 4 adds their separate review and publication workflow.

Admin requests use a same-origin `/api/admin/` proxy to the fixed Docker API host, forwarding only the administrator cookie and CSRF/origin/content headers. Layouts verify sessions on the server; every backend admin endpoint independently enforces the administrator role. Public discovery and synthetic-profile assessment contracts are unchanged. LLM configuration stays on the backend.

PDF parsing is a Linux subprocess with memory, CPU, output, page, byte and wall-time bounds; its environment excludes application credentials. Attachments/scripts are not executed, and text is rendered as plain text. The process limit is defense in depth, not a complete hostile-native-code sandbox. Downloads validate every DNS answer, pin TLS sockets to an approved public IP with original hostname verification, use timeouts, and reject redirects. See [document processing](document-processing.md) for security boundaries and limitations.

## Phase 4 integration

`Authorized document → typed LangGraph stages → Phase 3 extraction → deterministic evidence and schema checks → PostgreSQL interrupt checkpoint → immutable human revisions/decision → revalidated atomic RuleSet publication`.

The existing document and rule tables remain canonical. New workflow, review, event and publication tables link them without duplicating executable rule representations. Only the publisher writes existing RuleSet/RuleCondition/RuleEvidence after a recorded human approval. Historical content is protected by existing and new database guards. Checkpoints live in `sg_checkpoints`, with strict serialization and no applicant data.

`Server deterministic report → exact approved scheme/document-scoped pgvector retrieval → verified page citations + deterministic explanation`. Optional Gemini output can order existing identifiers only. Constrained questions quote approved document passages and cannot determine eligibility. The original `/eligibility/check` response contract remains supported.

The three services and existing data volumes are preserved. PostgreSQL remains major 16/Alpine with a SHA-pinned pgvector build. Source-document storage is unchanged. See [agent workflows](agent-workflows.md), [RAG architecture](rag-architecture.md), and [human review](human-review.md) for recovery, security, approval and operational limits.

## Phases 5 and 6

Opt-in source monitoring uses the existing secure fetch/parse/LangGraph review path. PostgreSQL owns durable job and policy history; Redis carries ID-only messages to bounded Celery workers. One PostgreSQL-locked Beat leader schedules due work. Human publication atomically links a new immutable rule version and reassessment outbox job. Owner-locked reassessment checks preferences/consent, runs the unchanged deterministic engine using the necessary current stored fields, and appends encrypted reports/impacts and deduplicated approved-only notifications. Next.js fixed-route proxies and server layouts reuse shared HttpOnly sessions and role/CSRF checks. The frontend never receives the encryption key or submits private profiles to Gemini/RAG. See the Phase 5/6 reports for integration and executed verification.

## Phase 7 production boundary

Production now has separate non-root backend and standalone Next.js images and an independent six-service Compose manifest. Only release tooling runs owner migrations; long-running processes receive a restricted runtime DB role. Browser public/private calls are same-origin and allowlisted, so cookies need no cross-origin relaxation and backend secrets stay server-only. Production HTML is dynamic with a fresh strict script nonce, host allowlists, secure cookies and bounded request bodies.

DocumentStorage remains the canonical content-addressed storage contract, with a configured S3 adapter sharing the same immutable keys/checksums and a dry-run/copy verification utility. Existing filesystem originals are not silently moved. PostgreSQL/checkpoint and original-document backup/recovery were tested locally. CI and measured demonstration/evaluation artifacts are documented in testing.md and final-project-report.md. No live cloud deployment is implied.

## Scheme-based demonstration assessments

The public selection UI uses the existing PostgreSQL scheme APIs with `is_demo=false`. `app.assessment` contains nine validated, versioned project-authored templates, separate from SQLAlchemy policy models. `AssessmentService` first delegates approved policy selection/validation to the existing eligibility service. Only when no applicable approved rule exists does an explicit category mapping supply an illustrative Program to the same deterministic engine. Ambiguous or invalid approved policies fail closed; templates cannot hide those failures.

The report records the assessment mode and criteria fingerprint. Illustrative traces never borrow government evidence or RuleSet IDs and do not invoke Gemini/RAG, write saved reports, enqueue monitoring/reassessment, or notify users. Authenticated saving and worker paths continue to use only the original approved-policy eligibility service. No schema migration or change to immutable history was needed.


## Profile-first discovery boundary

`DiscoveryProvider` holds transient answers and recommendation explanations in per-tab React memory. It never writes to browser storage. The homepage has no database fetch. Guests POST a bounded ProfileData-compatible body through the fixed public Next.js proxy; no cookies are forwarded. Citizens may explicitly save that same data through the existing CSRF-protected encrypted profile API. Login, logout and account deletion clear transient private state; guest registration may carry unsaved guest answers to the consent form.

`RecommendationService` reads the current non-demo, non-inactive PostgreSQL catalog, combines explicit category/occupation/student/employment signals, considers verified geography and optionally calls the existing approved-rule version selector and typed engine. Unverified coverage remains discoverable. Demonstration templates provide assessment availability only and never numeric ranking requirements. The dashboard and authenticated saved-profile endpoint reuse this service. No new tables, cache, worker queue, AI pipeline or incompatible profile store is introduced.
