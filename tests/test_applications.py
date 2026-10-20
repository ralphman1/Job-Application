from datetime import UTC, datetime

import pytest
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.models import Application
from tests.conftest import APPLICATIONS


def test_create_read_and_delete(client, create_application):
    record = create_application(
        company="  Northstar Labs  ",
        position=" Backend Engineer ",
        vacancy_url="https://example.com/jobs/backend",
        notes="  Ask about the team.  ",
    )
    assert record["company"] == "Northstar Labs"
    assert record["position"] == "Backend Engineer"
    assert record["notes"] == "Ask about the team."
    assert record["status"] == "applied"
    assert record["applied_on"] == "2026-10-01"
    assert record["next_action"] is None
    assert record["follow_up_on"] is None
    assert isinstance(record["id"], int)
    for field in ("created_at", "updated_at"):
        timestamp = datetime.fromisoformat(record[field])
        assert timestamp.utcoffset().total_seconds() == 0

    path = f"{APPLICATIONS}/{record['id']}"
    assert client.get(path).json() == record
    response = client.delete(path)
    assert response.status_code == 204
    assert response.content == b""
    assert client.get(path).status_code == 404


def test_repeated_company_and_position_are_separate_applications(create_application):
    first = create_application()
    second = create_application()
    assert first["id"] != second["id"]


@pytest.mark.parametrize("applied_on", ["2000-01-01", "2099-12-31"])
def test_applied_date_is_user_supplied(create_application, applied_on):
    assert create_application(applied_on=applied_on)["applied_on"] == applied_on


@pytest.mark.parametrize(
    "changes",
    [
        {"company": " "},
        {"company": None},
        {"company": "c" * 201},
        {"position": " "},
        {"position": None},
        {"position": "p" * 201},
        {"applied_on": "2026-02-30"},
        {"applied_on": None},
        {"status": "unknown"},
        {"status": None},
        {"vacancy_url": "not-a-url"},
        {"vacancy_url": "ftp://example.com/job"},
        {"notes": "n" * 5001},
        {"next_action": "a" * 501, "follow_up_on": "2026-10-20"},
        {"next_action": " ", "follow_up_on": "2026-10-20"},
        {"next_action": "Call the recruiter"},
        {"follow_up_on": "2026-10-20"},
        {"next_action": "Call", "follow_up_on": "yesterday"},
        {"id": 100},
        {"created_at": "2026-10-01T00:00:00Z"},
        {"unexpected": "value"},
    ],
)
def test_invalid_create_is_rejected_without_saving(client, changes):
    payload = {
        "company": "Northstar Labs",
        "position": "Engineer",
        "applied_on": "2026-10-01",
    }
    payload.update(changes)
    response = client.post(APPLICATIONS, json=payload)
    assert response.status_code == 422
    assert "detail" in response.json()
    assert client.get(APPLICATIONS).json() == {"items": [], "total": 0}


@pytest.mark.parametrize("field", ["company", "position", "applied_on"])
def test_required_fields_cannot_be_omitted(client, field):
    payload = {"company": "Northstar", "position": "Engineer", "applied_on": "2026-10-01"}
    del payload[field]
    assert client.post(APPLICATIONS, json=payload).status_code == 422


def test_patch_preserves_omitted_fields_and_clears_nullable_fields(client, create_application):
    record = create_application(notes="A note", vacancy_url="https://example.com/job")
    path = f"{APPLICATIONS}/{record['id']}"
    updated = client.patch(path, json={"position": " Senior Engineer "}).json()
    assert updated["position"] == "Senior Engineer"
    assert updated["notes"] == record["notes"]
    assert updated["vacancy_url"] == record["vacancy_url"]
    assert updated["created_at"] == record["created_at"]
    assert datetime.fromisoformat(updated["updated_at"]) >= datetime.fromisoformat(
        record["updated_at"]
    )

    cleared = client.patch(path, json={"notes": None, "vacancy_url": None}).json()
    assert cleared["notes"] is None
    assert cleared["vacancy_url"] is None
    assert cleared["position"] == "Senior Engineer"


@pytest.mark.parametrize("changes", [{}, {"company": "Northstar Labs"}, {"status": "applied"}])
def test_patch_without_actual_change_preserves_timestamp(client, create_application, changes):
    record = create_application()
    response = client.patch(f"{APPLICATIONS}/{record['id']}", json=changes)
    assert response.status_code == 200
    assert response.json() == record


