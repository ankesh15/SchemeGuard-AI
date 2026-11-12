import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Questionnaire } from "@/components/questionnaire";
import { ReportProvider, useReport } from "@/components/report-context";
import type { Requirements, SchemePage } from "@/lib/types";
import requirementsFixture from "./fixtures/requirements.json";
import schemesFixture from "./fixtures/schemes.json";
import reportFixture from "./fixtures/report.json";

const mocks = vi.hoisted(() => ({ push: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: mocks.push }) }));
const requirements = requirementsFixture as Requirements;
const schemes = schemesFixture as SchemePage;
function ReportProbe() {
  const { report } = useReport();
  return <div data-testid="report-state">{report?.assessment}</div>;
}
function mount(props: Requirements = requirements) {
  return render(
    <ReportProvider>
      <Questionnaire requirements={props} schemes={schemes.items} />
      <ReportProbe />
    </ReportProvider>,
  );
}

describe("eligibility questionnaire", () => {
  beforeEach(() => {
    mocks.push.mockReset();
  });
  it("requires a synthetic profile confirmation", async () => {
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    mount();
    await userEvent.click(
      screen.getByRole("button", { name: "See my assessment" }),
    );
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Confirm that you are using synthetic information.",
    );
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("shows validation errors instead of sending malformed numeric input", async () => {
    const user = userEvent.setup();
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    mount();
    await user.type(screen.getByLabelText("Age", { exact: true }), "twenty");
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: "See my assessment" }));
    expect(await screen.findByText("Enter a valid number.")).toBeVisible();
    expect(screen.getByLabelText("Age", { exact: true })).toHaveAttribute(
      "aria-invalid",
      "true",
    );
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("sends the synthetic example to the API and retains only the returned report in memory", async () => {
    const user = userEvent.setup();
    const fetcher = vi
      .fn()
      .mockResolvedValue(
        new Response(
          JSON.stringify({ report: reportFixture, explanation: null }),
          { status: 200 },
        ),
      );
    vi.stubGlobal("fetch", fetcher);
    const localStorageSpy = vi.spyOn(Storage.prototype, "setItem");
    mount();
    await user.click(
      screen.getByRole("button", { name: "Use a synthetic example" }),
    );
    await user.click(screen.getByRole("button", { name: "See my assessment" }));
    await waitFor(() =>
      expect(mocks.push).toHaveBeenCalledWith("/eligibility/report"),
    );
    expect(screen.getByTestId("report-state")).toHaveTextContent(
      "Known conditions satisfied",
    );
    const [url, options] = fetcher.mock.calls[0];
    const body = JSON.parse(options.body);
    expect(url).toBe("http://localhost:8000/api/v1/eligibility/explain");
    expect(body.synthetic_profile).toBe(true);
    expect(body.profile.receives_other_scholarship).toBe(false);
    expect(body.profile).not.toHaveProperty("name");
    expect(localStorageSpy).not.toHaveBeenCalled();
  });
  it("allows blank answers to reach the API for an unknown assessment", async () => {
    const fetcher = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          report: {
            ...reportFixture,
            result: "UNKNOWN",
            assessment: "More information required",
          },
          explanation: null,
        }),
        { status: 200 },
      ),
    );
    vi.stubGlobal("fetch", fetcher);
    mount();
    await userEvent.click(screen.getByRole("checkbox"));
    await userEvent.click(
      screen.getByRole("button", { name: "See my assessment" }),
    );
    await waitFor(() => expect(fetcher).toHaveBeenCalled());
    expect(JSON.parse(fetcher.mock.calls[0][1].body).profile).toEqual({});
  });
  it("reveals conditional fields and excludes stale hidden values", async () => {
    const user = userEvent.setup();
    mount();
    expect(
      screen.queryByLabelText("Certified disability percentage"),
    ).not.toBeInTheDocument();
    await user.selectOptions(
      screen.getByLabelText("Requesting disability support?"),
      "true",
    );
    expect(
      screen.getByLabelText("Certified disability percentage"),
    ).toBeVisible();
    await user.type(
      screen.getByLabelText("Certified disability percentage"),
      "40",
    );
    await user.selectOptions(
      screen.getByLabelText("Requesting disability support?"),
      "false",
    );
    expect(
      screen.queryByLabelText("Certified disability percentage"),
    ).not.toBeInTheDocument();
  });
  it("displays network errors and re-enables submission", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new TypeError("Network error")),
    );
    mount();
    await userEvent.click(
      screen.getByRole("button", { name: "Use a synthetic example" }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "See my assessment" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "We couldn’t reach the assessment service",
    );
    expect(
      screen.getByRole("button", { name: "See my assessment" }),
    ).toBeEnabled();
  });
  it("disables duplicate submissions during a pending request", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise(() => {})),
    );
    mount();
    await userEvent.click(
      screen.getByRole("button", { name: "Use a synthetic example" }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "See my assessment" }),
    );
    expect(
      screen.getByRole("button", { name: "Assessing conditions…" }),
    ).toBeDisabled();
  });
  it("does not offer a form when no approved rules exist", () => {
    mount({
      ...requirements,
      available: false,
      rule_set: null,
      fields: [],
      requirements: [],
    });
    expect(
      screen.getByText("More verified information is needed."),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "See my assessment" }),
    ).not.toBeInTheDocument();
  });
});
