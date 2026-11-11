from pydantic import BaseModel


class ValidationDetail(BaseModel):
    location: list[str | int]
    type: str
    message: str


class ErrorInfo(BaseModel):
    code: str
    message: str
    details: list[ValidationDetail] | None = None


class ErrorResponse(BaseModel):
    error: ErrorInfo
    request_id: str
