"""Session commands for Autumn CLI."""

import click
from typing import Optional
from datetime import datetime, timedelta

from ..api_client import APIClient, APIError
from ..utils.console import console
from ..utils.log_render import render_sessions_list
from ..utils.resolvers import resolve_context_param, resolve_tag_params, resolve_project_param, resolve_subproject_params
from ..utils.datetime_parse import parse_user_datetime, format_server_datetime


@click.group(invoke_without_command=True)
@click.pass_context
@click.option(
    "--period",
    "-P",
    type=click.Choice(
        ["day", "week", "fortnight", "month", "lunar cycle", "quarter", "year", "all"],
        case_sensitive=False,
    ),
    default="week",
    help="Time period (default: week)",
)
@click.option("--project", "-p", help="Filter by project name")
@click.option("--context", "-c", help="Filter by context (name or id)")
@click.option("--tag", "-t", multiple=True, help="Filter by tag (repeatable)")
@click.option("--start-date", help="Start date (YYYY-MM-DD)")
@click.option("--end-date", help="End date (YYYY-MM-DD)")
@click.option("--pick", is_flag=True, help="Interactively pick project/context/tags if not provided")
@click.option(
    "--raw/--markdown",
    default=False,
    help="Show raw (single-line) notes instead of Markdown",
)
def log(
    ctx: click.Context,
    period: Optional[str],
    project: Optional[str],
    context: Optional[str],
    tag: tuple,
    start_date: Optional[str],
    end_date: Optional[str],
    pick: bool,
    raw: bool,
):
    """Show activity logs (saved sessions). Use 'log search' for advanced search."""
    # If a subcommand was invoked, don't run this command
    if ctx.invoked_subcommand is None:
        try:
            client = APIClient()

            meta = client.get_discovery_meta(ttl_seconds=300, refresh=False)
            contexts_payload = meta.get("contexts", [])
            tags_payload = meta.get("tags", [])

            if pick:
                from ..utils.pickers import pick_project, pick_context, pick_tag

                if not project:
                    chosen = pick_project(client)
                    project = chosen or project

                if not context:
                    chosen = pick_context(client)
                    context = chosen or context

                if not tag:
                    chosen = pick_tag(client)
                    tag = tuple([chosen]) if chosen else tag

            ctx_res = resolve_context_param(context=context, contexts=contexts_payload)
            tag_resolved, _tag_warnings = resolve_tag_params(tags=list(tag) if tag else None, known_tags=tags_payload)

            resolved_context = ctx_res.value
            resolved_tags = tag_resolved or None

            # Resolve project name (case-insensitive + alias support)
            resolved_project = project
            if project:
                projects_meta = client.get_discovery_projects()
                proj_res = resolve_project_param(project=project, projects=projects_meta.get("projects", []))
                if proj_res.warning:
                    console.print(f"[autumn.warn]Warning:[/] {proj_res.warning}")
                resolved_project = proj_res.value or project

            # Normalize period to a consistent trailing window.
            # Server interprets period=week as "since Monday"; we want "last 7 days".
            normalized_period = period.lower() if period else "week"

            # For standard server-supported periods, prefer passing `period` directly
            # (unless the user provided explicit start/end).
            server_periods = {"day", "week", "month", "all"}

            if not start_date and not end_date and normalized_period in server_periods:
                result = client.log_activity(
                    period=normalized_period,
                    project=resolved_project,
                    start_date=None,
                    end_date=None,
                    context=resolved_context,
                    tags=resolved_tags,
                )
            else:
                # For custom periods (fortnight/lunar cycle/quarter/year) or explicit dates,
                # calculate a concrete date window.
                calculated_start_date = start_date
                calculated_end_date = end_date

                if not start_date and not end_date and normalized_period != "all":
                    from ..utils.periods import period_to_dates

                    derived_start, derived_end = period_to_dates(normalized_period)
                    calculated_start_date = derived_start
                    calculated_end_date = derived_end

                if normalized_period == "all" and not (calculated_start_date or calculated_end_date):
                    result = client.log_activity(
                        period="all",
                        project=resolved_project,
                        start_date=None,
                        end_date=None,
                        context=resolved_context,
                        tags=resolved_tags,
                    )
                else:
                    result = client.log_activity(
                        period=None,
                        project=resolved_project,
                        start_date=calculated_start_date,
                        end_date=calculated_end_date,
                        context=resolved_context,
                        tags=resolved_tags,
                    )

            logs = result.get("logs", [])
            count = result.get("count", len(logs))

            console.print(f"[autumn.label]Sessions:[/] {count}")
            rendered = render_sessions_list(logs, markdown_notes=not raw)
            if isinstance(rendered, list):
                for r in rendered:
                    console.print(r)
            else:
                console.print(rendered)
        except APIError as e:
            console.print(f"[autumn.err]Error:[/] {e}")
            raise click.Abort()


