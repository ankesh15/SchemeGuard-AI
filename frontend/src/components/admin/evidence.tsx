"use client";
import { useEffect, useState } from "react";
import { adminFetch, type ParsedPage } from "@/lib/admin";
import { ErrorState, LoadingState } from "@/components/ui";

export function EvidenceViewer({
  documentId,
  pageNumber,
  excerpt,
}: {
  documentId: string;
  pageNumber: number;
  excerpt?: string;
}) {
  const [page, setPage] = useState<ParsedPage | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    setPage(null);
    setError("");
    adminFetch<ParsedPage>(`documents/${documentId}/pages/${pageNumber}`, {
      signal: controller.signal,
    })
      .then((value) => {
        if (!controller.signal.aborted) setPage(value);
      })
      .catch((reason: Error) => {
        if (!controller.signal.aborted) setError(reason.message);
      });
    return () => controller.abort();
  }, [documentId, pageNumber]);
  return (
    <section
      className="admin-evidence"
      aria-label={`Source evidence page ${pageNumber}`}
    >
      <h3>Source page {pageNumber}</h3>
      {excerpt && <blockquote>{excerpt}</blockquote>}
      {error ? (
        <ErrorState message={error} />
      ) : !page ? (
        <LoadingState message="Loading source page…" />
      ) : (
        <>
          <p className="small-note">
            Extraction: {page.extraction_method}. Text is untrusted source
            content; verify against the original PDF.
          </p>
          {page.issues.map((issue) => (
            <p role="status" key={issue}>
              {issue}
            </p>
          ))}
          <pre className="admin-page-text">
            {page.text_content ||
              "No readable text on this page. Manual review is required."}
          </pre>
        </>
      )}
    </section>
  );
}
