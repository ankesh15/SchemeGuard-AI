# Curated dataset expansion implementation report

Completed on **12 November 2026 (Asia/Kolkata)**. The target of 250–300 authentic government scheme identities is met. This extends the existing Phase 2 project; Phase 3 has not been started.

## Actual data and preservation results

| Measure | Result |
| --- | ---: |
| Original government schemes preserved | 5 |
| Verified government schemes added | **277** |
| Government schemes in the curated catalog/database | **282** |
| Editorial categories / JSON manifests | **23** |
| New central directory records | 224 |
| New Goa state directory records | 53 |
| Total PostgreSQL scheme rows, including existing fictional demo | **283** |
| Total scheme-source rows, including fictional source | 289 |
| Document versions / rule sets / conditions / evidence | 1 / 1 / 6 / 6 — unchanged |
| Approved government rule sets added | **0** |

Verification of the new metadata means a manually reviewed, locatable identity in an official public directory. The [DBT Bharat central scheme directory](https://dbtbharat.gov.in/central-scheme/list) and [Government of Goa scheme catalog](https://www.goa.gov.in/government/schemes/) provide the primary provenance. No thresholds, benefits, deadlines, or application URLs were invented. `listed` means directory presence, not a current application window or operational approval. Some listed programmes are historical. The original five records and eleven official source relationships retain their original values and review dates.

A pre-import snapshot captured all rows in all six domain tables. After importing 277 records and after repeat imports, every original row compared identically by ID and full JSON representation, including UUIDs, timestamps, sources and approved synthetic policy history. Recreating all three containers subsequently preserved every current row exactly. No PostgreSQL reset or volume deletion occurred.

## Implemented changes and file inventory

| Area | Files / changes |
| --- | --- |
| Category datasets | `data/schemes/*.json`: 23 fully populated category manifests; `data/schemes/README.md` explains counts and provenance. Legacy `data/scholarships.json` is retained unchanged. |
| Validation | `backend/app/schemas/seed.py`: removes the five-record cap, validates optional legacy/required directory category consistency, retains all original provenance/applicability validation, rejects non-default source ports. |
| Import | `backend/app/seed.py`: deterministic multi-file loader, all-file validation before connection, cross-file duplicate slug/name checks, UUID5 insert-only import, batched existing-slug lookup, transaction/advisory lock, post-commit JSON/log statistics, `--path` and credential-free `--validate-only`. |
| Configuration | `backend/app/core/config.py`, `.env.example`, `docker-compose.yml`: default catalog directory; same read-only data mount, services, volumes and private database network. `seed_demo.py` still resolves its policy assets beside the configured catalog/legacy manifest. |
| Discovery API | `schemas/scheme.py`, `repositories/scheme.py`, `services/scheme.py`, `api/v1/schemes.py`: computed approved/effective rule availability, optional filter and database-backed category/state choices. Existing routes/search/pagination are preserved. |
| Application links | `services/eligibility.py`: retains NSP only for the original five reviewed NSP-backed records. Other metadata records have no unverified application link. The deterministic engine and rule tables are unchanged. |
| Frontend | `src/lib/catalog.ts`, `types.ts`, explorer/cards, home/scheme/detail/eligibility pages and minor questionnaire/layout wording. Categories/states are dynamic; metadata-only labels and unsupported notices are explicit; direct selection no longer stops at the first 100 schemes. Existing design and components remain. Stale request success/error callbacks are guarded during filter changes. |
| Tests | New `backend/tests/test_catalog.py`, new `frontend/tests/explorer.test.tsx`; `conftest.py` keeps the original five-record regression fixture independent of production data selection. |
| Verification helpers | New `scripts/verify_catalog.py`; `verify_phase2.py` uses the availability filter to find the demo at larger catalog sizes. Existing six-table persistence helper retained. |
| Documentation | README, architecture/database updates, `docs/datasets.md`, this report, and catalog README. Phase 1/2 reports are retained as historical records. |

## Database migrations and API contract

**No database schema change or new migration was required.** Existing scheme/source fields, UUIDs, relationships, category/state indexes and versioned policy tables already support the expansion. Alembic stays at **`0002_eligibility_rules`**. `alembic upgrade head`, round-trip migration tests and `alembic check` pass with no schema drift. No applied migration was edited.

- New `GET /api/v1/schemes/filters`: actual database category and verified state choices.
- Existing scheme list/detail responses add `eligibility_available`, reflecting an approved effective policy and non-inactive scheme. It is not an eligibility outcome.
- Existing `GET /api/v1/schemes` accepts optional `eligibility_available=true|false`, alongside unchanged validated search/category/state/pagination parameters.
- Existing requirements and assessment endpoints retain the safe metadata-only behavior: `available=false`, no questionnaire fields, and UNKNOWN/NO_APPROVED_RULE_SET with no evaluated version or fabricated conditions.

The seeder touches only `schemes` and `scheme_sources`. It never changes approved policies, documents, or assessments. Runtime applicant profiles and reports remain unpersisted.

## Verification executed

| Check | Result |
| --- | --- |
| Pre-change Phase 1/2 backend baseline | **210 passed**, existing three containers healthy |
| Final backend suite | **230 passed** in real PostgreSQL-backed tests; 20 new catalog cases plus all 210 existing regressions |
| Capacity | **PASS** — 501 synthetic records validated; 300 synthetic records imported/idempotently re-imported in an isolated PostgreSQL test transaction |
| Category manifest validation | PASS — 23 real manifests, category mismatch/missing field/invalid JSON/missing category/empty path rejection |
| Duplicate/source validation | PASS — duplicate slugs and normalized names across files, official HTTPS/domain/credentials/port checks |
| Preservation and atomicity | PASS — full current catalog import, local edits, IDs/source/history preservation, repeat import, and late DB-failure rollback across multiple files |
| Expanded API | PASS — all pages/unique IDs, category/state/search/detail/source relationships, availability filters and metadata-only UNKNOWN |
| Frontend suite | **27 passed** — original 21 plus six explorer/card/selector/cancellation regressions |
| Frontend types / Prettier | PASS |
| Backend Ruff / mypy | PASS — 52 Python files lint/format clean; 36 application files type-checked |
| Clean frontend production build | PASS — optimized build, TypeScript, static route generation in an isolated disposable container |
| Docker builds and startup | PASS — backend/frontend images build; `docker compose up --build -d` works; three services healthy |
| Actual repeat seed command | PASS — `files=23`, `records=282`, `inserted=0`, `preserved=282`, `sources_inserted=0` |
| Live catalog helper | PASS — all 282 curated records and every source relationship; 283 total database rows, 23 categories, 48 explorer pages; late-alphabetic direct questionnaire URL works |
| Existing live Phase 2 helper | PASS — PASS/FAIL/UNKNOWN synthetic cases, CORS, policy hash, five frontend pages and metadata-only fallback |
| Browser discovery | PASS — visible 283-record explorer, page 2, 23 categories, agriculture count 32, Goa/agriculture count 12, search PM KISAN, detail/source link and no-approved-rules notice |
| Container persistence | PASS — every row in all six domain tables unchanged after recreating database/API/frontend containers |
| Concurrent merge recovery | PASS — working source conflicts resolved, no conflict markers/unmerged index entries remain; no merge commit created |

The in-app browser intermittently blocked an initial cross-origin load; its normal Retry control recovered the catalog. A direct browser-only health navigation reported `ERR_BLOCKED_BY_CLIENT`; API readiness, cross-origin headers and frontend-to-API HTTP checks passed independently. No browser security restriction was disabled. The UI verification results above describe the successful observed interactions, not a claim that this testing client never blocked a request.

## Bugs fixed and repository state

The seed format no longer restricts records to exactly five. A scheme beyond the first 100 records can be opened directly in the questionnaire route without returning an erroneous 404. The fictional demo stays discoverable through the approved-policy query. New categories appear automatically, generic scheme wording replaces scholarship-only discovery labels, and national coverage is not displayed as zero states.

The expanded data exposed a pre-existing incorrect assumption that every government scheme uses NSP. That link is now retained only for the original reviewed scholarship records. Metadata-only records never acquire fabricated eligibility conditions.

A canceled explorer request can be reported as TypeError by a browser instead of AbortError. Superseded requests now cannot overwrite the active request's success/error state; the regression test simulates that case.

During implementation, an external Git operation committed current work and merged an older Phase 1 upload, introducing add/add conflicts into 21 existing paths. Both conflict versions were preserved in `/tmp/schemeguard-merge-conflicts`; working files retain the tested Phase 2/catalog content and conflicting paths were marked resolved. No merge commit was created by this implementation. Unrelated incoming bytecode additions were left untouched. The user's merge can be committed separately.

## Run, import and verify

```bash
python3 scripts/init_env.py
docker compose up --build -d
docker compose up -d --wait --wait-timeout 120
docker compose exec api alembic upgrade head
docker compose exec api python -m app.seed --validate-only
docker compose exec api python -m app.seed
docker compose exec -T api python -m tests.run
docker compose exec -T frontend npm test
docker compose exec -T frontend npm run typecheck
python3 scripts/verify_catalog.py
python3 scripts/verify_phase2.py
# Optional controlled recreation of all three services, preserving volumes:
python3 scripts/verify_persistence.py
```

Open [the explorer](http://localhost:3000/schemes) and [FastAPI docs](http://localhost:8000/docs). All services remain running. No additional container, dependency, database extension, background worker or exposed database port was added.

## Limitations and acceptance

The dataset is static. Directory presence establishes an authentic named record, not active availability; this review does not validate every downstream application portal or policy PDF. Descriptions are deliberately conservative, many central coverage fields remain unknown, and the Goa page does not identify every specific administering department. Geographic coverage is limited to supported source data and is not a domicile rule. Coverage is not representative of every state. Exact-name/slug validation cannot replace semantic alias review.

Insert-only imports intentionally do not apply later JSON edits to existing rows or delete rows removed from JSON. Corrections need a separate explicit reviewed operation. No real government eligibility rules have been published; the existing fictional policy remains the only assessable demo. Static-source monitoring, document extraction and human publication workflows are future work described in the dataset guide, not Phase 3 implementation.

All requested acceptance criteria pass: original functionality is retained, the seeder supports at least 300 records, the target authentic catalog is imported without duplication or overwrites, FastAPI/Next.js discovery works, unsupported eligibility claims remain blocked, Docker persists records, and relevant tests pass. The browser-client limitation above is explicitly recorded.
