# Human review and immutable publication

Only an active `admin` account with a valid HttpOnly session, allowed Origin and CSRF token may edit or decide reviews. Provision administrators through the existing CLI, never a public registration endpoint:

```bash
docker compose exec api python -m app.auth.provision --username reviewer
```

Open `/admin/reviews`. Read the preserved original PDF and each extracted page. Review headings, tables, exclusions, dependencies, required documents, dates, conflicts with other guidelines, and current applicability. **A successful extraction does not establish a complete or current government policy.** Do not approve an isolated threshold as if it represents all eligibility requirements.

## Revision editor

The immutable original proposal is displayed beside the current JSON proposal. Edit the existing deterministic expression schema: comparison, and, or, exclude, if. No `eval`, executable code or extra operators are accepted. Leaf fields must use the maintained Phase 3 vocabulary with matching types and units. Conditions reference original candidate IDs; each original candidate must be included exactly once or listed in `excluded_candidates` with a substantive reason. Reviewer-added conditions also need located page excerpts for every leaf.

Evidence uses `{node_key, page_number, excerpt}`. Each quote must actually occur on the stored source page; operators, thresholds, units and dates are checked. Currency must explicitly support annual INR; percentage units require a percent indication. Ambiguous language and exceptions produce findings for human resolution. Unsupported values, missing evidence, invalid expressions and contradictory complete programs block publication. Bounded satisfiability checks cover nested AND/OR, exclusions and conditional branches; policies exceeding the proof bounds are rejected for manual restructuring.

Record complete `scope_note` and `applicability_note`. An `official_stated` effective date requires a located excerpt containing that explicit date. `reviewer_activation` instead records an administrative activation date and reason; it does **not** claim that the government announced that date. Dates are never filled from extraction time. Review historical guideline validity against current official notices before activation.

All overlapping approved rule versions must be explicitly listed in `replaces_rule_set_ids`, with `replacement_notes` explaining date and applicability relationships. Approval does not mutate their date ranges or contents. The existing engine chooses the highest version effective on the assessment date; this is a single reviewed applicability scope per scheme, not an automatic resolver for competing regional policies. Split/reconcile differing scopes before approving.

Save a new revision with notes. Every save records actor, timestamp, exact proposal and SHA-256; it never overwrites a previous revision. Optimistic revision checks return 409 for stale edits. No browser storage retains draft policy edits.

## Decision contract

Approval references the exact saved revision number and SHA-256. It requires substantive notes, confirmation of an actual human reviewer, complete policy coverage and applicability, every original page, and every non-informational verification finding. Automated tests simulate these attestations only in disposable databases; they do not constitute real policy approval.

The backend revalidates before accepting the decision and again before publication. It records one immutable decision per review, with reviewer ID, timestamp, action, notes and attestations. Unique constraints reject duplicate approvals. Publication rechecks current administrator activity, source authorization, original-file checksum, typed policy validity, evidence and overlapping versions. A changed situation fails closed. Source review findings and uncertainty cannot themselves approve anything.

Rejection requires notes but no executable policy. It resumes the rejection branch and creates no RuleSet. Cancellation is restricted to undecided/unpublished workflows. Approved versions are never editable or deletable through these APIs; corrections require another sourced document/proposal, human decision and immutable rule version.

Database append-only triggers guard revisions, decisions, events, publication and embeddings; cross-entity triggers enforce matching workflow document/extraction and decision/revision/publication provenance. The PostgreSQL owner remains privileged and can bypass database guards; production role separation is a later deployment task.
