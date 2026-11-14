# Profile-first recommendations — implementation and verification

Verified locally on 2026-11-14. This extends the existing application; it does not implement another phase, replace eligibility, approve government rules or deploy to a cloud service.

## Result and repository audit

Primary journey: **Home → Find My Schemes → optional details → personalized results → scheme details → available assessment → report → edit details**.

The audit found reusable encrypted `ProfileData` storage, shared citizen/admin sessions, typed questionnaire controls, the version-aware `EligibilityService`, separate illustrative templates, existing scheme repositories and the six-service Compose stack. The old dashboard used state-filtered discovery only. It now calls the same `RecommendationService` as guests and citizens. No second rule engine, profile store or AI workflow was introduced.

Live development database after verification:

| Record | Actual count |
|---|---:|
| Government scheme records | 282 |
| All schemes, including retained legacy example | 283 |
| Scheme source records | 290 |
| Rule sets | 1 legacy example |
| Approved government rule sets | 0 |
| Document versions | 2 |
| Encrypted stored profiles | 4 |
| Saved assessments | 4 |
| Monitoring runs | 0 |
| Notifications | 0 |

No scheme, source, profile, historical rule, document, assessment or notification migration/reset was performed. The application remains at `0009_citizen_system`; `alembic check` reports no new upgrade operations. Public catalog/rule/document counts match the initial baseline. Browser tests generated four additional **closed**, anonymized test-account tombstones in the development database before final authentication checks were moved to an isolated test database; they did not change existing users. The final live database has 11 user rows and 4 active citizens. Account closure deliberately retains the existing audit/tombstone behavior. Later browser test accounts existed only in the isolated test stack.

## User experience

- The homepage makes no catalog request and renders no scheme grid. It retains the green/white identity, uses the requested heading and description, prioritizes **Find My Schemes**, and explains four steps.
- `/find-schemes` has five accessible, optional steps: age/state, education/student/course, occupation/employment, sensitive optional income, and catalog-derived interests. It has validation, progress, back/next, loading/error states and explicit encrypted-profile save consent.
- Guests need no account. Details/reports live only in React memory; there is no localStorage/sessionStorage, profile in a URL, analytics event or persistent guest record. Reloading clears guest answers. Registration can carry existing guest answers to the questionnaire, where saving still requires consent.
- Citizens securely prefill their own saved profile. New optional `interests`, `employment_status` and `field_of_study` fields use the existing encrypted JSON payload. Older profiles remain valid. The profile editor preserves these fields when editing its original fields. Logout, new login and account deletion clear transient private state. A draft belonging to another signed-in account is not used for questionnaire prefill.
- `/schemes` and `/dashboard/schemes` resolve to recommendations when submitted/saved details exist, otherwise the questionnaire. `/schemes/all` retains searchable, paginated manual exploration. Existing `/eligibility` links still work.
- Results show count, non-sensitive profile summary, category filter, relevance/name sorting, pages, reasons, missing information, assessment basis, source links and **Edit Details**. Empty results invite more details rather than displaying unrelated schemes.
- Scheme details show the current recommendation explanation. Compatible fields are reused by public questionnaires and approved-policy private assessment forms; unrelated/unsupported choice values remain unknown. Detailed criteria without a supported assessment are explicitly unavailable.
- The dashboard retains profile completeness, saved history, notifications and verified updates, and replaces geographic-only suggestions with shared recommendations and relevant categories. Recently viewed tracking was not introduced.

## Matching algorithm

`RecommendationService` reads current non-demo, non-inactive schemes and primary source relationships from PostgreSQL. It does not contain a copied scheme list, LLM call, demographic inference or income/age threshold.

