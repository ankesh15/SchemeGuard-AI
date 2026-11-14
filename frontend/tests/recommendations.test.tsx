import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import Home from "@/app/page";
import { CitizenAuth } from "@/components/citizen/auth";
import { DiscoveryForm } from "@/components/discovery-form";
import {
  DiscoveryProvider,
  useDiscovery,
} from "@/components/discovery-context";
import {
  DiscoveryEntry,
  RecommendationResults,
  RecommendationReason,
} from "@/components/recommendations";
import { Questionnaire } from "@/components/questionnaire";
import { ReportProvider } from "@/components/report-context";
import { emptyProfile, type RecommendationPage } from "@/lib/recommendations";
import type { AssessmentRequirements } from "@/lib/types";
import schemes from "./fixtures/schemes.json";
import education from "./fixtures/education-requirements.json";
const navigation = vi.hoisted(() => ({
  push: vi.fn(),
  replace: vi.fn(),
  refresh: vi.fn(),
}));
vi.mock("next/navigation", () => ({ useRouter: () => navigation }));
const options = {
  states: ["Assam", "Bihar"],
  categories: ["scholarship", "housing"],
  interests: [
    { value: "education", label: "Scholarships and Education" },
    { value: "housing", label: "Housing" },
  ],
};
const recommendation = {
  ...schemes.items.find((item) => !item.is_demo)!,
  eligibility_available: false,
  policy_currency: "UNVERIFIED",
  assessment_available: true,
  assessment_mode: "ILLUSTRATIVE",
  relevance: "HIGH",
  matching_reasons: [
    "Matches your interest in education",
    "Relevant to your student status",
  ],
  missing_information: ["Scheme-specific verified eligibility conditions"],
  ranking_points: 80,
  ranking_factors: { interest_category: 60, student_status: 20 },
  approved_rule_version: null,
};
const results = {
  items: [recommendation],
  total: 1,
  page: 1,
  page_size: 9,
  pages: 1,
  categories: ["scholarship"],
  notice: "Informational recommendations",
} as unknown as RecommendationPage;
const profile = {
  ...emptyProfile(),
  age_years: 21,
  state: "Assam",
  course_level: "undergraduate",
  current_student: true,
  annual_family_income_inr: 240000,
  occupation: "student",
  interests: ["education"],
};
const json = (value: unknown, status = 200) =>
  new Response(JSON.stringify(value), { status });
