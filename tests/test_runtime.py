import os
import socket
import subprocess
import sys
import time
from contextlib import contextmanager

import httpx

from tests.conftest import APPLICATIONS, ROOT, migrate


@contextmanager
def running_server(database_url, log_path):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    environment = {**os.environ, "DATABASE_URL": database_url}
    with log_path.open("a") as log_file:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--log-level",
                "warning",
            ],
            cwd=ROOT,
            env=environment,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
        try:
            with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=2) as client:
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    assert process.poll() is None, log_path.read_text()
                    try:
                        if client.get("/health").status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    time.sleep(0.05)
                else:
                    raise AssertionError(f"Server did not become healthy: {log_path.read_text()}")
                yield client
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def test_http_workflow_survives_a_real_server_restart(database_url, tmp_path):
    migrate(database_url)
    log_path = tmp_path / "uvicorn.log"
    private_note = "private-note-not-for-server-logs"
    with running_server(database_url, log_path) as client:
        response = client.post(
            APPLICATIONS,
            json={
                "company": "Northstar Labs",
                "position": "Backend Engineer",
                "applied_on": "2026-10-01",
                "notes": private_note,
            },
        )
        assert response.status_code == 201
        application_id = response.json()["id"]
        path = f"{APPLICATIONS}/{application_id}"
        response = client.patch(
            path,
            json={
                "status": "interview",
                "next_action": "Prepare interview questions",
                "follow_up_on": "2026-10-19",
            },
        )
        assert response.status_code == 200
        saved = response.json()
        response = client.get("/api/v1/follow-ups", params={"as_of": "2026-10-20"})
        assert response.status_code == 200
        assert [item["id"] for item in response.json()["items"]] == [application_id]
        history = client.get(f"{path}/history").json()
        assert [(item["from_status"], item["to_status"]) for item in history] == [
            (None, "applied"),
            ("applied", "interview"),
        ]

    with running_server(database_url, log_path) as client:
        response = client.get(path)
        assert response.status_code == 200
        assert response.json() == saved
        assert client.get(f"{path}/history").json() == history
        summary = client.get("/api/v1/summary", params={"as_of": "2026-10-20"}).json()
        assert summary["total"] == 1
        assert summary["by_status"]["interview"] == 1
        assert summary["overdue"] == 1
        assert client.patch(path, json={"status": "accepted"}).status_code == 200
        assert client.get("/api/v1/follow-ups", params={"as_of": "2026-10-20"}).json() == {
            "items": [],
            "total": 0,
        }

    logs = log_path.read_text()
    assert private_note not in logs
    assert database_url not in logs