| Signal | Points | Basis |
|---|---:|---|
| Selected interest matches normalized category | +60 | Project relevance heuristic |
| Explicit occupation/employment matches a relevant category | +20 once | Project relevance heuristic |
| Explicit current student and education/scholarship category | +20 | Project relevance heuristic |
| Verified national coverage or matching listed state | +8 | Existing catalog provenance |
| Applicable, safely loadable human-approved assessment | +5 | Existing approval/version/evidence checks |
| Education matches a positive direct course condition in that approved policy | +15 | Typed approved comparison; no lift from exclusions/conditionals |
| Supplied information satisfies all known approved conditions | +12 | Existing deterministic engine |
| Known approved conditions fail | −20 | Existing deterministic engine; the reason is displayed |

Related interests normalize to existing taxonomy: education covers scholarship/education; agriculture covers agriculture/fisheries; employment covers skills/employment; welfare covers social welfare/food security/disability. Youth is a separate explicit interest, not an assumed employment category. Other seeded categories appear dynamically. Existing occupation choices stay unchanged; employment status refines broad category relevance.

At least one category/profile relevance signal, a positive approved education match, or a complete approved-condition match is required. Availability or geography alone cannot recommend unrelated schemes. Unknown age/income/education never produce a failure. Unknown geographic coverage is retained with a missing-information explanation; only an explicitly verified state mismatch excludes a result. Approved policy ambiguity/configuration errors prevent an illustrative fallback.

HIGH means at least 75 additive points; lower scores are POTENTIAL. An explicit reviewed-condition failure is labeled MORE_INFORMATION with a requirement warning. These are relevance labels, never probabilities or government eligibility decisions. Sorting is descending points, then case-insensitive name and UUID; name sorting is also available. Schemes are unique by database ID. Category filtering applies before pagination; available categories derive from the complete matched set.

Only applicable human-reviewed rules can use precise policy criteria. Separate illustrative templates affect assessment availability only: their numerical conditions never affect recommendation ranking, approved rules, saved policy reports or notifications. Positive direct education comparisons are deliberately conservative; nested branches are evaluated as part of the overall approved program rather than promoted to independent education signals.

## APIs and privacy boundaries

| Method | Endpoint | Behavior |
|---|---|---|
| POST | `/api/v1/recommendations` | Stateless bounded profile body + paging/filter/sort; guest or citizen inputs |
| GET | `/api/v1/recommendations/options` | Categories/interests from the active government catalog; state input choices |
| POST | `/api/v1/me/recommendations` | Uses only authenticated citizen's own encrypted profile; body contains paging/filter/sort only |

All previous contracts remain available. Existing `/api/v1/dashboard` now returns ranked SchemeRead-compatible items with additive recommendation fields. OpenAPI has 75 operations including health/readiness.

Canonical input names follow the existing profile: `age_years`, `course_level`, `annual_family_income_inr`, `state`, `current_student`, `occupation`, plus optional new preference fields. `page` is 1–100000, `page_size` 1–30, `category` is an exact category and `sort_by` is `relevance`/`name`. Interests are normalized identifiers, at most 24; course text is bounded to 80 characters. Unexpected fields/user IDs are rejected.

The Next.js public proxy forwards no session cookies and bounds request bodies to 16 KB. Personal fields are only in POST bodies. Responses and sanitized errors use no-store; logs contain route/status/timing, not inputs. The backend limits recommendation calls to 120 per 900 seconds by direct peer, storing only hashed rate-counter keys. A proxy peer shares this quota. Private endpoints retain CSRF, exact Origin checks and role/owner authorization. Only explicit existing PUT profile actions persist private answers.

## Executed sample results

The complete captured responses (two top items per example) are in [sample inputs/results](verification/profile-first-recommendations-samples.json). These inputs are synthetic testing data.

| Input | Matched schemes | Top example |
|---|---:|---|
| Age 21, Assam, undergraduate student, income INR 240000, education interests | 78 | Ishan Uday Special Scholarship for the North Eastern Region |
| Assam and agriculture interest, other fields unknown | 21 | Agri Clinics and Agri Business Centres ACABC |
| Unemployed and employment interest | 12 | Capacity Building for Service Providers |
| All details unknown | 0 | Useful request for interests/details; no unrelated grid |

