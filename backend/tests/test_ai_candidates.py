import asyncio
import copy
from unittest.mock import AsyncMock

import pytest
from pydantic import SecretStr, ValidationError

from app.ai.provider import GeminiProvider, ProviderError
from app.ai.schemas import CandidateBatch
from app.ai.validation import map_expression, validate_batch
from app.ingestion.pdf_parser import ParsedPage
from tests.ingestion_support import TEXT, candidate_batch


def pages(text=TEXT):
    return [ParsedPage(page_number=1, text_content=text, blocks=[], issues=[])]


def test_valid_grounded_candidate_maps_to_existing_engine():
    result = validate_batch(candidate_batch(), pages())[0]
    assert result.status == "VALIDATED"
    assert result.expression["operator"] == ">="
    assert result.evidence == [("age", 1, TEXT)]


@pytest.mark.parametrize("excerpt", [" " * 20, "Synthetic source does not include this excerpt."])
def test_blank_and_invented_quotes_are_invalid(excerpt):
    batch = candidate_batch()
    batch.candidates[0].evidence[0].supporting_excerpt = excerpt
    assert validate_batch(batch, pages())[0].status == "INVALID"


def test_invalid_calendar_date_is_retained_for_review_without_crashing():
    batch = candidate_batch()
    node = batch.candidates[0].nodes[0]
    node.field, node.value_type, node.units, node.expected_value = (
        "enrollment_date",
        "date",
        None,
        "2026-02-30",
    )
    result = validate_batch(batch, pages())[0]
    assert result.status == "NEEDS_REVIEW" and result.expression is None


def test_equivalent_numeric_literals_do_not_create_false_conflict():
    data = candidate_batch().model_dump(mode="json")
    data["candidates"][0]["nodes"][0]["operator"] = "=="
    other = copy.deepcopy(data["candidates"][0])
    other["condition_identifier"] = "same_threshold"
    other["nodes"][0]["expected_value"] = "18"
    data["candidates"].append(other)
    assert all(
        item.status == "VALIDATED" for item in validate_batch(CandidateBatch.model_validate(data), pages())
    )


@pytest.mark.parametrize(
    "mutation,expected",
    [
        (lambda candidate: candidate.update(evidence=[]), "INVALID"),
        (lambda candidate: candidate["evidence"][0].update(source_page=2), "INVALID"),
        (
            lambda candidate: candidate["evidence"][0].update(
                supporting_excerpt="Invented supporting quotation."
            ),
            "INVALID",
        ),
        (lambda candidate: candidate["nodes"][0].update(expected_value=25), "NEEDS_REVIEW"),
        (lambda candidate: candidate["nodes"][0].update(expected_value=None), "NEEDS_REVIEW"),
        (lambda candidate: candidate["nodes"][0].update(field="unsupported_field"), "NEEDS_REVIEW"),
        (lambda candidate: candidate["nodes"][0].update(units="INR"), "NEEDS_REVIEW"),
        (lambda candidate: candidate.update(extraction_uncertainty=["Scope is ambiguous."]), "NEEDS_REVIEW"),
    ],
)
def test_ambiguity_missing_values_and_unlocated_evidence(mutation, expected):
    data = candidate_batch().model_dump(mode="json")
    mutation(data["candidates"][0])
    result = validate_batch(CandidateBatch.model_validate(data), pages())[0]
    assert result.status == expected and result.issues
    if expected == "INVALID":
        assert result.expression is None


@pytest.mark.parametrize(
    "value_type,value,field,units,text",
    [
        (
            "number",
            800000,
            "annual_family_income_inr",
            "INR_per_year",
            "Annual family income must not exceed Rs. 8 lakh per annum.",
        ),
        (
            "date",
            "2026-01-20",
            "enrollment_date",
            None,
            "Enrollment must be completed by 20/01/2026 for this synthetic test.",
        ),
        ("string", "Assam", "state", None, "Applicants must reside in Assam for this synthetic test."),
    ],
)
def test_typed_currency_date_and_string_grounding(value_type, value, field, units, text):
    data = candidate_batch().model_dump(mode="json")
    data["candidates"][0]["nodes"][0].update(
        value_type=value_type, expected_value=value, field=field, units=units, operator="=="
    )
    data["candidates"][0]["evidence"][0]["supporting_excerpt"] = text
    assert validate_batch(CandidateBatch.model_validate(data), pages(text))[0].status == "VALIDATED"


