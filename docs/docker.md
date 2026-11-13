# Docker development and production

Development: `python3 scripts/init_env.py` then `docker compose up --build -d`. The existing six services, hot reload and persistent volumes remain. Local UI is http://localhost:3000, API http://localhost:8000 and docs /docs. No PostgreSQL/Redis host port is exposed. Never use `down -v` or reset existing data. Stop integration-test runners before recreating application containers.

Production uses **only** `docker-compose.production.yml`, not an overlay on the development file. API/worker/scheduler share `backend/Dockerfile` target production; this excludes test/development packages and runs UID 10001 without a migration entrypoint. Frontend is a multi-stage Next.js standalone build running as node, with no development dependencies or source mounts in its runtime. Build-time Tailwind/type dependencies are included only in the builder. Both images have health checks. Application services have read-only roots, bounded writable /tmp, dropped capabilities, no-new-privileges, restart policies, rotating Docker logs and explicit memory limits. Worker concurrency is two with 9-minute graceful shutdown; scheduler leadership is still protected by PostgreSQL.

Production database/Redis networks are internal. Frontend/API ports bind only to host loopback for a trusted HTTPS reverse proxy. Container-to-container traffic uses fixed service names; no browser-only localhost API URL is embedded. Public and private browser requests use fixed-route same-origin Next proxies. Private proxies forward only the session cookie and CSRF/Origin headers; public proxies never forward cookies.

Copy `.env.production.example` to private `.env.production`, mode 0600, and supply independent random owner/runtime database passwords, a stable Fernet key and the exact HTTPS frontend origin. Prefer IAM workload credentials for S3. Production startup rejects missing encryption, automatic demo seeding, wildcard hosts, HTTP origins, local fixture embeddings and missing S3 configuration. Persistent local storage requires an explicit operator opt-in and a backed-up shared document volume. S3 configuration never silently migrates local originals; copy and verify them first.

```bash
docker compose --env-file .env.production -f docker-compose.production.yml build
docker compose --env-file .env.production -f docker-compose.production.yml up -d --wait db redis
python3 scripts/production.py migrate --env-file .env.production
python3 scripts/production.py grant-runtime --env-file .env.production
docker compose --env-file .env.production -f docker-compose.production.yml up -d --wait
```

Existing runtime-role passwords are preserved by the grant command. After every schema migration rerun grants for any newly introduced tables/sequences. Never give migration-owner credentials to long-lived app/worker/scheduler services. Named production volumes are separate from development by default; configure their names deliberately when continuing an existing deployment. Changing POSTGRES_PASSWORD does not rotate a database role password in an existing volume.

Resource limits are starting safeguards, not capacity estimates. Two PDF parser children can each reach a 768 MiB virtual-memory bound, so worker memory must account for parser and SDK overhead. Read-only filesystems still allow private persistent document volumes. Database backups and encryption keys must be maintained separately from container images. See deployment.md and security.md.
