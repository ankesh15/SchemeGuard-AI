import { RecommendationReason } from "@/components/recommendations";
import { PolicyEvidence } from "@/components/policy-evidence";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import {
  ArrowLeft,
  ArrowUpRight,
  BookOpen,
  CalendarDays,
  Check,
  ExternalLink,
  FileText,
  Landmark,
  MapPin,
  ShieldCheck,
} from "lucide-react";
import { apiFetch, ApiError, formatDate } from "@/lib/api";
import type { AssessmentRequirements, SchemeDetail } from "@/lib/types";
import { categoryLabel } from "@/lib/catalog";
import { ActionLink, Badge, ProjectDisclaimer } from "@/components/ui";
export const dynamic = "force-dynamic";
export default async function SchemeDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let scheme: SchemeDetail;
  let requirements: AssessmentRequirements;
  try {
    [scheme, requirements] = await Promise.all([
      apiFetch<SchemeDetail>(`/api/v1/schemes/${encodeURIComponent(id)}`),
      apiFetch<AssessmentRequirements>(
        `/api/v1/schemes/${encodeURIComponent(id)}/assessment-requirements`,
      ),
    ]);
  } catch (error) {
    if (error instanceof ApiError && [404, 422].includes(error.status))
      notFound();
    throw error;
  }
  if (scheme.is_demo) redirect("/eligibility");
  const illustrative = requirements.assessment_mode === "ILLUSTRATIVE";
  const approved = requirements.assessment_mode === "APPROVED_POLICY";
  return (
    <div className="container page-shell">
      <Link className="back-link" href="/schemes">
        <ArrowLeft size={16} />
        Your scheme discovery
      </Link>
      <div className="detail-heading">
        <Badge />
        <h1>{scheme.name}</h1>
        <p>
          {scheme.department ||
            scheme.ministry ||
            "Administering department not verified"}
        </p>
      </div>
      <RecommendationReason schemeId={scheme.id} />
      <div className="detail-layout">
        <div>
          <nav className="section-tabs" aria-label="Scheme sections">
            <a href="#overview">Overview</a>
            <a href="#requirements">Assessment criteria</a>
            <a href="#sources">Sources</a>
          </nav>
          <section id="overview" className="detail-section">
            <span className="eyebrow">The starting point</span>
            <h2>About this scheme</h2>
            <p>{scheme.description}</p>
            <div className="facts-grid">
              <div>
                <Landmark size={18} />
                <span>Administering body</span>
                <strong>
                  {scheme.department || scheme.ministry || "Not verified"}
                </strong>
              </div>
              <div>
                <MapPin size={18} />
                <span>Geographic applicability</span>
                <strong>
                  {scheme.applicability === "national"
                    ? "National coverage"
                    : scheme.applicable_states?.join(", ") || "Not verified"}
                </strong>
              </div>
              <div>
                <CalendarDays size={18} />
                <span>Metadata checked</span>
                <strong>
                  {scheme.verified_on
                    ? formatDate(scheme.verified_on)
                    : "Unknown"}
                </strong>
              </div>
              <div>
                <BookOpen size={18} />
                <span>Category</span>
                <strong>{categoryLabel(scheme.category)}</strong>
              </div>
            </div>
          </section>
          <section id="requirements" className="detail-section">
            <span className="eyebrow">Know what’s being checked</span>
            <h2>Assessment criteria, with context.</h2>
            {requirements.available ? (
              <>
                <div className="assessment-basis">
                  <span className="eyebrow">
                    {illustrative
                      ? "Illustrative assessment"
                      : "Reviewed policy assessment"}
                  </span>
                  <p>
                    {illustrative
                      ? "The following criteria are project-authored examples for this category. They are not verified government requirements."
                      : "These conditions come from the applicable approved policy version. Read their evidence for context."}
                  </p>
                </div>
                <ul className="requirement-list">
                  {requirements.requirements.map((item) => (
                    <li key={item.key}>
                      <span>
                        <Check size={16} />
                      </span>
                      <div>
                        <strong>{item.label}</strong>
                        <small>
                          {requirements.criteria_notes[item.key] ||
                            item.evidence[0]?.locator}
                        </small>
                      </div>
                    </li>
                  ))}
                </ul>
              </>
            ) : (
              <div className="notice">
                <FileText size={20} />
                <p>
                  Detailed assessment criteria are not yet available for this
                  scheme. You can still explore the official scheme information.
                </p>
              </div>
            )}
          </section>
          <PolicyEvidence schemeId={scheme.id} available={approved} />
          <section id="sources" className="detail-section">
            <span className="eyebrow">Follow the source</span>
            <h2>Official scheme references</h2>
            {illustrative && (
              <p className="small-note">
                These references establish scheme information. They are not
                evidence for the illustrative assessment criteria above.
              </p>
            )}
            <div className="source-list">
              {scheme.sources.map((source) => (
                <article key={source.id} className="source-card">
                  <FileText size={22} />
                  <div>
                    <h3>{source.title}</h3>
                    <p>{source.publisher}</p>
                    <p className="source-notes">{source.verification_notes}</p>
                    <a
                      className="text-link"
                      href={source.url}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      Visit official source
                      <ArrowUpRight size={15} />
                    </a>
                  </div>
                </article>
              ))}
            </div>
          </section>
        </div>
        <aside className="detail-aside">
          <div className="aside-card">
            <span className="aside-icon">
              <ShieldCheck size={28} />
            </span>
            <h2>Understand where you stand.</h2>
            <p>
              {illustrative
                ? "Add your details for an illustrative, category-based assessment with a clear explanation of each criterion."
                : approved
                  ? "Compare your details with reviewed conditions and explore their source evidence."
                  : "An assessment is not available here yet. Explore another scheme or consult the official source."}
            </p>
            <ActionLink
              href={
                requirements.available
                  ? `/eligibility?scheme=${scheme.id}`
                  : "/eligibility"
              }
            >
              {requirements.available
                ? "Check Eligibility"
                : "Choose another scheme"}
            </ActionLink>
            {approved && (
              <ActionLink
                href={`/dashboard/assessments/new?scheme=${scheme.id}`}
              >
                Save a private assessment
              </ActionLink>
            )}
            {scheme.policy_currency === "POTENTIALLY_OUTDATED" && (
              <p role="status" className="notice">
                The source needs verification. Review current official guidance
                before applying.
              </p>
            )}
            <div className="aside-divider" />
            <p className="small-note">
              {requirements.template
                ? `${requirements.template.title} · Criteria version ${requirements.template.version}`
                : requirements.rule_set
                  ? `Reviewed policy version ${requirements.rule_set.version_number}`
                  : "Assessment criteria unavailable"}
            </p>
            <ProjectDisclaimer />
            {requirements.official_application_url && (
              <a
                className="text-link mt-5"
                href={requirements.official_application_url}
                target="_blank"
                rel="noopener noreferrer"
              >
                Official application portal <ExternalLink size={14} />
              </a>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
