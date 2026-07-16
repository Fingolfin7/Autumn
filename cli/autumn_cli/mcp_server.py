"""Model Context Protocol tools for Autumn's v2 API facade."""

from __future__ import annotations

import functools
import os
from typing import Any, Callable, Dict, List, Optional, TypeVar

from .api_client import APIClient, APIError

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:  # pragma: no cover - exercised only without the optional extra
    FastMCP = None  # type: ignore[assignment,misc]


_MISSING_MCP = (
    "Autumn MCP support is not installed. Install it with "
    "'pip install autumn-cli[mcp]'."
)
mcp = FastMCP("Autumn MCP Server") if FastMCP is not None else None
_client: Optional[APIClient] = None
F = TypeVar("F", bound=Callable[..., Any])


def _get_client() -> APIClient:
    """Create the shared facade client on first use, never at import time."""
    global _client
    if _client is None:
        api_key = os.getenv("AUTUMN_API_KEY") or os.getenv("AUTUMN_API_TOKEN")
        base_url = os.getenv("AUTUMN_API_BASE")
        _client = APIClient(api_key=api_key, base_url=base_url, quiet=True)
    return _client


def _with_units(payload: Any) -> Any:
    """Retain the legacy MCP marker for the facade's minute-valued results."""
    if isinstance(payload, dict):
        return {**payload, "unit": "minutes"}
    return payload


def _tool(*, description: Optional[str] = None) -> Callable[[F], F]:
    """Register a tool and normalize facade failures to the legacy JSON style."""
    def decorate(function: F) -> F:
        @functools.wraps(function)
        def guarded(*args: Any, **kwargs: Any) -> Any:
            try:
                return function(*args, **kwargs)
            except APIError as exc:
                return {"error": str(exc)}

        if mcp is not None:
            registered = mcp.tool(description=description)(guarded)
            return registered  # type: ignore[return-value]
        return guarded  # type: ignore[return-value]

    return decorate


@_tool(description="Start a live timer for a project. Use this when the user begins working now.")
def start(
    project: str,
    subprojects: Optional[List[str]] = None,
    note: Optional[str] = None,
):
    """Start a new timer for a project.
    - Use when the user says they are starting work immediately.
    - If they mention subprojects, include them.
    - Do not add a note for a start session.
    - Do NOT use this for past sessions (use `track` instead).
    """
    return _with_units(
        _get_client().start_timer(project, subprojects=subprojects, note=note)
    )


@_tool(description="Stop a live timer for a project. Use this when the user finishes working or takes a break.")
def stop(
    note: Optional[str] = None,
    session_id: Optional[int] = None,
    project: Optional[str] = None,
):
    """Stop a live timer for a project.
    - Use when the user finishes working on a project or takes a break.
    - If they mention a note, include it.
    """
    return _with_units(
        _get_client().stop_timer(session_id=session_id, project=project, note=note)
    )


@_tool(description="Get the status of the current timer, including elapsed time for active sessions.")
def status(session_id: Optional[int] = None, project: Optional[str] = None):
    return _with_units(
        _get_client().get_timer_status(session_id=session_id, project=project)
    )


@_tool(description="Log a past work session with explicit start/end times or date.")
def track(
    project: str,
    start: Optional[str] = None,
    end: Optional[str] = None,
    date: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    subprojects: Optional[List[str]] = None,
    note: Optional[str] = None,
):
    """Track a past session.
    - Use when the user specifies a time range or date in the past.
    - Do NOT use this for starting a live timer (use `start` instead).
    """
    effective_start = start or (f"{date}T{start_time}" if date and start_time else None)
    effective_end = end or (f"{date}T{end_time}" if date and end_time else None)
    if not effective_start or not effective_end:
        return {"error": "Both start and end times are required."}
    return _with_units(
        _get_client().track_session(
            project, effective_start, effective_end, subprojects=subprojects, note=note
        )
    )


@_tool()
def delete_timer(session_id: Optional[int] = None):
    return _get_client().delete_timer(session_id=session_id)


@_tool()
def remove_timer(session_id: Optional[int] = None):
    return delete_timer(session_id=session_id)


@_tool()
def restart(session_id: Optional[int] = None, project: Optional[str] = None):
    return _with_units(
        _get_client().restart_timer(session_id=session_id, project=project)
    )


@_tool(description="List projects grouped by Active, Paused, Completed, and Archived.")
def projects(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    context: Optional[str] = None,
    tags: Optional[List[str]] = None,
):
    return _get_client().list_projects_grouped(
        start_date=start_date, end_date=end_date, context=context, tags=tags
    )


@_tool(description="List all the subprojects of a project.")
def subprojects(project: str):
    return _get_client().list_subprojects(project)


@_tool(description="Get the time tallies for a project between optional start and end dates.")
def totals(
    project: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    context: Optional[str] = None,
    tags: Optional[List[str]] = None,
):
    return _with_units(
        _get_client().get_project_totals(
            project, start_date=start_date, end_date=end_date, context=context, tags=tags
        )
    )


