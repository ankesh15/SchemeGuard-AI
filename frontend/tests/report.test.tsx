import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { EligibilityReportView } from "@/components/eligibility-report";
import type { EligibilityReport } from "@/lib/types";
import reportFixture from "./fixtures/report.json";
const report = reportFixture as EligibilityReport;

it("renders an explainable fictional report with version, evidence, and no official application claim", () => {
  render(<EligibilityReportView report={report} />);
  expect(
    screen.getByRole("heading", { name: "Known conditions satisfied" }),
  ).toBeVisible();
  expect(screen.getByText("Version 1")).toBeVisible();
  expect(screen.getByText("Synthetic development fixture")).toBeVisible();
  expect(
    screen.queryByRole("link", { name: "Official application portal" }),
  ).not.toBeInTheDocument();
  const summary = screen.getAllByText("View reasoning & evidence")[0];
  fireEvent.click(summary);
  expect(
    screen.getByText(/Fictional policy evidence · Section 1. Age/),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("link", { name: "Read the fictional policy" }),
  ).toHaveAttribute("href", "/policies/demo-policy-v1.md");
});

it("shows unknown requirements and the specific missing information", () => {
  render(
    <EligibilityReportView
      report={{
        ...report,
        result: "UNKNOWN",
        assessment: "More information required",
        missing_fields: [
          { key: "annual_income_inr", label: "Annual household income (INR)" },
        ],
        requirements: [{ ...report.requirements[1], result: "UNKNOWN" }],
      }}
    />,
  );
  expect(
    screen.getByRole("heading", { name: "More information required" }),
  ).toBeVisible();
  expect(screen.getByText("Annual household income (INR)")).toBeVisible();
  expect(screen.getAllByText("Unknown").length).toBeGreaterThan(0);
});

it("renders a failed assessment using the required non-approval language", () => {
  render(
    <EligibilityReportView
      report={{
        ...report,
        result: "FAIL",
        assessment: "Requirements not satisfied",
      }}
    />,
  );
  expect(
    screen.getByRole("heading", { name: "Requirements not satisfied" }),
  ).toBeVisible();
  expect(screen.getByText(/not official government approval/)).toBeVisible();
});
