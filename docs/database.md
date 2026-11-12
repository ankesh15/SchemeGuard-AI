# Database design — Phase 2 and curated catalog

PostgreSQL 16, SQLAlchemy 2.x, asyncpg, and Alembic remain in use. UUID domain keys and timezone-aware timestamps are preserved. No extension or future vector-search service is added.

## Migrations and preserved data

- `0001_initial_metadata`: unchanged Phase 1 tables, constraints, indexes, document immutability, and scheme update timestamps.
- `0002_eligibility_rules`: three new rule tables, `schemes.is_demo` with a false default, selection/evidence indexes, foreign keys/check constraints, and immutable-version/approval guards.

Migration 0002 is additive. The previous five government records remain non-demo, with their IDs, timestamps, descriptions, and eleven source references preserved. A separate explicit development seed adds one fictional scheme, one fictional source, one immutable authored document version, one approved synthetic rule set, six top-level conditions, and six evidence references. No applicant or assessment-result table exists.

## Tables and relationships

| Table | Purpose and constraints |
| --- | --- |
| `schemes` | Existing discovery fields plus `is_demo`; cannot change classification once rule history exists |
| `scheme_sources` | Existing scheme-linked source URLs, publisher, verification metadata, and supported fields |
| `document_versions` | Existing append-only source versions, hash, byte length, storage key, retrieval/publication dates, and same-source supersession |
| `rule_sets` | Scheme/version uniqueness, source-document FK, immutable title/dates/profile definitions/logic/scope, approval metadata and state |
| `rule_conditions` | Immutable top-level condition expression JSONB, label, key, and position; unique key/position within its set |
| `rule_evidence` | Immutable condition/source-document relationship, section locator, and excerpt; composite FKs guarantee same set and exact set source version |

One scheme has many rule versions. A rule version points to an immutable document version and has many ordered conditions; each condition has evidence references. The document belongs to a source of the same scheme, enforced on rule-set insertion. Conditions may contain safe nested expression trees; top-level logical_operator combines them with AND or OR. Program validation checks expression structure and referenced profile-field types when rules are loaded.

The rule set stores questionnaire definitions as JSONB metadata, not applicant responses. Each condition's expression is stored once. A draft must contain conditions and evidence before approval. INSERT child triggers lock the parent row so child assembly cannot race approval. No UPDATE or DELETE of rule contents/children is permitted; version numbers cannot be reused after rejection because versions cannot be deleted. TRUNCATE is also rejected through triggers.

Approval state is DRAFT, APPROVED, or REJECTED. APPROVED requires approved_at, approved_by, and an allowed approval_basis. A government scheme cannot use synthetic_fixture approval. Approval actor strings are metadata, not an authenticated administration system; no public approval route exists. Privileged database owners can bypass protections.

## Effective version selection

The repository selects APPROVED rows for the requested scheme where effective_from is on/before the service's assessment date, and effective_to is absent or on/after it. The highest applicable version number wins. Future, expired, rejected, and draft versions cannot be evaluated. The service determines the date in Asia/Kolkata; public callers cannot override it or choose a rule version.

If no version is available, requirements report available=false and assessment returns UNKNOWN with no evaluated version. A malformed approved configuration returns 503 instead of being treated as satisfied. Each successful assessment returns the exact rule-set ID/version and source-document ID/hash.

## Existing geography and source semantics

The original five verification dates remain 11 November 2026. The 277 new records were checked on 12 November 2026. Ishan Uday retains its eight verified states; 53 Goa state-programme records add Goa coverage. Other central coverage remains unknown. `listed` records directory presence rather than an application window. Demo classification is separate from scheme status; the fictional scheme has unknown government status and no official source/application URL.

For the fictional fixture, the reserved example.invalid source is labeled synthetic. `policies/demo-policy-v1.md` contains the actual authored source bytes. Its SHA-256 and byte count are persisted; the frontend's served file is checked against that hash. No government document snapshot or approved real scholarship rule is fabricated.

## Operations and verification

```bash
docker compose exec api alembic upgrade head
docker compose exec api alembic current
docker compose exec api alembic check
docker compose exec api python -m app.seed
docker compose exec api python -m app.seed_demo
docker compose exec -T api python -m tests.run
python3 scripts/verify_persistence.py
```

The seed commands acquire transaction advisory locks and preserve existing records. Fixture seeding refuses changed document bytes under an existing version. New policy contents require a new immutable document/rule version. Automatic development seeding is optional through SEED_DEMO_DATA; disabling it does not remove previously created immutable history.

Tests use disposable real PostgreSQL databases, transaction rollback, full migration round trips, explicit Phase 1-to-Phase 2 preservation checks, FK/approval/history constraints, and no-profile-persistence assertions. The persistence helper compares all rows in all six domain tables before and after recreating all three Compose services. The existing named PostgreSQL volume is retained.

Downgrades remove Phase 2 history and are destructive. They are exercised only in disposable test databases; normal development never downgrades or resets application data. Docker volumes are not backups, and production role separation/backup restore testing remain deferred.

## Catalog expansion without schema changes

No new migration is needed: the existing variable-length text, category, state-array and source-provenance columns already support this dataset. Alembic remains at `0002_eligibility_rules` and model/schema drift checks pass. All applied migrations are unchanged.

The default curated import contains 282 government records in 23 files; the live development database contains 283 schemes and 289 scheme-source rows including the pre-existing fictional fixture. Document/rule counts remain one document, one synthetic approved rule set, six conditions and six evidence references. No government rule set was added.

Import UUID5 keys use the original namespace. A transaction-scoped advisory lock serializes concurrent seed commands. Existing slugs skip every write, preserving UUIDs, timestamps, local edits, sources and immutable history; all newly inserted records and sources commit together. A full pre-import snapshot of the original six schemes and all associated source/document/rule rows was compared by ID after import. All were identical. The preservation and rollback behavior is also exercised in isolated PostgreSQL integration tests.

The response-only `eligibility_available` flag and category/state facets are computed queries, not schema changes or stored applicant decisions. The importer writes only `schemes` and `scheme_sources`.
