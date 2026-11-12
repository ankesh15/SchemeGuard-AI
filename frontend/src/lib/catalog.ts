import { apiFetch } from "./api";
import type { Scheme, SchemePage } from "./types";

export function categoryLabel(value: string): string {
  if (value === "scholarship") return "Scholarships";
  return value
    .split(/[_-]/)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

// The selector offers effective approved policies only. Direct links to
// metadata-only schemes still show their honest unsupported state.
export async function approvedSchemeChoices(): Promise<Scheme[]> {
  const first = await apiFetch<SchemePage>(
    "/api/v1/schemes?eligibility_available=true&page_size=100",
  );
  const remaining = await Promise.all(
    Array.from({ length: Math.max(0, first.pages - 1) }, (_, index) =>
      apiFetch<SchemePage>(
        `/api/v1/schemes?eligibility_available=true&page_size=100&page=${index + 2}`,
      ),
    ),
  );
  return [...first.items, ...remaining.flatMap((page) => page.items)];
}
