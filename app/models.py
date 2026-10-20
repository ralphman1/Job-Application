from datetime import UTC, date, datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator


class ApplicationStatus(StrEnum):
    APPLIED = "applied"
    INTERVIEW = "interview"
    OFFER = "offer"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


# Closing keeps the next action on the row, but the queue and overdue count ignore these.
CLOSED_STATUSES = (
    ApplicationStatus.ACCEPTED,
    ApplicationStatus.REJECTED,
    ApplicationStatus.WITHDRAWN,
)
STATUS_VALUES = "'applied', 'interview', 'offer', 'accepted', 'rejected', 'withdrawn'"


def utc_now() -> datetime:
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator):
    """SQLite stores datetimes without a timezone, so we write UTC and restore it on read."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("A timezone-aware timestamp is required")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value.replace(tzinfo=UTC)


class Base(DeclarativeBase):
    pass


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (
        CheckConstraint("length(trim(company)) BETWEEN 1 AND 200", name="ck_company_length"),
        CheckConstraint("length(trim(position)) BETWEEN 1 AND 200", name="ck_position_length"),
        CheckConstraint(f"status IN ({STATUS_VALUES})", name="ck_application_status"),
        CheckConstraint("vacancy_url IS NULL OR length(vacancy_url) <= 2048", name="ck_url_length"),
        CheckConstraint("notes IS NULL OR length(notes) <= 5000", name="ck_notes_length"),
        CheckConstraint(
            "(next_action IS NULL AND follow_up_on IS NULL) OR "
            "(next_action IS NOT NULL AND follow_up_on IS NOT NULL "
            "AND length(trim(next_action)) BETWEEN 1 AND 500)",
            name="ck_next_action_pair",
        ),
        Index("ix_applications_updated", "updated_at", "id"),
        Index("ix_applications_follow_up", "follow_up_on", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company: Mapped[str] = mapped_column(String(200))
    position: Mapped[str] = mapped_column(String(200))
    vacancy_url: Mapped[str | None] = mapped_column(String(2048))
    status: Mapped[str] = mapped_column(String(20), default=ApplicationStatus.APPLIED)
    applied_on: Mapped[date] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    next_action: Mapped[str | None] = mapped_column(String(500))
    follow_up_on: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)


class StatusHistory(Base):
    __tablename__ = "status_history"
    __table_args__ = (
        CheckConstraint(
            f"from_status IS NULL OR from_status IN ({STATUS_VALUES})",
            name="ck_history_from_status",
        ),
        CheckConstraint(f"to_status IN ({STATUS_VALUES})", name="ck_history_to_status"),
        Index("ix_history_application", "application_id", "changed_at", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    from_status: Mapped[str | None] = mapped_column(String(20))
    to_status: Mapped[str] = mapped_column(String(20))
    changed_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utc_now)
