// Presentation only. Historical fixture data remains unchanged in the backend.
export function schemeName(name: string, legacy = false): string {
  return legacy || name === "SchemeGuard Learning Scholarship (Fictional)"
    ? "SchemeGuard Learning Assessment"
    : name;
}

export function criteriaText(text: string, legacy = false): string {
  if (!legacy) return text;
  return text
    .replace(/fictional policy/gi, "assessment criteria")
    .replace(/fictional/gi, "illustrative")
    .replace(/synthetic/gi, "sample")
    .replace(/invented/gi, "illustrative");
}

export const assessmentLabels = {
  PASS: "Criteria matched",
  FAIL: "Criteria not matched",
  UNKNOWN: "Additional information required",
};
