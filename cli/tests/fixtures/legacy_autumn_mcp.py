# autumn_mcp_server.py
import os
import requests
from typing import Optional, List, Dict, Any
from urllib.parse import quote
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Autumn MCP Server")

AUTUMN_API_BASE = os.getenv("AUTUMN_API_BASE", "http://localhost:8000")
AUTUMN_API_TOKEN = os.getenv("AUTUMN_API_TOKEN")
AUTUMN_API_TIMEOUT = float(os.getenv("AUTUMN_API_TIMEOUT", "60"))
AUTUMN_API_RETRIES = int(os.getenv("AUTUMN_API_RETRIES", "1"))

TIME_UNIT_LABEL = os.getenv("AUTUMN_TIME_UNIT", "minutes")


def _headers(extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    headers = {
        "Accept": "application/json",
        "Accept-Units": TIME_UNIT_LABEL,
        "X-Autumn-Client": "mcp",
    }
    if AUTUMN_API_TOKEN:
        headers["Authorization"] = f"Token {AUTUMN_API_TOKEN}"
    if extra:
        headers.update(extra)
    return headers


def autumn_request(
    method: str,
    endpoint: str,
    params: Optional[Dict[str, Any]] = None,
    json: Optional[Dict[str, Any]] = None,
    data: Optional[Dict[str, Any]] = None,
) -> Any:
    url = f"{AUTUMN_API_BASE}{endpoint}"
    attempts = max(0, AUTUMN_API_RETRIES) + 1
    last_error = None
    for attempt in range(attempts):
        try:
            resp = requests.request(
                method=method,
                url=url,
                headers=_headers(),
                params=params,
                json=json,
                data=data,
                timeout=AUTUMN_API_TIMEOUT,
            )
            break
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
            last_error = exc
            if attempt == attempts - 1:
                raise
    else:
        raise last_error

    if not resp.content or resp.status_code == 204:
        return {"status": resp.status_code}
    return resp.json()


def _params_compact(compact: bool, extra: Optional[Dict[str, Any]] = None):
    params = dict(extra or {})
    if compact is False:
        params["compact"] = "false"
    return params


def _add_common_filters(
    params: Dict[str, Any],
    context: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> Dict[str, Any]:
    if context:
        params["context"] = context
    if tags:
        params["tags"] = ",".join(tags)
    return params


def _with_units(payload: Any, compact: bool) -> Any:
    if isinstance(payload, dict):
        tagged = dict(payload)
        tagged["unit"] = TIME_UNIT_LABEL
        return tagged
    return payload


@mcp.tool(
    description="Start a live timer for a project. "
    "Use this when the user begins working *now*."
)
def start(
    project: str,
    subprojects: Optional[List[str]] = None,
    note: Optional[str] = None,
    compact: bool = True,
):
    """Start a new timer for a project.
        - Use when the user says they are starting work immediately.
        - If they mention subprojects, include them.
        - Do not add a note for a start session
        - Do NOT use this for past sessions (use `track` instead).
    """
    payload: Dict[str, Any] = {"project": project}
    if subprojects:
        payload["subprojects"] = subprojects
    if note:
        payload["note"] = note
    res = autumn_request(
        "POST", "/api/timer/start/", json=payload, params=_params_compact(compact)
    )
    return _with_units(res, compact)


@mcp.tool(
    description="Stop a live timer for a project. "
    "Use this when the user finishes working on a project or takes a break."
)
def stop(
    note: Optional[str] = None,
    session_id: Optional[int] = None,
    project: Optional[str] = None,
    compact: bool = True,
):
    """
    Stop a live timer for a project.
    - Use when the user finishes working on a project or takes a break.
    - If they mention a note, include it.

    """
    payload: Dict[str, Any] = {}
    if note is not None:
        payload["note"] = note
    if session_id is not None:
        payload["session_id"] = session_id
    if project is not None:
        payload["project"] = project
    res = autumn_request(
        "POST", "/api/timer/stop/", json=payload, params=_params_compact(compact)
    )
    return _with_units(res, compact)


@mcp.tool(
    description="Get the status of the current timer. "
    "Use this to check if the user is currently tracking time for a project. It returns the elapsed time of an active session "
)
def status(
    session_id: Optional[int] = None,
    project: Optional[str] = None,
    compact: bool = True,
):
    params: Dict[str, Any] = {}
    if session_id is not None:
        params["session_id"] = session_id
    if project is not None:
        params["project"] = project
    params = _params_compact(compact, params)
    res = autumn_request("GET", "/api/timer/status/", params=params)
    return _with_units(res, compact)


@mcp.tool(
    description="Log a past work session with explicit start/end times or date. "
    "Use this when the user wants to record work that already happened."
    "Make sure to confirm the project name and any subproject names before calling this."
    "Include a note if the user provides one."
)
def track(
    project: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    date: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    subprojects: Optional[List[str]] = None,
    note: Optional[str] = None,
    compact: bool = True,
):
    """Track a past session.
        - Use when the user specifies a time range or date in the past.
        - Do NOT use this for starting a live timer (use `start` instead).
    """
    payload: Dict[str, Any] = {"project": project}
    if start and end:
        payload["start"] = start
        payload["end"] = end
    else:
        payload["date"] = date
        payload["start_time"] = start_time
        payload["end_time"] = end_time
    if subprojects:
        payload["subprojects"] = subprojects
    if note:
        payload["note"] = note
    res = autumn_request(
        "POST", "/api/track/", json=payload, params=_params_compact(compact)
    )
    return _with_units(res, compact)


@mcp.tool()
def delete_timer(session_id: Optional[int] = None):
    params: Dict[str, Any] = {}
    if session_id is not None:
        params["session_id"] = session_id
    return autumn_request("DELETE", "/api/timer/delete/", params=params)


@mcp.tool()
def remove_timer(session_id: Optional[int] = None):
    return delete_timer(session_id=session_id)


@mcp.tool()
def restart(
    session_id: Optional[int] = None,
    project: Optional[str] = None,
    compact: bool = True,
):
    payload: Dict[str, Any] = {}
    if session_id is not None:
        payload["session_id"] = session_id
    if project is not None:
        payload["project"] = project
    res = autumn_request(
        "POST", "/api/timer/restart/", json=payload, params=_params_compact(compact)
    )
    return _with_units(res, compact)


@mcp.tool(
    description="List all projects in Autumn. "
    "Use this to get a list of all projects the user can track time for. "
    "You can filter by start and end date to get projects created within that range."
    "Projects are grouped by Active, Paused, and Completed."
)
def projects(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    context: Optional[str] = None,
    tags: Optional[List[str]] = None,
    compact: bool = True,
):
    params: Dict[str, Any] = {}
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    params = _add_common_filters(params, context=context, tags=tags)
    params = _params_compact(compact, params)
    return autumn_request("GET", "/api/projects/grouped/", params=params)


@mcp.tool(
    description="List all the subprojects of a project. "
    "Use this to get the subprojects under a specific project. "
)
def subprojects(project: str, compact: bool = True):
    params = _params_compact(compact, {"project": project})
    return autumn_request("GET", "/api/subprojects/", params=params)


@mcp.tool(
    description="Get the time tallies for a project by the session durations found between start_date and end_date. "
)
def totals(
    project: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    context: Optional[str] = None,
    tags: Optional[List[str]] = None,
    compact: bool = True,
):
    params: Dict[str, Any] = {"project": project}
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    params = _add_common_filters(params, context=context, tags=tags)
    params = _params_compact(compact, params)
    res = autumn_request("GET", "/api/totals/", params=params)
    return _with_units(res, compact)


@mcp.tool(
    description="Rename a project or subproject. "
    "Use this when the user wants to change the name of an existing project or subproject."
)
def rename(project: str, new_name: str, subproject: Optional[str] = None):
    """
      Rename a project or subproject.
      JSON:
        - Project: { "type": "project", "project": "Old", "new_name": "New" }
        - Subproject: {
            "type": "subproject",
            "project": "Parent",
            "subproject": "OldSub",
            "new_name": "NewSub"
          }
      """
    if subproject:
        payload = {
            "type": "subproject",
            "project": project,
            "subproject": subproject,
            "new_name": new_name,
        }
    else:
        payload = {"type": "project", "project": project, "new_name": new_name}
    return autumn_request("POST", "/api/rename/", json=payload)


@mcp.tool()
def delete_project(project: str):
    return autumn_request("DELETE", "/api/project/delete/", json={"project": project})


@mcp.tool(
    description="Show activity logs. Filter by any of: project, subproject, period (default 'week', also 'day', 'month' or 'all'),"
                " start_date, end_date, note (snippet). By default the compact value is set to true, this means sessions will not include session notes,"
    " if you want to include session notes set compact to false. Units: minutes."
)
def log(
    period: Optional[str] = "week",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    project: Optional[str] = None,
    subproject: Optional[str] = None,
    note: Optional[str] = None,
    context: Optional[str] = None,
    tags: Optional[List[str]] = None,
    compact: bool = True,
):
    """
    Show activity logs. Filter by any of: project, subproject, start_date,
    end_date, note (snippet). Units: minutes.

    Supports:
      - period=week|month|day|all
      - start_date?, end_date?
      - project or project_name
      - subproject
      - note_snippet
      - compact?
    Defaults to period=week if no start/end/period filters provided by client.

    """
    params: Dict[str, Any] = {}
    if start_date or end_date:
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
    elif period:
        params["period"] = period
    if project:
        params["project"] = project  # alias supported by API
    if subproject:
        params["subproject"] = subproject
    if note:
        params["note_snippet"] = note
    params = _add_common_filters(params, context=context, tags=tags)
    params = _params_compact(compact, params)
    res = autumn_request("GET", "/api/log/", params=params)
    return _with_units(res, compact)


@mcp.tool(
    description="Search for sessions by project, subproject, start_date, end_date, note. "
    "Use this to find specific sessions based on various criteria. Rather than listing all sessions."
)
def search_sessions(
    project: Optional[str] = None,
    subproject: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    note: Optional[str] = None,
    active: bool = False,
    limit: Optional[int] = None,
    offset: Optional[int] = None,
    order: Optional[str] = None,
    context: Optional[str] = None,
    tags: Optional[List[str]] = None,
    compact: bool = True,
):
    """
    Search sessions by any of: project, subproject, start_date, end_date, note.
    At least one of those is required. Units: minutes.
    """
    params: Dict[str, Any] = {}
    if project:
        params["project"] = project
    if subproject:
        params["subproject"] = subproject
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    if note:
        params["note_snippet"] = note
    if active:
        params["active"] = "true"
    if limit is not None:
        params["limit"] = str(limit)
    if offset is not None:
        params["offset"] = str(offset)
    if order:
        params["order"] = order
    params = _add_common_filters(params, context=context, tags=tags)
    params = _params_compact(compact, params)
    res = autumn_request("GET", "/api/sessions/search/", params=params)
    return _with_units(res, compact)


@mcp.tool(description="Get the authenticated Autumn user identity.")
def me():
    return autumn_request("GET", "/api/me/")


@mcp.tool(description="Create a new Autumn project.")
def create_project(name: str, description: Optional[str] = None):
    payload: Dict[str, Any] = {"name": name}
    if description:
        payload["description"] = description
    return autumn_request("POST", "/api/create_project/", json=payload)


@mcp.tool(description="Create a new subproject under an existing project.")
def create_subproject(
    parent_project: str,
    name: str,
    description: Optional[str] = None,
):
    payload: Dict[str, Any] = {"parent_project": parent_project, "name": name}
    if description:
        payload["description"] = description
    return autumn_request("POST", "/api/create_subproject/", json=payload)


@mcp.tool(
    description="Mark a project status. Status should be active, paused, complete, or archived."
)
def mark_project(project: str, status: str):
    return autumn_request("POST", "/api/mark/", json={"project": project, "status": status})


@mcp.tool(description="Alias for mark_project, matching the CLI command name.")
def mark(project: str, status: str):
    return mark_project(project=project, status=status)


@mcp.tool(description="Get detailed information about one project by name.")
def get_project(name: str):
    return autumn_request("GET", f"/api/get_project/{quote(name, safe='')}/")


@mcp.tool(description="List projects as a flat ungrouped list with optional filters.")
def list_projects(
    status: Optional[str] = None,
    context: Optional[str] = None,
    tags: Optional[List[str]] = None,
    search: Optional[str] = None,
    compact: bool = True,
):
    params: Dict[str, Any] = {"compact": str(compact).lower()}
    if status:
        params["status"] = status
    if search:
        params["search"] = search
    params = _add_common_filters(params, context=context, tags=tags)
    return autumn_request("GET", "/api/projects/", params=params)


@mcp.tool(description="Delete a subproject from a project.")
def delete_subproject(project: str, subproject: str):
    endpoint = f"/api/delete_subproject/{quote(project, safe='')}/{quote(subproject, safe='')}/"
    return autumn_request("DELETE", endpoint)


@mcp.tool(description="Alias for delete_subproject, matching the CLI command name.")
def delete_sub(project: str, subproject: str):
    return delete_subproject(project=project, subproject=subproject)


@mcp.tool(description="Search subprojects by name within a parent project.")
def search_subprojects(project: str, search_term: str):
    return autumn_request(
        "GET",
        "/api/search_subprojects/",
        params={"project_name": project, "search_term": search_term},
    )


@mcp.tool(description="Edit an existing completed session.")
def edit_session(
    session_id: int,
    project: Optional[str] = None,
    subprojects: Optional[List[str]] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    note: Optional[str] = None,
    compact: bool = True,
):
    payload: Dict[str, Any] = {}
    if project is not None:
        payload["project"] = project
    if subprojects is not None:
        payload["subprojects"] = subprojects
    if start is not None:
        payload["start"] = start
    if end is not None:
        payload["end"] = end
    if note is not None:
        payload["note"] = note
    return autumn_request(
        "PATCH",
        f"/api/session/{session_id}/",
        json=payload,
        params={"compact": str(compact).lower()},
    )


@mcp.tool(
    description="Delete a saved/completed session log by ID. "
    "Use delete_timer for active or most-recent live timer sessions."
)
def delete_session(session_id: int):
    return autumn_request("DELETE", f"/api/delete_session/{session_id}/")


@mcp.tool(description="Alias for delete_session, for deleting a saved session log.")
def delete_session_log(session_id: int):
    return delete_session(session_id=session_id)


# Optional utility
@mcp.tool(
    description="Search for existing projects by name. "
    "Use this to confirm or resolve the correct project name "
    "before calling other tools that require a project argument."
)
def search_projects(search_term: str, status: Optional[str] = None):
    """Search for projects by name.
    - Use this when the user provides a project name that may not exactly match.
    - Always call this first if you are unsure whether the project exists.
    - The result will give you the canonical project name to use in other calls.
    """
    params = {"search_term": search_term}
    if status:
        params["status"] = status
    return autumn_request("GET", "/api/search_projects/", params=params)


@mcp.tool(description="List available contexts for filtering projects and sessions.")
def contexts(compact: bool = True):
    return autumn_request(
        "GET", "/api/contexts/", params={"compact": str(compact).lower()}
    )


@mcp.tool(description="Alias for contexts, matching the CLI command name.")
def context(compact: bool = True):
    return contexts(compact=compact)


@mcp.tool(description="List available tags for filtering projects and sessions.")
def tags(compact: bool = True):
    return autumn_request("GET", "/api/tags/", params={"compact": str(compact).lower()})


@mcp.tool(description="Alias for tags, matching the CLI command name.")
def tag(compact: bool = True):
    return tags(compact=compact)


@mcp.tool(description="Export Autumn data as JSON, optionally filtered.")
def export_data(
    project: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    context: Optional[int] = None,
    tags: Optional[List[int]] = None,
    compress: bool = False,
    autumn_compatible: bool = True,
):
    payload: Dict[str, Any] = {}
    if project:
        payload["project_name"] = project
    if start_date:
        payload["start_date"] = start_date
    if end_date:
        payload["end_date"] = end_date
    if context is not None:
        payload["context"] = context
    if tags:
        payload["tags"] = tags
    if compress:
        payload["compress"] = True
    if autumn_compatible:
        payload["autumn_compatible"] = True
    return autumn_request("POST", "/api/export/", json=payload)


@mcp.tool(description="Alias for export_data, matching the CLI command name.")
def export(
    project: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    context: Optional[int] = None,
    tags: Optional[List[int]] = None,
    compress: bool = False,
    autumn_compatible: bool = True,
):
    return export_data(
        project=project,
        start_date=start_date,
        end_date=end_date,
        context=context,
        tags=tags,
        compress=compress,
        autumn_compatible=autumn_compatible,
    )


@mcp.tool(description="Recompute and persist all project and subproject totals.")
def audit_totals():
    return autumn_request("POST", "/api/audit/")


@mcp.tool(description="Alias for audit_totals, matching the CLI command name.")
def audit():
    return audit_totals()


@mcp.tool(description="Get project totals across sessions, optionally filtered.")
def tally_by_sessions(
    project_name: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    context: Optional[str] = None,
    tags: Optional[List[str]] = None,
):
    params: Dict[str, Any] = {}
    if project_name:
        params["project_name"] = project_name
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    params = _add_common_filters(params, context=context, tags=tags)
    return autumn_request("GET", "/api/tally_by_sessions/", params=params)


@mcp.tool(description="Get subproject totals for a project, optionally filtered.")
def tally_by_subprojects(
    project_name: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    context: Optional[str] = None,
    tags: Optional[List[str]] = None,
):
    params: Dict[str, Any] = {"project_name": project_name}
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    params = _add_common_filters(params, context=context, tags=tags)
    return autumn_request("GET", "/api/tally_by_subprojects/", params=params)


@mcp.tool(description="List sessions for charts or analysis, optionally filtered.")
def list_sessions(
    project_name: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    context: Optional[str] = None,
    tags: Optional[List[str]] = None,
    compact: bool = False,
):
    params: Dict[str, Any] = {"compact": str(compact).lower()}
    if project_name:
        params["project_name"] = project_name
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    params = _add_common_filters(params, context=context, tags=tags)
    return autumn_request("GET", "/api/list_sessions/", params=params)


@mcp.tool(description="Get time totals aggregated by context.")
def tally_by_context(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    params: Dict[str, Any] = {}
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    return autumn_request("GET", "/api/tally_by_context/", params=params)


@mcp.tool(description="Get project count and time totals grouped by project status.")
def tally_by_status(context: Optional[str] = None):
    params: Dict[str, Any] = {}
    if context:
        params["context"] = context
    return autumn_request("GET", "/api/tally_by_status/", params=params)


@mcp.tool(description="Get time and project count aggregated by tag.")
def tally_by_tags():
    return autumn_request("GET", "/api/tally_by_tags/")


@mcp.tool(description="Get nested Context -> Project -> Subproject hierarchy with totals.")
def hierarchy(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    params: Dict[str, Any] = {}
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    return autumn_request("GET", "/api/hierarchy/", params=params)


@mcp.tool(description="Get projects with statistics for visualization and comparison.")
def projects_with_stats(
    context: Optional[str] = None,
    tags: Optional[List[str]] = None,
):
    params: Dict[str, Any] = {}
    params = _add_common_filters(params, context=context, tags=tags)
    return autumn_request("GET", "/api/projects_with_stats/", params=params)


@mcp.tool(
    description="Merge two projects into one new project. "
    "All sessions and subprojects from both projects will be moved to the new merged project. "
    "Subprojects with duplicate names will be automatically renamed to avoid conflicts."
)
def merge_projects(
    project1: str,
    project2: str, 
    new_project_name: str
):
    """Merge two projects into one new project.
    
    Args:
        project1: Name of the first project to merge
        project2: Name of the second project to merge  
        new_project_name: Name for the new merged project
        
    Returns:
        The merged project data with a success message
        
    Note:
        - Both projects must exist and belong to the authenticated user
        - The new project name must be unique
        - All sessions and subprojects will be moved to the new project
        - Subprojects with duplicate names will be renamed with project suffixes
        - Total time will be recalculated automatically
    """
    return autumn_request(
        "POST", 
        "/api/merge_projects/", 
        json={
            "project1": project1,
            "project2": project2,
            "new_project_name": new_project_name
        }
    )


@mcp.tool(
    description="Merge two subprojects into one new subproject. "
    "All sessions from both subprojects will be moved to the new merged subproject. "
    "Both subprojects must belong to the same parent project."
)
def merge_subprojects(
    subproject1: str,
    subproject2: str,
    new_subproject_name: str,
    project_id: int
):
    """Merge two subprojects into one new subproject.
    
    Args:
        subproject1: Name of the first subproject to merge
        subproject2: Name of the second subproject to merge
        new_subproject_name: Name for the new merged subproject
        project_id: ID of the parent project containing both subprojects
        
    Returns:
        The merged subproject data with a success message
        
    Note:
        - Both subprojects must exist and belong to the same parent project
        - The new subproject name must be unique within the parent project
        - All sessions will be moved to the new subproject
        - Total time will be recalculated automatically
    """
    return autumn_request(
        "POST", 
        "/api/merge_subprojects/", 
        json={
            "subproject1": subproject1,
            "subproject2": subproject2,
            "new_subproject_name": new_subproject_name,
            "project_id": project_id
        }
    )


if __name__ == "__main__":
    mcp.run()
