from datetime import date

from pydantic import ValidationError
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import CLOSED_STATUSES, Application, ApplicationStatus, StatusHistory, utc_now
from app.schemas import ApplicationCreate, ApplicationFields, ApplicationUpdate


class InvalidApplication(ValueError):
    pass


def _page(session: Session, query, *, limit: int, offset: int, order_by) -> dict:
    total = session.scalar(select(func.count()).select_from(query.subquery()))
    items = session.scalars(query.order_by(*order_by).limit(limit).offset(offset)).all()
    return {"items": items, "total": total}


def _as_stored(values: dict) -> dict:
    # HttpUrl is not a string column.
    if values["vacancy_url"] is not None:
        values["vacancy_url"] = str(values["vacancy_url"])
    return values


def create_application(session: Session, data: ApplicationCreate) -> Application:
    now = utc_now()
    application = Application(**_as_stored(data.model_dump()), created_at=now, updated_at=now)
    session.add(application)
    session.flush()
    session.add(
        StatusHistory(
            application_id=application.id,
            from_status=None,
            to_status=application.status,
            changed_at=application.created_at,
        )
    )
    session.commit()
    session.refresh(application)
    return application


def update_application(
    session: Session, application: Application, data: ApplicationUpdate
) -> Application:
    changes = data.model_dump(exclude_unset=True)
    # Check the row after the patch, not the body on its own. A date without
    # an action (or the other way around) is invalid even if only one side was sent.
    merged = {name: getattr(application, name) for name in ApplicationFields.model_fields}
    merged.update(changes)
    try:
        validated = ApplicationFields.model_validate(merged)
    except ValidationError as error:
        raise InvalidApplication(
            "next_action and follow_up_on must be set or cleared together"
        ) from error

    values = _as_stored(validated.model_dump())
    changed = {name: value for name, value in values.items() if getattr(application, name) != value}
    if not changed:
        return application

    previous_status = application.status
    for name, value in changed.items():
        setattr(application, name, value)
    application.updated_at = utc_now()
    if application.status != previous_status:
        session.add(
            StatusHistory(
                application_id=application.id,
                from_status=previous_status,
                to_status=application.status,
                changed_at=application.updated_at,
            )
        )
    session.commit()
    session.refresh(application)
    return application


def list_applications(
    session: Session,
    *,
    q: str | None,
    status: ApplicationStatus | None,
    limit: int,
    offset: int,
) -> dict:
    query = select(Application)
    term = (q or "").strip()
    if term:
        query = query.where(
            or_(
                Application.company.icontains(term, autoescape=True),
                Application.position.icontains(term, autoescape=True),
            )
        )
    if status is not None:
        query = query.where(Application.status == status)
    return _page(
        session,
        query,
        limit=limit,
        offset=offset,
        order_by=(Application.updated_at.desc(), Application.id.desc()),
    )


def list_follow_ups(session: Session, as_of: date, limit: int, offset: int) -> dict:
    # Due today still belongs in the queue. Overdue is stricter and lives in summarize().
    query = select(Application).where(
        Application.status.not_in(CLOSED_STATUSES),
        Application.next_action.is_not(None),
        Application.follow_up_on <= as_of,
    )
    return _page(
        session,
        query,
        limit=limit,
        offset=offset,
        order_by=(Application.follow_up_on, Application.id),
    )


def summarize(session: Session, as_of: date) -> dict:
    counts = dict(
        session.execute(select(Application.status, func.count()).group_by(Application.status)).all()
    )
    by_status = {status.value: counts.get(status.value, 0) for status in ApplicationStatus}
    overdue = session.scalar(
        select(func.count())
        .select_from(Application)
        .where(
            Application.status.not_in(CLOSED_STATUSES),
            Application.next_action.is_not(None),
            Application.follow_up_on < as_of,
        )
    )
    return {
        "total": sum(by_status.values()),
        "by_status": by_status,
        "overdue": overdue,
        "as_of": as_of,
    }
