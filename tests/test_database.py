import re

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select, text

from app.database import build_engine
from app.main import create_app
from app.models import Application, Base
from tests.conftest import migrate


def test_migration_builds_schema_matching_models_and_is_repeatable(database_url):
    config = migrate(database_url)
    engine = build_engine(database_url)
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(connection, opts={"compare_type": True})
            assert (
                context.get_current_revision()
                == ScriptDirectory.from_config(config).get_current_head()
            )
            assert compare_metadata(context, Base.metadata) == []
            assert connection.execute(select(Application).limit(1)).all() == []
            assert connection.scalar(text("PRAGMA foreign_keys")) == 1
        command.upgrade(config, "head")
        assert set(Base.metadata.tables).issubset(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_health_checks_readable_schema(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_fails_cleanly_before_migration(database_url):
    with TestClient(create_app(database_url)) as client:
        response = client.get("/health")
        assert response.status_code == 503
        assert "detail" in response.json()
        assert "sqlite" not in response.text.lower()
        assert "tracker.db" not in response.text


def test_openapi_exposes_workflow_and_response_schemas(client):
    assert client.get("/docs").status_code == 200
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    for path, methods in {
        "/api/v1/applications": ("get", "post"),
        "/api/v1/applications/{application_id}": ("get", "patch", "delete"),
        "/api/v1/applications/{application_id}/history": ("get",),
        "/api/v1/follow-ups": ("get",),
        "/api/v1/summary": ("get",),
    }.items():
        # Parameter names are documentation details; route shape is the contract.
        route = re.sub(r"\{[^}]+\}", "{id}", path)
        actual = next(key for key in schema["paths"] if re.sub(r"\{[^}]+\}", "{id}", key) == route)
        for method in methods:
            operation = schema["paths"][actual][method]
            assert operation.get("description")
            success_code = "201" if method == "post" else "204" if method == "delete" else "200"
            assert success_code in operation["responses"]
            if method != "delete":
                assert operation["responses"][success_code]["content"]["application/json"]["schema"]
