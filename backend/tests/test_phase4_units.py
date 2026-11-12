from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import SecretStr, ValidationError

from app.agents.explanation_agent import ExplanationPlan, GeminiExplanationPlan
from app.agents.validation import ensure_satisfiable
from app.agents.verification_agent import comparison_findings, date_located, verify_condition
from app.core.config import Settings
from app.eligibility.expressions import Comparison, Program
from app.ingestion.pdf_parser import ParsedPage
from app.rag.embeddings import EmbeddingError, GeminiEmbeddings, LocalHashEmbeddings, normalized_vector
from app.rag.grounding import question_intent
from app.schemas.workflow import EvidenceAnchor, ProposedCondition


def comparison(key="age", operator=">=", value=18, **changes):
    return {
        "kind": "comparison",
        "key": key,
        "field": "age_years",
        "operator": operator,
        "value": value,
        "value_type": "number",
        **changes,
    }


def program(expression, **field_changes):
    return Program.model_validate(
        {
            "fields": [
                {
                    "key": "age_years",
                    "label": "Age",
                    "section": "Test",
                    "value_type": "number",
                    **field_changes,
                }
            ],
            "expression": expression,
        }
    )


@pytest.mark.parametrize(
    "operator,word", [(">=", "at least"), ("<=", "not more than"), (">", "more than"), ("<", "less than")]
)
def test_operator_verification(operator, word):
    good = Comparison.model_validate(comparison(operator=operator))
    findings = comparison_findings(good, f"Applicant age must be {word} 18 years.", "years")
    assert not any(item["severity"] == "error" for item in findings)
    bad = Comparison.model_validate(comparison(operator="=="))
    assert "operator_mismatch" in {
        item["code"] for item in comparison_findings(bad, f"Applicant age must be {word} 18 years.", "years")
    }


@pytest.mark.parametrize(
    "changes,text,units,code",
    [
        ({"value": 19}, "Age must be at least 18 years", "years", "unsupported_threshold"),
        ({}, "Age must be at least 18 years", None, "missing_units"),
        (
            {"field": "annual_family_income_inr", "value": 800000},
            "Annual family income not more than Rs. 8 lakh per annum.",
            "INR_per_month",
            "currency_units",
        ),
        (
            {"field": "disability_percent", "value": 40},
            "Disability at least 40 units",
            "percent",
            "percentage_units",
        ),
        (
            {"field": "enrollment_date", "value_type": "date", "value": "2020-01-01"},
            "The year is 2020",
            None,
            "unsupported_date",
        ),
        (
            {"field": "gender", "value_type": "string", "value": "female", "operator": "=="},
            "Male applicants only",
            None,
            "unsupported_value",
        ),
    ],
)
def test_unsupported_evidence(changes, text, units, code):
    assert code in {
        item["code"]
        for item in comparison_findings(Comparison.model_validate(comparison(**changes)), text, units)
    }


def test_verified_currency_and_date():
    node = Comparison.model_validate(
        comparison(field="annual_family_income_inr", operator="<=", value=800000)
    )
    assert not [
        item
        for item in comparison_findings(
            node, "Annual income must not exceed Rs. 8 lakh per annum.", "INR_per_year"
        )
        if item["severity"] == "error"
    ]
    assert date_located(date(2020, 1, 1), "Effective 01 January 2020")


def test_missing_or_invented_page_and_exception():
    expression = Comparison.model_validate(comparison())
    page = ParsedPage(
        page_number=1,
        text_content="Age at least 18 years, subject to institution approval.",
        blocks=[],
        issues=[],
    )
    condition = ProposedCondition(key="age", label="Age", expression=expression.model_dump(), evidence=[])
    assert "missing_evidence" in {
        item["code"] for item in verify_condition(condition, expression, {1: page}, {"age_years": "years"})
    }
    condition.evidence = [EvidenceAnchor(node_key="age", page_number=2, excerpt=page.text_content)]
    assert "unlocated_evidence" in {
        item["code"] for item in verify_condition(condition, expression, {1: page}, {"age_years": "years"})
    }
    condition.evidence[0].page_number = 1
    assert "exception_scope" in {
        item["code"] for item in verify_condition(condition, expression, {1: page}, {"age_years": "years"})
    }


@pytest.mark.parametrize(
    "left,right",
    [
        (comparison(), comparison("b", "<", 18)),
        (comparison(value=18, operator="=="), comparison("b", "!=", 18)),
        (comparison(value=[18, 19], operator="IN"), comparison("b", "NOT IN", [18, 19])),
    ],
)
def test_contradictory_conjunction(left, right):
    with pytest.raises(ValueError, match="contradictory"):
        ensure_satisfiable(program({"kind": "and", "key": "all", "children": [left, right]}))
    ensure_satisfiable(program({"kind": "or", "key": "either", "children": [left, right]}))


