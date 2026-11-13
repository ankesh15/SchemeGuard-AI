# Deterministic eligibility methodology

The existing Python typed AST supports ==, !=, >, <, >=, <=, IN, NOT IN, dates, nested AND/OR, exclusions and conditional branches. It never calls eval/exec. Pydantic validates structure, field types, finite numeric values and operators before evaluation. Missing/null inputs produce UNKNOWN rather than a successful comparison. AND: FAIL dominates, otherwise UNKNOWN dominates PASS. OR: PASS dominates, otherwise UNKNOWN dominates FAIL. Unknown conditional guards remain UNKNOWN.

Only applicable approved policies can be selected. Overlapping versions require an explicitly reviewed replacement covering all effective alternatives; ambiguity returns a conflict. Future, draft, unreviewed or mismatched-document policies cannot support a decision. Saved assessments pin the original rule, date, engine marker and encrypted minimal input/report. Reproduction uses that exact version rather than current selection. Reassessment appends a new report, never overwrites history.

UI descriptions are “Known conditions satisfied”, “Requirements not satisfied” and “More information required”. No response promises government approval. Discovery metadata alone returns an unavailable questionnaire/UNKNOWN API report. Static category/state filters describe verified discovery scope, not personal eligibility. See rules.md, policy-versioning.md and reassessment.md.