@pytest.mark.parametrize(
    "changes",
    [
        {"company": None},
        {"position": None},
        {"applied_on": None},
        {"status": None},
        {"company": " "},
        {"status": "unknown"},
        {"vacancy_url": "file:///tmp/data"},
        {"next_action": "Follow up"},
        {"follow_up_on": "2026-10-20"},
        {"updated_at": "2026-01-01T00:00:00Z"},
        {"id": 1},
    ],
)
def test_invalid_patch_does_not_change_existing_record(client, create_application, changes):
    record = create_application()
    path = f"{APPLICATIONS}/{record['id']}"
    response = client.patch(path, json=changes)
    assert response.status_code == 422
    assert client.get(path).json() == record


def test_blank_notes_are_normalized_to_null(client, create_application):
    record = create_application(notes=" ")
    assert record["notes"] is None
    response = client.patch(f"{APPLICATIONS}/{record['id']}", json={"notes": "\n "})
    assert response.status_code == 200
    assert response.json()["notes"] is None


@pytest.mark.parametrize("method", ["get", "patch", "delete"])
def test_unknown_application_returns_404(client, method):
    request = getattr(client, method)
    arguments = {"json": {"notes": "Changed"}} if method == "patch" else {}
    response = request(f"{APPLICATIONS}/9999", **arguments)
    assert response.status_code == 404
    assert "detail" in response.json()


def test_unknown_application_history_returns_404(client):
    assert client.get(f"{APPLICATIONS}/9999/history").status_code == 404


@pytest.mark.parametrize("application_id", [0, -1, "invalid"])
def test_application_ids_must_be_positive_integers(client, application_id):
    assert client.get(f"{APPLICATIONS}/{application_id}").status_code == 422


def test_search_combines_with_status_and_counts_before_pagination(client, create_application):
    create_application(company="Northstar Labs", status="interview")
    second = create_application(company="Other", position="Northstar Engineer", status="interview")
    create_application(company="Northstar Labs", status="rejected")
    create_application(company="Unrelated")

    response = client.get(
        APPLICATIONS, params={"q": " NORTHSTAR ", "status": "interview", "limit": 1}
    )
    assert response.status_code == 200
    assert response.json()["total"] == 2
    assert [record["id"] for record in response.json()["items"]] == [second["id"]]
    next_page = client.get(
        APPLICATIONS,
        params={"q": "northstar", "status": "interview", "limit": 1, "offset": 1},
    ).json()
    assert next_page["total"] == 2
    assert len(next_page["items"]) == 1
    assert next_page["items"][0]["id"] != second["id"]
    assert client.get(APPLICATIONS, params={"q": "missing"}).json() == {"items": [], "total": 0}
    assert client.get(APPLICATIONS, params={"q": " "}).json()["total"] == 4


@pytest.mark.parametrize("literal", ["%", "_", "\\"])
def test_search_treats_sql_wildcards_as_literals(client, create_application, literal):
    match = create_application(company=f"Acme{literal}Research")
    create_application(company="Acme Research")
    response = client.get(APPLICATIONS, params={"q": literal})
    assert response.status_code == 200
    assert [record["id"] for record in response.json()["items"]] == [match["id"]]
    assert response.json()["total"] == 1


def test_application_order_has_a_stable_id_tiebreaker(client, create_application):
    records = [create_application(company=f"Company {number}") for number in range(3)]
    with Session(client.app.state.engine) as session:
        session.execute(update(Application).values(updated_at=datetime(2026, 10, 1, tzinfo=UTC)))
        session.commit()
    response = client.get(APPLICATIONS)
    assert [record["id"] for record in response.json()["items"]] == [
        record["id"] for record in reversed(records)
    ]


@pytest.mark.parametrize("endpoint", [APPLICATIONS, "/api/v1/follow-ups"])
@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 101}, {"offset": -1}])
def test_invalid_pagination_is_rejected(client, endpoint, params):
    assert client.get(endpoint, params=params).status_code == 422


def test_invalid_search_and_status_filters_are_rejected(client):
    assert client.get(APPLICATIONS, params={"q": "x" * 201}).status_code == 422
    assert client.get(APPLICATIONS, params={"status": "unknown"}).status_code == 422


def test_default_list_limit_is_twenty(client, create_application):
    for number in range(21):
        create_application(company=f"Company {number}")
    result = client.get(APPLICATIONS).json()
    assert len(result["items"]) == 20
    assert result["total"] == 21
    assert client.get(APPLICATIONS, params={"offset": 21}).json() == {"items": [], "total": 21}
