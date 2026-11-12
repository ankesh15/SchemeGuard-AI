"use client";
import { GroundedExplanation } from "@/components/policy-evidence";
import { BookOpen } from "lucide-react";
import { useReport } from "@/components/report-context";
import { EligibilityReportView } from "@/components/eligibility-report";
import { ActionLink } from "@/components/ui";
export default function ReportPage() {
  const { report, explanation } = useReport();
  return (
    <div className="container page-shell">
      {report ? (
        <>
          <EligibilityReportView report={report} />
          {explanation && <GroundedExplanation explanation={explanation} />}
        </>
      ) : (
        <div className="empty-state empty-report">
          <BookOpen size={34} />
          <span className="eyebrow">A fresh start</span>
          <h1>Your next explanation starts here.</h1>
          <p>
            There’s no assessment in this page’s memory. Profiles and reports
            aren’t saved, so refreshing the page clears the report.
          </p>
          <ActionLink href="/eligibility">
            Start an eligibility check
          </ActionLink>
        </div>
      )}
    </div>
  );
}