function mockService(saved = false) {
  const fetcher = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith("recommendations/options")) return json(options);
    if (url.includes("profiles/me"))
      return json({ exists: true, profile, completeness: { percent: 80 } });
    if (url.endsWith("/me"))
      return saved
        ? json({ user_id: "own", role: "citizen", csrf_token: "csrf-test" })
        : json({ error: { message: "Sign in" } }, 401);
    if (url.endsWith("recommendations")) return json(results);
    if (url.endsWith("assessment/check")) return json({ result: "UNKNOWN" });
    throw new Error("Unexpected request: " + url);
  });
  vi.stubGlobal("fetch", fetcher);
  return fetcher;
}
function Seed({ children }: { children: React.ReactNode }) {
  const context = useDiscovery();
  return (
    <>
      <button
        onClick={() => {
          context.setProfile(profile);
          context.remember(results.items);
        }}
      >
        Load profile
      </button>
      {children}
    </>
  );
}
async function next() {
  await userEvent.click(screen.getByRole("button", { name: "Next" }));
}
describe("profile-first discovery", () => {
  it("home makes no catalog request and contains no automatic scheme cards", () => {
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    const { container } = render(<Home />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "Discover Government Schemes Made for You",
    );
    expect(
      screen.getAllByRole("link", { name: "Find My Schemes" })[0],
    ).toHaveAttribute("href", "/find-schemes");
    expect(screen.getByRole("link", { name: "How It Works" })).toHaveAttribute(
      "href",
      "#how-it-works",
    );
    expect(container.querySelector(".scheme-grid")).toBeNull();
    expect(fetcher).not.toHaveBeenCalled();
    expect(
      screen.getByRole("heading", { name: "Tell Us About Yourself" }),
    ).toBeVisible();
  });
  it("guest form validates, supports back/unknown, and sends no personal data to storage or URLs", async () => {
    const fetcher = mockService();
    const storage = vi.spyOn(Storage.prototype, "setItem");
    render(
      <DiscoveryProvider>
        <DiscoveryForm />
      </DiscoveryProvider>,
    );
    await screen.findByLabelText("Age in years");
    fireEvent.change(screen.getByLabelText("Age in years"), {
      target: { value: "131" },
    });
    await next();
    expect(screen.getByRole("alert")).toHaveTextContent(/130 or less/);
    fireEvent.change(screen.getByLabelText("Age in years"), {
      target: { value: "21" },
    });
    await next();
    expect(screen.getByLabelText("Education level")).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(screen.getByLabelText("Age in years")).toHaveValue("21");
    await next();
    await userEvent.selectOptions(
      screen.getByLabelText("Currently a student?"),
      "true",
    );
    fireEvent.change(screen.getByLabelText("Course or field of study"), {
      target: { value: "x".repeat(81) },
    });
    await next();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "at most 80 characters",
    );
    // An optional hidden answer must not block progressing or leak into the submitted profile.
    await userEvent.selectOptions(
      screen.getByLabelText("Currently a student?"),
      "false",
    );
    await next();
    await next();
    await next();
    await userEvent.click(screen.getByLabelText("Scholarships and Education"));
    expect(
      screen.queryByText("Save these changes to my private encrypted profile"),
    ).toBeNull();
    await userEvent.click(
      screen.getByRole("button", { name: "Find Relevant Schemes" }),
    );
    expect(navigation.push).toHaveBeenCalledWith("/schemes/recommended");
    expect(fetcher.mock.calls.some(([, init]) => init?.method === "PUT")).toBe(
      false,
    );
    expect(storage).not.toHaveBeenCalled();
  });
  it("prefills only the authenticated saved profile and saves changes with explicit consent and CSRF", async () => {
    const fetcher = mockService(true);
    render(
      <DiscoveryProvider>
        <DiscoveryForm />
      </DiscoveryProvider>,
    );
    expect(await screen.findByLabelText("Age in years")).toHaveValue("21");
    expect(screen.getByLabelText("State or union territory")).toHaveValue(
      "Assam",
    );
    await next();
    expect(screen.getByLabelText("Education level")).toHaveValue(
      "undergraduate",
    );
    expect(screen.getByLabelText("Currently a student?")).toHaveValue("true");
    await next();
    await next();
    await next();
    expect(screen.getByLabelText("Scholarships and Education")).toBeChecked();
    await userEvent.click(
      screen.getByLabelText(
        "Save these changes to my private encrypted profile",
      ),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Find Relevant Schemes" }),
    );
    const saved = fetcher.mock.calls.find(([, init]) => init?.method === "PUT");
    expect(saved).toBeDefined();
    expect(saved![1]?.headers).toMatchObject({ "X-CSRF-Token": "csrf-test" });
    expect(JSON.parse(saved![1]?.body as string).interests).toEqual([
      "education",
    ]);
  });
  it("fetches recommendations by bounded POST, explains cards, and links editing and details", async () => {
    const fetcher = mockService();
    render(
      <DiscoveryProvider>
        <Seed>
          <RecommendationResults />
        </Seed>
      </DiscoveryProvider>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Load profile" }));
    expect(
      await screen.findByRole("heading", { name: recommendation.name }),
    ).toBeVisible();
    expect(screen.getByText("Highly Relevant")).toBeVisible();
    expect(
      screen.getByText("Matches your interest in education"),
    ).toBeVisible();
    expect(screen.getByRole("link", { name: "Edit Details" })).toHaveAttribute(
      "href",
      "/find-schemes",
    );
    expect(screen.getByRole("link", { name: /View Details/ })).toHaveAttribute(
      "href",
      `/schemes/${recommendation.id}`,
    );
    const call = fetcher.mock.calls.find(([url]) =>
      url.endsWith("/recommendations"),
    )!;
    expect(call[1]?.method).toBe("POST");
    expect(call[0]).not.toContain("240000");
    expect(JSON.parse(call[1]?.body as string)).toMatchObject({
      state: "Assam",
      interests: ["education"],
      page: 1,
    });
    await userEvent.selectOptions(
      screen.getByLabelText("Category"),
      "scholarship",
    );
    await waitFor(() =>
      expect(
        fetcher.mock.calls.some(
          ([, init]) =>
            init?.body &&
            JSON.parse(init.body as string).category === "scholarship",
        ),
      ).toBe(true),
    );
  });
  it("keeps no-match results useful rather than rendering unrelated schemes", async () => {
    const fetcher = mockService();
    fetcher.mockImplementation(async () =>
      json({ ...results, items: [], total: 0, pages: 0 }),
    );
    render(
      <DiscoveryProvider>
        <Seed>
          <RecommendationResults />
        </Seed>
      </DiscoveryProvider>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Load profile" }));
    expect(
      await screen.findByRole("heading", {
        name: "Let’s make your recommendations more useful.",
      }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Update my details" }),
    ).toHaveAttribute("href", "/find-schemes");
  });
  it("hands off compatible profile fields to assessment without unrelated keys or any storage", async () => {
    const fetcher = mockService();
    function Handoff() {
      const { profile } = useDiscovery();
      return profile ? (
        <Questionnaire requirements={education as AssessmentRequirements} />
      ) : null;
    }
    render(
      <DiscoveryProvider>
        <ReportProvider>
          <Seed>
            <Handoff />
          </Seed>
        </ReportProvider>
      </DiscoveryProvider>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Load profile" }));
    expect(screen.getByLabelText("Age", { exact: true })).toHaveValue("21");
    expect(screen.getByLabelText("Education level")).toHaveValue(
      "undergraduate",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Check Eligibility" }),
    );
    const call = fetcher.mock.calls.find(([url]) =>
      url.endsWith("assessment/check"),
    )!;
    const body = JSON.parse(call[1]?.body as string);
    expect(body.profile).toMatchObject({
      age_years: "21",
      current_student: true,
      course_level: "undergraduate",
    });
    expect(body.profile).not.toHaveProperty("interests");
  });
  it("shows recommendation reasons on scheme detail and clears them with the memory context", async () => {
    render(
      <DiscoveryProvider>
        <Seed>
          <RecommendationReason schemeId={recommendation.id} />
        </Seed>
      </DiscoveryProvider>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Load profile" }));
    expect(
      screen.getByRole("heading", { name: "Why this was recommended" }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: /Back to recommendations/ }),
    ).toHaveAttribute("href", "/schemes/recommended");
  });
  it("routes a new guest from the scheme entry point to the questionnaire without a catalog fetch", async () => {
    const fetcher = mockService();
    render(
      <DiscoveryProvider>
        <DiscoveryEntry />
      </DiscoveryProvider>,
    );
    await waitFor(() =>
      expect(navigation.replace).toHaveBeenCalledWith("/find-schemes"),
    );
    expect(fetcher.mock.calls.every(([url]) => url === "/api/account/me")).toBe(
      true,
    );
  });
  it("reports service failures and retains an editable profile", async () => {
    const fetcher = mockService();
    fetcher.mockImplementation(async () =>
      json({ error: { message: "Temporarily unavailable" } }, 503),
    );
    render(
      <DiscoveryProvider>
        <Seed>
          <RecommendationResults />
        </Seed>
      </DiscoveryProvider>,
    );
    await userEvent.click(screen.getByRole("button", { name: "Load profile" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Temporarily unavailable",
    );
    expect(screen.getByRole("link", { name: "Edit Details" })).toBeVisible();
  });
});

it("lets a guest register to continue their answers without saving them automatically", async () => {
  const fetcher = vi.fn(async () =>
    json({ user_id: "new-citizen", role: "citizen", csrf_token: "csrf" }),
  );
  vi.stubGlobal("fetch", fetcher);
  render(
    <DiscoveryProvider>
      <Seed>
        <CitizenAuth register />
      </Seed>
    </DiscoveryProvider>,
  );
  await userEvent.click(screen.getByRole("button", { name: "Load profile" }));
  fireEvent.change(screen.getByLabelText("Username"), {
    target: { value: "guest_new_citizen" },
  });
  fireEvent.change(screen.getByLabelText("Password", { exact: true }), {
    target: { value: "Long-test-password-123!" },
  });
  fireEvent.change(screen.getByLabelText("Confirm password"), {
    target: { value: "Long-test-password-123!" },
  });
  await userEvent.click(screen.getByRole("button", { name: "Create account" }));
  await waitFor(() =>
    expect(navigation.replace).toHaveBeenCalledWith("/find-schemes"),
  );
  expect(fetcher.mock.calls).toHaveLength(1);
});
