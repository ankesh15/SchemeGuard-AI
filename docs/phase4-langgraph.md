# Phase 4 implementation report — LangGraph processing and RAG

Verified locally on 13 November 2026 (Asia/Kolkata). Scope stops at Phase 4.

## Outcome

Implemented the typed, PostgreSQL-checkpointed extraction → verification → schema validation → human interrupt → publication workflow; administrator review/revisions/decisions; immutable publication into the existing rule tables; pgvector embeddings and approved-document retrieval; deterministic grounded explanations and constrained document questions; and the corresponding Next.js workspace.

The application is running at [localhost:3000](http://localhost:3000), API [localhost:8000](http://localhost:8000), and [FastAPI docs](http://localhost:8000/docs). The engineering workflow is verified using deterministic AI fixtures and simulated human decisions in disposable PostgreSQL. **No real government policy was approved. Live Gemini generation/embedding was not verified because credentials are absent.** The authorized historical official document is retained in an actual pending human review, as required by the approval boundary.

## Repository audit and preservation

The baseline was inspected before integration. Its 321 backend and 40 frontend tests passed before changes. The real catalog has **283 database records: 282 government schemes and one fictional fixture**, not 300. Existing static category manifests, insert-only seed behavior, discovery/filter/pagination APIs, frontend design, administrator sessions, Phase 3 original storage/parser/chunking/Gemini mapper, and deterministic PASS/FAIL/UNKNOWN engine were reused.

Existing canonical models are Scheme, SchemeSource, DocumentVersion; RuleSet, RuleCondition and RuleEvidence; User/LoginSession/AuditEvent/RateLimit; and the Phase 3 asset/page/chunk/job/candidate/evidence/error/source-authorization entities. The previous document/rule migrations and historical records were not rewritten. No applicant profiles, saved assessments, citizen registration, worker queue or policy-monitoring feature was added.

The pre-change snapshot contained 625 rows across 13 domain/history tables. Every original JSON row was compared after integration and preserved unchanged. Catalog smoke verification still finds 282 official records, 23 categories and 48 explorer pages at its test page size.

## Functionality

- Typed LangGraph state and seven explicit stages, stable workflow UUID/thread IDs, official async PostgreSQL saver and durable interrupt/resume. Request-key idempotence, bounded retries/timeouts, safe failure history, explicit resume and safe undecided cancellation.
- Phase 3 extraction reused directly, including exact-document successful extraction reuse. Stable job IDs protect checkpoint replay from duplicate paid extraction. Fixture provider labels remain visible.
- Located page evidence checks, supported typed fields/operators, quantitative thresholds, annual INR/percentage units, date boundaries, exception/negation findings and bounded complete-program contradiction checks. Missing/ambiguous information cannot silently become an approved value.
- Immutable original proposal plus append-only administrator revisions. Exact revision/digest decisions, CSRF/origin/role/session checks, substantive notes, page inspection and completeness/applicability attestations, findings acknowledgement, duplicate-decision prevention and audit events.
- Publication revalidates the exact saved decision, active reviewer, source authorization, original checksum, every condition's evidence, effective-date basis, complete program and explicit overlapping-version review. A scheme lock serializes version numbers. Draft parent, conditions, evidence, approval metadata and publication ledger commit atomically; replay is idempotent.
- 768-dimensional normalized chunk embeddings, model/provider namespaces, atomic idempotent indexing, exact cosine scans, exact scheme/document/approved-version scoping, source checksums and page citations. Failures retain originals/history; bounded lexical fallback is explicit. Local feature hashing is an explicitly labeled test fixture, forbidden in production.
- New explanation API evaluates on the server and copies the deterministic result/traces/version into the explanation. Templates always work from approved evidence. Optional Gemini output is restricted to ordering existing trace/citation IDs and cannot supply decisions, thresholds or factual policy prose. Arbitrary applicant profiles are never sent to Gemini.
- Constrained document questions quote only relevant approved-document passages, with page links or an explicit evidence gap. Only fixed intent queries reach the embedding provider.
- Protected workflow overview, status/history/errors, pending queue, original/current JSON comparison editor, evidence viewer, revision history, approve/reject controls, document workflow/index actions, public approved history and grounded report citations. The existing visual design is extended with reusable controls and responsive layouts.

## Database changes

| Revision | Additions |
| --- | --- |
| `0005_workflow_rag` | pgvector extension; agent_workflows, workflow_events, policy_reviews, review_revisions, review_decisions, rule_publications, chunk_embeddings; FK/index/unique/status and append-only guards |
| `0006_graph_checkpoints` | SDK-compatible checkpoint tables/indexes in sg_checkpoints, with ten current saver migration versions owned by Alembic |
| `0007_workflow_provenance` | Matching document/job, current review/revision/administrator, approved publication provenance and immutable workflow identity/binding guards |

Live working database after the demonstration: **283 schemes, two document versions, one existing fictional RuleSet, one pending extracted candidate, one workflow, one review/revision, zero review decisions/publications, and zero semantic embedding rows** (Gemini credentials absent). The pending thread has six checkpoint snapshots. These counts distinguish live records from isolated test fixtures.

Alembic upgrade, repeated upgrade, downgrade/re-upgrade in disposable databases, old-record preservation and schema/model drift checks are tested. The live head is `0007_workflow_provenance`; `alembic check` reports no new operations. Existing RuleSet/RuleCondition/RuleEvidence/DocumentVersion representations remain canonical.

## API changes

All existing contracts remain available, including `/eligibility/check`. New admin endpoints independently require active administrator authorization and CSRF/origin checks for mutations; their Next proxy forwards only approved headers/routes and has bounded review-body size.

| Method | Endpoint |
| --- | --- |
| POST, GET | `/api/v1/admin/workflows` |
| GET | `/api/v1/admin/workflows/{id}` |
| POST | `/api/v1/admin/workflows/{id}/resume` |
| POST | `/api/v1/admin/workflows/{id}/cancel` |
| GET | `/api/v1/admin/reviews` |
| GET | `/api/v1/admin/reviews/{id}` |
| POST | `/api/v1/admin/reviews/{id}/revisions` |
| POST | `/api/v1/admin/reviews/{id}/approve` |
| POST | `/api/v1/admin/reviews/{id}/reject` |
| POST | `/api/v1/admin/documents/{id}/index` |
| GET | `/api/v1/schemes/{id}/rule-history` |
| POST | `/api/v1/schemes/{id}/questions` |
| POST | `/api/v1/eligibility/explain` |

Lists paginate and validate status/query bounds. Invalid policy bodies return 422, stale revisions/duplicate decisions or active workflow locks return 409, missing entities return 404, authentication/authorization return 401/403, and provider/index unavailability returns safe failures. Failed graph invocations retain a FAILED workflow resource for inspection instead of concealing the saved history.

## Docker verification

Exactly three services remain: **frontend, api and db**. All were built successfully and reported healthy after recreation. API/frontend remain non-root and use development hot reload; PostgreSQL has no exposed host port. Existing postgres_data and document_data volumes are retained.

The database image builds official **pgvector 0.8.7** from a checksum-pinned archive on the same PostgreSQL 16 Alpine base, preserving the major version, libc and data directory. Before switching the existing service, a private 130142-byte PostgreSQL backup was made and restored into an isolated temporary verification container. The restore retained all 283 schemes and both document versions; CREATE EXTENSION vector succeeded at 0.8.7. The temporary verification container was removed; the existing volume was never removed or reset.

`verify_persistence.py` then recreated all three services and compared all **25 public tables, four checkpoint tables and original PDF checksums** before/after. They matched. An authenticated post-restart run resumed the same pending official workflow from its saved checkpoint. Original source/rule history remained unchanged. `pip check` found no broken requirements. An isolated `NODE_ENV=production` Next.js compile from the built frontend image succeeded without touching the running development .next volume; this is build verification, not a later production deployment.

## Tests and demonstrations

Backend: **372 tests passed in 36.07 seconds**, including real PostgreSQL integration and migration tests. Bounded explanation context, whitespace-note rejection and date-boundary verification are included. Frontend: **47 tests passed** across seven files; TypeScript and Prettier checks passed. Ruff, formatting, strict mypy and Alembic drift checks passed in the API container. After the final metadata-only explanation clarification, all **51 Phase 4 tests passed again in 11.48 seconds**, with Ruff and strict mypy clean.

Coverage includes graph transitions, extraction reuse, real Postgres checkpoints, fresh-runner resume, missing credentials/recovery, rejection/cancellation, authorization and CSRF, exact saved revisions/digests, immutable history, duplicate approvals, original preservation, contradictory policies, evidence gaps, overlap review, transactional rollback after draft insertion and later recovery, approved publication/engine PASS/FAIL/UNKNOWN, vector dimensions/namespace/scope, lexical fallback, bad embedding/model responses, timeouts/429 retries, malicious explanation plans and immutable deterministic results. Frontend tests cover explicit review attestations/page/finding requirements, unsaved invalid edits, incomplete-policy blocking, queue/provider links, metadata-only question suppression, missing evidence, citations, form validation and prior regressions.

Browser QA exercised the actual synthetic questionnaire → new explanation API → report, verified the rendered deterministic assessment and cited source excerpts, and confirmed refresh clears report memory. Administrator authorization, source evidence and all new protected Next pages were verified through real HTTP requests using the same-origin proxy; review/approval control interactions use deterministic component tests rather than claiming an actual human policy decision.

Existing live Phase 2, Phase 3 and catalog verification scripts passed. The complete publication/vector path uses **simulated automated review in disposable PostgreSQL with synthetic policy fixtures**. Those tests do not publish a government policy into the working database.

### Authorized official document

- [NSP-hosted AICTE Saksham degree guideline](https://scholarships.gov.in/public/schemeGuidelines/AICTE/AICTE_2012_G.pdf), historical July 2020 guideline; four pages, 510568 bytes.
- SHA-256 `06ebed9e50a47ae76cba985ddde78cd65f19f2193b0e4c9c164fff529580474c`.
- Document `fb71dd58-7e39-4f21-92f3-b11dbf6e9386`; scheme `557ae037-9b67-5eb1-9b1f-9ca68888c570`.
- Workflow `9e11fb00-1122-4e00-90a6-7d8422b5da29`, reused explicit fixture extraction with one page-2 disability candidate, remained PENDING_REVIEW before and after service recreation.
- [Open its protected review](http://localhost:3000/admin/reviews/0649dd5e-8e9f-5728-9c48-52e778a5f001). No decision/publication exists. Effective date, complete-policy coverage and current applicability are unverified; these block publication.
- A synthetic profile containing disability percentage 40 returns UNKNOWN / NO_APPROVED_RULE_SET. No threshold-based government approval is invented from that metadata or candidate.

Live Gemini generation and semantic embeddings remain unverified without credentials. The official full-policy approval demonstration is intentionally pending an actual human's complete source review; no automated test is presented as that review.

## Files created and modified

Created:

- `backend/app/agents/`: state, graph, extraction_agent, verification_agent, validation, proposals, review, publisher, explanation_agent and package initializer.
- `backend/app/rag/`: embeddings, retriever, citations, grounding and package initializer.
- `backend/app/models/workflow.py`, `backend/app/schemas/workflow.py`, `backend/app/api/v1/admin_workflows.py`, `backend/app/api/v1/grounding.py`.
- Three incremental migration files 0005–0007 and `backend/tests/test_phase4_workflow.py`, `backend/tests/test_phase4_units.py`.
- `frontend/src/app/admin/(workspace)/workflows/` and `reviews/` list/detail routes.
- `frontend/src/components/admin/workflows.tsx`, `review.tsx`, `workflow-start.tsx`; `frontend/src/components/policy-evidence.tsx`; `frontend/src/lib/workflow.ts`; `frontend/tests/workflows.test.tsx`.
- `docker/postgres/Dockerfile`, `scripts/verify_phase4.py`, and the four Phase 4 guides/report.

Modified:

- Backend main/factory, v1 router, admin overview, body limits, settings, models exports and Phase 3 ingestion's optional stable job ID; pyproject and both hash-locked dependency files; migration-head assertion.
- Docker Compose and .env.example.
- Frontend same-origin proxy, scheme detail/report pages, global styles, document detail/overview/session navigation, questionnaire, report context, admin types and questionnaire regression fixtures/assertions.
- README, architecture/database docs and the persistence verification script. Existing rule engine and catalog datasets are unchanged.

## Run commands

From the repository root, preserve the existing .env and volumes:

```bash
# For a fresh checkout only; preserves an existing .env:
python3 scripts/init_env.py
docker compose up --build -d
docker compose up -d --wait --wait-timeout 120
docker compose exec api alembic upgrade head
docker compose exec api python -m app.seed
docker compose exec api python -m app.auth.provision --username reviewer
```

Supply GEMINI_API_KEY in ignored .env and recreate api after changing provider configuration. Keep credentials backend-only. Open `/admin/documents` → start workflow → `/admin/reviews`. Never attest to actual human review from a script or publish incomplete historical government policy.

```bash
docker compose exec api python -m tests.run -q
docker compose exec api ruff check app tests alembic --no-cache
docker compose exec api mypy app --cache-dir /tmp/mypy-phase4
docker compose exec api alembic check
docker compose exec frontend npm test
docker compose exec frontend npm run typecheck
docker compose exec frontend npm run format:check
python3 scripts/verify_phase2.py
python3 scripts/verify_catalog.py
python3 scripts/verify_phase3.py --credentials .local/phase3-demo-credentials.json
python3 scripts/verify_phase4.py --credentials .local/phase3-demo-credentials.json
python3 scripts/verify_persistence.py
docker compose ps
```

The private credentials-file option is for the existing local demo; fresh operators may omit it and use --username to enter their own provisioned password securely. No credentials, private backup or session cookies are checked in. Do not reset the database or delete its volumes.

## Limitations and acceptance status

All implemented engineering paths are exercised with real PostgreSQL and deterministic AI fixtures. Official workflow interruption, restart recovery and UNKNOWN fallback are verified live. Human-approved immutable publication and scoped vector retrieval are verified in isolated integration tests. All acceptance criteria concerning implementation are covered; **real Gemini service access and an actual human-approved complete official-policy demonstration remain unverified**, so the report does not claim unconditional live-official acceptance.

Processing is bounded synchronous request work with explicit operator resume, not unattended crash recovery. No Celery/Redis or worker service is introduced. Evidence checks cannot prove natural-language policy completeness or resolve conflicting source notices; a qualified human must reconcile them. The editor uses the existing typed JSON schema for complex/nested changes. Vocabulary, 768 dimensions and satisfiability complexity are bounded; unsupported policy concepts require deliberate, tested schema extensions. Exact vector scans are functional at MVP scale; no large-catalog retrieval benchmark or HNSW tuning is claimed. Local hashing and lexical fallback are labeled rather than represented as semantic AI. Public document Q&A is extractive and intentionally limited.

Production database role separation, robust native-PDF sandboxing, trusted proxy rate-limit configuration, remote original storage/backups, external edge controls and later worker deployment remain documented deployment limitations. No Phase 5 monitoring, notifications, personal-profile storage or new phase work has begun.

Suggested commit: `feat: add checkpointed policy review workflows and approved-source RAG`.
