"""Typed, checkpointed LangGraph stages. No node can self-approve a policy."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, nullcontext
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid5

import psycopg
from fastapi import HTTPException
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, RetryPolicy, interrupt
from psycopg.rows import dict_row
from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.agents.extraction_agent import extract_candidates
from app.agents.proposals import assemble_proposal, proposal_digest, validate_draft
from app.agents.publisher import publish
from app.agents.state import PolicyWorkflowState, ReviewResume
from app.ai.provider import GeminiProvider, LLMProvider, ProviderError
from app.core.config import Settings
from app.ingestion.storage import document_storage
from app.models import (
    AgentWorkflow,
    DocumentVersion,
    PolicyReview,
    ReviewDecision,
    ReviewRevision,
    SchemeSource,
    WorkflowEvent,
)
from app.schemas.workflow import PolicyDraft
from app.services.ingestion import approved_source, get_document


async def event(
    session: AsyncSession, workflow: AgentWorkflow, stage: str, name: str, **details: str | int | bool
) -> None:
    identifier = uuid5(workflow.id, f"event:{workflow.attempts}:{stage}:{name}")
    if not await session.get(WorkflowEvent, identifier):
        session.add(
            WorkflowEvent(id=identifier, workflow_id=workflow.id, stage=stage, event=name, details=details)
        )
    workflow.stage, workflow.updated_at = stage, datetime.now(UTC)


@asynccontextmanager
async def workflow_lock(settings: Settings, identifier: UUID) -> AsyncIterator[None]:
    # A transaction-scoped lock on a dedicated connection is released even if
    # the API process dies. It never locks business rows across the interrupt.
    engine = create_async_engine(settings.sqlalchemy_url, poolclass=NullPool, hide_parameters=True)
    key = int.from_bytes(identifier.bytes[:8], "big", signed=True)
    try:
        async with engine.begin() as connection:
            if not await connection.scalar(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": key}):
                raise HTTPException(
                    409, "This workflow is being executed; try again after its current operation"
                )
            yield
    finally:
        await engine.dispose()


class WorkflowRunner:
    def __init__(
        self,
        settings: Settings,
        sessions: async_sessionmaker[AsyncSession],
        provider: LLMProvider | None = None,
    ):
        self.settings, self.sessions = settings, sessions
        self.provider = provider or GeminiProvider(settings)

    async def prepare(self, state: PolicyWorkflowState) -> dict[str, Any]:
        async with self.sessions() as session:
            workflow = await self.load(session, state)
            document = await get_document(session, workflow.document_version_id)
            await approved_source(session, document.source_id)
            await asyncio.to_thread(
                document_storage(self.settings).read,
                document.storage_key,
                document.checksum,
                self.settings.pdf_max_bytes,
            )
            await event(session, workflow, "prepare", "source_prepared")
            await session.commit()
            return {"document_version_id": str(document.id)}

    async def extraction(self, state: PolicyWorkflowState) -> dict[str, Any]:
        async with self.sessions() as session:
            workflow = await self.load(session, state)
            job = await extract_candidates(session, self.settings, workflow, self.provider)
            await event(
                session,
                workflow,
                "extraction",
                "candidates_extracted",
                job_id=str(job.id),
                provider=job.provider,
                count=job.candidate_count,
            )
            await session.commit()
            return {"extraction_job_id": str(job.id)}

    async def verification(self, state: PolicyWorkflowState) -> dict[str, Any]:
        async with self.sessions() as session:
            workflow = await self.load(session, state)
            document = await get_document(session, workflow.document_version_id)
            draft, findings = await assemble_proposal(
                session, UUID(state["extraction_job_id"]), f"Reviewed policy: {document.scheme_name}"
            )
            await event(session, workflow, "verification", "source_findings_recorded", findings=len(findings))
            await session.commit()
            return {"proposal": draft.model_dump(mode="json"), "findings": findings}

    async def schema_validation(self, state: PolicyWorkflowState) -> dict[str, Any]:
        from app.models import RuleCandidate

        async with self.sessions() as session:
            workflow = await self.load(session, state)
            identifier = uuid5(workflow.id, "human-review-v1")
            review = await session.get(PolicyReview, identifier)
            if review is None:
                draft = PolicyDraft.model_validate(state["proposal"])
                document = await session.get(DocumentVersion, workflow.document_version_id)
                assert document is not None
                source = await session.get(SchemeSource, document.source_id)
                assert source is not None
                candidates = set(
                    await session.scalars(
                        select(RuleCandidate.id).where(RuleCandidate.job_id == workflow.extraction_job_id)
                    )
                )
                validation, _, findings = await validate_draft(
                    session, draft, document.id, source.scheme_id, candidates
                )
                original_findings = state.get("findings", []) + findings
                review = PolicyReview(
                    id=identifier,
                    workflow_id=workflow.id,
                    original_proposal=draft.model_dump(mode="json"),
                    verification_findings=list({item["id"]: item for item in original_findings}.values()),
                )
                session.add(review)
                await session.flush()
                session.add(
                    ReviewRevision(
                        id=uuid5(identifier, "revision:1"),
                        review_id=identifier,
                        revision_number=1,
                        actor_id=None,
                        proposal=draft.model_dump(mode="json"),
                        proposal_sha256=proposal_digest(draft),
                        notes="Agent-generated original proposal. No human approval has occurred.",
                    )
                )
                await event(
                    session,
                    workflow,
                    "schema_validation",
                    "proposal_validated",
                    publishable=validation.publishable,
                    errors=len(validation.errors),
                )
                await session.commit()
            return {"review_id": str(identifier)}

    async def human_review(self, state: PolicyWorkflowState) -> dict[str, Any]:
        async with self.sessions() as session:
            workflow = await self.load(session, state)
            decision = await session.scalar(
                select(ReviewDecision).where(ReviewDecision.review_id == UUID(state["review_id"]))
            )
            if decision is None:
                workflow.status = "PENDING_REVIEW"
                await event(
                    session, workflow, "human_review", "human_review_requested", review_id=state["review_id"]
                )
                await session.commit()
        # Do not catch interrupt's GraphInterrupt, and keep preceding writes
        # idempotent because LangGraph re-enters this node when resumed.
        resumed = interrupt(
            {
                "review_id": state["review_id"],
                "workflow_id": state["workflow_id"],
                "message": "An authenticated human must inspect and decide the saved proposal.",
            },
            response_schema=ReviewResume,
        )
        async with self.sessions() as session:
            recorded = await session.get(ReviewDecision, UUID(resumed["decision_id"]))
            if not recorded or str(recorded.review_id) != state["review_id"]:
                raise ValueError("The interrupt can resume only from its persisted administrator decision")
            return {"decision_id": str(recorded.id), "decision": recorded.action}

    async def publication(self, state: PolicyWorkflowState) -> dict[str, Any]:
        async with self.sessions() as session:
            rule_set = await publish(
                session, self.settings, UUID(state["workflow_id"]), UUID(state["decision_id"])
            )
            workflow = await self.load(session, state)
            await event(
                session,
                workflow,
                "publication",
                "immutable_rule_published",
                rule_set_id=str(rule_set.id),
                version=rule_set.version_number,
            )
            await session.commit()
            return {"published_rule_set_id": str(rule_set.id)}

    async def complete(self, state: PolicyWorkflowState) -> dict[str, Any]:
        async with self.sessions() as session:
            workflow = await self.load(session, state)
            workflow.status = "APPROVED" if state.get("published_rule_set_id") else "REJECTED"
            await event(session, workflow, "complete", "workflow_completed", status=workflow.status)
            await session.commit()
            return {"status": workflow.status}

    @staticmethod
    async def load(session: AsyncSession, state: PolicyWorkflowState) -> AgentWorkflow:
        workflow = await session.get(AgentWorkflow, UUID(state["workflow_id"]))
        if workflow is None or workflow.status == "CANCELLED":
            raise ValueError("Workflow is missing or cancelled")
        return workflow

    def build(self, checkpointer: AsyncPostgresSaver) -> Any:
        graph = StateGraph(PolicyWorkflowState)
        graph.add_node("prepare", self.prepare)
        graph.add_node("extraction", self.extraction)
        retry = RetryPolicy(max_attempts=2, initial_interval=0.5, max_interval=2, retry_on=OperationalError)
        graph.add_node("verification", self.verification, retry_policy=retry)
        graph.add_node("schema_validation", self.schema_validation, retry_policy=retry)
        graph.add_node("human_review", self.human_review)
        graph.add_node("publication", self.publication)
        graph.add_node("complete", self.complete)
        graph.add_edge(START, "prepare")
        for first, second in (
            ("prepare", "extraction"),
            ("extraction", "verification"),
            ("verification", "schema_validation"),
            ("schema_validation", "human_review"),
        ):
            graph.add_edge(first, second)
        graph.add_conditional_edges(
            "human_review", lambda value: "publication" if value.get("decision") == "APPROVE" else "complete"
        )
        graph.add_edge("publication", "complete")
        graph.add_edge("complete", END)
        return graph.compile(checkpointer=checkpointer)

    async def run(self, identifier: UUID, *, lock_held: bool = False) -> None:
        async with nullcontext() if lock_held else workflow_lock(self.settings, identifier):
            async with self.sessions() as session:
                workflow = await session.get(AgentWorkflow, identifier)
                if workflow is None:
                    raise HTTPException(404, "Workflow not found")
                if workflow.status in {"APPROVED", "REJECTED"}:
                    return
                if workflow.status == "CANCELLED":
                    raise HTTPException(409, "Cancelled workflows cannot resume")
                if workflow.status in {"PROCESSING", "FAILED"} and (
                    workflow.stage != "human_review" or workflow.status == "FAILED"
                ):
                    if workflow.attempts >= self.settings.workflow_max_attempts:
                        raise HTTPException(
                            409,
                            "Workflow retry limit reached; inspect history and create a new reviewed request",
                        )
                    workflow.attempts += 1
                workflow.status = "PROCESSING"
                workflow.error_code, workflow.error_message = None, None
                await event(session, workflow, workflow.stage, "execution_started")
                await session.commit()
            try:
                async with asyncio.timeout(self.settings.workflow_timeout):
                    uri = self.settings.sqlalchemy_url.set(drivername="postgresql").render_as_string(
                        hide_password=False
                    )
                    async with await psycopg.AsyncConnection.connect(
                        uri,
                        autocommit=True,
                        row_factory=dict_row,
                        options="-csearch_path=sg_checkpoints,public",
                        prepare_threshold=0,
                    ) as connection:
                        serde = JsonPlusSerializer(
                            pickle_fallback=False,
                            allowed_json_modules=[],
                            allowed_msgpack_modules=[
                                ("langgraph.types", "Interrupt"),
                                ("langgraph.types", "Send"),
                            ],
                        )
                        graph = self.build(AsyncPostgresSaver(connection, serde=serde))
                        config = {
                            "configurable": {"thread_id": str(identifier)},
                            "recursion_limit": 20,
                            "callbacks": [],
                        }
                        snapshot = await graph.aget_state(config)
                        async with self.sessions() as session:
                            decision = await session.scalar(
                                select(ReviewDecision)
                                .join(PolicyReview, PolicyReview.id == ReviewDecision.review_id)
                                .where(PolicyReview.workflow_id == identifier)
                            )
                        command: Any = {"workflow_id": str(identifier)} if not snapshot.values else None
                        if decision and any(task.interrupts for task in snapshot.tasks):
                            command = Command(resume={"decision_id": str(decision.id)})
                        await graph.ainvoke(command, config=config, durability="sync")
                        # A crash can occur after the DB review write but before
                        # the interrupt checkpoint. Re-enter once, using only the
                        # already recorded decision; never synthesize approval.
                        snapshot = await graph.aget_state(config)
                        if decision and any(task.interrupts for task in snapshot.tasks):
                            await graph.ainvoke(
                                Command(resume={"decision_id": str(decision.id)}),
                                config=config,
                                durability="sync",
                            )
            except (Exception, asyncio.CancelledError) as error:
                async with self.sessions() as session:
                    workflow = await session.get(AgentWorkflow, identifier)
                    assert workflow is not None
                    workflow.status = "FAILED"
                    workflow.error_code = (
                        error.code
                        if isinstance(error, ProviderError)
                        else "workflow_timeout"
                        if isinstance(error, TimeoutError)
                        else "workflow_interrupted"
                        if isinstance(error, asyncio.CancelledError)
                        else "workflow_failed"
                    )
                    workflow.error_message = "Workflow execution stopped safely. Inspect its extraction/review history before resuming."
                    await event(
                        session,
                        workflow,
                        workflow.stage,
                        "execution_failed",
                        code=workflow.error_code,
                        error_type=type(error).__name__,
                    )
                    await session.commit()
                if isinstance(error, asyncio.CancelledError):
                    raise
