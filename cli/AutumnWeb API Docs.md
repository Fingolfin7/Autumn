# Autumn API (/api/*) – reference for CLI wrapper

All endpoints below live under `/api/` and use Django REST Framework with `IsAuthenticated`.

## Auth + request basics

- Authentication required for every endpoint shown (session auth or token auth, depending on your DRF setup).
- Send JSON bodies for `POST`/`DELETE` where noted:
  - `Content-Type: application/json`
- Datetimes are returned as ISO 8601 strings (`.isoformat()`).
- **Durations are minutes** (float, typically rounded to 4 decimals).

---

## Conventions (important context)

### 1) `compact` output mode (new endpoints)
Most newer endpoints call `_compact()` which defaults to **true** unless you pass `?compact=false`.

- Default behavior: `compact=true`
- Compact responses use abbreviated keys like:
  - project name: `p`
  - subprojects: `subs`
  - duration minutes: `dur` or `elapsed` depending on endpoint

### 2) Subproject name matching is case-sensitive in practice
`timer_start`/`track_session` resolve subprojects using `name__in=subs` (case-sensitive in most DBs unless configured otherwise). If casing differs, the API may report them as unknown.

### 3) Context filtering
Many list/search endpoints apply an “active context” filter via `filter_by_active_context()`:

- You can pass `?context=` to override the session-stored context.
- `context` can be:
  - a numeric context id, or
  - a context name, or
  - `all` (disables context filtering)

Exception: `export_json_api` only attempts to treat `context` as an **integer id**.

### 4) Tag filtering can be inconsistent
There are two tag-filter paths:

- `_apply_tag_filters()` (used by several endpoints) expects `tags` as **names** (string or list); it also tries to constrain tags to the user.
- `filter_sessions_by_params()` (used by sessions endpoints) accepts:
  - tag **IDs** (legacy/web forms)
  - tag **names** (CLI)

Some endpoints apply both filters; `.distinct()` is used to prevent duplicates.

---

# New “compact” endpoints

## 1) Start timer
**POST** `/api/timer/start/`

Body:
```json
{
  "project": "Project Name",
  "subprojects": ["A", "B"],
  "note": "optional"
}
```

Notes:


- subprojects may also be "A,B" (comma-separated).

- Subprojects must already exist under the given project, or you get Unknown subprojects: ....

Response:

- 201 Created

```json
{
  "ok": true,
  "session": {
    "id": 123,
    "p": "Project Name",
    "pid": 42,
    "subs": ["A", "B"],
    "start": "2026-01-15T12:34:56+01:00",
    "end": null,
    "active": true,
    "elapsed": 0.0,
    "note": "optional"
  }
}
```

Note: All session responses now include `pid` (compact) or `project_id` (non-compact) for the parent project ID.

## 2) Stop timer


POST /api/timer/stop/

Body:


```json
{
  "session_id": 123,
  "project": "optional project name to disambiguate",
  "note": "optional overwrite"
}
```

Selection behavior:


- If session_id is provided, it stops that session.

- Else it picks the most recent active session, optionally filtered by project.

Response 200 OK:


```json
{
  "ok": true,
  "session": { "...": "same shape as start" },
  "duration": 42.5
}
```

## 3) Timer status


GET /api/timer/status/

Query:


- session_id=... (optional)

- project=... (optional)

- compact=true|false (optional)

Responses:


- If no active timers:


```json
{ "ok": true, "active": 0 }
```


- If active timers:

```json
{
  "ok": true,
  "active": 2,
  "sessions": [
    {
      "id": 1,
      "p": "P1",
      "pid": 42,
      "subs": [],
      "start": "2026-01-15T12:00:00+01:00",
      "end": null,
      "active": true,
      "elapsed": 3.2
    }
  ]
}
```

Quirk:


- With session_id, it errors if the session exists but is not active: 400 “Session not active”.

## 4) Restart timer


POST /api/timer/restart/

Body:


```json
{ "session_id": 123, "project": "optional" }
```