@log.command("search")
@click.option("--project", "-p", help="Filter by project name")
@click.option("--context", "-c", help="Filter by context (name or id)")
@click.option("--tag", "-t", multiple=True, help="Filter by tag (repeatable)")
@click.option("--start-date", help="Start date (YYYY-MM-DD)")
@click.option("--end-date", help="End date (YYYY-MM-DD)")
@click.option("--note-snippet", "-n", help="Search for text in notes")
@click.option("--active/--no-active", default=False, help="Include active sessions")
@click.option("--limit", type=int, help="Limit number of results")
@click.option("--offset", type=int, help="Offset for pagination")
@click.option("--pick", is_flag=True, help="Interactively pick project/context/tags if not provided")
@click.option(
    "--raw/--markdown",
    default=False,
    help="Show raw (single-line) notes instead of Markdown",
)
def log_search(
    project: Optional[str],
    context: Optional[str],
    tag: tuple,
    start_date: Optional[str],
    end_date: Optional[str],
    note_snippet: Optional[str],
    active: bool,
    limit: Optional[int],
    offset: Optional[int],
    pick: bool,
    raw: bool,
):
    """Search sessions with filters."""
    try:
        client = APIClient()

        meta = client.get_discovery_meta(ttl_seconds=300, refresh=False)
        contexts_payload = meta.get("contexts", [])
        tags_payload = meta.get("tags", [])

        if pick:
            from ..utils.pickers import pick_project, pick_context, pick_tag

            if not project:
                chosen = pick_project(client)
                project = chosen or project

            if not context:
                chosen = pick_context(client)
                context = chosen or context

            if not tag:
                chosen = pick_tag(client)
                tag = tuple([chosen]) if chosen else tag

        ctx_res = resolve_context_param(context=context, contexts=contexts_payload)
        tag_resolved, _tag_warnings = resolve_tag_params(tags=list(tag) if tag else None, known_tags=tags_payload)

        resolved_context = ctx_res.value
        resolved_tags = tag_resolved or None

        # Resolve project name (case-insensitive + alias support)
        resolved_project = project
        if project:
            projects_meta = client.get_discovery_projects()
            proj_res = resolve_project_param(project=project, projects=projects_meta.get("projects", []))
            if proj_res.warning:
                console.print(f"[autumn.warn]Warning:[/] {proj_res.warning}")
            resolved_project = proj_res.value or project

        result = client.search_sessions(
            project=resolved_project,
            start_date=start_date,
            end_date=end_date,
            note_snippet=note_snippet,
            active=active,
            limit=limit,
            offset=offset,
            context=resolved_context,
            tags=resolved_tags,
        )

        sessions_list = result.get("sessions", [])
        count = result.get("count", len(sessions_list))

        console.print(f"[autumn.label]Sessions:[/] {count}")
        rendered = render_sessions_list(sessions_list, markdown_notes=not raw)
        if isinstance(rendered, list):
            for r in rendered:
                console.print(r)
        else:
            console.print(rendered)
    except APIError as e:
        console.print(f"[autumn.err]Error:[/] {e}")
        raise click.Abort()


