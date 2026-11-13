# Database design — Phase 3

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

Tests use disposable real PostgreSQL databases, transaction rollback, full migration round trips, explicit Phase 1-to-Phase 2 preservation checks, FK/approval/history constraints, and public-stateless-profile assertions and private owner-isolation checks. The persistence helper compares aggregate row hashes/counts in all discovered public/checkpoint tables and verifies original PDF checksums before and after recreating all six Compose services. The existing named PostgreSQL volume is retained.

Downgrades remove Phase 2 history and are destructive. They are exercised only in disposable test databases; normal development never downgrades or resets application data. Docker volumes are not backups, and production role separation/backup restore testing remain deferred.

## Catalog expansion without schema changes

No new migration is needed: the existing variable-length text, category, state-array and source-provenance columns already support this dataset. The catalog expansion itself remained at `0002_eligibility_rules`; Phase 3 subsequently adds `0003_ai_ingestion`. Earlier applied migrations remain unchanged.

The default curated import contains 282 government records in 23 files; the live development database contains 283 schemes and 289 scheme-source rows including the pre-existing fictional fixture. Document/rule counts remain one document, one synthetic approved rule set, six conditions and six evidence references. No government rule set was added.

Import UUID5 keys use the original namespace. A transaction-scoped advisory lock serializes concurrent seed commands. Existing slugs skip every write, preserving UUIDs, timestamps, local edits, sources and immutable history; all newly inserted records and sources commit together. A full pre-import snapshot of the original six schemes and all associated source/document/rule rows was compared by ID after import. All were identical. The preservation and rollback behavior is also exercised in isolated PostgreSQL integration tests.

The response-only `eligibility_available` flag and category/state facets are computed queries, not schema changes or stored applicant decisions. The importer writes only `schemes` and `scheme_sources`.


## Phase 3 incremental migration

`0003_ai_ingestion` adds 12 tables without modifying existing scheme/document/rule rows: `users`, `login_sessions`, `rate_limits`, `audit_events`, `source_authorizations`, `document_assets`, `document_pages`, `document_chunks`, `document_processing_jobs`, `extracted_rule_candidates`, `candidate_evidence`, and `extraction_errors`.

`document_assets` extends the existing immutable DocumentVersion by its primary/FK ID, preserving upload filename, acquisition method, raw PDF metadata and page count. Status is mutable; source hash/size/storage/supersession remain in DocumentVersion. Existing historical text documents need no asset row and are untouched. Source authorizations pin an exact SchemeSource URL hash to the approving administrator.

Pages and chunks belong to an existing document version. Composite foreign keys prevent cross-document chunk/page or candidate/evidence/job references. Page and chunk identifiers are stable UUID5 values; chunks include algorithm-tagged identity, section, page, method, bounding box, offsets and text hash. Jobs track provider/model/schema version, immutable input chunk references, status, errors and counts. A partial unique index permits one RUNNING job per document. An expired lease is marked FAILED before a subsequent extraction.

Candidate expressions use the existing typed engine shape, stored only as a preview. A database check allows **PENDING only**, with separate technical validation states VALIDATED, NEEDS_REVIEW, INVALID and CONFLICT. Append-only UPDATE/DELETE/TRUNCATE guards protect candidates, page text, chunks, evidence, errors and audit events. No publication operation or candidate-to-approved-rule conversion is implemented. RuleSet, RuleCondition and RuleEvidence are reused only as the established future publication destination and existing evaluation source.

Sessions store SHA-256 digests of high-entropy tokens, never raw cookies. Passwords use Argon2id. User role supports admin/citizen for future account infrastructure, but Phase 3 provisions administrators only through the operator CLI. Account/session/rate/job/status rows are operational state; evidence and rule content remain historical records. Database owners remain privileged and can bypass database guards.

Current Phase 3 counts and exact preservation checks are recorded in [the Phase 3 report](phase3-ai-ingestion.md). Downgrade tests run only against disposable databases; never downgrade the development database to clean up data.

`0004_least_privilege` changes only the default role for future user rows to citizen. Existing administrator roles are preserved; the provisioning CLI explicitly assigns admin. This avoids accidental privilege grants when citizen accounts are introduced later. The current migration head is `0004_least_privilege`.

## Phase 4 additions

- `0005_workflow_rag`: pgvector extension and seven tables: agent_workflows, workflow_events, policy_reviews, review_revisions, review_decisions, rule_publications, chunk_embeddings. UUID foreign keys retain document/extraction/rule provenance; review decisions, publications and chunk namespaces have uniqueness guards. Append-only history triggers prohibit update/delete/truncate; original review proposals/findings cannot be altered.
- `0006_graph_checkpoints`: separate `sg_checkpoints` schema with the official PostgreSQL saver's checkpoint_migrations/checkpoints/checkpoint_blobs/checkpoint_writes definitions and indexes. DDL is versioned by Alembic, not SDK setup on every request.
- `0007_workflow_provenance`: cross-entity triggers bind extraction jobs to the exact workflow document, decisions to current revisions and active administrators, and publications to matching approved rules/documents/human decisions. Workflow identity and published rule bindings are immutable.

RuleSet, RuleCondition, RuleEvidence and DocumentVersion remain the sole existing executable policy/version representations. Publication appends a DRAFT parent, conditions and page evidence, then transitions it to APPROVED with reviewer metadata within one transaction and an immutable publication ledger. Per-scheme locking serializes version allocation. Prior approved versions and effective dates are never overwritten. Overlap relationships require explicit review.

`chunk_embeddings.embedding` is vector(768), normalized and namespaced by provider/model; chunk SHA-256 prevents interpreting a changed chunk with an old vector. Exact cosine scans are used for this MVP. Checkpoint rows and original PDFs are included in the recreation/persistence verification script. Back up both PostgreSQL (including sg_checkpoints) and the document_data volume; neither alone is a full recovery backup.

## Phases 5 and 6

Migration 0008 adds durable background jobs, opt-in source monitors/runs, policy changes/details/review events with provenance guards. Migration 0009 adds encrypted owner-scoped profiles, preferences, immutable assessments/reassessment events, and approved-publication-only notifications. Existing users/login_sessions/audit_events are reused. Account deletion purges its private rows leaf-first while preserving policy/audit references. See phase5-policy-monitoring.md and phase6-user-system.md for schemas/APIs/tests; authentication.md documents sensitive-payload encryption and operational key/backup requirements. Never downgrade the working database.
