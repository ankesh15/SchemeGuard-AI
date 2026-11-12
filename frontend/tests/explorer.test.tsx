import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Explorer } from "@/components/explorer";
import { SchemeCard } from "@/components/scheme-card";
import { approvedSchemeChoices } from "@/lib/catalog";
import type { Scheme, SchemePage } from "@/lib/types";
import fixture from "./fixtures/schemes.json";

const record: Scheme = {
  ...fixture.items[0],
  id: "government-record",
  name: "Agriculture discovery record",
  category: "agriculture",
  is_demo: false,
  eligibility_available: false,
  applicability: "states",
  applicable_states: ["Goa"],
};
const page = (overrides: Partial<SchemePage> = {}): SchemePage => ({
  items: [record], total: 282, pages: 47, page: 1, page_size: 6, ...overrides,
});
function respond(value: object) {
  return new Response(JSON.stringify(value), { status: 200 });
}

beforeEach(() => vi.unstubAllGlobals());

describe("expanded scheme explorer", () => {
  it("loads categories and verified states from the API and supports pagination/search/filter queries", async () => {
    const fetcher = vi.fn(async (url: string) => {
      if (url.endsWith("/filters")) return respond({ categories: ["agriculture", "scholarship"], states: ["Goa", "Assam"] });
      return respond(page());
    });
    vi.stubGlobal("fetch", fetcher);
    const user = userEvent.setup();
    render(<Explorer />);
    expect(await screen.findByText("282 schemes to explore")).toBeVisible();
    expect(screen.getByRole("option", { name: "Agriculture" })).toBeVisible();
    await user.selectOptions(screen.getByLabelText("Category"), "agriculture");
    await waitFor(() => expect(fetcher.mock.calls.some(([url]) => url.includes("category=agriculture"))).toBe(true));
    await user.selectOptions(screen.getByLabelText("State or union territory"), "Goa");
    await waitFor(() => expect(fetcher.mock.calls.some(([url]) => url.includes("state=Goa"))).toBe(true));
    await user.click(screen.getByRole("button", { name: "Next" }));
    await waitFor(() => expect(fetcher.mock.calls.some(([url]) => url.includes("page=2"))).toBe(true));
    await user.type(screen.getByLabelText("Search schemes"), "PM KISAN");
    await waitFor(() => expect(fetcher.mock.calls.some(([url]) => url.includes("search=PM+KISAN") && url.includes("page=1"))).toBe(true));
    expect(screen.getByText("Discovery metadata only")).toBeVisible();
  });
  it("keeps a useful error state when filters cannot load", async () => {
    vi.stubGlobal("fetch", vi.fn(async (url: string) => {
      if (url.endsWith("/filters")) throw new TypeError("offline");
      return respond(page());
    }));
    render(<Explorer />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Filters could not be loaded");
    expect(screen.getByRole("button", { name: "Retry filters" })).toBeEnabled();
  });
  it("distinguishes approved rules from discovery metadata without implying an award", () => {
    const { rerender } = render(<SchemeCard scheme={record} />);
    expect(screen.getByText("Discovery metadata only")).toBeVisible();
    expect(screen.queryByText("Approved eligibility rules")).not.toBeInTheDocument();
    expect(screen.getByText("Goa")).toBeVisible();
    rerender(<SchemeCard scheme={{ ...record, eligibility_available: true }} />);
    expect(screen.getByText("Approved eligibility rules")).toBeVisible();
  });
  it("does not present national coverage as zero verified states", () => {
    render(<SchemeCard scheme={{ ...record, applicability: "national", applicable_states: [] }} />);
    expect(screen.getByText("National coverage")).toBeVisible();
    expect(screen.queryByText("0 verified states")).not.toBeInTheDocument();
  });
  it("loads approved policy choices beyond the first 100 results", async () => {
    const fetcher = vi.fn(async (url: string) => respond(page({
      items: [{ ...record, id: url.includes("page=2") ? "page-two-policy" : "page-one-policy", eligibility_available: true }],
      total: 101, pages: 2, page_size: 100,
    })));
    vi.stubGlobal("fetch", fetcher);
    expect((await approvedSchemeChoices()).map((item) => item.id)).toEqual(["page-one-policy", "page-two-policy"]);
    expect(fetcher.mock.calls[1][0]).toContain("eligibility_available=true");
    expect(fetcher.mock.calls[1][0]).toContain("page=2");
  });
});
