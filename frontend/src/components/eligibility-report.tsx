import Link from "next/link";
import {
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  CalendarDays,
  CheckCircle2,
  CircleHelp,
  ExternalLink,
  FileText,
  Info,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import type { EligibilityReport, Result, Trace } from "@/lib/types";
import { formatDate } from "@/lib/api";
import { categoryLabel } from "@/lib/catalog";
import { assessmentLabels, criteriaText, schemeName } from "@/lib/presentation";
import { ProjectDisclaimer } from "./ui";
const statuses = {
  PASS: {
    label: "Criteria matched",
    icon: CheckCircle2,
    className: "result-pass",
  },
  FAIL: {
    label: "Criteria not matched",
    icon: XCircle,
    className: "result-fail",
  },
  UNKNOWN: {
    label: "Additional information required",
    icon: CircleHelp,
    className: "result-unknown",
  },
};
function ReasonTree({ trace, legacy }: { trace: Trace; legacy: boolean }) {
  const status = statuses[trace.result];
  const Icon = status.icon;
  return (
    <li>
      <div className="reason-tree-node">
        <Icon size={15} className={status.className} />
        <div>
          <strong>{criteriaText(trace.label, legacy)}</strong>
          <p>{criteriaText(trace.explanation, legacy)}</p>
        </div>
      </div>
      {trace.children.length > 0 && (
        <ul>
          {trace.children.map((child) => (
            <ReasonTree key={child.key} trace={child} legacy={legacy} />
          ))}
        </ul>
      )}
    </li>
  );
}
function RequirementDecision({
  requirement,
  note,
  showEvidence,
  legacy,
}: {
  requirement: Trace;
  note?: string;
  showEvidence: boolean;
  legacy: boolean;
}) {
  const status = statuses[requirement.result];
  const Icon = status.icon;
  return (
    <article className="decision-card">
      <div className="decision-heading">
        <span className={`decision-icon ${status.className}`}>
          <Icon size={20} />
        </span>
        <div>
          <h3>{criteriaText(requirement.label, legacy)}</h3>
          <p>{note || criteriaText(requirement.explanation, legacy)}</p>
        </div>
        <span className={`decision-label ${status.className}`}>
          {status.label}
        </span>
      </div>
      <details>
        <summary>
          {showEvidence ? "View reasoning & evidence" : "View reasoning"}
        </summary>
        <div className="decision-details">
          <ul className="reason-tree">
            <ReasonTree trace={requirement} legacy={legacy} />
          </ul>
          {showEvidence &&
            requirement.evidence.map((evidence) => (
              <div className="evidence-quote" key={evidence.id}>
                <span className="eyebrow">
                  Policy evidence · {evidence.locator}
                </span>
                <p>{evidence.excerpt}</p>
                <a
                  href={evidence.url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {evidence.source_title} <ExternalLink size={13} />
                </a>
              </div>
            ))}
        </div>
      </details>
    </article>
  );
}
function detailValue(value: string | number | boolean | null): string {
  return value === null
    ? "Not provided"
    : typeof value === "boolean"
      ? value
        ? "Yes"
        : "No"
      : typeof value === "number"
        ? value.toLocaleString("en-IN")
        : value.replaceAll("_", " ");
}
export function EligibilityReportView({
  report,
  saved = false,
}: {
  report: EligibilityReport;
  saved?: boolean;
}) {
  const status = statuses[report.result];
  const Icon = status.icon;
  const illustrative =
    report.assessment_mode === "ILLUSTRATIVE" || report.is_demo;
  const approved = !!report.rule_set && !illustrative;
  const name = schemeName(report.scheme_name, report.is_demo);
  const overall = illustrative
    ? assessmentLabels[report.result]
    : report.assessment;
  return (
    <>
      <Link
        className="back-link"
        href={`/eligibility?scheme=${report.scheme_id}`}
      >
        <ArrowLeft size={16} />
        Start a new check
      </Link>
      <div className="page-heading report-page-heading">
        <span className="eyebrow">
          Assessment Result
          {report.category ? ` · ${categoryLabel(report.category)}` : ""}
        </span>
        <h1>Your assessment, explained.</h1>
        <p>{name}</p>
        <ProjectDisclaimer />
      </div>
      {report.policy_currency === "POTENTIALLY_OUTDATED" && (
        <div className="notice" role="status">
          <p>
            Policy currency warning: a monitored source changed or could not be
            verified. Check current official guidance before applying.
          </p>
        </div>
      )}
      <div className="report-layout">
        <div>
          <div className="assessment-basis">
            <span className="eyebrow">
              {illustrative
                ? "Illustrative assessment"
                : approved
                  ? "Reviewed policy assessment"
                  : "Assessment unavailable"}
            </span>
            <p>
              {illustrative
                ? "This estimate uses project-authored assessment criteria. Official scheme sources do not verify these criteria."
                : approved
                  ? "Conditions are evaluated against the recorded approved policy version. Evidence is attached to the supported conditions."
                  : "A suitable assessment template or applicable reviewed policy is not available for this scheme."}
            </p>
          </div>
          <section className={`assessment-panel ${status.className}`}>
            <Icon size={32} />
            <div>
              <span className="eyebrow">Overall assessment</span>
              <h2>{overall}</h2>
              <p>
                {report.reason === "NO_APPROVED_RULE_SET"
                  ? "No assessment can be produced from scheme information alone."
                  : report.result === "PASS"
                    ? "Your provided details match the assessment criteria. This does not guarantee government eligibility, funding or approval."
                    : report.result === "FAIL"
                      ? "One or more criteria do not match your provided details. Review the breakdown below."
                      : "Some required information is missing. The report shows what is needed to resolve the remaining criteria."}
              </p>
            </div>
          </section>
          <div className="result-summary">
            {(["PASS", "FAIL", "UNKNOWN"] as Result[]).map((result) => {
              const item = statuses[result];
              const ItemIcon = item.icon;
              return (
                <div key={result}>
                  <ItemIcon size={19} className={item.className} />
                  <strong>
                    {
                      report.requirements.filter(
                        (requirement) => requirement.result === result,
                      ).length
                    }
                  </strong>
                  <span>{item.label}</span>
                </div>
              );
            })}
          </div>
          {!!report.applicant_details?.length && (
            <section className="applicant-summary">
              <span className="eyebrow">Your details</span>
              <h2>Details used in this assessment</h2>
              <dl className="applicant-grid">
                {report.applicant_details.map((field) => (
                  <div key={field.key}>
                    <dt>{field.label}</dt>
                    <dd>{detailValue(field.value)}</dd>
                  </div>
                ))}
              </dl>
            </section>
          )}
          {report.missing_fields.length > 0 && (
            <section className="missing-panel">
              <CircleHelp size={22} />
              <div>
                <h2>Additional information required</h2>
                <p>
                  These unanswered details are needed to resolve the remaining
                  criteria.
                </p>
                <ul>
                  {report.missing_fields.map((field) => (
                    <li key={field.key}>{field.label}</li>
                  ))}
                </ul>
              </div>
            </section>
          )}
          {!!report.requirements.length && (
            <div className="section-heading compact">
              <div>
                <span className="eyebrow">One criterion at a time</span>
                <h2>The reasoning behind the result.</h2>
              </div>
            </div>
          )}
          <div className="decisions-list">
            {report.requirements.map((requirement) => (
              <RequirementDecision
                key={requirement.key}
                requirement={requirement}
                note={report.criteria_notes?.[requirement.key]}
                showEvidence={approved}
                legacy={report.is_demo}
              />
            ))}
          </div>
          <div className="notice mt-6">
            <Info size={19} className="shrink-0" />
            <p>
              {saved
                ? "This saved assessment retains its original version and result. Later policy changes do not overwrite it."
                : "This assessment is kept only in this browser page’s memory. Refreshing clears the report; it is not saved to your account."}
            </p>
          </div>
        </div>
        <aside>
          <div className="aside-card report-aside">
            <span className="aside-icon">
              <FileText size={26} />
            </span>
            <h2>The criteria behind this assessment.</h2>
            <dl className="report-facts">
              <div>
                <dt>
                  <BookOpen size={15} />
                  {illustrative ? "Criteria version" : "Policy version"}
                </dt>
                <dd>
                  {report.template
                    ? `${report.template.title} · Version ${report.template.version}`
                    : report.rule_set
                      ? `Version ${report.rule_set.version_number}`
                      : "No criteria evaluated"}
                </dd>
              </div>
              <div>
                <dt>
                  <ShieldCheck size={15} />
                  Assessment basis
                </dt>
                <dd>
                  {illustrative
                    ? "Project-authored illustration"
                    : approved
                      ? "Human-reviewed policy rules"
                      : "Not supported"}
                </dd>
              </div>
              <div>
                <dt>
                  <CalendarDays size={15} />
                  Assessment date
                </dt>
                <dd>{formatDate(report.assessed_on)}</dd>
              </div>
              <div>
                <dt>Assessment timestamp (IST)</dt>
                <dd>
                  {new Date(report.evaluated_at).toLocaleString("en-IN", {
                    timeZone: "Asia/Kolkata",
                  })}
                </dd>
              </div>
            </dl>
            {approved && report.rule_set && (
              <p className="small-note">{report.rule_set.scope_note}</p>
            )}
            {report.template && (
              <p className="small-note">
                The criteria version identifies this category template, not a
                government policy version.
              </p>
            )}
            {report.official_source_url && (
              <>
                <div className="aside-divider" />
                <h3>About this scheme</h3>
                <p className="small-note">
                  {illustrative
                    ? "This official reference identifies the scheme. It is not supporting evidence for the illustrative criteria above."
                    : "Consult the official source for current guidance."}
                </p>
                <a
                  className="text-link mt-4"
                  href={report.official_source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Visit official scheme source <ArrowUpRight size={15} />
                </a>
              </>
            )}
            {approved && report.official_application_url && (
              <a
                className="button button-primary mt-6"
                href={report.official_application_url}
                target="_blank"
                rel="noopener noreferrer"
              >
                Official application portal <ArrowUpRight size={16} />
              </a>
            )}
            <div className="aside-divider" />
            <Link className="text-link" href="/eligibility">
              Check another scheme <ArrowRight size={15} />
            </Link>
            <Link className="text-link mt-4" href="/schemes">
              Explore government sources <ArrowUpRight size={15} />
            </Link>
          </div>
        </aside>
      </div>
    </>
  );
}
