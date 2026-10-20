# Retrospective

The first iteration provides a complete local workflow: record an application,
plan an action, change the hiring stage, inspect history and find due work.
Closing and reopening applications changes the queue without destroying the
saved action. All SRS requirements have implementation and verification evidence
in the validation document.

## What worked

Writing the contract first kept the parallel work compatible. The backend, test
and delivery work shared field names, response shapes and date rules. Separate
test authorship exposed a documentation gap that an implementation-only review
had missed. A real server restart and a container recreation checked persistence
beyond the in-process test client.

The API-only boundary made a useful first slice possible without accounts,
frontend work or external services. The dated action queue gives the CRUD
records a concrete purpose. SQLite and Swagger keep local demonstration short.

## What implementation clarified

Partial updates need validation after merging with stored values. Checking only
the incoming JSON would reject valid date-only changes or allow half an action
to remain after clearing one field. Closing preserves actions intentionally;
reopening may therefore surface an old overdue action.

SQLite does not preserve timezone information in its native datetime handling.
An explicit UTC conversion keeps timestamp responses consistent after restart.
Calendar dates use stricter validation than Pydantic's default coercion so a
timestamp cannot quietly become a follow-up date.

Independent testing found a missing Swagger operation description, which was
fixed. The product scope and API behavior did not need to change during this
iteration. That is an outcome of the current work, not a claim that the initial
requirements have been validated with users.

## Deliberate limitations and debt

- There is one trusted local user and no authentication. Shared or public
  hosting requires a new security and ownership model.
- Concurrent edits use last-write-wins. Conflict detection and simultaneous
  status-history correctness under competing writers need attention before
  multi-user use.
- UTC determines today's date. A user near a date boundary can supply `as_of`;
  a user-facing timezone preference is deferred.
- Search uses SQLite's ASCII case behavior. Full Unicode case folding is not
  supported.
- Status history is unpaginated and follows application deletion. There is no
  durable audit archive, backup scheduler or recovery UI.
- The locked test stack emits an upstream TestClient deprecation warning. A
  future dependency update should replace the deprecated transport and rerun
  the contract and runtime suite.
- Swagger assumes a technically comfortable user. A broader audience will need
  a dedicated interface, informed by observation rather than feature guesses.

## What to do next

First, ask a job seeker to use the tracker for one week. Observe whether they
understand the action queue, keep it current and find entering data worthwhile.
Use those findings to decide whether to add an interface or improve the workflow.

If notifications provide value, add opt-in reminders with explicit timezone and
delivery rules. If shared access becomes a requirement, design authentication,
data ownership and concurrency handling, then evaluate PostgreSQL and deployment
operations. Those changes follow a new requirement rather than being prerequisites
for the current local product.
