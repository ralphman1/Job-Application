from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app.main import create_app

ROOT = Path(__file__).resolve().parents[1]
APPLICATIONS = "/api/v1/applications"


def migrate(database_url: str) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, "head")
    return config


@pytest.fixture
def database_url(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'tracker.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    return url


@pytest.fixture
def migrated_url(database_url):
    migrate(database_url)
    return database_url


@pytest.fixture
def client(migrated_url):
    with TestClient(create_app(migrated_url)) as test_client:
        yield test_client


@pytest.fixture
def create_application(client):
    def create(**changes):
        payload = {
            "company": "Northstar Labs",
            "position": "Software Engineer",
            "applied_on": "2026-10-01",
        }
        payload.update(changes)
        response = client.post(APPLICATIONS, json=payload)
        assert response.status_code == 201, response.text
        return response.json()

    return create
