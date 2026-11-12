"""Syntactic/grounding checks only. Every outcome still requires human review."""

import re
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from app.ai.schemas import CandidateBatch, CandidateRule
from app.eligibility.expressions import (
    EXPRESSION_ADAPTER,
    Comparison,
    Expression,
    Group,
    ProfileField,
    Program,
    ValueType,
    typed_value,
)
from app.ingestion.pdf_parser import ParsedPage
from app.ingestion.text_processor import normalize

# Human-maintained field vocabulary, not government eligibility thresholds.
FIELDS: dict[str, tuple[str, ValueType, str | None]] = {
    "age_years": ("Age in years", "number", "years"),
    "annual_family_income_inr": ("Annual family income", "number", "INR_per_year"),
    "disability_percent": ("Disability percentage", "number", "percent"),
    "gender": ("Gender", "string", None),
    "category": ("Social category", "string", None),
    "state": ("State or union territory", "string", None),
    "course_level": ("Course level", "string", None),
    "study_mode": ("Study mode", "string", None),
    "enrollment_date": ("Enrollment date", "date", None),
    "receives_other_scholarship": ("Receives another scholarship", "boolean", None),
}


@dataclass
class ValidatedCandidate:
    candidate: CandidateRule
    expression: dict[str, Any] | None = None
    status: str = "VALIDATED"
    issues: list[str] = field(default_factory=list)
    evidence: list[tuple[str, int, str]] = field(default_factory=list)
    logical_relationship: str = "unspecified"
    source_batch_number: int = 1


def map_expression(candidate: CandidateRule) -> Expression:
    nodes = {node.key: node for node in candidate.nodes}
    if len(nodes) != len(candidate.nodes) or not candidate.root:
        raise ValueError("Missing root or duplicate node identifier")
    visited: set[str] = set()

    def build(key: str, depth: int) -> dict[str, Any]:
        if depth > 12 or key in visited or key not in nodes:
            raise ValueError("Invalid, repeated, or cyclic expression reference")
        visited.add(key)
        node = nodes[key]
        if node.kind == "comparison" and (
            node.children or node.expression or node.when or node.then or node.otherwise
        ):
            raise ValueError("Comparison contains unexpected logical references")
        if node.kind != "comparison" and any(
            value is not None
            for value in (node.field, node.operator, node.expected_value, node.value_type, node.units)
        ):
            raise ValueError("Logical node contains an unexpected comparison literal")
        if node.kind in {"and", "or"} and (node.expression or node.when or node.then or node.otherwise):
            raise ValueError("Group contains unexpected branch references")
        if node.kind == "exclude" and (node.children or node.when or node.then or node.otherwise):
            raise ValueError("Exclusion contains unexpected branch references")
        if node.kind == "if" and (node.children or node.expression):
            raise ValueError("Conditional contains unexpected references")
        base: dict[str, Any] = {
            "kind": node.kind,
            "key": node.key,
            "label": candidate.label if key == candidate.root else "",
        }
        if node.kind == "comparison":
            if node.field not in FIELDS or node.expected_value is None:
                raise ValueError("Unsupported field or missing rule value")
            if (node.value_type, node.units) != FIELDS[node.field][1:]:
                raise ValueError("Value type or units do not match the supported field")
            base.update(
                field=node.field,
                operator=node.operator,
                value_type=node.value_type,
                value=node.expected_value,
            )
        elif node.kind in {"and", "or"}:
            base["children"] = [build(child, depth + 1) for child in node.children]
        elif node.kind == "exclude" and node.expression:
            base["expression"] = build(node.expression, depth + 1)
        elif node.kind == "if" and node.when and node.then:
            base.update(
                when=build(node.when, depth + 1),
                then=build(node.then, depth + 1),
                otherwise=build(node.otherwise, depth + 1) if node.otherwise else None,
            )
        else:
            raise ValueError("Condition cannot be represented without human interpretation")
        return base

    expression = EXPRESSION_ADAPTER.validate_python(build(candidate.root, 0))
    if visited != nodes.keys():
        raise ValueError("Unreferenced expression nodes")
    used = {node.field for node in candidate.nodes if node.kind == "comparison" and node.field is not None}
    fields = [
        ProfileField(key=key, label=FIELDS[key][0], value_type=FIELDS[key][1], section="Extracted policy")
        for key in sorted(used)
        if key is not None
    ]
    Program(fields=fields, expression=expression)
    return expression