@_tool(description="Rename a project or subproject.")
def rename(project: str, new_name: str, subproject: Optional[str] = None):
    """Rename a project or subproject.

    For a project, provide ``project`` and ``new_name``. For a subproject,
    also provide its existing ``subproject`` name.
    """
    if subproject:
        return _get_client().rename_subproject(project, subproject, new_name)
    return _get_client().rename_project(project, new_name)


@_tool()
def delete_project(project: str):
    return _get_client().delete_project(project)


@_tool(description="Show activity logs. Filter by project, period, dates, context, or tags. Units: minutes.")
def log(
    period: Optional[str] = "week",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    project: Optional[str] = None,
    subproject: Optional[str] = None,
    note: Optional[str] = None,
    context: Optional[str] = None,
    tags: Optional[List[str]] = None,
):
    """Show activity logs filtered by project, subproject, dates, note,
    context, or tags. ``period`` supports week, month, day, and all. Units
    are minutes; explicit dates take precedence over ``period``.
    """
    if note or subproject:
        result = _get_client().search_sessions(
            project=project,
            start_date=start_date,
            end_date=end_date,
            note_snippet=note,
            context=context,
            tags=tags,
        )
        if subproject:
            sessions = [
                item for item in result.get("sessions", [])
                if subproject in (item.get("subprojects") or [])
            ]
            result = {"count": len(sessions), "sessions": sessions}
        return _with_units(result)
    return _with_units(
        _get_client().log_activity(
            period=period,
            project=project,
            start_date=start_date,
            end_date=end_date,
            context=context,
            tags=tags,
        )
    )


@_tool(description="Search for sessions by project, subproject, dates, or note.")
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
):
    """Search sessions by project, subproject, start date, end date, or note.
    At least one search criterion should be provided. Units: minutes.
    """
    result = _get_client().search_sessions(
        project=project,
        start_date=start_date,
        end_date=end_date,
        note_snippet=note,
        active=active,
        limit=limit,
        offset=offset,
        context=context,
        tags=tags,
    )
    if subproject:
        sessions = [
            item for item in result.get("sessions", [])
            if subproject in (item.get("subprojects") or [])
        ]
        result = {"count": len(sessions), "sessions": sessions}
    if order and isinstance(result.get("sessions"), list):
        result["sessions"].sort(key=lambda item: item.get("start") or "", reverse=order.startswith("-"))
    return _with_units(result)


@_tool(description="Get the authenticated Autumn user identity, including the v2 api_version.")
def me():
    return _get_client().get_me()


@_tool(description="Create a new Autumn project.")
def create_project(name: str, description: Optional[str] = None):
    return _get_client().create_project(name, description=description)


@_tool(description="Create a new subproject under an existing project.")
def create_subproject(parent_project: str, name: str, description: Optional[str] = None):
    return _get_client().create_subproject(parent_project, name, description=description)


@_tool(description="Mark a project status. Status should be active, paused, complete, or archived.")
def mark_project(project: str, status: str):
    return _get_client().mark_project_status(project, status)


@_tool(description="Alias for mark_project, matching the CLI command name.")
def mark(project: str, status: str):
    return mark_project(project=project, status=status)


@_tool(description="Get detailed information about one project by name.")
def get_project(name: str):
    return _get_client().get_project(name)


@_tool(description="List projects as a flat ungrouped list with optional filters.")
def list_projects(
    status: Optional[str] = None,
    context: Optional[str] = None,
    tags: Optional[List[str]] = None,
    search: Optional[str] = None,
):
    return _get_client().list_projects_flat(status=status, context=context, tags=tags, search=search)


@_tool(description="Delete a subproject from a project.")
def delete_subproject(project: str, subproject: str):
    return _get_client().delete_subproject(project, subproject)


@_tool(description="Alias for delete_subproject, matching the CLI command name.")
def delete_sub(project: str, subproject: str):
    return delete_subproject(project=project, subproject=subproject)


@_tool(description="Search subprojects by name within a parent project.")
def search_subprojects(project: str, search_term: str):
    return _get_client().search_subprojects(project, search_term)


@_tool(description="Edit an existing completed session.")
def edit_session(
    session_id: int,
    project: Optional[str] = None,
    subprojects: Optional[List[str]] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
    note: Optional[str] = None,
):
    return _get_client().edit_session(
        session_id, project=project, subprojects=subprojects, start=start, end=end, note=note
    )


@_tool(description="Delete a saved/completed session log by ID.")
def delete_session(session_id: int):
    return _get_client().delete_session(session_id)


@_tool(description="Alias for delete_session, for deleting a saved session log.")
def delete_session_log(session_id: int):
    return delete_session(session_id=session_id)


