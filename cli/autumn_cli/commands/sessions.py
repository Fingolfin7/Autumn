"""Session commands for Autumn CLI."""

import sys

import click
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta

from ..api_client import APIClient, APIError
from ..utils.console import console
from ..utils.formatters import format_duration_minutes, parse_utc_to_local
from ..utils.log_render import (
    format_subprojects_bracketed,
    render_sessions_list,
)
from ..utils.resolvers import (
    resolve_context_param,
    resolve_project_name,
    resolve_subproject_params,
    resolve_tag_params,
)
from ..utils.datetime_parse import parse_user_datetime, format_server_datetime
from ..utils.duration_parse import parse_duration_to_seconds
from ..utils.cli_options import date_range_options, period_option, search_options
from ..utils.periods import normalize_period, parse_date_arg
from ..utils.splits import parse_split, resolve_split_selection


def _format_session_id_line(session_id: Optional[int]) -> str:
    if session_id is None:
        return "Session ID: [autumn.muted]unknown[/]"
    return f"Session ID: #[autumn.id]{session_id}[/]"


def _resolve_excluded_projects(client: APIClient, exclude: tuple) -> Optional[list[str]]:
    if not exclude:
        return None
    return [resolve_project_name(client, project) for project in exclude]


class SessionRef(click.ParamType):
    """A saved session ID (``123`` or ``#123``) or ``last``."""

    name = "SESSION"

    def convert(self, value: Any, param: Optional[click.Parameter], ctx: Optional[click.Context]):
        if isinstance(value, int):
            return value
        text = str(value).strip().lstrip("#")
        if text.casefold() == "last":
            return "last"
        if text.isdigit():
            return int(text)
        self.fail(f"'{value}' is not a session ID (use a number or 'last').", param, ctx)


SESSION_REF = SessionRef()


def _session_summary(session: Dict[str, Any]) -> str:
    start = parse_utc_to_local(session.get("start_time") or session.get("start") or "")
    when = start.strftime("%a %d %b %H:%M") if start else "-"
    project = session.get("project") or session.get("p") or ""
    duration = session.get("duration_minutes") or session.get("elapsed") or 0
    return (
        f"#[autumn.id]{session.get('id')}[/] [autumn.time]{when}[/] "
        f"[autumn.duration]{format_duration_minutes(duration)}[/] "
        f"[autumn.project]{project}[/]"
    )


def _recent_sessions(client: APIClient, limit: int = 10) -> List[Dict[str, Any]]:
    return client.search_sessions(limit=limit, ordering="newest").get("sessions", [])


def _resolve_session_ref(client: APIClient, ref: Any, *, action: str) -> int:
    """Turn an ID, ``last`` or nothing (interactive pick) into a session ID."""
    if isinstance(ref, int):
        return ref

    if ref == "last":
        recent = _recent_sessions(client, limit=1)
        if not recent:
            raise APIError("No saved sessions found.")
        console.print(f"[autumn.muted]Last session:[/] {_session_summary(recent[0])}")
        return int(recent[0]["id"])

    if not sys.stdin.isatty():
        raise click.UsageError(
            f"Give the session to {action}: an ID (see `autumn log --ids`) or 'last'."
        )
    recent = _recent_sessions(client)
    if not recent:
        raise APIError("No saved sessions found.")
    console.print(f"[autumn.label]Recent sessions[/] (choose one to {action}):")
    for index, session in enumerate(recent, start=1):
        console.print(f"  [dim]{index})[/] {_session_summary(session)}")
    choice = click.prompt(
        f"Enter number (1-{len(recent)})",
        type=click.IntRange(1, len(recent)),
    )
    return int(recent[choice - 1]["id"])


