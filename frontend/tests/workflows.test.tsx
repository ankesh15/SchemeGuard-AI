import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ReviewDetail } from "@/components/admin/review";
import { Workflows } from "@/components/admin/workflows";
import { AdminWorkspace } from "@/components/admin/session";
import {
  PolicyEvidence,
  GroundedExplanation,
} from "@/components/policy-evidence";
import type { Review } from "@/lib/workflow";
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), refresh: vi.fn() }),
}));
const administrator = {
  user_id: "reviewer",
  username: "reviewer",
  role: "admin",
  csrf_token: "csrf",
  expires_at: "2026-12-01",
};
const workflow = {
  id: "workflow",
  thread_id: "workflow",
  graph_version: "policy-v1",
  document_version_id: "doc",
  scheme_id: "scheme",
  scheme_name: "Synthetic policy",
  document_filename: "synthetic.pdf",
  status: "PENDING_REVIEW",
  stage: "human_review",
  attempts: 1,
  extraction_job_id: "job",
  provider: "fixture",
  model: "synthetic",
  review_id: "review",
  published_rule_set_id: null,
  error_code: null,
  error_message: null,
  created_at: "2026-11-13",
  updated_at: "2026-11-13",
};
const draft = {
  title: "Synthetic policy",
  logical_operator: "and" as const,
  effective_from: "2020-01-01",
  effective_to: null,
  effective_date_basis: "reviewer_activation",
  effective_date_note: "Synthetic test only date",
  scope_note: "Complete synthetic policy",
  applicability_note: "Synthetic applicability only",
  conditions: [
    {
      key: "age",
      label: "Synthetic age",
      source_candidate_id: "candidate",
      expression: {
        kind: "comparison",
        key: "age",
        field: "age_years",
        operator: ">=",
        value: 18,
        value_type: "number",
      },
      evidence: [
        {
          node_key: "age",
          page_number: 1,
          excerpt: "Synthetic age must be at least 18 years.",
        },
      ],
    },
  ],
};
const review = {
  id: "review",
  status: "PENDING_REVIEW",
  workflow,
  document: {
    id: "doc",
    scheme_id: "scheme",
    scheme_name: "Synthetic policy",
    source_id: "source",
    source_url: "https://example.gov.in/test.pdf",
    original_filename: "synthetic.pdf",
    checksum: "a".repeat(64),
    file_size: 100,
    page_count: 1,
    version_number: 1,
    retrieved_at: "2026-11-13",
    publication_date: null,
    processing_status: "PARSED",
    acquisition_method: "upload",
    pdf_metadata: {},
  },
  revision_number: 1,
  proposal_sha256: "b".repeat(64),
  draft,
  original_proposal: draft,
  findings: [
    {
      id: "finding",
      condition: "policy",
      code: "complete_policy_review",
      message: "Inspect all policy pages",
      severity: "warning",
    },
  ],
  required_finding_ids: ["finding"],
  validation: {
    publishable: true,
    errors: [],
    warnings: [],
    overlapping_rule_sets: [],
  },
  revision_history: [
    {
      id: "revision",
      revision_number: 1,
      actor_id: null,
      notes: "Original extraction",
      created_at: "2026-11-13",
    },
  ],
  decision: null,
} satisfies Review;
const json = (value: unknown, status = 200) =>
  new Response(JSON.stringify(value), { status });
function mount(value: Review = review) {
  const fetcher = vi.fn(async (url: string, options?: RequestInit) => {
    if (url.includes("/pages/"))
      return json({
        text_content: "Synthetic age must be at least 18 years.",
        extraction_method: "pymupdf",
        blocks: [],
        issues: [],
      });
    if (options?.method === "POST")
      return json({
        ...value,
        status: "APPROVED",
        workflow: { ...workflow, status: "APPROVED" },
      });
    return json(value);
  });
  vi.stubGlobal("fetch", fetcher);
  render(
    <AdminWorkspace session={administrator}>
      <ReviewDetail id="review" />
    </AdminWorkspace>,
  );
  return fetcher;
}

