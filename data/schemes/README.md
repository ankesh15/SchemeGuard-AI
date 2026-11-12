# Curated scheme catalog

This directory contains **282 authentic government scheme identities** in **23 category JSON manifests**: the original five scholarship records, 224 additional central directory records, and 53 Goa state records. The fictional Phase 2 fixture is seeded separately and is not included in this count.

The new records were reviewed on **12 November 2026** against the public [DBT Bharat central scheme directory](https://dbtbharat.gov.in/central-scheme/list) and [Government of Goa scheme directory](https://www.goa.gov.in/government/schemes/). Verification establishes identity, directory presence and the fields named in each source's `supported_fields`. It does not establish a current application window, amount, entitlement, or approved eligibility policy. Directory titles can retain historical spelling and closed or superseded programmes.

Each file declares `schema_version: 1`, a `category`, a `review_method`, and a non-empty `schemes` array. Filenames follow the category for readability. The loader accepts any number of records and reads only direct `*.json` children, in sorted order; it does not import this README. The original `../scholarships.json` remains a compatible historical manifest and regression fixture, not a second default import source.

Every record includes a stable slug, official directory name, cautious description, nullable ministry/department, editorial category, applicability, nullable state list, directory status, verification date, and one or more official source relationships. Source notes identify the directory section and scheme identity. Unknown fields stay null/unknown. In particular, the Goa catalog page does not verify every individual administering department, so those fields are null.

For the full provenance inventory, deduplication decisions, extension instructions, and limitations see [the dataset guide](../../docs/datasets.md). No scraper, crawler, or remote API synchronization is used.

```bash
docker compose exec api python -m app.seed --validate-only
docker compose exec api python -m app.seed
```
