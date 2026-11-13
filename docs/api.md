# API design and route inventory

Generated from the running FastAPI OpenAPI schema after Phase 7 changes. Backend base /api/v1; /health and /ready are unversioned. Private writes require the existing cookie, CSRF token and exact allowed Origin. Registration cannot choose an admin role. UUIDs, body types, query bounds and response schemas are available at /docs. Standard errors include request_id and sanitized error details. Public source-grounding/assessment endpoints accept synthetic information; citizen persistence is separate and owner-scoped. Browser routes proxy to the fixed internal API; public proxy routes never forward cookies.

| Method | Path | Access |
|---|---|---|
| GET | `/health` | Public |
| GET | `/ready` | Public |
| GET | `/api/v1/schemes` | Public |
| GET | `/api/v1/schemes/filters` | Public |
| GET | `/api/v1/schemes/{scheme_id}` | Public |
| POST | `/api/v1/eligibility/check` | Public / synthetic inputs only for assessment |
| GET | `/api/v1/schemes/{scheme_id}/requirements` | Public |
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

Total documented operations: **70**. Existing API contracts are preserved; Phase 7 adds infrastructure/validation rather than new policy-decision endpoints.