def _resolve_read_filters(
    client: APIClient,
    *,
    project: Optional[str],
    subprojects: tuple,
    exclude: tuple,
    context: Optional[str],
    tag: tuple,
    pick: bool,
) -> Dict[str, Any]:
    """Resolve the shared project/context/tag filters used by log commands."""
    meta = client.get_discovery_meta(ttl_seconds=300, refresh=False)

    if pick:
        from ..utils.pickers import pick_project, pick_context, pick_tag

        if not project:
            project = pick_project(client) or project
        if not context:
            context = pick_context(client) or context
        if not tag:
            chosen = pick_tag(client)
            tag = (chosen,) if chosen else tag

    if subprojects and not project:
        raise click.UsageError("--subproject needs --project.")

    ctx_res = resolve_context_param(context=context, contexts=meta.get("contexts", []))
    tag_resolved, _tag_warnings = resolve_tag_params(
        tags=list(tag) if tag else None, known_tags=meta.get("tags", [])
    )
    resolved_project = resolve_project_name(client, project) if project else None

    resolved_subs = None
    if subprojects and resolved_project:
        try:
            known = client.list_subprojects(resolved_project).get("subprojects", [])
        except APIError:
            known = []
        resolved_subs, sub_warnings = resolve_subproject_params(
            subprojects=subprojects, known_subprojects=known, project=resolved_project
        )
        for warning in sub_warnings:
            console.print(f"[autumn.warn]Warning:[/] {warning}")

    return {
        "project": resolved_project,
        "context": ctx_res.value,
        "tags": tag_resolved or None,
        "exclude": _resolve_excluded_projects(client, exclude),
        "subprojects": resolved_subs or None,
    }


def _print_sessions(
    rows: List[Dict[str, Any]],
    *,
    count: int,
    raw: bool,
    show_ids: bool,
    max_note_length: Optional[int],
    search: Optional[str],
    related: bool,
    related_status: Optional[str],
) -> None:
    """Print a log; meaning-based matches follow under their own heading."""
    direct = [row for row in rows if row.get("match") != "related"]
    related_rows = [row for row in rows if row.get("match") == "related"]

    def _print(group: List[Dict[str, Any]]) -> None:
        rendered = render_sessions_list(
            group,
            markdown_notes=not raw,
            show_ids=show_ids,
            max_note_length=max_note_length,
        )
        for item in rendered if isinstance(rendered, list) else [rendered]:
            console.print(item)

    console.print(f"[autumn.label]Sessions:[/] {count}")
    if direct or not related_rows:
        _print(direct)

    if related_rows:
        console.print("")
        console.print(f"[autumn.label]Related by meaning:[/] {len(related_rows)}")
        _print(related_rows)

    if search and related and related_status == "unavailable":
        console.print(
            "[autumn.muted]Related matches were unavailable (they need AI features "
            "and an OpenAI key on your account, or the provider is cooling down).[/]"
        )


class _LogGroup(click.Group):
    """Let `autumn log` take bare words: `autumn log today`, `autumn log Autumn`.

    A period word becomes --period; any other word becomes --project.
    """

    def parse_args(self, ctx: click.Context, args: list) -> list:
        args = list(args)
        value_options = {
            name
            for param in self.params
            if isinstance(param, click.Option) and not param.is_flag and not param.count
            for name in param.opts
        }
        has_project = any(
            arg in ("-p", "--project") or arg.startswith("--project=") for arg in args
        )
        index = 0
        while index < len(args):
            arg = args[index]
            if arg == "--":
                break
            if arg.startswith("-"):
                index += 2 if arg in value_options else 1
                continue
            if arg in self.commands:
                break
            pair = f"{arg} {args[index + 1]}" if index + 1 < len(args) else ""
            if normalize_period(arg):
                args[index:index + 1] = ["--period", arg]
                index += 2
            elif pair and normalize_period(pair):
                args[index:index + 2] = ["--period", pair]
                index += 2
            elif not has_project:
                args[index:index + 1] = ["--project", arg]
                has_project = True
                index += 2
            else:
                break
        return super().parse_args(ctx, args)


_show_ids_option = click.option(
    "--ids", "--show-ids", "show_ids", is_flag=True, help="Show session IDs (for edit/delete)"
)
_raw_option = click.option(
    "--raw/--markdown",
    default=False,
    help="Show raw (single-line) notes instead of Markdown",
)

DEFAULT_MAX_NOTE_LENGTH = 300


def _note_options(fn):
    fn = click.option(
        "--max-note-length", "-m", type=int, default=None, metavar="N",
        help=f"Truncate notes after this many characters (implies --truncate; "
        f"default {DEFAULT_MAX_NOTE_LENGTH}, or config log.max_note_length)",
    )(fn)
    fn = click.option(
        "--truncate/--no-truncate", default=None,
        help="Shorten long notes (default off; set config log.truncate_notes to change)",
    )(fn)
    return fn


def _config_bool(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "y", "on")
    return bool(value)


