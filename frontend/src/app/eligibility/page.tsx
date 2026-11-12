import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { apiFetch, ApiError } from "@/lib/api";
import type { Requirements, Scheme, SchemePage } from "@/lib/types";
import { approvedSchemeChoices } from "@/lib/catalog";
import { Questionnaire } from "@/components/questionnaire";
export const metadata: Metadata = { title: "Eligibility questionnaire" };
export const dynamic = "force-dynamic";

export default async function EligibilityPage({
  searchParams,
}: {
  searchParams: Promise<{ scheme?: string }>;
}) {
  const { scheme } = await searchParams;
  const choices = await approvedSchemeChoices();
  let selected: Scheme | undefined;
  if (scheme) {
    try {
      selected = await apiFetch<Scheme>(
        `/api/v1/schemes/${encodeURIComponent(scheme)}`,
      );
    } catch (error) {
      if (error instanceof ApiError && [404, 422].includes(error.status))
        notFound();
      throw error;
    }
  } else {
    selected = choices.find((item) => item.is_demo) || choices[0];
    if (!selected)
      selected = (await apiFetch<SchemePage>("/api/v1/schemes?page_size=1"))
        .items[0];
  }
  if (!selected) notFound();
  if (!choices.some((item) => item.id === selected.id)) choices.push(selected);
  const requirements = await apiFetch<Requirements>(
    `/api/v1/schemes/${selected.id}/requirements`,
  );
  return (
    <div className="container page-shell">
      <div className="page-heading">
        <span className="eyebrow">The eligibility check</span>
        <h1>Let’s make the requirements clear.</h1>
        <p>
          A few synthetic details. A transparent assessment. Every condition
          explained.
        </p>
      </div>
      <Questionnaire
        key={selected.id}
        requirements={requirements}
        schemes={choices}
      />
    </div>
  );
}
