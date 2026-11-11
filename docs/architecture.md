# Phase 1 architecture

The backend is a modular monolith. A single development API process serves public discovery endpoints; PostgreSQL is the only stateful service. Later background workers can reuse application services, repositories, and domain contracts without coupling jobs to HTTP handlers. No worker containers are introduced in Phase 1.

## Request flow

`HTTP → versioned router → service → repository → async SQLAlchemy session → PostgreSQL`

`app.main.create_app` configures the application, exception handlers, logging, and CORS. The lifespan owns a bounded, pre-ping database connection pool and disposes it on shutdown. Settings use pydantic-settings; credentials are represented by `SecretStr` and SQLAlchemy URL objects so reserved password characters are encoded correctly. Each request receives a separate async session through dependency injection; public APIs do not commit writes.

Routers validate IDs and query objects. Services enforce not-found behavior and build typed response models. Repositories implement parameterized queries, literal substring search, verified geography filtering, eager source loading, deterministic ordering, and bounded pagination. The model layer uses SQLAlchemy 2.x typed mappings. Alembic owns schema evolution; application code never calls `create_all`.

## Startup and operations

Compose waits for PostgreSQL's health check. The non-root API entrypoint runs `alembic upgrade head`, then executes the reload server. Migration failure prevents startup. This is suitable for one development API instance; a future scaled deployment should use an explicit migration release step with appropriate locking and database roles.

`/health` reports whether the HTTP process is running. `/ready` issues a live `SELECT 1` under a bounded timeout and reports 503 on connectivity errors. It is also the API container's health check. Readiness does not assert that seed data exists. Both services share an internal Docker network; database ports are not published. The API additionally joins an ingress network so Docker can publish its host loopback port. No requests to official government sites occur at application startup, during seeding, or while serving APIs.

The PostgreSQL named volume survives service recreation. Backend files are bind-mounted for hot reload. The reviewed seed manifest is mounted read-only. The Docker image packages the same files and uses hash-locked dependencies; the development target adds test and analysis tooling.

## Evidence boundaries

The seed is curated metadata verified from official websites on a fixed date. Each factual field is mapped to one or more source records through `supported_fields`. Seed validation checks official HTTPS domains, primary-source uniqueness, supported geography, and evidence coverage. This checks the manifest's structure; it does not establish authenticity of arbitrary future documents.

Unknown information remains null or explicitly `unknown`. A directory listing does not establish application availability or user eligibility. No thresholds or rule values are stored. Ishan Uday is the only seed with verified state coverage. No eligibility decision is exposed.

`document_versions` stores identity, source, version number, content hash, storage locator, retrieval date, optional publication date, and same-source supersession. Database triggers reject updates, deletion, and truncation. No document snapshots are fabricated from source URLs. Future document ingestion must treat remote content as untrusted data and must add content size limits, safe fetching, file validation, and review boundaries. Any future AI-extracted rule must receive human approval before publication; an LLM must never make the final eligibility decision. No rule engine or review workflow is implemented here.

## Security and limitations

The four public endpoints require no authentication because they expose public metadata only. There are no HTTP mutation or administrative endpoints; the explicit seed CLI requires database access. Future administrative writes must add authentication and authorization first.

Logs are JSON with timestamps, event names, request IDs, matched route templates, duration, and status. They omit request bodies, raw paths, query strings, authentication headers, SQL parameters, and exception messages. Database failures return generic 503 responses; unexpected failures return generic 500 responses. Validation errors omit raw inputs. Explicit CORS origins allow GET only, without credentials. CORS is a browser policy, not authorization.

This is a development configuration. Database owner credentials, a single API process, offset pagination, and linear substring search are acceptable for the Phase 1 dataset. Production role separation, TLS, backup/restore exercises, rate limits, image digest pinning, dependency vulnerability monitoring, secret management, and deployment configuration belong to later work. No internet-facing production deployment is performed in this phase.
