"""Deterministic source checks produce findings, never human approval."""

import hashlib
import re
from datetime import date
from typing import Any

from app.ai.validation import FIELDS, numeric_values
from app.eligibility.expressions import Comparison, Expression, expression_children, typed_value
from app.ingestion.pdf_parser import ParsedPage
from app.ingestion.text_processor import normalize
from app.schemas.workflow import EvidenceAnchor, ProposedCondition


def walk(expression: Expression) -> list[Expression]:
    return [expression, *[node for child in expression_children(expression) for node in walk(child)]]


def finding(condition: str, code: str, message: str, severity: str = "error") -> dict[str, Any]:
    return {
        "id": hashlib.sha256(f"{condition}:{code}:{message}".encode()).hexdigest()[:24],
        "condition": condition,
        "code": code,
        "message": message,
        "severity": severity,
    }


def located(reference: EvidenceAnchor, pages: dict[int, ParsedPage]) -> bool:
    page = pages.get(reference.page_number)
    quote = normalize(reference.excerpt)
    return bool(
        page
        and quote
        and any(
            quote in normalize(value)
            for value in [page.text_content, *[str(block["text"]) for block in page.blocks]]
        )
    )


def date_located(value: date, excerpt: str) -> bool:
    return any(
        text.casefold() in normalize(excerpt).casefold()
        for text in (
            value.isoformat(),
            value.strftime("%d/%m/%Y"),
            value.strftime("%d-%m-%Y"),
            value.strftime("%d %B %Y"),
            value.strftime("%B %d, %Y"),
        )
    )


def comparison_findings(node: Comparison, excerpt: str, units: str | None) -> list[dict[str, Any]]:
    findings = []
    text = normalize(excerpt).casefold()
    values = node.value if isinstance(node.value, list) else [node.value]
    if node.value_type == "number":
        if not units:
            findings.append(
                finding(node.key, "missing_units", "Numeric fields require explicit reviewed units.")
            )
        currency = bool(units and units.startswith("INR"))
        if currency and (
            units != "INR_per_year"
            or not re.search(r"₹|\brs\.?|\binr\b|rupees?", text)
            or not re.search(r"annual|per annum|year", text)
        ):
            findings.append(
                finding(
                    node.key,
                    "currency_units",
                    "Annual INR units are not explicitly supported by the excerpt.",
                )
            )
        if units == "percent" and not re.search(r"%|percent", text):
            findings.append(
                finding(node.key, "percentage_units", "The excerpt does not establish percentage units.")
            )
        numbers = numeric_values(text, currency)
        if not all(typed_value(value, "number") in numbers for value in values):
            findings.append(
                finding(
                    node.key,
                    "unsupported_threshold",
                    "A proposed number is absent from the supporting passage.",
                )
            )
        cues = [
            (r"not less than|at least|minimum(?: of)?", ">="),
            (r"not (?:be )?more than|not exceed|up to|maximum(?: of)?|at most|no more than", "<="),
            (r"(?<!not )less than|below|under", "<"),
            (r"(?<!not )greater than|more than|above|exceed(?:s)?", ">"),
        ]
        detected = next((operator for pattern, operator in cues if re.search(pattern, text)), None)
        if detected and node.operator in {"==", ">", ">=", "<", "<="} and node.operator != detected:
            findings.append(
                finding(
                    node.key,
                    "operator_mismatch",
                    f"The excerpt indicates {detected}, while the proposed operator is {node.operator}.",
                )
            )
        elif not detected:
            findings.append(
                finding(
                    node.key,
                    "operator_ambiguous",
                    "Comparison wording requires manual verification.",
                    "warning",
                )
            )
    elif node.value_type == "date":
        date_cues = [
            (r"on or after|not before|from", ">="),
            (r"on or before|not later than|through|up to", "<="),
            (r"(?<!not )before|earlier than", "<"),
            (r"(?<!or )after|later than", ">"),
        ]
        date_operator = next((operator for pattern, operator in date_cues if re.search(pattern, text)), None)
        if date_operator and node.operator in {"==", ">", ">=", "<", "<="} and node.operator != date_operator:
            findings.append(
                finding(
                    node.key,
                    "operator_mismatch",
                    "The explicit date comparison wording disagrees with the proposed operator.",
                )
            )
        elif not date_operator:
            findings.append(
                finding(
                    node.key,
                    "date_operator_ambiguous",
                    "Manually verify the date comparison boundary and inclusive/exclusive wording.",
                    "warning",
                )
            )
        if not all(
            isinstance(parsed := typed_value(value, "date"), date) and date_located(parsed, text)
            for value in values
        ):
            findings.append(
                finding(
                    node.key,
                    "unsupported_date",
                    "A proposed date cannot be located in an explicit source calendar representation.",
                )
            )
    elif node.value_type == "string":
        canonical = re.sub(r"[-_]", " ", text)
        if not all(normalize(re.sub(r"[-_]", " ", str(value))).casefold() in canonical for value in values):
            findings.append(
                finding(
                    node.key, "unsupported_value", "A proposed categorical value is absent from the excerpt."
                )
            )
    else:
        findings.append(
            finding(
                node.key,
                "boolean_interpretation",
                "Verify the exact boolean meaning and any exclusions against the complete policy.",
                "warning",
            )
        )
    if node.operator in {"!=", "IN", "NOT IN"}:
        findings.append(
            finding(
                node.key,
                "membership_or_exclusion",
                "Verify membership, negation and exception scope against the complete policy.",
                "warning",
            )
        )
    if re.search(r"except|unless|subject to|provided that|however", text):
        findings.append(
            finding(
                node.key,
                "exception_scope",
                "The passage includes an exception/dependency; review its representation in the complete rule tree.",
                "warning",
            )
        )
    return findings


def verify_condition(
    condition: ProposedCondition, expression: Expression, pages: dict[int, ParsedPage], units: dict[str, str]
) -> list[dict[str, Any]]:
    findings = []
    nodes = walk(expression)
    node_keys = {node.key for node in nodes}
    for reference in condition.evidence:
        if reference.node_key not in node_keys or not located(reference, pages):
            findings.append(
                finding(
                    condition.key,
                    "unlocated_evidence",
                    f"Evidence for {reference.node_key} cannot be located on source page {reference.page_number}.",
                )
            )
    for node in nodes:
        if not isinstance(node, Comparison):
            continue
        references = [
            reference
            for reference in condition.evidence
            if reference.node_key == node.key and located(reference, pages)
        ]
        if not references:
            findings.append(
                finding(
                    node.key,
                    "missing_evidence",
                    "Every comparison needs its own located source-page excerpt.",
                )
            )
            continue
        if (
            node.field in FIELDS
            and units.get(node.field) != FIELDS[node.field][2]
            and node.value_type == "number"
        ):
            findings.append(
                finding(
                    node.key,
                    "field_units_mismatch",
                    "Reviewed units do not match the supported field definition.",
                )
            )
        findings.extend(
            comparison_findings(
                node, " ".join(reference.excerpt for reference in references), units.get(node.field)
            )
        )
    if not findings:
        findings.append(
            finding(
                condition.key,
                "evidence_located",
                "Typed values and comparison wording are supported by located evidence. Human review is still required.",
                "info",
            )
        )
    return findings
