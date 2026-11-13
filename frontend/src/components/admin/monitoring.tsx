"use client";
import Link from "next/link";
import { useEffect, useState, type FormEvent } from "react";
import {
  adminFetch,
  adminJSON,
  type ApprovedSource,
  type ResultPage,
} from "@/lib/admin";
import { useAdmin } from "./session";
import { ErrorState, LoadingState } from "@/components/ui";
interface Monitor {
  id: string;
  source_title: string;
  source_url: string;
  enabled: boolean;
  frequency: string;
  hour_utc: number;
  weekday: number;
  verification_status: string;
  last_success_at: string | null;
  last_failure_at: string | null;
  next_check_at: string;
}
interface Change {
  id: string;
  source_title: string;
  source_url: string;
  verification_status: string;
  classification: string;
  detected_at: string;
  workflow_id: string | null;
  review_id?: string | null;
  new_document_id: string;
  old_document_id: string | null;
  details?: {
    condition_id: string;
    field: string | null;
    change_type: string;
    old_value: unknown;
    new_value: unknown;
    old_evidence: unknown[];
    new_evidence: unknown[];
  }[];
  documents?: { id: string; version_number: number; checksum: string }[];
}
export function Monitoring() {
  const session = useAdmin();
  const [items, setItems] = useState<Monitor[] | null>(null);
  const [sources, setSources] = useState<ApprovedSource[]>([]);
  const [runs, setRuns] = useState<Record<string, unknown>[]>([]);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [busy, setBusy] = useState(false);
  const [source, setSource] = useState("");
  const [frequency, setFrequency] = useState("weekly");
  const [hour, setHour] = useState(3);
  const [weekday, setWeekday] = useState(0);
  const [notes, setNotes] = useState("");
  const [attest, setAttest] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      adminFetch<{ items: Monitor[] }>("monitors", {
        signal: controller.signal,
      }),
      adminFetch<ApprovedSource[]>("sources", { signal: controller.signal }),
      adminFetch<ResultPage<Record<string, unknown>>>("monitoring-runs", {
        signal: controller.signal,
      }),
    ])
      .then(([a, b, c]) => {
        if (!controller.signal.aborted) {
          setItems(a.items);
          setSources(b);
          setRuns(c.items);
        }
      })
      .catch((reason: Error) => {
        if (!controller.signal.aborted) setError(reason.message);
      });
    return () => controller.abort();
  }, [refresh]);
  async function mutate(path: string, body: unknown, method = "POST") {
    setBusy(true);
    setError("");
    try {
      await adminFetch(path, {
        ...adminJSON(body, session.csrf_token),
        method,
      });
      setRefresh((value) => value + 1);
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Monitoring request failed",
      );
    } finally {
      setBusy(false);
    }
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!attest || !source || notes.trim().length < 20) {
      setError(
        "Select an approved source and confirm permitted scheduled access with detailed notes.",
      );
      return;
    }
    await mutate("monitors", {
      source_id: source,
      enabled: true,
      frequency,
      hour_utc: hour,
      weekday,
      access_permitted: attest,
      access_notes: notes,
    });
  }
  return (
    <>
      <section className="admin-card">
        <div className="admin-top">
          <div>
            <span className="eyebrow">Opt-in official sources</span>
            <h2>Policy monitoring</h2>
          </div>
          <button
            className="button button-secondary"
            onClick={() => setRefresh((value) => value + 1)}
          >
            Refresh
          </button>
        </div>
        <p>
          Only explicitly selected, approved PDF sources are checked. Changed
          bytes remain unverified until the complete policy is reviewed.
        </p>
        {error && <ErrorState message={error} />}
        <form
          onSubmit={(event) => void submit(event)}
          className="admin-form-grid"
        >
          <label>
            Approved source
            <select
              value={source}
              onChange={(event) => setSource(event.target.value)}
              required
            >
              <option value="">Choose an authorized URL</option>
              {sources
                .filter((item) => !item.revoked_at)
                .map((item) => (
                  <option key={item.source_id} value={item.source_id}>
                    {item.scheme_name} — {item.title}
                  </option>
                ))}
            </select>
          </label>
          <label>
            Frequency
            <select
              value={frequency}
              onChange={(event) => setFrequency(event.target.value)}
            >
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
            </select>
          </label>
          <label>
            Hour (UTC)
            <input
              type="number"
              min={0}
              max={23}
              value={hour}
              onChange={(event) => setHour(Number(event.target.value))}
            />
          </label>
          <label>
            Weekday
            <select
              value={weekday}
              onChange={(event) => setWeekday(Number(event.target.value))}
            >
              {[
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
                "Sunday",
              ].map((value, index) => (
                <option key={value} value={index}>
                  {value}
                </option>
              ))}
            </select>
          </label>
          <label>
            Access permission notes
            <textarea
              minLength={20}
              maxLength={2000}
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
            />
          </label>
          <label className="review-check">
            <input
              type="checkbox"
              checked={attest}
              onChange={(event) => setAttest(event.target.checked)}
            />
            I verified that this source permits scheduled access at this
            frequency.
          </label>
          <button className="button button-primary" disabled={busy}>
            Enable selected source
          </button>
        </form>
      </section>
      <section className="admin-card">
        <h2>Monitored sources</h2>
        {!items ? (
          <LoadingState message="Loading monitors…" />
        ) : !items.length ? (
          <p>
            No sources are monitored. Catalog records are never enrolled
            automatically.
          </p>
        ) : (
          items.map((item) => (
            <article className="review-condition" key={item.id}>
              <h3>{item.source_title}</h3>
              <a
                className="text-link"
                href={item.source_url}
                target="_blank"
                rel="noreferrer"
              >
                Official source ↗
              </a>
              <p>
                {item.enabled ? "Enabled" : "Disabled"} · {item.frequency} at{" "}
                {item.hour_utc}:00 UTC · {item.verification_status}
              </p>
              <p>
                Last success:{" "}
                {item.last_success_at
                  ? new Date(item.last_success_at).toLocaleString()
                  : "Not checked"}
                <br />
                Last failure:{" "}
                {item.last_failure_at
                  ? new Date(item.last_failure_at).toLocaleString()
                  : "None"}
                <br />
                Next check: {new Date(item.next_check_at).toLocaleString()}
              </p>
              <div className="admin-actions">
                <button
                  className="button button-secondary"
                  disabled={busy}
                  onClick={() =>
                    void mutate(
                      `monitors/${item.id}`,
                      { enabled: !item.enabled },
                      "PATCH",
                    )
                  }
                >
                  {item.enabled ? "Disable" : "Enable"}
                </button>
                <button
                  className="button button-secondary"
                  disabled={busy || !item.enabled}
                  onClick={() => void mutate(`monitors/${item.id}/check`, {})}
                >
                  Queue check
                </button>
              </div>
            </article>
          ))
        )}
      </section>
      <section className="admin-card">
        <h2>Monitoring history & failures</h2>
        {!runs.length ? (
          <p>No checks have run yet.</p>
        ) : (
          runs.map((run) => (
            <article key={String(run.id)}>
              <strong>
                {String(run.status)} · {String(run.job_status)}
              </strong>
              <p>
                Run {String(run.id)} · Attempt {String(run.attempts)}
              </p>
              <p>
                {run.error_code
                  ? String(run.error_code)
                  : "No recorded failure"}
              </p>
            </article>
          ))
        )}
        <Link className="text-link" href="/admin/policy-changes">
          Review detected policy changes →
        </Link>
      </section>
    </>
  );
}
export function PolicyChanges() {
  const [data, setData] = useState<ResultPage<Change> | null>(null);
  const [error, setError] = useState("");
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    adminFetch<ResultPage<Change>>(
      `policy-changes?page=${page}${status ? `&status=${status}` : ""}`,
      { signal: controller.signal },
    )
      .then((value) => {
        if (!controller.signal.aborted) setData(value);
      })
      .catch((reason: Error) => {
        if (!controller.signal.aborted) setError(reason.message);
      });
    return () => controller.abort();
  }, [page, status]);
  return (
    <section className="admin-card">
      <h2>Detected policy changes</h2>
      <label>
        Review status
        <select
          value={status}
          onChange={(event) => {
            setStatus(event.target.value);
            setPage(1);
          }}
        >
          <option value="">All statuses</option>
          {[
            "PENDING_REVIEW",
            "APPROVED",
            "REJECTED",
            "CLARIFICATION",
            "NO_POLICY_CHANGE",
          ].map((value) => (
            <option key={value}>{value}</option>
          ))}
        </select>
      </label>
      {error ? (
        <ErrorState message={error} />
      ) : !data ? (
        <LoadingState message="Loading policy changes…" />
      ) : (
        <>
          <div className="admin-document-list">
            {data.items.map((item) => (
              <article key={item.id}>
                <div>
                  <strong>{item.source_title}</strong>
                  <p>
                    {item.classification} · {item.verification_status}
                  </p>
                </div>
                <Link
                  className="text-link"
                  href={`/admin/policy-changes/${item.id}`}
                >
                  Compare policy versions →
                </Link>
              </article>
            ))}
          </div>
          {!data.items.length && (
            <p>
              No matching changes. Unapproved proposals are never public policy
              updates.
            </p>
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
export function PolicyChangeDetail({ id }: { id: string }) {
  const session = useAdmin();
  const [data, setData] = useState<Change | null>(null);
  const [error, setError] = useState("");
  const [notes, setNotes] = useState("");
  const [refresh, setRefresh] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    adminFetch<Change>(`policy-changes/${id}`, { signal: controller.signal })
      .then((value) => {
        if (!controller.signal.aborted) setData(value);
      })
      .catch((reason: Error) => {
        if (!controller.signal.aborted) setError(reason.message);
      });
    return () => controller.abort();
  }, [id, refresh]);
  if (!data)
    return error ? (
      <ErrorState message={error} />
    ) : (
      <LoadingState message="Comparing source-backed policies…" />
    );
  return (
    <>
      <section className="admin-card">
        <span className="eyebrow">
          {data.verification_status} · {data.classification}
        </span>
        <h2>{data.source_title}</h2>
        <p>
          A content change is a proposal, not a verified government eligibility
          change. Inspect both source versions and the complete human review.
        </p>
        <div className="admin-actions">
          {data.review_id && (
            <Link
              className="button button-primary"
              href={`/admin/reviews/${data.review_id}`}
            >
              Review full policy & approve / reject
            </Link>
          )}
          {data.workflow_id && (
            <Link
              className="text-link"
              href={`/admin/workflows/${data.workflow_id}`}
            >
              Workflow status & recovery →
            </Link>
          )}
        </div>
        {data.documents?.map((item) => (
          <p key={item.id}>
            <Link className="text-link" href={`/admin/documents/${item.id}`}>
              Document version {item.version_number} →
            </Link>
            <br />
            <code className="admin-hash">{item.checksum}</code>
          </p>
        ))}
      </section>
      {data.details?.map((item, index) => (
        <section className="admin-card" key={index}>
          <span className="eyebrow">{item.change_type}</span>
          <h3>{item.field || item.condition_id}</h3>
          <div className="review-comparison">
            <div>
              <h4>Old approved rule</h4>
              <pre className="admin-page-text">
                {JSON.stringify(item.old_value, null, 2)}
              </pre>
              <h4>Old evidence</h4>
              <pre className="admin-page-text">
                {JSON.stringify(item.old_evidence, null, 2)}
              </pre>
            </div>
            <div>
              <h4>New proposed rule</h4>
              <pre className="admin-page-text">
                {JSON.stringify(item.new_value, null, 2)}
              </pre>
              <h4>New evidence</h4>
              <pre className="admin-page-text">
                {JSON.stringify(item.new_evidence, null, 2)}
              </pre>
            </div>
          </div>
        </section>
      ))}
      <section className="admin-card">
        <h3>Request clarification</h3>
        <label>
          Review notes
          <textarea
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            minLength={20}
          />
        </label>
        <button
          className="button button-secondary"
          disabled={
            notes.trim().length < 20 ||
            ["APPROVED", "REJECTED"].includes(data.verification_status)
          }
          onClick={async () => {
            try {
              await adminFetch(
                `policy-changes/${id}/clarify`,
                adminJSON({ notes }, session.csrf_token),
              );
              setRefresh((value) => value + 1);
            } catch (reason) {
              setError(
                reason instanceof Error
                  ? reason.message
                  : "Clarification failed",
              );
            }
          }}
        >
          Request a revised proposal
        </button>
        {error && <p role="alert">{error}</p>}
      </section>
    </>
  );
}
