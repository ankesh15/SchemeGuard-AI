# Railway API and Vercel frontend deployment

This guide deploys the Next.js frontend from `frontend/` to Vercel and the FastAPI services to Railway. It keeps database credentials server-side. Deploy only reviewed commits from the repository's production branch.

## Railway services

The backend uses PostgreSQL with the `vector` extension and Redis for Celery. Document originals use filesystem storage. Keep the original PostgreSQL service intact when migrating an existing environment. The application database must have pgvector installed because Alembic migration `0005_workflow_rag` creates a vector column.

**Current Railway blocker:** the API and worker are separate services, but they both read and write document originals. Railway volumes attach to one service, so a filesystem volume on the API is not visible to the worker. With S3 removed from the deployment configuration, document upload and background processing are not production-ready on Railway until the services share storage through a single service or the application moves originals to shared storage such as PostgreSQL.

In the Railway production environment, configure:

| Service | Source / command | Public access |
| --- | --- | --- |
| API | GitHub repository `ankesh15/SchemeGuard-AI`, Dockerfile `backend/Dockerfile`, start command `python -m app.ops.railway_start`, health path `/ready` | Generate an HTTPS Railway domain on container port 8000 |
| Worker | Same repository and Dockerfile; `celery -A app.workers.celery_app:celery_app worker --loglevel=INFO --concurrency=2 --queues=monitoring,documents --hostname=worker@%h` | Private only |
| Scheduler | Same repository and Dockerfile; `python -m app.workers.scheduler` | Private only; run one replica |
| PostgreSQL | PostgreSQL image with pgvector installed; do not replace a database volume in place | Private only |
| Redis | Railway Redis template | Private only |

The provided `railway_start` command runs Alembic upgrades, the idempotent insert-only scheme seed, and restricted runtime-role grants before it starts Uvicorn. Migration-owner credentials are removed from the long-running API process environment. Workers and the scheduler receive only the restricted database URL. Do not run multiple API start commands with conflicting migration-owner configuration.

### API environment variables

Set the following on the API service. Use Railway variable references for database and Redis values; never paste resolved secrets into source files.

| Variable | Value |
| --- | --- |
| `APP_ENV` | `production` |
| `SEED_DEMO_DATA` | `false` |
| `DATABASE_URL` | Runtime-role PostgreSQL URL (`postgresql://...` is accepted and normalized to asyncpg) |
| `MIGRATION_DATABASE_URL` | Private PostgreSQL owner URL, e.g. `${{pgvector.DATABASE_URL_PRIVATE}}` |
| `RUNTIME_DATABASE_URL` | Private connection URL for restricted `schemeguard_app` role |
| `RUNTIME_DATABASE_USER` | `schemeguard_app` |
| `RUNTIME_DATABASE_PASSWORD` | Random, URL-safe secret of at least 24 characters |
| `PROFILE_ENCRYPTION_KEY` | Stable Fernet key; keep a separate encrypted backup and never rotate without re-encrypting profiles |
| `REDIS_URL` | Private Redis URL reference |
| `DOCUMENT_STORAGE_BACKEND` | `filesystem` |
| `ALLOW_LOCAL_DOCUMENT_STORAGE` | `true` only when a persistent volume is mounted |
| `DOCUMENT_STORAGE_ROOT` | `/var/lib/schemeguard/documents` |
| `PDF_MAX_BYTES` | `4194304` (4 MiB, to fit the Vercel proxy request limit) |
| `ALLOWED_HOSTS` | JSON list containing the API hostname, `healthcheck.railway.app`, `localhost`, and `127.0.0.1` |
| `ADMIN_ALLOWED_ORIGINS` | JSON list containing the exact production Vercel HTTPS origin |
| `CORS_ORIGINS` | `[]`; the browser uses same-origin Next.js proxy routes |

