> Latest user-flow update (2026-11-14): the primary journey is profile-first recommendations, with manual browsing retained at `/schemes/all`. See [implementation, modified files and final verification](profile-first-recommendations.md). Earlier phase measurements below remain historical.

# SchemeGuard AI — final implementation and verification report

This is the Phase 7 verification record. Subsequent scheme-based demonstration assessment work, verified on 14 November 2026, is documented in [the assessment implementation report](demonstration-assessments.md), including current coverage and regression results. Historical Phase 7 measurements below are retained as originally executed.

## Problem and solution

Government scheme information is distributed across portals, changing documents and partially overlapping guidelines. Discovery metadata does not prove personal eligibility, an LLM can misread a clause, and silent rule replacement makes past decisions impossible to reproduce. SchemeGuard separates verified discovery, source-preserved document intelligence, human publication and deterministic assessment. Unknown information remains unknown; evidence and version history accompany every supported decision.

The modular monolith uses Next.js/TypeScript/Tailwind, FastAPI/Pydantic, SQLAlchemy/PostgreSQL/Alembic/pgvector, PyMuPDF, Google GenAI structured extraction, checkpointed LangGraph, and Redis/Celery/Beat. Workers run independently. There is one canonical scheme/document/rule representation and one deterministic engine. Phase 7 preserves the prior frontend, records, migrations, engine semantics, policy history and APIs rather than rebuilding them.

## Actual working dataset and supported policies

Measured from the current application database (verification/project-facts.json):

| Item | Actual count/status |
|---|---|
| Scheme records | 283 |
| Curated government discovery records | 282; static source-traceable metadata, not 282 executable policies |
| Approved rule sets | 1, clearly labeled fictional development scholarship |
| Approved government eligibility rule sets | 0 |
| Document versions | 2: authored fictional policy and a preserved historical official PDF |
| Processed PDF originals | 1; 4 extracted pages and 26 stored chunks |
| Monitored live sources | 0; enrollment is explicit, not automatic |
| Public/checkpoint database tables | 41 including migration bookkeeping; exact names in project-facts.json |
| FastAPI operations | 70, inventoried in api.md |
| Docker services | frontend, api, db, redis, worker, scheduler |
| Current migration | 0009_citizen_system; Phase 7 required no new schema migration |

The official historical Saksham PDF remains pending actual human review and current-policy reconciliation. Real thresholds or deadlines were not invented to expand executable coverage. Synthetic test documents/policies and simulated approvals exist in disposable test databases, not as approved government policy in the working database. Existing original bytes/checksums were rechecked in recovery; the optional credential-based pending-workflow smoke could not be rerun because automatic approval review timed out. No safety rejection reason was supplied, and no bypass/publication was attempted.

## Completed functionality

- Search/category/state discovery, pagination, source links, detail pages and clear discovery-only/approved/outdated labels.
- Safe typed comparison/date/nested AND/OR/exclusion/conditional rules with PASS/FAIL/UNKNOWN, decision traces, missing fields, evidence, effective-date/version selection and ambiguity rejection. Saved historical reports pin original inputs/date/version; later rules never overwrite them.
- Administrator sessions/authorization, exact official-source approval, bounded secure PDF download/upload, immutable originals/document versions, page/block/table-aware extraction/chunking, evidence validation, structured candidate extraction and pending review.
- Persisted LangGraph stages/checkpoints, revision/digest-based human review, clarification/rejection/publication, immutable rule history and approved-document-scoped vector/lexical retrieval with located citations. LLMs/RAG never choose eligibility outcomes.
- Opt-in source schedules, durable PostgreSQL outbox/jobs, private Redis delivery, bounded workers, singleton scheduler, checksums/HTTP validators, preserved changed originals, normalized policy differences, material-change review, currency warnings and approved-only updates.
- Citizen registration/login/logout/password changes, optional encrypted profiles, private saved assessments/history/reproduction, preference/consent-aware reassessment and deduplicated owner notifications, account settings and own-data deletion with policy/audit history preserved.
- Phase 7 hardening: password-change/login race fix; global body and pagination bounds; explicit hosts; safe correlated/worker logs; consistent managed TLS DSNs; fixed same-origin public proxy; production nonce CSP/security headers; non-root production images/read-only roots/resource/log safeguards; separate migration/runtime DB roles; configured S3 adapter and dry-run/copy verification; CI checks/caches/pinned actions without auto-deploy; synthetic evaluation/demo/performance tools; recovery and local production verification.

