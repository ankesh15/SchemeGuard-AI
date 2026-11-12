from typing import Any, TypedDict


class PolicyWorkflowState(TypedDict, total=False):
    workflow_id: str
    document_version_id: str
    extraction_job_id: str
    review_id: str
    decision_id: str
    decision: str
    published_rule_set_id: str
    status: str
    proposal: dict[str, Any]
    findings: list[dict[str, Any]]


class ReviewResume(TypedDict):
    decision_id: str
