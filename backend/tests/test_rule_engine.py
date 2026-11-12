import ast
from itertools import product
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.demo_policy import SYNTHETIC_PASS_PROFILE, comparison, demo_program
from app.eligibility.engine import Result, combine_and, combine_or, evaluate
from app.eligibility.expressions import EXPRESSION_ADAPTER, ProfileError, Program


def program(expression, value_type="number"):
    return Program.model_validate(
        {
            "fields": [{"key": "value", "label": "Value", "section": "Test", "value_type": value_type}],
            "expression": expression,
        }
    )


@pytest.mark.parametrize(
    "operator,value,expected",
    [
        ("==", 5, "PASS"),
        ("==", 4, "FAIL"),
        ("!=", 4, "PASS"),
        ("!=", 5, "FAIL"),
        (">", 6, "PASS"),
        (">", 5, "FAIL"),
        ("<", 4, "PASS"),
        ("<", 5, "FAIL"),
        (">=", 5, "PASS"),
        (">=", 4, "FAIL"),
        ("<=", 5, "PASS"),
        ("<=", 6, "FAIL"),
        ("IN", 5, "PASS"),
        ("IN", 7, "FAIL"),
        ("NOT IN", 7, "PASS"),
        ("NOT IN", 5, "FAIL"),
    ],
)
def test_all_numeric_operators(operator, value, expected):
    rule = comparison("test", "value", operator, [4, 5, 6] if operator in {"IN", "NOT IN"} else 5)
    assert evaluate(program(rule), {"value": value}).result == expected


@pytest.mark.parametrize(
    "operator,actual,expected",
    [
        ("==", "2026-06-01", "PASS"),
        ("!=", "2026-06-02", "PASS"),
        (">", "2026-06-02", "PASS"),
        (">", "2026-06-01", "FAIL"),
        ("<", "2026-05-31", "PASS"),
        ("<", "2026-06-01", "FAIL"),
        (">=", "2026-06-01", "PASS"),
        ("<=", "2026-06-01", "PASS"),
        ("IN", "2026-06-01", "PASS"),
        ("NOT IN", "2026-06-02", "PASS"),
    ],
)
def test_date_comparisons(operator, actual, expected):
    value = ["2026-06-01"] if operator in {"IN", "NOT IN"} else "2026-06-01"
    assert (
        evaluate(
            program(comparison("test", "value", operator, value, "date"), "date"), {"value": actual}
        ).result
        == expected
    )


@pytest.mark.parametrize("operator", ["==", "!=", ">", "<", ">=", "<=", "IN", "NOT IN"])
@pytest.mark.parametrize("profile", [{}, {"value": None}])
def test_missing_never_passes_a_comparison(operator, profile):
    trace = evaluate(
        program(comparison("test", "value", operator, [1] if operator in {"IN", "NOT IN"} else 1)), profile
    )
    assert trace.result == "UNKNOWN"
    assert trace.missing_fields == ["value"]


@pytest.mark.parametrize("results", list(product(list(Result), repeat=3)))
def test_and_truth_table(results):
    expected = (
        Result.FAIL
        if Result.FAIL in results
        else Result.UNKNOWN
        if Result.UNKNOWN in results
        else Result.PASS
    )
    assert combine_and(list(results)) == expected


@pytest.mark.parametrize("results", list(product(list(Result), repeat=3)))
def test_or_truth_table(results):
    expected = (
        Result.PASS
        if Result.PASS in results
        else Result.UNKNOWN
        if Result.UNKNOWN in results
        else Result.FAIL
    )
    assert combine_or(list(results)) == expected


@pytest.mark.parametrize(
    "field,value,expected",
    [
        ("age", 18, "PASS"),
        ("age", 25, "PASS"),
        ("age", 17, "FAIL"),
        ("age", 26, "FAIL"),
        ("annual_income_inr", "300000", "PASS"),
        ("annual_income_inr", "300000.00000000000000001", "FAIL"),
        ("course", "science", "PASS"),
        ("course", "other", "FAIL"),
        ("study_mode", "part_time", "FAIL"),
        ("enrollment_date", "2026-06-01", "PASS"),
        ("enrollment_date", "2026-12-31", "PASS"),
        ("enrollment_date", "2026-05-31", "FAIL"),
        ("enrollment_date", "2027-01-01", "FAIL"),
        ("receives_other_scholarship", True, "FAIL"),
        ("receives_other_scholarship", None, "UNKNOWN"),
    ],
)
def test_fictional_policy_boundaries_and_nested_paths(field, value, expected):
    trace = evaluate(demo_program(), SYNTHETIC_PASS_PROFILE | {field: value})
    assert trace.result == expected
    assert len(trace.children) == 6


