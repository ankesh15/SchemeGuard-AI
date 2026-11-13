# Test and verification record — Phase 7

Baseline before changes: 414 backend tests and 60 frontend tests passed; six development services were healthy. A private pre-Phase-7 backup was taken. No application database/volume was reset. Tests use disposable real PostgreSQL databases and synthetic profiles/policies; they do not approve real government rules.

Executed Phase 7 checks:

| Check | Actual result |
|---|---|
| Backend regression | 421 passed in 59.20 seconds, including migrations, engine, source/PDF/AI guards, graph/human review/RAG, monitoring/history, authentication/isolation, reassessment/notifications and new production-security/evaluation/demo tests |
| Ruff and strict mypy | Passed; no known application type/lint failure |
| Frontend unit/component tests | 63 passed across 11 files; TypeScript and Prettier lint passed |
| Chromium E2E | 2 passed: register/profile/save UNKNOWN fictional assessment/replay/notifications/logout/private-route protection/own synthetic account deletion; mobile explorer/metadata-only boundary |
| Production Docker | Backend production and multi-stage standalone frontend built; six-service production profile reached healthy state after correcting quoted tmpfs/worker-queue arguments and builder dev dependencies |
| HTTPS production smoke | Local trusted-certificate harness: all rendered scripts match CSP nonce; HSTS, Secure/HttpOnly session, citizen profile, admin denial and own-account deletion passed |
| Production database role | NOSUPERUSER/NOCREATEDB/NOCREATEROLE verified; schema DDL denied |
| Production background delivery | Real PostgreSQL outbox → singleton Beat → Redis → Celery probe succeeded once; duplicate delivery skipped |
| Dependency advisories | pip-audit: 85 pinned runtime packages, 0 known advisories; npm audit: 0 reported vulnerabilities; no ignore list |
| Frontend secret boundary | 35 production browser JS artifacts scanned; no backend-only secret-variable references found |
| Recovery | Restored 41 public/checkpoint tables and 757 snapshot rows into a new recovery DB; row hashes matched, original PDFs/checksums and private profile decryption checked; only the recovery DB was dropped |
| AI evaluation | See evaluation.json: gold-reference guard/engine/diff checks executed; real-model extraction accuracy and independent human-review agreement remain unmeasured |

The A/B/C demonstration reuses the actual HTTP/services/graph/review/publication/RAG/reassessment implementation under deterministic PDF/LLM fixtures. It preserves both documents/rule versions and checks original report replay and notification deduplication. Its exact-revision “human” action is simulated in a disposable database. It does not claim real government approval or live Gemini access. Browser tests use the existing frontend framework plus Playwright in an isolated browser process, with authored synthetic accounts and recording disabled.

Reproduce from the repository:

```bash
docker compose exec api python -m tests.run
docker compose exec api ruff check app tests alembic
docker compose exec api mypy --cache-dir /tmp/mypy app
docker compose exec frontend npm run typecheck
docker compose exec frontend npm test
docker compose exec frontend npm run lint
docker compose exec --user 0 frontend npx playwright install --with-deps chromium
docker compose exec --user 0 frontend npm run e2e
docker compose exec api python -m tests.run tests/test_final_demonstration.py -s
docker compose exec api python -m app.evaluate
python3 scripts/benchmark.py
python3 scripts/verify_workers.py
python3 scripts/verify_recovery.py
```

Do not recreate containers while test runners are active. Tests may create labeled synthetic accounts in the local development database; current E2E removes only its own newly created account through the normal UI. Database-heavy tests create/drop only their generated `_test` databases. Recovery retains private backups under ignored .local/backups. Original user/database records remain intact.

## Measured performance and reliability

`verification/performance.json` records one warmup followed by 20 sequential local HTTP samples per endpoint. Median/p95 milliseconds: health 2.009/2.165; DB readiness 4.742/5.267; scholarship search 16.924/18.789; deterministic assessment 18.025/19.777. PostgreSQL EXPLAIN ANALYZE/BUFFERS and reviewed index names are included. The small catalog's sequential search scan is reasonable at this measured scale; no speculative index/migration was added.

`verification/demonstration.json` records one isolated run: PDF parse 426.927 ms; mock extraction 0.058 ms (not model/network latency); reviewed publication 256.978 ms; RAG 37.561 ms; evaluation/save 39.084 ms; combined monitor/parse/graph/compare/review 1255.566 ms; reassessment 39.895 ms. These are smoke measurements, not capacity, SLA, p95 workflow or real Gemini/S3 benchmarks. Timeouts, finite retries, crash leases and duplicate delivery have deterministic integration coverage; a real production-profile delivery probe verifies wiring separately.

## CI status and limits

.github/workflows/ci.yml defines least-privilege read-only-token checks for Python lint/types/PostgreSQL tests/migrations/security/evaluation; frontend lint/types/tests/build/npm audit; production Docker builds; Chromium E2E; worker/recovery checks. Dependency caches are used, and external Actions are pinned to verified commit SHAs. No production secrets or auto-deployment job exists. These steps were exercised locally as described; the workflow was not pushed or executed on GitHub during this phase.

Real Gemini/S3/managed database/Redis connections, independent human annotation agreement, external cloud deployment, OS-image vulnerability scanning, formal penetration testing, full automated WCAG/axe certification, high-concurrency load and regional disaster recovery are unverified. Review those before a real-world release. Primary implementation guidance: [Next.js standalone](https://github.com/vercel/next.js/tree/canary/examples/with-docker), [Next.js CSP](https://nextjs.org/docs/app/guides/content-security-policy), [Playwright CI](https://playwright.dev/docs/ci), [S3 conditional object writes](https://docs.aws.amazon.com/boto3/latest/reference/services/s3/client/put_object.html).
