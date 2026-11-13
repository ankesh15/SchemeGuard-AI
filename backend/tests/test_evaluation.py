from app.evaluate import run
from tests.conftest import DATA


async def test_reference_evaluation_is_measured_and_honest():
    report = await run(DATA / "evaluation/phase7.json", "fixture")
    assert report["rule_extraction_accuracy"] is None
    assert report["human_review_agreement"] is None
    assert report["deterministic_decision_accuracy"]["correct"] == 11
    assert report["false_eligibility_rate"]["false_pass"] == 0
    assert report["missing_information"]["correct"] == 3
    assert report["change_detection"]["false_positive"] == report["change_detection"]["false_negative"] == 0
