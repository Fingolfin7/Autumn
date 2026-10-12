"""Commitment management commands."""

from __future__ import annotations

from typing import Any, Optional

import click
from rich.table import Table

from ..api_client import APIClient, APIError
from ..utils.console import console
from ..utils.duration_parse import parse_duration_to_seconds
from ..utils.resolvers import resolve_project_name, resolve_project_param


AGGREGATION_TYPES = ["project", "subproject", "context", "tag"]
COMMITMENT_TYPES = ["time", "sessions"]
PERIODS = ["daily", "weekly", "fortnightly", "monthly", "quarterly", "yearly"]
PERIOD_ALIASES = {
    "day": "daily",
    "d": "daily",
    "week": "weekly",
    "w": "weekly",
    "fortnight": "fortnightly",
    "2w": "fortnightly",
    "month": "monthly",
    "m": "monthly",
    "quarter": "quarterly",
    "q": "quarterly",
    "year": "yearly",
    "y": "yearly",
}


class CommitmentPeriod(click.ParamType):
    """A commitment period; accepts ``week`` as well as ``weekly``."""

    name = "PERIOD"

    def convert(self, value: Any, param: Optional[click.Parameter], ctx: Optional[click.Context]) -> str:
        text = str(value).strip().lower()
        text = PERIOD_ALIASES.get(text, text)
        if text not in PERIODS:
            self.fail(
                f"'{value}' is not a period. Use day, week, fortnight, month, quarter or year.",
                param,
                ctx,
            )
        return text


COMMITMENT_PERIOD = CommitmentPeriod()

PERIOD_LABELS = {
    "daily": "day",
    "weekly": "week",
    "fortnightly": "2 weeks",
    "monthly": "month",
    "quarterly": "quarter",
    "yearly": "year",
}


def _minutes_or_sessions(
    raw: str, commitment_type: str, label: str, *, allow_negative: bool = False
) -> int:
    """Parse a time duration to minutes, or validate a session count."""
    if commitment_type == "sessions":
        try:
            value = int(raw)
        except (TypeError, ValueError):
            raise click.BadParameter(f"{label} must be a whole number of sessions.")
        if value <= 0 and not (allow_negative and value < 0):
            raise click.BadParameter(f"{label} must be greater than zero.")
        return value

    negative = str(raw).strip().startswith("-")
    try:
        seconds = parse_duration_to_seconds(str(raw).strip()[1:] if negative else raw)
    except ValueError as exc:
        raise click.BadParameter(f"Invalid duration for {label}: {exc}")
    if seconds % 60:
        raise click.BadParameter(f"{label} must resolve to whole minutes.")
    minutes = seconds // 60
    if negative:
        if not allow_negative:
            raise click.BadParameter(f"{label} must be greater than zero.")
        return -minutes
    return minutes


def _time_text(value: Any) -> str:
    try:
        minutes = int(value or 0)
    except (TypeError, ValueError):
        return str(value or 0)
    if minutes and minutes % 60 == 0:
        return f"{minutes // 60}h"
    return f"{minutes}m"


def _amount_text(value: Any, commitment_type: str) -> str:
    if commitment_type == "sessions":
        return f"{value} sessions"
    return _time_text(value)


def _status_markup(status: str) -> str:
    style = {
        "complete": "autumn.ok",
        "approaching": "autumn.ok",
        "on-track": "autumn.ok",
        "warning": "autumn.warn",
        "behind": "autumn.err",
    }.get(status, "autumn.muted")
    return f"[{style}]{status}[/]"


def _pending_note(pending_revision: Any) -> str:
    if not isinstance(pending_revision, dict):
        return ""
    changes = pending_revision.get("changes") or {}
    summaries = []
    for field, value in changes.items():
        label = str(field).replace("_", "-")
        if isinstance(value, (dict, list)):
            summaries.append(label)
        else:
            summaries.append(f"{label}={value}")
    effective_from = str(pending_revision.get("effective_from") or "?")[:10]
    fields = ", ".join(summaries) or "changes"
    return f"[autumn.warn](pending: {fields} from {effective_from})[/]"


