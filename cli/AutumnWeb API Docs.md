# AutumnWeb API v2: reference for the CLI

The CLI talks only to the versioned `/api/v2/` API; the old `/api/` (v1)
endpoints were removed from AutumnWeb. The authoritative contract is the
OpenAPI schema checked into the AutumnWeb repository as `openapi-v2.yaml`
(regenerate it there with `python manage.py spectacular --file openapi-v2.yaml`).
This page summarises what the CLI relies on. `api_client.py` translates v2
resources into the older dict shapes that the command modules still consume.

## Basics

- Auth: `Authorization: Token <key>` (`autumn auth login` fetches the key from
  `/get-auth-token/`). `GET /healthz/` is unauthenticated and is used to wake
  sleeping deployments.
- Durations are **minutes** (float). Datetimes are ISO-8601; a timestamp with
  no offset is read as UTC. `start_date`/`end_date` filters are `YYYY-MM-DD`
  days in the account's timezone (`GET /api/v2/me/` reports it).
- Filters take IDs, not names: `project_ids`, `subproject_ids`, `context_ids`,
  `tag_ids`, and `exclude_project_ids`/`exclude_subproject_ids`/`exclude_tag_ids`
  (comma-separated). The client resolves names to IDs first.
- Lists page with `limit`/`offset` and return `count` (this page) and `total`.
- Errors use one envelope:
  `{"error": {"code": "validation_error", "message": "Invalid input.", "details": {"end": ["…"]}}}`.
  The client appends `details` to the message. `version_conflict` means an
  `If-Match` version was stale; `restart_required` (commitments) means the
  change needs `…/restart/`.
- Writes that must not be applied twice carry a client `uuid` (timer start,
  session create) so the client may retry them after a wake-up.

## Search and related matches

`search` (case-insensitive text over project names, assigned subproject names
and session notes) is accepted by `sessions`, `export`, every `reports/*`
endpoint and `projects` (where it also covers descriptions). With `search`,
`related=true` adds records that match by meaning; it needs AI features and an
OpenAI key on the account. The response header `X-Autumn-Related` is
`included` or `unavailable` (the client exposes it as `related_status`).

On `GET /api/v2/sessions/`, `ordering=relevance` (default) lists direct matches
newest first, then related matches best first; `ordering=newest` sorts by end
time. Each row then carries `match: "direct" | "related"`. Without `search`
the two orderings are the same.

## Endpoints

| Method and path | Purpose | Notes |
|---|---|---|
| `GET /api/v2/me/` | Identity, timezone, capabilities | |
| `GET /api/v2/timers/` | Running timers | |
| `POST /api/v2/timers/` | Start | `project_id`, `subproject_ids`, `note`, `start`, `uuid`, `stop_after_minutes` |
| `PATCH /api/v2/timers/{id}` | Edit a running timer (e.g. its note) | `If-Match`; no trailing slash |
| `DELETE /api/v2/timers/{id}` | Discard without saving | `If-Match` |
| `POST /api/v2/timers/{id}/stop/` | Stop | `end`, `note`, `subproject_allocations`; `If-Match` |
| `POST /api/v2/timers/{id}/restart/` | Restart from a new `start` | `If-Match` |
| `GET /api/v2/sessions/` | Saved sessions | filters, `search`, `related`, `ordering`, `include=note`, `uuid` |
| `POST /api/v2/sessions/` | Create a completed session | `project_id`, `start`, `end`, `subproject_ids` or `subproject_allocations`, `note`, `uuid` |
| `GET/PATCH/DELETE /api/v2/sessions/{id}` | Read, edit in place, delete | `If-Match` on writes |
| `GET/POST /api/v2/projects/` | List (`status`, `search`, `related`, `ordering=name\|id`) / create | create takes `context_id`, `tag_ids` |
| `GET/PATCH/DELETE /api/v2/projects/{id}` | Detail with subprojects / edit / delete | |
| `GET/POST /api/v2/projects/{id}/subprojects/` | List / create subprojects | |
| `POST /api/v2/projects/merge/` | Merge projects | `source_ids`, `new_name` |
| `GET/PATCH/DELETE /api/v2/subprojects/{id}` | Subproject detail / edit / delete | |
| `POST /api/v2/subprojects/merge/` | Merge subprojects | `project_id`, `source_ids`, `new_name` |
| `GET/POST /api/v2/contexts/`, `PATCH/DELETE /api/v2/contexts/{id}` | Contexts (with stats) | |
| `GET/POST /api/v2/tags/`, `PATCH/DELETE /api/v2/tags/{id}` | Tags (with stats) | |
| `GET /api/v2/reports/totals/` | `total_minutes`, `session_count` | shared filters |
| `GET /api/v2/reports/tallies/?by=` | Totals by `project`, `subproject`, `context`, `tag` or `status` | subproject tallies include a `residual` entry |
| `GET /api/v2/reports/hierarchy/` | Project → subproject tree | |
| `GET /api/v2/reports/charts/?chart_type=` | Chart payloads as the web uses them | `aggregate=true` with `heatmap` returns `{weekday (Sunday=0), hour, average_hours}` cells |
| `GET /api/v2/export/` | Format-2 export (or `export_format=1`) | shared filters, `compress=true` |
| `POST /api/v2/import/` | Import an export | `data` or `data_compressed`, `force`; format-1 extras `merge`, `tolerance`, `autumn_import`, `context` |
| `GET/POST /api/v2/commitments/` | List (`include=streak`) / create | |
| `GET/PATCH/DELETE /api/v2/commitments/{id}` | Detail / edit / delete | `If-Match` on writes |
| `POST /api/v2/commitments/{id}/restart/` | New generation | `keep_balance`, `changes` |
| `POST /api/v2/commitments/{id}/adjustments/` | Balance adjustment | `amount`, `reason` |
| `GET /api/v2/commitments/{id}/periods/` | Closed periods | `generation`, `limit`, `offset` |
