"use client";
import type { Explanation } from "@/lib/workflow";
import Link from "next/link";
import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  BookOpen,
  Check,
  ChevronRight,
  FlaskConical,
  Info,
  LoaderCircle,
  LockKeyhole,
  RotateCcw,
} from "lucide-react";
import { apiFetch, ApiError } from "@/lib/api";
import {
  buildProfile,
  exampleAnswers,
  isVisible,
  validateAnswers,
  type Answers,
} from "@/lib/form";
import type {
  EligibilityReport,
  ProfileField,
  Requirements,
  Scheme,
} from "@/lib/types";
import { useReport } from "./report-context";
import { DemoNotice } from "./ui";

function QuestionField({
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
  schemes,
}: {
  requirements: Requirements;
  schemes: Scheme[];
}) {
  const router = useRouter();
  const { setReport, setExplanation } = useReport();
  const [answers, setAnswers] = useState<Answers>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [confirmed, setConfirmed] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const sections = [
    ...new Set(requirements.fields.map((field) => field.section)),
  ];
  const demo = schemes.find((scheme) => scheme.is_demo);
  const answered = requirements.fields.filter(
    (field) => isVisible(field, answers) && answers[field.key]?.trim(),
  ).length;
  const visibleCount = requirements.fields.filter((field) =>
    isVisible(field, answers),
  ).length;
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    const validation = validateAnswers(requirements.fields, answers);
    setErrors(validation);
    if (!confirmed) {
      setError("Confirm that you are using synthetic information.");
      return;
    }
    if (Object.keys(validation).length) {
      setError("Please correct the highlighted fields before continuing.");
      document.getElementById(Object.keys(validation)[0])?.focus();
      return;
    }
    setSubmitting(true);
    setReport(null);
    setExplanation(null);
    try {
      const data = await apiFetch<{
        report: EligibilityReport;
        explanation: Explanation;
      }>("/api/v1/eligibility/explain", {
        method: "POST",
        body: JSON.stringify({
          scheme_id: requirements.scheme_id,
          synthetic_profile: true,
          profile: buildProfile(requirements.fields, answers),
        }),
      });
      setReport(data.report);
      setExplanation(data.explanation);
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
          reason.status === 422
            ? "Please check the highlighted fields and try again."
            : "The assessment service is unavailable. Your information has not been saved. Please try again.",
        );
      } else
        setError(
          "We couldn’t reach the assessment service. Your information has not been saved. Please try again.",
        );
      setSubmitting(false);
    }
  }
  return (
    <div className="questionnaire-layout">
      <div>
        <div className="scheme-selector">
          <label htmlFor="selected-scheme">Selected scheme</label>
          <select
            id="selected-scheme"
            value={requirements.scheme_id}
            disabled={submitting}
            onChange={(event) =>
              router.push(`/eligibility?scheme=${event.target.value}`)
            }
          >
            {schemes.map((scheme) => (
              <option key={scheme.id} value={scheme.id}>
                {scheme.name}
              </option>
            ))}
          </select>
        </div>
        {!requirements.available ? (
          <div className="empty-state">
            <BookOpen size={32} />
            <h2>More verified information is needed.</h2>
            <p>
              No approved rule set is available for this scheme. Its metadata
              alone cannot support an eligibility assessment.
            </p>
            {demo && (
              <Link
                className="button button-primary"
                href={`/eligibility?scheme=${demo.id}`}
              >
                Try the fictional scholarship <ArrowRight size={17} />
              </Link>
            )}
          </div>
        ) : (
          <>
            {requirements.is_demo && <DemoNotice />}
            <div className="form-intro">
              <div>
                <h2>A synthetic profile, at your pace.</h2>
                <p>
                  Answer what you know. Blank answers become unknown, never an
                  assumed pass.
                </p>
              </div>
              <button
                className="text-link"
                type="button"
                disabled={submitting}
                onClick={() => {
                  setAnswers({ ...exampleAnswers });
                  setConfirmed(true);
                  setErrors({});
                  setError("");
                }}
              >
                <FlaskConical size={15} />
                Use a synthetic example
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
              <div className="form-confirm">
                <label>
                  <input
                    type="checkbox"
                    checked={confirmed}
                    disabled={submitting}
                    onChange={(event) => {
                      setConfirmed(event.target.checked);
                      setError("");
                    }}
                  />
                  <span>
                    I’m using fictional information for this development check.
                  </span>
                </label>
                <p>
                  <LockKeyhole size={14} />
                  No name, Aadhaar number, contact details, or documents are
                  requested. This profile and its report are not saved.
                </p>
              </div>
              {error && (
                <div className="form-error" role="alert">
                  {error}
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
                    setConfirmed(false);
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
                      Assessing conditions…
                    </>
                  ) : (
                    <>
                      See my assessment
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
          <span className="eyebrow">Your check, explained</span>
          <h2>
            A few details.
            <br />A clearer picture.
          </h2>
          <div className="answer-progress">
            <div>
              <span>
                {answered} of {visibleCount} answered
              </span>
              <span>
                {visibleCount ? Math.round((answered / visibleCount) * 100) : 0}
                %
              </span>
            </div>
            <progress
              value={answered}
              max={visibleCount || 1}
              aria-label="Questionnaire answers completed"
            />
          </div>
          <ul className="assurance-list">
            <li>
              <Check size={17} />
              <span>
                <strong>Consistent by design</strong>The same policy and profile
                produce the same assessment.
              </span>
            </li>
            <li>
              <Info size={17} />
              <span>
                <strong>Honest about unknowns</strong>Missing information is
                shown clearly in your report.
              </span>
            </li>
            <li>
              <BookOpen size={17} />
              <span>
                <strong>Evidence within reach</strong>Every requirement links to
                its policy section.
              </span>
            </li>
          </ul>
          <div className="aside-divider" />
          <p className="small-note">
            {requirements.rule_set
              ? `Policy v${requirements.rule_set.version_number} · ${requirements.is_demo ? "Fictional development fixture" : "Approved rules"}`
              : "No effective approved rules"}
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
