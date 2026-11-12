import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AdminLogin } from "@/components/admin/login";
import { AdminWorkspace } from "@/components/admin/session";
import { Documents } from "@/components/admin/documents";
import { ExtractionDetail } from "@/components/admin/extraction-detail";
import { EvidenceViewer } from "@/components/admin/evidence";
import { adminFetch, type AdminSession } from "@/lib/admin";

const navigation = vi.hoisted(() => ({ replace: vi.fn(), refresh: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => navigation }));
const session: AdminSession = {
  user_id: "admin-fixture",
  username: "reviewer",
  role: "admin",
  csrf_token: "csrf-fixture",
  expires_at: "2026-11-13T00:00:00Z",
};
const source = {
  source_id: "source-fixture",
  scheme_id: "scheme-fixture",
  scheme_name: "Synthetic source test",
  title: "Source",
  publisher: "Test",
  url: "https://example.gov.in/fixture.pdf",
  approved_at: "2026-11-12",
  revoked_at: null,
};
const json = (data: unknown, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json" },
  });

describe("administrator document workspace", () => {
  beforeEach(() => {
    navigation.replace.mockReset();
    navigation.refresh.mockReset();
  });
  it("validates credentials before contacting the API", async () => {
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    render(<AdminLogin />);
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Enter your username and password.",
    );
    expect(fetcher).not.toHaveBeenCalled();
  });
  it("signs in through the same-origin API without browser storage", async () => {
    const fetcher = vi.fn().mockResolvedValue(json(session));
    vi.stubGlobal("fetch", fetcher);
    const storage = vi.spyOn(Storage.prototype, "setItem");
    render(<AdminLogin />);
    await userEvent.type(screen.getByLabelText("Username"), "Reviewer");
    await userEvent.type(
      screen.getByLabelText("Password"),
      "synthetic-password",
    );
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    await waitFor(() =>
      expect(navigation.replace).toHaveBeenCalledWith("/admin"),
    );
    expect(fetcher.mock.calls[0][0]).toBe("/api/admin/auth/login");
    expect(fetcher.mock.calls[0][1].credentials).toBe("same-origin");
    expect(storage).not.toHaveBeenCalled();
    expect(screen.getByLabelText("Password")).toHaveValue("");
  });
  it("shows login failures and enables retry", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          json({ error: { message: "Invalid credentials" } }, 401),
        ),
    );
    render(<AdminLogin />);
    fireEvent.change(screen.getByLabelText("Username"), {
      target: { value: "reviewer" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "bad" },
    });
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toBeVisible();
    expect(screen.getByRole("button", { name: "Sign in" })).toBeEnabled();
  });
  it("requires a matching-source attestation before sending an upload", async () => {
    const fetcher = vi.fn(async (url: string, _options?: RequestInit) =>
      json(
        url.includes("/sources")
          ? [source]
          : url.includes("/schemes")
            ? { items: [] }
            : { items: [], total: 0, page: 1, page_size: 20 },
      ),
    );
    vi.stubGlobal("fetch", fetcher);
    render(
      <AdminWorkspace session={session}>
        <Documents />
      </AdminWorkspace>,
    );
    await screen.findByRole("option", {
      name: "Synthetic source test — Source",
    });
    await userEvent.selectOptions(
      screen.getByLabelText("Authorized source"),
      source.source_id,
    );
    await userEvent.click(screen.getByRole("button", { name: "Upload PDF" }));
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Choose a PDF and confirm",
    );
    expect(
      fetcher.mock.calls.every(
        ([, options]) => !options || options.method !== "POST",
      ),
    ).toBe(true);
  });
  it("rejects oversized uploads locally", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) =>
        json(
          url.includes("/sources")
            ? [source]
            : url.includes("/schemes")
              ? { items: [] }
              : { items: [], total: 0, page: 1, page_size: 20 },
        ),
      ),
    );
    render(
      <AdminWorkspace session={session}>
        <Documents />
      </AdminWorkspace>,
    );
    await screen.findByRole("option", {
      name: "Synthetic source test — Source",
    });
    await userEvent.selectOptions(
      screen.getByLabelText("Authorized source"),
      source.source_id,
    );
    const file = new File(["synthetic"], "fixture.pdf", {
      type: "application/pdf",
    });
    Object.defineProperty(file, "size", { value: 11 * 1024 * 1024 });
    fireEvent.change(screen.getByLabelText("Upload a matching PDF"), {
      target: { files: [file] },
    });
    await userEvent.click(
      screen.getByLabelText(
        "This PDF matches the selected scheme and approved source.",
      ),
    );
    await userEvent.click(screen.getByRole("button", { name: "Upload PDF" }));
    expect(screen.getByRole("alert")).toHaveTextContent("no larger than 10 MB");
  });
  it("renders source text literally with page references", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        json({
          page_number: 2,
          text_content: "<script>untrusted source</script>",
          blocks: [],
          issues: [],
          extraction_method: "pymupdf",
        }),
      ),
    );
    const { container } = render(
      <EvidenceViewer
        documentId="document-fixture"
        pageNumber={2}
        excerpt="Synthetic quoted evidence"
      />,
    );
    expect(
      await screen.findByText("<script>untrusted source</script>"),
    ).toBeVisible();
    expect(container.querySelector("script")).toBeNull();
    expect(
      screen.getByRole("heading", { name: "Source page 2" }),
    ).toBeVisible();
  });
  it("shows pending candidate evidence with a clear mock label and no publish control", async () => {
    const candidate = {
      id: "candidate",
      document_version_id: "document",
      condition_identifier: "synthetic_age",
      label: "Synthetic age condition",
      logical_relationship: "and",
      review_status: "PENDING",
      validation_status: "NEEDS_REVIEW",
      validation_issues: ["Historical scope requires review"],
      payload: {
        nodes: [
          {
            key: "age",
            kind: "comparison",
            field: "age_years",
            operator: ">=",
            expected_value: 18,
            units: "years",
            children: [],
          },
        ],
      },
      mapped_expression: null,
      evidence: [
        { node_key: "age", page_number: 2, excerpt: "Synthetic evidence only" },
      ],
    };
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) =>
        json(
          url.includes("/candidates")
            ? { items: [candidate], total: 1, page: 1, page_size: 20 }
            : {
                id: "job",
                document_version_id: "document",
                status: "PENDING_REVIEW",
                provider: "fixture",
                model: "supervised-mock",
                input_chunk_count: 2,
                errors: [],
              },
        ),
      ),
    );
    render(<ExtractionDetail id="job" />);
    expect(await screen.findByText("Synthetic age condition")).toBeVisible();
    expect(screen.getByText(/Supervised mock demonstration/)).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Inspect page 2 · age" }),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: /publish|approve/i }),
    ).not.toBeInTheDocument();
  });
  it("reports processing failures", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) =>
        json(
          url.includes("/candidates")
            ? { items: [], total: 0 }
            : {
                status: "FAILED",
                provider: "gemini",
                errors: [
                  {
                    code: "gemini_credentials_missing",
                    message: "Gemini credentials are not configured.",
                    page_number: null,
                  },
                ],
              },
        ),
      ),
    );
    render(<ExtractionDetail id="failed-job" />);
    expect(await screen.findByText("gemini_credentials_missing")).toBeVisible();
    expect(screen.getByText(/No candidate rules stored/)).toBeVisible();
  });
  it("handles expired API sessions without exposing backend internals", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({}, 401)));
    await expect(adminFetch("documents")).rejects.toThrow(
      "session has expired",
    );
  });
});
