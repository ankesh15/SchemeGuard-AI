export interface AdminSession {
  user_id: string;
  username: string;
  role: string;
  csrf_token: string;
  expires_at: string;
}
export interface AdminOverview {
  documents: number;
  pending_candidates: number;
  pending_reviews: number;
  workflows: number;
  failed_jobs: number;
  gemini_configured: boolean;
  gemini_model: string;
  pdf_max_bytes: number;
  pdf_max_pages: number;
  notice: string;
}
export interface ApprovedSource {
  source_id: string;
  scheme_id: string;
  scheme_name: string;
  url: string;
  title: string;
  publisher: string;
  approved_at: string;
  revoked_at: string | null;
}
export interface ProcessingJob {
  id: string;
  document_version_id: string;
  status: string;
  provider: string;
  model: string | null;
  input_chunk_count: number;
  candidate_count: number;
  started_at: string;
  finished_at: string | null;
  errors?: { code: string; message: string; page_number: number | null }[];
}
export interface IngestedDocument {
  id: string;
  scheme_id: string;
  scheme_name: string;
  source_id: string;
  source_url: string;
  original_filename: string;
  checksum: string;
  file_size: number;
  page_count: number;
  version_number: number;
  retrieved_at: string;
  publication_date: string | null;
  processing_status: string;
  acquisition_method: string;
  pdf_metadata: Record<string, string>;
  jobs?: ProcessingJob[];
  pages?: { page_number: number; issues: string[] }[];
}
export interface ParsedPage {
  extraction_method: string;
  document_version_id: string;
  page_number: number;
  text_content: string;
  blocks: {
    section_identifier: string;
    text: string;
    extraction_method: string;
    heading: string | null;
    bbox: number[];
    kind: string;
  }[];
  issues: string[];
}
export interface Candidate {
  id: string;
  document_version_id: string;
  condition_identifier: string;
  label: string;
  logical_relationship: string;
  review_status: string;
  validation_status: string;
  validation_issues: string[];
  payload: {
    root: string | null;
    nodes: {
      key: string;
      kind: string;
      field: string | null;
      operator: string | null;
      expected_value: unknown;
      units: string | null;
      children: string[];
    }[];
    extraction_uncertainty: string[];
  };
  mapped_expression: unknown;
  evidence: { node_key: string; page_number: number; excerpt: string }[];
}
export interface ResultPage<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}
export class AdminError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "AdminError";
  }
}
export async function adminFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(`/api/admin/${path}`, {
    ...options,
    credentials: "same-origin",
    cache: "no-store",
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new AdminError(
      response.status,
      response.status === 401
        ? "Your administrator session has expired. Sign in again."
        : body.error?.message ||
            "The administrator service is unavailable. Please try again.",
    );
  }
  return response.status === 204
    ? (undefined as T)
    : (response.json() as Promise<T>);
}
export function adminJSON(body: unknown, csrf?: string): RequestInit {
  return {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(csrf ? { "X-CSRF-Token": csrf } : {}),
    },
    body: JSON.stringify(body),
  };
}