def _resolve_commitment_id(client: APIClient, target: str) -> int:
    """Accept a commitment ID (``12`` or ``#12``) or its target's name."""
    target = str(target).strip().lstrip("#")
    if target.isdigit():
        return int(target)
    items = client.list_commitments(active=None, compact=True).get("commitments", [])
    # Target names resolve like project names: alias, any case, unique part.
    names = [{"name": item.get("name")} for item in items if item.get("name")]
    resolved = resolve_project_param(project=target, projects=names, partial=True)
    name = resolved.value if resolved.warning is None else target
    matches = [
        item
        for item in items
        if str(item.get("name") or "").casefold() == str(name).casefold()
    ]
    if not matches:
        raise APIError(
            f"No commitment for '{target}'. See `autumn cmt list` for IDs and targets."
        )
    if len(matches) > 1:
        raise APIError(
            f"Commitment target is ambiguous: {target}. Use the commitment ID."
        )
    return int(matches[0]["id"])


def _resolve_project(client: APIClient, name: str) -> str:
    return resolve_project_name(client, name)


def _new_payload(
    client: APIClient,
    *,
    aggregation_type: str,
    target: str,
    target_value: Optional[str],
    commitment_type: str,
    period: Optional[str],
    start_date: Optional[str],
    timezone: Optional[str],
    no_banking: Optional[bool],
    max_balance: Optional[str],
    min_balance: Optional[str],
    include: tuple[str, ...],
    exclude: tuple[str, ...],
    editing: bool = False,
) -> dict[str, Any]:
    """Build a create/patch body from Click option values."""
    if (include or exclude) and aggregation_type not in {"context", "tag"}:
        raise click.UsageError(
            "--include/--exclude currently apply only to context or tag commitments."
        )

    data: dict[str, Any] = {}
    if not editing:
        data["aggregation_type"] = aggregation_type
        if aggregation_type == "subproject":
            project, separator, subproject = target.partition("/")
            if not separator or not project.strip() or not subproject.strip():
                raise click.UsageError('A subproject target must be written as "Project/Subproject".')
            data["project"] = _resolve_project(client, project.strip())
            data["target"] = subproject.strip()
        elif aggregation_type == "project":
            data["target"] = _resolve_project(client, target)
        else:
            data["target"] = target

    if target_value is not None:
        data["target_value"] = _minutes_or_sessions(
            target_value, commitment_type, "target value"
        )
    if commitment_type is not None:
        data["commitment_type"] = commitment_type
    if period is not None:
        data["period"] = period
    if start_date is not None:
        data["start_date"] = start_date
    if timezone is not None:
        data["timezone"] = timezone
    if no_banking is not None:
        data["banking_enabled"] = not no_banking
    if max_balance is not None:
        data["max_balance"] = _minutes_or_sessions(max_balance, commitment_type, "max balance")
    if min_balance is not None:
        data["min_balance"] = _minutes_or_sessions(
            min_balance, commitment_type, "min balance", allow_negative=True
        )
    if include:
        data["include_projects"] = list(include)
    if exclude:
        data["exclude_projects"] = list(exclude)
    return data


