from datetime import date
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field

from app.eligibility.expressions import (
    Comparison,
    Conditional,
    Exclusion,
    Expression,
    Group,
    Normalized,
    Program,
    Scalar,
    normalize_profile,
    typed_value,
)


class Result(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


ASSESSMENTS: dict[Result, str] = {
    Result.PASS: "Known conditions satisfied",
    Result.FAIL: "Requirements not satisfied",
    Result.UNKNOWN: "More information required",
}


def combine_and(results: list[Result]) -> Result:
    if not results:
        raise ValueError("AND must contain at least one condition")
    if Result.FAIL in results:
        return Result.FAIL
    return Result.UNKNOWN if Result.UNKNOWN in results else Result.PASS


def combine_or(results: list[Result]) -> Result:
    if not results:
        raise ValueError("OR must contain at least one condition")
    if Result.PASS in results:
        return Result.PASS
    return Result.UNKNOWN if Result.UNKNOWN in results else Result.FAIL


class Trace(BaseModel):
    key: str
    label: str
    kind: str
    result: Result
    explanation: str
    missing_fields: list[str] = Field(default_factory=list)
    children: list["Trace"] = Field(default_factory=list)


def _compare(left: Normalized, comparison: Comparison) -> bool:
    if comparison.operator in {"IN", "NOT IN"}:
        assert isinstance(comparison.value, list)
        present = left in [typed_value(value, comparison.value_type) for value in comparison.value]
        return present if comparison.operator == "IN" else not present
    right = typed_value(comparison.value, comparison.value_type)
    if comparison.operator == "==":
        return left == right
    if comparison.operator == "!=":
        return left != right
    # Validation guarantees both operands share a numeric or calendar-date type.
    if isinstance(left, Decimal) and isinstance(right, Decimal):
        ordered_left, ordered_right = left, right
        return {
            ">": ordered_left > ordered_right,
            "<": ordered_left < ordered_right,
            ">=": ordered_left >= ordered_right,
            "<=": ordered_left <= ordered_right,
        }[comparison.operator]
    if isinstance(left, date) and isinstance(right, date):
        return {">": left > right, "<": left < right, ">=": left >= right, "<=": left <= right}[
            comparison.operator
        ]
    raise ValueError("Operands do not match the validated rule type")


def evaluate(program: Program, profile: dict[str, Scalar]) -> Trace:
    values = normalize_profile(program, profile)
    fields = {field.key: field for field in program.fields}

    def visit(expression: Expression) -> Trace:
        label = expression.label or expression.key.replace("_", " ").capitalize()
        if isinstance(expression, Comparison):
            actual = values.get(expression.field)
            if actual is None:
                return Trace(
                    key=expression.key,
                    label=label,
                    kind=expression.kind,
                    result=Result.UNKNOWN,
                    explanation=f"Provide {fields[expression.field].label.lower()} to assess this condition.",
                    missing_fields=[expression.field],
                )
            result = Result.PASS if _compare(actual, expression) else Result.FAIL
            return Trace(
                key=expression.key,
                label=label,
                kind=expression.kind,
                result=result,
                explanation=f"The declared value {'satisfies' if result == Result.PASS else 'does not satisfy'} this condition ({expression.operator} {expression.value}).",
            )
        if isinstance(expression, Group):
            children = [visit(child) for child in expression.children]
            result = (combine_and if expression.kind == "and" else combine_or)(
                [child.result for child in children]
            )
            missing = sorted({field for child in children for field in child.missing_fields})
            if expression.kind == "or" and result == Result.PASS:
                missing = []  # An established alternative is sufficient; other branches are not required.
            return Trace(
                key=expression.key,
                label=label,
                kind=expression.kind,
                result=result,
                explanation="All requirements must be satisfied."
                if expression.kind == "and"
                else "At least one alternative must be satisfied.",
                missing_fields=missing,
                children=children,
            )
        if isinstance(expression, Exclusion):
            child = visit(expression.expression)
            result = {Result.PASS: Result.FAIL, Result.FAIL: Result.PASS, Result.UNKNOWN: Result.UNKNOWN}[
                child.result
            ]
            return Trace(
                key=expression.key,
                label=label,
                kind=expression.kind,
                result=result,
                explanation="An exclusion applies."
                if result == Result.FAIL
                else "No exclusion established."
                if result == Result.PASS
                else "More information is needed to check this exclusion.",
                missing_fields=child.missing_fields,
                children=[child],
            )
        if isinstance(expression, Conditional):
            guard = visit(expression.when)
            if guard.result == Result.UNKNOWN:
                return Trace(
                    key=expression.key,
                    label=label,
                    kind=expression.kind,
                    result=Result.UNKNOWN,
                    explanation="The prerequisite is unknown; the conditional requirement cannot yet be assessed.",
                    missing_fields=guard.missing_fields,
                    children=[guard],
                )
            branch = expression.then if guard.result == Result.PASS else expression.otherwise
            if branch is None:
                return Trace(
                    key=expression.key,
                    label=label,
                    kind=expression.kind,
                    result=Result.PASS,
                    explanation="This additional requirement does not apply to the declared profile.",
                    children=[guard],
                )
            child = visit(branch)
            return Trace(
                key=expression.key,
                label=label,
                kind=expression.kind,
                result=child.result,
                explanation="Evaluated the applicable conditional branch.",
                missing_fields=child.missing_fields,
                children=[guard, child],
            )
        raise ValueError("Unsupported expression")

    return visit(program.expression)
