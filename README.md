# Job Application Tracker API

A local tracker for submitted job applications and dated next actions. Add an
application, record changes in its hiring stage, and find what needs attention
today. Swagger is the interface for this first iteration.

The product targets one technically comfortable job seeker using a trusted
computer. It has no accounts or authentication and is intended for local use.

## Run locally

Install [Python 3.12](https://www.python.org/downloads/) and
[uv](https://docs.astral.sh/uv/getting-started/installation/), then run these
commands from the repository root:

```sh
uv sync --frozen
uv run alembic upgrade head
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open [Swagger](http://127.0.0.1:8000/docs). The
[health endpoint](http://127.0.0.1:8000/health) reports whether the database schema
is readable. Run the migration before starting the local server: the API does
not create tables on startup.

Data is stored in `data/tracker.db`. Stopping or restarting the server preserves
it. Keep that file private; it can contain personal job-search notes.

To use a different database file, set `DATABASE_URL` for **both** migrations and
the server. The parent directory must exist. `.env.example` is provided as a
starting point; `.env` is not loaded automatically:

```sh
cp .env.example .env
# Edit DATABASE_URL in .env if needed.
uv run --env-file .env alembic upgrade head
uv run --env-file .env uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## Run with Docker

Install Docker with the Compose plugin. The same application runs in one
container; no database server or worker is required:

```sh
docker compose up --build -d
docker compose ps
docker compose logs api
```

Swagger is available at the same localhost URL. The container entrypoint applies
migrations before starting Uvicorn. The container runs as a non-root user, and
Compose publishes port 8000 only on `127.0.0.1`.

SQLite lives in the named `tracker-data` volume. `docker compose restart api`
and `docker compose down` preserve it. `docker compose down --volumes` deletes
that database. The container database and local `data/tracker.db` are separate.

## Try the workflow

With the server running, add three fictional applications:

```sh
uv run python scripts/demo.py
```

The script prints the created IDs, a reference date and the action-queue URL.
Each run adds three more records. It does not reset or replace existing data.
It accepts `--base-url` for another local port and rejects remote hosts.

Follow the [five-minute demo](docs/demo.md) to update a status in Swagger, inspect
history, close an application and confirm that data survives a restart.

To create a single application directly:

```sh
curl -X POST http://127.0.0.1:8000/api/v1/applications \
  -H 'Content-Type: application/json' \
  -d '{"company":"Example Studio","position":"Backend Engineer","applied_on":"2026-10-20","next_action":"Ask about the next stage","follow_up_on":"2026-10-23"}'
```

## API and behavior

| Method and path | Purpose |
| --- | --- |
| `POST /api/v1/applications` | Add an application |
| `GET /api/v1/applications` | Search, filter by status and paginate |
| `GET /api/v1/applications/{id}` | Read one application |
| `PATCH /api/v1/applications/{id}` | Edit details, status or next action |
| `DELETE /api/v1/applications/{id}` | Delete the application and its history |
| `GET /api/v1/applications/{id}/history` | Read status history |
| `GET /api/v1/follow-ups` | Find active actions due by `as_of` |
| `GET /api/v1/summary` | Count applications by status and overdue actions |
| `GET /health` | Check database availability |

The action text and date must both be present or both be null. PATCH validates
the final record: omitted fields stay unchanged, and explicit null clears
optional fields. Empty PATCH is a no-op.

`accepted`, `rejected` and `withdrawn` are closed. Closing preserves an action
but excludes it from the queue and overdue count; reopening includes it again.
`offer` remains active. Status changes are allowed in any direction to support
corrections and are recorded atomically with the application update.

Dates are calendar dates; timestamps are UTC. `as_of` defaults to today's UTC
date. The queue includes actions due today; overdue means strictly before that
date. List responses contain `items` and `total`, with default limit 20 and
maximum 100. Search is a literal substring of company or position with SQLite's
built-in ASCII case-insensitive behavior.

## Checks

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest
```

Tests use temporary SQLite files. The runtime test launches a real server,
checks the workflow and restarts it against the same temporary database.
CI also applies migrations to an empty database and checks for model/schema
drift with `uv run alembic check`.

## Engineering notes

- [Problem definition](docs/problem.md): target user, value hypothesis and scope.
- [SRS](docs/srs.md): requirements, acceptance criteria and API contract.
- [Architecture](docs/architecture.md): design choices and trade-offs.
- [Validation](docs/validation.md): requirement-to-test evidence and actual results.
- [Retrospective](docs/retrospective.md): limitations, changes and next iteration.
- [AI usage](docs/ai-usage.md): how AI contributed and how the result was checked.

The service uses FastAPI, Pydantic 2, SQLAlchemy 2 and Alembic. SQLite keeps
installation small. There is no frontend, reminder delivery, job scraping or
public deployment. Concurrent edits use last-write-wins, and non-ASCII case
folding is not guaranteed. User research, multi-user access and stronger
concurrency controls remain future work.
