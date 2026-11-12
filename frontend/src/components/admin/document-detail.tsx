"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import {
  adminFetch,
  adminJSON,
  type IngestedDocument,
  type ProcessingJob,
} from "@/lib/admin";
import { ErrorState, LoadingState } from "@/components/ui";
import { EvidenceViewer } from "./evidence";
import { WorkflowStart } from "./workflow-start";
import { useAdmin } from "./session";

export function DocumentDetail({ id }: { id: string }) {
  const session = useAdmin();
  const [document, setDocument] = useState<IngestedDocument | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const [page, setPage] = useState(1);
  useEffect(() => {
    const controller = new AbortController();
    adminFetch<IngestedDocument>(`documents/${id}`, {
      signal: controller.signal,
    })
      .then((value) => {
        if (!controller.signal.aborted) setDocument(value);
      })
      .catch((reason: Error) => {
        if (!controller.signal.aborted) setError(reason.message);
      });
    return () => controller.abort();
  }, [id, refresh]);
  async function extract(mode: "parse_only" | "gemini") {
    setBusy(true);
    setError("");
    try {
      await adminFetch<ProcessingJob>(
        `documents/${id}/extract`,
        adminJSON({ mode }, session.csrf_token),
      );
      setRefresh((value) => value + 1);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Extraction could not start.",
      );
    } finally {
      setBusy(false);
    }
  }
  if (!document)
    return error ? (
      <ErrorState
        message={error}
        retry={() => {
          setError("");
          setRefresh((value) => value + 1);
        }}
      />
    ) : (
      <LoadingState message="Loading document…" />
    );
  return (
    <>
      <section className="admin-card">
        <Link className="text-link" href="/admin/documents">
          ← All documents
        </Link>
        <p className="eyebrow">
          Version {document.version_number} · {document.processing_status}
        </p>
        <h2>{document.original_filename}</h2>
        <p>{document.scheme_name}</p>
        <dl className="admin-metadata">
          <div>
            <dt>Pages / size</dt>
            <dd>
              {document.page_count} pages ·{" "}
              {Math.ceil(document.file_size / 1024)} KB
            </dd>
          </div>
          <div>
            <dt>Retrieved</dt>
            <dd>{new Date(document.retrieved_at).toLocaleString()}</dd>
          </div>
          <div>
            <dt>Publication date</dt>
            <dd>{document.publication_date || "Unknown"}</dd>
          </div>
          <div>
            <dt>SHA-256</dt>
            <dd className="admin-hash">{document.checksum}</dd>
          </div>
        </dl>
        <p>
          <a
            className="text-link"
            href={document.source_url}
            target="_blank"
            rel="noreferrer"
          >
            Official source ↗
          </a>{" "}
          ·{" "}
          <a className="text-link" href={`/api/admin/documents/${id}/original`}>
            Download preserved original
          </a>
        </p>
        <div className="admin-actions">
          <button
            className="button button-secondary"
            disabled={busy}
            onClick={() => void extract("parse_only")}
          >
            Extract text only
          </button>
          <button
            className="button button-primary"
            disabled={busy}
            onClick={() => void extract("gemini")}
          >
            Generate pending candidates
          </button>
        </div>
        {busy && (
          <LoadingState message="Processing this document. This may take up to 90 seconds…" />
        )}
        {error && (
          <p role="alert" className="form-error">
            {error}
          </p>
        )}
        <p className="small-note">
          Gemini receives bounded source text. Inspect its output as untrusted
          suggestions. Neither action publishes rules.
        </p>
      </section>
      <WorkflowStart document={document} />
      <section className="admin-card">
        <h2>Processing history</h2>
        {!document.jobs?.length ? (
          <p>No extraction jobs yet.</p>
        ) : (
          <div className="admin-document-list">
            {document.jobs.map((job) => (
              <article key={job.id}>
                <div>
                  <strong>{job.status}</strong>
                  <p>
                    {job.provider} {job.model || ""} · {job.candidate_count}{" "}
                    candidates
                  </p>
                  <small>{new Date(job.started_at).toLocaleString()}</small>
                </div>
                <Link
                  className="text-link"
                  href={`/admin/extractions/${job.id}`}
                >
                  Inspect extraction →
                </Link>
              </article>
            ))}
          </div>
        )}
      </section>
      {!!document.pages?.length && (
        <section className="admin-card">
          <label className="admin-form">
            Source page
            <select
              value={page}
              onChange={(event) => setPage(Number(event.target.value))}
            >
              {document.pages.map((item) => (
                <option key={item.page_number} value={item.page_number}>
                  Page {item.page_number}
                  {item.issues.length ? " — needs review" : ""}
                </option>
              ))}
            </select>
          </label>
          <EvidenceViewer documentId={id} pageNumber={page} />
        </section>
      )}
    </>
  );
}
