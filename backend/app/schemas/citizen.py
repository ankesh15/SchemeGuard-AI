from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, StrictBool, StrictInt, field_validator

from app.core.enums import IndianState
from app.schemas.eligibility import InputValue, ProfileKey


class RegisterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=3, max_length=80, pattern=r"^[a-z][a-z0-9_.-]*$")
    password: SecretStr = Field(min_length=12, max_length=128)


class PasswordChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: SecretStr = Field(min_length=1, max_length=1024)
    new_password: SecretStr = Field(min_length=12, max_length=128)


class AccountPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=3, max_length=80, pattern=r"^[a-z][a-z0-9_.-]*$")
    current_password: SecretStr = Field(min_length=1, max_length=1024)


class AccountDelete(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: SecretStr = Field(min_length=1, max_length=1024)
    acknowledge_deletion: StrictBool


class ProfileData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    state: IndianState | None = None
    age_years: StrictInt | None = Field(default=None, ge=0, le=130)
    annual_family_income_inr: float | None = Field(
        default=None, ge=0, le=1e12, strict=True, allow_inf_nan=False
    )
    course_level: str | None = Field(default=None, min_length=1, max_length=80)
    current_student: StrictBool | None = None
    employment_status: (
        Literal["unemployed", "part_time", "full_time", "self_employed", "retired", "other"] | None
    ) = None
    field_of_study: str | None = Field(default=None, min_length=1, max_length=80)
    interests: list[str] = Field(default_factory=list, max_length=24)
    occupation: Literal["student", "employed", "self_employed", "unemployed", "retired", "other"] | None = (
        None
    )
    attributes: dict[ProfileKey, InputValue] = Field(default_factory=dict, max_length=24)

    @field_validator("interests")
    @classmethod
    def interest_names(cls, values: list[str]) -> list[str]:
        import re

        normalized = [value.strip().lower().replace("-", "_") for value in values]
        if any(not re.fullmatch(r"[a-z][a-z0-9_]{0,59}", value) for value in normalized):
            raise ValueError("Interests must use category identifiers")
        return list(dict.fromkeys(normalized))

    @field_validator("attributes")
    @classmethod
    def supported_attributes(cls, values: dict[str, InputValue]) -> dict[str, InputValue]:
        from app.ai.validation import FIELDS
        from app.eligibility.expressions import typed_value

        types = {key: value[1] for key, value in FIELDS.items()} | {
            "age": "number",
            "annual_income_inr": "number",
            "course": "string",
            "requests_disability_support": "boolean",
        }
        reserved = {
            "state",
            "age_years",
            "annual_family_income_inr",
            "course_level",
            "current_student",
            "occupation",
        }
        for key, value in values.items():
            if key not in types or key in reserved:
                raise ValueError("Additional attributes must use a supported non-identifying scheme field")
            if value is not None:
                typed_value(value, types[key])
            if key in {"disability_percent", "age", "annual_income_inr"} and value is not None:
                number = float(value)
                maximum = 100 if key == "disability_percent" else 130 if key == "age" else 1e12
                if not 0 <= number <= maximum:
                    raise ValueError("Additional numeric attribute is outside its valid input domain")
        return values


class Preferences(BaseModel):
    model_config = ConfigDict(extra="forbid")
    in_app: StrictBool = True
    automatic_reassessment: StrictBool = True
    policy_updates: StrictBool = True


class AssessmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scheme_id: UUID
    request_key: UUID
    assessed_on: date | None = None
    use_saved_profile: StrictBool = True
    profile: dict[ProfileKey, InputValue] = Field(default_factory=dict, max_length=32)
    allow_reassessment: StrictBool = False

    @field_validator("profile")
    @classmethod
    def approved_vocabulary(cls, values: dict[str, InputValue]) -> dict[str, InputValue]:
        from app.ai.validation import FIELDS

        if set(values) - (
            set(FIELDS) | {"age", "annual_income_inr", "course", "requests_disability_support"}
        ):
            raise ValueError(
                "Assessment answers must use supported scheme fields; identity information is not accepted"
            )
        return values