For the student example, interest + occupation + student status + verified state yield 108 points. Income and age add **zero** points because no government rule is approved. The illustration is separately identified when the user chooses an assessment.

```bash
curl -s http://localhost:3000/api/v1/recommendations \
  -H 'Content-Type: application/json' \
  -d '{"age_years":21,"state":"Assam","course_level":"undergraduate","current_student":true,"occupation":"student","annual_family_income_inr":240000,"interests":["education"],"page":1,"page_size":9,"sort_by":"relevance"}'
```

## Actual verification

| Check | Result |
|---|---|
| Full PostgreSQL backend regression | **491 passed**, 66.61 s; 33 new recommendation cases |
| Full frontend Vitest regression | **84 passed**, 13 files, 2.33 s |
| Full existing + new Chrome browser suite | **9 passed**, 35.7 s |
| Final profile-first desktop/mobile browser rerun | **4 passed**, 22.8 s |
| Python Ruff | Passed |
| Python mypy | Passed, 109 application modules |
| TypeScript no-emit check | Passed |
| Frontend Prettier lint | Passed |
| Alembic | Head `0009_citizen_system`; no schema drift |
| Development Docker image build | Passed |
| Production backend/Next.js standalone image build | Passed; includes new routes |
| Development Compose startup/recreation | Six services healthy; preserved persistent volume |
| Public proxy → backend → PostgreSQL samples | Passed for all four inputs above |

Backend cases cover student/agriculture/employment profiles, optional income, incomplete inputs, multiple interests, approved-condition/education precision, exclusion separation, unsupported values, no invented template thresholds, verified/missing geography, duplicates/ranking/pagination/filtering/name sorting, no match, source links, no guest profile/history writes, own saved profiles/CSRF and dashboard parity. Existing tests continue to cover policy/AI workflows, historical versions, deterministic three-valued logic, authentication, rollback, reassessment and notifications.

Frontend cases cover the empty-of-schemes homepage, questionnaire CTA/navigation/validation/unknown answers, guest privacy, saved-profile prefill and explicit save, recommendation cards/filters/errors/empty state, editing/detail links, assessment prefill and guest-to-registration continuity. Existing authentication and admin tests remain intact.

Browser checks used the project's pinned Playwright packages and installed isolated system Chrome. They tested 1280px desktop and 390px mobile, no horizontal overflow, guest/citizen profile → PostgreSQL results → detail → prefilled assessment → result → recommendations → edit, direct `/schemes` saved-profile resolution, consent-based encrypted save, dashboard reuse and logout clearing. The existing manual explorer, unsupported assessment state, saved historical replay and authorization checks also passed. Guest tests observed no runtime page errors or browser storage entries.

Repeated registration QA reached the live application's existing five-per-hour throttle. It was **not disabled, deleted or bypassed**. Final citizen browser checks used an isolated Compose test network, a tmpfs PostgreSQL database with generated credentials, and the same application source/pinned images at localhost:3100. Test-account cleanup used normal authentication, CSRF and current-password deletion. This temporary stack was stopped after verification; the main six-service stack remains at localhost:3000/8000. No production deployment or real Gemini execution is claimed.

Screenshots show only sample public inputs:

- [Homepage, desktop](verification/profile-first/home-desktop.png)
- [Personalized results, desktop](verification/profile-first/results-desktop.png)
- [Personalized results, mobile](verification/profile-first/results-mobile.png)

## Run and test

From the repository root, with the existing `.env` and encryption key retained:

```bash
docker compose up --build -d --wait --wait-timeout 120
docker compose ps
docker compose exec api alembic current
docker compose exec api alembic check
docker compose exec api python -m tests.run
docker compose exec api ruff check app tests
docker compose exec api mypy app --cache-dir /tmp/recommendation-mypy
docker compose exec frontend npm run typecheck
docker compose exec frontend npm test
docker compose exec frontend npm run lint
```

Open http://localhost:3000 and select **Find My Schemes**. Manual exploration: http://localhost:3000/schemes/all. Backend documentation: http://localhost:8000/docs. The existing insert-only seed remains `docker compose exec api python -m app.seed`; this feature requires neither reseeding nor migrations.

