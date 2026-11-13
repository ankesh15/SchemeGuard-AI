# Phase 5 — automated policy monitoring

Implemented opt-in approved-source monitoring; durable PostgreSQL jobs/outbox; Redis/Celery worker queues and a PostgreSQL-locked singleton Beat scheduler; secure conditional fetching/checksum comparison; immutable document version preservation; reused PyMuPDF/LangGraph processing; deterministic old/new policy comparisons; clarification/rejection/approval through the Phase 4 human review; approved-only public updates; and administrator monitoring/change/history/failure pages.

Existing Phase 4 was inspected and verified before changes: 372 backend tests and 47 frontend tests passed, all three original services were healthy, and a private pre-Phase-5 PostgreSQL backup was created. The actual working catalog remains 283 records (282 government and one fictional), not an assumed 300. Existing official documents, pending review, approved fictional rules and static datasets were preserved.

## Database and APIs

Incremental migration `0008_policy_monitoring` adds background_jobs, source_monitoring_config, monitoring_runs, policy_changes, policy_change_details and policy_change_review_events. History snapshots/events are append-only, and source/document/scheme/approved-rule provenance is enforced by a trigger. Final change decisions cannot be rewritten. Existing RuleSet/RuleCondition/RuleEvidence and DocumentVersion remain canonical. No new ingestion system or duplicate executable-rule representation is introduced.

Authenticated APIs: GET/POST `/api/v1/admin/monitors`; PATCH `/monitors/{id}`; POST `/monitors/{id}/check`; GET `/monitoring-runs`; GET `/policy-changes` and `/{id}`; POST `/{id}/approve`, `/reject`, `/clarify`. Approval uses the same exact-revision/digest/body contract as Phase 4. Public GET `/api/v1/policy-updates` returns only verified changes linked to published rules. Existing stateless eligibility requests now optionally accept an assessment date. Unreviewed overlapping effective policies return a conflict instead of silently choosing the highest number.

## Operations and failures

Monitoring is disabled by default. Only an active administrator's explicitly approved source can be enrolled, with recorded access permission notes, daily/weekly UTC schedule and source-specific minimum interval. No live source is enrolled merely because it exists in the catalog. Checksum changes create preserved versions and pending policy changes, not automatic rule approval. A source becomes potentially outdated if its document changes or verification fails; the last approved policy is retained.

ETag/Last-Modified are hints, with periodic unconditional retrieval; 304 requires an existing original/checksum. Redirects stay rejected and require separately approving the final URL. Existing TLS/IP pinning, SSRF rejection, file/page limits and parser isolation remain in force. Identical normalized text can avoid AI cost but cannot establish visual/table equivalence; it remains inspectable. Unsupported, missing or ambiguous extracted conditions remain inconclusive. Explicit deadline/document-label differences are informational source facts, not invented rule operators.

Jobs have finite leases, a PostgreSQL execution lock, bounded attempts, timeouts, exponential retry delays and durable state. Crash or Redis delivery duplication cannot create duplicate rule versions. Beat only dispatches due PostgreSQL schedules/outbox records; its process-lifetime PostgreSQL lock prevents a second logical scheduler. Warm worker shutdown and broker visibility settings are documented in the Celery guide.

## Verification

Final executed test results, Docker health and operational probe results are appended after verification. Synthetic policies are used for deterministic monitoring and simulated human approval; no real government policy is automatically approved. The authorized historical official Saksham PDF remains pending actual human review. Missing Gemini credentials still prevent live model verification; this is reported rather than replaced with fabricated government rules.

Run:

```bash
docker compose up --build -d
docker compose exec api alembic upgrade head
docker compose exec api python -m tests.run -q
docker compose exec frontend npm test
docker compose exec frontend npm run typecheck
python3 scripts/verify_workers.py
docker compose logs --tail 50 worker scheduler
docker compose ps
```

Created modules: `app/models/monitoring.py`, `schemas/monitoring.py`, `services/jobs.py`, `services/monitoring.py`, `services/policy_diff.py`, `api/v1/monitoring.py`, `workers/{celery_app,monitoring_tasks,document_tasks,comparison_tasks,scheduler}.py`; migration 0008; backend monitoring tests; frontend monitoring/change list/detail pages and components/tests; worker verification script and three Phase 5 guides. Modified secure fetcher, rule repository, assessment-date schema/service, Phase 4 review/publication hooks, route exports, locks/settings/Compose, admin navigation/proxy, migration assertions, README and persistence verification.

User-specific notifications are intentionally absent from Phase 5. They are implemented only in the separately requested Phase 6 after this phase's verification gate.

Suggested commit: `feat: add durable approved-source monitoring and reviewed policy updates`.

## Executed results before Phase 6

- Backend: **389 passed in 44.47 seconds** (including real PostgreSQL, all legacy engine/API/document/review tests, migration round-trips/drift checks, monitoring scheduling/detection, retries, expired leases, invalid downloads, duplicate delivery, clarification/rejection and simulated change approval).
- Frontend: **50 passed** across eight files; TypeScript passed. Ruff and strict mypy passed for all 90 backend modules.
- All six Docker services reached healthy state after the scheduler SDK connection-name collision was fixed. Both application images built successfully. A real Beat/Redis/worker probe reached SUCCEEDED in one attempt and duplicate delivery did not execute it again. A second Beat leader was rejected by the PostgreSQL lock.
- Bugs fixed during verification: comparison-list aliasing incorrectly marked material differences inconclusive; the scheduler's leader connection originally shadowed Celery's broker connection; redirect errors needed to be rejected before reading optional headers; final rejection snapshots needed to be frozen before the decision; and admin review responses now refresh workflow state after independent graph sessions publish.
- No real source was automatically enrolled and no government rule was approved. Live external monitoring/AI remains dependent on approved access conditions, reachable official hosts and Gemini credentials.

Phase 5's implemented acceptance paths pass under deterministic external/AI fixtures; real background delivery is verified independently. The previously existing 283 scheme rows, two documents and historical rule/review state remain preserved. Phase 6 begins only after this verification gate, as explicitly requested.

Final Docker checks: all six services healthy; isolated production Next.js build passed; all public/checkpoint rows and original PDF hashes matched after recreating all six containers. Phase 5 verification completed before Phase 6 implementation began.

The subsequent Phase 6 adds citizen functionality and its own migration; Phase 5's pre-transition results above remain its recorded verification gate. The final combined regression suite contains 414 passing backend tests and 60 passing frontend tests. See [full file inventory](phase56-file-inventory.md) and [Phase 6 completion report](phase6-user-system.md) for the final state.
