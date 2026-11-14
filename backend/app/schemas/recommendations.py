"""Transient discovery inputs; never an eligibility claim or stored assessment."""

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.citizen import ProfileData
from app.schemas.scheme import SchemeRead


class RecommendationOptions(BaseModel):
    page: int = Field(default=1, ge=1, le=100_000)
    page_size: int = Field(default=9, ge=1, le=30)
    category: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]{0,59}$")
    sort_by: Literal["relevance", "name"] = "relevance"

    model_config = {"extra": "forbid"}


class RecommendationRequest(ProfileData, RecommendationOptions):
    pass


class RecommendationRead(SchemeRead):
    relevance: Literal["HIGH", "POTENTIAL", "MORE_INFORMATION"]
    matching_reasons: list[str]
    missing_information: list[str]
    ranking_points: int
    ranking_factors: dict[str, int]
    approved_rule_version: int | None = None


class RecommendationPage(BaseModel):
    items: list[RecommendationRead]
    total: int
    page: int
    page_size: int
    pages: int
    categories: list[str]
    notice: str = (
        "Recommendations are informational demonstrations, not government eligibility determinations."
    )
    algorithm_version: Literal["category-relevance-v1"] = "category-relevance-v1"