@click.group(invoke_without_command=True)
@click.pass_context
def commitments(ctx: click.Context) -> None:
    """Create, inspect, and manage recurring commitments."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(commitments_list)


@commitments.command("list")
@click.option("--all", "include_inactive", is_flag=True, help="Include inactive commitments")
@click.option("--json", "json_out", is_flag=True, help="Output raw JSON")
@click.option("--streak", is_flag=True, help="Include streak information")
def commitments_list(include_inactive: bool, json_out: bool, streak: bool) -> None:
    """List commitments and their current progress."""
    try:
        result = APIClient().list_commitments(
            active=None if include_inactive else True, streak=streak, compact=True
        )
        if json_out:
            console.print_json(data=result)
            return
        items = result.get("commitments", [])
        if not items:
            console.print("[autumn.muted]No commitments found.[/]")
            return

        table = Table(title="Commitments", header_style="autumn.title", padding=(0, 1))
        table.add_column("ID", style="autumn.id", justify="right")
        table.add_column("Target")
        table.add_column("Goal", style="autumn.duration", justify="right")
        table.add_column("Progress", justify="right")
        table.add_column("Balance", justify="right")
        table.add_column("Active", justify="center")
        if streak:
            table.add_column("Streak", justify="right")

        for item in items:
            ctype = item.get("type", "time")
            period = item.get("period", "")
            goal = f"{_amount_text(item.get('target', 0), ctype)}/{PERIOD_LABELS.get(period, period)}"
            progress = item.get("prog") or {}
            actual = _amount_text(progress.get("actual", 0), ctype)
            pct = progress.get("pct", 0)
            progress_text = f"{actual} ({pct}%) {_status_markup(progress.get('status', ''))}"
            bal = item.get("bal", 0)
            try:
                signed = f"{int(bal):+d}"
            except (TypeError, ValueError):
                signed = str(bal)
            balance = _amount_text(signed, ctype)
            target_text = (
                f"[autumn.project]{item.get('name', '')}[/] "
                f"[autumn.muted]({item.get('agg', '')})[/]"
            )
            pending_note = _pending_note(item.get("pending_revision"))
            if pending_note:
                target_text = f"{target_text}\n{pending_note}"
            row = [
                str(item.get("id", "-")),
                target_text,
                goal,
                progress_text,
                balance,
                "[autumn.ok]yes[/]" if item.get("active") else "[autumn.muted]no[/]",
            ]
            if streak:
                streak_value = item.get("streak", "-")
                if isinstance(streak_value, dict):
                    streak_value = streak_value.get("current", streak_value.get("days", "-"))
                row.append(str(streak_value))
            table.add_row(*row)
        console.print(table)
    except APIError as exc:
        console.print(f"[autumn.err]Error:[/] {exc}")
        raise click.Abort()


def _commitment_type(commitment_type: Optional[str], count_sessions: bool) -> Optional[str]:
    if count_sessions:
        if commitment_type not in (None, "sessions"):
            raise click.UsageError("--sessions conflicts with --commitment-type time.")
        return "sessions"
    return commitment_type


def _goal(goal: Optional[str], target_value: Optional[str]) -> Optional[str]:
    if goal is not None and target_value is not None and goal != target_value:
        raise click.UsageError("Give the goal once: as GOAL or with --target-value.")
    return goal if goal is not None else target_value


@commitments.command("show")
@click.argument("commitment")
def commitments_show(commitment: str) -> None:
    """Show full commitment details (by ID or target name)."""
    try:
        client = APIClient()
        commitment_id = _resolve_commitment_id(client, commitment)
        result = client.get_commitment(commitment_id)
        item = result.get("commitment", {})
        ctype = item.get("commitment_type", "time")
        progress = item.get("progress", {})
        console.print(f"[autumn.title]Commitment #[/] [autumn.id]{item.get('id', commitment_id)}[/]")
        console.print(f"[autumn.label]Target:[/] [autumn.project]{item.get('target_name', '')}[/] ({item.get('aggregation_type', '')})")
        console.print(f"[autumn.label]Goal:[/] {_amount_text(item.get('target', 0), ctype)}/{item.get('period', '')}")
        console.print(f"[autumn.label]Progress:[/] {_amount_text(progress.get('actual', 0), ctype)} / {_amount_text(progress.get('target', item.get('target', 0)), ctype)} ({progress.get('percentage', 0)}%) {_status_markup(progress.get('status', ''))}")
        console.print(f"[autumn.label]Balance:[/] {_amount_text(item.get('balance', 0), ctype)}")
        console.print(f"[autumn.label]Period window:[/] {progress.get('effective_period_start') or progress.get('period_start', '-')} to {progress.get('period_end', '-')}")
        console.print(f"[autumn.label]Banking:[/] {'enabled' if item.get('banking_enabled') else 'disabled'}")
        console.print(f"[autumn.label]Active:[/] {'yes' if item.get('active') else 'no'}")
        pending_note = _pending_note(item.get("pending_revision"))
        if pending_note:
            console.print(pending_note)
        rules = item.get("rules") or []
        console.print("[autumn.label]Rules:[/]")
        if rules:
            for rule in rules:
                console.print(f"  - {rule}")
        else:
            console.print("  [autumn.muted]None[/]")
        if "streak" in result:
            console.print(f"[autumn.label]Streak:[/] {result['streak']}")
    except APIError as exc:
        console.print(f"[autumn.err]Error:[/] {exc}")
        raise click.Abort()


def _commitment_options(required_target_value: bool):
    """Apply shared new/edit options to a Click command."""
    def decorate(fn):
        fn = click.option("--include", multiple=True, help="Include projects (context/tag commitments only; rules are otherwise not yet exposed).")(fn)
        fn = click.option("--exclude", multiple=True, help="Exclude projects (context/tag commitments only; rules are otherwise not yet exposed).")(fn)
        fn = click.option("--min-balance", help="Minimum balance (duration for time commitments)")(fn)
        fn = click.option("--max-balance", help="Maximum balance (duration for time commitments)")(fn)
        fn = click.option("--no-banking", flag_value=True, default=None, help="Disable balance banking")(fn)
        fn = click.option("--timezone", help="IANA timezone name")(fn)
        fn = click.option("--start-date", help="Start date (YYYY-MM-DD)")(fn)
        fn = click.option(
            "--period", "-P", type=COMMITMENT_PERIOD,
            default="weekly" if required_target_value else None,
            show_default=required_target_value,
            help="day, week, fortnight, month, quarter or year",
        )(fn)
        fn = click.option(
            "--sessions", "count_sessions", is_flag=True,
            help="Count sessions instead of time (same as --commitment-type sessions)",
        )(fn)
        fn = click.option("--commitment-type", type=click.Choice(COMMITMENT_TYPES), default=None)(fn)
        fn = click.option("--target-value", help="Goal duration (for time) or session count; same as GOAL")(fn)
        return fn
    return decorate


@commitments.command("new")
@click.option("--type", "aggregation_type", type=click.Choice(AGGREGATION_TYPES), default="project", show_default=True,
              help="What TARGET names")
@click.argument("target")
@click.argument("goal", required=False)
@_commitment_options(required_target_value=True)
def commitments_new(aggregation_type: str, target: str, goal: Optional[str], **options: Any) -> None:
    """Create a recurring goal for TARGET of GOAL per period.

    GOAL is a duration (5h, 90m) or, with --sessions, a session count.
    Subproject targets are written "Project/Subproject".

    \b
    Examples:
      autumn cmt new Autumn 5h                 # 5 hours a week
      autumn cmt new Autumn 30m -P day
      autumn cmt new Autumn 3 --sessions -P week
      autumn cmt new Work 20h --type context
      autumn cmt new "Autumn/Frontend" 2h --type subproject
    """
    options["target_value"] = _goal(goal, options.get("target_value"))
    if options["target_value"] is None:
        raise click.UsageError("Give a goal, e.g. `autumn cmt new Autumn 5h`.")
    options["commitment_type"] = (
        _commitment_type(options.get("commitment_type"), options.pop("count_sessions")) or "time"
    )
    try:
        client = APIClient()
        data = _new_payload(client, aggregation_type=aggregation_type, target=target, editing=False, **options)
        result = client.create_commitment(data)
        item = result.get("commitment", {})
        console.print(f"[autumn.ok]Commitment created:[/] #[autumn.id]{item.get('id', '?')}[/]")
    except APIError as exc:
        console.print(f"[autumn.err]Error:[/] {exc}")
        raise click.Abort()


@commitments.command("edit")
@click.argument("commitment")
@_commitment_options(required_target_value=False)
def commitments_edit(commitment: str, **options: Any) -> None:
    """Change a commitment's goal, period or balance limits.

    COMMITMENT is an ID or target name. The target and aggregation cannot
    change; use `restart` to change type mid-stream.
    """
    try:
        client = APIClient()
        commitment_id = _resolve_commitment_id(client, commitment)
        requested_ctype = _commitment_type(
            options.pop("commitment_type"), options.pop("count_sessions")
        )
        existing: dict[str, Any] = {}
        needs_existing = (
            requested_ctype is None
            and any(options.get(key) is not None for key in ("target_value", "max_balance", "min_balance"))
        ) or options.get("include") or options.get("exclude")
        if needs_existing:
            existing = client.get_commitment(commitment_id).get("commitment", {})
        ctype = requested_ctype or existing.get("commitment_type", "time")
        aggregation_type = existing.get("aggregation_type", "project")
        data = _new_payload(
            client,
            aggregation_type=aggregation_type,
            target="",
            commitment_type=ctype,
            editing=True,
            **options,
        )
        if requested_ctype is None:
            data.pop("commitment_type", None)
        if not data:
            raise click.UsageError("Specify at least one field to update.")
        result = client.update_commitment(commitment_id, data)
        item = result.get("commitment", {})
        console.print(f"[autumn.ok]Commitment updated:[/] #[autumn.id]{item.get('id', commitment_id)}[/]")
    except APIError as exc:
        console.print(f"[autumn.err]Error:[/] {exc}")
        raise click.Abort()


@commitments.command("delete")
@click.argument("commitment")
@click.option("--yes", "-y", "yes", is_flag=True, help="Skip confirmation prompt")
def commitments_delete(commitment: str, yes: bool) -> None:
    """Delete a commitment (by ID or target name)."""
    try:
        client = APIClient()
        commitment_id = _resolve_commitment_id(client, commitment)
        if not yes and not click.confirm(f"Delete commitment {commitment_id}?", default=False):
            console.print("[autumn.muted]Cancelled.[/]")
            return
        client.delete_commitment(commitment_id)
        console.print(f"[autumn.ok]Commitment deleted:[/] #[autumn.id]{commitment_id}[/]")
    except APIError as exc:
        console.print(f"[autumn.err]Error:[/] {exc}")
        raise click.Abort()


@commitments.command("restart")
@click.argument("target")
@click.option(
    "--keep-balance", is_flag=True, help="Carry the current balance into the restart"
)
@click.option(
    "--reset-balance", is_flag=True, help="Reset the balance for the new generation"
)
@click.option("--period", "-P", type=COMMITMENT_PERIOD, help="day, week, fortnight, month, quarter or year")
@click.option("--commitment-type", type=click.Choice(COMMITMENT_TYPES))
@click.option(
    "--target-value",
    help="Goal duration (for time) or session count; required when changing type",
)
@click.option("--start-date", help="Start date (YYYY-MM-DD)")
@click.option("--timezone", help="IANA timezone name")
def commitments_restart(
    target: str,
    keep_balance: bool,
    reset_balance: bool,
    period: Optional[str],
    commitment_type: Optional[str],
    target_value: Optional[str],
    start_date: Optional[str],
    timezone: Optional[str],
) -> None:
    """Restart into a new generation, setting unit-specific target values together."""
    if keep_balance == reset_balance:
        raise click.UsageError(
            "Specify exactly one of --keep-balance or --reset-balance."
        )
    try:
        client = APIClient()
        commitment_id = _resolve_commitment_id(client, target)
        current_ctype: Optional[str] = None
        if (commitment_type is None) != (target_value is None):
            existing = client.get_commitment(commitment_id).get("commitment", {})
            current_ctype = existing.get("commitment_type", "time")
        if (
            commitment_type is not None
            and target_value is None
            and commitment_type != current_ctype
        ):
            raise click.UsageError(
                "--target-value is required when changing --commitment-type; "
                "the stored number cannot be safely reinterpreted in new units."
            )
        parsed_target = None
        if target_value is not None:
            parsed_target = _minutes_or_sessions(
                target_value,
                commitment_type or current_ctype or "time",
                "target value",
            )
        changes = {
            key: value
            for key, value in {
                "period": period,
                "commitment_type": commitment_type,
                "target_value": parsed_target,
                "start_date": start_date,
                "timezone": timezone,
            }.items()
            if value is not None
        }
        result = client.restart_commitment(
            commitment_id,
            keep_balance=keep_balance,
            changes=changes or None,
        )
        item = result.get("commitment", {})
        console.print(
            f"[autumn.ok]Commitment restarted:[/] "
            f"#[autumn.id]{item.get('id', commitment_id)}[/]"
        )
    except APIError as exc:
        console.print(f"[autumn.err]Error:[/] {exc}")
        raise click.Abort()


def _adjust_amount(raw: str) -> int:
    """Whole minutes from ``30``, ``-30``, ``1h30m`` or ``-45m``."""
    text = str(raw).strip()
    try:
        return int(text)
    except ValueError:
        return _minutes_or_sessions(text, "time", "amount", allow_negative=True)


@commitments.command("adjust")
@click.argument("target")
@click.argument("amount_arg", metavar="[AMOUNT]", required=False)
@click.option("--amount", help="Minutes or a duration; negative to remove (e.g. --amount -30m)")
@click.option("--reason", "-r", help="Reason for the adjustment")
def commitments_adjust(
    target: str, amount_arg: Optional[str], amount: Optional[str], reason: Optional[str]
) -> None:
    """Add to (or with a negative amount, take from) a commitment's balance.

    \b
    Examples:
      autumn cmt adjust Autumn 1h -r "Worked offline"
      autumn cmt adjust 12 --amount -30m
    """
    raw_amount = _goal(amount_arg, amount)
    if raw_amount is None:
        raise click.UsageError("Give an amount, e.g. `autumn cmt adjust Autumn 1h`.")
    amount = _adjust_amount(raw_amount)
    try:
        client = APIClient()
        commitment_id = _resolve_commitment_id(client, target)
        result = client.adjust_commitment(
            commitment_id, amount=amount, reason=reason
        )
        adjustment = result.get("adjustment", {})
        console.print(
            f"[autumn.ok]Commitment adjusted.[/] "
            f"[autumn.label]Balance:[/] {_time_text(adjustment.get('balance', 0))}"
        )
    except APIError as exc:
        console.print(f"[autumn.err]Error:[/] {exc}")
        raise click.Abort()
