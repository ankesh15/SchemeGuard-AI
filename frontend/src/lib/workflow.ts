import type { IngestedDocument } from "./admin";
export interface Workflow {
  id: string;
  thread_id: string;
  graph_version: string;
  document_version_id: string;
  scheme_id: string;
  scheme_name: string;
  document_filename: string;
  status: string;
  stage: string;
  attempts: number;
  extraction_job_id: string | null;
  provider: string;
  model: string | null;
  review_id: string | null;
  published_rule_set_id: string | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  history?: {
    id: string;
    stage: string;
    event: string;
    details: Record<string, unknown>;
    created_at: string;
  }[];
}
export interface Review {
  id: string;
  status: string;
  workflow: Workflow;
  document: IngestedDocument;
  revision_number: number;
  proposal_sha256: string;
  draft: PolicyDraft;
  original_proposal: PolicyDraft;
  findings: {
    id: string;
    condition: string;
    code: string;
    message: string;
    severity: string;
  }[];
  required_finding_ids: string[];
  validation: {
    publishable: boolean;
    errors: string[];
    warnings: string[];
    overlapping_rule_sets: {
      id: string;
      version_number: number;
      title: string;
      effective_from: string;
      effective_to: string | null;
      scope_note: string;
    }[];
  };
  revision_history: {
    id: string;
    revision_number: number;
    actor_id: string | null;
    notes: string;
    created_at: string;
  }[];
  decision: {
    id: string;
    action: string;
    reviewer_id: string;
    notes: string;
    created_at: string;
  } | null;
}
export interface PolicyDraft {
  title: string;
  logical_operator: "and" | "or";
  effective_from: string | null;
  effective_to: string | null;
  effective_date_basis: string;
  effective_date_note: string;
  scope_note: string;
  applicability_note: string;
  conditions: {
    key: string;
    label: string;
    source_candidate_id: string | null;
    expression: Record<string, unknown> | null;
    evidence: { node_key: string; page_number: number; excerpt: string }[];
  }[];
  [key: string]: unknown;
}
export interface Citation {
  id: string;
  scheme_id: string;
  document_version_id: string;
  document_sha256: string;
  page_number: number | null;
  locator: string;
  excerpt: string;
  source_title: string;
  publisher: string;
  url: string;
}
export interface Explanation {
  result: string;
  assessment: string;
  summary: string;
  rule_version: number | null;
  mode: string;
  retrieval_mode: string;
  citations: Citation[];
}
