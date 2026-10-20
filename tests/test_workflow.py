from datetime import UTC, datetime

import pytest
from sqlalchemy import event, func, select, update
from sqlalchemy.exc import StatementError
from sqlalchemy.orm import Session

from app.models import Application, StatusHistory
from tests.conftest import APPLICATIONS

FOLLOW_UPS = "/api/v1/follow-ups"
SUMMARY = "/api/v1/summary"
AS_OF = "2026-10-20"
STATUSES = ("applied", "interview", "offer", "accepted", "rejected", "withdrawn")


def test_complete_application_workflow(client, create_application):
    record = create_application()
    path = f"{APPLICATIONS}/{record['id']}"
    initial_history = client.get(f"{path}/history").json()
    assert len(initial_history) == 1
    assert initial_history[0]["application_id"] == record["id"]
    assert initial_history[0]["from_status"] is None
    assert initial_history[0]["to_status"] == "applied"
    assert datetime.fromisoformat(initial_history[0]["changed_at"]).utcoffset().total_seconds() == 0

    response = client.patch(
        path,
        json={
            "status": "interview",
            "next_action": " Prepare questions ",
            "follow_up_on": AS_OF,
        },
    )
    assert response.status_code == 200
    assert response.json()["next_action"] == "Prepare questions"
    queue = client.get(FOLLOW_UPS, params={"as_of": AS_OF}).json()
    assert [item["id"] for item in queue["items"]] == [record["id"]]
    assert queue["total"] == 1
    history = client.get(f"{path}/history").json()
    assert [(item["from_status"], item["to_status"]) for item in history] == [
        (None, "applied"),
        ("applied", "interview"),
    ]

    assert client.patch(path, json={"status": "interview"}).status_code == 200
    assert client.get(f"{path}/history").json() == history
    assert client.patch(path, json={"status": "accepted"}).status_code == 200
    assert client.get(FOLLOW_UPS, params={"as_of": AS_OF}).json() == {"items": [], "total": 0}
    stored = client.get(path).json()
    assert stored["next_action"] == "Prepare questions"
    assert stored["follow_up_on"] == AS_OF


def test_next_action_patch_validates_the_combined_record(client, create_application):
    record = create_application(next_action="Send a message", follow_up_on="2026-10-19")
    path = f"{APPLICATIONS}/{record['id']}"
    response = client.patch(path, json={"follow_up_on": AS_OF})
    assert response.status_code == 200
    assert response.json()["next_action"] == "Send a message"
    assert response.json()["follow_up_on"] == AS_OF

    response = client.patch(path, json={"next_action": "Call instead"})
    assert response.status_code == 200
    assert response.json()["follow_up_on"] == AS_OF
    for changes in ({"next_action": None}, {"follow_up_on": None}, {"next_action": " "}):
        invalid = client.patch(path, json=changes)
        assert invalid.status_code == 422
        assert client.get(path).json() == response.json()

    cleared = client.patch(path, json={"next_action": None, "follow_up_on": None})
    assert cleared.status_code == 200
    assert cleared.json()["next_action"] is None
    assert cleared.json()["follow_up_on"] is None
    assert client.get(FOLLOW_UPS, params={"as_of": AS_OF}).json()["total"] == 0


@pytest.mark.parametrize("status", ["accepted", "rejected", "withdrawn"])
def test_closed_applications_keep_actions_and_reopening_restores_them(
    client, create_application, status
):
    record = create_application(status=status, next_action="Follow up", follow_up_on="2026-10-19")
    path = f"{APPLICATIONS}/{record['id']}"
    assert client.get(FOLLOW_UPS, params={"as_of": AS_OF}).json()["total"] == 0
    assert client.get(SUMMARY, params={"as_of": AS_OF}).json()["overdue"] == 0
    assert client.patch(path, json={"status": "applied"}).status_code == 200
    assert client.get(FOLLOW_UPS, params={"as_of": AS_OF}).json()["total"] == 1
    assert client.get(SUMMARY, params={"as_of": AS_OF}).json()["overdue"] == 1
    assert client.get(path).json()["follow_up_on"] == "2026-10-19"


def test_queue_includes_today_and_overdue_but_not_future_with_stable_sort(
    client, create_application
):
    today = create_application(next_action="Prepare", follow_up_on=AS_OF, status="offer")
    overdue = create_application(next_action="Call", follow_up_on="2026-10-19")
    same_day = create_application(next_action="Email", follow_up_on=AS_OF)
    create_application(next_action="Future", follow_up_on="2026-10-21")
    create_application()
    response = client.get(FOLLOW_UPS, params={"as_of": AS_OF})
    assert response.status_code == 200
    assert response.json()["total"] == 3
    assert [item["id"] for item in response.json()["items"]] == [
        overdue["id"],
        today["id"],
        same_day["id"],
    ]
    page = client.get(FOLLOW_UPS, params={"as_of": AS_OF, "limit": 1, "offset": 1}).json()
    assert page["total"] == 3
    assert [item["id"] for item in page["items"]] == [today["id"]]
    assert client.get(SUMMARY, params={"as_of": AS_OF}).json()["overdue"] == 1


