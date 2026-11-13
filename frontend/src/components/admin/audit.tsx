"use client";
import { useEffect, useState } from "react";
import { adminFetch } from "@/lib/admin";
import { ErrorState, LoadingState } from "@/components/ui";
export function AuditLog() {
  const [events, setEvents] = useState<
    | {
        id: string;
        action: string;
        actor_id: string | null;
        target_id: string | null;
        created_at: string;
      }[]
    | null
  >(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    adminFetch<NonNullable<typeof events>>("audit", {
      signal: controller.signal,
    })
      .then((value) => {
        if (!controller.signal.aborted) setEvents(value);
      })
      .catch((reason: Error) => {
        if (!controller.signal.aborted) setError(reason.message);
      });
    return () => controller.abort();
  }, []);
  return (
    <section className="admin-card">
      <h2>Security & policy audit</h2>
      <p>
        Latest 100 actions. This view contains account identifiers and policy
        references, never decrypted applicant inputs.
      </p>
      {error ? (
        <ErrorState message={error} />
      ) : !events ? (
        <LoadingState message="Loading protected audit events…" />
      ) : !events.length ? (
        <p>No audit events.</p>
      ) : (
        events.map((event) => (
          <article key={event.id} className="review-condition">
            <strong>{event.action.replaceAll("_", " ")}</strong>
            <p>{new Date(event.created_at).toLocaleString()}</p>
            <p className="small-note admin-hash">
              Actor: {event.actor_id || "Unauthenticated"} · Target:{" "}
              {event.target_id || "—"}
            </p>
          </article>
        ))
      )}
    </section>
  );
}
