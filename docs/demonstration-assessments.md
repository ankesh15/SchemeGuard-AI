# Scheme-based demonstration assessments — implementation report

Implemented and verified on 14 November 2026. SchemeGuard remains an academic project demonstration, not an official government service. Illustrative criteria are not representations of current government requirements.

## Experience

`/eligibility` now starts with the existing PostgreSQL government catalog, with asynchronous search, category/state filters and pagination. No scheme is selected automatically. The old learning fixture is excluded with `is_demo=false`; old public fixture links lead back to government selection. Its database record, approved fixture rules, documents and saved history are preserved.

Selecting a scheme loads its metadata and server-selected questionnaire. The page shows either a reviewed-policy basis, an illustrative category basis, or an unsupported state. **Use Sample Details** uses the selected questionnaire's examples, not one scholarship profile for every category. Missing answers are allowed. Input validation, per-question errors, progress, request cancellation in catalog search, loading/empty/error states and mobile layouts are retained.

Reports show the scheme/category, entered details, PASS/FAIL/UNKNOWN with natural labels, matched/unmatched/unresolved conditions, missing fields, explanations, timestamp and criteria provenance. Reviewed rules retain valid evidence. Illustrative reports explain the authored criteria and contain no policy citations; official scheme links appear separately with an explicit source-scope note. The normal UI no longer presents development-fixture terminology or a large warning banner. Historical fixture data is relabeled only for public presentation; original backend evidence is not rewritten or falsely quoted.

The concise disclaimer is: “SchemeGuard AI is a project demonstration. Results are estimates and do not determine government eligibility.”

## Actual coverage

The working database contains **283 schemes: 282 government discovery records and one preserved legacy fixture**. There is **one approved legacy fixture RuleSet, zero approved government RuleSets and two document versions**. No rule or document was approved, deleted or replaced by this work.

Nine project-authored templates cover **225 government schemes across 14 populated categories**. The remaining **57 schemes across nine categories** stay explicitly unsupported. These counts describe demonstration coverage, not verified government eligibility coverage.

| Template | Categories | Relevant details |
|---|---|---|
| Education | scholarship, education | Age, family income, student status, education level |
| Livelihood | agriculture, fisheries | Age, family income, livelihood |
| Healthcare support | health | Family income, requested support, existing coverage; no diagnoses |
| Work and training | skills, youth; employment alias | Age, employment situation, training/work interest |
| Family support | women_child | Family income and requested support type; no child identities or medical records |
| Housing | housing | Age, family income and home ownership |
| Business | business | Age, business stage and plan availability |
| Social support | social_welfare, food_security, disability | Family income and support interest; no disability certification claims |
| Later-life support | pension | Age, family income and existing pension support |

Culture, energy, environment, research, rural development, sanitation, sports, transport and urban development currently have no suitable template. Unknown geographic coverage is not guessed. When a scheme has verified state-specific catalog coverage, the questionnaire can add a clearly illustrative location match; otherwise no state eligibility criterion is invented. The existing discovery state filter continues to use verified coverage only.

## Backend boundary

`backend/app/assessment/templates/*.json` is a separate, version-controlled asset collection. Pydantic validates each template, typed Program, descriptions and sample profile. `AssessmentService` reuses the existing deterministic engine without adding operators. Its mode is selected on the server:

1. Load the scheme and applicable approved policy through the existing eligibility service.
2. If a genuine human-reviewed policy applies, use it, including its questionnaire, immutable version and evidence.
3. If no approved policy applies, use a suitable project-authored category template when available.
4. Otherwise return UNSUPPORTED/UNKNOWN without a decision trace. Inactive and legacy fixture schemes are unsupported in this new public path.

Ambiguous versions, malformed approved rules, invalid evidence and approval failures propagate as errors; a template never hides those failures. A questionnaire fingerprint detects changed criteria between loading and submission and returns 409. The approved rule selected during submission is pinned for that evaluation.

Illustrative responses have `assessment_mode: ILLUSTRATIVE`, `template.basis: project_authored_illustration`, a template ID/version/fingerprint, `rule_set: null`, `policy_currency: UNVERIFIED` and empty evidence arrays at every trace node. They have no approval timestamp, policy UUID or source-document association. The conditions are never inserted into RuleSet/RuleCondition/RuleEvidence or extraction candidate tables.

The public route validates only the selected fields, rejects identifying/unexpected attributes and invalid numeric values, bounds bodies and applies rate limiting. It does not invoke Gemini, RAG, Celery, monitoring, reassessment, private assessment saving or notifications. Inputs and reports remain transient. The request-rate counter stores only a hashed key/count, not applicant details. No personal inputs are logged or sent to a model.

## APIs and compatibility

Added:

- `GET /api/v1/schemes/{id}/assessment-requirements`
- `POST /api/v1/assessment/check`