Behavior:


- Sets start_time = now, is_active = true, and end_time = null.

Response:


```json
{ "ok": true, "session": { "...": "same shape as start" } }
```

## 5) Delete timer (discard session)


DELETE /api/timer/delete/

Body or query:


- JSON: { "session_id": 123 }

- or ?session_id=123

- If omitted: deletes most recent active session.

Response 200 OK:


```json
{ "ok": true, "deleted": 123 }
```

## 6) Track a completed session (no live timer)


POST /api/track/

Body supports two time input styles:

A) Direct start/end

```json
{
  "project": "Project Name",
  "subprojects": "A,B",
  "start": "2026-01-15 09:00:00",
  "end": "2026-01-15 10:15:00",
  "note": "optional"
}
```

start/end are parsed by parse_date_or_datetime, which accepts:


- %m-%d-%Y

- %m-%d-%Y %H:%M:%S

- %Y-%m-%d

- %Y-%m-%d %H:%M:%S

B) Legacy (date + start_time/end_time)

```json
{
  "project": "Project Name",
  "date": "01-15-2026",
  "start_time": "09:00:00",
  "end_time": "10:15:00"
}
```

Crossing midnight:


- If end_time < start_time, it assumes the session crossed midnight and subtracts one day from start_time.

Response 201 Created:


```json
{ "ok": true, "session": { "...": "same shape as start" } }
```

## 7) Projects grouped by status


GET /api/projects/grouped/

Query:


- start_date, end_date (optional; passed through in_window)

- context (optional; id/name/all)

- tags (optional; treated as tag names by _apply_tag_filters)

- compact=true|false

Compact response:


```json
{
  "summary": {
    "active": 2,
    "paused": 1,
    "complete": 0,
    "archived": 0,
    "total": 3
  },
  "projects": {
    "active": ["P1", "P2"],
    "paused": ["P3"],
    "complete": [],
    "archived": []
  }
}
```

Non-compact response includes computed stats per project:


- session_count, avg_session_duration, context, tags, etc.

Note:


- Unknown/legacy status strings become their own group key.

## 8) Projects list (flat)

**GET** `/api/projects/`

Returns a flat (ungrouped) list of projects with optional filters.

Query:

- `status`: filter by status (active, paused, complete, archived) - optional
- `context`: filter by context id or name - optional
- `tags`: filter by tag names (comma-separated) - optional
- `search`: search by name (icontains) - optional
- `compact=true|false` (default true)

Compact response:

```json
{
  "count": 15,
  "projects": ["Project A", "Project B", "..."]
}
```

Non-compact response:

```json
{
  "count": 15,
  "projects": [
    {
      "id": 1,
      "name": "Project A",
      "status": "active",
      "description": "...",
      "total_minutes": 1234.5,
      "session_count": 42,
      "avg_session_minutes": 29.4,
      "context": "Work",
      "tags": ["Client", "Priority"]
    }
  ]
}
```

## 9) Subprojects list

**GET** `/api/subprojects/`

Query:

- `project` (or `project_name`) required
- `compact=true|false` (default true)

Compact response:

```json
{ "project": "My Project", "subprojects": ["A", "B"] }
```

Non-compact response includes stats and parent project ID:

```json
{
  "project": "My Project",
  "project_id": 42,
  "subprojects": [
    {
      "id": 1,
      "name": "A",
      "description": "...",
      "session_count": 25,
      "total_minutes": 750.0
    }
  ]
}
```

## 10) Totals (project + subproject totals)

**GET** `/api/totals/`

Query:


- project required

- optional filters: start_date, end_date, project_name, subproject, subprojects, tags, note_snippet, context

- compact=true|false

Compact response:


```json
{
  "project": "My Project",
  "total": 123.4567,
  "subs": [["A", 50.0], ["B", 73.4567]]
}
```

Notes:


- If a session has no subprojects, it is bucketed under "no subproject".

- If a session has multiple subprojects, its full duration is added to each subproject total.

