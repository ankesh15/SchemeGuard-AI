"use client";
import Link from "next/link";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { ArrowLeft, ArrowRight, Check, LockKeyhole } from "lucide-react";
import { apiFetch } from "@/lib/api";
import { AdminError } from "@/lib/admin";
import {
  citizenFetch,
  citizenJSON,
  type CitizenSession,
  type ProfileData,
  type ProfileRead,
} from "@/lib/citizen";
import {
  discoveryProfile,
  emptyProfile,
  profileAnswers,
  type DiscoveryOptions,
} from "@/lib/recommendations";
import { validateAnswers, type Answers } from "@/lib/form";
import type { ProfileField } from "@/lib/types";
import { QuestionField } from "./questionnaire";
import { useDiscovery } from "./discovery-context";
import { ErrorState, LoadingState, ProjectDisclaimer } from "./ui";

const steps = [
  "Personal details",
  "Education",
  "Employment",
  "Financial information",
  "Interests and needs",
];
const choices = (values: string[]) =>
  values.map((value) => ({
    value,
    label: value
      .replaceAll("_", " ")
      .replace(/^./, (char) => char.toUpperCase()),
  }));
function fields(options: DiscoveryOptions): ProfileField[][] {
  const field = (
    key: string,
    label: string,
    value_type: ProfileField["value_type"],
    extra: Partial<ProfileField> = {},
  ): ProfileField => ({
    key,
    label,
    value_type,
    section: "About you",
    help_text: "Optional. Leave blank or choose unknown if you prefer.",
    choices: [],
    integer: false,
    minimum: null,
    maximum: null,
    visible_when: null,
    ...extra,
  });
  return [
    [
      field("age_years", "Age in years", "number", {
        integer: true,
        minimum: 0,
        maximum: 130,
      }),
      field("state", "State or union territory", "string", {
        choices: choices(options.states).map((item) => ({
          ...item,
          label: item.value,
        })),
      }),
    ],
    [
      field("course_level", "Education level", "string", {
        choices: choices([
          "primary",
          "secondary",
          "higher_secondary",
          "diploma",
          "undergraduate",
          "postgraduate",
          "other",
        ]),
      }),
      field("current_student", "Currently a student?", "boolean"),
      field("field_of_study", "Course or field of study", "string", {
        help_text:
          "Optional, up to 80 characters. This is not used to infer scheme requirements.",
        visible_when: { field: "current_student", equals: true },
      }),
    ],
    [
      field("occupation", "Occupation", "string", {
        choices: choices([
          "student",
          "employed",
          "self_employed",
          "unemployed",
          "retired",
          "other",
        ]),
      }),
      field("employment_status", "Employment status", "string", {
        choices: choices([
          "unemployed",
          "part_time",
          "full_time",
          "self_employed",
          "retired",
          "other",
        ]),
      }),
    ],
    [
      field(
        "annual_family_income_inr",
        "Annual family income (INR)",
        "number",
        {
          minimum: 0,
          maximum: 1e12,
          help_text:
            "Sensitive and optional. Only reviewed policy rules can use income to refine a match. You can leave it unknown.",
        },
      ),
    ],
    [],
  ];
}
export function DiscoveryForm() {
  const router = useRouter();
  const { profile, ownerId, setProfile } = useDiscovery();
  const [base, setBase] = useState<ProfileData | null>(null);
  const [options, setOptions] = useState<DiscoveryOptions | null>(null);
  const [session, setSession] = useState<CitizenSession | null>(null);
  const [answers, setAnswers] = useState<Answers>({});
  const [interests, setInterests] = useState<string[]>([]);
  const [step, setStep] = useState(0);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [save, setSave] = useState(false);
  const [busy, setBusy] = useState(false);
  const [retry, setRetry] = useState(0);
  const heading = useRef<HTMLHeadingElement>(null);
  const initialProfile = useRef(profile);
  const initialOwner = useRef(ownerId);
  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      const ownProfile = async () => {
        try {
          const account = await citizenFetch<CitizenSession>("me", {
            signal: controller.signal,
          });
          if (account.role !== "citizen") return { account: null, data: null };
          const data = await citizenFetch<ProfileRead>("profiles/me", {
            signal: controller.signal,
          });
          return { account, data };
        } catch (reason) {
          if (reason instanceof AdminError && reason.status === 401)
            return { account: null, data: null };
          throw reason;
        }
      };
      try {
        const [settings, own] = await Promise.all([
          apiFetch<DiscoveryOptions>("/api/v1/recommendations/options", {
            signal: controller.signal,
          }),
          ownProfile(),
        ]);
        if (controller.signal.aborted) return;
        const reusable =
          !initialOwner.current ||
          initialOwner.current === own.account?.user_id;
        const value =
          (reusable ? initialProfile.current : null) ||
          own.data?.profile ||
          emptyProfile();
        setBase(value);
        setAnswers(profileAnswers(value));
        setInterests(value.interests || []);
        setSession(own.account);
        setOptions(settings);
      } catch (reason) {
        if (!controller.signal.aborted)
          setError(
            reason instanceof Error
              ? reason.message
              : "Details could not be loaded",
          );
      }
    }
    void load();
    return () => controller.abort();
  }, [retry]);
  function move(next: number) {
    setStep(next);
    setErrors({});
    setError("");
    requestAnimationFrame(() => heading.current?.focus());
  }
  if (!options)
    return error ? (
      <ErrorState
        message={error}
        retry={() => {
          setError("");
          setRetry((value) => value + 1);
        }}
      />
    ) : (
      <LoadingState message="Preparing your questionnaire…" />
    );
  const sections = fields(options);
  // Keep any existing typed course value when editing an older encrypted profile.
  if (
    answers.course_level &&
    !sections[1][0].choices.some((item) => item.value === answers.course_level)
  )
    sections[1][0].choices.push({
      value: answers.course_level,
      label: answers.course_level,
    });
  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy || !options) return;
    const validation = validateAnswers(sections[step], answers);
    if (
      step === 1 &&
      answers.current_student === "true" &&
      (answers.field_of_study?.length || 0) > 80
    )
      validation.field_of_study = "Use at most 80 characters.";
    setErrors(validation);
    if (Object.keys(validation).length) {
      document.getElementById(Object.keys(validation)[0])?.focus();
      return;
    }
    if (step < 4) {
      move(step + 1);
      return;
    }
    const updated = discoveryProfile(answers, interests, base);
    setBusy(true);
    setError("");
    try {
      if (session && save)
        await citizenFetch(
          "profiles/me",
          citizenJSON(updated, session.csrf_token, "PUT"),
        );
      setProfile(updated, session?.user_id);
      router.push("/schemes/recommended");
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Unable to continue. Your details have not been saved.",
      );
      setBusy(false);
    }
  }
  return (
    <section className="discovery-layout">
      <aside className="discovery-aside">
        <span className="eyebrow">A better place to begin</span>
        <h2>
          Your needs.
          <br />
          Your next opportunity.
        </h2>
        <p>
          A few details help us find relevant categories and explain each
          recommendation.
        </p>
        <div className="privacy-note">
          <LockKeyhole size={20} />
          <p>
            {session
              ? "Your details are prefilled. Changes are saved only if you choose to save them."
              : "No account needed. Your answers stay in this tab’s memory and are cleared when you reload or leave the app."}
          </p>
        </div>
        <Link href="/schemes/all" className="text-link">
          Prefer to browse all schemes? →
        </Link>
      </aside>
      <div className="discovery-panel">
        <ol className="discovery-progress" aria-label="Questionnaire progress">
          {steps.map((label, index) => (
            <li
              key={label}
              aria-current={index === step ? "step" : undefined}
              className={index <= step ? "reached" : ""}
            >
              <span>{index < step ? <Check size={15} /> : index + 1}</span>
              <small>{label}</small>
            </li>
          ))}
        </ol>
        <p className="eyebrow">Step {step + 1} of 5 · All answers optional</p>
        <h2 ref={heading} tabIndex={-1}>
          {steps[step]}
        </h2>
        <p className="discovery-step-note">
          {step === 4
            ? "Choose the areas you want to explore. You can select several interests."
            : "Share what you know. Unknown information stays unknown."}
        </p>
        <form onSubmit={(event) => void submit(event)} noValidate>
          <fieldset disabled={busy} className="discovery-fields">
            <legend className="sr-only">{steps[step]}</legend>
            {sections[step].map((field) => (
              <QuestionField
                key={field.key}
                field={field}
                value={answers[field.key] || ""}
                answers={answers}
                error={errors[field.key]}
                disabled={busy}
                onChange={(value) =>
                  setAnswers((old) => ({ ...old, [field.key]: value }))
                }
              />
            ))}
            {step === 4 && (
              <div className="interest-grid">
                {options.interests.map((interest) => (
                  <label
                    key={interest.value}
                    className={`interest-choice ${interests.includes(interest.value) ? "selected" : ""}`}
                  >
                    <input
                      type="checkbox"
                      value={interest.value}
                      checked={interests.includes(interest.value)}
                      onChange={(event) =>
                        setInterests((old) =>
                          event.target.checked
                            ? [...old, interest.value]
                            : old.filter((value) => value !== interest.value),
                        )
                      }
                    />
                    <span>{interest.label}</span>
                  </label>
                ))}
              </div>
            )}
          </fieldset>
          {step === 4 && session && (
            <label className="review-check discovery-consent">
              <input
                type="checkbox"
                checked={save}
                onChange={(event) => setSave(event.target.checked)}
                disabled={busy}
              />
              Save these changes to my private encrypted profile
            </label>
          )}
          {error && (
            <p role="alert" className="form-error">
              {error}
            </p>
          )}
          <div className="discovery-actions">
            {step > 0 && (
              <button
                className="button button-secondary"
                type="button"
                disabled={busy}
                onClick={() => move(step - 1)}
              >
                <ArrowLeft size={16} />
                Back
              </button>
            )}
            <button className="button button-primary" disabled={busy}>
              {busy
                ? "Preparing…"
                : step === 4
                  ? "Find Relevant Schemes"
                  : "Next"}
              <ArrowRight size={16} />
            </button>
          </div>
        </form>
        <ProjectDisclaimer />
      </div>
    </section>
  );
}