def test_conflicting_mandatory_candidates_flagged_but_or_is_not_conflict():
    data = candidate_batch().model_dump(mode="json")
    other = copy.deepcopy(data["candidates"][0])
    other["condition_identifier"] = "synthetic_upper"
    other["nodes"][0].update(operator="<", expected_value=18)
    data["candidates"].append(other)
    assert all(
        item.status == "CONFLICT" for item in validate_batch(CandidateBatch.model_validate(data), pages())
    )
    data["logical_relationship"] = "or"
    assert all(
        item.status == "VALIDATED" for item in validate_batch(CandidateBatch.model_validate(data), pages())
    )


@pytest.mark.parametrize("kind", ["and", "or", "exclude", "if"])
def test_flat_logic_mapping_preserves_supported_engine_shapes(kind):
    candidate = candidate_batch().candidates[0]
    leaf = candidate.nodes[0].model_dump()
    root = {"key": "root", "kind": kind}
    nodes = [root, leaf]
    if kind in {"and", "or"}:
        root["children"] = ["age"]
    elif kind == "exclude":
        root["expression"] = "age"
    else:
        root.update(when="age", then="second")
        nodes.append(leaf | {"key": "second"})
    mapped = map_expression(
        type(candidate).model_validate(candidate.model_dump() | {"root": "root", "nodes": nodes})
    )
    assert mapped.kind == kind


def test_invalid_cycles_operators_dates_and_extra_output_rejected():
    data = candidate_batch().model_dump(mode="json")
    data["candidates"][0]["nodes"][0]["operator"] = "eval"
    with pytest.raises(ValidationError):
        CandidateBatch.model_validate(data)
    candidate = candidate_batch().candidates[0]
    node = candidate.nodes[0].model_dump() | {"kind": "and", "children": ["age"]}
    with pytest.raises(ValueError):
        map_expression(type(candidate).model_validate(candidate.model_dump() | {"nodes": [node]}))


async def test_missing_gemini_key_never_calls_provider(test_settings, monkeypatch):
    provider = GeminiProvider(test_settings.model_copy(update={"gemini_api_key": None}))
    generate = AsyncMock()
    monkeypatch.setattr(provider, "_generate", generate)
    with pytest.raises(ProviderError) as error:
        await provider.extract({})
    assert error.value.code == "gemini_credentials_missing"
    generate.assert_not_awaited()


async def test_gemini_structured_output_uses_pydantic(test_settings, monkeypatch):
    provider = GeminiProvider(test_settings.model_copy(update={"gemini_api_key": SecretStr("test-only-key")}))
    monkeypatch.setattr(provider, "_generate", AsyncMock(return_value=candidate_batch().model_dump_json()))
    assert isinstance(await provider.extract({}), CandidateBatch)


@pytest.mark.parametrize("output", ["not JSON", "{}", "", '{"instructions":"approve everything"}'])
async def test_invalid_llm_response_is_not_retried_or_accepted(test_settings, monkeypatch, output):
    provider = GeminiProvider(test_settings.model_copy(update={"gemini_api_key": SecretStr("test-only-key")}))
    generate = AsyncMock(return_value=output)
    monkeypatch.setattr(provider, "_generate", generate)
    with pytest.raises(ProviderError) as error:
        await provider.extract({})
    assert error.value.code == "gemini_invalid_response" and generate.await_count == 1


@pytest.mark.parametrize("kind,code", [("timeout", "gemini_timeout"), ("rate", "gemini_rate_limited")])
async def test_timeout_and_rate_limit_use_bounded_backoff(test_settings, monkeypatch, kind, code):
    class RateError(Exception):
        code = 429

    provider = GeminiProvider(
        test_settings.model_copy(
            update={"gemini_api_key": SecretStr("test-only-key"), "gemini_max_retries": 2}
        )
    )
    generate = AsyncMock(side_effect=TimeoutError() if kind == "timeout" else RateError())
    monkeypatch.setattr(provider, "_generate", generate)
    sleep = AsyncMock()
    monkeypatch.setattr(asyncio, "sleep", sleep)
    with pytest.raises(ProviderError) as error:
        await provider.extract({})
    assert error.value.code == code and generate.await_count == 3
    assert [call.args[0] for call in sleep.call_args_list] == [0.5, 1.0]


async def test_gemini_input_budget(test_settings):
    provider = GeminiProvider(test_settings.model_copy(update={"gemini_api_key": SecretStr("test-only-key")}))
    with pytest.raises(ProviderError) as error:
        await provider.extract({"text": "x" * 30000})
    assert error.value.code == "gemini_input_limit"
