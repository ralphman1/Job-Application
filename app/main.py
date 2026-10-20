import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app import config
from app.database import build_engine
from app.routes import health_router, router

logger = logging.getLogger(__name__)


def create_app(database_url: str | None = None) -> FastAPI:
    engine = build_engine(database_url or config.database_url())

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        # Alembic owns the schema. Startup only needs to close the pool later.
        yield
        engine.dispose()

    application = FastAPI(
        title="Job Application Tracker",
        version="0.1.0",
        description=(
            "A small local tracker for job applications and the next thing to do. "
            "No login — keep it on localhost."
        ),
        lifespan=lifespan,
    )
    application.state.engine = engine
    application.include_router(router)
    application.include_router(health_router)

    @application.exception_handler(SQLAlchemyError)
    async def database_failure(_request: Request, _error: SQLAlchemyError):
        # The traceback can contain notes from the failed statement. Log the fact, not the values.
        logger.error("Database operation failed")
        return JSONResponse(status_code=500, content={"detail": "Database operation failed"})

    return application


app = create_app()
