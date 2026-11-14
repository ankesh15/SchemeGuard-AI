# API design and route inventory

Generated from the running FastAPI OpenAPI schema after Phase 7 changes. Backend base /api/v1; /health and /ready are unversioned. Private writes require the existing cookie, CSRF token and exact allowed Origin. Registration cannot choose an admin role. UUIDs, body types, query bounds and response schemas are available at /docs. Standard errors include request_id and sanitized error details. Public source-grounding/assessment endpoints accept synthetic information; citizen persistence is separate and owner-scoped. Browser routes proxy to the fixed internal API; public proxy routes never forward cookies.

| Method | Path | Access |
|---|---|---|
| GET | `/health` | Public |
| GET | `/ready` | Public |
| POST | `/api/v1/recommendations` | Public; bounded transient profile body, no persistence |
| GET | `/api/v1/recommendations/options` | Public; catalog-derived interests/categories and states |
| POST | `/api/v1/me/recommendations` | Citizen; own encrypted saved profile, CSRF/Origin required |
| GET | `/api/v1/schemes` | Public |
| GET | `/api/v1/schemes/filters` | Public |
| GET | `/api/v1/schemes/{scheme_id}` | Public |
| POST | `/api/v1/eligibility/check` | Public / synthetic inputs only for assessment |
| GET | `/api/v1/schemes/{scheme_id}/requirements` | Public |
| GET | `/api/v1/schemes/{scheme_id}/assessment-requirements` | Public; explicitly identified assessment basis |
| POST | `/api/v1/assessment/check` | Public; bounded, non-persisted demonstration/approved assessment |
| POST | `/api/v1/admin/auth/login` | Public; admin credentials + allowed Origin |
| GET | `/api/v1/admin/auth/session` | Administrator |
| POST | `/api/v1/admin/auth/logout` | Administrator |
| GET | `/api/v1/admin/overview` | Administrator |
| POST | `/api/v1/admin/sources` | Administrator |
| GET | `/api/v1/admin/sources` | Administrator |
| POST | `/api/v1/admin/sources/{identifier}/revoke` | Administrator |
| POST | `/api/v1/admin/documents` | Administrator |
| GET | `/api/v1/admin/documents` | Administrator |
| GET | `/api/v1/admin/documents/{identifier}` | Administrator |
| GET | `/api/v1/admin/documents/{identifier}/original` | Administrator |
| GET | `/api/v1/admin/documents/{identifier}/pages/{page_number}` | Administrator |
| POST | `/api/v1/admin/documents/{identifier}/extract` | Administrator |
| GET | `/api/v1/admin/extractions/{identifier}` | Administrator |
| GET | `/api/v1/admin/extractions/{identifier}/candidates` | Administrator |
| GET | `/api/v1/admin/audit` | Administrator |
| POST | `/api/v1/admin/workflows` | Administrator |
| GET | `/api/v1/admin/workflows` | Administrator |
| GET | `/api/v1/admin/workflows/{identifier}` | Administrator |
| POST | `/api/v1/admin/workflows/{identifier}/resume` | Administrator |
| POST | `/api/v1/admin/workflows/{identifier}/cancel` | Administrator |
| GET | `/api/v1/admin/reviews` | Administrator |
| GET | `/api/v1/admin/reviews/{identifier}` | Administrator |
| POST | `/api/v1/admin/reviews/{identifier}/revisions` | Administrator |
| POST | `/api/v1/admin/reviews/{identifier}/approve` | Administrator |
| POST | `/api/v1/admin/reviews/{identifier}/reject` | Administrator |
| POST | `/api/v1/admin/documents/{identifier}/index` | Administrator |
| POST | `/api/v1/eligibility/explain` | Public / synthetic inputs only for assessment |
| GET | `/api/v1/schemes/{scheme_id}/rule-history` | Public |
| POST | `/api/v1/schemes/{scheme_id}/questions` | Public; bounded questions, approved evidence only |
| GET | `/api/v1/admin/monitors` | Administrator |
| POST | `/api/v1/admin/monitors` | Administrator |
| PATCH | `/api/v1/admin/monitors/{identifier}` | Administrator |
| POST | `/api/v1/admin/monitors/{identifier}/check` | Administrator |
| GET | `/api/v1/admin/monitoring-runs` | Administrator |
| GET | `/api/v1/admin/policy-changes` | Administrator |
| GET | `/api/v1/admin/policy-changes/{identifier}` | Administrator |
| POST | `/api/v1/admin/policy-changes/{identifier}/clarify` | Administrator |
| POST | `/api/v1/admin/policy-changes/{identifier}/approve` | Administrator |
| POST | `/api/v1/admin/policy-changes/{identifier}/reject` | Administrator |
| GET | `/api/v1/policy-updates` | Public |
| GET | `/api/v1/profiles/options` | Citizen |
| GET | `/api/v1/profiles/me` | Citizen |
| PUT | `/api/v1/profiles/me` | Citizen |
| DELETE | `/api/v1/profiles/me` | Citizen |
| POST | `/api/v1/assessments` | Citizen |
| GET | `/api/v1/assessments` | Citizen |
| GET | `/api/v1/assessments/{identifier}` | Citizen |
| POST | `/api/v1/assessments/{identifier}/reproduce` | Citizen |
| GET | `/api/v1/notification-preferences` | Citizen |
| PUT | `/api/v1/notification-preferences` | Citizen |
| GET | `/api/v1/notifications` | Citizen |
| POST | `/api/v1/notifications/read-all` | Citizen |
| POST | `/api/v1/notifications/{identifier}/read` | Citizen |
| GET | `/api/v1/dashboard` | Citizen |
| GET | `/api/v1/me/policy-updates` | Citizen |
| POST | `/api/v1/auth/register` | Public (Origin required for authentication writes) |
| POST | `/api/v1/auth/login` | Public (Origin required for authentication writes) |
| POST | `/api/v1/auth/logout` | Account |
| GET | `/api/v1/me` | Account |
| DELETE | `/api/v1/me` | Citizen + current password + deletion acknowledgement |
| PATCH | `/api/v1/me` | Citizen + current password |
| POST | `/api/v1/auth/password` | Citizen + current password |