Extended the existing catalog query with optional `is_demo` and scheme responses with separate `assessment_available`/`assessment_mode` metadata. The default backend listing remains compatible; the public UI explicitly filters fixtures out. `eligibility_available` continues to indicate approved rules, not template availability.

The old `/eligibility/check`, `/eligibility/explain` and `/schemes/{id}/requirements` contracts remain unchanged. In those APIs, government metadata with no approved policy still returns UNKNOWN. The existing citizen saving and worker services still use the original approved-policy service. Passing a demonstration mode/template to private saving is rejected; a template PASS cannot become a saved approved government determination. Existing stateless calls, legacy saved reports, authenticated ownership, RAG, human approval and policy monitoring remain available.

## Files and database

Created `app/assessment` with nine JSON templates and a validated registry; `app/schemas/assessment.py`; `app/services/assessment.py`; backend regression coverage; frontend presentation helpers, selection tests, questionnaire/report fixtures and an assessment E2E spec. Updated the existing eligibility router, scheme schema/repository/service, public proxy allowlist, selector/explorer/cards, questionnaire/report, landing/detail/footer copy and citizen presentation. Reused existing styling and form components with scoped report/disclaimer styles.

**No SQLAlchemy model or schema changed. No migration is needed.** Alembic remains at `0009_citizen_system`; its drift check passed. Existing PostgreSQL/document volumes, keys, policy/document history and all services were retained. A private pre-change backup is in ignored `.local/backups/before-assessment-templates.dump`. The earlier development-cache refresh-loop fix remains in place.

## Executed verification

| Check | Actual result |
|---|---|
| Focused PostgreSQL/template/legacy API tests | 81 passed initially |
| Complete backend regression | **458 passed in 61.51 s**, including auth, graph/review, RAG, monitoring, history, reassessment and notifications |
| Frontend component/unit tests | **73 passed across 12 files**, including retained conditional visibility and private-proxy boundaries |
| Browser integration | **5 passed in 13.5 s** with the pinned Playwright package and installed Chrome in an isolated profile |
| Type checks | Strict mypy passed for 106 application modules; TypeScript passed |
| Formatting/lint | Ruff and frontend Prettier checks passed |
| Database | Migration drift check passed; no new schema operations |
| Production images | Backend and standalone frontend built successfully; nine template assets verified in the backend image; no cloud deployment |
| Development Docker | Updated images built; all six services healthy after recreation; volumes retained |

Browser checks exercised government search/selection, sample PASS, blank UNKNOWN, unmatched FAIL, mobile housing-specific questions, unsupported categories, source separation, login/profile/private saved history/reproduction/logout/deletion and mobile discovery. A sample report screenshot was visually inspected. Initial browser assertions used obsolete result copy and label selectors; the final run uses the new labels and semantic combobox selectors. The container's browser dependency download failed on Debian mirror/DNS timeouts; equivalent repository specs passed using existing local Chrome, not an invented container-browser result.

Browser tests use newly generated accounts and sample profiles. Successful runs delete their own account through normal authentication, CSRF and password checks, with cleanup on assertion failure. One initial failed run before that cleanup improvement left a generated `e2e_` test account and sample history; no pre-existing account or personal data was changed or removed.

## Run and maintain

```bash
docker compose up --build -d
# Existing database migrations remain safe/idempotent:
docker compose exec api alembic upgrade head
docker compose exec api python -m tests.run
docker compose exec frontend npm test
docker compose exec frontend npm run typecheck
docker compose exec frontend npm run lint
# Standard CI/container browser setup, when mirror access is available:
docker compose exec --user 0 frontend npx playwright install --with-deps chromium
docker compose exec --user 0 frontend npm run e2e
```

Open [scheme assessments](http://localhost:3000/eligibility). The saved-history browser regression uses the retained development learning fixture; do not seed it into production. No reseeding is required for the templates. All six existing services are retained; PostgreSQL/Redis remain internal. Never reset the database or remove volumes.

To add a template, copy the JSON structure, choose an explicit category mapping, use only supported typed expressions, describe every criterion as illustrative, supply a valid sample, and add positive/negative/missing/boundary/isolation tests. Increment the template version when criteria change; the response fingerprint also changes. JSON assets are cached per API process, so restart the API after edits. Do not add government URLs as condition evidence or copy these assets into policy tables. Genuine rules must continue through official-source processing and human approval.

## Limitations

Illustrative criteria can differ substantially from real requirements, benefit rules and application deadlines. They are estimates for a college demonstration, with no official accuracy claim. Unsupported categories remain unavailable. Public demonstration reports disappear on refresh and cannot be saved as policy determinations or trigger notifications. Real government saving/reassessment still requires actual approved rules. Gemini/embedding credentials and real government-policy approval were not needed or exercised for this change. No unrelated phase, cloud deployment or new Docker service was introduced.

Suggested commit: `feat: add scheme-based demonstration assessments with isolated category templates`. No commit, push or deployment was performed automatically.
