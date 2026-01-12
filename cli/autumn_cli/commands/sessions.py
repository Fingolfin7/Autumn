"""Session commands for Autumn CLI."""

import click
from typing import Optional
from datetime import datetime, timedelta, date

from ..api_client import APIClient, APIError
from ..utils.console import console
from ..utils.log_render import render_sessions_list
from ..utils.resolvers import resolve_context_param, resolve_tag_params


@click.group(invoke_without_command=True)
@click.pass_context
@click.option(
    "--period",
    "-p",
    type=click.Choice(
        ["day", "week", "fortnight", "month", "lunar cycle", "quarter", "year", "all"],
        case_sensitive=False,
    ),
    default="week",
    help="Time period (default: week)",
)
@click.option("--project", help="Filter by project name")
@click.option("--context", "-c", help="Filter by context (name or id)")
@click.option("--tag", "-t", multiple=True, help="Filter by tag (repeatable)")
@click.option("--start-date", help="Start date (YYYY-MM-DD)")
@click.option("--end-date", help="End date (YYYY-MM-DD)")
@click.option("--pick", is_flag=True, help="Interactively pick project/context/tags if not provided")
def log(
    ctx: click.Context,
    period: Optional[str],
    project: Optional[str],
    context: Optional[str],
    tag: tuple,
    start_date: Optional[str],
    end_date: Optional[str],
    pick: bool,
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
                from ..utils.pickers import pick_from_names

                if not project:
                    grouped = client.list_projects_grouped()
                    all_projects = []
                    for bucket in (grouped.get("projects") or {}).values():
                        for p in bucket or []:
                            name = p.get("name") or p.get("project")
                            if name:
                                all_projects.append(name)
                    all_projects = sorted(set(all_projects))
                    chosen = pick_from_names(label="project", names=all_projects)
                    project = chosen or project

                if not context:
                    ctx_names = [c.get("name") for c in contexts_payload if c.get("name")]
                    chosen = pick_from_names(label="context", names=sorted(ctx_names))
                    context = chosen or context

                if not tag:
                    tag_names = [t.get("name") for t in tags_payload if t.get("name")]
                    chosen = pick_from_names(label="tag", names=sorted(tag_names))
                    tag = tuple([chosen]) if chosen else tag

            ctx_res = resolve_context_param(context=context, contexts=contexts_payload)
            tag_resolved, _tag_warnings = resolve_tag_params(tags=list(tag) if tag else None, known_tags=tags_payload)

            resolved_context = ctx_res.value
            resolved_tags = tag_resolved or None

            # Normalize period to a consistent trailing window.
            # Server interprets period=week as "since Monday"; we want "last 7 days".
            normalized_period = period.lower() if period else "week"

            # For standard server-supported periods, prefer passing `period` directly
            # (unless the user provided explicit start/end).
            server_periods = {"day", "week", "month", "all"}

            if not start_date and not end_date and normalized_period in server_periods:
                result = client.log_activity(
                    period=normalized_period,
                    project=project,
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
                        project=project,
                        start_date=None,
                        end_date=None,
                        context=resolved_context,
                        tags=resolved_tags,
                    )
                else:
                    result = client.log_activity(
                        period=None,
                        project=project,
                        start_date=calculated_start_date,
                        end_date=calculated_end_date,
                        context=resolved_context,
                        tags=resolved_tags,
                    )

            logs = result.get("logs", [])
            count = result.get("count", len(logs))

            console.print(f"[autumn.label]Sessions:[/] {count}")
            console.print(render_sessions_list(logs))
        except APIError as e:
            console.print(f"[autumn.err]Error:[/] {e}")
            raise click.Abort()


@log.command("search")
@click.option("--project", help="Filter by project name")
@click.option("--context", "-c", help="Filter by context (name or id)")
@click.option("--tag", "-t", multiple=True, help="Filter by tag (repeatable)")
@click.option("--start-date", help="Start date (YYYY-MM-DD)")
@click.option("--end-date", help="End date (YYYY-MM-DD)")
@click.option("--note-snippet", help="Search for text in notes")
@click.option("--active/--no-active", default=False, help="Include active sessions")
@click.option("--limit", type=int, help="Limit number of results")
@click.option("--offset", type=int, help="Offset for pagination")
@click.option("--pick", is_flag=True, help="Interactively pick project/context/tags if not provided")
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
):
    """Search sessions with filters."""
    try:
        client = APIClient()

        meta = client.get_discovery_meta(ttl_seconds=300, refresh=False)
        contexts_payload = meta.get("contexts", [])
        tags_payload = meta.get("tags", [])

        if pick:
            from ..utils.pickers import pick_from_names

            if not project:
                grouped = client.list_projects_grouped()
                all_projects = []
                for bucket in (grouped.get("projects") or {}).values():
                    for p in bucket or []:
                        name = p.get("name") or p.get("project")
                        if name:
                            all_projects.append(name)
                all_projects = sorted(set(all_projects))
                chosen = pick_from_names(label="project", names=all_projects)
                project = chosen or project

            if not context:
                ctx_names = [c.get("name") for c in contexts_payload if c.get("name")]
                chosen = pick_from_names(label="context", names=sorted(ctx_names))
                context = chosen or context

            if not tag:
                tag_names = [t.get("name") for t in tags_payload if t.get("name")]
                chosen = pick_from_names(label="tag", names=sorted(tag_names))
                tag = tuple([chosen]) if chosen else tag

        ctx_res = resolve_context_param(context=context, contexts=contexts_payload)
        tag_resolved, _tag_warnings = resolve_tag_params(tags=list(tag) if tag else None, known_tags=tags_payload)

        resolved_context = ctx_res.value
        resolved_tags = tag_resolved or None

        result = client.search_sessions(
            project=project,
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
        console.print(render_sessions_list(sessions_list))
    except APIError as e:
        console.print(f"[autumn.err]Error:[/] {e}")
        raise click.Abort()


@click.command()
@click.argument("project")
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
def track(project: str, subprojects: tuple, start: str, end: str, note: Optional[str]):
    """Track a completed session (manually log time)."""
    try:
        start_iso = _normalize_datetime(start)
        end_iso = _normalize_datetime(end)

        client = APIClient()
        subprojects_list = list(subprojects) if subprojects else None
        result = client.track_session(project, start_iso, end_iso, subprojects_list, note)

        if result.get("ok"):
            session = result.get("session", {})
            duration = session.get("elapsed") or session.get("duration_minutes", 0)
            console.print("[autumn.ok]Session tracked.[/]")
            console.print(f"[autumn.label]ID:[/] {session.get('id')}")
            console.print(f"[autumn.label]Project:[/] {project}")
            console.print(f"[autumn.label]Duration:[/] {duration} minutes")
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

    The current server-side `parse_date_or_datetime()` only accepts:
      - %m-%d-%Y
      - %m-%d-%Y %H:%M:%S
      - %Y-%m-%d
      - %Y-%m-%d %H:%M:%S

    It does NOT accept ISO-8601 forms like `...T...` or timezone suffixes like `Z`.

    This function accepts common ISO/space-separated inputs (optionally with timezone)
    and converts them into `%Y-%m-%d %H:%M:%S`.

    Special keyword:
      - `now` (case-insensitive) resolves to the current local time.
      - optional relative offsets: `now-5m`, `now+2h`, `now-1d`.

    Important: if the input includes a timezone (e.g. `Z` or `-05:00`), we convert
    it to *local time* and then drop the timezone info to match what the server
    expects.
    """

    raw = (dt_str or "").strip()
    if not raw:
        raise ValueError("Empty datetime")

    # Support `now` keyword (case-insensitive), with optional relative offsets.
    # Examples: now, NOW, now-5m, now+2h, now-1d
    lower = raw.lower()
    if lower == "now" or lower.startswith("now+") or lower.startswith("now-"):
        base = datetime.now().astimezone().replace(tzinfo=None)
        if lower == "now":
            return base.strftime("%Y-%m-%d %H:%M:%S")

        # Parse relative suffix: now(+|-)<int><unit>
        # units: s, m, h, d
        import re

        m = re.fullmatch(r"now([+-])(\d+)([smhd])", lower)
        if not m:
            raise ValueError(
                "Invalid now-offset format. Use now, now-5m, now+2h, now-1d, now+30s."
            )

        sign, amount_s, unit = m.group(1), m.group(2), m.group(3)
        amount = int(amount_s)
        seconds = {
            "s": 1,
            "m": 60,
            "h": 3600,
            "d": 86400,
        }[unit] * amount

        delta = timedelta(seconds=seconds)
        dt = base + delta if sign == "+" else base - delta
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    # Normalize common UTC marker for Python parsing.
    candidate = raw
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"

    dt: Optional[datetime]

    # Prefer ISO parsing (handles offsets / fractional seconds)
    try:
        dt = datetime.fromisoformat(candidate)
    except ValueError:
        dt = None

    if dt is None:
        formats = [
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
        ]
        for fmt in formats:
            try:
                dt = datetime.strptime(raw, fmt)
                break
            except ValueError:
                continue

    if dt is None:
        raise ValueError(f"Could not parse datetime: {dt_str}")

    # If timezone-aware, convert to local time then drop tzinfo.
    if dt.tzinfo is not None:
        dt = dt.astimezone().replace(tzinfo=None)


    return dt.strftime("%Y-%m-%d %H:%M:%S")
