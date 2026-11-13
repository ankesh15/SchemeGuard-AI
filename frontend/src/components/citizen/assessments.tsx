"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import {
  citizenFetch,
  citizenJSON,
  type SavedAssessment,
  type ProfileRead,
} from "@/lib/citizen";
import { apiFetch } from "@/lib/api";
import type { SchemePage, Requirements } from "@/lib/types";
import { ErrorState, LoadingState } from "@/components/ui";
import { EligibilityReportView } from "@/components/eligibility-report";
import { QuestionField } from "@/components/questionnaire";
import { buildProfile, validateAnswers, type Answers } from "@/lib/form";
import { useCitizen } from "./session";
export function SavedAssessments() {
  const [data, setData] = useState<{
    items: SavedAssessment[];
    total: number;
  } | null>(null);
  const [page, setPage] = useState(1);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    setError("");
    setData(null);
    citizenFetch<typeof data>(`assessments?page=${page}`, {
      signal: controller.signal,
    })
      .then((value) => {
        if (!controller.signal.aborted) setData(value);
      })
      .catch((reason: Error) => {
        if (!controller.signal.aborted) setError(reason.message);
      });
    return () => controller.abort();
  }, [page]);
  return (
    <section className="admin-card">
      <div className="admin-top">
        <div>
          <span className="eyebrow">Immutable policy references</span>
          <h2>Your saved assessments</h2>
        </div>
        <Link
          className="button button-primary"
          href="/dashboard/assessments/new"
        >
          Create an assessment
        </Link>
      </div>
      {error ? (
        <ErrorState message={error} />
      ) : !data ? (
        <LoadingState message="Loading private history…" />
      ) : !data.items.length ? (
        <p>
          No assessments saved. You can still use the public synthetic demo
          without an account.
        </p>
      ) : (
        <>
          <div className="admin-document-list">
            {data.items.map((item) => (
              <article key={item.id}>
                <div>
                  <strong>{item.scheme_name}</strong>
                  <p>
                    {item.assessment} · Version{" "}
                    {item.rule_version ?? "unavailable"}
                  </p>
                  <small>
                    {new Date(item.created_at).toLocaleString()}
                    {item.parent_id ? " · Reassessment" : ""}
                  </small>
                </div>
                <Link
                  className="text-link"
                  href={`/dashboard/assessments/${item.id}`}
                >
                  Read assessment →
                </Link>
              </article>
            ))}
          </div>
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
export function SavedAssessmentDetail({ id }: { id: string }) {
  const session = useCitizen();
  const [data, setData] = useState<SavedAssessment | null>(null);
  const [error, setError] = useState("");
  const [replay, setReplay] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const controller = new AbortController();
    citizenFetch<SavedAssessment>(`assessments/${id}`, {
      signal: controller.signal,
    })
      .then((value) => {
        if (!controller.signal.aborted) setData(value);
      })
      .catch((reason: Error) => {
        if (!controller.signal.aborted) setError(reason.message);
      });
    return () => controller.abort();
  }, [id]);
  if (!data)
    return error ? (
      <ErrorState message={error} />
    ) : (
      <LoadingState message="Loading the original saved report…" />
    );
  return (
    <>
      <section className="admin-card">
        <span className="eyebrow">Private historical assessment</span>
        <p>
          Saved {new Date(data.created_at).toLocaleString()} · Assessment date{" "}
          {data.assessed_on} · Pinned policy version{" "}
          {data.rule_version ?? "unavailable"}
        </p>
        <p>Later policy updates never overwrite this result.</p>
        {data.current_policy_currency === "POTENTIALLY_OUTDATED" && (
          <div role="status" className="notice">
            The scheme source currently needs verification. This report
            preserves its original policy evidence; confirm current requirements
            at the official source before applying.
          </div>
        )}
        {data.parent_id && (
          <Link
            className="text-link"
            href={`/dashboard/assessments/${data.parent_id}`}
          >
            View the preserved previous assessment →
          </Link>
        )}
        {data.impact && (
          <details>
            <summary>What changed in this reassessment</summary>
            <pre className="admin-page-text">
              {JSON.stringify(data.impact, null, 2)}
            </pre>
          </details>
        )}
        <button
          className="button button-secondary"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            setError("");
            try {
              const result = await citizenFetch<{ matches_original: boolean }>(
                `assessments/${id}/reproduce`,
                citizenJSON({}, session.csrf_token),
              );
              setReplay(
                result.matches_original
                  ? "Reproduction matched the original result and rule traces."
                  : "Reproduction differs; contact the project operator.",
              );
            } catch (reason) {
              setError(
                reason instanceof Error
                  ? reason.message
                  : "Reproduction unavailable",
              );
            } finally {
              setBusy(false);
            }
          }}
        >
          Verify reproducibility
        </button>
        {replay && <p role="status">{replay}</p>}
        {error && <p role="alert">{error}</p>}
      </section>
      {data.report && <EligibilityReportView report={data.report} />}
    </>
  );
}
export function NewAssessment({
  initialScheme = "",
}: {
  initialScheme?: string;
}) {
  const session = useCitizen();
  const router = useRouter();
  const [schemes, setSchemes] = useState<SchemePage | null>(null);
  const [id, setId] = useState(initialScheme);
  const [requirements, setRequirements] = useState<Requirements | null>(null);
  const [answers, setAnswers] = useState<Answers>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [consent, setConsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [key, setKey] = useState<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    apiFetch<SchemePage>(
      "/api/v1/schemes?eligibility_available=true&page_size=100",
      { signal: controller.signal },
    )
      .then((value) => {
        if (!controller.signal.aborted) {
          setSchemes(value);
          if (!initialScheme) setId(value.items[0]?.id || "");
        }
      })
      .catch((reason: Error) => {
        if (!controller.signal.aborted) setError(reason.message);
      });
    return () => controller.abort();
  }, [initialScheme]);
  useEffect(() => {
    if (!id) return;
    const controller = new AbortController();
    setRequirements(null);
    setError("");
    setKey(null);
    Promise.all([
      apiFetch<Requirements>(
        `/api/v1/schemes/${encodeURIComponent(id)}/requirements`,
        { signal: controller.signal },
      ),
      citizenFetch<ProfileRead>("profiles/me", { signal: controller.signal }),
    ])
      .then(([rules, profile]) => {
        if (controller.signal.aborted) return;
        setRequirements(rules);
        const values = {
          ...profile.profile,
          ...profile.profile.attributes,
          ...(profile.profile.age_years !== null
            ? { age: profile.profile.age_years }
            : {}),
          ...(profile.profile.annual_family_income_inr !== null
            ? { annual_income_inr: profile.profile.annual_family_income_inr }
            : {}),
        };
        setAnswers(
          Object.fromEntries(
            rules.fields.map((field) => [
              field.key,
              (values as Record<string, unknown>)[field.key] === null ||
              (values as Record<string, unknown>)[field.key] === undefined
                ? ""
                : String((values as Record<string, unknown>)[field.key]),
            ]),
          ),
        );
      })
      .catch((reason: Error) => {
        if (!controller.signal.aborted) setError(reason.message);
      });
    return () => controller.abort();
  }, [id]);
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!requirements?.available) return;
    const validation = validateAnswers(requirements.fields, answers);
    setErrors(validation);
    if (Object.keys(validation).length) {
      setError("Correct the highlighted input fields.");
      return;
    }
    setBusy(true);
    setError("");
    const requestKey = key || crypto.randomUUID();
    setKey(requestKey);
    try {
      const saved = await citizenFetch<SavedAssessment>(
        "assessments",
        citizenJSON(
          {
            scheme_id: id,
            request_key: requestKey,
            use_saved_profile: false,
            profile: buildProfile(requirements.fields, answers),
            allow_reassessment: consent,
          },
          session.csrf_token,
        ),
      );
      router.push(`/dashboard/assessments/${saved.id}`);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Assessment could not be saved",
      );
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="admin-card">
      <span className="eyebrow">Deterministic assessment</span>
      <h2>Save an assessment with its evidence.</h2>
      <p>
        Only supported approved policies can be assessed. This saves a private
        report and the minimal encrypted inputs needed to reproduce it. Missing
        answers remain unknown.
      </p>
      <label>
        Scheme
        <select
          value={id}
          disabled={busy}
          onChange={(event) => {
            setId(event.target.value);
            setConsent(false);
          }}
        >
          <option value="">Select a supported scheme</option>
          {initialScheme &&
            !schemes?.items.some((item) => item.id === initialScheme) && (
              <option value={initialScheme}>
                {requirements?.scheme_name || "Selected scheme"}
              </option>
            )}
          {schemes?.items.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name}
            </option>
          ))}
        </select>
      </label>
      {error && (
        <p role="alert" className="form-error">
          {error}
        </p>
      )}
      {!schemes ? (
        <LoadingState message="Loading supported schemes…" />
      ) : !id ? (
        <p>
          No approved schemes are available.{" "}
          <Link href="/schemes">Browse discovery metadata</Link>.
        </p>
      ) : !requirements ? (
        <LoadingState message="Loading the approved questionnaire…" />
      ) : !requirements.available ? (
        <div className="notice">
          <p>
            No approved eligibility policy exists for this scheme. Metadata
            alone cannot produce an eligibility assessment.
          </p>
        </div>
      ) : (
        <form
          className="admin-form"
          onSubmit={(event) => void submit(event)}
          noValidate
        >
          <p>
            {requirements.scheme_name} · Rule version{" "}
            {requirements.rule_set?.version_number}
          </p>
          {requirements.is_demo && (
            <div className="notice">
              <p>
                Fictional development policy. All thresholds are invented and no
                government award is offered.
              </p>
            </div>
          )}
          <div className="admin-form-grid">
            {requirements.fields.map((field) => (
              <QuestionField
                key={field.key}
                field={field}
                value={answers[field.key] || ""}
                answers={answers}
                error={errors[field.key]}
                disabled={busy}
                onChange={(value) => {
                  setAnswers((old) => ({ ...old, [field.key]: value }));
                  setKey(null);
                }}
              />
            ))}
          </div>
          <label className="review-check">
            <input
              type="checkbox"
              checked={consent}
              onChange={(event) => {
                setConsent(event.target.checked);
                setKey(null);
              }}
              disabled={busy}
            />
            Allow automatic reassessment of this saved scheme after verified
            material policy updates, using my then-current stored profile and
            notification preferences.
          </label>
          <p className="small-note">
            Questionnaire edits are used for this saved report. Update your
            stored profile separately if they should be used in future
            reassessment.
          </p>
          <button className="button button-primary" disabled={busy}>
            {busy ? "Evaluating…" : "Evaluate & save privately"}
          </button>
        </form>
      )}
    </section>
  );
}