@click.command()
@click.argument("project", required=False)
@click.option("--subprojects", "-s", multiple=True, help="Subproject names (can specify multiple)")
@click.option(
    "--start",
    required=True,
    help="Start time (e.g. 2026-01-11T22:18:11-05:00, 2026-01-11T22:18:11Z, or 2026-01-11 22:18:11)",
)
@click.option(
    "--end",
    required=True,
    help="End time (e.g. 2026-01-12T02:56:13-05:00, 2026-01-12T02:56:13Z, or 2026-01-12 02:56:13)",
)
@click.option("--note", "-n", help="Note for the session")
@click.option("--pick", is_flag=True, help="Interactively pick project/subprojects")
def track(project: Optional[str], subprojects: tuple, start: str, end: str, note: Optional[str], pick: bool):
    """Track a completed session (manually log time)."""
    try:
        start_iso = _normalize_datetime(start)
        end_iso = _normalize_datetime(end)

        client = APIClient()

        # Interactive picker for project if --pick or no project provided
        if pick or not project:
            from ..utils.pickers import pick_project, pick_subproject

            picked_project = pick_project(client)
            if not picked_project:
                console.print("[autumn.warn]No project selected.[/]")
                raise click.Abort()
            project = picked_project

            # Also offer to pick subprojects if --pick was explicit
            if pick and not subprojects:
                picked_sub = pick_subproject(client, project)
                if picked_sub:
                    subprojects = (picked_sub,)

        # Resolve project name (case-insensitive + alias support)
        projects_meta = client.get_discovery_projects()
        proj_res = resolve_project_param(project=project, projects=projects_meta.get("projects", []))
        if proj_res.warning:
            console.print(f"[autumn.warn]Warning:[/] {proj_res.warning}")
        resolved_project = proj_res.value or project

        # Resolve subprojects (case-insensitive + alias support)
        subprojects_list = None
        if subprojects:
            try:
                known_subs_res = client.list_subprojects(resolved_project)
                known_subs = known_subs_res.get("subprojects", []) if isinstance(known_subs_res, dict) else known_subs_res
            except Exception:
                known_subs = []
            resolved_subs, sub_warnings = resolve_subproject_params(
                subprojects=subprojects, known_subprojects=known_subs
            )
            for w in sub_warnings:
                console.print(f"[autumn.warn]Warning:[/] {w}")
            subprojects_list = resolved_subs if resolved_subs else None

        result = client.track_session(resolved_project, start_iso, end_iso, subprojects_list, note)

        if result.get("ok"):
            session = result.get("session", {})
            duration = session.get("elapsed") or session.get("duration_minutes", 0)
            console.print("[autumn.ok]Session tracked.[/]")
            console.print(f"[autumn.label]ID:[/] [autumn.id]{session.get('id')}[/]")
            console.print(f"[autumn.label]Project:[/] [autumn.project]{resolved_project}[/]")
            console.print(f"[autumn.label]Duration:[/] [autumn.duration]{duration} minutes[/]")

        else:
            console.print(f"[autumn.err]Error:[/] {result.get('error', 'Unknown error')}")
    except APIError as e:
        console.print(f"[autumn.err]Error:[/] {e}")
        raise click.Abort()
    except ValueError as e:
        console.print(f"[autumn.err]Error:[/] Invalid date format - {e}")
        raise click.Abort()


def _normalize_datetime(dt_str: str) -> str:
    """Normalize a user-provided datetime to the server-accepted format.

    Server expects `%Y-%m-%d %H:%M:%S` (no timezone, no `T`).

    This accepts:
      - ISO-8601 and space-separated timestamps (optionally with timezone)
      - `now`, `today`, `yesterday`
      - Relative offsets like `-5m`, `+2h`, `now-1d`, `today+90m`

    If the input includes a timezone (e.g. `Z` or `-05:00`), we convert it to
    local time before formatting.
    """

    user_dt = parse_user_datetime(dt_str)
    if not user_dt:
        raise ValueError(f"Could not parse datetime: {dt_str}")

    # Convert to server format
    return format_server_datetime(user_dt.dt)
