# Phase 6 — citizen accounts, private assessments and notifications

Phase 6 extends the existing modular monolith rather than replacing its authentication, deterministic engine or document workflows. A citizen can register/sign in, maintain an optional encrypted profile, browse the existing catalog, answer an approved questionnaire, save a private version-pinned report, replay the original result and review verified policy updates and notifications. Existing stateless synthetic APIs remain backward compatible. Discovery-only metadata cannot yield a supported eligibility decision. Reports continue to use PASS/FAIL/UNKNOWN and the informational descriptions, never government approval.

## Database and privacy

Incremental migration `0009_citizen_system` adds `profiles`, `notification_preferences`, `assessments`, `reassessment_events`, `notifications`. Existing `users`, `login_sessions`, `audit_events`, schemes, document versions and published RuleSet/RuleCondition/RuleEvidence are reused. Owner composite foreign keys prevent cross-account assessment chains/notification links; constraints require UNKNOWN without a policy; an insertion guard requires an effective approved policy for saved decisions. Saved reports and reassessment impacts reject updates/truncation. Account deletion explicitly deletes its private chain; it never removes government policy history. No existing record or volume is reset.

Sensitive payloads are encrypted with a separately configured stable Fernet key and bound to owner/purpose. Only required rule fields are snapshotted, not the whole profile. Overall results and relational linkage remain plaintext for owner-scoped indexing/selection. Private data is absent from Redis payloads, public APIs, application logs and browser storage. See authentication.md for security assumptions, key custody and deletion/backup limitations.

## APIs and interface

Shared-cookie authentication: POST `/api/v1/auth/register`, `/auth/login`, `/auth/logout`, `/auth/password`; GET/PATCH/DELETE `/me`. No public role selection or admin registration exists. Password reset is unavailable because no secure delivery mechanism is configured.

Citizen-only APIs: GET/PUT/DELETE `/profiles/me`; GET `/profiles/options`; POST/GET `/assessments`; GET `/{id}` and POST `/{id}/reproduce`; GET `/notifications` including unread_count; POST `/{id}/read` and `/read-all`; GET/PUT `/notification-preferences`; GET `/dashboard` and `/me/policy-updates`. Pagination/query validation, owner filtering, origin/CSRF, body bounds, password/action limits and no-store headers are enforced. All existing administrator ingestion/review/monitoring routes still require admin role.

Pages: `/login`, `/register`, `/dashboard`, `/dashboard/profile`, `/dashboard/schemes`, `/dashboard/assessments`, `/dashboard/assessments/new`, `/dashboard/assessments/{id}`, `/dashboard/notifications`, `/dashboard/policy-updates`, `/dashboard/settings`. The existing navigation, Explorer, questionnaire fields, report/evidence components and light theme are reused. Protected server layouts check the backend session; all API actions recheck authorization. Session expiry produces a sign-in message. Forms provide validation, optional unknown inputs, explicit reassessment consent, loading/error/empty states and deletion acknowledgements. No profile is sent to Gemini.

Administrator navigation now consolidates scheme/approved-history inspection, documents/sources, graph workflows, human review, monitoring, changes/failures and audit logs. Catalog edits remain through the validated append-only seed command; government policy publications still require the existing full human review UI.

## Publication and reassessment

Phase 5 human publication atomically enqueues a durable ID-only reassessment job. After a verified material change becomes effective, the existing workers identify only interested saved assessments, check citizen activity and consent/preferences, load the current authorized stored profile, run the same deterministic engine and append a new assessment with encrypted condition-level impact. Original reports remain reproducible against their original snapshots/date/rule. Missing fields remain UNKNOWN. Deterministic event/notification IDs, owner locks and unique keys prevent duplicates. Preferences control in-app delivery, general update messages and automatic reassessment independently. See reassessment.md and notifications.md.

## Docker and run commands

The six services are preserved: frontend, api, db, redis, worker, scheduler. Only localhost frontend/API ports are exposed. PostgreSQL, Redis and original PDFs retain persistent volumes. API/worker share the private key; frontend never receives it. Existing development hot reload is retained. Workers must be restarted after Python changes; they do not hot reload. Single logical Beat leadership remains database locked.

```bash
python3 scripts/init_env.py
docker compose up --build -d
docker compose exec api alembic upgrade head
docker compose exec api python -m app.seed
docker compose exec api python -m app.auth.provision --username reviewer
# Open http://localhost:3000/register for your citizen account.
docker compose exec api python -m tests.run
docker compose exec frontend npm test
docker compose exec frontend npm run typecheck
python3 scripts/verify_phase6.py
python3 scripts/verify_workers.py
docker compose ps
docker compose logs --tail 50 api worker scheduler
```

`init_env.py` preserves existing database credentials and encryption keys. Never replace the key after writing private data, delete volumes, or run `docker compose down -v`. Live verification uses a clearly labeled synthetic local citizen and fictional scholarship; credentials stay ignored in `.local/phase6-demo-credentials.json` (0600) and are never printed. Remove demo accounts through the authenticated account deletion flow when no longer needed.

## Files created and changed

Backend additions: models/citizen.py, schemas/citizen.py, auth/encryption.py, api/v1/citizen_auth.py, api/v1/citizen.py, services/citizen.py, services/reassessment.py, services/currency.py, migration 0009 and citizen/reassessment integration tests. Existing auth/security, admin_auth, router, eligibility schemas/service, scheme schemas/service, monitoring publication hook, worker dispatcher, config/main/body limits, model exports, lockfiles and migration assertions are extended. The rule engine operators and official policy data remain unchanged.

