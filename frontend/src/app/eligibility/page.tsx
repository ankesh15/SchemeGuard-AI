import { notFound, redirect } from "next/navigation";
import type { Metadata } from "next";
import { apiFetch, ApiError } from "@/lib/api";
import { categoryLabel } from "@/lib/catalog";
import type { AssessmentRequirements, SchemeDetail } from "@/lib/types";
import { Questionnaire } from "@/components/questionnaire";
import { Explorer } from "@/components/explorer";
import { ProjectDisclaimer } from "@/components/ui";
export const metadata: Metadata = { title: "Eligibility Assessment" };
export const dynamic = "force-dynamic";

export default async function EligibilityPage({
  searchParams,
}: {
  searchParams: Promise<{ scheme?: string }>;
}) {
  const { scheme } = await searchParams;
  if (!scheme)
    return (
      <div className="container page-shell">
        <div className="page-heading">
          <span className="eyebrow">Eligibility Assessment</span>
          <h1>Choose your starting point.</h1>
          <p>
            Find a government scheme, add your details, and understand the
            assessment criteria.
          </p>
          <ProjectDisclaimer />
        </div>
        <Explorer assessment />
      </div>
    );
  let selected: SchemeDetail;
  let requirements: AssessmentRequirements;
  try {
    [selected, requirements] = await Promise.all([
      apiFetch<SchemeDetail>(`/api/v1/schemes/${encodeURIComponent(scheme)}`),
      apiFetch<AssessmentRequirements>(
        `/api/v1/schemes/${encodeURIComponent(scheme)}/assessment-requirements`,
      ),
    ]);
  } catch (error) {
    if (error instanceof ApiError && [404, 422].includes(error.status))
      notFound();
    throw error;
  }
  if (selected.is_demo) redirect("/eligibility");
  return (
    <div className="container page-shell">
      <div className="page-heading">
        <span className="eyebrow">
          Eligibility Assessment · {categoryLabel(selected.category)}
        </span>
        <h1>{selected.name}</h1>
        <p>{selected.description}</p>
        <ProjectDisclaimer />
      </div>
      <Questionnaire
        key={`${selected.id}:${requirements.criteria_token}`}
        requirements={requirements}
      />
    </div>
  );
}