def _note_limit(truncate: Optional[bool], max_note_length: Optional[int]) -> Optional[int]:
    """Resolve --truncate/--no-truncate and -m against the log.* config keys."""
    from ..config import get_config_value

    if truncate is None:
        truncate = max_note_length is not None or _config_bool(
            get_config_value("log.truncate_notes", False)
        )
    if not truncate:
        return None
    if max_note_length is not None:
        if max_note_length < 1:
            raise click.BadParameter("must be at least 1", param_hint="'-m' / '--max-note-length'")
        return max_note_length
    try:
        configured = int(get_config_value("log.max_note_length", DEFAULT_MAX_NOTE_LENGTH))
    except (TypeError, ValueError):
        configured = DEFAULT_MAX_NOTE_LENGTH
    return configured if configured > 0 else DEFAULT_MAX_NOTE_LENGTH


def _filter_options(fn):
    fn = click.option("--pick", is_flag=True, help="Interactively pick project/context/tags if not provided")(fn)
    fn = click.option("--tag", "-t", multiple=True, help="Filter by tag (repeatable)")(fn)
    fn = click.option("--context", "-c", help="Filter by context (name or id)")(fn)
    fn = click.option("--exclude", "-x", multiple=True, help="Exclude project by name (repeatable)")(fn)
    fn = click.option(
        "--subproject", "-s", "subprojects", multiple=True,
        help="Only sessions with this subproject (repeatable; needs -p)",
    )(fn)
    fn = click.option("--project", "-p", help="Filter by project (name, alias or unique part)")(fn)
    return fn


@click.group(cls=_LogGroup, invoke_without_command=True)
@click.pass_context
@period_option(help_suffix=". Also accepted as a bare word: `autumn log today`")
@_filter_options
@date_range_options
@search_options("sessions")
@_raw_option
@_note_options
@_show_ids_option
def log(
    ctx: click.Context,
    period: Optional[str],
    project: Optional[str],
    subprojects: tuple,
    exclude: tuple,
    context: Optional[str],
    tag: tuple,
    pick: bool,
    start_date: Optional[str],
    end_date: Optional[str],
    search: Optional[str],
    related: bool,
    raw: bool,
    truncate: Optional[bool],
    max_note_length: Optional[int],
    show_ids: bool,
):
    """Show saved sessions (default: the last 7 days).

    \b
    Examples:
      autumn log                     # last 7 days
      autumn log today
      autumn log Autumn month        # bare words: period and/or project
      autumn log --since monday --ids
      autumn log -m 120              # shorten notes over 120 characters
      autumn log -q "login bug"      # search all time
      autumn log -q "auth" --related # also match by meaning
    """
    if ctx.invoked_subcommand is not None:
        return
    note_limit = _note_limit(truncate, max_note_length)
    try:
        client = APIClient()
        filters = _resolve_read_filters(
            client,
            project=project,
            subprojects=subprojects,
            exclude=exclude,
            context=context,
            tag=tag,
            pick=pick,
        )

        # Searches default to all time; a plain log to the last week.
        if not start_date and not end_date:
            from ..utils.periods import period_to_dates

            start_date, end_date = period_to_dates(period or ("all" if search else "week"))

        extra: Dict[str, Any] = {}
        if search:
            extra.update(search=search, related=related)
        if filters["subprojects"]:
            extra["subprojects"] = filters["subprojects"]
        result = client.log_activity(
            period=None,
            project=filters["project"],
            start_date=start_date,
            end_date=end_date,
            context=filters["context"],
            tags=filters["tags"],
            exclude=filters["exclude"],
            **extra,
        )

        logs = result.get("logs", [])
        _print_sessions(
            logs,
            count=result.get("count", len(logs)),
            raw=raw,
            show_ids=show_ids,
            max_note_length=note_limit,
            search=search,
            related=related,
            related_status=result.get("related_status"),
        )
    except APIError as e:
        console.print(f"[autumn.err]Error:[/] {e}")
        raise click.Abort()