@_tool(description="Search for existing projects by name before calling tools requiring a project.")
def search_projects(search_term: str, status: Optional[str] = None):
    """Search for projects by name.
    - Use this when the supplied project name may not exactly match.
    - Call this first when unsure whether a project exists.
    - Results provide the canonical project name for other calls.
    """
    return _get_client().search_projects(search_term, status=status)


@_tool(description="List available contexts for filtering projects and sessions.")
def contexts():
    return _get_client().list_contexts()


@_tool(description="Alias for contexts, matching the CLI command name.")
def context():
    return contexts()


@_tool(description="List available tags for filtering projects and sessions.")
def tags():
    return _get_client().list_tags()


@_tool(description="Alias for tags, matching the CLI command name.")
def tag():
    return tags()


@_tool(description="Export Autumn data as format-2 JSON, optionally filtered.")
def export_data(
    project: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    context: Optional[int] = None,
    tags: Optional[List[int]] = None,
    compress: bool = False,
    autumn_compatible: bool = True,
):
    return _get_client().export_data(
        project=project, start_date=start_date, end_date=end_date, context=context,
        tags=tags, compress=compress, autumn_compatible=autumn_compatible
    )


@_tool(description="Alias for export_data, matching the CLI command name.")
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
        project=project, start_date=start_date, end_date=end_date, context=context,
        tags=tags, compress=compress, autumn_compatible=autumn_compatible
    )


@_tool(description="Return the API's deprecation notice for the retired totals audit.")
def audit_totals():
    return _get_client().audit_totals()


@_tool(description="Alias for audit_totals, matching the CLI command name.")
def audit():
    return audit_totals()


@_tool(description="Get project totals across sessions, optionally filtered.")
def tally_by_sessions(
    project_name: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    context: Optional[str] = None,
    tags: Optional[List[str]] = None,
):
    return _get_client().tally_by_sessions(
        project_name=project_name, start_date=start_date, end_date=end_date,
        context=context, tags=tags
    )


@_tool(description="Get subproject totals for a project, optionally filtered.")
def tally_by_subprojects(
    project_name: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    context: Optional[str] = None,
    tags: Optional[List[str]] = None,
):
    return _get_client().tally_by_subprojects(
        project_name, start_date=start_date, end_date=end_date, context=context, tags=tags
    )


@_tool(description="List sessions for charts or analysis, optionally filtered.")
def list_sessions(
    project_name: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    context: Optional[str] = None,
    tags: Optional[List[str]] = None,
):
    return _get_client().list_sessions(
        project_name=project_name, start_date=start_date, end_date=end_date,
        context=context, tags=tags
    )


@_tool(description="Get time totals aggregated by context.")
def tally_by_context(start_date: Optional[str] = None, end_date: Optional[str] = None):
    return _get_client().tally_by_context(start_date=start_date, end_date=end_date)


@_tool(description="Get project count and time totals grouped by project status.")
def tally_by_status(context: Optional[str] = None):
    return _get_client().tally_by_status(context=context)


@_tool(description="Get time and project count aggregated by tag.")
def tally_by_tags():
    return _get_client().tally_by_tags()


@_tool(description="Get nested Context -> Project -> Subproject hierarchy with totals.")
def hierarchy(start_date: Optional[str] = None, end_date: Optional[str] = None):
    return _get_client().get_hierarchy(start_date=start_date, end_date=end_date)


@_tool(description="Get projects with statistics for visualization and comparison.")
def projects_with_stats(context: Optional[str] = None, tags: Optional[List[str]] = None):
    return _get_client().get_projects_with_stats(context=context, tags=tags)


@_tool(description="Merge two projects into one new project, moving their sessions and subprojects.")
def merge_projects(project1: str, project2: str, new_project_name: str):
    """Merge two projects into a uniquely named new project.

    All sessions and subprojects move to the merged project. Duplicate
    subproject names are renamed automatically and totals are recalculated.
    """
    return _get_client().merge_projects(project1, project2, new_project_name)


@_tool(description="Merge two subprojects into one new subproject in the same parent project.")
def merge_subprojects(
    subproject1: str,
    subproject2: str,
    new_subproject_name: str,
    project_id: int,
):
    """Merge two subprojects in a parent project and move their sessions.

    Both subprojects must belong to ``project_id`` and the new name must be
    unique within that parent project. Totals are recalculated automatically.
    """
    return _get_client().merge_subprojects(
        project_id, subproject1, subproject2, new_subproject_name
    )


@_tool(description="List commitments with optional activity, aggregation, progress, and streak filters.")
def list_commitments(
    active: Optional[bool] = None,
    aggregation_type: Optional[str] = None,
    progress: bool = True,
    streak: bool = False,
):
    return _get_client().list_commitments(
        active=active,
        aggregation_type=aggregation_type,
        progress=progress,
        streak=streak,
    )


def main() -> None:
    """Run the Autumn MCP server over the default transport."""
    if mcp is None:
        raise SystemExit(_MISSING_MCP)
    mcp.run()


if __name__ == "__main__":
    main()