def numeric_values(excerpt: str, currency: bool = False) -> set[Decimal]:
    values = set()
    for match in re.finditer(r"(?<![\w])-?\d[\d,]*(?:\.\d+)?", excerpt):
        value = Decimal(match.group().replace(",", ""))
        after = excerpt[match.end() : match.end() + 15].casefold().lstrip()
        if currency and re.match(r"(?:lakh|lac)\b", after):
            value *= 100_000
        elif currency and re.match(r"crore\b", after):
            value *= 10_000_000
        values.add(value)
    return values


def value_grounded(node: Any, excerpts: str) -> bool:
    values = node.expected_value if isinstance(node.expected_value, list) else [node.expected_value]
    if node.value_type == "number":
        currency = node.units == "INR_per_year"
        if currency and (
            not re.search(r"₹|\brs\.?|\binr\b|rupees?", excerpts, re.I)
            or not re.search(r"per annum|annual|year", excerpts, re.I)
        ):
            return False
        if node.units == "percent" and not re.search(r"%|percent", excerpts, re.I):
            return False
        numbers = numeric_values(excerpts, currency)
        try:
            return all(typed_value(value, "number") in numbers for value in values)
        except ValueError:
            return False
    if node.value_type == "string":
        return all(
            re.search(r"(?<!\w)" + re.escape(str(value).casefold()) + r"(?!\w)", excerpts.casefold())
            for value in values
        )
    if node.value_type == "date":
        for value in values:
            try:
                date_value = typed_value(value, "date")
            except ValueError:
                return False
            if not isinstance(date_value, date) or not any(
                text in excerpts
                for text in (
                    str(date_value),
                    date_value.strftime("%d-%m-%Y"),
                    date_value.strftime("%d/%m/%Y"),
                )
            ):
                return False
        return True
    # Boolean semantics require human interpretation, so flag explicitly below.
    return True


def mandatory_comparisons(expression: Expression) -> list[Comparison]:
    if isinstance(expression, Comparison):
        return [expression]
    if isinstance(expression, Group) and expression.kind == "and":
        return [comparison for child in expression.children for comparison in mandatory_comparisons(child)]
    return []


def conflicts(first: Comparison, second: Comparison) -> bool:
    if first.field != second.field or first.value_type != second.value_type:
        return False
    a = (
        [typed_value(value, first.value_type) for value in first.value]
        if isinstance(first.value, list)
        else typed_value(first.value, first.value_type)
    )
    b = (
        [typed_value(value, second.value_type) for value in second.value]
        if isinstance(second.value, list)
        else typed_value(second.value, second.value_type)
    )
    if first.operator == second.operator == "==":
        return a != b
    if {first.operator, second.operator} == {"==", "!="}:
        return a == b
    if first.operator == second.operator == "IN" and isinstance(a, list) and isinstance(b, list):
        return not any(value in b for value in a)
    for equality, other in ((first, second), (second, first)):
        if equality.operator == "==" and isinstance(other.value, list):
            value = typed_value(equality.value, equality.value_type)
            members = [typed_value(member, other.value_type) for member in other.value]
            if (other.operator == "IN" and value not in members) or (
                other.operator == "NOT IN" and value in members
            ):
                return True
    if (
        first.value_type not in {"number", "date"}
        or first.operator not in {"==", ">", ">=", "<", "<="}
        or second.operator not in {"==", ">", ">=", "<", "<="}
    ):
        return False
    bounds = []
    for item in (first, second):
        value = typed_value(item.value, item.value_type)
        if item.operator in {"==", ">", ">="}:
            bounds.append(("lower", value, item.operator == ">"))
        if item.operator in {"==", "<", "<="}:
            bounds.append(("upper", value, item.operator == "<"))
    for _, lower, strict_lower in [entry for entry in bounds if entry[0] == "lower"]:
        for _, upper, strict_upper in [entry for entry in bounds if entry[0] == "upper"]:
            if lower > upper or (lower == upper and (strict_lower or strict_upper)):  # type: ignore[operator]
                return True
    return False