@log.command("search")
@_filter_options
@date_range_options
@search_options("sessions")
@click.option("--note-snippet", "-n", help="Only sessions whose note contains this text")
@click.option("--active/--no-active", default=False, help="Search running timers instead")
@click.option("--newest", is_flag=True, help="Order by end time instead of relevance")
@click.option("--limit", type=int, help="Limit number of results")
@click.option("--offset", type=int, help="Offset for pagination")
@_raw_option
@_note_options
@_show_ids_option
def log_search(
    project: Optional[str],
    subprojects: tuple,
    exclude: tuple,
    context: Optional[str],
    tag: tuple,
    pick: bool,
    start_date: Optional[str],
    end_date: Optional[str],
    search: Optional[str],
    related: bool,
    note_snippet: Optional[str],
    active: bool,
    newest: bool,
    limit: Optional[int],
    offset: Optional[int],
    raw: bool,
    truncate: Optional[bool],
    max_note_length: Optional[int],
    show_ids: bool,
):
    """Search sessions across all time, with paging.

    \b
    Examples:
      autumn log search -q "deploy"
      autumn log search -q "deploy" --related --limit 20
      autumn log search -p Autumn -n "TODO"
    """
    note_limit = _note_limit(truncate, max_note_length)
    try:
        client = APIClient()
        filters = _resolve_read_filters(
            client,
            project=project,
            subprojects=subprojects,
            exclude=exclude,
            context=context,
            tag=tag,
            pick=pick,
        )

        extra: Dict[str, Any] = {}
        if search:
            extra.update(search=search, related=related)
        if newest:
            extra["ordering"] = "newest"
        if filters["subprojects"]:
            extra["subprojects"] = filters["subprojects"]
        result = client.search_sessions(
            project=filters["project"],
            start_date=start_date,
            end_date=end_date,
            note_snippet=note_snippet,
            active=active,
            limit=limit,
            offset=offset,
            context=filters["context"],
            tags=filters["tags"],
            exclude=filters["exclude"],
            **extra,
        )

        sessions_list = result.get("sessions", [])
        _print_sessions(
            sessions_list,
            count=result.get("count", len(sessions_list)),
            raw=raw,
            show_ids=show_ids,
            max_note_length=note_limit,
            search=search,
            related=related,
            related_status=result.get("related_status"),
        )
    except APIError as e:
        console.print(f"[autumn.err]Error:[/] {e}")
        raise click.Abort()


def _parse_duration_arg(raw: Optional[str], hint: str) -> Optional[int]:
    if raw is None:
        return None
    try:
        return parse_duration_to_seconds(raw)
    except ValueError as error:
        raise click.BadParameter(str(error), param_hint=hint) from None


def _parse_on_date(raw: Optional[str]):
    if raw is None:
        return None
    try:
        return datetime.strptime(parse_date_arg(raw), "%Y-%m-%d").date()
    except ValueError as error:
        raise click.BadParameter(str(error), param_hint="--on") from None