def test_summary_includes_every_status_and_updates_after_delete(client, create_application):
    assert client.get(SUMMARY, params={"as_of": AS_OF}).json() == {
        "total": 0,
        "by_status": dict.fromkeys(STATUSES, 0),
        "overdue": 0,
        "as_of": AS_OF,
    }
    for status in STATUSES:
        create_application(status=status, next_action="Follow up", follow_up_on="2026-10-19")
    extra = create_application(next_action="Today", follow_up_on=AS_OF)
    result = client.get(SUMMARY, params={"as_of": AS_OF}).json()
    assert result["total"] == 7
    assert result["by_status"] == {**dict.fromkeys(STATUSES, 1), "applied": 2}
    assert result["overdue"] == 3
    assert client.delete(f"{APPLICATIONS}/{extra['id']}").status_code == 204
    assert client.get(SUMMARY, params={"as_of": AS_OF}).json()["by_status"]["applied"] == 1


def test_default_reference_date_is_today_in_utc(client):
    before = datetime.now(UTC).date().isoformat()
    result = client.get(SUMMARY)
    after = datetime.now(UTC).date().isoformat()
    assert result.status_code == 200
    assert result.json()["as_of"] in {before, after}


@pytest.mark.parametrize("endpoint", [FOLLOW_UPS, SUMMARY])
def test_invalid_reference_date_is_rejected(client, endpoint):
    assert client.get(endpoint, params={"as_of": "2026-02-30"}).status_code == 422


def test_initial_history_uses_the_supplied_status(client, create_application):
    record = create_application(status="offer")
    history = client.get(f"{APPLICATIONS}/{record['id']}/history").json()
    assert len(history) == 1
    assert (history[0]["from_status"], history[0]["to_status"]) == (None, "offer")


def test_history_ties_use_insertion_order(client, create_application):
    record = create_application()
    path = f"{APPLICATIONS}/{record['id']}"
    for status in ("offer", "rejected", "interview"):
        assert client.patch(path, json={"status": status}).status_code == 200
    with Session(client.app.state.engine) as session:
        session.execute(update(StatusHistory).values(changed_at=datetime(2026, 10, 1, tzinfo=UTC)))
        session.commit()
    history = client.get(f"{path}/history").json()
    assert [item["to_status"] for item in history] == [
        "applied",
        "offer",
        "rejected",
        "interview",
    ]
    assert [item["id"] for item in history] == sorted(item["id"] for item in history)


def test_status_change_rolls_back_when_history_cannot_be_saved(client, create_application):
    record = create_application(notes="Keep this note")
    path = f"{APPLICATIONS}/{record['id']}"

    def reject_history(mapper, connection, target):
        raise RuntimeError("Injected history failure")

    event.listen(StatusHistory, "before_insert", reject_history)
    try:
        with pytest.raises(RuntimeError, match="Injected history failure"):
            client.patch(path, json={"status": "offer", "notes": "Should roll back"})
    finally:
        event.remove(StatusHistory, "before_insert", reject_history)

    assert client.get(path).json() == record
    assert len(client.get(f"{path}/history").json()) == 1
    assert client.patch(path, json={"status": "offer"}).status_code == 200


def test_create_rolls_back_when_initial_history_cannot_be_saved(client):
    def reject_history(mapper, connection, target):
        raise RuntimeError("Injected initial history failure")

    event.listen(StatusHistory, "before_insert", reject_history)
    try:
        with pytest.raises(RuntimeError, match="Injected initial history failure"):
            client.post(
                APPLICATIONS,
                json={"company": "Example", "position": "Engineer", "applied_on": AS_OF},
            )
    finally:
        event.remove(StatusHistory, "before_insert", reject_history)

    assert client.get(APPLICATIONS).json() == {"items": [], "total": 0}
    with Session(client.app.state.engine) as session:
        assert session.scalar(select(func.count()).select_from(Application)) == 0
        assert session.scalar(select(func.count()).select_from(StatusHistory)) == 0


def test_delete_cascades_history(client, create_application):
    record = create_application()
    path = f"{APPLICATIONS}/{record['id']}"
    assert client.patch(path, json={"status": "interview"}).status_code == 200
    with Session(client.app.state.engine) as session:
        assert session.scalar(select(func.count()).select_from(StatusHistory)) == 2
    assert client.delete(path).status_code == 204
    with Session(client.app.state.engine) as session:
        assert session.scalar(select(func.count()).select_from(StatusHistory)) == 0


def test_database_failure_does_not_expose_personal_values(client, create_application, caplog):
    record = create_application()
    path = f"{APPLICATIONS}/{record['id']}"
    private_note = "personal-recruiter-note"

    def reject_history(mapper, connection, target):
        raise StatementError(
            "Injected database error", "INSERT ...", {"notes": private_note}, RuntimeError()
        )

    event.listen(StatusHistory, "before_insert", reject_history)
    try:
        response = client.patch(path, json={"status": "interview", "notes": private_note})
    finally:
        event.remove(StatusHistory, "before_insert", reject_history)

    assert response.status_code == 500
    assert "detail" in response.json()
    assert private_note not in response.text
    assert "INSERT" not in response.text
    assert private_note not in caplog.text
    assert client.get(path).json() == record


def test_follow_up_default_limit_is_twenty(client, create_application):
    for number in range(21):
        create_application(company=f"Company {number}", next_action="Follow up", follow_up_on=AS_OF)
    result = client.get(FOLLOW_UPS, params={"as_of": AS_OF}).json()
    assert len(result["items"]) == 20
    assert result["total"] == 21
