"""Public grounding uses server-selected approved versions, never pending policy."""

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.agents.explanation_agent import explain_assessment
from app.api.v1.admin_workflows import DB, Embeddings
from app.api.v1.eligibility import get_eligibility_service
from app.auth.security import limit
from app.models import DocumentVersion, RulePublication, RuleSet
from app.rag.grounding import grounded_quotes, question_intent
from app.rag.retriever import retrieve_for_rule
from app.repositories.scheme import SchemeRepository
from app.schemas.eligibility import EligibilityRequest
from app.services.eligibility import EligibilityService

router = APIRouter(tags=["source-grounded explanations"])
Service = Annotated[EligibilityService, Depends(get_eligibility_service)]


class QuestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=5, max_length=500)
    document_version_id: UUID | None = None


async def public_limit(request: Request, session: DB) -> None:
    # Hash the direct connection address; never trust client forwarding headers.
    address = request.client.host if request.client else "unknown"
    await limit(session, f"public-grounding:{address}", 60, 900)


@router.post("/eligibility/explain")
async def explain(
    body: EligibilityRequest,
    request: Request,
    response: Response,
    session: DB,
    service: Service,
    embeddings: Embeddings,
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    await public_limit(request, session)
    report = await service.check(body)
    explanation = await explain_assessment(session, request.app.state.settings, embeddings, report)
    return {"report": report.model_dump(mode="json"), "explanation": explanation}


@router.get("/schemes/{scheme_id}/rule-history")
async def rule_history(scheme_id: UUID, response: Response, session: DB) -> dict[str, Any]:
    from fastapi import HTTPException

    if not await SchemeRepository(session).get(scheme_id):
        raise HTTPException(404, "Scheme not found")
    response.headers["Cache-Control"] = "no-store"
    rules = await session.scalars(
        select(RuleSet)
        .options(selectinload(RuleSet.document).selectinload(DocumentVersion.source))
        .where(RuleSet.scheme_id == scheme_id, RuleSet.approval_status == "APPROVED")
        .order_by(RuleSet.version_number.desc())
        .limit(100)
    )
    today = datetime.now(ZoneInfo("Asia/Kolkata")).date()
    items = []
    for rule in rules:
        publication = await session.scalar(
            select(RulePublication).where(RulePublication.rule_set_id == rule.id)
        )
        items.append(
            {
                **EligibilityService.version(rule).model_dump(mode="json"),
                "effective_today": rule.effective_from <= today
                and (rule.effective_to is None or rule.effective_to >= today),
                "reviewed_replacement_ids": publication.replaced_rule_set_ids if publication else [],
            }
        )
    return {
        "scheme_id": str(scheme_id),
        "items": items,
        "notice": "Approved version history. Assessments select the highest effective version; this is not government approval.",
    }


@router.post("/schemes/{scheme_id}/questions")
async def question(
    scheme_id: UUID,
    body: QuestionRequest,
    request: Request,
    response: Response,
    session: DB,
    service: Service,
    embeddings: Embeddings,
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    await public_limit(request, session)
    _, rule, _ = await service.load(scheme_id)
    intent = question_intent(body.question)
    citations, mode = [], "no_approved_source"
    # External embedding requests contain only a fixed intent, never arbitrary
    # user questions, personal data, or instructions embedded in those questions.
    if rule and intent:
        query = {
            "income": "income annual financial limit",
            "documents": "required documents certificates proof",
            "disability": "disability percentage eligibility",
            "requirements": "eligibility requirements applicant student conditions",
            "application": "application deadline date portal",
            "benefits": "benefit amount award payment",
        }[intent]
        passages, mode = await retrieve_for_rule(
            session,
            request.app.state.settings,
            embeddings,
            scheme_id,
            rule.id,
            query,
            document_version_id=body.document_version_id,
        )
        citations = grounded_quotes(query, passages)
    return {
        "answer": "The approved source contains the following passages. Read the full cited guideline for context."
        if citations
        else "The available approved source does not establish the requested information.",
        "citations": [item.model_dump(mode="json") for item in citations],
        "rule_set_id": str(rule.id) if rule else None,
        "rule_version": rule.version_number if rule else None,
        "retrieval_mode": mode,
        "notice": "Document evidence only. This answer does not assess eligibility or provide official government approval.",
    }
