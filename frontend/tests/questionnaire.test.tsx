import { useState } from "react";
import legacyRequirements from "./fixtures/requirements.json";
import { buildProfile, type Answers } from "@/lib/form";
import type { ProfileField } from "@/lib/types";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Questionnaire, QuestionField } from "@/components/questionnaire";
import { ReportProvider, useReport } from "@/components/report-context";
import type { AssessmentRequirements } from "@/lib/types";
import requirementsFixture from "./fixtures/education-requirements.json";
import housingFixture from "./fixtures/housing-requirements.json";
import reportFixture from "./fixtures/assessment-report.json";
const mocks = vi.hoisted(() => ({ push: vi.fn(), refresh: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => mocks }));
const requirements = requirementsFixture as AssessmentRequirements;
function ReportProbe() {
  const { report } = useReport();
  return <div data-testid="report-state">{report?.assessment}</div>;
}
function mount(props: AssessmentRequirements = requirements) {
  return render(
    <ReportProvider>
      <Questionnaire requirements={props} />
      <ReportProbe />
    </ReportProvider>,
  );
}
const result = (value: unknown = reportFixture, status = 200) =>
  new Response(JSON.stringify(value), { status });
describe("scheme assessment questionnaire", () => {
  beforeEach(() => {
    mocks.push.mockReset();
    mocks.refresh.mockReset();
  });
  it("uses natural language with a clear illustrative basis and no development confirmation", () => {
    const { container } = mount();
    expect(
      screen.getByRole("heading", { name: "Your details", level: 2 }),
    ).toBeVisible();
    expect(screen.getByText("Illustrative assessment")).toBeVisible();
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    expect(container.textContent).not.toMatch(/fictional|synthetic|invented/i);
  });
  it("validates numeric input without sending malformed values", async () => {
    const user = userEvent.setup();
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    mount();
    await user.type(screen.getByLabelText("Age", { exact: true }), "twenty");
    await user.click(screen.getByRole("button", { name: "Check Eligibility" }));
    expect(await screen.findByText("Enter a valid number.")).toBeVisible();
    expect(screen.getByLabelText("Age", { exact: true })).toHaveAttribute(
      "aria-invalid",
      "true",
    );
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("submits category sample details with a criteria fingerprint and keeps the report only in memory", async () => {
    const user = userEvent.setup();
    const fetcher = vi.fn().mockResolvedValue(result());
    vi.stubGlobal("fetch", fetcher);
    const storage = vi.spyOn(Storage.prototype, "setItem");
    mount();
    await user.click(
      screen.getByRole("button", { name: "Use Sample Details" }),
    );
    await user.click(screen.getByRole("button", { name: "Check Eligibility" }));
    await waitFor(() =>
      expect(mocks.push).toHaveBeenCalledWith("/eligibility/report"),
    );
    expect(screen.getByTestId("report-state")).toHaveTextContent(
      "Criteria matched",
    );
    const [url, options] = fetcher.mock.calls[0];
    const body = JSON.parse(options.body);
    expect(url).toBe("/api/v1/assessment/check");
    expect(body.criteria_token).toBe(requirements.criteria_token);
    expect(body.scheme_id).toBe(requirements.scheme_id);
    expect(body.profile.current_student).toBe(true);
    expect(body).not.toHaveProperty("synthetic_profile");
    expect(body.profile).not.toHaveProperty("name");
    expect(storage).not.toHaveBeenCalled();
  });
  it("allows missing information to reach the deterministic engine", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      result({
        ...reportFixture,
        result: "UNKNOWN",
        assessment: "Additional information required",
      }),
    );
    vi.stubGlobal("fetch", fetcher);
    mount();
    await userEvent.click(
      screen.getByRole("button", { name: "Check Eligibility" }),
    );
    await waitFor(() => expect(fetcher).toHaveBeenCalled());
    expect(JSON.parse(fetcher.mock.calls[0][1].body).profile).toEqual({});
  });
  it("asks housing questions instead of unrelated education questions", async () => {
    mount(housingFixture as AssessmentRequirements);
    expect(screen.getByLabelText("Already own a home?")).toBeVisible();
    expect(screen.queryByLabelText("Education level")).not.toBeInTheDocument();
    await userEvent.click(
      screen.getByRole("button", { name: "Use Sample Details" }),
    );
    expect(screen.getByLabelText("Already own a home?")).toHaveValue("false");
  });
  it("recovers from network failures", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("Network error")),
    );
    mount();
    await userEvent.click(
      screen.getByRole("button", { name: "Check Eligibility" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "We couldn’t reach the assessment service",
    );
    expect(
      screen.getByRole("button", { name: "Check Eligibility" }),
    ).toBeEnabled();
  });
  it("blocks duplicate submissions while evaluating", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise(() => {})),
    );
    mount();
    await userEvent.click(
      screen.getByRole("button", { name: "Check Eligibility" }),
    );
    expect(
      screen.getByRole("button", { name: "Assessing criteria…" }),
    ).toBeDisabled();
  });
  it("clearly reports unsupported categories without producing a form", () => {
    mount({
      ...requirements,
      available: false,
      assessment_mode: "UNSUPPORTED",
      template: null,
      fields: [],
      requirements: [],
      sample_profile: {},
    });
    expect(screen.getByText("Assessment not available yet.")).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Check Eligibility" }),
    ).not.toBeInTheDocument();
  });
  it("requires reloading when server criteria change", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          result({ error: { message: "Criteria changed" } }, 409),
        ),
    );
    mount();
    await userEvent.click(
      screen.getByRole("button", { name: "Check Eligibility" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "assessment criteria changed",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Reload questionnaire" }),
    );
    expect(mocks.refresh).toHaveBeenCalled();
  });
});

it("preserves conditional question visibility and excludes hidden answers from submission", async () => {
  const fields = (legacyRequirements.fields as ProfileField[]).filter((field) =>
    ["requests_disability_support", "disability_percent"].includes(field.key),
  );
  function ConditionalQuestions() {
    const [answers, setAnswers] = useState<Answers>({});
    return (
      <>
        {fields.map((field) => (
          <QuestionField
            key={field.key}
            field={field}
            answers={answers}
            value={answers[field.key] || ""}
            disabled={false}
            onChange={(value) =>
              setAnswers((previous) => ({ ...previous, [field.key]: value }))
            }
          />
        ))}
        <output data-testid="conditional-profile">
          {JSON.stringify(buildProfile(fields, answers))}
        </output>
      </>
    );
  }
  const user = userEvent.setup();
  render(<ConditionalQuestions />);
  expect(
    screen.queryByLabelText("Certified disability percentage"),
  ).not.toBeInTheDocument();
  await user.selectOptions(
    screen.getByLabelText("Requesting disability support?"),
    "true",
  );
  await user.type(
    screen.getByLabelText("Certified disability percentage"),
    "40",
  );
  expect(screen.getByTestId("conditional-profile")).toHaveTextContent(
    "disability_percent",
  );
  await user.selectOptions(
    screen.getByLabelText("Requesting disability support?"),
    "false",
  );
  expect(
    screen.queryByLabelText("Certified disability percentage"),
  ).not.toBeInTheDocument();
  expect(screen.getByTestId("conditional-profile")).not.toHaveTextContent(
    "disability_percent",
  );
});
