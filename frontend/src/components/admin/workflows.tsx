"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { adminFetch, adminJSON, type ResultPage } from "@/lib/admin";
import type { Workflow } from "@/lib/workflow";
import { ErrorState, LoadingState } from "@/components/ui";
import { useAdmin } from "./session";

export function Workflows({ reviews = false }: { reviews?: boolean }) {
  const [data, setData] = useState<ResultPage<Workflow> | null>(null);
  const [error, setError] = useState("");
  const [status, setStatus] = useState(reviews ? "PENDING_REVIEW" : "");
  const [page, setPage] = useState(1);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setError("");
    setData(null);
    const path = `${reviews ? "reviews" : "workflows"}?page=${page}&page_size=20${status ? `&status=${status}` : reviews ? "&status=ALL" : ""}`;
    const load = reviews
      ? adminFetch<ResultPage<{ id: string; workflow: Workflow }>>(path, {
          signal: controller.signal,
        }).then((value) => ({
          ...value,
          items: value.items.map((item) => ({
            ...item.workflow,
            review_id: item.id,
          })),
        }))
      : adminFetch<ResultPage<Workflow>>(path, { signal: controller.signal });
    load
      .then((value) => {
        if (!controller.signal.aborted) setData(value);
      })
      .catch((reason: Error) => {
        if (!controller.signal.aborted) setError(reason.message);
      });
    return () => controller.abort();
  }, [page, refresh, reviews, status]);
  return (
    <section className="admin-card">
      <div className="admin-top">
        <div>
          <span className="eyebrow">Policy intelligence</span>
          <h2>{reviews ? "Human review queue" : "Agent workflows"}</h2>
        </div>
        <button
          className="button button-secondary"
          onClick={() => setRefresh((value) => value + 1)}
        >
          Refresh
        </button>
      </div>
      <p>
        Extraction and verification pause before publication. A human must
        inspect the complete policy and its evidence.
      </p>
      <label>
        Status
        <select
          aria-label="Workflow status"
          value={status}
          onChange={(event) => {
            setStatus(event.target.value);
            setPage(1);
          }}
        >
          <option value="">All statuses</option>
          {(reviews
            ? ["PENDING_REVIEW", "APPROVED", "REJECTED", "CANCELLED"]
            : [
                "PROCESSING",
                "PENDING_REVIEW",
                "APPROVED",
                "REJECTED",
                "FAILED",
                "CANCELLED",
              ]
          ).map((value) => (
            <option key={value}>{value}</option>
          ))}
        </select>
      </label>
      {error ? (
        <ErrorState
          message={error}
          retry={() => setRefresh((value) => value + 1)}
        />
      ) : !data ? (
        <LoadingState message="Loading workflows…" />
      ) : (
        <>
          <p className="small-note">{data.total} workflows</p>
          <div className="admin-document-list">
            {data.items.map((item) => (
              <article key={item.id}>
                <div>
                  <strong>{item.scheme_name}</strong>
                  <p>
                    {item.document_filename} · {item.status} · {item.stage}
                  </p>
                  <small>
                    {item.provider} / {item.model || "not started"}
                  </small>
                  {item.error_message && (
                    <p role="alert">{item.error_message}</p>
                  )}
                </div>
                <div>
                  <Link
                    className="text-link"
                    href={`/admin/workflows/${item.id}`}
                  >
                    View workflow →
                  </Link>
                  {item.review_id && (
                    <Link
                      className="text-link"
                      href={`/admin/reviews/${item.review_id}`}
                    >
                      Inspect review →
                    </Link>
                  )}
                </div>
              </article>
            ))}
          </div>
          {!data.items.length && (
            <p>No workflows match this filter. Start one from a document.</p>
          )}
          <div className="admin-actions">
            <button
              className="button button-secondary"
              disabled={page === 1}
              onClick={() => setPage((value) => value - 1)}
            >
              Previous
            </button>
            <span>Page {page}</span>
            <button
              className="button button-secondary"
              disabled={page * data.page_size >= data.total}
              onClick={() => setPage((value) => value + 1)}
            >
              Next
            </button>
          </div>
        </>
      )}
    </section>
  );
}

export function WorkflowDetail({ id }: { id: string }) {
  const administrator = useAdmin();
  const [data, setData] = useState<Workflow | null>(null);
  const [error, setError] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    adminFetch<Workflow>(`workflows/${id}`, { signal: controller.signal })
      .then((value) => {
        if (!controller.signal.aborted) setData(value);
      })
      .catch((reason: Error) => {
        if (!controller.signal.aborted) setError(reason.message);
      });
    return () => controller.abort();
  }, [id, refresh]);
  async function action(name: "resume" | "cancel") {
    setBusy(true);
    setError("");
    try {
      await adminFetch(
        `workflows/${id}/${name}`,
        adminJSON({ notes }, administrator.csrf_token),
      );
      setRefresh((value) => value + 1);
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Workflow action failed",
      );
    } finally {
      setBusy(false);
    }
  }
  if (!data)
    return error ? (
      <ErrorState message={error} />
    ) : (
      <LoadingState message="Loading workflow…" />
    );
  return (
    <>
      <section className="admin-card">
        <div className="admin-top">
          <div>
            <span className="eyebrow">{data.status}</span>
            <h2>{data.scheme_name}</h2>
            <p>
              Stage: {data.stage} · Attempt {data.attempts} · {data.provider}
            </p>
          </div>
          <button
            className="button button-secondary"
            onClick={() => setRefresh((value) => value + 1)}
          >
            Refresh status
          </button>
        </div>
        <p className="admin-hash">Thread: {data.thread_id}</p>
        <p>Document: {data.document_filename}</p>
        <Link
          className="text-link"
          href={`/admin/documents/${data.document_version_id}`}
        >
          Inspect original document →
        </Link>
        {data.review_id && (
          <Link
            className="button button-primary"
            href={`/admin/reviews/${data.review_id}`}
          >
            Open saved review
          </Link>
        )}
        {data.published_rule_set_id && (
          <Link
            className="text-link"
            href={`/schemes/${data.scheme_id}#policy-history`}
          >
            View approved rule history →
          </Link>
        )}
        {data.error_code && (
          <p role="alert">
            {data.error_code}: {data.error_message}
          </p>
        )}
        {error && (
          <p role="alert" className="form-error">
            {error}
          </p>
        )}
        {!["APPROVED", "REJECTED", "CANCELLED"].includes(data.status) && (
          <>
            <label>
              Recovery / cancellation notes
              <textarea
                minLength={20}
                maxLength={2000}
                value={notes}
                onChange={(event) => setNotes(event.target.value)}
              />
            </label>
            <div className="admin-actions">
              <button
                className="button button-secondary"
                disabled={busy || notes.trim().length < 20}
                onClick={() => void action("resume")}
              >
                Resume saved workflow
              </button>
              <button
                className="button button-secondary"
                disabled={busy || notes.trim().length < 20}
                onClick={() => void action("cancel")}
              >
                Cancel if undecided
              </button>
            </div>
            <p className="small-note">
              An active execution holds a database lock. Retry after it
              finishes. Resume cannot invent a human approval.
            </p>
          </>
        )}
      </section>
      <section className="admin-card">
        <h2>Workflow history</h2>
        <ol className="workflow-history">
          {data.history?.map((item) => (
            <li key={item.id}>
              <strong>
                {item.stage} · {item.event}
              </strong>
              <p>{new Date(item.created_at).toLocaleString()}</p>
              <pre>{JSON.stringify(item.details, null, 2)}</pre>
            </li>
          ))}
        </ol>
      </section>
    </>
  );
}
