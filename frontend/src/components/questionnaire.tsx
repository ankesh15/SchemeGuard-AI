"use client";
import Link from "next/link";
import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  BookOpen,
  Check,
  ChevronRight,
  Info,
  LoaderCircle,
  LockKeyhole,
  RotateCcw,
  Sparkles,
} from "lucide-react";
import { apiFetch, ApiError } from "@/lib/api";
import {
  buildProfile,
  isVisible,
  validateAnswers,
  type Answers,
} from "@/lib/form";
import { categoryLabel } from "@/lib/catalog";
import type {
  AssessmentRequirements,
  EligibilityReport,
  ProfileField,
} from "@/lib/types";
import { assessmentPrefill } from "@/lib/recommendations";
import { useOptionalDiscovery } from "./discovery-context";
import { useReport } from "./report-context";
export function QuestionField({
  field,
  value,
  error,
  answers,
  onChange,
  disabled,
}: {
  field: ProfileField;
  value: string;
  error?: string;
  answers: Answers;
  onChange: (value: string) => void;
  disabled: boolean;
}) {
  if (!isVisible(field, answers)) return null;
  const common = {
    id: field.key,
    name: field.key,
    value,
    disabled,
    onChange: (
      event: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>,
    ) => onChange(event.target.value),
    "aria-invalid": !!error,
    "aria-describedby": `${field.key}-help${error ? ` ${field.key}-error` : ""}`,
  };
  return (
    <div className="question-field">
      <label htmlFor={field.key}>{field.label}</label>
      {field.value_type === "boolean" ? (
        <select {...common}>
          <option value="">Not sure yet</option>
          <option value="true">Yes</option>
          <option value="false">No</option>
        </select>
      ) : field.choices.length ? (
        <select {...common}>
          <option value="">Choose or leave unknown</option>
          {field.choices.map((choice) => (
            <option key={choice.value} value={choice.value}>
              {choice.label}
            </option>
          ))}
        </select>
      ) : (
        <input
          {...common}
          type={field.value_type === "date" ? "date" : "text"}
          inputMode={
            field.value_type === "number"
              ? field.integer
                ? "numeric"
                : "decimal"
              : undefined
          }
          autoComplete="off"
          maxLength={200}
          placeholder={
            field.value_type === "number" ? "Leave blank if unknown" : undefined
          }
        />
      )}
      <p id={`${field.key}-help`} className="field-help">
        {field.help_text ||
          "Optional. Leave unknown if you don’t have this information."}
      </p>
      {error && (
        <p id={`${field.key}-error`} className="field-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

export function Questionnaire({
  requirements,
}: {
  requirements: AssessmentRequirements;
}) {
  const router = useRouter();
  const { setReport, setExplanation } = useReport();
  const discovery = useOptionalDiscovery();
  const [answers, setAnswers] = useState<Answers>(() =>
    assessmentPrefill(requirements.fields, discovery?.profile || null),
  );
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const sections = [
    ...new Set(requirements.fields.map((field) => field.section)),
  ];
  const illustrative = requirements.assessment_mode === "ILLUSTRATIVE";
  const visible = requirements.fields.filter((field) =>
    isVisible(field, answers),
  );
  const answered = visible.filter((field) => answers[field.key]?.trim()).length;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting || !requirements.available) return;
    setError("");
    const validation = validateAnswers(requirements.fields, answers);
    setErrors(validation);
    if (Object.keys(validation).length) {
      setError("Please correct the highlighted fields before continuing.");
      document.getElementById(Object.keys(validation)[0])?.focus();
      return;
    }
    setSubmitting(true);
    setReport(null);
    setExplanation(null);
    try {
      const report = await apiFetch<EligibilityReport>(
        "/api/v1/assessment/check",
        {
          method: "POST",
          body: JSON.stringify({
            scheme_id: requirements.scheme_id,
            criteria_token: requirements.criteria_token,
            profile: buildProfile(requirements.fields, answers),
          }),
        },
      );
      setReport(report);
      router.push("/eligibility/report");
    } catch (reason) {
      if (reason instanceof ApiError) {
        const fieldErrors: Record<string, string> = {};
        reason.details.forEach((detail) => {
          const field = detail.location.at(-1);
          if (typeof field === "string") fieldErrors[field] = detail.message;
        });
        setErrors(fieldErrors);
        setError(
          reason.status === 409
            ? "The assessment criteria changed. Reload this questionnaire before trying again."
            : reason.status === 422
              ? "Please check the highlighted fields and try again."
              : "The assessment service is unavailable. Your details have not been saved. Please try again.",
        );
      } else
        setError(
          "We couldn’t reach the assessment service. Your details have not been saved. Please try again.",
        );
    } finally {
      setSubmitting(false);
    }
  }
  return (
    <div className="questionnaire-layout">
      <div>
        <Link className="back-link" href="/eligibility">
          Choose another scheme
        </Link>
        {!requirements.available ? (
          <div className="empty-state">
            <BookOpen size={32} />
            <h2>Assessment not available yet.</h2>
            <p>
              No applicable reviewed policy or suitable assessment template is
              available for this scheme. We don’t substitute unrelated criteria.
            </p>
            <Link className="button button-primary" href="/eligibility">
              Explore other schemes <ArrowRight size={17} />
            </Link>
          </div>
        ) : (
          <>
            <div className="assessment-basis">
              <span className="eyebrow">
                {illustrative
                  ? "Illustrative assessment"
                  : "Reviewed policy assessment"}
              </span>
              <p>
                {illustrative
                  ? "Uses project-authored criteria for this category. These are not verified government requirements."
                  : "Uses the applicable approved policy version and its supporting evidence."}
              </p>
            </div>
            <div className="form-intro">
              <div>
                <h2>Your details</h2>
                <p>
                  Answer what you know. Leave anything unavailable blank;
                  missing answers remain unresolved.
                </p>
              </div>
              <button
                className="text-link"
                type="button"
                disabled={submitting}
                onClick={() => {
                  setAnswers(
                    Object.fromEntries(
                      Object.entries(requirements.sample_profile)
                        .filter(([, value]) => value !== null)
                        .map(([key, value]) => [key, String(value)]),
                    ),
                  );
                  setErrors({});
                  setError("");
                }}
              >
                <Sparkles size={15} />
                Use Sample Details
              </button>
            </div>
            <form onSubmit={submit} noValidate>
              <div className="question-sections">
                {sections.map((section, index) => (
                  <section className="question-section" key={section}>
                    <div className="question-section-heading">
                      <span>{String(index + 1).padStart(2, "0")}</span>
                      <h3>{section}</h3>
                    </div>
                    <div className="question-grid">
                      {requirements.fields
                        .filter((field) => field.section === section)
                        .map((field) => (
                          <QuestionField
                            key={field.key}
                            field={field}
                            value={answers[field.key] || ""}
                            answers={answers}
                            error={errors[field.key]}
                            disabled={submitting}
                            onChange={(value) => {
                              setAnswers((previous) => ({
                                ...previous,
                                [field.key]: value,
                              }));
                              setErrors((previous) => {
                                const next = { ...previous };
                                delete next[field.key];
                                return next;
                              });
                            }}
                          />
                        ))}
                    </div>
                  </section>
                ))}
              </div>
              <p className="assessment-privacy small-note">
                <LockKeyhole size={15} />
                No name, Aadhaar number, contact details or documents are
                requested. This assessment is not saved to your account.
              </p>
              {error && (
                <div className="form-error" role="alert">
                  {error}
                  <button
                    className="text-link"
                    type="button"
                    onClick={() => router.refresh()}
                  >
                    Reload questionnaire
                  </button>
                </div>
              )}
              <div className="form-actions">
                <button
                  className="text-link"
                  type="button"
                  disabled={submitting}
                  onClick={() => {
                    setAnswers({});
                    setErrors({});
                    setError("");
                  }}
                >
                  <RotateCcw size={15} />
                  Clear answers
                </button>
                <button
                  className="button button-primary"
                  type="submit"
                  disabled={submitting}
                >
                  {submitting ? (
                    <>
                      <LoaderCircle size={17} className="animate-spin" />
                      Assessing criteria…
                    </>
                  ) : (
                    <>
                      Check Eligibility
                      <ArrowRight size={17} />
                    </>
                  )}
                </button>
              </div>
            </form>
          </>
        )}
      </div>
      <aside className="question-aside">
        <div className="aside-card">
          <span className="eyebrow">
            {categoryLabel(requirements.category)}
          </span>
          <h2>
            A few details.
            <br />A clearer picture.
          </h2>
          <div className="answer-progress">
            <div>
              <span>
                {answered} of {visible.length} answered
              </span>
              <span>
                {visible.length
                  ? Math.round((answered / visible.length) * 100)
                  : 0}
                %
              </span>
            </div>
            <progress
              value={answered}
              max={visible.length || 1}
              aria-label="Questionnaire answers completed"
            />
          </div>
          <ul className="assurance-list">
            <li>
              <Check size={17} />
              <span>
                <strong>Consistent by design</strong>The same criteria and
                details produce the same result.
              </span>
            </li>
            <li>
              <Info size={17} />
              <span>
                <strong>Clear about missing details</strong>Additional
                information is identified in your report.
              </span>
            </li>
            <li>
              <BookOpen size={17} />
              <span>
                <strong>Understand each criterion</strong>
                {illustrative
                  ? "The report explains the illustrative criteria used."
                  : "Reviewed conditions retain their policy evidence."}
              </span>
            </li>
          </ul>
          {requirements.requirements.length > 0 && (
            <details className="criteria-preview">
              <summary>View assessment criteria</summary>
              <ul>
                {requirements.requirements.map((item) => (
                  <li key={item.key}>
                    <strong>{item.label}</strong>
                    <p>
                      {requirements.criteria_notes[item.key] ||
                        item.evidence[0]?.excerpt}
                    </p>
                  </li>
                ))}
              </ul>
            </details>
          )}
          <div className="aside-divider" />
          <p className="small-note">
            {requirements.template
              ? `${requirements.template.title} · Criteria version ${requirements.template.version}`
              : requirements.rule_set
                ? `Reviewed policy version ${requirements.rule_set.version_number}`
                : "Assessment criteria unavailable"}
          </p>
          <Link
            className="text-link mt-4"
            href={`/schemes/${requirements.scheme_id}`}
          >
            View scheme details <ChevronRight size={15} />
          </Link>
        </div>
      </aside>
    </div>
  );
}