@click.command()
@click.argument("project", required=False)
@click.argument("duration", required=False)
@click.option("--subprojects", "-s", multiple=True, help="Subproject names (can specify multiple)")
@click.option(
    "--split",
    help='Set the subproject split (for example "api=60,frontend=40" or "even")',
)
@click.option("--start", help="Start: 14:00, 9am, now-2h, 2026-01-11 22:18")
@click.option("--end", help="End (default: now when only a start or duration is given)")
@click.option("--for", "for_", help="Duration instead of positional DURATION (e.g. 45m, 1h30m)")
@click.option("--on", "on_date", help="Day for time-only --start/--end (yesterday, monday, 2026-01-11)")
@click.option("--note", "-n", help="Note for the session")
@click.option("--pick", is_flag=True, help="Interactively pick project/subprojects")
def track(
    project: Optional[str],
    duration: Optional[str],
    subprojects: tuple,
    split: Optional[str],
    start: Optional[str],
    end: Optional[str],
    for_: Optional[str],
    on_date: Optional[str],
    note: Optional[str],
    pick: bool,
):
    """Log time you already spent (a completed session).

    Give any two of a start, an end and a duration; a duration alone
    ends now. Time-only values are on today unless --on says otherwise.

    \b
    Examples:
      autumn track Autumn 45m -n "Code review"   # ended just now
      autumn track Autumn --start 9:00 --end 11:30
      autumn track Autumn 2h --start 14:00
      autumn track Autumn --on yesterday --start 9am --end 5pm
    """
    try:
        split_spec = parse_split(split)
    except ValueError as error:
        raise click.BadParameter(str(error), param_hint="--split") from None

    if duration is not None and for_ is not None:
        raise click.UsageError("Give the duration once: either DURATION or --for.")
    duration_seconds = _parse_duration_arg(duration or for_, "DURATION")
    anchor = _parse_on_date(on_date)

    try:
        start_iso, end_iso = _resolve_track_window(start, end, duration_seconds, anchor)

        client = APIClient()

        # Interactive picker for project if --pick or no project provided
        if pick or not project:
            from ..utils.pickers import pick_project, pick_subproject

            # Only show active/paused projects for tracking time
            picked_project = pick_project(client, statuses=["active", "paused"])
            if not picked_project:
                console.print("[autumn.warn]No project selected.[/]")
                raise click.Abort()
            project = picked_project

            # Also offer to pick subprojects if --pick was explicit
            if pick and not subprojects:
                picked_sub = pick_subproject(client, project)
                if picked_sub:
                    subprojects = (picked_sub,)

        resolved_project = resolve_project_name(client, project)

        subprojects_list, allocations, sub_warnings = resolve_split_selection(
            client, resolved_project, subprojects, split_spec
        )
        for warning in sub_warnings:
            console.print(f"[autumn.warn]Warning:[/] {warning}")

        track_kwargs = {"allocations": allocations} if allocations is not None else {}
        result = client.track_session(
            resolved_project,
            start_iso,
            end_iso,
            subprojects_list,
            note,
            **track_kwargs,
        )

        if result.get("ok"):
            session = result.get("session", {})
            minutes = session.get("elapsed") or session.get("duration_minutes", 0)
            console.print("[autumn.ok]Session tracked.[/]")
            console.print(
                f"Tracked [autumn.project]{resolved_project}[/] "
                f"{format_subprojects_bracketed(session)}, "
                f"[autumn.duration]{format_duration_minutes(minutes)}[/] "
                f"[autumn.muted]([/][autumn.time]{start_iso[:16]}[/] [autumn.muted]to[/] "
                f"[autumn.time]{end_iso[11:16]}[/][autumn.muted])[/]"
            )
            console.print(_format_session_id_line(session.get("id")))

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


def _parse_point(raw: str, anchor) -> Tuple[datetime, bool]:
    """Parse a start/end value; time-only values land on ``anchor``'s date."""
    time_only = _parse_time_only(raw)
    if time_only is not None:
        return datetime.combine(anchor, time_only), True
    return parse_user_datetime(raw).dt, False


def _resolve_track_window(
    start_raw: Optional[str],
    end_raw: Optional[str],
    duration_seconds: Optional[int],
    anchor=None,
) -> Tuple[str, str]:
    """Work out a session's start and end from any two of start/end/duration.

    Time-only inputs (``15:00``) are placed on ``anchor`` (default today)
    rather than rolling into tomorrow; if both are time-only and the end is
    earlier, the range crosses midnight. A lone duration or start ends now.
    """
    now_local = datetime.now().astimezone().replace(tzinfo=None)
    day = anchor or now_local.date()
    duration = timedelta(seconds=duration_seconds) if duration_seconds else None

    if start_raw and end_raw and duration:
        raise click.UsageError("Give at most two of --start, --end and a duration.")

    start_dt = end_dt = None
    start_time_only = end_time_only = False
    if start_raw:
        start_dt, start_time_only = _parse_point(start_raw, day)
    if end_raw:
        end_dt, end_time_only = _parse_point(end_raw, day)

    if start_dt and end_dt:
        if start_time_only and end_time_only and end_dt < start_dt:
            end_dt += timedelta(days=1)
    elif start_dt and duration:
        end_dt = start_dt + duration
    elif end_dt and duration:
        start_dt = end_dt - duration
    elif duration:
        if anchor is not None:
            raise click.UsageError("With --on, also give --start or --end.")
        end_dt = now_local
        start_dt = now_local - duration
    elif start_dt:
        if anchor is not None and anchor != now_local.date():
            raise click.UsageError("Add --end or a duration for a session on another day.")
        end_dt = now_local
    elif end_dt:
        raise click.UsageError("Add --start or a duration to go with --end.")
    else:
        raise click.UsageError(
            "Say how long: `autumn track PROJECT 45m`, or give --start and --end."
        )

    if end_dt <= start_dt:
        raise click.UsageError("The session must end after it starts.")
    return format_server_datetime(start_dt), format_server_datetime(end_dt)