Frontend additions: lib/citizen.ts, lib/citizen-server.ts; fixed account API proxy; citizen auth/session/dashboard/profile/assessment/notification/settings components; protected dashboard route tree and login/register; admin audit and scheme/history pages; citizen component/server-auth tests and a test-only server module alias. Existing header/admin navigation, scheme detail/card, questionnaire field export, report warning, types, security headers and test config are extended. `.env.example`, Compose, init_env.py, README and the Phase 6 verification script/guides document the setup.

## Limitations and verification

No real Gemini key, external email/recovery mechanism, identity verification, MFA or production deployment is configured. The historical official PDF remains pending real human review; no government approval is simulated in the live database. Full policy publication/reassessment is tested using deterministic synthetic documents and mock AI in a disposable PostgreSQL database. The current dataset is static discovery metadata; only approved supported policies can be evaluated. Operational retention, encrypted backups and key rotation require an explicit operator policy; high-volume reassessment sharding/load testing is future work. Automatic reassessment uses stored profile data, not transient questionnaire edits unless the citizen separately updates the profile.

Executed final test/build/container/persistence results are recorded below after the verification commands finish. Do not treat this document's feature description as evidence that unexecuted tests passed.

Suggested commit: `feat: add private citizen accounts, reproducible assessments and verified policy reassessment notifications`.

## Executed completion results (13 November 2026)

- **414 backend tests passed in 76.00 seconds**, using disposable PostgreSQL databases, full migrations and regression fixtures. Ruff, strict mypy (98 application modules), dependency checks and Alembic drift checks passed. Tests cover authentication, role restrictions, CSRF/origin, expiration/revocation, rate limiting, encrypted/typed profiles, private ownership, idempotent saves, immutable report history, exact-version replay, metadata-only UNKNOWN, account deletion, source currency, geographic discovery and the full simulated publication/reassessment path. The latest focused private suite also passed 23 tests before the final additional geographic-discovery test was included in the complete suite.
- **60 frontend tests passed across ten files**; TypeScript and Prettier checks passed. Registration and profile validation, metadata-only guards, cookie transport without browser storage, protected server routes, notification controls/preferences and all earlier explorer/questionnaire/report/admin workflow tests were executed.
- Both backend/frontend Docker images built. Isolated Next.js production compilation, type checking and prerendering passed with `NODE_ENV=production`. The first isolated build exposed a build-directory dependency-boundary issue and the next inherited the development environment; both verification commands were corrected without changing application architecture.
- A live same-origin synthetic citizen flow passed: login/registration → encrypted stored profile → fictional PASS report → private history → original-version reproduction → logout/revoked access. Its credentials remain ignored/private, never printed. A separate real Beat → Redis → Celery delivery probe succeeded in one attempt; duplicate delivery did not execute twice.
- Existing live Phase 2 smoke checks passed for PASS/FAIL/UNKNOWN, source hashes, stateless behavior and frontend connectivity. Full catalog verification passed: **282 curated government schemes, 283 total records, 23 categories and 48 six-card explorer pages**, including source relationships, search/pagination, category/state filters and metadata-only links beyond page one. The official historical four-page Saksham PDF passed its original checksum/evidence/pending-workflow verification. No real government policy was approved.
- All rows in **41 public/checkpoint tables**, together with original PDF byte checksums, survived recreation of all six containers. PostgreSQL volumes were preserved. The first live synthetic profile/report was included in this check; a second synthetic report was subsequently saved to verify the restored script and post-recreation flow.
- Browser inspection confirmed unauthenticated `/dashboard` redirects to `/login`, with readable desktop/mobile form controls and existing navigation/theme. It identified missing shared form classes, which were fixed. Authenticated interactions were verified through component tests and the real cookie-proxy HTTP flow; no claim of a manually completed browser login or government approval is made.

Bugs fixed during Phase 6 verification: duplicate private cache-control headers; a missing currency-helper argument; missing shared citizen input styling; historical warning handling; numeric representation differences incorrectly implying policy differences; and test-only server module resolution/mock-call selection. Input and credential fields are cleared after sensitive operations; no stored input snapshot is exposed by the API.

Acceptance criteria: citizen auth/profiles/private discovery, supported assessments and saved history, reviewed-change reassessment, preference-aware deduplicated notifications, owner isolation, protected administration and functional Docker/test paths all pass with deterministic synthetic policy/AI fixtures. Real Gemini calls, real new government policy publication, external email/password recovery, high-volume worker load and production security deployment were not verified/configured. These limitations do not authorize inventing policy values or bypassing review. Phase 6 is the stopping point; no Phase 7 work was started.

See [combined created/modified file inventory](phase56-file-inventory.md) for every actual changed repository path, including shared Phase 5/6 files.

Final live counts: 283 schemes (282 government, one fictional), two preserved document versions, zero approved government policies, one synthetic citizen/profile and two encrypted fictional assessment reports. Zero live monitors and notifications are intentional: no source is automatically enrolled and no unreviewed government update is announced. All six rebuilt services are healthy (frontend/api/db/redis/worker/scheduler). API/worker shared-key compatibility was verified by decrypting the synthetic API-written profile inside the worker without printing its contents.

The dashboard discovery panel uses only verified geographic metadata, with an explicit non-eligibility notice. Current-source warnings are separate from immutable historical reports. No personal inputs are used for public catalog filtering or AI calls.
