import { describe, expect, it } from "vitest";
import { buildProfile, exampleAnswers, validateAnswers } from "@/lib/form";
import type { Requirements } from "@/lib/types";
import fixture from "./fixtures/requirements.json";
const requirements = fixture as Requirements;

describe("dynamic profile validation", () => {
  it("allows unanswered fields so the API can return UNKNOWN", () => {
    expect(validateAnswers(requirements.fields, {})).toEqual({});
    expect(buildProfile(requirements.fields, {})).toEqual({});
  });
  it.each(["not a number", "Infinity", "NaN", "1e3", " "])(
    "validates numeric input %s",
    (value) => {
      const errors = validateAnswers(requirements.fields, { age: value });
      if (value.trim()) expect(errors.age).toBeDefined();
      else expect(errors.age).toBeUndefined();
    },
  );
  it("validates input domains without rejecting failing eligibility profiles", () => {
    expect(
      validateAnswers(requirements.fields, {
        age: "17",
        annual_income_inr: "300001",
      }),
    ).toEqual({});
    expect(
      validateAnswers(requirements.fields, { age: "-1" }).age,
    ).toBeDefined();
    expect(validateAnswers(requirements.fields, { age: "21.5" }).age).toBe(
      "Enter a whole number.",
    );
  });
  it("validates real calendar dates and listed choices", () => {
    expect(
      validateAnswers(requirements.fields, { enrollment_date: "2026-02-30" })
        .enrollment_date,
    ).toBeDefined();
    expect(
      validateAnswers(requirements.fields, { enrollment_date: "2026-06-01" }),
    ).toEqual({});
    expect(
      validateAnswers(requirements.fields, { course: "unlisted" }).course,
    ).toBeDefined();
  });
  it("keeps decimal precision and preserves a declared false", () => {
    const profile = buildProfile(requirements.fields, { ...exampleAnswers });
    expect(profile.receives_other_scholarship).toBe(false);
    expect(
      buildProfile(requirements.fields, {
        annual_income_inr: "300000.00000000000001",
      }).annual_income_inr,
    ).toBe("300000.00000000000001");
  });
  it("omits hidden dependent fields and validates them when applicable", () => {
    const answers = {
      requests_disability_support: "false",
      disability_percent: "invalid",
    };
    expect(buildProfile(requirements.fields, answers)).not.toHaveProperty(
      "disability_percent",
    );
    expect(validateAnswers(requirements.fields, answers)).toEqual({});
    expect(
      validateAnswers(requirements.fields, {
        ...answers,
        requests_disability_support: "true",
      }).disability_percent,
    ).toBeDefined();
  });
});
