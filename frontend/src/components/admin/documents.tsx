"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import {
  adminFetch,
  adminJSON,
  type ApprovedSource,
  type IngestedDocument,
  type ResultPage,
} from "@/lib/admin";
import type { Scheme, SchemePage } from "@/lib/types";
import { useAdmin } from "./session";
import { ErrorState, LoadingState } from "@/components/ui";
export function Documents() {
  const session = useAdmin();
  const [documents, setDocuments] =
    useState<ResultPage<IngestedDocument> | null>(null);
  const [sources, setSources] = useState<ApprovedSource[]>([]);
  const [schemes, setSchemes] = useState<Scheme[]>([]);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState("");
  const [source, setSource] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [page, setPage] = useState(1);
  const [file, setFile] = useState<File | null>(null);
  const [attested, setAttested] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      adminFetch<ResultPage<IngestedDocument>>(`documents?page=${page}`, {
        signal: controller.signal,
      }),
      adminFetch<ApprovedSource[]>("sources", { signal: controller.signal }),
    ])
      .then(([items, approved]) => {
        if (!controller.signal.aborted) {
          setDocuments(items);
          setSources(approved);
        }
      })
      .catch((reason: Error) => {
        if (!controller.signal.aborted) setError(reason.message);
      });
    return () => controller.abort();
  }, [refresh, page]);
  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(() => {
      adminFetch<SchemePage>(
        `schemes?page_size=20${search.trim() ? `&search=${encodeURIComponent(search.trim())}` : ""}`,
        { signal: controller.signal },
      )
        .then((data) => {
          if (!controller.signal.aborted)
            setSchemes(data.items.filter((item) => !item.is_demo));
        })
        .catch((reason: Error) => {
          if (!controller.signal.aborted) setError(reason.message);
        });
    }, 250);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [search]);
  async function perform(action: () => Promise<unknown>, message: string) {
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      await action();
      setSuccess(message);
      setRefresh((value) => value + 1);
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Document operation failed.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="admin-section-heading">
        <h2>Documents & authorized sources</h2>
        <p>
          Keep each PDF attached to the correct scheme and exact official URL.
        </p>
      </div>
      {error && (
        <div className="form-error" role="alert">
          {error}{" "}
          <button
            className="text-link"
            onClick={() => {
              setError("");
              setRefresh((value) => value + 1);
            }}
          >
            Retry
          </button>
        </div>
      )}
      {success && (
        <p className="notice" role="status">
          {success}
        </p>
      )}
      <div className="admin-grid">
        <section className="admin-card">
          <h2>Authorize an official source</h2>
          <form
            className="admin-form"
            onSubmit={(event) => {
              event.preventDefault();
              const values = new FormData(event.currentTarget);
              if (!selected) {
                setError("Select a government scheme first.");
                return;
              }
              if (values.get("authorized") !== "on") {
                setError(
                  "Confirm that the source is an authorized public document.",
                );
                return;
              }
              void perform(async () => {
                const approved = await adminFetch<ApprovedSource>(
                  "sources",
                  adminJSON(
                    {
                      scheme_id: selected,
                      url: values.get("url"),
                      title: values.get("title"),
                      publisher: values.get("publisher"),
                      notes: values.get("notes"),
                      authorized_public_document: true,
                    },
                    session.csrf_token,
                  ),
                );
                setSource(approved.source_id);
              }, "Source authorized for document ingestion. This does not approve any policy rules.");
            }}
          >
            <label>
              Find a scheme
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search the government catalog…"
                maxLength={200}
              />
            </label>
            <label>
              Government scheme
              <select
                value={selected}
                onChange={(event) => setSelected(event.target.value)}
                required
              >
                <option value="">Select a scheme</option>
                {schemes.map((item) => (
                  <option value={item.id} key={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Official PDF URL
              <input
                name="url"
                type="url"
                required
                maxLength={2000}
                placeholder="https://official.gov.in/policy.pdf"
              />
            </label>
            <label>
              Document title
              <input name="title" required minLength={3} maxLength={300} />
            </label>
            <label>
              Official publisher
              <input name="publisher" required minLength={3} maxLength={200} />
            </label>
            <label>
              Source verification notes
              <textarea
                name="notes"
                required
                minLength={20}
                maxLength={2000}
                placeholder="How this source identifies the scheme and document…"
              />
            </label>
            <label className="admin-checkbox">
              <input name="authorized" type="checkbox" />I verified that this is
              an authorized public official document for the selected scheme.
            </label>
            <button className="button button-primary" disabled={busy}>
              {busy ? "Working…" : "Authorize source"}
            </button>
          </form>
        </section>
        <section className="admin-card">
          <h2>Register an original PDF</h2>
          <div className="admin-form">
            <label>
              Authorized source
              <select
                value={source}
                onChange={(event) => setSource(event.target.value)}
              >
                <option value="">Select an approved source</option>
                {sources
                  .filter((item) => !item.revoked_at)
                  .map((item) => (
                    <option value={item.source_id} key={item.source_id}>
                      {item.scheme_name} — {item.title}
                    </option>
                  ))}
              </select>
            </label>
            <p className="small-note">
              Downloads use the exact approved URL. Redirects and private
              network destinations are rejected.
            </p>
            <button
              className="button button-secondary"
              disabled={busy || !source}
              onClick={() =>
                void perform(
                  () =>
                    adminFetch(
                      "documents",
                      adminJSON({ source_id: source }, session.csrf_token),
                    ),
                  "Official PDF downloaded and registered. Identical source versions are preserved without duplication.",
                )
              }
            >
              Download approved PDF
            </button>
            <div className="aside-divider" />
            <label>
              Upload a matching PDF
              <input
                type="file"
                accept="application/pdf,.pdf"
                onChange={(event) => setFile(event.target.files?.[0] || null)}
              />
            </label>
            <label className="admin-checkbox">
              <input
                type="checkbox"
                checked={attested}
                onChange={(event) => setAttested(event.target.checked)}
              />
              This PDF matches the selected scheme and approved source.
            </label>
            <button
              className="button button-primary"
              disabled={busy || !source}
              onClick={() => {
                if (!file || !attested) {
                  setError(
                    "Choose a PDF and confirm that it matches the selected source.",
                  );
                  return;
                }
                if (
                  !file.name.toLowerCase().endsWith(".pdf") ||
                  file.size > 10 * 1024 * 1024
                ) {
                  setError("Choose a PDF no larger than 10 MB.");
                  return;
                }
                void perform(
                  () =>
                    adminFetch(
                      `documents?source_id=${source}&original_filename=${encodeURIComponent(file.name)}&attested=true`,
                      {
                        method: "POST",
                        headers: {
                          "Content-Type": "application/pdf",
                          "X-CSRF-Token": session.csrf_token,
                        },
                        body: file,
                      },
                    ),
                  "PDF uploaded and registered. Its original bytes and version are preserved.",
                );
              }}
            >
              Upload PDF
            </button>
            <p className="small-note">
              Only public scheme policy PDFs. Maximum 10 MB and 50 pages by
              default. File contents are validated by the backend.
            </p>
          </div>
        </section>
      </div>
      <section className="admin-card">
        <h2>Registered document versions</h2>
        {!documents ? (
          <LoadingState />
        ) : !documents.items.length ? (
          <p>
            No original PDFs registered yet. Authorize a source and add its
            document above.
          </p>
        ) : (
          <div className="admin-document-list">
            {documents.items.map((item) => (
              <article key={item.id}>
                <div>
                  <span className="eyebrow">
                    Version {item.version_number} · {item.processing_status}
                  </span>
                  <h3>
                    <Link href={`/admin/documents/${item.id}`}>
                      {item.original_filename}
                    </Link>
                  </h3>
                  <p>{item.scheme_name}</p>
                  <small>
                    {item.page_count} pages · {Math.ceil(item.file_size / 1024)}{" "}
                    KB
                  </small>
                </div>
                <Link
                  className="text-link"
                  href={`/admin/documents/${item.id}`}
                >
                  Inspect document →
                </Link>
              </article>
            ))}
          </div>
        )}
        {documents && documents.total > documents.page_size && (
          <nav className="pagination" aria-label="Document pagination">
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
              disabled={page * documents.page_size >= documents.total}
              onClick={() => setPage((value) => value + 1)}
            >
              Next
            </button>
          </nav>
        )}
      </section>
    </>
  );
}