def _normalize_track_window(start_raw: str, end_raw: str) -> tuple[str, str]:
    """Normalize track start/end with same-day semantics for time-only inputs."""
    return _resolve_track_window(start_raw, end_raw, None)


def _parse_time_only(raw: str):
    """Parse time-only inputs like `15:00`, `15:00:05`, `3:00PM`, `3pm`, `3 pm`."""
    s = (raw or "").strip().replace(" ", "")
    if not s:
        return None

    for fmt in ("%H:%M:%S", "%H:%M", "%I:%M%p", "%I%p"):
        try:
            return datetime.strptime(s, fmt).time()
        except ValueError:
            continue

    return None


@click.command("edit")
@click.argument("session_id", metavar="[SESSION]", type=SESSION_REF, required=False)
@click.option("-p", "--project", help="Change the project")
@click.option("-s", "--subproject", "--subprojects", "subprojects", multiple=True, help="Change subprojects (can use multiple times)")
@click.option(
    "--split",
    help='Set the subproject split (for example "api=60,frontend=40" or "even")',
)
@click.option("--start", help="Change start time (9:30 keeps the session's day; or now-1h, 2026-01-15 09:00)")
@click.option("--end", help="Change end time (same formats as --start)")
@click.option("--for", "for_", help="Set the length; the end moves to start + duration (e.g. 45m)")
@click.option("-n", "--note", help="Replace the note")
@click.option("-a", "--append-note", help="Append text to the existing note")
@click.option("--pick", is_flag=True, help="Interactively pick project/subprojects")
def edit_session(
    session_id: Any,
    project: Optional[str],
    subprojects: tuple,
    split: Optional[str],
    start: Optional[str],
    end: Optional[str],
    for_: Optional[str],
    note: Optional[str],
    append_note: Optional[str],
    pick: bool,
):
    """Edit an existing completed session in place.

    The session keeps the same ID after editing. SESSION is an ID, 'last',
    or omitted to choose from your recent sessions.

    To append to a live timer instead, use `autumn note TEXT`.

    \b
    Examples:
      autumn edit last -a "Added follow-up context"
      autumn edit 123 --note "Updated note"
      autumn edit 123 -p "New Project"
      autumn edit 123 --start 9:00 --end 10:30
      autumn edit 123 --for 45m
      autumn edit 123 -s Frontend -s Backend
    """
    try:
        split_spec = parse_split(split)
    except ValueError as error:
        raise click.BadParameter(str(error), param_hint="--split") from None

    if note is not None and append_note is not None:
        raise click.UsageError("Use either --note or --append-note, not both.")
    if for_ is not None and end is not None:
        raise click.UsageError("Use either --end or --for, not both.")
    if append_note is not None:
        append_note = append_note.strip()
        if not append_note:
            raise click.BadParameter(
                "Appended note text cannot be empty.", param_hint="--append-note"
            )
    duration_seconds = _parse_duration_arg(for_, "--for")

    try:
        client = APIClient()
        session_id = _resolve_session_ref(client, session_id, action="edit")

        # Handle project selection
        resolved_project = None
        if pick and not project:
            from ..utils.pickers import pick_project
            project = pick_project(client, label="new project")

        if project:
            resolved_project = resolve_project_name(client, project)

        # Handle subproject selection
        subprojects_list = None
        if pick and not subprojects and resolved_project:
            from ..utils.pickers import pick_subproject
            picked_sub = pick_subproject(client, resolved_project, label="new subproject")
            if picked_sub:
                subprojects = (picked_sub,)

        current: Optional[Dict[str, Any]] = None

        def _current() -> Dict[str, Any]:
            nonlocal current
            if current is None:
                current = client.get_session(session_id).get("session", {})
            return current

        allocations = None
        if split_spec is not None:
            effective_project = resolved_project
            if not effective_project:
                effective_project = _current().get("p") or _current().get("project")
            if not effective_project:
                raise APIError("Could not determine the session's project.")
            subprojects_list, allocations, sub_warnings = resolve_split_selection(
                client, effective_project, subprojects, split_spec
            )
            for warning in sub_warnings:
                console.print(f"[autumn.warn]Warning:[/] {warning}")
        elif subprojects and resolved_project:
            try:
                known_subs_res = client.list_subprojects(resolved_project)
                known_subs = known_subs_res.get("subprojects", []) if isinstance(known_subs_res, dict) else known_subs_res
            except APIError:
                known_subs = []
            resolved_subs, sub_warnings = resolve_subproject_params(
                subprojects=subprojects, known_subprojects=known_subs, project=resolved_project
            )
            for w in sub_warnings:
                console.print(f"[autumn.warn]Warning:[/] {w}")
            subprojects_list = resolved_subs if resolved_subs else None
        elif subprojects:
            # If subprojects provided but no project change, pass them through
            subprojects_list = list(subprojects)

        start_iso, end_iso = _edit_window(start, end, duration_seconds, _current)

        edit_kwargs = {"allocations": allocations} if allocations is not None else {}
        result = client.edit_session(
            session_id=session_id,
            project=resolved_project,
            subprojects=subprojects_list,
            start=start_iso,
            end=end_iso,
            note=note,
            append_note=append_note,
            **edit_kwargs,
        )

        if result.get("ok"):
            session = result.get("session", {})
            updated_id = session.get("id", session_id)
            proj_name = session.get("p") or session.get("project")
            duration = session.get("elapsed") or session.get("dur") or 0

            console.print("[autumn.ok]Session updated.[/]")
            console.print(
                f"[autumn.label]Session ID:[/] [autumn.id]{updated_id}[/] "
                "[autumn.muted](unchanged)[/]"
            )
            console.print(f"[autumn.label]Project:[/] [autumn.project]{proj_name}[/]")
            console.print(f"[autumn.label]Duration:[/] [autumn.duration]{format_duration_minutes(duration)}[/]")

            if session.get("subs"):
                subs_str = ", ".join(session.get("subs", []))
                console.print(f"[autumn.label]Subprojects:[/] [autumn.subproject]{subs_str}[/]")
        else:
            console.print(f"[autumn.err]Error:[/] {result.get('error', 'Unknown error')}")
            raise click.Abort()

    except APIError as e:
        console.print(f"[autumn.err]Error:[/] {e}")
        raise click.Abort()
    except ValueError as e:
        console.print(f"[autumn.err]Error:[/] Invalid date format - {e}")
        raise click.Abort()


