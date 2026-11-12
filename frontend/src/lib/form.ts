import type { ProfileField } from "./types";
export type Answers = Record<string, string>;

export function isVisible(field: ProfileField, answers: Answers): boolean {
  return (
    !field.visible_when ||
    answers[field.visible_when.field] === String(field.visible_when.equals)
  );
}

export function validateAnswers(
  fields: ProfileField[],
  answers: Answers,
): Record<string, string> {
  const errors: Record<string, string> = {};
  for (const field of fields.filter((item) => isVisible(item, answers))) {
    const value = answers[field.key]?.trim() || "";
    if (!value) continue; // Missing values belong to UNKNOWN, not a forced form answer.
    if (value.length > 200) errors[field.key] = "Use at most 200 characters.";
    if (field.value_type === "number") {
      const number = Number(value);
      if (!/^-?\d+(?:\.\d+)?$/.test(value) || !Number.isFinite(number))
        errors[field.key] = "Enter a valid number.";
      else if (field.integer && !Number.isInteger(number))
        errors[field.key] = "Enter a whole number.";
      else if (field.minimum !== null && number < field.minimum)
        errors[field.key] = `Enter ${field.minimum} or more.`;
      else if (field.maximum !== null && number > field.maximum)
        errors[field.key] = `Enter ${field.maximum} or less.`;
    } else if (field.value_type === "date") {
      const date = new Date(`${value}T00:00:00Z`);
      if (
        !/^\d{4}-\d{2}-\d{2}$/.test(value) ||
        !Number.isFinite(date.getTime()) ||
        date.toISOString().slice(0, 10) !== value
      )
        errors[field.key] = "Enter a valid date.";
    } else if (
      field.value_type === "boolean" &&
      !["true", "false"].includes(value)
    )
      errors[field.key] = "Choose yes, no, or leave this unknown.";
    else if (
      field.choices.length &&
      !field.choices.some((choice) => choice.value === value)
    )
      errors[field.key] = "Choose one of the listed options.";
  }
  return errors;
}

export function buildProfile(
  fields: ProfileField[],
  answers: Answers,
): Record<string, string | boolean> {
  return Object.fromEntries(
    fields
      .filter(
        (field) => isVisible(field, answers) && answers[field.key]?.trim(),
      )
      .map((field) => [
        field.key,
        field.value_type === "boolean"
          ? answers[field.key] === "true"
          : answers[field.key].trim(),
      ]),
  );
}

export const exampleAnswers: Answers = {
  age: "21",
  annual_income_inr: "240000",
  course: "engineering",
  study_mode: "full_time",
  enrollment_date: "2026-08-01",
  receives_other_scholarship: "false",
  requests_disability_support: "false",
};