## Executed verification

Baseline: 414 backend and 60 frontend tests passed before Phase 7 edits. Final backend run: **421 passed in 59.20 seconds**. Frontend: **63 passed**, TypeScript and Prettier lint passed. **Two Chromium E2E tests passed**, covering real registration/profile/fictional UNKNOWN save/replay/notifications/logout/private routes/own test-account deletion and mobile discovery. Ruff, strict mypy over 102 application modules, package checks and Alembic model drift checks passed.

The A/B/C isolated integration demonstration passed: preserved PDF → mock structured AI → LangGraph → simulated exact-revision human publication; private profile → discovery → approved deterministic evidence-backed saved result; changed PDF → monitoring/comparison → simulated reviewed replacement → new assessment → one notification. Both originals and policy versions remain, the original report reproduces, and retries do not duplicate a notification. Human review is simulated only for tests; model latency/accuracy is not inferred from mock timings.

A production backend and standalone frontend image were built and a separate local production profile reached six healthy services. HTTPS verification with an explicitly trusted short-lived localhost certificate checked CSP nonces on every rendered script, HSTS, Secure/HttpOnly cookies, citizen profiles, administrator denial and own test-account deletion. Runtime privileges were checked: no superuser/create-db/create-role, and schema DDL is denied. A real production-profile Beat/Redis/worker probe succeeded in one attempt; duplicate delivery did not execute again. The browser artifact scan found no backend secret references in 35 JS files. These are **local production-profile checks**, not a cloud deployment.

The final frontend rebuild encountered an npm registry ECONNRESET after the earlier successful production build. Dependency fetching now has bounded retries/timeouts; the final retry completed successfully with the current Dockerfile. The architecture/runtime source had already passed the local production smoke. Temporary approval-review timeouts affected optional rechecks, not the completed baseline/recovery tests.

Recovery restored 41 tables and 757 snapshot rows into a generated non-production DB, matched all row hashes, checked restored original PDF hashes and private decryption, and dropped only its generated recovery DB. The working database, volumes and encryption key were retained. pip-audit checked 85 pinned runtime packages with 0 known advisories; npm reported 0 vulnerabilities, with no advisory ignore list. This is not a penetration test or OS-image security certification.

## Actual evaluation and performance

The manually inspected fictional reference dataset has three source clauses, 11 boundary/missing profiles and six material/nonmaterial change pairs. Executed gold-reference checks: 3/3 evidence excerpts located; 11/11 deterministic expected outcomes; 0 false PASS across six non-PASS cases; 3/3 missing-input outcomes UNKNOWN; change comparison 3 true positives, 0 false positives and 0 false negatives (precision/recall 1.0 on this tiny set). This is **not real Gemini extraction accuracy**. Real extraction accuracy, model latency and independent human-review agreement are null/unmeasured without credentials/independent annotations. See verification/evaluation.json.

Twenty sequential local samples per endpoint (warmup excluded) measured median/p95 milliseconds: health 2.009/2.165, readiness 4.742/5.267, scholarship search 16.924/18.789, deterministic evaluation 18.025/19.777. The single-run synthetic PDF/graph/RAG/monitoring/reassessment timings and EXPLAIN ANALYZE/index review are in verification/demonstration.json and performance.json. No unsupported throughput/SLA or AI accuracy claim is made; no speculative indexing was added at this scale.

## Deployment status and remaining work

| Area | Status |
|---|---|
| Local development application | Implemented and regression-tested; six-service infrastructure preserved |
| Local production Docker profile | Final images built; all six healthy; final HTTPS and restricted-role checks passed. Isolated test services then stopped with volumes retained |
| GitHub CI | Authored with SHA-pinned actions, caching and checks; local equivalents executed, remote GitHub run not triggered |
| Live cloud deployment | Not performed; no cloud resources or DNS/certificates were created/modified |
| S3 production storage | Adapter/checksum/conditional-write fixtures and migration utility implemented; real IAM/bucket/network/restore unverified |
| Gemini processing | SDK/provider/retries/schema/grounding implemented and mocked; real key/model calls unavailable |
| Government eligibility coverage | Pending real human review; zero approved government policies |
| Independent AI evaluation | Reference guards/engine/diff evaluated; representative real-model accuracy and human agreement not measured |
| Recovery | Local PostgreSQL/filesystem drill passed; managed-service/regional disaster recovery unverified |
| Security capacity/assurance | Regression/dependency/role/CSP checks passed; MFA/recovery delivery, edge abuse capacity, retention/key rotation, WCAG certification, load/pentest/OS scans remain operator/future work |

