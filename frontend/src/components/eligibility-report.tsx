"use client";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  CalendarDays,
  Check,
  CheckCircle2,
  CircleHelp,
  ExternalLink,
  FileText,
  Info,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import { formatDate } from "@/lib/api";
import type { EligibilityReport, Result, Trace } from "@/lib/types";
import { DemoNotice } from "./ui";

const statuses = {
  PASS: { label: "Satisfied", icon: CheckCircle2, className: "result-pass" },
  FAIL: { label: "Not satisfied", icon: XCircle, className: "result-fail" },
  UNKNOWN: { label: "Unknown", icon: CircleHelp, className: "result-unknown" },
};
function ReasonTree({ trace }: { trace: Trace }) {
  const status = statuses[trace.result];
  const Icon = status.icon;
  return (
    <li>
      <div className="reason-tree-node">
        <Icon size={15} className={status.className} />
        <div>
          <strong>{trace.label}</strong>
          <p>{trace.explanation}</p>
        </div>
      </div>
      {trace.children.length > 0 && (
        <ul>
          {trace.children.map((child) => (
            <ReasonTree key={child.key} trace={child} />
          ))}
        </ul>
      )}
    </li>
  );
}
function RequirementDecision({ requirement }: { requirement: Trace }) {
  const status = statuses[requirement.result];
  const Icon = status.icon;
  return (
    <article className="decision-card">
      <div className="decision-heading">
        <span className={`decision-icon ${status.className}`}>
          <Icon size={20} />
        </span>
        <div>
          <h3>{requirement.label}</h3>
          <p>{requirement.explanation}</p>
        </div>
        <span className={`decision-label ${status.className}`}>
          {status.label}
        </span>
      </div>
      <details>
        <summary>View reasoning & evidence</summary>
        <div className="decision-details">
          <ul className="reason-tree">
            <ReasonTree trace={requirement} />
          </ul>
          {requirement.evidence.map((evidence) => (
            <div className="evidence-quote" key={evidence.id}>
              <span className="eyebrow">
                {evidence.is_demo
                  ? "Fictional policy evidence"
                  : "Policy evidence"}{" "}
                · {evidence.locator}
              </span>
              <p>{evidence.excerpt}</p>
              <a href={evidence.url} target="_blank" rel="noopener noreferrer">
                {evidence.source_title} <ExternalLink size={13} />
              </a>
            </div>
          ))}
        </div>
      </details>
    </article>
  );
}

export function EligibilityReportView({
  report,
}: {
  report: EligibilityReport;
}) {
  const status = statuses[report.result];
  const Icon = status.icon;
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
        <span className="eyebrow">Your eligibility report</span>
        <h1>Your assessment, explained.</h1>
        <p>{report.scheme_name}</p>
      </div>
      {report.is_demo && <DemoNotice />}
      {report.policy_currency === "POTENTIALLY_OUTDATED" && (
        <div className="notice" role="status">
          <p>
            Policy currency warning: a monitored source changed or could not be
            verified. This assessment retains the last approved rules; check the
            latest official guidance.
          </p>
        </div>
      )}
      <div className="report-layout">
        <div>
          <section className={`assessment-panel ${status.className}`}>
            <Icon size={32} />
            <div>
              <span className="eyebrow">Overall assessment</span>
              <h2>{report.assessment}</h2>
              <p>
                {report.reason === "NO_APPROVED_RULE_SET"
                  ? "No effective approved policy is available. An assessment cannot be made from scheme metadata alone."
                  : report.result === "PASS"
                    ? "The declared synthetic profile satisfies the known conditions in this policy version. This is not an award or official approval."
                    : report.result === "FAIL"
                      ? "One or more known conditions are not satisfied. The breakdown below explains which requirements need attention."
                      : "Some required information is missing. The known conditions are assessed below, and unknown requirements stay unresolved."}
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
          {report.missing_fields.length > 0 && (
            <section className="missing-panel">
              <CircleHelp size={22} />
              <div>
                <h2>Here’s what’s still missing</h2>
                <p>
                  These unanswered details are needed to resolve the remaining
                  conditions.
                </p>
                <ul>
                  {report.missing_fields.map((field) => (
                    <li key={field.key}>{field.label}</li>
                  ))}
                </ul>
              </div>
            </section>
          )}
          <div className="section-heading compact">
            <div>
              <span className="eyebrow">One requirement at a time</span>
              <h2>The reasoning behind the result.</h2>
            </div>
          </div>
          <div className="decisions-list">
            {report.requirements.map((requirement) => (
              <RequirementDecision
                key={requirement.key}
                requirement={requirement}
              />
            ))}
          </div>
          <div className="notice mt-6">
            <Info size={19} className="shrink-0" />
            <p>
              {report.notices.find((notice) =>
                notice.startsWith("This is an assessment"),
              )}{" "}
              Your report exists only in this browser session’s memory and
              disappears on refresh.
            </p>
          </div>
        </div>
        <aside>
          <div className="aside-card report-aside">
            <span className="aside-icon">
              <FileText size={26} />
            </span>
            <h2>
              The policy behind
              <br />
              this assessment.
            </h2>
            <dl className="report-facts">
              <div>
                <dt>
                  <BookOpen size={15} />
                  Rule version
                </dt>
                <dd>
                  {report.rule_set
                    ? `Version ${report.rule_set.version_number}`
                    : "No version evaluated"}
                </dd>
              </div>
              <div>
                <dt>
                  <ShieldCheck size={15} />
                  Review basis
                </dt>
                <dd>
                  {report.rule_set?.approval_basis === "synthetic_fixture"
                    ? "Synthetic development fixture"
                    : report.rule_set
                      ? "Human-reviewed rules"
                      : "Awaiting approved rules"}
                </dd>
              </div>
              <div>
                <dt>
                  <CalendarDays size={15} />
                  Assessment date
                </dt>
                <dd>{formatDate(report.assessed_on)}</dd>
              </div>
            </dl>
            {report.rule_set && (
              <p className="small-note">{report.rule_set.scope_note}</p>
            )}
            {report.is_demo ? (
              <a
                className="button button-secondary mt-6"
                href="/policies/demo-policy-v1.md"
                target="_blank"
                rel="noopener noreferrer"
              >
                Read the fictional policy <ArrowUpRight size={16} />
              </a>
            ) : (
              report.official_application_url && (
                <a
                  className="button button-primary mt-6"
                  href={report.official_application_url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Official application portal <ArrowUpRight size={16} />
                </a>
              )
            )}
            {report.is_demo && (
              <p className="small-note mt-4">
                This fictional scholarship has no application portal or
                financial award.
              </p>
            )}
            <div className="aside-divider" />
            <Link className="text-link" href="/eligibility">
              Try another synthetic profile <ArrowRight size={15} />
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
