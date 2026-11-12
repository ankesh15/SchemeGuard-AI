# Deterministic rules and approval

The pure `backend/app/eligibility` package performs no database, HTTP, file, model-provider, or background-job I/O. Its only inputs are a validated `Program` and an applicant-value mapping. Results are PASS, FAIL, or UNKNOWN. The application service selects an approved, effective immutable version before calling it.

## Expressions

Each expression has a unique `key`, an optional human-readable `label`, and a discriminator `kind`:

| Kind | Fields | Meaning |
| --- | --- | --- |
| `comparison` | `field`, `operator`, `value_type`, `value` | Compare a declared field with a typed literal or membership list |
| `and` | `children` | All child conditions |
| `or` | `children` | Any child alternative |
| `exclude` | `expression` | Matching the child excludes the profile |
| `if` | `when`, `then`, optional `otherwise` | Evaluate the branch selected by the guard |

Comparison operators: `==`, `!=`, `>`, `<`, `>=`, `<=`, `IN`, `NOT IN`. Types: `number`, `string`, `boolean`, `date`. Ordered comparisons require numbers or dates. Membership lists contain 1–50 values of the declared type. Numbers are compared as Decimal; date literals and profile dates use strict ISO calendar dates. Numeric strings are supported to preserve decimal precision; booleans and non-finite numbers are rejected as numeric inputs. No dynamic Python expressions, dotted object traversal, calls, imports, `eval`, or `exec` are supported.

Every referenced profile field must be declared with the matching type. Profile field names and expression keys are bounded tokens. A program has at most 32 fields, 128 expression nodes, and 12 nested levels. Empty groups, unknown operators/kinds, duplicate keys, invalid literals, and unexpected profile fields fail validation. Applicant input is limited to scalar/null values, 32 keys, and bounded strings. These are application-validation limits, not a complete production edge rate-limit/body-size policy.

Example from the **fictional** policy, not a government rule:

```json
{"kind":"comparison","key":"age_minimum","field":"age","operator":">=","value_type":"number","value":18}
```

## Three-valued semantics

| A | B | AND | OR |
| --- | --- | --- | --- |
| PASS | PASS | PASS | PASS |
| PASS | FAIL | FAIL | PASS |
| PASS | UNKNOWN | UNKNOWN | PASS |
| FAIL | FAIL | FAIL | FAIL |
| FAIL | UNKNOWN | FAIL | UNKNOWN |
| UNKNOWN | UNKNOWN | UNKNOWN | UNKNOWN |

Missing and null values are UNKNOWN, including for `!=`, `IN`, and `NOT IN`. False and zero are known values. Exclusion inverts PASS/FAIL and preserves UNKNOWN. A conditional with an unknown guard remains UNKNOWN even if another branch could appear permissive. A false guard with no `otherwise` branch means that additional requirement does not apply; it does not demand fields from the unselected branch.

All children of an AND/OR group are traced. A known passing OR alternative removes missing fields from irrelevant alternatives from the actionable missing-field list; those branch traces still show UNKNOWN. An AND may return FAIL and still identify missing information elsewhere. Reports use top-level requirement outcomes, so a false conditional guard or an unmatched alternative is not mislabeled as a failed overall requirement.

## Database publication boundary

New rule sets must start as DRAFT. Their scheme, version number, dates, source version, profile definitions, and scope note never change. Conditions and evidence are insert-only and may be added only while the parent is DRAFT. Parent locking serializes insertion and approval. A draft can transition once to APPROVED or REJECTED; approved/rejected versions and their children cannot be updated, deleted, or truncated through normal DML.

Approval requires a nonempty condition set, evidence for each condition, an actor, an approval timestamp, and an approval basis. Foreign keys and triggers enforce same-set evidence, the rule set's exact source-document version, and the source document's scheme association. Synthetic approval is rejected for non-demo schemes; a scheme with rule history cannot be reclassified between government and demo. Government rules require `human_review`. A real administrator must establish actual human review before using that basis; the label is not itself authentication or proof of a reviewer identity. Database owners can bypass database protections; no public approval/admin write route exists in Phase 2.

Only APPROVED versions with `effective_from <= assessment date` and no expired `effective_to` are selected. The highest applicable version number wins. DRAFT, REJECTED, future, and expired versions are excluded. The assessment date is determined by the service using Asia/Kolkata; the public request cannot select a rule version, approval state, or backdated assessment date. Responses return the exact version and source-document hash used.

Approved JSON is still parsed and validated at use time. Malformed configuration fails closed with 503; it never becomes a permissive result. No effective approved policy yields UNKNOWN with `NO_APPROVED_RULE_SET`, no trace, and no evaluated version.

## Fictional fixture and future government rules

`python -m app.seed_demo` validates the authored fixture and captures the exact bytes of `data/policies/demo-policy-v1.md`, then inserts a DRAFT version, conditions, and evidence before approving it with the explicit `synthetic_fixture` basis and `development-fixture` actor. It is limited to development/test environments and never approves government schemes. Repetition preserves existing versions. Changed policy bytes require a new version; they cannot overwrite the recorded document.

The fixture is the permitted Phase 2 fallback after conflicting Saksham source wording prevented verification of a coherent current rule set. Government metadata remains public discovery data. No rules extracted by AI are published, no fictional thresholds are attached to government records, and no LLM decides eligibility.

Future government policy work needs authenticated administration, verified immutable official documents, complete field-level evidence, explicit human approval, and new immutable versions. Those workflows are outside Phase 2.