On a host with frontend dependencies and Playwright Chromium installed, run `cd frontend && npm run e2e`. Install its test browser with `npx playwright install chromium` when available. The executed local runs copied the pinned runner packages to `/tmp` to use installed Chrome because the container lacked browser runtime packages. Fresh isolated databases are recommended for repeated registration runs; security quotas are intentionally preserved. For production builds, use the existing private production environment: `docker compose --env-file .env.production -f docker-compose.production.yml build api frontend`. Building alone does not deploy anything.

## Limitations

- Relevance is a transparent category heuristic, not semantic understanding of every target group. Catalog metadata may describe institutional as well as individual assistance; inspect official guidance. Fine-grained government eligibility stays unknown without approved rules.
- No government policy is currently approved in the live database. Existing illustrative templates are labeled estimates and cannot be saved/published as government policy assessments. The private approved-policy history/reassessment behavior remains unchanged.
- Many schemes have unverified state coverage, benefits, enrollment status or deadlines. Discovery retains these records and exposes uncertainty rather than inventing restrictions.
- No new live AI, RAG, policy-monitoring or production deployment validation was performed. Existing mocked AI/monitoring regression tests passed. Matching calls no AI service.
- Guest data is lost on reload or leaving the app. Saving requires an authenticated citizen's explicit consent. No recently viewed tracking, analytics, Aadhaar collection or additional storage service was added.
- Matching scans the current small catalog and loads only applicable approved programs for detailed checks. Large catalogs with many approved versions may need batched program loading after measurement.
- Shared-proxy rate quotas and the existing registration throttle limit repeated tests; do not weaken them for demonstrations.

## Created and modified files for this redesign

Created:

- `backend/app/api/v1/recommendations.py`
- `backend/app/schemas/recommendations.py`
- `backend/app/services/recommendations.py`
- `backend/tests/test_recommendations.py`
- `frontend/src/app/find-schemes/page.tsx`
- `frontend/src/app/schemes/recommended/page.tsx`
- `frontend/src/app/schemes/all/page.tsx`
- `frontend/src/components/discovery-context.tsx`
- `frontend/src/components/discovery-form.tsx`
- `frontend/src/components/recommendations.tsx`
- `frontend/src/lib/recommendations.ts`
- `frontend/tests/recommendations.test.tsx`
- `frontend/e2e/recommendations.spec.ts`
- `docs/profile-first-recommendations.md`
- `docs/verification/profile-first-recommendations-samples.json`
- `docs/verification/profile-first-verification.json`
- `docs/verification/profile-first/{home-desktop,results-desktop,results-mobile}.png`

Modified:

- `backend/app/api/v1/{router,citizen}.py`
- `backend/app/schemas/citizen.py`
- `backend/app/services/citizen.py`
- `backend/app/main.py`
- `backend/tests/test_citizen.py`
- `frontend/src/app/{page,layout}.tsx`
- `frontend/src/app/globals.css`
- `frontend/src/app/schemes/page.tsx`
- `frontend/src/app/schemes/[id]/page.tsx`
- `frontend/src/app/eligibility/report/page.tsx`
- `frontend/src/app/dashboard/schemes/page.tsx`
- `frontend/src/app/api/v1/[...path]/route.ts`
- `frontend/src/components/{header,questionnaire,report-context}.tsx`
- `frontend/src/components/citizen/{dashboard,profile,auth,session,settings,assessments}.tsx`
- `frontend/src/lib/citizen.ts`
- `frontend/tests/production-boundaries.test.ts`
- `frontend/e2e/citizen.spec.ts`
- `README.md`, `docs/{api,architecture,database,final-project-report}.md`

Pre-existing uncommitted assessment changes were retained. SQLAlchemy models, existing migrations, datasets, Compose services and historical report contents were not rewritten.

Suggested commit message: `feat: add profile-first scheme discovery and explainable recommendations`
