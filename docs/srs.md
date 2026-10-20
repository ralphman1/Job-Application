# Software requirements specification

Version 1.0. This specification is written before implementation. Changes found
during development must be recorded in the validation document and reflected
here when they change the contract.

## Context and assumptions

The actor is one local job seeker. Swagger at `/docs` is the user interface.
The system runs on a trusted computer, bound to localhost, with a persistent
SQLite file. There is no login and no isolation between different users. Remote
or shared access is outside the security model.

All HTTP paths below use the `/api/v1` prefix, except `/health`. JSON field names
and documentation are English. Dates use `YYYY-MM-DD`. Timestamps use UTC and
include an offset in responses. The application uses UTC for today's date.

## Requirements and acceptance criteria

| ID | Requirement | Acceptance criterion |
| --- | --- | --- |
| FR-01 | Create and read applications | A valid create returns 201 and an ID; GET returns the saved details and server timestamps. |
| FR-02 | Edit and delete applications | PATCH changes only supplied fields; DELETE returns 204, and subsequent reads return 404. |
| FR-03 | Track status changes | Creation records an initial history event; a change records old and new status atomically; setting the same status adds no event. |
| FR-04 | Maintain a dated next action | Text and date are set together, can be edited independently when the final pair is valid, and can be cleared together. |
| FR-05 | Show the action queue | Only active applications with an action due on or before the reference date are listed, oldest due date first. |
| FR-06 | Find applications | Search by company or position combines with a status filter and stable pagination. |
| FR-07 | Summarize progress | Return total applications, counts for every status and active actions strictly overdue on the reference date. |
| FR-08 | Demonstrate the API | Swagger contains descriptions, examples, response schemas and expected errors for the full workflow. |
| NFR-01 | Preserve data | Data survives a server restart; a migration creates the schema on a new SQLite database. |
| NFR-02 | Keep writes consistent | An application change and its history event commit together; failure leaves no partial update. |
| NFR-03 | Run reproducibly | A lock file, Python version, local commands, Docker instructions and CI checks are provided. |
| NFR-04 | Respect local data privacy | Default network exposure is loopback; application logs exclude request bodies, notes and database URLs. |
| NFR-05 | Bound list responses | Application and follow-up lists have limit 20 by default, maximum 100, offset 0 by default, and a total count. |
| NFR-06 | Report availability | Health returns 200 only when the application schema is readable; database failure returns a generic 503. |

## Data model

`Application` has an integer ID; required `company`, `position`, `applied_on`;
optional `vacancy_url`, `notes`, `next_action`, `follow_up_on`; `status`;
and server-managed `created_at` and `updated_at` timestamps.

- Company and position: trimmed strings, 1–200 characters.
- Vacancy URL: optional HTTP or HTTPS URL, at most 2048 characters. It is stored,
  never fetched by the server.
- Notes: optional trimmed text, at most 5000 characters; empty text becomes null.
- Next action: optional trimmed text, 1–500 characters when set. Blank text is
  invalid. Its date must be present exactly when its text is present.
- Applied date is supplied by the caller. Historical and future calendar dates
  are accepted; the system does not infer dates from status changes.
- Status is one of `applied`, `interview`, `offer`, `accepted`, `rejected`,
  `withdrawn`, and defaults to `applied` on creation. Explicit null is invalid.
- `accepted`, `rejected`, `withdrawn` are closed; `offer` remains active.
- Any status may be changed to any other status to permit correcting records.
  Closing preserves the action fields but hides the action from the queue and
  overdue count. Reopening makes that same action eligible again.
- Duplicate company/position pairs are allowed.

`StatusHistory` has an integer ID, application ID, nullable `from_status`,
required `to_status`, and server-managed UTC `changed_at`. The initial event has
`from_status=null`. History is read-only through the API and deleted with its
application.

## API contract

| Method and path | Request | Successful response |
| --- | --- | --- |
| POST `/applications` | Writable application fields | 201, ApplicationRead |
| GET `/applications` | `q`, `status`, `limit`, `offset` | 200, `{items: ApplicationRead[], total: integer}` |
| GET `/applications/{id}` | Positive integer ID | 200, ApplicationRead |
| PATCH `/applications/{id}` | Any subset of writable fields | 200, ApplicationRead |
| DELETE `/applications/{id}` | Positive integer ID | 204, no body |
| GET `/applications/{id}/history` | Positive integer ID | 200, StatusHistoryRead array |
| GET `/follow-ups` | Optional `as_of`, `limit`, `offset` | 200, `{items: ApplicationRead[], total: integer}` |
| GET `/summary` | Optional `as_of` | 200, `{total, by_status, overdue, as_of}` |
| GET `/health` | None | 200, `{status: "ok"}` |

ApplicationRead contains all Application fields. StatusHistoryRead contains all
history fields. All six keys are always present in `by_status`, including zeros.

The application list sorts by `updated_at DESC, id DESC`. Search is a literal
substring of company or position, ignoring ASCII letter case, with SQLite's
built-in case behavior for other characters. `%` and `_` are literal characters.
Search text is trimmed, limited to 200 characters, and blank search matches all.
Filters apply before counting and pagination.

The action queue sorts by `follow_up_on ASC, id ASC`. If omitted, `as_of` is
today in UTC. Due today is included; overdue means strictly earlier than
`as_of`. Future actions are saved but not returned before their due date.
History sorts by `changed_at ASC, id ASC` and is unpaginated for this local MVP.

PATCH validates the combined stored and supplied fields. An omitted field is
unchanged. Explicit null clears only nullable fields. Empty PATCH is a valid
no-op. A request that changes no stored values does not change `updated_at`.
IDs, history and timestamps are not writable; unknown body fields are rejected.

Invalid values, inconsistent action/date pairs and pagination outside the
documented range return 422. Missing applications return 404, including their
history route. Expected errors use FastAPI's `detail` response field. Unexpected
server errors do not return internal database information.

## Reliability and operational limits

Use one process with a session per request. Successful writes commit before a
response is returned; session cleanup rolls back failed writes. SQLite foreign
keys are enabled so deleting an application removes its history. The system is
designed for a personal dataset, not high write concurrency. Concurrent edits
use last-write-wins; conflict detection is deferred.

No external service is needed for application requests. Standard access and
error logs plus `/health` are sufficient for this local iteration. Dependencies
and container images are needed during installation. No numerical throughput or
latency guarantee is claimed without a measured workload.
