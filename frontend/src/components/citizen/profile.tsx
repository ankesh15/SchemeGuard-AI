"use client";
import { useEffect, useState, type FormEvent } from "react";
import {
  citizenFetch,
  citizenJSON,
  type ProfileRead,
  type ProfileData,
} from "@/lib/citizen";
import { useOptionalDiscovery } from "@/components/discovery-context";
import { useCitizen } from "./session";
import { ErrorState, LoadingState } from "@/components/ui";
import { QuestionField } from "@/components/questionnaire";
import { buildProfile, validateAnswers, type Answers } from "@/lib/form";
import type { ProfileField } from "@/lib/types";
interface Options {
  states: string[];
  fields: ProfileField[];
}
export function CitizenProfile() {
  const session = useCitizen();
  const discovery = useOptionalDiscovery();
  const [data, setData] = useState<ProfileRead | null>(null);
  const [options, setOptions] = useState<Options>({ states: [], fields: [] });
  const [state, setState] = useState("");
  const [age, setAge] = useState("");
  const [income, setIncome] = useState("");
  const [education, setEducation] = useState("");
  const [student, setStudent] = useState("");
  const [occupation, setOccupation] = useState("");
  const [answers, setAnswers] = useState<Answers>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  function fill(value: ProfileRead) {
    setData(value);
    discovery?.setProfile(value.profile, session.user_id);
    const profile = value.profile;
    setState(profile.state || "");
    setAge(profile.age_years === null ? "" : String(profile.age_years));
    setIncome(
      profile.annual_family_income_inr === null
        ? ""
        : String(profile.annual_family_income_inr),
    );
    setEducation(profile.course_level || "");
    setStudent(
      profile.current_student === null ? "" : String(profile.current_student),
    );
    setOccupation(profile.occupation || "");
    setAnswers(
      Object.fromEntries(
        Object.entries(profile.attributes).map(([key, value]) => [
          key,
          value === null ? "" : String(value),
        ]),
      ),
    );
  }
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      citizenFetch<ProfileRead>("profiles/me", { signal: controller.signal }),
      citizenFetch<Options>("profiles/options", { signal: controller.signal }),
    ])
      .then(([profile, fields]) => {
        if (!controller.signal.aborted) {
          fill(profile);
          setOptions({
            ...fields,
            fields: fields.fields.map((field) =>
              ["course", "requests_disability_support"].includes(field.key)
                ? {
                    ...field,
                    section: "Learning assessment fields",
                    label:
                      field.key === "course"
                        ? "Learning assessment course"
                        : "Requesting additional support?",
                    help_text: "Used only by the project learning assessment.",
                  }
                : field,
            ),
          });
        }
      })
      .catch((reason: Error) => {
        if (!controller.signal.aborted) setError(reason.message);
      });
    return () => controller.abort();
  }, []);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setNotice("");
    const validation = validateAnswers(options.fields, answers);
    setErrors(validation);
    if (Object.keys(validation).length) return;
    if (age && (!/^\d+$/.test(age) || Number(age) > 130)) {
      setError("Enter a whole age from 0 to 130, or leave it unknown.");
      return;
    }
    if (
      income &&
      (!Number.isFinite(Number(income)) ||
        Number(income) < 0 ||
        Number(income) > 1e12)
    ) {
      setError("Enter a valid non-negative annual income or leave it unknown.");
      return;
    }
    const profile: ProfileData = {
      ...data?.profile,
      state: state || null,
      age_years: age ? Number(age) : null,
      annual_family_income_inr: income ? Number(income) : null,
      course_level: education.trim() || null,
      current_student: student === "" ? null : student === "true",
      occupation: occupation || null,
      attributes: buildProfile(options.fields, answers),
    };
    setBusy(true);
    try {
      fill(
        await citizenFetch<ProfileRead>(
          "profiles/me",
          citizenJSON(profile, session.csrf_token, "PUT"),
        ),
      );
      setNotice("Your private profile was saved.");
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "Profile could not be saved",
      );
    } finally {
      setBusy(false);
    }
  }
  if (!data)
    return error ? (
      <ErrorState message={error} />
    ) : (
      <LoadingState message="Loading your encrypted profile…" />
    );
  return (
    <section className="admin-card">
      <span className="eyebrow">
        Private profile · {data.completeness.percent}% complete
      </span>
      <h2>Your information, on your terms.</h2>
      <p>
        Every field is optional. Collect only information needed for schemes you
        assess. Do not enter Aadhaar, identity numbers, names, contact details
        or documents. Profile completeness does not establish eligibility.
      </p>
      <form
        className="admin-form"
        onSubmit={(event) => void submit(event)}
        noValidate
      >
        <fieldset disabled={busy} className="admin-form-grid">
          <label>
            State or union territory
            <select
              value={state}
              onChange={(event) => setState(event.target.value)}
            >
              <option value="">Unknown</option>
              {options.states.map((value) => (
                <option key={value}>{value}</option>
              ))}
            </select>
          </label>
          <label>
            Age in years
            <input
              inputMode="numeric"
              autoComplete="off"
              maxLength={3}
              value={age}
              onChange={(event) => setAge(event.target.value)}
            />
          </label>
          <label>
            Annual family income (INR)
            <input
              inputMode="decimal"
              autoComplete="off"
              maxLength={20}
              value={income}
              onChange={(event) => setIncome(event.target.value)}
            />
          </label>
          <label>
            Education / course level
            <input
              maxLength={80}
              autoComplete="off"
              value={education}
              onChange={(event) => setEducation(event.target.value)}
              placeholder="Use the wording in your scheme’s questionnaire"
            />
          </label>
          <label>
            Currently a student?
            <select
              value={student}
              onChange={(event) => setStudent(event.target.value)}
            >
              <option value="">Unknown</option>
              <option value="true">Yes</option>
              <option value="false">No</option>
            </select>
          </label>
          <label>
            Occupation
            <select
              value={occupation}
              onChange={(event) => setOccupation(event.target.value)}
            >
              <option value="">Unknown</option>
              {[
                "student",
                "employed",
                "self_employed",
                "unemployed",
                "retired",
                "other",
              ].map((value) => (
                <option key={value} value={value}>
                  {value.replaceAll("_", " ")}
                </option>
              ))}
            </select>
          </label>
        </fieldset>
        <details>
          <summary>Additional scheme fields (optional)</summary>
          <div className="admin-form-grid">
            {options.fields.map((field) => (
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
          </div>
        </details>
        <button className="button button-primary" disabled={busy}>
          {busy ? "Saving…" : "Save private profile"}
        </button>
      </form>
      {error && (
        <p role="alert" className="form-error">
          {error}
        </p>
      )}
      {notice && <p role="status">{notice}</p>}
      <details className="mt-5">
        <summary>Delete stored profile</summary>
        <p>
          This removes the profile used for future reassessment. Saved
          assessments retain their encrypted minimal historical snapshots until
          account deletion.
        </p>
        <label className="review-check">
          <input
            type="checkbox"
            checked={confirmDelete}
            onChange={(event) => setConfirmDelete(event.target.checked)}
          />
          I want to remove my stored profile.
        </label>
        <button
          className="button button-secondary"
          disabled={busy || !confirmDelete}
          onClick={async () => {
            setBusy(true);
            try {
              await citizenFetch(
                "profiles/me",
                citizenJSON({}, session.csrf_token, "DELETE"),
              );
              fill(await citizenFetch<ProfileRead>("profiles/me"));
              setConfirmDelete(false);
              setNotice(
                "Stored profile deleted. Missing future answers will remain unknown.",
              );
            } catch (reason) {
              setError(
                reason instanceof Error ? reason.message : "Deletion failed",
              );
            } finally {
              setBusy(false);
            }
          }}
        >
          Delete profile
        </button>
      </details>
    </section>
  );
}
