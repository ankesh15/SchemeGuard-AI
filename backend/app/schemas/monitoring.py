from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool


class MonitorCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    source_id: UUID
    enabled: StrictBool = False
    frequency: Literal["daily", "weekly"] = "weekly"
    hour_utc: int = Field(default=3, ge=0, le=23)
    weekday: int = Field(default=0, ge=0, le=6)
    min_interval_seconds: int = Field(default=3600, ge=60, le=604800)
    access_permitted: StrictBool
    access_notes: str = Field(min_length=20, max_length=2000)


class MonitorPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    enabled: StrictBool | None = None
    frequency: Literal["daily", "weekly"] | None = None
    hour_utc: int | None = Field(default=None, ge=0, le=23)
    weekday: int | None = Field(default=None, ge=0, le=6)
    min_interval_seconds: int | None = Field(default=None, ge=60, le=604800)
    access_notes: str | None = Field(default=None, min_length=20, max_length=2000)


class ClarificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    notes: str = Field(min_length=20, max_length=4000)
