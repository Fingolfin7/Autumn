"""Text formatting utilities for CLI output."""

from datetime import datetime, timedelta
from typing import List, Dict, Any

from rich.table import Table

from .console import console


def format_duration_minutes(minutes: float) -> str:
    """Format duration in minutes to human-readable string.

    Uses second-level accuracy (Mm Ss / Hh Mm Ss).
    """
    if minutes is None:
        return "N/A"

    try:
        total_seconds = int(round(float(minutes) * 60))
    except Exception:
        total_seconds = 0

    hours, rem = divmod(total_seconds, 3600)
    mins, secs = divmod(rem, 60)

    if hours > 0:
        return f"{hours}h {mins:02d}m {secs:02d}s"
    return f"{mins}m {secs:02d}s"


def format_duration_hours(hours: float) -> str:
    """Format duration in hours to human-readable string."""
    if hours is None:
        return "N/A"

    return f"{hours:.2f}h"


def format_datetime(iso_string: str) -> str:
    """Format ISO datetime string to readable format.

    Old-CLI-inspired: shorter and easier to scan.
    """
    try:
        dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
        return dt.strftime("%d %b %Y %H:%M")
    except Exception:
        return iso_string


def format_date(iso_string: str) -> str:
    """Format ISO date/datetime string to date only."""
    try:
        dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return iso_string


def format_time_hms(iso_string: str) -> str:
    """Format an ISO datetime string to time-only (HH:MM:SS)."""
    try:
        dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
        return dt.strftime("%H:%M:%S")
    except Exception:
        return iso_string


def format_log_date_header(iso_date_or_datetime: str) -> str:
    """Format a date key (YYYY-MM-DD) to 'Weekday DD Month YYYY'."""
    try:
        # Accept either YYYY-MM-DD or a full ISO datetime
        part = iso_date_or_datetime.split("T", 1)[0]
        dt = datetime.fromisoformat(part)
        return dt.strftime("%A %d %B %Y")
    except Exception:
        return iso_date_or_datetime


def format_day_total_minutes(total_minutes: float) -> str:
    """Format a day total in minutes the old way (Xh Ym or Xm Ss-like).

    Mirrors old CLI behavior: if hours > 0 show 'Hh Mm', else show 'Mm Ss'.
    """
    try:
        td = timedelta(minutes=float(total_minutes or 0))
    except Exception:
        td = timedelta(minutes=0)

    seconds = int(td.total_seconds())
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)

    if hours > 0:
        return f"{hours:02d}h {minutes:02d}m"
    return f"{minutes:02d}m {secs:02d}s"


def _get_session_fields(session: Dict) -> Dict[str, Any]:
    """Normalize session dict keys from various API responses."""
    project = session.get("p") or session.get("project") or ""
    subs = session.get("subs") or session.get("subprojects") or []

    start_raw = session.get("start") or session.get("start_time") or ""
    end_raw = session.get("end") or session.get("end_time")

    duration = (
        session.get("dur")
        or session.get("duration_minutes")
        or session.get("elapsed_minutes")
        or session.get("elapsed")
        or 0
    )

    note = session.get("note") or ""

    return {
        "id": session.get("id"),
        "project": project,
        "subprojects": subs,
        "start": start_raw,
        "end": end_raw,
        "duration": duration,
        "note": note,
    }


def sessions_table(
    sessions: List[Dict],
    *,
    show_notes: bool = True,
    note_width: int = 40,
) -> Table:
    """Create a Rich table for sessions.

    Note: we return a Table so commands can print it with consistent styling.
    """
    table = Table(show_header=True, header_style="autumn.title", show_lines=False)

    table.add_column("ID", style="autumn.id", no_wrap=True)
    table.add_column("Project", style="autumn.project")
    table.add_column("Subprojects", style="autumn.subproject")
    table.add_column("Start", style="autumn.time", no_wrap=True)
    table.add_column("End", style="autumn.time", no_wrap=True)
    table.add_column("Dur", style="autumn.time", no_wrap=True, justify="right")
    if show_notes:
        table.add_column("Note", style="autumn.note", overflow="fold", max_width=note_width)

    if not sessions:
        table.add_row("-", "-", "-", "-", "-", "-", "No sessions found." if show_notes else "")
        return table

    for s in sessions:
        f = _get_session_fields(s)
        subs_str = ", ".join(f["subprojects"]) if f["subprojects"] else "-"

        start_str = format_datetime(f["start"])
        end_str = format_datetime(f["end"]) if f["end"] else "Active"
        dur_str = format_duration_minutes(float(f["duration"]) if f["duration"] is not None else 0)

        row = [
            str(f["id"] or ""),
            f["project"],
            subs_str,
            start_str,
            end_str,
            dur_str,
        ]
        if show_notes:
            note = f["note"].strip().replace("\r", " ").replace("\n", " ")
            row.append(note)

        # Highlight active sessions
        style = "autumn.ok" if not f["end"] else None
        table.add_row(*row, style=style)

    return table


def format_sessions_table(sessions: List[Dict], compact: bool = True) -> str:
    """Backwards-compatible wrapper.

    Older commands called this and expected a string; now we render a Rich table.
    Always includes notes in compact mode (per request).
    """
    table = sessions_table(sessions, show_notes=True)
    with console.capture() as capture:
        console.print(table)
    return capture.get()


