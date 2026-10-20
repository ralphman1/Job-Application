from datetime import date, datetime
from typing import Annotated, Self

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    HttpUrl,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.models import ApplicationStatus

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Action = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
Notes = Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)]
VacancyURL = Annotated[HttpUrl, Field(max_length=2048)]


def calendar_date(value):
    # datetime is a date subclass, and "2026-1-2" parses but is not the form we store.
    if type(value) is date:
        return value
    if isinstance(value, str) and len(value) == 10:
        try:
            parsed = date.fromisoformat(value)
            if parsed.isoformat() == value:
                return parsed
        except ValueError:
            pass
    raise ValueError("Use a calendar date in YYYY-MM-DD format")


CalendarDate = Annotated[date, BeforeValidator(calendar_date)]


class ApplicationFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company: Name
    position: Name
    applied_on: CalendarDate
    status: ApplicationStatus = ApplicationStatus.APPLIED
    vacancy_url: VacancyURL | None = None
    notes: Notes | None = None
    next_action: Action | None = None
    follow_up_on: CalendarDate | None = None

    @field_validator("notes")
    @classmethod
    def blank_notes_become_null(cls, value: str | None) -> str | None:
        return value or None

    @model_validator(mode="after")
    def next_action_needs_a_date(self) -> Self:
        if (self.next_action is None) != (self.follow_up_on is None):
            raise ValueError("next_action and follow_up_on must be set or cleared together")
        return self


class ApplicationCreate(ApplicationFields):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "company": "Example Labs",
                    "position": "Software Engineer",
                    "applied_on": "2026-10-20",
                    "vacancy_url": "https://example.com/jobs/engineer",
                    "next_action": "Ask the recruiter about the next step",
                    "follow_up_on": "2026-10-23",
                }
            ]
        },
    )


class ApplicationUpdate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [{"status": "interview", "notes": "Technical interview scheduled"}]
        },
    )

    company: Name | None = None
    position: Name | None = None
    applied_on: CalendarDate | None = None
    status: ApplicationStatus | None = None
    vacancy_url: VacancyURL | None = None
    notes: Notes | None = None
    next_action: Action | None = None
    follow_up_on: CalendarDate | None = None

    @model_validator(mode="before")
    @classmethod
    def keep_required_fields(cls, values):
        if isinstance(values, dict):
            for name in ("company", "position", "applied_on", "status"):
                if name in values and values[name] is None:
                    raise ValueError(f"{name} cannot be null")
        return values

    @field_validator("notes")
    @classmethod
    def blank_notes_become_null(cls, value: str | None) -> str | None:
        return value or None


class ApplicationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company: str
    position: str
    applied_on: date
    status: ApplicationStatus
    vacancy_url: str | None
    notes: str | None
    next_action: str | None
    follow_up_on: date | None
    created_at: datetime
    updated_at: datetime


class ApplicationPage(BaseModel):
    items: list[ApplicationRead]
    total: int


class StatusHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    application_id: int
    from_status: ApplicationStatus | None
    to_status: ApplicationStatus
    changed_at: datetime


class Summary(BaseModel):
    total: int
    by_status: dict[ApplicationStatus, int]
    overdue: int
    as_of: date


class ErrorResponse(BaseModel):
    detail: str


class ValidationErrorResponse(BaseModel):
    detail: str | list[dict]


class HealthResponse(BaseModel):
    status: str
