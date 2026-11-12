"""Authored test expressions. Every value belongs only to the fictional policy."""

from typing import Any

from app.eligibility.expressions import Program

DEMO_SLUG = "schemeguard-learning-scholarship"
POLICY_FILENAME = "demo-policy-v1.md"


def comparison(
    key: str, field: str, operator: str, value: object, value_type: str = "number"
) -> dict[str, Any]:
    return {
        "kind": "comparison",
        "key": key,
        "field": field,
        "operator": operator,
        "value_type": value_type,
        "value": value,
    }


def demo_program() -> Program:
    fields = [
        {
            "key": "age",
            "label": "Age",
            "value_type": "number",
            "section": "About your synthetic profile",
            "minimum": 0,
            "maximum": 120,
            "integer": True,
            "help_text": "Use an invented age. Do not enter a date of birth.",
        },
        {
            "key": "annual_income_inr",
            "label": "Annual household income (INR)",
            "value_type": "number",
            "section": "About your synthetic profile",
            "minimum": 0,
            "maximum": 100000000000,
            "help_text": "A fictional annual total in rupees. Decimals are supported.",
        },
        {
            "key": "course",
            "label": "Course",
            "value_type": "string",
            "section": "Education",
            "choices": [
                {"value": "engineering", "label": "Engineering"},
                {"value": "science", "label": "Science"},
                {"value": "other", "label": "Another course"},
            ],
        },
        {
            "key": "study_mode",
            "label": "Study mode",
            "value_type": "string",
            "section": "Education",
            "choices": [
                {"value": "full_time", "label": "Full time"},
                {"value": "part_time", "label": "Part time"},
            ],
        },
        {
            "key": "enrollment_date",
            "label": "Enrollment date",
            "value_type": "date",
            "section": "Education",
            "help_text": "Use an invented date. This is not an application deadline.",
        },
        {
            "key": "receives_other_scholarship",
            "label": "Receiving another scholarship?",
            "value_type": "boolean",
            "section": "Additional support",
        },
        {
            "key": "requests_disability_support",
            "label": "Requesting disability support?",
            "value_type": "boolean",
            "section": "Additional support",
        },
        {
            "key": "disability_percent",
            "label": "Certified disability percentage",
            "value_type": "number",
            "section": "Additional support",
            "minimum": 0,
            "maximum": 100,
            "help_text": "Synthetic percentage only; no documents are collected.",
            "visible_when": {"field": "requests_disability_support", "equals": True},
        },
    ]
    conditions = [
        {
            "kind": "and",
            "key": "age_requirement",
            "label": "Age within the fictional policy range",
            "children": [
                comparison("age_minimum", "age", ">=", 18),
                comparison("age_maximum", "age", "<=", 25),
            ],
        },
        comparison("income_requirement", "annual_income_inr", "<=", 300000)
        | {"label": "Household income within the test limit"},
        {
            "kind": "or",
            "key": "study_requirement",
            "label": "An accepted full-time study pathway",
            "children": [
                {
                    "kind": "and",
                    "key": "engineering_path",
                    "children": [
                        comparison("engineering_course", "course", "==", "engineering", "string"),
                        comparison("engineering_full_time", "study_mode", "==", "full_time", "string"),
                    ],
                },
                {
                    "kind": "and",
                    "key": "science_path",
                    "children": [
                        comparison("science_course", "course", "==", "science", "string"),
                        comparison("science_full_time", "study_mode", "==", "full_time", "string"),
                    ],
                },
            ],
        },
        {
            "kind": "exclude",
            "key": "other_award_exclusion",
            "label": "No other scholarship received",
            "expression": comparison(
                "other_award_received", "receives_other_scholarship", "==", True, "boolean"
            ),
        },
        {
            "kind": "if",
            "key": "support_requirement",
            "label": "Additional support requirements",
            "when": comparison("support_requested", "requests_disability_support", "==", True, "boolean"),
            "then": comparison("support_percentage", "disability_percent", ">=", 40),
        },
        {
            "kind": "and",
            "key": "enrollment_requirement",
            "label": "Enrollment within the fictional date range",
            "children": [
                comparison("enrollment_start", "enrollment_date", ">=", "2026-06-01", "date"),
                comparison("enrollment_end", "enrollment_date", "<=", "2026-12-31", "date"),
            ],
        },
    ]
    return Program.model_validate(
        {
            "fields": fields,
            "expression": {
                "kind": "and",
                "key": "assessment",
                "label": "Fictional scholarship assessment",
                "children": conditions,
            },
        }
    )


SYNTHETIC_PASS_PROFILE: dict[str, Any] = {
    "age": 21,
    "annual_income_inr": "240000",
    "course": "engineering",
    "study_mode": "full_time",
    "enrollment_date": "2026-08-01",
    "receives_other_scholarship": False,
    "requests_disability_support": False,
}
