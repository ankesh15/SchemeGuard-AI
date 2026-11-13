import { AdminError } from "./admin";
import type { EligibilityReport, Result } from "./types";
export interface CitizenSession {
  user_id: string;
  username: string;
  role: "citizen" | "admin";
  csrf_token: string;
  expires_at: string;
  password_reset_available?: boolean;
}
export interface ProfileData {
  state: string | null;
  age_years: number | null;
  annual_family_income_inr: number | null;
  course_level: string | null;
  current_student: boolean | null;
  occupation: string | null;
  attributes: Record<string, string | number | boolean | null>;
}
export interface ProfileRead {
  exists: boolean;
  profile: ProfileData;
  completeness: { completed: number; total: number; percent: number };
  updated_at: string | null;
  notice: string;
}
export interface SavedAssessment {
  id: string;
  scheme_id: string;
  scheme_name: string;
  result: Result;
  assessment: string;
  rule_set_id: string | null;
  rule_version: number | null;
  created_at: string;
  assessed_on: string;
  allow_reassessment: boolean;
  parent_id: string | null;
  policy_change_id: string | null;
  report?: EligibilityReport;
  impact?: Record<string, unknown> | null;
  current_policy_currency?: string;
}
export interface Notice {
  id: string;
  scheme_id: string;
  policy_change_id: string;
  assessment_id: string | null;
  notification_type: string;
  title: string;
  description: string;
  created_at: string;
  read_at: string | null;
}
export interface Preferences {
  in_app: boolean;
  automatic_reassessment: boolean;
  policy_updates: boolean;
}
export interface PolicyUpdate {
  id: string;
  scheme_id: string;
  classification: string;
  published_at: string;
  effective_from: string | null;
}
export async function citizenFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch(`/api/account/${path}`, {
    ...options,
    credentials: "same-origin",
    cache: "no-store",
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new AdminError(
      response.status,
      response.status === 401
        ? "Your session has expired. Sign in again."
        : body.error?.message ||
            "The account service is unavailable. Please retry.",
    );
  }
  return response.status === 204
    ? (undefined as T)
    : (response.json() as Promise<T>);
}
export const citizenJSON = (
  body: unknown,
  csrf?: string,
  method = "POST",
): RequestInit => ({
  method,
  headers: {
    "Content-Type": "application/json",
    ...(csrf ? { "X-CSRF-Token": csrf } : {}),
  },
  body: JSON.stringify(body),
});
