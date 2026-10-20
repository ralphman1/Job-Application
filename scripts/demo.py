"""Add fictional applications to a running local tracker."""

import argparse
import json
from datetime import UTC, datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


def request_json(base_url: str, path: str, body: dict | None = None) -> dict:
    request = Request(
        f"{base_url}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"},
    )
    with urlopen(request, timeout=5) as response:
        return json.load(response)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")
    target = urlsplit(base_url)
    if target.scheme != "http" or target.hostname not in {"127.0.0.1", "localhost", "::1"}:
        parser.error("The demo writes data; use an HTTP server on loopback.")

    today = datetime.now(UTC).date()
    samples = [
        ("Northstar Labs", "Backend Engineer", "applied", -1, "Ask about the next stage"),
        ("Harbor Analytics", "Software Engineer", "interview", 0, "Prepare interview questions"),
        ("Orchard Systems", "API Engineer", "offer", 1, "Review the offer details"),
    ]
    try:
        request_json(base_url, "/health")
        for company, position, status, days, action in samples:
            application = request_json(
                base_url,
                "/api/v1/applications",
                {
                    "company": company,
                    "position": position,
                    "status": status,
                    "applied_on": (today - timedelta(days=10)).isoformat(),
                    "vacancy_url": "https://example.com/jobs/backend-engineer",
                    "notes": "Fictional demo application.",
                    "next_action": action,
                    "follow_up_on": (today + timedelta(days=days)).isoformat(),
                },
            )
            print(f"Created {application['id']}: {company} ({status})")
        print(f"Reference date: {today}")
        print(f"Action queue: {base_url}/api/v1/follow-ups?as_of={today}")
        print(json.dumps(request_json(base_url, f"/api/v1/summary?as_of={today}"), indent=2))
    except HTTPError as exc:
        raise SystemExit(f"Tracker returned HTTP {exc.code}; check the server logs.") from exc
    except URLError as exc:
        raise SystemExit(f"Could not reach the local tracker: {exc.reason}") from exc


if __name__ == "__main__":
    main()
