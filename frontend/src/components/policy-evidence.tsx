"use client";
import { useEffect, useState, type FormEvent } from "react";
import { apiFetch } from "@/lib/api";
import type { Citation, Explanation } from "@/lib/workflow";
import { LoadingState } from "./ui";
export function Citations({ items }: { items: Citation[] }) {
  return (
    <div className="source-list">
      {items.map((item) => (
        <article className="source-card" key={item.id}>
          <div>
            <h3>{item.source_title}</h3>
            <p>
              {item.publisher} ·{" "}
              {item.page_number ? `Page ${item.page_number}` : item.locator}
            </p>
            <blockquote>{item.excerpt}</blockquote>
            <a
              className="text-link"
              href={item.url}
              target="_blank"
              rel="noopener noreferrer"
            >
              Read cited source ↗
            </a>
            <p className="small-note admin-hash">
              Document SHA-256: {item.document_sha256}
            </p>
          </div>
        </article>
      ))}
    </div>
  );
}
export function GroundedExplanation({
  explanation,
}: {
  explanation: Explanation;
}) {
  return (
    <section className="detail-section">
      <span className="eyebrow">Source-grounded explanation</span>
      <h2>Your assessment, with evidence.</h2>
      <p>{explanation.summary}</p>
      <p className="small-note">
        Policy version {explanation.rule_version ?? "unavailable"} ·{" "}
        {explanation.mode === "deterministic_template"
          ? "Deterministic explanation"
          : "Verified trace ordering"}{" "}
        · {explanation.retrieval_mode.replaceAll("_", " ")}
      </p>
      <Citations items={explanation.citations} />
    </section>
  );
}
interface HistoryItem {
  id: string;
  version_number: number;
  title: string;
  effective_from: string;
  effective_to: string | null;
  scope_note: string;
  approved_at: string;
}
interface Answer {
  answer: string;
  citations: Citation[];
  notice: string;
}
export function PolicyEvidence({
  schemeId,
  available,
}: {
  schemeId: string;
  available: boolean;
}) {
  const [history, setHistory] = useState<HistoryItem[] | null>(null);
  const [error, setError] = useState("");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    apiFetch<{ items: HistoryItem[] }>(
      `/api/v1/schemes/${schemeId}/rule-history`,
      { signal: controller.signal },
    )
      .then((value) => {
        if (!controller.signal.aborted) setHistory(value.items);
      })
      .catch((reason: Error) => {
        if (!controller.signal.aborted) setError(reason.message);
      });
    return () => controller.abort();
  }, [schemeId]);
  async function ask(event: FormEvent) {
    event.preventDefault();
    if (question.trim().length < 5) return;
    setBusy(true);
    setError("");
    setAnswer(null);
    try {
      setAnswer(
        await apiFetch<Answer>(`/api/v1/schemes/${schemeId}/questions`, {
          method: "POST",
          body: JSON.stringify({ question: question.trim() }),
        }),
      );
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Evidence could not be retrieved",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <section id="policy-history" className="detail-section">
      <span className="eyebrow">Versioned policy evidence</span>
      <h2>Approved rule history</h2>
      {!history ? (
        <LoadingState message="Loading policy history…" />
      ) : history.length ? (
        history.map((item) => (
          <details className="source-card" key={item.id}>
            <summary>
              Version {item.version_number} · {item.title}
            </summary>
            <p>
              Effective: {item.effective_from} to{" "}
              {item.effective_to || "open ended"}
            </p>
            <p>
              Reviewed: {new Date(item.approved_at).toLocaleDateString("en-IN")}
            </p>
            <p>{item.scope_note}</p>
          </details>
        ))
      ) : (
        <p>
          No approved rule versions are available. Discovery metadata cannot
          establish eligibility.
        </p>
      )}
      {available && (
        <form onSubmit={(event) => void ask(event)} className="admin-card">
          <h3>Ask the approved document</h3>
          <p>
            Ask about requirements, income, documents, benefits or applications.
            Answers quote the source and cannot decide eligibility. Do not
            include personal information in your question.
          </p>
          <label htmlFor="policy-question">Your document question</label>
          <input
            id="policy-question"
            required
            minLength={5}
            maxLength={500}
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="What income limit does the source specify?"
          />
          <button
            className="button button-secondary"
            disabled={busy || question.trim().length < 5}
          >
            {busy ? "Finding evidence…" : "Find source passages"}
          </button>
        </form>
      )}
      {error && (
        <p role="alert" className="form-error">
          {error}
        </p>
      )}
      {answer && (
        <div role="status">
          <p>{answer.answer}</p>
          <Citations items={answer.citations} />
          <p className="small-note">{answer.notice}</p>
        </div>
      )}
    </section>
  );
}
