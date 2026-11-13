"""Read-only synthetic reference evaluation. No rule is persisted or approved."""

import argparse
import asyncio
import json
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import UUID

from app.ai.provider import GeminiProvider
from app.ai.schemas import CandidateBatch
from app.ai.validation import validate_batch
from app.core.config import get_settings
from app.eligibility.engine import evaluate
from app.eligibility.expressions import EXPRESSION_ADAPTER, ProfileField, Program
from app.ingestion.pdf_parser import ParsedPage
from app.services.policy_diff import compare_policies


def reference_batch(rule: dict[str, Any]) -> CandidateBatch:
    return CandidateBatch.model_validate(
        {
            "scheme_id": str(UUID(int=1)),
            "source_document_version": str(UUID(int=2)),
            "logical_relationship": "and",
            "limitations": [],
            "candidates": [
                {
                    "condition_identifier": rule["id"],
                    "label": "Fictional reference only",
                    "root": "condition",
                    "nodes": [
                        {
                            "key": "condition",
                            "kind": "comparison",
                            "field": rule["field"],
                            "operator": rule["operator"],
                            "expected_value": rule["value"],
                            "value_type": rule["type"],
                            "units": rule["units"],
                        }
                    ],
                    "evidence": [
                        {"node_key": "condition", "source_page": 1, "supporting_excerpt": rule["text"]}
                    ],
                    "extraction_uncertainty": [],
                }
            ],
        }
    )


async def run(path: Path, provider: str) -> dict[str, Any]:
    dataset = json.loads(await asyncio.to_thread(path.read_text))
    correct = total = eligible_false = negative = missing_correct = missing_total = citations = located = 0
    extracted_correct = 0
    extraction_times = []
    statuses: list[str] = []
    settings = get_settings()
    available = bool(settings.gemini_api_key and settings.gemini_api_key.get_secret_value().strip())
    for rule in dataset["rules"]:
        gold = reference_batch(rule)
        result = gold
        if provider == "gemini" and available:
            started = perf_counter()
            result = await GeminiProvider(settings).extract(
                {
                    "scheme_id": str(gold.scheme_id),
                    "source_document_version": str(gold.source_document_version),
                    "pages": [{"page_number": 1, "text": rule["text"]}],
                }
            )
            extraction_times.append(round(1000 * (perf_counter() - started), 3))
        page = ParsedPage(page_number=1, text_content=rule["text"], blocks=[], issues=[])
        validated = validate_batch(result, [page])
        semantics = [
            (node.field, node.operator, node.expected_value)
            for candidate in result.candidates
            for node in candidate.nodes
            if node.kind == "comparison"
        ]
        extracted_correct += semantics == [(rule["field"], rule["operator"], rule["value"])]
        for candidate in validated:
            citations += len(candidate.candidate.evidence)
            located += len(candidate.evidence)
        statuses.extend(item.status for item in validated)
        expression = EXPRESSION_ADAPTER.validate_python(validate_batch(gold, [page])[0].expression)
        program = Program(
            fields=[
                ProfileField(
                    key=rule["field"],
                    label=rule["field"],
                    value_type=rule["type"],
                    section="Fictional evaluation",
                )
            ],
            expression=expression,
        )
        for example in rule["profiles"]:
            outcome = evaluate(program, example["input"]).result.value
            correct += outcome == example["result"]
            total += 1
            if example["result"] != "PASS":
                negative += 1
                eligible_false += outcome == "PASS"
            if example["result"] == "UNKNOWN":
                missing_total += 1
                missing_correct += outcome == "UNKNOWN"
    tp = fp = fn = 0

    def condition(value: Any) -> dict[str, Any]:
        return {
            "key": "income",
            "label": "Fictional income condition",
            "expression": {
                "kind": "comparison",
                "key": "income",
                "field": "annual_family_income_inr",
                "operator": "<=",
                "value_type": "number",
                "value": value,
            },
            "evidence": [],
        }

    for item in dataset["changes"]:
        predicted = (
            compare_policies([condition(item["old"])], [condition(item["new"])], complete=True)[0]
            == "MATERIAL"
        )
        tp += predicted and item["material"]
        fp += predicted and not item["material"]
        fn += not predicted and item["material"]
    live = provider == "gemini" and available
    return {
        "dataset": dataset["title"],
        "provider": "gemini" if live else "gold_fixture_validation",
        "requested_provider": provider,
        "rule_extraction_accuracy": {
            "correct": extracted_correct,
            "total": len(dataset["rules"]),
            "rate": extracted_correct / len(dataset["rules"]),
        }
        if live
        else None,
        "extraction_ms": extraction_times if live else None,
        "citation_location_accuracy": {
            "located": located,
            "total": citations,
            "rate": located / citations if citations else None,
        },
        "deterministic_decision_accuracy": {"correct": correct, "total": total, "rate": correct / total},
        "false_eligibility_rate": {
            "false_pass": eligible_false,
            "negative_cases": negative,
            "rate": eligible_false / negative,
        },
        "missing_information": {
            "correct": missing_correct,
            "total": missing_total,
            "rate": missing_correct / missing_total,
        },
        "change_detection": {
            "true_positive": tp,
            "false_positive": fp,
            "false_negative": fn,
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
        },
        "human_review_agreement": None,
        "candidate_validation_statuses": statuses,
        "limitations": [
            "Small hand-authored synthetic reference set; not representative government-policy accuracy.",
            "Gold fixture validation does not measure model extraction accuracy.",
            "No independent human-review agreement dataset is available.",
        ]
        + (
            []
            if live
            else ["Live Gemini extraction was not measured; credentials missing or fixture mode selected."]
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("/app/data/evaluation/phase7.json"))
    parser.add_argument("--provider", choices=["fixture", "gemini"], default="fixture")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args.dataset, args.provider)), indent=2))


if __name__ == "__main__":
    main()
