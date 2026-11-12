# Static government scheme dataset

The catalog contains **282 verified government scheme identities** across **23 editorial categories**. This adds **277** records to the original five. PostgreSQL contains **283 scheme records** when the separate fictional Phase 2 fixture is enabled. The target of 250–300 government records is met; the gap to 300 is 18, which is not a missing acceptance requirement. The seeder has no 300-record cap: validation of 501 synthetic records and a 300-record PostgreSQL import are tested in isolated databases.

## Provenance and verification scope

| Records | Official source | Review scope |
| --- | --- | --- |
| 224 new central records | [DBT Bharat central scheme directory](https://dbtbharat.gov.in/central-scheme/list), Direct Benefit Transfer Mission, Government of India | Manually selected entries under their named department/ministry headings on 12 November 2026; identity and directory listing only |
| 53 new state records | [Government of Goa scheme directory](https://www.goa.gov.in/government/schemes/) | Manually selected distinct state scheme names and their catalog references on 12 November 2026; departmental attribution left unknown when absent |
| 5 preserved scholarship records | [NSP directory](https://scholarships.gov.in/All-Scholarships), [UGC Ishan Uday](https://www.ugc.gov.in/Scholarships/stu_Scholarship5), [West Bengal higher education overview](https://banglaruchchashiksha.wb.gov.in/scholarship_schemes), and the original [Ministry of Education PIB release](https://www.pib.gov.in/PressReleasePage.aspx?PRID=2294003&lang=1&reg=6) | Original metadata, eleven sources and 11 November 2026 verification dates retained verbatim |

These are authored static JSON records, selected after reading official public pages. No collection script, scraper, browser automation against government sites, private API, or runtime external synchronization is part of the implementation. myScheme's public search did not expose usable static listing content in this review; Kerala's department page returned an access restriction. Neither was bypassed or used to invent extra records.

`listed` means identity present in the cited directory at review time. It **does not mean active**, open to new applications, or available to an applicant. Historical fellowships and programmes can remain on official directories after closure, renaming or replacement. Names retain directory terminology; source notes explain the scope. Descriptions summarize directory administration and direct users to the official reference instead of inventing benefits. Categories are SchemeGuard navigation labels, not asserted official classifications.

A central department listing does not establish universal national coverage: these records retain `applicability: unknown` unless geography was independently verified. Goa records use the verified state-programme scope, without inventing residence rules. Ishan Uday retains its previously verified eight-state coverage. Unknown coverage is excluded by state filters.

## Deduplication decisions

The catalog deliberately excludes generic institutional names, payroll/salary rows, unidentifiable budget lines and repeated delivery-channel listings. Specifically:

- MOVCDNER appears once despite two directory labels. ATMA functionary/farmer channels and the two SMAM funding channels are not counted as separate schemes.
- EPF member/pensioner listings produce one Employees Pension Scheme record. ISRO centre-specific apprenticeship payment listings do not inflate the catalog.
- Mission Vatsalya, PALNA, Shakti Sadan and Anganwadi salary/training/payment channels are not counted as additional schemes; only the selected beneficiary programme entry is retained.
- Goa notifications, application forms, amendments and revised versions are grouped under a single scheme identity. Repeated Atal Asra, Matrutva and Gagan Bharari notifications do not become separate records. Ambiguous umbrella compilations are omitted.
- Genuine separately identified degree/diploma scholarships, SC/ST/OBC scholarship programmes, fellowships versus scholarships, and distinct educational level programmes retain distinct slugs. Existing scholarship slugs are never renamed.

The loader rejects duplicate slugs across all files and exact case/whitespace-normalized duplicate names under different slugs. It cannot automatically recognize every semantic alias: reviewers must compare policy identity and administrative scope before adding a record. The source notes are human-readable locators, not approved policy evidence or immutable downloaded documents.

## Organization and format

`data/schemes/*.json` are manifests using `backend/app/schemas/seed.py`. The legacy `data/scholarships.json` remains supported when explicitly passed as a file. Schema version 1 retains the existing required fields, official HTTPS domain validation, exactly one primary source, no duplicate source URL per scheme, supported-field provenance, state enums and consistent applicability rules. Category manifests must declare a category and every record must match it. Unknown properties are rejected. Official URLs with credentials, HTTP, non-default ports or lookalike domains are rejected.

The existing official-domain allowlist is unchanged: government `.gov.in` and `.nic.in` hosts plus the existing explicit AICTE domains. Other legitimate authorities require a deliberate reviewed validator change before importing their own URLs; an official government directory URL can be used when it directly identifies the scheme. A domain match alone cannot prove factual accuracy: a reviewer must actually inspect the page and locate the scheme.

There is no fixed five-record or 300-record limit. Read size should remain reasonable for this intentionally in-memory static import; use a controlled data pipeline for very large catalogs later.

## Import commands

From the project root:

```bash
python3 scripts/init_env.py
docker compose up --build -d
# Validate without opening a database connection:
docker compose exec api python -m app.seed --validate-only
# Full transaction; inserts missing schemes and leaves existing rows untouched:
docker compose exec api python -m app.seed
# Explicit source selection, including backward compatibility:
docker compose exec api python -m app.seed --path /app/data/schemes
docker compose exec api python -m app.seed --path /app/data/scholarships.json
```

`SEED_DATA_PATH` defaults to `/app/data/schemes`. The existing read-only `./data:/app/data` mount makes file changes visible. Development bootstrap seeds the government catalog when the existing `SEED_DEMO_DATA` switch is enabled, then separately seeds the fictional policy. With that switch disabled, run the explicit government seed command after migrations. No new service or volume is required.

All files are fully validated before opening the database transaction. A transaction-scoped advisory lock serializes imports. Slugs use the existing UUID5 namespace. A matching database slug is skipped, including its sources; local metadata edits, UUIDs, dates, approved rules, source relationships, and document history remain untouched. Missing rows and their sources are inserted together. Any validation, constraint, or database failure yields a non-zero exit and rolls back the whole import. Import code never deletes rows or resets volumes.

A successful initial expansion printed:

```json
{"files":23,"records":282,"inserted":277,"preserved":5,"sources_inserted":277,"validation_only":false}
```

A repeat import prints `inserted: 0`, `preserved: 282`, and `sources_inserted: 0`. The independently seeded fictional record is not part of these catalog import statistics. JSON counts are printed only after commit; structured logging also records the same statistics. Validation-only prints record/file counts without claiming insertion.

## Adding or reviewing records

1. Read an accessible public official page. Confirm the specific scheme identity and distinguish variants, rebrands, subcomponents, repeated notices, and central schemes merely implemented by a state.
2. Choose a permanent lowercase hyphenated slug. Search the entire catalog and database for aliases before adding it. Do not rename a slug to force an update.
3. Add the record to the matching category manifest (or create a manifest with a new category). Declare exactly one primary official HTTPS source, supported fields, publisher, title, locatable verification notes and the actual review date.
4. Keep unsupported descriptions, departments or geography null/unknown. Add no eligibility expressions, benefits, financial amounts, deadlines or guessed application URLs to this metadata format.
5. Run validation, backend tests, frontend tests and live discovery verification. Import with `python -m app.seed` and review inserted/preserved statistics.

Editing a record that is already in PostgreSQL intentionally does **not** update it. Metadata corrections need an explicit reviewed maintenance operation later. Removing a JSON record does not delete its database record. This behavior protects existing local edits and history.

## Discovery and eligibility

Existing discovery pagination, search, category/state filters and official-source details now work across the expanded catalog. `GET /api/v1/schemes/filters` returns actual category and verified state choices. Responses include `eligibility_available`, derived from an approved, effective rule version and a non-inactive scheme. The optional query parameter filters on that flag.

An availability flag denotes an approved/effective policy's presence, not a successful assessment or government approval. The existing eligibility service still validates configuration and evidence and fails closed on invalid policies. Metadata-only schemes expose no questionnaire fields and yield UNKNOWN/NO_APPROVED_RULE_SET if directly assessed. Newly imported records have no eligibility rules. The fictional test policy remains the only assessable fixture.

The frontend keeps its existing design. Categories/states load from the API, cards identify discovery-only records, direct questionnaire links fetch their scheme by ID instead of searching only the first 100 results, and the policy selector loads approved policies through pagination. The original five NSP-backed scholarship records retain their existing NSP application link. Other metadata records do not inherit that scholarship-specific link; users can follow their verified official source references.

## Static-data limits and future monitoring

Static verification becomes stale and does not establish that a downstream portal works today. This change verifies the cited directories and their identities, not every linked guideline or PDF. It introduces no real eligibility rules or government reviewer approvals. Some government departments, national geography, application portals and present operational status remain unknown. Scope is skewed toward centrally listed programmes and Goa; this is not comprehensive coverage of every state.

Future monitoring can enqueue reviewed source URLs for controlled retrieval, hash approved documents into immutable document versions, propose changes for human review, and publish new rule versions only after approval. A detected change must never silently overwrite metadata or approved rule history. That monitoring/extraction pipeline and Phase 3 are not implemented here.