Total documented operations: **72**. Existing API contracts are preserved; Phase 7 adds infrastructure/validation rather than new policy-decision endpoints.

## Opt-in project assessment API

The original `/eligibility/check`, `/eligibility/explain` and `/schemes/{id}/requirements` contracts remain strict: metadata alone still produces UNKNOWN, never a template result. `/schemes?is_demo=false` excludes legacy fixtures without changing the default API listing. Scheme responses now separately expose `assessment_available` and `assessment_mode`; `eligibility_available` still means approved rules, not template availability.

`GET /schemes/{id}/assessment-requirements` chooses `APPROVED_POLICY`, `ILLUSTRATIVE` or `UNSUPPORTED` on the server and returns typed fields, a sample profile, criteria notes and `criteria_token`. `POST /assessment/check` accepts `scheme_id`, `profile`, optional `assessed_on` and optional `criteria_token`. The UI always supplies the token; stale criteria return 409. Mode/template/approval cannot be selected by the caller. Unknown or malformed fields return 422 without echoing personal values.

Illustrative reports carry a project template version/fingerprint, `rule_set: null`, empty evidence at every trace node and `policy_currency: UNVERIFIED`. Official metadata links are separate references, not citations for those conditions. Only supplied questionnaire values are returned in the transient input summary; nothing is written to saved assessments, policies, extraction candidates or notification jobs. The hashed request-rate counter is the only request-management write. See demonstration-assessments.md.


## Profile-first recommendation contract

POST `/recommendations` accepts existing profile field names (`age_years`, `state`, `course_level`, `current_student`, `occupation`, `annual_family_income_inr`, `attributes`) and optional `employment_status`, `field_of_study`, and `interests`. All profile answers are optional. Interest identifiers are bounded and normalized; related catalog categories are grouped transparently. `page` starts at 1; `page_size` is 1–30; `category` is an exact catalog category and `sort_by` is `relevance` or `name`. Inputs belong in the JSON body, never query parameters.

Each item extends the existing SchemeRead contract with `relevance` (HIGH/POTENTIAL/MORE_INFORMATION), `matching_reasons`, `missing_information`, additive integer `ranking_points`/`ranking_factors` and nullable `approved_rule_version`. Points are ordering heuristics, not confidence or eligibility percentages. `eligibility_available` remains specific to approved policies; `assessment_mode` separately identifies APPROVED_POLICY, ILLUSTRATIVE or UNSUPPORTED.

The body does not accept another user's ID. POST `/me/recommendations` accepts only the paging/filter/sort fields and uses the authenticated citizen's own decrypted profile. Both paths and the dashboard call the same RecommendationService. The public path never forwards session cookies or writes profiles, reports, policy rows or notifications. All recommendation responses, including validation failures, use no-store; only hashed request-rate counters are updated. The public proxy limits bodies to 16 KB; Pydantic bounds fields/collections and the backend applies 120 requests per 900 seconds per direct peer (a shared proxy peer shares that quota). See [profile-first recommendations](profile-first-recommendations.md) for examples and limitations.
