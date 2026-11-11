# SchemeGuard AI — Phase 1

SchemeGuard AI is an Indian government scheme discovery and policy history project. Phase 1 delivers a Dockerized, typed FastAPI backend, PostgreSQL, migrations, five source-verified scholarship records, and public read-only discovery APIs. It does not determine eligibility.

The existing workspace is the project root; no extra nested repository is needed.

## Run

Prerequisites: Docker Engine with Docker Compose v2 or newer, and Python 3 for the optional environment helper. Run from this directory:

```bash
python3 scripts/init_env.py
docker compose up --build -d
docker compose exec api alembic upgrade head
docker compose exec api python -m app.seed
docker compose ps
curl --fail http://localhost:8000/health
curl --fail http://localhost:8000/ready
curl --fail 'http://localhost:8000/api/v1/schemes?page=1&page_size=2'
```

The helper creates `.env` using a generated password and preserves an existing `.env`. Alternatively, copy `.env.example` to `.env` and set `POSTGRES_PASSWORD`. Secrets must not be committed. Changing the password in `.env` does not change credentials in an existing PostgreSQL volume; rotate the database password deliberately.

The API automatically applies migrations before starting the single development server. The explicit Alembic command above is safe to repeat. Seeding is explicit and insert-only: a repeat preserves existing records, descriptions, timestamps, and source records. It does not refresh verification dates or fetch external pages.

Open [Swagger UI](http://localhost:8000/docs) or [ReDoc](http://localhost:8000/redoc). `API_PORT` defaults to `8000` and is bound to the local machine only. The development API uses hot reload through the backend bind mount. Only `api` and `db` services run. Both share an internal database network; an API-only ingress network supports the published loopback port. PostgreSQL has no host port.

## APIs

| Method | Path | Result |
| --- | --- | --- |
| GET | `/health` | Process health; does not require a database |
| GET | `/ready` | Live `SELECT 1`; 503 if the database is unavailable or times out |
| GET | `/api/v1/schemes` | Paginated discovery with optional filters |
| GET | `/api/v1/schemes/{scheme_id}` | UUID detail with field-level evidence references; 404 when absent |

Listing query parameters:

| Parameter | Default | Validation and meaning |
| --- | --- | --- |
| `page` | `1` | Integer from 1 to 100000 |
| `page_size` | `20` | Integer from 1 to 100 |
| `search` | omitted | 1–200 trimmed characters; case-insensitive name/description substring; `%` and `_` are literal |
| `category` | omitted | Lowercase category token, max 60 characters; `scholarship` is the seeded category |
| `state` | omitted | Indian state/UT name, case-insensitive; e.g. `Assam` |

Filters combine with AND. Ordering is by name then UUID. The response contains `items`, `total`, `page`, `page_size`, and `pages`. Valid filters with no matches return an empty page with 200. Malformed IDs, invalid parameters, and unexpected query keys return 422. Error responses contain an error code, message, and request ID; validation errors also include safe field locations. Raw inputs and database errors are not echoed. Responses carry `X-Request-ID`.

```bash
curl --fail --get http://localhost:8000/api/v1/schemes \
  --data-urlencode 'state=Assam' --data-urlencode 'category=scholarship'
curl --fail --get http://localhost:8000/api/v1/schemes \
  --data-urlencode 'search=Pragati'
# Copy an id from the listing:
curl --fail http://localhost:8000/api/v1/schemes/REPLACE_WITH_UUID
```

## Source verification and unknowns

The curated [seed manifest](data/scholarships.json) contains five distinct scholarship variants: AICTE Pragati (technical degree), AICTE Saksham (technical degree), UGC Ishan Uday, PM YASASVI Top Class School Education, and PM-USP CSSS. Eleven scheme/source relationships were checked on **11 November 2026**. Primary identity evidence is the [National Scholarship Portal directory](https://scholarships.gov.in/All-Scholarships). Supplementary evidence comes from [UGC](https://www.ugc.gov.in/Scholarships/stu_Scholarship5), [West Bengal's Higher Education department](https://banglaruchchashiksha.wb.gov.in/scholarship_schemes), and a [Ministry of Education PIB release](https://www.pib.gov.in/PressReleasePage.aspx?PRID=2294003&lang=1&reg=6).

`listed` means the scheme was found in the official directory on the verification date. It does not mean applications are open, the scheme will remain unchanged, or a user is eligible. Category is an internal discovery taxonomy. The dataset contains no eligibility thresholds, financial amounts, deadlines, or executable rules. Differing financial benefit descriptions on official Ishan Uday pages are deliberately omitted.

Only Ishan Uday's eight North Eastern states are recorded as verified geography. Other records use `applicability: "unknown"` and `applicable_states: null`; national coverage is not inferred from the administering body. State filters exclude unknown coverage. An empty result therefore does not prove that no scheme is applicable to a person. Future verified national coverage would match every valid state. These are discovery filters, not eligibility decisions.

Each detail response includes evidence URLs, publishers, dates, supported fields, and review notes. No document bytes were downloaded or ingested; `document_versions` is initially empty. Its table prepares for immutable, hash-addressed policy history in a later phase.

## Verify

```bash
docker compose exec -T api python -m tests.run
docker compose exec -T api ruff check --no-cache app tests alembic
docker compose exec -T api ruff format --check --no-cache app tests alembic
docker compose exec -T api mypy --cache-dir=/tmp/schemeguard-mypy app
docker compose exec -T api alembic check
python3 scripts/verify_persistence.py
```

`tests.run` creates a randomly named disposable PostgreSQL database, applies real Alembic migrations, runs pytest, and drops only that generated database. No SQLite or mock-only database substitution is used. Direct pytest requires an explicit `TEST_DATABASE_URL` ending in `_test` and fails closed if it is missing. The migration round-trip test uses a second disposable database. The local database role needs permission to create test databases; this is provided by the development PostgreSQL image. Runtime and test database roles should be separated in a future production configuration.

The persistence check briefly recreates this project's API and database containers and compares all metadata rows, including IDs and timestamps. It preserves the named volume. `docker compose down` also preserves the volume. **`docker compose down -v` deletes the database data** and is not needed for normal development.

## Layout

```text
backend/
  app/{api/v1,core,models,schemas,repositories,services}/
  app/{main,bootstrap,seed}.py
  alembic/versions/
  tests/
  Dockerfile
  pyproject.toml
  requirements.lock
  requirements-dev.lock
data/scholarships.json
docs/{architecture,database,phase1-report}.md
scripts/{init_env.py,test.sh,verify_persistence.py}
docker-compose.yml
.env.example
```

Dependencies and transitive hashes are locked for Python 3.12. Docker installs them with `--require-hashes`. To intentionally refresh locks with uv, run `uv pip compile --generate-hashes --output-file requirements.lock pyproject.toml` and the equivalent command with `--extra dev --output-file requirements-dev.lock` inside `backend/` using Python 3.12. Rebuild and rerun all checks afterwards.

For details, see [architecture](docs/architecture.md), [database design](docs/database.md), and the [Phase 1 implementation report](docs/phase1-report.md). Phase 1 has no frontend, LLM integration, rule engine, background worker, notification service, or public administrative writes. Production deployment configuration is deferred to the final phase.