The `GEMINI_API_KEY` is optional for startup. Without it, document intelligence and embedding-backed RAG actions that require Gemini are unavailable; the deterministic eligibility engine remains authoritative. Add the key as a Railway secret when ready. Never add it to Vercel.

### Worker and scheduler environment

Both services need `APP_ENV=production`, the same stable `PROFILE_ENCRYPTION_KEY`, `DATABASE_URL` set to the API's runtime-role URL, and `REDIS_URL`. Do not copy `MIGRATION_DATABASE_URL`, `RUNTIME_DATABASE_PASSWORD`, or `RUNTIME_DATABASE_USER` to worker or scheduler. Set the worker and scheduler to one replica each; only one scheduler process should own the monitoring schedule. The filesystem limitation above must be resolved before enabling jobs that read document originals.

## Vercel project

Create a Vercel Git project connected to `ankesh15/SchemeGuard-AI` and set **Root Directory** to `frontend`. Use Next.js auto-detection, `npm ci`, and `npm run build`. `next.config.ts` selects the standalone output only outside Vercel so both Vercel and the existing Docker deployment retain their supported packaging.

Set these server-side Vercel environment variables for Production:

| Variable | Value |
| --- | --- |
| `INTERNAL_API_URL` | The API's HTTPS Railway service domain, with no trailing slash |
| `ADMIN_ALLOWED_ORIGINS` | JSON array with the exact Vercel production origin, e.g. `["https://schemeguard-ai.vercel.app"]` |

Do not prefix `INTERNAL_API_URL` with `NEXT_PUBLIC_`. Do not configure database URLs, Redis, Gemini keys, storage credentials, or profile encryption keys in Vercel. Redeploy after changing environment variables. Preview deployments should use their own exact origin if administrator mutations are enabled there; otherwise keep administrative writes on the production origin only.

## Deployment order

1. Provision a pgvector-capable PostgreSQL service and Redis in Railway. Preserve any existing database service and volume.
2. Configure the API variables, service Dockerfile, start command, restart policy, and `/ready` health path. Generate the API HTTPS domain and set its hostname plus `healthcheck.railway.app` in `ALLOWED_HOSTS`. The backend image runs as UID 10001; check mounted-volume permissions before enabling filesystem writes.
3. Configure the Vercel project with the `frontend` root directory and the API URL. Add its exact production origin to the API's `ADMIN_ALLOWED_ORIGINS`.
4. Deploy the API. Wait for `/ready` to return HTTP 200, then confirm `alembic upgrade head` completed and seed output reports inserted/preserved counts. The startup seed is repeatable and does not overwrite existing scheme rows.
5. Configure and deploy the worker and one scheduler. Verify a Celery task can reach Redis and PostgreSQL before enabling monitored sources.
6. Verify `https://<api-domain>/health`, `https://<api-domain>/ready`, `https://<api-domain>/docs`, and the Vercel scheme explorer. Create or provision an administrator through the existing secure operator path; no default admin credential is included.
7. Back up the database, document volume, and profile encryption key before public use. Keep the prior database and its volume until record counts and required data have been confirmed on the pgvector database.

## Platform limits and recovery

The admin upload proxy accepts PDFs up to 4 MiB because Vercel Functions cap request bodies at 4.5 MB. Larger uploads require a future direct-to-object-storage upload flow. The admin proxy sets a 300-second Vercel function maximum and a 280-second upstream timeout; plan limits can be lower. Long extraction should be submitted as a background workflow and polled by document status.

The API, worker, and scheduler are separate Railway services, but they share the same source and production image. PostgreSQL and Redis are not public HTTP services. Document storage needs to be made shared before enabling document workflows. Railway deployments do not migrate or delete the original database volume. Keep backups and the Fernet key independently before switching traffic or database URLs.

The initial configuration does not provision Gemini credentials or an administrator account. It does not claim a live deployment until Railway and Vercel show successful deployment states and the API readiness endpoint has been checked.