def validate_batch(batch: CandidateBatch, pages: list[ParsedPage]) -> list[ValidatedCandidate]:
    indexed = {page.page_number: page for page in pages}
    results = []
    seen = set()
    for candidate in batch.candidates:
        result = ValidatedCandidate(candidate, logical_relationship=batch.logical_relationship)
        if not candidate.evidence:
            result.status = "INVALID"
            result.issues.append("No supporting source evidence was provided.")
        if candidate.condition_identifier in seen:
            raise ValueError("Duplicate candidate condition identifier")
        seen.add(candidate.condition_identifier)
        try:
            expression = map_expression(candidate)
            result.expression = expression.model_dump(mode="json")
        except ValueError:
            result.issues.append(
                "Expression has unsupported fields, missing values, units, types, or invalid logical references."
            )
            if result.status != "INVALID":
                result.status = "NEEDS_REVIEW"
        grouped: dict[str, list[str]] = {}
        for reference in candidate.evidence:
            page = indexed.get(reference.source_page)
            quote = normalize(reference.supporting_excerpt)
            if (
                not quote
                or reference.node_key not in {node.key for node in candidate.nodes}
                or not page
                or not any(
                    quote in normalize(text)
                    for text in [page.text_content, *[block["text"] for block in page.blocks]]
                )
            ):
                result.issues.append(f"Evidence cannot be located on source page {reference.source_page}.")
                result.status = "INVALID"
            else:
                result.evidence.append(
                    (reference.node_key, reference.source_page, reference.supporting_excerpt)
                )
                grouped.setdefault(reference.node_key, []).append(reference.supporting_excerpt)
        for node in candidate.nodes:
            if node.kind == "comparison":
                if node.key not in grouped:
                    result.issues.append(f"Missing located evidence for comparison {node.key}.")
                    result.status = "INVALID"
                elif not value_grounded(node, " ".join(grouped[node.key])):
                    result.issues.append(
                        f"Value or unit for {node.key} is not explicitly grounded in its excerpt."
                    )
                    if result.status != "INVALID":
                        result.status = "NEEDS_REVIEW"
                if node.value_type == "boolean":
                    result.issues.append("Boolean interpretation requires explicit human review.")
                    if result.status == "VALIDATED":
                        result.status = "NEEDS_REVIEW"
        if (
            candidate.extraction_uncertainty
            or batch.logical_relationship == "unspecified"
            or batch.limitations
        ):
            result.issues.append("Extraction uncertainty or incomplete logical scope requires human review.")
            result.issues.extend("Model limitation: " + note for note in batch.limitations)
            if result.status == "VALIDATED":
                result.status = "NEEDS_REVIEW"
        if result.status == "INVALID":
            result.expression = None
        results.append(result)
    mark_conflicts(results, batch.logical_relationship)
    return results


def mark_conflicts(results: list[ValidatedCandidate], relationship: str) -> None:
    # Detect contradictions within AND trees and between mandatory AND candidates.
    comparisons = [
        (index, item)
        for index, result in enumerate(results)
        if result.expression
        for item in mandatory_comparisons(EXPRESSION_ADAPTER.validate_python(result.expression))
    ]
    for position, (index, first) in enumerate(comparisons):
        for other_index, second in comparisons[position + 1 :]:
            if (index == other_index or relationship == "and") and conflicts(first, second):
                for target in {index, other_index}:
                    results[target].status = "CONFLICT"
                    if "Conflicting mandatory conditions were extracted." not in results[target].issues:
                        results[target].issues.append("Conflicting mandatory conditions were extracted.")
