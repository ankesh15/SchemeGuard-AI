"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { adminFetch, type AdminOverview } from "@/lib/admin";
import { ErrorState, LoadingState } from "@/components/ui";
export function Overview() {
  const [data, setData] = useState<AdminOverview | null>(null);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    adminFetch<AdminOverview>("overview", { signal: controller.signal })
      .then((value) => {
        if (!controller.signal.aborted) setData(value);
      })
      .catch((reason: Error) => {
        if (!controller.signal.aborted) setError(reason.message);
      });
    return () => controller.abort();
  }, [retry]);
  if (error)
    return (
      <ErrorState
        message={error}
        retry={() => {
          setError("");
          setRetry((value) => value + 1);
        }}
      />
    );
  if (!data) return <LoadingState message="Loading document workspace…" />;
  return (
    <>
      <div className="admin-stats">
        {[
          ["Original documents", data.documents],
          ["Pending candidates", data.pending_candidates],
          ["Pending human reviews", data.pending_reviews],
          ["Failed jobs", data.failed_jobs],
        ].map(([label, value]) => (
          <article className="aside-card" key={label}>
            <span className="eyebrow">{label}</span>
            <strong>{value}</strong>
          </article>
        ))}
      </div>
      <section className="admin-card">
        <h2>From policy PDF to reviewable evidence.</h2>
        <ol>
          <li>
            Authorize an exact official document source for an existing scheme.
          </li>
          <li>Upload a matching PDF or download it from the approved URL.</li>
          <li>
            Extract page-aware text, then generate structured candidate rules.
          </li>
          <li>
            Inspect every page, revise the complete proposal, and record a human
            approval or rejection.
          </li>
        </ol>
        <Link href="/admin/documents" className="button button-primary">
          Manage documents
        </Link>
        <Link href="/admin/reviews" className="button button-secondary">
          Open human review queue
        </Link>
      </section>
      <section className="admin-card">
        <h2>Extraction configuration</h2>
        <p>
          Gemini:{" "}
          <strong>
            {data.gemini_configured
              ? "Configured"
              : "Credentials not configured"}
          </strong>{" "}
          · Model: {data.gemini_model}
        </p>
        <p>
          PDF limit: {Math.round(data.pdf_max_bytes / 1024 / 1024)} MB ·{" "}
          {data.pdf_max_pages} pages
        </p>
        {!data.gemini_configured && (
          <p className="small-note">
            Text extraction works without Gemini credentials. A project operator
            can configure the API key on the backend. No key is entered or
            displayed here.
          </p>
        )}
      </section>
    </>
  );
}