def test_exclusion_and_conditional_satisfiability():
    with pytest.raises(ValueError, match="contradictory"):
        ensure_satisfiable(
            program(
                {
                    "kind": "and",
                    "key": "all",
                    "children": [
                        comparison(),
                        {"kind": "exclude", "key": "exclude", "expression": comparison("other")},
                    ],
                }
            )
        )
    ensure_satisfiable(
        program(
            {
                "kind": "if",
                "key": "conditional",
                "when": comparison(),
                "then": comparison("then", ">=", 20),
                "otherwise": comparison("else", "<", 18),
            }
        )
    )


def test_unknown_operator_and_null_value_are_not_executable():
    for changes in [
        {"operator": "eval"},
        {"value": None},
        {"operator": ">", "value_type": "string", "value": "18"},
    ]:
        with pytest.raises(ValidationError):
            Comparison.model_validate(comparison(**changes))


@pytest.mark.parametrize("vector", [[], [0.0] * 768, [float("nan")] * 768, [1.0] * 767, [float("inf")] * 768])
def test_vector_validation(vector):
    with pytest.raises(EmbeddingError):
        normalized_vector(vector)


async def test_offline_embeddings_explicit_deterministic():
    provider = LocalHashEmbeddings()
    assert await provider.embed(["income evidence"]) == await provider.embed(["income evidence"])
    assert len((await provider.embed(["income evidence"]))[0]) == 768


async def test_missing_embedding_and_explanation_credentials():
    settings = Settings(gemini_api_key=None)
    with pytest.raises(EmbeddingError, match="credentials_missing"):
        await GeminiEmbeddings(settings).embed(["test"])
    with pytest.raises(ValueError, match="credentials"):
        await GeminiExplanationPlan(settings).plan({})


@pytest.mark.parametrize(
    "failure",
    [
        TimeoutError(),
        type("RateLimited", (Exception,), {"code": 429})(),
        ValueError("invalid provider response"),
    ],
)
async def test_embedding_failures_bounded_retries(failure):
    from google import genai

    settings = Settings(gemini_api_key=SecretStr("synthetic-not-real"), embedding_max_retries=1)
    asynchronous = SimpleNamespace(models=SimpleNamespace(embed_content=AsyncMock(side_effect=failure)))
    manager = AsyncMock()
    manager.__aenter__.return_value = asynchronous
    with (
        patch.object(genai, "Client", return_value=SimpleNamespace(aio=manager)),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        with pytest.raises(EmbeddingError, match="provider_unavailable"):
            await GeminiEmbeddings(settings).embed(["source text"])
    assert asynchronous.models.embed_content.await_count == (2 if not isinstance(failure, ValueError) else 1)


async def test_invalid_embedding_response():
    from google import genai

    model = SimpleNamespace(
        embed_content=AsyncMock(return_value=SimpleNamespace(embeddings=[SimpleNamespace(values=[1.0] * 10)]))
    )
    manager = AsyncMock()
    manager.__aenter__.return_value = SimpleNamespace(models=model)
    with patch.object(genai, "Client", return_value=SimpleNamespace(aio=manager)):
        with pytest.raises(EmbeddingError, match="invalid_vector"):
            await GeminiEmbeddings(Settings(gemini_api_key=SecretStr("synthetic"))).embed(["test"])


@pytest.mark.parametrize(
    "question,intent",
    [
        ("What income limit is specified?", "income"),
        ("Which documents are required?", "documents"),
        ("What are the requirements?", "requirements"),
        ("Write me a song", None),
    ],
)
def test_constrained_questions(question, intent):
    assert question_intent(question) == intent


def test_explanation_plan_cannot_contain_decision_or_threshold():
    with pytest.raises(ValidationError):
        ExplanationPlan.model_validate(
            {"trace_order": [], "citation_ids": [], "result": "PASS", "threshold": 0}
        )


def test_integer_and_input_bound_contradictions():
    for expression in [
        {
            "kind": "and",
            "key": "all",
            "children": [comparison(operator=">", value=18), comparison("upper", "<", 19)],
        },
        comparison(operator="==", value=17),
    ]:
        with pytest.raises(ValueError, match="contradictory"):
            ensure_satisfiable(program(expression, integer=True, minimum=18))


async def test_explanation_provider_context_is_bounded():
    with pytest.raises(ValueError, match="bounded"):
        await GeminiExplanationPlan(Settings(gemini_api_key=SecretStr("synthetic"))).plan(
            {"untrusted": "x" * 50000}
        )


def test_human_notes_cannot_be_whitespace():
    from app.schemas.workflow import RejectionRequest

    with pytest.raises(ValidationError):
        RejectionRequest(expected_revision=1, notes=" " * 30)


def test_date_operator_boundary_verification():
    node = Comparison.model_validate(
        comparison(field="enrollment_date", operator=">", value_type="date", value="2020-01-01")
    )
    findings = comparison_findings(node, "Enrollment must be on or before 2020-01-01.", None)
    assert "operator_mismatch" in {item["code"] for item in findings}
