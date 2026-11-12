"""Explicit operator-only mock demonstration on an already ingested official PDF.

This is never exposed as an API mode and is never an automatic Gemini fallback.
"""

import argparse
import asyncio
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.ai.schemas import CandidateBatch
from app.auth.security import Administrator
from app.core.config import get_settings
from app.core.database import make_engine
from app.ingestion.text_processor import normalize
from app.models import Scheme, User
from app.services.ingestion import get_document, process_document

OFFICIAL_URL = "https://scholarships.gov.in/public/schemeGuidelines/AICTE/AICTE_2012_G.pdf"
EXCERPT = "Specially-abled student, having disability of not less than 40%."


class SupervisedOfficialFixture:
    name = "fixture"
    model: str | None = "supervised-mock-historical-saksham"

    async def extract(self, context: dict[str, Any]) -> CandidateBatch:
        found = any(
            part["page_number"] == 2 and normalize(EXCERPT) in normalize(part["text"])
            for part in context["sections"]
        )
        return CandidateBatch.model_validate(
            {
                "scheme_id": context["scheme_id"],
                "source_document_version": context["source_document_version"],
                "logical_relationship": "and",
                "limitations": [
                    "Supervised MOCK demonstration of one historical condition; not a complete policy extraction or current eligibility rule."
                ],
                "candidates": [
                    {
                        "condition_identifier": "historical_disability_percentage",
                        "label": "Historical disability percentage — supervised mock",
                        "root": "disability",
                        "nodes": [
                            {
                                "key": "disability",
                                "kind": "comparison",
                                "field": "disability_percent",
                                "operator": ">=",
                                "expected_value": 40,
                                "value_type": "number",
                                "units": "percent",
                            }
                        ],
                        "evidence": [
                            {"node_key": "disability", "source_page": 2, "supporting_excerpt": EXCERPT}
                        ],
                        "extraction_uncertainty": [
                            "July 2020 guideline: current policy applicability and all other conditions require human verification."
                        ],
                    }
                ]
                if found
                else [],
            }
        )


async def main(identifier: UUID, username: str) -> None:
    settings = get_settings()
    if settings.app_env == "production":
        raise ValueError("Mock demonstrations are disabled in production")
    engine = make_engine(settings)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            user = await session.scalar(
                select(User).where(User.username == username, User.role == "admin", User.is_active.is_(True))
            )
            if not user:
                raise ValueError("Provision an active administrator before this operator-only demonstration")
            document = await get_document(session, identifier)
            scheme = await session.get(Scheme, document.scheme_id)
            if document.source_url != OFFICIAL_URL or not scheme or scheme.slug != "aicte-saksham-degree":
                raise ValueError(
                    "The fixture is restricted to its reviewed official source and matching scheme"
                )
            administrator = Administrator(
                user.id, user.username, datetime.now(UTC) + timedelta(minutes=10), "operator-cli"
            )
            job = await process_document(
                session, settings, administrator, identifier, "gemini", SupervisedOfficialFixture()
            )
            print(
                json.dumps(
                    {
                        "job_id": str(job.id),
                        "document_version_id": str(identifier),
                        "status": job.status,
                        "candidate_count": job.candidate_count,
                        "provider": job.provider,
                        "notice": "MOCK provider, real historical PDF, pending review only; no rules published.",
                    }
                )
            )
            if job.status == "FAILED" or job.candidate_count != 1:
                raise ValueError(
                    "Supervised demonstration did not produce its single grounded pending candidate"
                )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--document-id", required=True, type=UUID)
    parser.add_argument("--admin-username", required=True)
    parser.add_argument("--acknowledge-mock", required=True, action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.document_id, args.admin_username))
