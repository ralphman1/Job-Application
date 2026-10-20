from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import services
from app.database import get_session
from app.models import Application, ApplicationStatus, StatusHistory, utc_now
from app.schemas import (
    ApplicationCreate,
    ApplicationPage,
    ApplicationRead,
    ApplicationUpdate,
    CalendarDate,
    ErrorResponse,
    HealthResponse,
    StatusHistoryRead,
    Summary,
    ValidationErrorResponse,
)

SessionDep = Annotated[Session, Depends(get_session)]
ApplicationId = Annotated[int, Path(gt=0)]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]

router = APIRouter(
    prefix="/api/v1",
    responses={
        422: {"model": ValidationErrorResponse},
        500: {"model": ErrorResponse},
    },
)
health_router = APIRouter()
missing = {404: {"model": ErrorResponse}}


def load_application(session: Session, application_id: int) -> Application:
    application = session.get(Application, application_id)
    if application is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return application


@router.post(
    "/applications", response_model=ApplicationRead, status_code=201, tags=["Applications"]
)
def create_application(payload: ApplicationCreate, session: SessionDep):
    """Save an application and its first status change in one go."""
    return services.create_application(session, payload)


@router.get("/applications", response_model=ApplicationPage, tags=["Applications"])
def list_applications(
    session: SessionDep,
    q: Annotated[str | None, Query(max_length=200)] = None,
    status: ApplicationStatus | None = None,
    limit: Limit = 20,
    offset: Offset = 0,
):
    """Search company or position, optionally by status. Newest updates come first."""
    return services.list_applications(session, q=q, status=status, limit=limit, offset=offset)


@router.get(
    "/applications/{application_id}",
    response_model=ApplicationRead,
    responses=missing,
    tags=["Applications"],
)
def read_application(application_id: ApplicationId, session: SessionDep):
    """Read one application, including its current next action."""
    return load_application(session, application_id)


@router.patch(
    "/applications/{application_id}",
    response_model=ApplicationRead,
    responses=missing,
    tags=["Applications"],
)
def update_application(
    application_id: ApplicationId, payload: ApplicationUpdate, session: SessionDep
):
    """Change the fields you send. Leave a field out to keep it; send null to clear it."""
    application = load_application(session, application_id)
    try:
        return services.update_application(session, application, payload)
    except services.InvalidApplication as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.delete(
    "/applications/{application_id}",
    status_code=204,
    responses=missing,
    tags=["Applications"],
)
def delete_application(application_id: ApplicationId, session: SessionDep) -> Response:
    """Delete the application and the history that belongs to it."""
    application = load_application(session, application_id)
    session.delete(application)
    session.commit()
    return Response(status_code=204)


@router.get(
    "/applications/{application_id}/history",
    response_model=list[StatusHistoryRead],
    responses=missing,
    tags=["Applications"],
)
def read_history(application_id: ApplicationId, session: SessionDep):
    """Status changes from oldest to newest. Setting the same status again adds nothing."""
    load_application(session, application_id)
    return session.scalars(
        select(StatusHistory)
        .where(StatusHistory.application_id == application_id)
        .order_by(StatusHistory.changed_at, StatusHistory.id)
    ).all()


@router.get("/follow-ups", response_model=ApplicationPage, tags=["Follow-ups"])
def list_follow_ups(
    session: SessionDep,
    as_of: Annotated[CalendarDate | None, Query()] = None,
    limit: Limit = 20,
    offset: Offset = 0,
):
    """Active applications whose next action is due on or before as_of."""
    return services.list_follow_ups(session, as_of or utc_now().date(), limit, offset)


@router.get("/summary", response_model=Summary, tags=["Follow-ups"])
def read_summary(
    session: SessionDep,
    as_of: Annotated[CalendarDate | None, Query()] = None,
):
    """How many applications are in each status, and how many actions are already late."""
    return services.summarize(session, as_of or utc_now().date())


@health_router.get(
    "/health",
    response_model=HealthResponse,
    responses={503: {"model": ErrorResponse}},
    tags=["Health"],
)
def health(session: SessionDep):
    """Check that the tables are there, without returning any applications."""
    try:
        session.execute(select(Application).limit(1))
        session.execute(select(StatusHistory).limit(1))
    except SQLAlchemyError as error:
        raise HTTPException(status_code=503, detail="Database unavailable") from error
    return {"status": "ok"}
