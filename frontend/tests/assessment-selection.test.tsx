import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import EligibilityPage from "@/app/eligibility/page";
import { ReportProvider } from "@/components/report-context";
import { SchemeCard } from "@/components/scheme-card";
import type { Scheme } from "@/lib/types";
import schemes from "./fixtures/schemes.json";
import requirements from "./fixtures/education-requirements.json";
const navigation = vi.hoisted(() => ({ push: vi.fn(), refresh: vi.fn() }));
vi.mock("next/navigation", () => ({
  useRouter: () => navigation,
  notFound: () => {
    throw new Error("NOT_FOUND");
  },
  redirect: (url: string) => {
    throw new Error("REDIRECT " + url);
  },
}));
const government = {
  ...schemes.items.find((item) => !item.is_demo)!,
  assessment_mode: "ILLUSTRATIVE" as const,
  assessment_available: true,
};
const json = (value: unknown) =>
  new Response(JSON.stringify(value), { status: 200 });
describe("government scheme assessment selection", () => {
  it("opens a searchable catalog with no automatically selected old learning fixture", async () => {
    const fetcher = vi.fn(async (url: string) =>
      json(
        url.includes("/filters")
          ? { categories: ["scholarship"], states: ["Assam"] }
          : {
              items: [government],
              page: 1,
              page_size: 6,
              total: 282,
              pages: 47,
            },
      ),
    );
    vi.stubGlobal("fetch", fetcher);
    render(await EligibilityPage({ searchParams: Promise.resolve({}) }));
    expect(
      screen.getByRole("heading", { name: "Choose your starting point." }),
    ).toBeVisible();
    expect(
      await screen.findByRole("link", { name: `Assess ${government.name}` }),
    ).toHaveAttribute("href", `/eligibility?scheme=${government.id}`);
    expect(screen.getByLabelText("Search schemes")).toBeVisible();
    expect(screen.getByLabelText("Category")).toBeVisible();
    expect(screen.getByLabelText("State or union territory")).toBeVisible();
    expect(
      fetcher.mock.calls.some(([url]) => url.includes("is_demo=false")),
    ).toBe(true);
    expect(
      fetcher.mock.calls.some(([url]) => url.includes("requirements")),
    ).toBe(false);
  });
  it("loads metadata and the correct questionnaire for the selected government scheme", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) =>
        json(
          url.includes("assessment-requirements")
            ? requirements
            : { ...government, sources: [] },
        ),
      ),
    );
    const page = await EligibilityPage({
      searchParams: Promise.resolve({ scheme: government.id }),
    });
    render(<ReportProvider>{page}</ReportProvider>);
    expect(
      screen.getByRole("heading", { level: 1, name: government.name }),
    ).toBeVisible();
    expect(screen.getByLabelText("Education level")).toBeVisible();
    expect(
      screen.queryByLabelText("Already own a home?"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText(/not verified government requirements/),
    ).toBeVisible();
  });
  it("redirects old public learning-fixture links to government scheme selection", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) =>
        json(
          url.includes("assessment-requirements")
            ? requirements
            : { ...government, is_demo: true },
        ),
      ),
    );
    await expect(
      EligibilityPage({
        searchParams: Promise.resolve({ scheme: government.id }),
      }),
    ).rejects.toThrow("REDIRECT /eligibility");
  });
  it("keeps illustrative availability distinct from approved policy availability", () => {
    render(<SchemeCard scheme={government as Scheme} assessment />);
    expect(screen.getByText("Illustrative assessment available")).toBeVisible();
    expect(
      screen.queryByText("Approved eligibility rules"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: `Assess ${government.name}` }),
    ).toHaveAttribute("href", `/eligibility?scheme=${government.id}`);
  });
});