These deployment and policy-review prerequisites must be completed before offering real-world government eligibility guidance. The project is a reproducible final-year demonstration and a production-minded implementation, not an official government approval service.

## Run and demonstrate

```bash
python3 scripts/init_env.py
docker compose up --build -d
docker compose exec api alembic upgrade head
docker compose exec api python -m app.seed
docker compose exec api python -m tests.run tests/test_final_demonstration.py -s
docker compose exec api python -m app.evaluate
docker compose exec frontend npm test
```

Open http://localhost:3000 (citizen /register, administrator /admin/login); provision your own administrator with `docker compose exec api python -m app.auth.provision --username reviewer`. See docker.md/deployment.md for owner-only production migrations, persistent storage, TLS and recovery commands. Private generated credentials/backups remain ignored under .local; no key is hardcoded or committed. Never delete/reset volumes or run down -v. Migration rollback uses forward repair or a verified compatible image/backup, never ad hoc history edits.

The required architecture/database/API/Docker/authentication/AI/RAG/eligibility/monitoring/security/testing/deployment documentation is present. The Phase 7 file inventory lists created/modified paths. No Phase 8 or automatic cloud deployment is started. Suggested commit: `feat: harden production deployment, CI, recovery and end-to-end verification`.

## Final acceptance record

Verified on 2026-11-13. Final Docker builds succeeded for both development images and production backend/standalone frontend images. After rebuilding, the final production HTTPS smoke, owner-only runtime-grant command, CI YAML/pinned-action structural validation and development migration/package/lint checks passed again. Both six-service stacks were healthy at the same time; see [runtime snapshot](verification/final-runtime.json). The temporary localhost TLS harness and isolated production test services were stopped after verification. All volumes were retained, and the six development services remain available at localhost:3000/8000.

| Acceptance criterion | Result and scope |
|---|---|
| 1. Frontend builds and starts | Passed locally in development and production images |
| 2. FastAPI starts/health checks | Passed, including database readiness |
| 3. Migrations | Passed at 0009; no model drift; no new Phase 7 migration |
| 4. Discovery | Passed against existing 283-record catalog and browser/API tests |
| 5. Approved-only eligibility | Passed; executable working policy is fictional, government rules remain unapproved |
| 6. Gemini processing or disclosed unavailable access | Provider/schema/error paths mocked and tested; live Gemini unavailable and clearly disclosed |
| 7. LangGraph human review | Passed with simulated exact-revision human decisions in disposable fixtures |
| 8. RAG source citations | Passed with approved-document fixtures and located page citations; real embedding access unavailable |
| 9. Verified-change monitoring | Detection, comparison and reviewed activation passed under synthetic external-service fixtures; live monitoring remains opt-in/off |
| 10. Historical versions | Passed preservation/replay tests and recovery checks |
| 11. Reproducible saved assessments | Passed original-version reproduction after reviewed replacement |
| 12. Authentication/authorization | Passed backend isolation/security and real browser/TLS checks |
| 13. Notifications | Passed impact, consent, ownership and deduplication tests |
| 14. Docker | Final six development and six isolated production services healthy; real worker delivery checked |
| 15. Security/regressions | Executed checks passed; external pentest, OS-image scan and capacity certification were not performed |
| 16. Complete synthetic demonstration | A/B/C integration passed; citizen/mobile browser smoke passed. Comprehensive browser automation of every administrator screen is not claimed |
| 17. Deployment documentation | Complete and local production/recovery procedure exercised; real cloud/S3/managed-service deployment remains unverified |

Phase 7 implementation and local verification are complete. This is not an unrestricted real-world production launch: live Gemini/S3, approved current government policies, real hosting/TLS, independent evaluation and operational security/capacity prerequisites remain as listed above. The [file inventory](phase7-file-inventory.md) lists every created/modified Phase 7 path; verification JSON files contain measured evidence without credentials or applicant payloads.
