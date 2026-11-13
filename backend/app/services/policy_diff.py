"""Deterministic normalized comparison. Proposed differences are never verified facts."""

import json
import re
from decimal import Decimal
from typing import Any

from app.eligibility.expressions import EXPRESSION_ADAPTER


def normalize(value: Any) -> Any:
    if isinstance(value, dict):
        if value.get("value_type") == "number" and "value" in value:
            value = dict(value)
            raw = value["value"]
            value["value"] = (
                [str(Decimal(str(item)).normalize()) for item in raw]
                if isinstance(raw, list)
                else str(Decimal(str(raw)).normalize())
            )
        return {key: normalize(item) for key, item in sorted(value.items()) if key not in {"key", "label"}}
    if isinstance(value, list):
        return sorted([normalize(item) for item in value], key=lambda item: json.dumps(item, sort_keys=True))
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(Decimal(str(value)).normalize())
    return value


def stable_key(key: str) -> str:
    return re.sub(r"^c\d+_", "", key)


def leaves(
    expression: dict[str, Any], path: str = "", excluded: bool = False
) -> list[tuple[str, dict[str, Any]]]:
    kind = expression.get("kind")
    if kind == "comparison":
        # IDs plus field/operator context prevent unrelated conditions being paired.
        return [
            (
                f"{path}/{stable_key(expression['key'])}:{expression['field']}",
                {**expression, "excluded": excluded},
            )
        ]
    result = []
    if kind in {"and", "or"}:
        for child in expression.get("children", []):
            result += leaves(child, path + "/" + kind, excluded)
    elif kind == "exclude":
        result += leaves(expression["expression"], path + "/exclude", not excluded)
    elif kind == "if":
        for name in ("when", "then", "otherwise"):
            if expression.get(name):
                result += leaves(expression[name], path + "/" + name, excluded)
    return result


def compare_policies(
    old: list[dict[str, Any]],
    new: list[dict[str, Any]],
    *,
    old_logic: str = "and",
    new_logic: str = "and",
    complete: bool = False,
) -> tuple[str, list[dict[str, Any]]]:
    old_map: dict[str, tuple[dict[str, Any], list[dict[str, Any]]]] = {}
    new_map: dict[str, tuple[dict[str, Any], list[dict[str, Any]]]] = {}
    issues = []
    for conditions, mapping in ((old, old_map), (new, new_map)):
        for item in conditions:
            expression = item.get("expression")
            if not expression:
                issues.append(
                    {
                        "condition_id": item.get("key", "unknown"),
                        "change_type": "INCONCLUSIVE",
                        "field": None,
                        "old_value": None,
                        "new_value": None,
                        "old_evidence": [],
                        "new_evidence": item.get("evidence", []),
                        "reason": "A condition cannot be represented by the supported rule schema.",
                        "verification_status": "PENDING_REVIEW",
                    }
                )
                continue
            EXPRESSION_ADAPTER.validate_python(expression)
            for key, node in leaves(expression):
                if key in mapping:
                    raise ValueError("Ambiguous duplicate comparison identity")
                mapping[key] = (node, item.get("evidence", []))
    details = list(issues)
    for key in sorted(old_map.keys() | new_map.keys()):
        previous, old_evidence = old_map.get(key, (None, []))
        proposed, new_evidence = new_map.get(key, (None, []))
        if normalize(previous) == normalize(proposed):
            continue
        field = (proposed or previous or {}).get("field")
        change_type = "CONDITION_CHANGED"
        if previous is None:
            change_type = "NEW_EXCLUSION" if proposed and proposed.get("excluded") else "NEW_CONDITION"
        elif proposed is None:
            change_type = "REMOVED_EXCLUSION" if previous.get("excluded") else "REMOVED_CONDITION"
        elif (
            previous.get("operator") == proposed.get("operator")
            and previous.get("value_type") == proposed.get("value_type") == "number"
        ):
            before, after = previous.get("value"), proposed.get("value")
            if isinstance(before, (float, int, str)) and isinstance(after, (float, int, str)):
                if Decimal(str(after)) > Decimal(str(before)):
                    change_type = "THRESHOLD_INCREASED"
                elif Decimal(str(after)) < Decimal(str(before)):
                    change_type = "THRESHOLD_DECREASED"
        if (previous is None or proposed is None) and not complete:
            change_type = "INCONCLUSIVE_" + change_type
        details.append(
            {
                "condition_id": key,
                "field": field,
                "change_type": change_type,
                "old_value": previous,
                "new_value": proposed,
                "old_evidence": old_evidence,
                "new_evidence": new_evidence,
                "verification_status": "PENDING_REVIEW",
            }
        )
    if old_logic != new_logic:
        details.append(
            {
                "condition_id": "policy_logic",
                "field": None,
                "change_type": "LOGIC_CHANGED",
                "old_value": old_logic,
                "new_value": new_logic,
                "old_evidence": [],
                "new_evidence": [],
                "verification_status": "PENDING_REVIEW",
            }
        )
    if not details:
        return (
            "WORDING" if json.dumps(old, sort_keys=True) != json.dumps(new, sort_keys=True) else "FORMATTING"
        ), []
    if (
        issues
        or not complete
        and any(str(item["change_type"]).startswith("INCONCLUSIVE") for item in details)
    ):
        return "INCONCLUSIVE", details
    return "MATERIAL", details


def compare_document_facts(
    old_pages: list[dict[str, Any]], new_pages: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Only explicit self-contained labels, retaining exact page excerpts.

    Missing/ambiguous mentions are inconclusive; this never creates executable
    rule fields for deadlines or required-document lists.
    """

    def facts(pages: list[dict[str, Any]]) -> dict[str, list[tuple[str, dict[str, Any]]]]:
        result: dict[str, list[tuple[str, dict[str, Any]]]] = {}
        for page in pages:
            for line in str(page["text"]).splitlines():
                for field, pattern in (
                    ("application_deadline", r"(?:application deadline|last date|closing date)\s*:\s*(.+)"),
                    ("required_documents", r"required documents\s*:\s*(.+)"),
                ):
                    match = re.search(pattern, line, re.I)
                    if match:
                        value = " ".join(match.group(1).split())
                        result.setdefault(field, []).append(
                            (
                                value,
                                {
                                    "document_version_id": page["document_version_id"],
                                    "page_number": page["page_number"],
                                    "excerpt": line.strip(),
                                },
                            )
                        )
        return result

    old = facts(old_pages)
    new = facts(new_pages)
    details = []
    for field in sorted(old.keys() | new.keys()):
        before = old.get(field, [])
        after = new.get(field, [])
        if before and after and {value for value, _ in before} == {value for value, _ in after}:
            continue
        clear = len(before) == len(after) == 1
        details.append(
            {
                "condition_id": "document_fact:" + field,
                "field": field,
                "change_type": (
                    "APPLICATION_DEADLINE_CHANGED"
                    if field == "application_deadline"
                    else "REQUIRED_DOCUMENTS_CHANGED"
                )
                if clear
                else "INCONCLUSIVE_DOCUMENT_FACT",
                "old_value": before[0][0] if len(before) == 1 else None,
                "new_value": after[0][0] if len(after) == 1 else None,
                "old_evidence": [item[1] for item in before],
                "new_evidence": [item[1] for item in after],
                "verification_status": "PENDING_REVIEW",
                "executable": False,
            }
        )
    return details
