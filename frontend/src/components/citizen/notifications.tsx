"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { citizenFetch, citizenJSON, type Notice } from "@/lib/citizen";
import { ErrorState, LoadingState } from "@/components/ui";
import { useCitizen } from "./session";
export function CitizenNotifications() {
  const session = useCitizen();
  const [data, setData] = useState<{
    items: Notice[];
    total: number;
    unread_count: number;
  } | null>(null);
  const [page, setPage] = useState(1);
  const [unread, setUnread] = useState(false);
  const [revision, setRevision] = useState(0);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    setError("");
    citizenFetch<typeof data>(
      `notifications?page=${page}&unread_only=${unread}`,
      { signal: controller.signal },
    )
      .then((value) => {
        if (!controller.signal.aborted) setData(value);
      })
      .catch((reason: Error) => {
        if (!controller.signal.aborted) setError(reason.message);
      });
    return () => controller.abort();
  }, [page, unread, revision]);
  async function mark(path: string) {
    setBusy(true);
    setError("");
    try {
      await citizenFetch(path, citizenJSON({}, session.csrf_token));
      setRevision((value) => value + 1);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Could not update notifications",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="admin-card">
      <div className="admin-top">
        <div>
          <span className="eyebrow">Verified updates only</span>
          <h2>Your notifications</h2>
          <p aria-live="polite">{data?.unread_count ?? 0} unread</p>
        </div>
        <button
          className="button button-secondary"
          disabled={busy || !data?.unread_count}
          onClick={() => void mark("notifications/read-all")}
        >
          Mark all as read
        </button>
      </div>
      <label className="review-check">
        <input
          type="checkbox"
          checked={unread}
          onChange={(event) => {
            setUnread(event.target.checked);
            setPage(1);
          }}
        />
        Unread only
      </label>
      {error && (
        <ErrorState
          message={error}
          retry={() => setRevision((value) => value + 1)}
        />
      )}{" "}
      {!data ? (
        <LoadingState message="Loading private notifications…" />
      ) : !data.items.length ? (
        <p>
          No notifications here. Verified changes affecting your saved schemes
          will appear according to your{" "}
          <Link href="/dashboard/settings">preferences</Link>.
        </p>
      ) : (
        <>
          {data.items.map((item) => (
            <article className="review-condition" key={item.id}>
              <span className="eyebrow">
                {item.read_at ? "Read" : "Unread"} ·{" "}
                {item.notification_type.replaceAll("_", " ")}
              </span>
              <h3>{item.title}</h3>
              <p>{item.description}</p>
              <small>{new Date(item.created_at).toLocaleString()}</small>
              <div className="admin-actions">
                <Link className="text-link" href={`/schemes/${item.scheme_id}`}>
                  View scheme →
                </Link>
                {item.assessment_id && (
                  <Link
                    className="text-link"
                    href={`/dashboard/assessments/${item.assessment_id}`}
                  >
                    Review assessment →
                  </Link>
                )}
                {!item.read_at && (
                  <button
                    className="button button-secondary button-small"
                    disabled={busy}
                    onClick={() => void mark(`notifications/${item.id}/read`)}
                  >
                    Mark as read
                  </button>
                )}
              </div>
            </article>
          ))}
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
              disabled={page * 20 >= data.total}
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
