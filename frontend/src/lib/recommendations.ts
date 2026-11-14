import type { ProfileData } from "./citizen";
import type { ProfileField, Scheme } from "./types";
import type { Answers } from "./form";

export interface Recommendation extends Scheme {
  relevance: "HIGH" | "POTENTIAL" | "MORE_INFORMATION";
  matching_reasons: string[];
  missing_information: string[];
  ranking_points: number;
  ranking_factors: Record<string, number>;
  approved_rule_version: number | null;
}
export interface RecommendationPage {
  items: Recommendation[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
  categories: string[];
  notice: string;
}
export interface DiscoveryOptions {
  states: string[];
  interests: { value: string; label: string }[];
  categories: string[];
}
export const emptyProfile = (): ProfileData => ({
  state: null,
  age_years: null,
  annual_family_income_inr: null,
  course_level: null,
  current_student: null,
  occupation: null,
  employment_status: null,
  field_of_study: null,
  interests: [],
  attributes: {},
});
export const relevanceLabel = {
  HIGH: "Highly Relevant",
  POTENTIAL: "Potentially Relevant",
  MORE_INFORMATION: "More Information Needed",
};
export function profileAnswers(profile: ProfileData): Answers {
  return Object.fromEntries(
    Object.entries({
      ...profile.attributes,
      ...profile,
      age: profile.age_years,
      annual_income_inr: profile.annual_family_income_inr,
    })
      .filter(
        ([, value]) =>
          value !== null &&
          ["string", "boolean", "number"].includes(typeof value),
      )
      .map(([key, value]) => [key, String(value)]),
  );
}
export function assessmentPrefill(
  fields: ProfileField[],
  profile: ProfileData | null,
): Answers {
  if (!profile) return {};
  const values = profileAnswers(profile);
  return Object.fromEntries(
    fields
      .filter((field) => {
        const value = values[field.key];
        return (
          value !== undefined &&
          (!field.choices.length ||
            field.choices.some((choice) => choice.value === value))
        );
      })
      .map((field) => [field.key, values[field.key]]),
  );
}
export function discoveryProfile(
  answers: Answers,
  interests: string[],
  base?: ProfileData | null,
): ProfileData {
  return {
    ...(base || emptyProfile()),
    age_years: answers.age_years?.trim() ? Number(answers.age_years) : null,
    state: answers.state || null,
    course_level: answers.course_level || null,
    current_student: answers.current_student
      ? answers.current_student === "true"
      : null,
    field_of_study:
      answers.current_student === "true"
        ? answers.field_of_study?.trim() || null
        : null,
    occupation: answers.occupation || null,
    employment_status: answers.employment_status || null,
    annual_family_income_inr: answers.annual_family_income_inr?.trim()
      ? Number(answers.annual_family_income_inr)
      : null,
    interests,
  };
}
