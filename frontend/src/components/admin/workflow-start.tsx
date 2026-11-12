"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { adminFetch, adminJSON, type IngestedDocument } from "@/lib/admin";
import type { Workflow } from "@/lib/workflow";
import { useAdmin } from "./session";

export function WorkflowStart({ document }: { document: IngestedDocument }) {
  const administrator = useAdmin();
  const router = useRouter();
  const [job, setJob] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [requestKey, setRequestKey] = useState<string | null>(null);
  async function start() {
    setBusy(true);
    setError("");
    setNotice("");
    const key = requestKey || crypto.randomUUID();
    setRequestKey(key);
    try {
      const workflow = await adminFetch<Workflow>(
        "workflows",
        adminJSON(
          {
            document_version_id: document.id,
            extraction_job_id: job || null,
            request_key: key,
          },
          administrator.csrf_token,
        ),
      );
      router.push(`/admin/workflows/${workflow.id}`);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Workflow could not start. Check the workflow list before retrying.",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="admin-card">
      <span className="eyebrow">Checkpointed processing</span>
      <h2>Start an agent workflow</h2>
      <p>
        Prepare this exact document, extract candidates, verify evidence, and
        pause for human review.
      </p>
      <label>
        Candidate extraction
        <select
          value={job}
          disabled={busy}
          onChange={(event) => {
            setJob(event.target.value);
            setRequestKey(null);
          }}
        >
          <option value="">Generate a new Gemini extraction</option>
          {document.jobs
            ?.filter(
              (item) =>
                ["PENDING_REVIEW", "INCOMPLETE"].includes(item.status) &&
                item.candidate_count > 0,
            )
            .map((item) => (
              <option value={item.id} key={item.id}>
                Reuse {item.provider}: {item.candidate_count} candidates ·{" "}
                {item.id.slice(0, 8)}
              </option>
            ))}
        </select>
      </label>
      <div className="admin-actions">
        <button
          className="button button-primary"
          disabled={busy}
          onClick={() => void start()}
        >
          {busy ? "Processing…" : "Start review workflow"}
        </button>
        <button
          className="button button-secondary"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            setError("");
            setNotice("");
            try {
              const result = await adminFetch<{
                indexed: number;
                preserved: number;
              }>(
                `documents/${document.id}/index`,
                adminJSON({}, administrator.csrf_token),
              );
              setNotice(
                `Indexed ${result.indexed} new chunks; ${result.preserved} existing embeddings preserved.`,
              );
            } catch (reason) {
              setError(
                reason instanceof Error ? reason.message : "Index unavailable",
              );
            } finally {
              setBusy(false);
            }
          }}
        >
          Index parsed chunks
        </button>
      </div>
      <p className="small-note">
        New extraction requires Gemini credentials. Reusing an extraction
        preserves its provider label. Indexing uses the configured embedding
        provider and does not approve a policy.
      </p>
      {busy && (
        <p role="status">
          Processing is bounded and may take several minutes. The workflow ID
          and history are persisted.
        </p>
      )}
      {error && (
        <p role="alert" className="form-error">
          {error}
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
    </section>
  );
}
