import Link from "next/link";
import { notFound } from "next/navigation";
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
import type { Requirements, SchemeDetail } from "@/lib/types";
import { ActionLink, Badge, DemoNotice } from "@/components/ui";

export const dynamic = "force-dynamic";
export default async function SchemeDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  let scheme: SchemeDetail;
  let requirements: Requirements;
  try {
    [scheme, requirements] = await Promise.all([
      apiFetch<SchemeDetail>(`/api/v1/schemes/${encodeURIComponent(id)}`),
      apiFetch<Requirements>(
        `/api/v1/schemes/${encodeURIComponent(id)}/requirements`,
      ),
    ]);
  } catch (error) {
    if (error instanceof ApiError && [404, 422].includes(error.status))
      notFound();
    throw error;
  }
  return (
    <div className="container page-shell">
      <Link className="back-link" href="/schemes">
        <ArrowLeft size={16} />
        All scholarships
      </Link>
      <div className="detail-heading">
        <Badge demo={scheme.is_demo} />
        <h1>{scheme.name}</h1>
        <p>
          {scheme.department || "An authored SchemeGuard development example"}
        </p>
      </div>
      {scheme.is_demo && <DemoNotice />}
      <div className="detail-layout">
        <div>
          <nav className="section-tabs" aria-label="Scheme sections">
            <a href="#overview">Overview</a>
            <a href="#requirements">Requirements</a>
            <a href="#sources">Evidence & sources</a>
          </nav>
          <section id="overview" className="detail-section">
            <span className="eyebrow">The starting point</span>
            <h2>About this scholarship</h2>
            <p>{scheme.description}</p>
            <div className="facts-grid">
              <div>
                <Landmark size={18} />
                <span>Administering body</span>
                <strong>
                  {scheme.department || "Fictional development fixture"}
                </strong>
              </div>
              <div>
                <MapPin size={18} />
                <span>Geographic applicability</span>
                <strong>
                  {scheme.applicable_states?.join(", ") || "Not verified"}
                </strong>
              </div>
              <div>
                <CalendarDays size={18} />
                <span>
                  {scheme.is_demo ? "Policy type" : "Metadata checked"}
                </span>
                <strong>
                  {scheme.is_demo
                    ? "Authored test policy"
                    : scheme.verified_on
                      ? formatDate(scheme.verified_on)
                      : "Unknown"}
                </strong>
              </div>
              <div>
                <BookOpen size={18} />
                <span>Category</span>
                <strong>Scholarship</strong>
              </div>
            </div>
          </section>
          <section id="requirements" className="detail-section">
            <span className="eyebrow">Know what’s being checked</span>
            <h2>Requirements, with context.</h2>
            {requirements.available ? (
              <>
                <p>
                  These requirements belong only to the fictional test policy.
                  View the full policy to see every invented threshold and
                  condition.
                </p>
                <ul className="requirement-list">
                  {requirements.requirements.map((item) => (
                    <li key={item.key}>
                      <span>
                        <Check size={16} />
                      </span>
                      <div>
                        <strong>{item.label}</strong>
                        <small>{item.evidence[0]?.locator}</small>
                      </div>
                    </li>
                  ))}
                </ul>
                <a
                  className="text-link"
                  href="/policies/demo-policy-v1.md"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Read the fictional policy <ExternalLink size={15} />
                </a>
              </>
            ) : (
              <div className="notice">
                <FileText size={20} />
                <p>
                  <strong>Rules are awaiting verified review.</strong> The
                  government metadata is available, but no approved eligibility
                  rule set is effective for this scheme. We won’t infer a
                  decision from incomplete information.
                </p>
              </div>
            )}
          </section>
          <section id="sources" className="detail-section">
            <span className="eyebrow">Follow the evidence</span>
            <h2>
              {scheme.is_demo
                ? "The authored policy"
                : "Official source references"}
            </h2>
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
                      href={
                        scheme.is_demo
                          ? "/policies/demo-policy-v1.md"
                          : source.url
                      }
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      {scheme.is_demo
                        ? "Read fictional policy"
                        : "Visit official source"}
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
              {requirements.available
                ? "Try a synthetic profile and see which fictional conditions are satisfied, unmet, or unknown."
                : "A trustworthy assessment needs approved rules. Try the fictional example to see how the assessment works."}
            </p>
            <ActionLink
              href={
                requirements.available
                  ? `/eligibility?scheme=${scheme.id}`
                  : "/eligibility"
              }
            >
              {requirements.available
                ? "Check the demo conditions"
                : "Try the fictional demo"}
            </ActionLink>
            <div className="aside-divider" />
            <p className="small-note">
              {requirements.rule_set
                ? `Policy version ${requirements.rule_set.version_number} · Synthetic fixture approval`
                : "No approved eligibility rules available"}
            </p>
            <p className="small-note">
              An assessment is not official approval or an application
              submission.
            </p>
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
