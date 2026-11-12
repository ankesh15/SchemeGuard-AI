"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { adminFetch, adminJSON } from "@/lib/admin";
import type { Review, PolicyDraft } from "@/lib/workflow";
import { ErrorState, LoadingState } from "@/components/ui";
import { EvidenceViewer } from "./evidence";
import { useAdmin } from "./session";

export function ReviewDetail({ id }: { id: string }) {
  const administrator = useAdmin();
  const [data, setData] = useState<Review | null>(null);
  const [editor, setEditor] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState<number[]>([]);
  const [findings, setFindings] = useState<string[]>([]);
  const [attest, setAttest] = useState([false, false, false]);
  const [refresh, setRefresh] = useState(0);
  function accept(value: Review) {
    setData(value);
    setEditor(JSON.stringify(value.draft, null, 2));
    setFindings([]);
    setAttest([false, false, false]);
    setPages([]);
  }
  useEffect(() => {
    const controller = new AbortController();
    adminFetch<Review>(`reviews/${id}`, { signal: controller.signal })
      .then((value) => {
        if (!controller.signal.aborted) accept(value);
      })
      .catch((reason: Error) => {
        if (!controller.signal.aborted) setError(reason.message);
      });
    return () => controller.abort();
  }, [id, refresh]);
  let draft: PolicyDraft | null = null;
  try {
    const parsed: unknown = JSON.parse(editor);
    if (
      parsed &&
      typeof parsed === "object" &&
      "conditions" in parsed &&
      Array.isArray(parsed.conditions)
    )
      draft = parsed as PolicyDraft;
  } catch {
    /* Invalid edits stay visible until corrected. */
  }
  const dirty = data ? editor !== JSON.stringify(data.draft, null, 2) : false;
  const pending = data?.status === "PENDING_REVIEW";
  function change(key: string, value: unknown) {
    if (draft) setEditor(JSON.stringify({ ...draft, [key]: value }, null, 2));
  }
  async function action(name: "revisions" | "approve" | "reject") {
    if (!data) return;
    if (name === "revisions" && !draft) {
      setError("Enter a complete JSON policy with a conditions array.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const base = { expected_revision: data.revision_number, notes };
      const body =
        name === "revisions"
          ? { ...base, draft }
          : name === "approve"
            ? {
                ...base,
                proposal_sha256: data.proposal_sha256,
                human_review_confirmed: attest[0],
                complete_policy_confirmed: attest[1],
                applicability_confirmed: attest[2],
                reviewed_pages: pages,
                acknowledged_findings: findings,
              }
            : base;
      const value = await adminFetch<Review>(
        `reviews/${id}/${name}`,
        adminJSON(body, administrator.csrf_token),
      );
      accept(value);
      setNotes("");
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Review could not be saved",
      );
    } finally {
      setBusy(false);
    }
  }
  if (!data)
    return error ? (
      <ErrorState
        message={error}
        retry={() => setRefresh((value) => value + 1)}
      />
    ) : (
      <LoadingState message="Loading saved policy review…" />
    );
  const approvalReady =
    pending &&
    !dirty &&
    data.validation.publishable &&
    attest.every(Boolean) &&
    pages.length === data.document.page_count &&
    data.required_finding_ids.every((value) => findings.includes(value)) &&
    notes.trim().length >= 20;
  return (
    <>
      <section className="admin-card">
        <span className="eyebrow">
          {data.status} · Saved revision {data.revision_number}
        </span>
        <h2>{data.workflow.scheme_name}</h2>
        <p>
          {data.document.original_filename} · {data.document.page_count} pages ·{" "}
          {data.workflow.provider} / {data.workflow.model}
        </p>
        <p className="admin-hash">
          Saved proposal SHA-256: {data.proposal_sha256}
        </p>
        <div className="admin-actions">
          <Link
            className="text-link"
            href={`/admin/workflows/${data.workflow.id}`}
          >
            Workflow & errors →
          </Link>
          <a
            className="text-link"
            href={`/api/admin/documents/${data.document.id}/original`}
          >
            Download preserved PDF
          </a>
          <a
            className="text-link"
            href={data.document.source_url}
            target="_blank"
            rel="noreferrer"
          >
            Official source ↗
          </a>
          <Link
            className="text-link"
            href={`/schemes/${data.workflow.scheme_id}#policy-history`}
          >
            Approved history →
          </Link>
        </div>
        <div className="notice">
          <p>
            Inspect every original page, exclusions, dependencies, dates and
            applicability. An extraction can omit requirements. Approval
            publishes executable rules and records your administrator identity.
          </p>
        </div>
        {data.workflow.provider !== "gemini" && (
          <p className="small-note">
            This proposal reuses a {data.workflow.provider} extraction. It does
            not demonstrate a live Gemini response.
          </p>
        )}
      </section>
      <section className="admin-card">
        <h2>Compare & revise the policy</h2>
        <p>
          Edit the complete typed proposal. Every original candidate must remain
          included or appear in excluded_candidates with a reason. Nested AND,
          OR, exclusions and conditional expressions retain the existing engine
          schema.
        </p>
        <div className="review-comparison">
          <details>
            <summary>Original agent proposal (immutable)</summary>
            <pre className="admin-page-text">
              {JSON.stringify(data.original_proposal, null, 2)}
            </pre>
          </details>
          <div>
            <label htmlFor="policy-editor">Current proposed policy JSON</label>
            <textarea
              id="policy-editor"
              className="policy-editor"
              value={editor}
              spellCheck={false}
              disabled={!pending || busy}
              onChange={(event) => setEditor(event.target.value)}
            />
          </div>
        </div>
        {pending && draft && (
          <div className="admin-form-grid">
            <label>
              Effective / activation date
              <input
                type="date"
                value={draft.effective_from || ""}
                onChange={(event) =>
                  change("effective_from", event.target.value || null)
                }
              />
            </label>
            <label>
              End date, if known
              <input
                type="date"
                value={draft.effective_to || ""}
                onChange={(event) =>
                  change("effective_to", event.target.value || null)
                }
              />
            </label>
            <label>
              Date basis
              <select
                value={draft.effective_date_basis}
                onChange={(event) =>
                  change("effective_date_basis", event.target.value)
                }
              >
                <option value="unverified">Unverified</option>
                <option value="official_stated">
                  Explicit date in source (evidence required)
                </option>
                <option value="reviewer_activation">
                  Reviewed administrative activation
                </option>
              </select>
            </label>
            {(
              [
                ["effective_date_note", "Date basis and evidence notes"],
                ["scope_note", "Complete policy scope"],
                ["applicability_note", "Current applicability review"],
              ] as const
            ).map(([key, label]) => (
              <label key={key}>
                {label}
                <textarea
                  value={String(draft?.[key] || "")}
                  onChange={(event) => change(key, event.target.value)}
                />
              </label>
            ))}
          </div>
        )}
        {draft?.conditions.map((condition) => (
          <article className="review-condition" key={condition.key}>
            <h3>{condition.label}</h3>
            <p className="small-note">
              {condition.key} · source candidate{" "}
              {condition.source_candidate_id || "Reviewer-added condition"}
            </p>
            <pre>{JSON.stringify(condition.expression, null, 2)}</pre>
            {condition.evidence.map((anchor, index) => (
              <blockquote key={index}>
                <button
                  className="text-link"
                  onClick={() => setPage(anchor.page_number)}
                >
                  Inspect page {anchor.page_number}
                </button>
                <p>{anchor.excerpt}</p>
                <small>Node: {anchor.node_key}</small>
              </blockquote>
            ))}
          </article>
        ))}
        {!draft && (
          <p role="alert" className="form-error">
            The policy JSON is incomplete or invalid. Correct it before saving.
          </p>
        )}
        {dirty && (
          <p role="status">Unsaved changes. Save a revision before approval.</p>
        )}
        <h3>Saved proposal validation</h3>
        {data.validation.publishable ? (
          <p>
            All automated publication checks passed. Human review is still
            required.
          </p>
        ) : (
          <ul>
            {data.validation.errors.map((message) => (
              <li key={message}>{message}</li>
            ))}
          </ul>
        )}
        {data.validation.overlapping_rule_sets.length > 0 && (
          <>
            <h3>Overlapping approved versions</h3>
            <p>
              Review each date and applicability relationship. Add every
              reviewed ID to replaces_rule_set_ids and explain replacement_notes
              in the policy editor. Historical versions remain intact.
            </p>
            {data.validation.overlapping_rule_sets.map((rule) => (
              <p key={rule.id}>
                Version {rule.version_number}: {rule.title} ·{" "}
                {rule.effective_from} to {rule.effective_to || "open ended"}
                <br />
                <code>{rule.id}</code>
                <br />
                {rule.scope_note}
              </p>
            ))}
          </>
        )}
      </section>
      <section className="admin-card">
        <h2>Inspect source evidence</h2>
        <label>
          Source page
          <select
            aria-label="Source page"
            value={page}
            onChange={(event) => setPage(Number(event.target.value))}
          >
            {Array.from({ length: data.document.page_count }, (_, index) => (
              <option key={index + 1}>{index + 1}</option>
            ))}
          </select>
        </label>
        <EvidenceViewer documentId={data.document.id} pageNumber={page} />
      </section>
      <section className="admin-card">
        <h2>Findings & human decision</h2>
        <p>
          Resolve errors in a saved revision. Acknowledge each retained finding
          and record its resolution in your notes.
        </p>
        {data.findings.map((item) => (
          <label className="review-check" key={item.id}>
            <input
              type="checkbox"
              disabled={!pending || item.severity === "info"}
              checked={findings.includes(item.id)}
              onChange={(event) =>
                setFindings((values) =>
                  event.target.checked
                    ? [...values, item.id]
                    : values.filter((value) => value !== item.id),
                )
              }
            />
            <span>
              <strong>
                {item.severity.toUpperCase()} · {item.code}
              </strong>
              <br />
              {item.message}
            </span>
          </label>
        ))}
        {pending && (
          <>
            <fieldset>
              <legend>Confirm pages actually inspected</legend>
              {Array.from(
                { length: data.document.page_count },
                (_, index) => index + 1,
              ).map((number) => (
                <label className="review-check" key={number}>
                  <input
                    type="checkbox"
                    checked={pages.includes(number)}
                    onChange={(event) =>
                      setPages((values) =>
                        event.target.checked
                          ? [...values, number]
                          : values.filter((value) => value !== number),
                      )
                    }
                  />
                  I inspected original page {number}
                </label>
              ))}
            </fieldset>
            {[
              "I am the human reviewer and have inspected the original document.",
              "The complete policy, exclusions and dependencies are represented.",
              "I verified applicability, effective dates and all overlapping approved versions.",
            ].map((label, index) => (
              <label className="review-check" key={label}>
                <input
                  type="checkbox"
                  checked={attest[index]}
                  onChange={(event) =>
                    setAttest((values) =>
                      values.map((value, position) =>
                        position === index ? event.target.checked : value,
                      ),
                    )
                  }
                />
                {label}
              </label>
            ))}
            <label>
              Revision / decision notes (at least 20 characters)
              <textarea
                aria-label="Review notes"
                minLength={20}
                maxLength={4000}
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
              />
            </label>
            <div className="admin-actions">
              <button
                className="button button-secondary"
                disabled={busy || !draft || !dirty || notes.trim().length < 20}
                onClick={() => void action("revisions")}
              >
                Save new revision
              </button>
              <button
                className="button button-primary"
                disabled={busy || !approvalReady}
                onClick={() => void action("approve")}
              >
                Approve saved revision & publish
              </button>
              <button
                className="button button-secondary"
                disabled={busy || dirty || notes.trim().length < 20}
                onClick={() => void action("reject")}
              >
                Reject saved proposal
              </button>
            </div>
          </>
        )}
        {busy && (
          <LoadingState message="Saving the decision and resuming its checkpoint…" />
        )}
        {error && (
          <p role="alert" className="form-error">
            {error}
          </p>
        )}
        {data.decision && (
          <div className="notice">
            <p>
              {data.decision.action} by administrator{" "}
              {data.decision.reviewer_id} at{" "}
              {new Date(data.decision.created_at).toLocaleString()}
              <br />
              {data.decision.notes}
            </p>
          </div>
        )}
      </section>
      <section className="admin-card">
        <h2>Immutable revision history</h2>
        {data.revision_history.map((item) => (
          <article key={item.id}>
            <strong>
              Revision {item.revision_number} ·{" "}
              {item.actor_id || "Extraction agent"}
            </strong>
            <p>{item.notes}</p>
            <p className="small-note">
              {new Date(item.created_at).toLocaleString()}
            </p>
          </article>
        ))}
      </section>
    </>
  );
}