## 11) Rename (project or subproject)

**POST** `/api/rename/`

Project rename:


```json
{ "type": "project", "project": "Old", "new_name": "New" }
```

Response:


```json
{ "ok": true, "project": "New" }
```

Subproject rename:

```json
{
  "type": "subproject",
  "project": "Parent",
  "subproject": "OldSub",
  "new_name": "NewSub"
}
```

Response:


```json
{ "ok": true, "project": "Parent", "subproject": "NewSub" }
```

Conflicts:


- 409 if the target name already exists.

## 12) Delete project via JSON body

**DELETE** `/api/project/delete/`

Body:


```json
{ "project": "Project Name" }
```

Response:


- 204 No Content

## 13) Search sessions

**GET** `/api/sessions/search/`

Requires at least one of:


- project or project_name

- subproject

- start_date

- end_date

- note_snippet

Optional:


- active=true|false (default false i.e. completed sessions)

- order (default -end_time for completed, -start_time for active)

- limit, offset

- context, tags, compact

Compact response:

```json
{
  "count": 2,
  "sessions": [
    { "id": 1, "p": "P", "pid": 42, "subs": ["A"], "start": "...", "end": "...", "dur": 12.5 },
    { "id": 2, "p": "P", "pid": 42, "subs": [], "start": "...", "end": "...", "dur": 5.0 }
  ]
}
```

Non-compact response includes `project_id` instead of `pid`.

## 14) Activity log


**GET** `/api/log/`

Query supports:

- `period=day|week|month|all`
- plus filters like search (project/subproject/date/note/context/tags/compact)

Default window:

- If period is day|week|month and no explicit start_date/end_date is provided:
    - day: since today 00:00
    - week: trailing 7 days (not "since Monday")
    - month: since 1st of current month

Response includes `pid`/`project_id` for each log entry:

```json
{
  "count": 3,
  "logs": [
    { "id": 1, "p": "P", "pid": 42, "subs": [], "start": "...", "end": "...", "dur": 30.5 }
  ]
}
```

## 15) Mark project status


**POST** `/api/mark/`

Body:

```json
{ "project": "Project Name", "status": "active|paused|complete|archived" }
```

Response:

```json
{ "ok": true, "project": "Project Name", "status": "paused" }
```

## 16) Export JSON (sessions/projects)

**GET** or **POST** `/api/export/`

Accepts filters via query params (GET) or JSON body (POST):

- `project_name` (or `project`): string (icontains)
- `start_date`: `YYYY-MM-DD` (inclusive)
- `end_date`: `YYYY-MM-DD` (inclusive)
- `context`: context id (integer only)
- `tags`: list of tag ids, or comma-separated string
- `compress`: bool (wraps payload with `json_compress`)
- `autumn_compatible`: bool (CLI compatibility format)

Response 200 OK: JSON object (either the export payload or a compressed wrapper).

## 17) Contexts list

**GET** `/api/contexts/`

Query:

- `compact=true|false` (default true)

Compact response:

```json
{ "count": 2, "contexts": [{"id": 1, "name": "Work"}] }
```

Non-compact response includes stats:

```json
{
  "count": 2,
  "contexts": [
    {
      "id": 1,
      "name": "Work",
      "description": "Work-related projects",
      "project_count": 5,
      "session_count": 142,
      "total_minutes": 8520.5,
      "avg_session_minutes": 60.0
    }
  ]
}
```

## 18) Tags list

**GET** `/api/tags/`

Query:

- `compact=true|false` (default true)

Compact response:

```json
{ "count": 2, "tags": [{"id": 1, "name": "Client"}] }
```

Non-compact response includes stats:

```json
{
  "count": 2,
  "tags": [
    {
      "id": 1,
      "name": "DeepWork",
      "color": "#ff5500",
      "project_count": 3,
      "session_count": 87,
      "total_minutes": 4350.0,
      "avg_session_minutes": 50.0
    }
  ]
}
```

