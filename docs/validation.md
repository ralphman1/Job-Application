# Validation against the SRS

Validated on 20 October 2026. The first iteration implements every requirement in
SRS 1.0. The product value remains a hypothesis; these checks establish system
behavior, not a reduction in missed follow-ups for real users.

## Executed checks

| Check | Actual result |
| --- | --- |
| `uv sync --frozen` dependency installation | Locked dependencies installed successfully. |
| `uv run ruff check .` | All checks passed. |
| `uv run ruff format --check .` | 23 Python files already formatted. |
| `uv run pytest` | **86 passed**, one upstream deprecation warning, in 3.72 seconds. |
| `uv run alembic upgrade head` | Initial schema created successfully on the local database. |
| `uv run alembic check` | No new upgrade operations detected. |
| Docker Compose build and startup | Image built; migration entrypoint succeeded; container became healthy. |
| Documented HTTP demo script | Three fictional applications created; total 3, overdue 1. |
| Docker HTTP workflow | Search, status changes, history, close/reopen, queue and summary agreed with the SRS. |
| Container identity and port | UID 10001; published port restricted to 127.0.0.1:8000. |
| Restart and container recreation | The application and its four history events survived both operations. |
| Privacy checks | A synthetic private note was absent from responses to injected database failures and from captured logs. |

The local test environment used Python 3.12.5, SQLite 3.46.1 and uv 0.12.10.
The built Linux container used Python 3.12.15. Runtime dependency versions are
recorded in `uv.lock` rather than duplicated here.

Starlette emits one deprecation warning for the locked HTTPX/TestClient
combination and recommends its newer test transport. The current combination
passes the suite; the warning is not suppressed. Updating the test client should
be reviewed with a future dependency update. It does not affect the runtime API.

## Requirement traceability

The test names below are in [application tests](../tests/test_applications.py),
[workflow tests](../tests/test_workflow.py),
[database tests](../tests/test_database.py) and
[real HTTP runtime tests](../tests/test_runtime.py).

| Requirement | Implementation | Test or performed check | Result |
| --- | --- | --- | --- |
| FR-01 Create/read | Application routes and service | `test_create_read_and_delete`, invalid-create cases | Pass |
| FR-02 Edit/delete | Merged PATCH validation and deletion | `test_patch_preserves_omitted_fields_and_clears_nullable_fields`, no-op and missing-record cases | Pass |
| FR-03 Status history | History insertion in the same write transaction | `test_initial_history_uses_the_supplied_status`, `test_complete_application_workflow`, rollback cases | Pass |
| FR-04 Dated next action | Validation of the combined stored and supplied pair | `test_next_action_patch_validates_the_combined_record` | Pass |
| FR-05 Action queue | Active-status and due-date query | `test_queue_includes_today_and_overdue_but_not_future_with_stable_sort`, closed/reopen cases | Pass |
| FR-06 Search/filter | Literal search, status predicate and pagination | `test_search_combines_with_status_and_counts_before_pagination`, wildcard and tie-order cases | Pass |
| FR-07 Summary | Counts for all statuses and active overdue actions | `test_summary_includes_every_status_and_updates_after_delete` | Pass |
| FR-08 Swagger | Route descriptions, request examples and response schemas | `test_openapi_exposes_workflow_and_response_schemas`; `/docs` and `/openapi.json` served from Docker | Pass |
| NFR-01 Persistence | Alembic schema and file-backed SQLite | `test_migration_builds_schema_matching_models_and_is_repeatable`, real server restart and Docker recreation | Pass |
| NFR-02 Atomic writes | Shared transaction for application/history | `test_status_change_rolls_back_when_history_cannot_be_saved`, initial-history rollback case | Pass |
| NFR-03 Reproducible run | Locked dependencies, README, Docker and CI configuration | Local checks and Linux container startup executed; remote CI not run | Pass locally |
| NFR-04 Privacy | Loopback exposure and safe database error handling | `test_database_failure_does_not_expose_personal_values`, runtime logs and container inspection | Pass |
| NFR-05 Bounded lists | Validated limits and count-before-pagination queries | Default-limit, invalid-pagination and filtered-total cases for both lists | Pass |
| NFR-06 Health | Schema queries and generic database failure | `test_health_checks_readable_schema`, `test_health_fails_cleanly_before_migration`, Compose health check | Pass |

## Real HTTP and Docker evidence

The automated runtime test starts Uvicorn on an available loopback port, uses a
temporary migrated SQLite file, creates and edits an application, then stops and
restarts the process. It verifies identical saved details and history before
closing the application and checking the queue. It cleans up its processes.

The separate Docker check used an isolated Compose project and its named volume:

1. Built and started the service, then ran `scripts/demo.py` against it.
2. Verified health, Swagger HTML, OpenAPI routes, search, queue and summary.
3. Moved Northstar through `applied → interview → accepted → interview`.
   Repeating `interview` added no event; closing removed its overdue action;
   reopening restored that action.
4. Restarted the container and compared the complete application and history.
5. Ran Compose down without deleting volumes, created a new container and
   compared those same records again.
6. Checked the non-root UID and captured logs. Removed the isolated test
   containers, network and demo volume after successful verification.

The final check reported:

```json
{
  "health": "ok",
  "swagger": "served",
  "sample_applications": 3,
  "history_events": 4,
  "overdue": 1,
  "container_uid": 10001,
  "restart_persistence": true,
  "container_recreation_persistence": true,
  "private_note_absent_from_logs": true
}
```

## Findings and remaining validation

Independent contract testing found a missing OpenAPI operation description. It
was added and the complete suite rerun. SQLite needed explicit UTC conversion
on timestamp reads, and date validation rejects timestamps instead of silently
coercing them into calendar dates. These implementations preserve the written
contract; no functional requirement was removed.

The GitHub Actions workflow is included but has not run on a remote repository.
Swagger HTML and its generated contract were checked over HTTP; the manual
click-through is documented in [the demo](demo.md). Load testing, public-hosting
security assessment and real-user research are outside this iteration. No
throughput, production-readiness or product-impact claim is made.
