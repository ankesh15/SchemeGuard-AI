from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, TypeAdapter, model_validator

ValueType = Literal["number", "string", "boolean", "date"]
type Scalar = str | int | float | bool | None
type Normalized = str | Decimal | bool | date | None


def typed_value(value: object, value_type: ValueType) -> Normalized:
    if value_type == "number":
        if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
            raise ValueError("Must be a finite number")
        try:
            number = Decimal(str(value))
        except InvalidOperation as error:
            raise ValueError("Must be a finite number") from error
        if not number.is_finite() or number.copy_abs() > Decimal("1e18"):
            raise ValueError("Number is outside the supported range")
        return number
    if value_type == "boolean":
        if type(value) is not bool:
            raise ValueError("Must be true or false")
        return value
    if value_type == "date":
        if not isinstance(value, str) or len(value) != 10:
            raise ValueError("Must be an ISO date (YYYY-MM-DD)")
        try:
            parsed = date.fromisoformat(value)
        except ValueError as error:
            raise ValueError("Must be a valid ISO date (YYYY-MM-DD)") from error
        if parsed.isoformat() != value:
            raise ValueError("Must be an ISO date (YYYY-MM-DD)")
        return parsed
    if not isinstance(value, str) or not value.strip() or len(value) > 200:
        raise ValueError("Must be a non-empty string of at most 200 characters")
    return value


class ExpressionBase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,79}$")
    label: str = Field(default="", max_length=200)


class Comparison(ExpressionBase):
    kind: Literal["comparison"]
    field: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    operator: Literal["==", "!=", ">", "<", ">=", "<=", "IN", "NOT IN"]
    value_type: ValueType
    value: JsonValue

    @model_validator(mode="after")
    def safe_typed_literal(self) -> "Comparison":
        if self.operator in {">", "<", ">=", "<="} and self.value_type not in {"number", "date"}:
            raise ValueError("Ordered comparisons require numbers or dates")
        if self.operator in {"IN", "NOT IN"}:
            if not isinstance(self.value, list) or not 1 <= len(self.value) <= 50:
                raise ValueError("Membership operators require 1 to 50 typed values")
            for value in self.value:
                typed_value(value, self.value_type)
        else:
            typed_value(self.value, self.value_type)
        return self


class Group(ExpressionBase):
    kind: Literal["and", "or"]
    children: list["Expression"] = Field(min_length=1, max_length=32)


class Exclusion(ExpressionBase):
    kind: Literal["exclude"]
    expression: "Expression"


class Conditional(ExpressionBase):
    kind: Literal["if"]
    when: "Expression"
    then: "Expression"
    otherwise: "Expression | None" = None


type Expression = Annotated[Comparison | Group | Exclusion | Conditional, Field(discriminator="kind")]
Group.model_rebuild()
Exclusion.model_rebuild()
Conditional.model_rebuild()
EXPRESSION_ADAPTER = TypeAdapter(Expression)


class Choice(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    value: str
    label: str


class Visibility(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    field: str
    equals: bool


class ProfileField(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    label: str = Field(min_length=1, max_length=120)
    value_type: ValueType
    section: str = Field(max_length=80)
    help_text: str = Field(default="", max_length=300)
    choices: list[Choice] = Field(default_factory=list, max_length=50)
    minimum: float | None = None
    maximum: float | None = None
    integer: bool = False
    visible_when: Visibility | None = None


def expression_children(expression: Expression) -> list[Expression]:
    if isinstance(expression, Group):
        return expression.children
    if isinstance(expression, Exclusion):
        return [expression.expression]
    if isinstance(expression, Conditional):
        return [expression.when, expression.then, *([expression.otherwise] if expression.otherwise else [])]
    return []


class Program(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    fields: list[ProfileField] = Field(min_length=1, max_length=32)
    expression: Expression

    @model_validator(mode="after")
    def validate_tree(self) -> "Program":
        fields = {field.key: field for field in self.fields}
        if len(fields) != len(self.fields):
            raise ValueError("Duplicate profile field")
        seen: set[str] = set()

        def walk(expression: Expression, depth: int) -> None:
            if depth > 12 or len(seen) >= 128:
                raise ValueError("Rule expression is too complex")
            if expression.key in seen:
                raise ValueError("Expression keys must be unique")
            seen.add(expression.key)
            if isinstance(expression, Comparison):
                field = fields.get(expression.field)
                if field is None or field.value_type != expression.value_type:
                    raise ValueError("Comparison must reference a field of the declared type")
            for child in expression_children(expression):
                walk(child, depth + 1)

        walk(self.expression, 0)
        for field in self.fields:
            if field.minimum is not None and field.maximum is not None and field.minimum > field.maximum:
                raise ValueError("Invalid input bounds")
            if field.visible_when and (
                field.visible_when.field not in fields
                or fields[field.visible_when.field].value_type != "boolean"
                or field.visible_when.field == field.key
            ):
                raise ValueError("Visibility must reference a different boolean field")
        return self


class ProfileError(ValueError):
    def __init__(self, field: str, message: str) -> None:
        self.field = field
        self.message = message
        super().__init__(message)


def normalize_profile(program: Program, profile: dict[str, Scalar]) -> dict[str, Normalized]:
    fields = {field.key: field for field in program.fields}
    unknown = profile.keys() - fields.keys()
    if unknown:
        raise ProfileError(sorted(unknown)[0], "Unexpected profile field")
    result: dict[str, Normalized] = {}
    for key, value in profile.items():
        if value is None:
            result[key] = None
            continue
        field = fields[key]
        try:
            normalized = typed_value(value, field.value_type)
            if isinstance(normalized, Decimal):
                if field.integer and normalized != normalized.to_integral_value():
                    raise ValueError("Must be a whole number")
                if field.minimum is not None and normalized < Decimal(str(field.minimum)):
                    raise ValueError(f"Must be at least {field.minimum:g}")
                if field.maximum is not None and normalized > Decimal(str(field.maximum)):
                    raise ValueError(f"Must be at most {field.maximum:g}")
            if field.choices and normalized not in [choice.value for choice in field.choices]:
                raise ValueError("Select one of the supported choices")
        except ValueError as error:
            raise ProfileError(key, str(error)) from error
        result[key] = normalized
    return result
