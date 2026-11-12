"""Pure validation and bounded satisfiability checks using the existing engine AST."""

from datetime import date
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from typing import Any

from app.eligibility.expressions import (
    Comparison,
    Conditional,
    Exclusion,
    Expression,
    Group,
    Normalized,
    Program,
    typed_value,
)

COMPLEMENT = {
    "==": "!=",
    "!=": "==",
    ">": "<=",
    ">=": "<",
    "<": ">=",
    "<=": ">",
    "IN": "NOT IN",
    "NOT IN": "IN",
}


def expression_dnf(expression: Expression, negate: bool = False) -> list[list[Comparison]]:
    if isinstance(expression, Comparison):
        return [
            [
                expression.model_copy(update={"operator": COMPLEMENT[expression.operator]})
                if negate
                else expression
            ]
        ]
    if isinstance(expression, Exclusion):
        return expression_dnf(expression.expression, not negate)
    if isinstance(expression, Conditional):
        positive = Group(kind="and", key="positive", children=[expression.when, expression.then])
        negative: Expression = Exclusion(kind="exclude", key="negative", expression=expression.when)
        if expression.otherwise:
            negative = Group(kind="and", key="else_branch", children=[negative, expression.otherwise])
        return expression_dnf(Group(kind="or", key="branches", children=[positive, negative]), negate)
    conjunction = (expression.kind == "and") != negate
    branches: list[list[Comparison]] = [[]] if conjunction else []
    for child in expression.children:
        terms = expression_dnf(child, negate)
        if conjunction:
            if len(branches) * len(terms) > 128:
                raise ValueError("Policy logic is too complex for bounded contradiction verification")
            branches = [left + right for left in branches for right in terms]
        else:
            branches += terms
        if len(branches) > 128 or any(len(branch) > 128 for branch in branches):
            raise ValueError("Policy logic exceeds verification limits")
    return branches


def allowed(value: Normalized, condition: Comparison) -> bool:
    expected = condition.value
    if condition.operator in {"IN", "NOT IN"}:
        assert isinstance(expected, list)
        included = value in [typed_value(item, condition.value_type) for item in expected]
        return included if condition.operator == "IN" else not included
    target = typed_value(expected, condition.value_type)
    if condition.operator == "==":
        return value == target
    if condition.operator == "!=":
        return value != target
    # Ordered engine comparisons are restricted to Decimal/date values.
    if not isinstance(value, (Decimal, date)) or not isinstance(target, type(value)):
        return False
    if condition.operator == ">":
        return value > target  # type: ignore[operator]
    if condition.operator == ">=":
        return value >= target  # type: ignore[operator]
    if condition.operator == "<":
        return value < target  # type: ignore[operator]
    return value <= target  # type: ignore[operator]


def branch_possible(branch: list[Comparison], program: Program) -> bool:
    fields = {field.key: field for field in program.fields}
    for key in {item.field for item in branch}:
        conditions = [item for item in branch if item.field == key]
        field = fields[key]
        finite: list[Normalized] | None = (
            [choice.value for choice in field.choices]
            if field.choices
            else [False, True]
            if field.value_type == "boolean"
            else None
        )
        for item in conditions:
            options = (
                [typed_value(value, item.value_type) for value in item.value]
                if item.operator == "IN" and isinstance(item.value, list)
                else [typed_value(item.value, item.value_type)]
                if item.operator == "=="
                else None
            )
            if options is not None:
                finite = options if finite is None else [value for value in finite if value in options]
        if finite is not None and field.value_type == "number":
            finite = [
                value
                for value in finite
                if isinstance(value, Decimal)
                and (field.minimum is None or value >= Decimal(str(field.minimum)))
                and (field.maximum is None or value <= Decimal(str(field.maximum)))
                and (not field.integer or value == value.to_integral_value())
            ]
        if finite is not None:
            if not any(all(allowed(value, item) for item in conditions) for value in finite):
                return False
            continue
        lower: tuple[Any, bool] | None = None
        upper: tuple[Any, bool] | None = None
        if field.value_type == "number":
            lower = (Decimal(str(field.minimum)), False) if field.minimum is not None else None
            upper = (Decimal(str(field.maximum)), False) if field.maximum is not None else None
        for item in conditions:
            if item.operator in {">", ">=", "<", "<="}:
                value = typed_value(item.value, item.value_type)
                strict = item.operator in {">", "<"}
                if item.operator in {">", ">="}:
                    if lower is None or value > lower[0] or (value == lower[0] and strict):
                        lower = (value, strict)
                elif upper is None or value < upper[0] or (value == upper[0] and strict):
                    upper = (value, strict)
        if lower is not None and upper is not None:
            if lower[0] > upper[0] or (lower[0] == upper[0] and (lower[1] or upper[1])):
                return False
            if lower[0] == upper[0] and not all(allowed(lower[0], item) for item in conditions):
                return False
            if field.value_type == "number" and field.integer:
                first = int(lower[0].to_integral_value(rounding=ROUND_CEILING))
                last = int(upper[0].to_integral_value(rounding=ROUND_FLOOR))
                first += int(lower[1] and first == lower[0])
                last -= int(upper[1] and last == upper[0])
                if first > last:
                    return False
                if last - first <= 128 and not any(
                    all(allowed(Decimal(value), item) for item in conditions)
                    for value in range(first, last + 1)
                ):
                    return False
            if field.value_type == "date":
                first_day = lower[0].toordinal() + int(lower[1])
                last_day = upper[0].toordinal() - int(upper[1])
                if first_day > last_day:
                    return False
                if last_day - first_day <= 128 and not any(
                    all(allowed(date.fromordinal(value), item) for item in conditions)
                    for value in range(first_day, last_day + 1)
                ):
                    return False
    return True


def ensure_satisfiable(program: Program) -> None:
    if not any(branch_possible(branch, program) for branch in expression_dnf(program.expression)):
        raise ValueError("The complete proposed policy is internally contradictory")
