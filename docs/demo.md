# Five-minute demo

Use a local server started from the README and open
http://127.0.0.1:8000/docs. The examples below are fictional. For predictable
counts, use an empty demo database rather than deleting personal records.

## 1. Create applications

In another terminal, run:

```sh
uv run python scripts/demo.py
```

It creates three applications and prints their IDs and today's UTC date. Save
the ID for **Northstar Labs** and the printed reference date. Repeating the
script adds more records because separate applications at the same company are
valid.

On an empty database, the sample has an `applied` record due yesterday, an
`interview` record due today and an `offer` record due tomorrow. The initial
summary has total 3 and overdue 1.

## 2. Find today's work

In Swagger, expand `GET /api/v1/follow-ups`, click **Try it out**, put the printed
reference date in `as_of` and execute. Northstar appears first, followed by Harbor
Analytics. Orchard Systems is due tomorrow and is not yet in this queue.

Run `GET /api/v1/follow-ups` with tomorrow's date to see the offer's action too.
An offer remains active because reviewing it is still work to do.

Run `GET /api/v1/applications` with `q=northstar` and `status=applied`. The two
filters combine, and `total` reports the filtered number before pagination.

## 3. Record progress

Use `PATCH /api/v1/applications/{id}` with Northstar's ID and:

```json
{"status": "interview"}
```

Read its history. It now has the initial `null → applied` event followed by
`applied → interview`. Repeat the PATCH and read history again; no duplicate
event is added. The action and due date stay unchanged because PATCH omitted
them.

## 4. Close and reopen

PATCH the same application with:

```json
{"status": "accepted"}
```

Read the action queue and summary with the original reference date. Northstar
is absent from the queue, and overdue becomes 0 on this sample database. GET the
application to confirm that the next action is still stored. PATCH back to
`interview` to see the same action return to the queue.

An attempt to clear only `next_action` with null returns 422 because the
remaining date would have no action. To clear both, send:

```json
{"next_action": null, "follow_up_on": null}
```

## 5. Restart and verify

Stop the local server with Ctrl+C, start it again with the same README command,
and GET Northstar by ID. Its latest status and complete history remain. With
Docker, run `docker compose restart api` instead and wait for health to return
200 before reading the application.

The demonstration exercises the intended vertical slice. Automated tests cover
the same contract plus failure cases; the validation document records which
checks were actually executed.