def _edit_window(
    start: Optional[str],
    end: Optional[str],
    duration_seconds: Optional[int],
    current,
) -> Tuple[Optional[str], Optional[str]]:
    """Normalize edit times; time-only values keep the session's own day."""
    needs_current = duration_seconds is not None or any(
        value is not None and _parse_time_only(value) is not None for value in (start, end)
    )
    if not needs_current:
        return (
            _normalize_datetime(start) if start else None,
            _normalize_datetime(end) if end else None,
        )

    session = current()
    current_start = parse_utc_to_local(session.get("start") or "")
    if current_start is None:
        raise APIError("Could not read the session's current start time.")
    current_start = current_start.replace(tzinfo=None)
    day = current_start.date()

    start_dt = _parse_point(start, day)[0] if start else None
    end_dt, end_time_only = _parse_point(end, day) if end else (None, False)
    effective_start = start_dt or current_start
    if duration_seconds is not None:
        end_dt = effective_start + timedelta(seconds=duration_seconds)
    elif end_dt is not None and end_time_only and end_dt <= effective_start:
        end_dt += timedelta(days=1)

    return (
        format_server_datetime(start_dt) if start_dt else None,
        format_server_datetime(end_dt) if end_dt else None,
    )


@click.command("delete-session")
@click.argument("session_id", metavar="[SESSION]", type=SESSION_REF, required=False)
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
def delete_session(session_id: Any, yes: bool):
    """Delete a saved session by ID (or 'last').

    This is for saved session logs. To discard a running timer, use
    `autumn discard`.
    """
    try:
        client = APIClient()
        session_id = _resolve_session_ref(client, session_id, action="delete")
        if not yes and not click.confirm(
            f"Delete saved session #{session_id}? This cannot be undone."
        ):
            console.print("[autumn.muted]Cancelled.[/]")
            return

        result = client.delete_session(session_id)

        if result.get("ok", True):
            deleted_id = result.get("deleted", session_id)
            console.print(
                f"[autumn.warn]Session deleted[/] (Session ID: {deleted_id})",
                highlight=True,
            )
        else:
            raise click.ClickException(result.get("error", "Unknown error"))
    except APIError as e:
        console.print(f"[autumn.err]Error:[/] {e}")
        raise click.Abort()
