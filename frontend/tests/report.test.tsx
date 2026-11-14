import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { EligibilityReportView } from "@/components/eligibility-report";
import type { EligibilityReport } from "@/lib/types";
import reportFixture from "./fixtures/assessment-report.json";
import legacyFixture from "./fixtures/report.json";
const report = reportFixture as EligibilityReport;
it("shows the selected scheme, applicant details and transparent template basis without fake citations", () => {
  const { container } = render(<EligibilityReportView report={report} />);
  expect(
    screen.getByRole("heading", { name: "Criteria matched" }),
  ).toBeVisible();
  expect(screen.getByText(report.scheme_name)).toBeVisible();
  expect(
    screen.getByRole("heading", { name: "Details used in this assessment" }),
  ).toBeVisible();
  expect(screen.getByText("Education assessment · Version 1")).toBeVisible();
  expect(screen.getByText("Project-authored illustration")).toBeVisible();
  expect(screen.queryByText(/Policy evidence/)).not.toBeInTheDocument();
  expect(
    screen.getByText(/not supporting evidence for the illustrative criteria/),
  ).toBeVisible();
  expect(container.textContent).not.toMatch(/fictional|synthetic|invented/i);
  expect(
    screen.queryByRole("link", { name: "Official application portal" }),
  ).not.toBeInTheDocument();
});
it("shows unresolved requirements and missing information", () => {
  render(
    <EligibilityReportView
      report={{
        ...report,
        result: "UNKNOWN",
        assessment: "Additional information required",
        missing_fields: [
          {
            key: "annual_family_income_inr",
            label: "Annual family income (INR)",
          },
        ],
        requirements: [{ ...report.requirements[0], result: "UNKNOWN" }],
      }}
    />,
  );
  expect(
    screen.getAllByRole("heading", { name: "Additional information required" })
      .length,
  ).toBeGreaterThan(0);
  expect(
    screen.getAllByText("Annual family income (INR)").length,
  ).toBeGreaterThan(0);
});
it("explains criteria that did not match without promising government eligibility", () => {
  render(
    <EligibilityReportView
      report={{ ...report, result: "FAIL", assessment: "Criteria not matched" }}
    />,
  );
  expect(
    screen.getByRole("heading", { name: "Criteria not matched" }),
  ).toBeVisible();
  expect(
    screen.getByText(
      /Results are estimates and do not determine government eligibility/,
    ),
  ).toBeVisible();
});
it("preserves real reviewed-policy evidence instead of attaching it to an illustration", () => {
  const legacy = legacyFixture as EligibilityReport;
  const reviewed: EligibilityReport = {
    ...legacy,
    is_demo: false,
    assessment_mode: "APPROVED_POLICY",
    scheme_name: "Isolated reviewed-policy fixture",
    rule_set: {
      ...legacy.rule_set!,
      approval_basis: "human_review",
      scope_note: "Reviewed in an isolated test.",
    },
    requirements: [
      {
        ...legacy.requirements[0],
        label: "Reviewed age condition",
        evidence: [
          {
            ...legacy.requirements[0].evidence[0],
            is_demo: false,
            source_title: "Reviewed source fixture",
          },
        ],
      },
    ],
  };
  render(<EligibilityReportView report={reviewed} />);
  fireEvent.click(screen.getByText("View reasoning & evidence"));
  expect(
    screen.getByText(/Policy evidence · Section 1. Age/),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("link", { name: "Reviewed source fixture" }),
  ).toHaveAttribute("href", reviewed.requirements[0].evidence[0].url);
  expect(screen.getByText("Human-reviewed policy rules")).toBeVisible();
});
it("never renders source evidence for an illustrative report, even with malformed client data", () => {
  render(
    <EligibilityReportView
      report={{
        ...report,
        requirements: (legacyFixture as EligibilityReport).requirements,
      }}
    />,
  );
  expect(screen.queryByText(/Policy evidence/)).not.toBeInTheDocument();
  expect(
    screen.queryByRole("link", { name: "Fictional development policy v1" }),
  ).not.toBeInTheDocument();
});
it("keeps legacy saved history while using natural public terminology", () => {
  const { container } = render(
    <EligibilityReportView report={legacyFixture as EligibilityReport} saved />,
  );
  expect(screen.getByText("SchemeGuard Learning Assessment")).toBeVisible();
  expect(screen.getByText("Version 1")).toBeVisible();
  expect(
    screen.getByText(/saved assessment retains its original version/),
  ).toBeVisible();
  expect(container.textContent).not.toMatch(/fictional|synthetic|invented/i);
});
