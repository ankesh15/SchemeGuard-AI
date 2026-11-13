import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { Monitoring, PolicyChangeDetail } from "@/components/admin/monitoring";
import { AdminWorkspace } from "@/components/admin/session";
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), refresh: vi.fn() }),
}));
const session = {
  user_id: "admin",
  username: "reviewer",
  role: "admin",
  csrf_token: "csrf",
  expires_at: "2026-12-01",
};
const json = (value: unknown) =>
  new Response(JSON.stringify(value), { status: 200 });
function mount() {
  const fetcher = vi.fn(async (url: string, options?: RequestInit) =>
    json(
      url.endsWith("sources")
        ? [
            {
              source_id: "source",
              scheme_name: "Synthetic scheme",
              title: "Official fixture",
              revoked_at: null,
            },
          ]
        : url.includes("monitoring-runs")
          ? { items: [] }
          : options?.method === "POST"
            ? {}
            : { items: [] },
    ),
  );
  vi.stubGlobal("fetch", fetcher);
  render(
    <AdminWorkspace session={session}>
      <Monitoring />
    </AdminWorkspace>,
  );
  return fetcher;
}
describe("opt-in policy monitoring", () => {
  it("does not enroll sources without explicit access confirmation", async () => {
    const fetcher = mount();
    await screen.findByRole("option", {
      name: "Synthetic scheme — Official fixture",
    });
    await userEvent.selectOptions(
      screen.getByLabelText("Approved source"),
      "source",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Enable selected source" }),
    );
    expect(
      await screen.findByText(/Select an approved source and confirm/),
    ).toBeVisible();
    expect(
      fetcher.mock.calls.filter((call) => call[1]?.method === "POST"),
    ).toHaveLength(0);
  });
  it("submits only the selected source and chosen schedule", async () => {
    const fetcher = mount();
    await screen.findByRole("option", {
      name: "Synthetic scheme — Official fixture",
    });
    await userEvent.selectOptions(
      screen.getByLabelText("Approved source"),
      "source",
    );
    fireEvent.change(screen.getByLabelText("Access permission notes"), {
      target: {
        value:
          "Synthetic source permits this scheduled access in isolated tests.",
      },
    });
    await userEvent.click(
      screen.getByRole("checkbox", { name: /I verified that this source/ }),
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Enable selected source" }),
    );
    await waitFor(() =>
      expect(
        fetcher.mock.calls.some((call) => call[1]?.method === "POST"),
      ).toBe(true),
    );
    const call = fetcher.mock.calls.find((call) => call[1]?.method === "POST")!;
    expect(JSON.parse(call[1]!.body as string)).toMatchObject({
      source_id: "source",
      frequency: "weekly",
      access_permitted: true,
    });
  });
  it("shows old and new evidence as a pending comparison", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        json({
          id: "change",
          source_title: "Synthetic policy",
          verification_status: "PENDING_REVIEW",
          classification: "MATERIAL",
          new_document_id: "new",
          old_document_id: "old",
          review_id: "review",
          workflow_id: "workflow",
          documents: [],
          details: [
            {
              condition_id: "income",
              field: "annual_family_income_inr",
              change_type: "THRESHOLD_INCREASED",
              old_value: 250000,
              new_value: 300000,
              old_evidence: [{ excerpt: "Synthetic old evidence" }],
              new_evidence: [{ excerpt: "Synthetic new evidence" }],
            },
          ],
        }),
      ),
    );
    render(
      <AdminWorkspace session={session}>
        <PolicyChangeDetail id="change" />
      </AdminWorkspace>,
    );
    expect(await screen.findByText("Old approved rule")).toBeVisible();
    expect(screen.getByText("New proposed rule")).toBeVisible();
    expect(screen.getByText(/PENDING_REVIEW/)).toBeVisible();
    expect(
      screen.getByRole("link", {
        name: "Review full policy & approve / reject",
      }),
    ).toHaveAttribute("href", "/admin/reviews/review");
  });
});