def projects_tables(projects_data: Dict) -> List[Table]:
    """Create Rich tables for projects grouped by status.

    Returns a list of Table objects that can be printed directly.
    """
    projects = projects_data.get("projects", {})
    tables = []

    if not any(projects.values()):
        return tables

    status_order = ["active", "paused", "complete", "archived"]
    status_styles = {
        "active": "autumn.status.active",
        "paused": "autumn.status.paused",
        "complete": "autumn.status.complete",
        "archived": "autumn.status.archived",
    }

    for status_key in status_order:
        proj_list = projects.get(status_key, [])
        if not proj_list:
            continue

        table = Table(
            show_header=True,
            header_style="autumn.title",
            show_lines=False,
            expand=False,
            title=f"[{status_styles.get(status_key, 'autumn.title')}]{status_key.upper()}[/]",
            title_justify="left",
            padding=(0, 1),
        )

        table.add_column("Project", style="autumn.project", no_wrap=True)
        table.add_column("Total", style="autumn.time", justify="right", no_wrap=True)
        table.add_column("Sessions", style="autumn.muted", justify="right", no_wrap=True)
        table.add_column("Avg", style="autumn.time", justify="right", no_wrap=True)
        table.add_column("Started", style="autumn.muted", no_wrap=True)
        table.add_column("Last Active", style="autumn.time", no_wrap=True)
        table.add_column("Context", style="autumn.subproject", no_wrap=True)
        table.add_column("Tags", style="autumn.note", overflow="fold", max_width=20)

        for proj in proj_list:
            if isinstance(proj, str):
                # Compact format - just project name
                table.add_row(proj, "-", "-", "-", "-", "-", "-", "-")
            else:
                # Full format with metadata
                name = proj.get("name", "")
                total_time = proj.get("total_time", 0)
                session_count = proj.get("session_count", 0)
                avg_session = proj.get("avg_session_duration", 0)
                start_date = proj.get("start_date", "")
                last_updated = proj.get("last_updated", "")
                context = proj.get("context", "") or ""
                tags = proj.get("tags", []) or []

                # Format the total time
                total_str = format_duration_minutes(float(total_time)) if total_time else "0m"

                # Format session count
                sessions_str = str(session_count) if session_count else "0"

                # Format average session duration
                avg_str = format_duration_minutes(float(avg_session)) if avg_session else "-"

                # Format dates
                start_str = format_date(start_date) if start_date else "-"
                last_str = format_date(last_updated) if last_updated else "-"

                # Format tags
                tags_str = ", ".join(tags) if tags else "-"

                table.add_row(name, total_str, sessions_str, avg_str, start_str, last_str, context or "-", tags_str)

        tables.append(table)

    return tables


def format_projects_table(projects_data: Dict) -> str:
    """Format projects grouped data as a string (backwards compatible).

    For direct Rich console output, use projects_tables() instead.
    """
    tables = projects_tables(projects_data)
    if not tables:
        return "No projects found."

    output_parts = []
    for table in tables:
        with console.capture() as capture:
            console.print(table)
            console.print()
        output_parts.append(capture.get())

    return "".join(output_parts).rstrip()


def format_totals_table(totals_data: Dict) -> str:
    """Format project/subproject totals as a table."""
    from tabulate import tabulate

    project = totals_data.get("project", "")
    total = totals_data.get("total") or totals_data.get("total_minutes", 0)
    subs = totals_data.get("subs") or totals_data.get("subprojects", [])

    headers = ["Project/Subproject", "Total Time"]
    rows = [[project, format_duration_minutes(total)]]

    for sub in subs:
        if isinstance(sub, list):
            name, minutes = sub
        else:
            name = sub.get("name", "")
            minutes = sub.get("total_minutes", 0)
        rows.append([f"  └─ {name}", format_duration_minutes(minutes)])

    return tabulate(rows, headers=headers, tablefmt="grid")


def contexts_table(contexts: List[Dict[str, Any]], show_description: bool = False) -> Table:
    """Render a table of contexts."""
    table = Table(show_header=True, header_style="autumn.title", padding=(0, 1))
    table.add_column("ID", style="autumn.id", no_wrap=True, justify="right")
    table.add_column("Name", style="autumn.project", no_wrap=True)
    if show_description:
        table.add_column("Description", style="autumn.description", overflow="fold")

    for c in contexts:
        cid = c.get("id")
        name = c.get("name", "")
        if show_description:
            table.add_row(str(cid) if cid is not None else "-", name, c.get("description", "") or "")
        else:
            table.add_row(str(cid) if cid is not None else "-", name)

    return table


def tags_table(tags: List[Dict[str, Any]], show_color: bool = False) -> Table:
    """Render a table of tags."""
    table = Table(show_header=True, header_style="autumn.title", padding=(0, 1))
    table.add_column("ID", style="autumn.id", no_wrap=True, justify="right")
    table.add_column("Name", style="autumn.note", no_wrap=True)
    if show_color:
        table.add_column("Color", style="autumn.muted", no_wrap=True)

    for t in tags:
        tid = t.get("id")
        name = t.get("name", "")
        if show_color:
            table.add_row(str(tid) if tid is not None else "-", name, t.get("color", "") or "")
        else:
            table.add_row(str(tid) if tid is not None else "-", name)

    return table

