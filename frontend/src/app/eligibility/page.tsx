import { notFound } from "next/navigation";
import type { Metadata } from "next";
import { apiFetch } from "@/lib/api";
import type { Requirements, SchemePage } from "@/lib/types";
import { Questionnaire } from "@/components/questionnaire";
export const metadata: Metadata = { title: "Eligibility questionnaire" };
export const dynamic = "force-dynamic";

export default async function EligibilityPage({
  searchParams,
}: {
  searchParams: Promise<{ scheme?: string }>;
}) {
  const { scheme } = await searchParams;
  const data = await apiFetch<SchemePage>("/api/v1/schemes?page_size=100");
  const selected = scheme
    ? data.items.find((item) => item.id === scheme)
    : data.items.find((item) => item.is_demo) || data.items[0];
  if (!selected) notFound();
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
        schemes={data.items}
      />
    </div>
  );
}
