"""Explicit synthetic-fixture approval only. Never approves government rules."""

import asyncio
import hashlib
import logging
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import uuid5

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.database import make_engine
from app.core.logging import configure_logging
from app.demo_policy import DEMO_SLUG, POLICY_FILENAME, demo_program
from app.eligibility.expressions import Group
from app.models import DocumentVersion, RuleCondition, RuleEvidence, RuleSet, Scheme, SchemeSource
from app.seed import SEED_NAMESPACE

DEMO_ID = uuid5(SEED_NAMESPACE, DEMO_SLUG)
RULE_SET_ID = uuid5(DEMO_ID, "rules-v1")


async def seed_demo(session: AsyncSession, data_directory: Path) -> bool:
    await session.execute(text("SELECT pg_advisory_xact_lock(724199174)"))
    content = (data_directory / "policies" / POLICY_FILENAME).read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    existing = await session.get(RuleSet, RULE_SET_ID)
    if existing:
        document = await session.get(DocumentVersion, existing.source_document_version_id)
        if not document or document.content_sha256 != digest:
            raise ValueError("Demo policy bytes changed; create a new immutable version")
        return False
    scheme = await session.scalar(select(Scheme).where(Scheme.slug == DEMO_SLUG))
    if scheme is not None:
        raise ValueError("Existing demo slug must not be overwritten")
    session.add(
        Scheme(
            id=DEMO_ID,
            slug=DEMO_SLUG,
            is_demo=True,
            name="SchemeGuard Learning Scholarship (Fictional)",
            description="An authored, fictional scholarship for exploring explainable eligibility. It is not a government scheme and has no financial award.",
            ministry=None,
            department=None,
            category="scholarship",
            applicability="unknown",
            applicable_states=None,
            verified_on=None,
            status="unknown",
        )
    )
    await session.flush()
    source_id = uuid5(DEMO_ID, "fictional-policy-source")
    session.add(
        SchemeSource(
            id=source_id,
            scheme_id=DEMO_ID,
            url="https://example.invalid/schemeguard-demo-policy-v1",
            title="Fictional development policy v1",
            publisher="SchemeGuard development fixture",
            is_primary=True,
            supported_fields=["fictional_test_rules"],
            verified_on=date(2026, 11, 12),
            verification_notes="Authored synthetic fixture. The example.invalid address is a reserved placeholder, not an official source. Read the bundled /policies/demo-policy-v1.md file.",
        )
    )
    await session.flush()
    document_id = uuid5(DEMO_ID, "policy-document-v1")
    session.add(
        DocumentVersion(
            id=document_id,
            source_id=source_id,
            version_number=1,
            content_sha256=digest,
            content_length_bytes=len(content),
            media_type="text/markdown",
            storage_key=f"policies/{POLICY_FILENAME}",
            retrieved_at=datetime.now(UTC),
            published_on=date(2026, 11, 12),
        )
    )
    await session.flush()
    program = demo_program()
    session.add(
        RuleSet(
            id=RULE_SET_ID,
            scheme_id=DEMO_ID,
            version_number=1,
            title="Fictional learning scholarship policy v1",
            approval_status="DRAFT",
            effective_from=date(2026, 1, 1),
            source_document_version_id=document_id,
            profile_fields=[field.model_dump(mode="json") for field in program.fields],
            scope_note="Synthetic development fixture only. All thresholds and dates are invented. No government rules have been approved or evaluated.",
        )
    )
    await session.flush()
    assert isinstance(program.expression, Group)
    sections = [
        "1. Age",
        "2. Household income",
        "3. Study pathway",
        "4. Exclusion",
        "5. Conditional support",
        "6. Enrollment date",
    ]
    policy_text = content.decode("utf-8")
    for position, expression in enumerate(program.expression.children):
        condition_id = uuid5(RULE_SET_ID, expression.key)
        session.add(
            RuleCondition(
                id=condition_id,
                rule_set_id=RULE_SET_ID,
                condition_key=expression.key,
                label=expression.label,
                position=position,
                expression=expression.model_dump(mode="json"),
            )
        )
        await session.flush()
        section = sections[position]
        excerpt = policy_text.split(f"## {section}\n", 1)[1].split("\n## ", 1)[0].strip()
        session.add(
            RuleEvidence(
                id=uuid5(condition_id, section),
                rule_set_id=RULE_SET_ID,
                condition_id=condition_id,
                document_version_id=document_id,
                locator=f"Section {section}",
                excerpt=excerpt,
            )
        )
    await session.flush()
    rule_set = await session.get(RuleSet, RULE_SET_ID)
    assert rule_set is not None
    rule_set.approval_status = "APPROVED"
    rule_set.approved_at = datetime.now(UTC)
    rule_set.approved_by = "development-fixture"
    rule_set.approval_basis = "synthetic_fixture"
    await session.flush()
    return True


async def main() -> None:
    settings = get_settings()
    if settings.app_env not in {"development", "test"}:
        raise SystemExit("Synthetic fixture seeding is limited to development and test environments")
    configure_logging(settings.log_level)
    engine = make_engine(settings)
    try:
        async with async_sessionmaker(engine).begin() as session:
            # Policy assets live beside the catalog directory (or legacy file).
            inserted = await seed_demo(session, settings.seed_data_path.parent)
        logging.getLogger("schemeguard.seed").info("synthetic_fixture_seeded inserted=%s", inserted)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