## 19) Current user

**GET** `/api/me/`

Response 200 OK:

```json
{
  "ok": true,
  "id": 1,
  "username": "alice",
  "email": "alice@example.com",
  "first_name": "Alice",
  "last_name": "Doe",
  "active_session_count": 1
}
```

## 20) Edit session

**PATCH** `/api/session/<id>/`

Edit an existing completed session. Uses delete-and-recreate pattern internally to work correctly with signal-based time totals.

Body (all fields optional - only provided fields are updated):

```json
{
  "project": "New Project Name",
  "subprojects": ["A", "B"],
  "start": "2026-01-15T09:00:00+00:00",
  "end": "2026-01-15T10:30:00+00:00",
  "note": "Updated note"
}
```

Query:

- `compact=true|false` (default true)

Notes:

- Cannot edit active sessions (stop the timer first)
- Returns the new session object with a **new ID**
- If changing project, subprojects must exist under the new project
- If `subprojects` is not provided, existing subprojects are preserved (if valid for the project)

Response 200 OK:

```json
{
  "ok": true,
  "session": {
    "id": 456,
    "p": "New Project Name",
    "pid": 42,
    "subs": ["A", "B"],
    "start": "2026-01-15T09:00:00+00:00",
    "end": "2026-01-15T10:30:00+00:00",
    "active": false,
    "elapsed": 90.0,
    "note": "Updated note"
  }
}
```

## 21) Audit (recompute totals)

**POST** `/api/audit/`

Recomputes and persists totals for all of the authenticated user's projects and subprojects using `audit_total_time(log=False)`.

Response 200 OK:

```json
{
  "ok": true,
  "projects": {"count": 3, "changed": 1, "delta_total": 9.0},
  "subprojects": {"count": 5, "changed": 2, "delta_total": 18.0}
}
```


---

Compatibility (“legacy/migrated”) endpoints


These remain available and are used by older clients. Some are thin wrappers around the new endpoints.

Projects


- POST /api/create_project/

- GET /api/list_projects/ (optional start_date, end_date, context)

- GET /api/search_projects/?search_term=...&status=... (status optional)

- GET /api/get_project/<project_name>/

- DELETE /api/delete_project/<project_name>/

Subprojects


- POST /api/create_subproject/ (requires parent_project in body)

- GET /api/list_subprojects/<project_name>/ and /api/list_subprojects/?project_name=...

- GET /api/search_subprojects/?project_name=...&search_term=...

- DELETE /api/delete_subproject/<project_name>/<subproject_name>/

Sessions


Shimmed onto the new compact endpoints:


- POST /api/start_session/ → /api/timer/start/

- POST /api/restart_session/ → /api/timer/restart/

- POST /api/end_session/ → /api/timer/stop/

- POST /api/log_session/ → /api/track/

Direct:


- GET /api/list_sessions/ (completed sessions)

- GET /api/list_active_sessions/

- DELETE /api/delete_session/<int:session_id>/

Tallies

- GET /api/tally_by_sessions/

- GET /api/tally_by_subprojects/


---

Merge endpoints

Merge two projects into a new one


POST /api/merge_projects/

Body:


```json
{
  "project1": "A",
  "project2": "B",
  "new_project_name": "A+B"
}
```

Behavior notes:


- Moves all sessions and subprojects to the new project.

- Subproject name conflicts are renamed by appending (<old project name>), with a counter if needed.

- Deletes the original projects at the end.

- Audits total times.

Response 201:


```json
{
  "message": "Successfully merged A and B into A+B",
  "project": { "id": 101, "name": "A+B" }
}
```

Merge two subprojects into a new one (within one project)


POST /api/merge_subprojects/

Body:


```json
{
  "project_id": 10,
  "subproject1": "X",
  "subproject2": "Y",
  "new_subproject_name": "X+Y"
}
```

Behavior:


- Creates new subproject.

- Re-links sessions from old subprojects to the merged one.

- Deletes originals.

- Audits total time.


---