describe("human policy review", () => {
  it("requires saved validation, explicit human attestations, every page and finding", async () => {
    const fetcher = mount();
    const approve = await screen.findByRole("button", {
      name: "Approve saved revision & publish",
    });
    expect(approve).toBeDisabled();
    await userEvent.type(
      screen.getByLabelText("Review notes"),
      "Synthetic human review demonstration only.",
    );
    for (const name of [
      "WARNING · complete_policy_review",
      "I inspected original page 1",
      "I am the human reviewer",
      "The complete policy",
      "I verified applicability",
    ]) {
      await userEvent.click(
        screen.getByRole("checkbox", { name: new RegExp(name) }),
      );
    }
    expect(approve).toBeEnabled();
    await userEvent.click(approve);
    await waitFor(() =>
      expect(
        fetcher.mock.calls.some((call) => call[0].endsWith("/approve")),
      ).toBe(true),
    );
    const sent = fetcher.mock.calls.find((call) =>
      call[0].endsWith("/approve"),
    )!;
    const body = JSON.parse(sent[1]!.body as string);
    expect(body.expected_revision).toBe(1);
    expect(body.proposal_sha256).toBe(review.proposal_sha256);
    expect(body.reviewed_pages).toEqual([1]);
    expect(body.acknowledged_findings).toEqual(["finding"]);
    expect((sent[1]!.headers as Record<string, string>)["X-CSRF-Token"]).toBe(
      "csrf",
    );
  });
  it("retains original proposal and blocks approval of unsaved invalid edits", async () => {
    mount();
    const editor = await screen.findByLabelText("Current proposed policy JSON");
    fireEvent.change(editor, { target: { value: "{ invalid" } });
    expect(
      screen.getByRole("button", { name: "Approve saved revision & publish" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Save new revision" }),
    ).toBeDisabled();
    expect(
      screen.getByText("Original agent proposal (immutable)"),
    ).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "incomplete or invalid",
    );
  });
  it("shows server validation errors and never enables an incomplete policy", async () => {
    mount({
      ...review,
      validation: {
        ...review.validation,
        publishable: false,
        errors: ["Missing source evidence"],
      },
    });
    expect(await screen.findByText("Missing source evidence")).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Approve saved revision & publish" }),
    ).toBeDisabled();
  });
  it("lists pending workflow links with explicit provider labels", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        json({
          items: [{ id: "review", workflow }],
          total: 1,
          page: 1,
          page_size: 20,
        }),
      ),
    );
    render(<Workflows reviews />);
    expect(await screen.findByText("Synthetic policy")).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Inspect review →" }),
    ).toHaveAttribute("href", "/admin/reviews/review");
    expect(screen.getByText("fixture / synthetic")).toBeVisible();
  });
});

describe("approved public evidence", () => {
  it("does not offer questions for metadata-only schemes", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => json({ items: [] })),
    );
    render(<PolicyEvidence schemeId="scheme" available={false} />);
    expect(
      await screen.findByText(
        /Discovery metadata cannot establish eligibility/,
      ),
    ).toBeVisible();
    expect(
      screen.queryByRole("button", { name: "Find source passages" }),
    ).not.toBeInTheDocument();
  });
  it("returns an explicit evidence gap for questions absent from approved sources", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) =>
        json(
          url.endsWith("questions")
            ? {
                answer:
                  "The available approved source does not establish the requested information.",
                citations: [],
                notice: "Evidence only.",
              }
            : { items: [] },
        ),
      ),
    );
    render(<PolicyEvidence schemeId="scheme" available />);
    await userEvent.type(
      screen.getByLabelText("Your document question"),
      "What income limit is specified?",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Find source passages" }),
    );
    expect(
      await screen.findByText(/available approved source does not establish/),
    ).toBeVisible();
  });
  it("renders a deterministic assessment and page citation without rewriting results", () => {
    render(
      <GroundedExplanation
        explanation={{
          result: "FAIL",
          assessment: "Requirements not satisfied",
          summary:
            "Requirements not satisfied. Source-backed deterministic assessment.",
          rule_version: 2,
          mode: "deterministic_template",
          retrieval_mode: "lexical_fallback",
          citations: [
            {
              id: "c",
              scheme_id: "s",
              document_version_id: "d",
              document_sha256: "a".repeat(64),
              page_number: 2,
              locator: "page:2",
              excerpt: "Source quotation only.",
              source_title: "Official guideline",
              publisher: "Publisher",
              url: "https://example.gov.in/policy.pdf#page=2",
            },
          ],
        }}
      />,
    );
    expect(screen.getByText(/Requirements not satisfied/)).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Read cited source ↗" }),
    ).toHaveAttribute("href", "https://example.gov.in/policy.pdf#page=2");
  });
});