@pytest.mark.parametrize(
    "requested,percentage,expected,missing",
    [
        (False, None, "PASS", []),
        (True, 40, "PASS", []),
        (True, 39.99, "FAIL", []),
        (True, None, "UNKNOWN", ["disability_percent"]),
        (None, 100, "UNKNOWN", ["requests_disability_support"]),
    ],
)
def test_conditional_requirements(requested, percentage, expected, missing):
    trace = evaluate(
        demo_program(),
        SYNTHETIC_PASS_PROFILE | {"requests_disability_support": requested, "disability_percent": percentage},
    )
    assert trace.result == expected
    assert trace.missing_fields == missing


def test_conditional_otherwise_and_or_irrelevant_missing_values():
    rule = {
        "kind": "if",
        "key": "conditional",
        "when": comparison("guard", "value", ">", 10),
        "then": comparison("yes", "value", "<", 20),
        "otherwise": comparison("no", "value", "==", 5),
    }
    assert evaluate(program(rule), {"value": 5}).result == "PASS"
    fields = [{"key": key, "label": key, "value_type": "number", "section": "test"} for key in ("a", "b")]
    alternative = Program.model_validate(
        {
            "fields": fields,
            "expression": {
                "kind": "or",
                "key": "alternatives",
                "children": [comparison("first", "a", "==", 1), comparison("second", "b", "==", 2)],
            },
        }
    )
    trace = evaluate(alternative, {"a": 1})
    assert trace.result == "PASS" and trace.missing_fields == []
    assert trace.children[1].result == "UNKNOWN"


@pytest.mark.parametrize(
    "expression",
    [
        {"kind": "python", "key": "unsafe", "code": "__import__('os')"},
        {"kind": "and", "key": "empty", "children": []},
        comparison("bad", "value", "LIKE", "anything", "string"),
        comparison("bad", "value", ">", "alpha", "string"),
        comparison("bad", "value", "IN", []),
        comparison("bad", "value", "IN", [1, True]),
        comparison("bad", "value", "==", True),
        comparison("bad", "value", "==", "2026-02-30", "date"),
        comparison("bad", "__class__", "==", 1),
        comparison("bad", "value", "==", {"nested": 1}),
    ],
)
def test_invalid_rule_expressions_rejected(expression):
    with pytest.raises(ValidationError):
        EXPRESSION_ADAPTER.validate_python(expression)


def test_unknown_fields_duplicate_keys_and_excessive_depth_rejected():
    with pytest.raises(ValidationError):
        program(comparison("test", "undeclared", "==", 1))
    duplicate = {"kind": "and", "key": "test", "children": [comparison("test", "value", "==", 1)]}
    with pytest.raises(ValidationError):
        program(duplicate)
    nested = comparison("leaf", "value", "==", 1)
    for depth in range(15):
        nested = {"kind": "and", "key": f"group_{depth}", "children": [nested]}
    with pytest.raises(ValidationError):
        program(nested)


@pytest.mark.parametrize("value", [True, "NaN", "Infinity", "1e1000000", "-1e1000000", {}, [], "wrong"])
def test_bad_profile_types_do_not_coerce_into_numeric_results(value):
    with pytest.raises(ProfileError):
        evaluate(program(comparison("test", "value", ">=", 0)), {"value": value})


def test_decimal_precision_and_boolean_string_distinction():
    assert (
        evaluate(
            program(comparison("test", "value", ">", "0.1")), {"value": "0.1000000000000000000000000001"}
        ).result
        == "PASS"
    )
    boolean = program(comparison("boolean", "value", "==", False, "boolean"), "boolean")
    with pytest.raises(ProfileError):
        evaluate(boolean, {"value": "false"})
    assert evaluate(boolean, {"value": False}).result == "PASS"


def test_stored_expressions_are_not_executed_as_code():
    for path in Path("app/eligibility").glob("*.py"):
        tree = ast.parse(path.read_text())
        assert not any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"eval", "exec"}
            for node in ast.walk(tree)
        )
