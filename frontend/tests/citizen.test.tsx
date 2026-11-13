import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { CitizenAuth } from "@/components/citizen/auth";
import { CitizenWorkspace } from "@/components/citizen/session";
import { CitizenNotifications } from "@/components/citizen/notifications";
import { CitizenSettings } from "@/components/citizen/settings";
import { NewAssessment } from "@/components/citizen/assessments";
import type { CitizenSession } from "@/lib/citizen";
const replace = vi.fn(),
  refresh = vi.fn(),
  push = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, refresh, push }),
}));
const session: CitizenSession = {
  user_id: "fixture",
  username: "citizen",
  role: "citizen",
  csrf_token: "csrf-fixture",
  expires_at: "2027-01-01",
};
const json = (value: unknown) =>
  new Response(JSON.stringify(value), { status: 200 });
function workspace(children: React.ReactNode) {
  render(<CitizenWorkspace session={session}>{children}</CitizenWorkspace>);
}
describe("citizen private workspace", () => {
  it("validates registration and matching passwords before sending", async () => {
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    render(<CitizenAuth register />);
    await userEvent.click(
      screen.getByRole("button", { name: "Create account" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "lowercase username",
    );
    fireEvent.change(screen.getByLabelText("Username"), {
      target: { value: "synthetic_user" },
    });
    fireEvent.change(screen.getByLabelText("Password", { exact: true }), {
      target: { value: "Long-synthetic-password-123!" },
    });
    fireEvent.change(screen.getByLabelText("Confirm password"), {
      target: { value: "different" },
    });
    await userEvent.click(
      screen.getByRole("button", { name: "Create account" }),
    );
    expect(screen.getByRole("alert")).toHaveTextContent("do not match");
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("uses cookie transport and never saves a session in browser storage", async () => {
    const storage = vi.spyOn(Storage.prototype, "setItem");
    const fetcher = vi.fn(async (_url: string, _options?: RequestInit) =>
      json(session),
    );
    vi.stubGlobal("fetch", fetcher);
    render(<CitizenAuth />);
    fireEvent.change(screen.getByLabelText("Username"), {
      target: { value: "synthetic_user" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "Long-synthetic-password-123!" },
    });
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/dashboard"));
    expect(fetcher.mock.calls[0][0]).toBe("/api/account/auth/login");
    expect(storage).not.toHaveBeenCalled();
    expect(screen.getByLabelText("Password")).toHaveValue("");
  });
  it("does not fabricate an assessment for a metadata-only scheme", async () => {
    const fetcher = vi.fn(async (url: string) =>
      json(
        url.includes("requirements")
          ? { available: false, fields: [], scheme_name: "Metadata scheme" }
          : url.includes("profiles")
            ? { profile: { attributes: {} } }
            : { items: [{ id: "scheme", name: "Metadata scheme" }], total: 1 },
      ),
    );
    vi.stubGlobal("fetch", fetcher);
    workspace(<NewAssessment initialScheme="scheme" />);
    expect(
      await screen.findByText(/Metadata alone cannot produce/),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Evaluate & save privately" }),
    ).not.toBeInTheDocument();
  });
  it("marks notifications with CSRF and refreshes the unread count", async () => {
    let read = false;
    const fetcher = vi.fn(async (url: string, options?: RequestInit) => {
      if (options?.method === "POST") {
        read = true;
        return new Response(null, { status: 204 });
      }
      return json({
        items: [
          {
            id: "notice",
            scheme_id: "scheme",
            policy_change_id: "change",
            assessment_id: "assessment",
            notification_type: "NEW_INFORMATION_REQUIRED",
            title: "Verified policy update",
            description: "Review missing fields",
            created_at: "2026-11-01",
            read_at: read ? "2026-11-02" : null,
          },
        ],
        total: 1,
        unread_count: read ? 0 : 1,
      });
    });
    vi.stubGlobal("fetch", fetcher);
    workspace(<CitizenNotifications />);
    await screen.findByText("Verified policy update");
    await userEvent.click(
      screen.getByRole("button", { name: /^Mark as read$/ }),
    );
    await waitFor(() => expect(screen.getByText("0 unread")).toBeVisible());
    const call = fetcher.mock.calls.find((call) => call[1]?.method === "POST")!;
    expect(call[0]).toBe("/api/account/notifications/notice/read");
    expect(call[1]?.headers).toMatchObject({ "X-CSRF-Token": "csrf-fixture" });
  });
  it("persists explicit notification preferences without requesting email", async () => {
    const fetcher = vi.fn(async () =>
      json({
        in_app: true,
        automatic_reassessment: true,
        policy_updates: true,
      }),
    );
    vi.stubGlobal("fetch", fetcher);
    workspace(<CitizenSettings />);
    await screen.findByLabelText("In-app notifications");
    await userEvent.click(screen.getByLabelText("In-app notifications"));
    await userEvent.click(
      screen.getByRole("button", { name: "Save preferences" }),
    );
    await screen.findByRole("status");
    const call = fetcher.mock.calls.find(
      (call) => ((call as unknown[])[1] as RequestInit)?.method === "PUT",
    ) as unknown as [string, RequestInit];
    expect(JSON.parse(call[1].body as string)).toMatchObject({ in_app: false });
    expect(screen.getByText(/Password reset is unavailable/)).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Delete account and private data" }),
    ).toBeDisabled();
  });
  it("revokes the session on sign out", async () => {
    const fetcher = vi.fn(
      async (_url: string, _options?: RequestInit) =>
        new Response(null, { status: 204 }),
    );
    vi.stubGlobal("fetch", fetcher);
    workspace(<p>Private content</p>);
    await userEvent.click(screen.getByRole("button", { name: "Sign out" }));
    await waitFor(() => expect(replace).toHaveBeenCalledWith("/login"));
    expect(fetcher.mock.calls[0][0]).toBe("/api/account/auth/logout");
  });
});

// Profile fields remain optional; malformed values must not be sent to storage.
import { CitizenProfile } from "@/components/citizen/profile";
describe("private profile input", () => {
  it("keeps unknown fields empty and rejects an out-of-domain age", async () => {
    const fetcher = vi.fn(async (url: string, options?: RequestInit) =>
      json(
        url.includes("options")
          ? { states: ["Assam"], fields: [] }
          : {
              exists: true,
              profile: {
                state: null,
                age_years: null,
                annual_family_income_inr: null,
                current_student: null,
                course_level: null,
                occupation: null,
                attributes: {},
              },
              completeness: { completed: 0, total: 5, percent: 0 },
              notice: "Optional",
              updated_at: null,
            },
      ),
    );
    vi.stubGlobal("fetch", fetcher);
    workspace(<CitizenProfile />);
    await screen.findByLabelText("Age in years");
    expect(screen.getByLabelText("Annual family income (INR)")).toHaveValue("");
    fireEvent.change(screen.getByLabelText("Age in years"), {
      target: { value: "131" },
    });
    await userEvent.click(
      screen.getByRole("button", { name: "Save private profile" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "whole age from 0 to 130",
    );
    expect(fetcher.mock.calls.some((call) => call[1]?.method === "PUT")).toBe(
      false,
    );
  });
});
