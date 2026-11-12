export type Result = "PASS" | "FAIL" | "UNKNOWN";
export interface Scheme {
  id: string;
  slug: string;
  name: string;
  description: string | null;
  ministry: string | null;
  department: string | null;
  category: string;
  is_demo: boolean;
  eligibility_available: boolean;
  status: string;
  applicability: string;
  applicable_states: string[] | null;
  official_source_url: string | null;
  verified_on: string | null;
  created_at: string;
  updated_at: string;
}
export interface Source {
  id: string;
  url: string;
  title: string;
  publisher: string;
  is_primary: boolean;
  supported_fields: string[];
  verification_notes: string;
  verified_on: string;
}
export interface SchemeDetail extends Scheme {
  sources: Source[];
}
export interface SchemePage {
  items: Scheme[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}
export interface ProfileField {
  key: string;
  label: string;
  value_type: "number" | "string" | "boolean" | "date";
  section: string;
  help_text: string;
  choices: { value: string; label: string }[];
  minimum: number | null;
  maximum: number | null;
  integer: boolean;
  visible_when: { field: string; equals: boolean } | null;
}
export interface Evidence {
  id: string;
  document_version_id: string;
  document_sha256: string;
  source_title: string;
  publisher: string;
  locator: string;
  excerpt: string;
  url: string;
  is_demo: boolean;
}
export interface RuleVersion {
  id: string;
  version_number: number;
  title: string;
  approval_status: "APPROVED";
  approval_basis: string;
  approved_at: string;
  effective_from: string;
  effective_to: string | null;
  source_document_version_id: string;
  source_document_sha256: string;
  scope_note: string;
}
export interface Requirement {
  key: string;
  label: string;
  evidence: Evidence[];
}
export interface Requirements {
  scheme_id: string;
  scheme_name: string;
  is_demo: boolean;
  available: boolean;
  rule_set: RuleVersion | null;
  fields: ProfileField[];
  requirements: Requirement[];
  notices: string[];
  official_application_url: string | null;
}
export interface Trace {
  key: string;
  label: string;
  kind: string;
  result: Result;
  explanation: string;
  missing_fields: string[];
  evidence: Evidence[];
  children: Trace[];
}
export interface EligibilityReport {
  scheme_id: string;
  scheme_name: string;
  is_demo: boolean;
  result: Result;
  assessment: string;
  reason: "EVALUATED" | "NO_APPROVED_RULE_SET";
  evaluated_at: string;
  assessed_on: string;
  rule_set: RuleVersion | null;
  requirements: Trace[];
  trace: Trace | null;
  missing_fields: { key: string; label: string }[];
  notices: string[];
  official_application_url: string | null;
}

export interface SchemeFilters {
  categories: string[];
  states: string[];
}
