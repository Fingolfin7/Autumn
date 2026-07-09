"""Commitment management commands."""

from __future__ import annotations

from typing import Any, Optional

import click
from rich.table import Table

from ..api_client import APIClient, APIError
from ..utils.console import console
from ..utils.duration_parse import parse_duration_to_seconds
from ..utils.resolvers import resolve_project_param


AGGREGATION_TYPES = ["project", "subproject", "context", "tag"]
COMMITMENT_TYPES = ["time", "sessions"]
PERIODS = ["daily", "weekly", "fortnightly", "monthly", "quarterly", "yearly"]
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


def _resolve_project(client: APIClient, name: str) -> str:
    projects = client.get_discovery_projects().get("projects", [])
    resolved = resolve_project_param(project=name, projects=projects)
    if resolved.warning:
        console.print(f"[autumn.warn]Warning:[/] {resolved.warning}")
    return resolved.value or name


def _new_payload(
    client: APIClient,
    *,
    aggregation_type: str,
    target: str,
    target_value: Optional[str],
    commitment_type: str,
    period: Optional[str],
    start_date: Optional[str],
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
            row = [
                str(item.get("id", "-")),
                f"[autumn.project]{item.get('name', '')}[/] [autumn.muted]({item.get('agg', '')})[/]",
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


@commitments.command("show")
@click.argument("commitment_id", type=int)
def commitments_show(commitment_id: int) -> None:
    """Show full commitment details."""
    try:
        result = APIClient().get_commitment(commitment_id)
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
        fn = click.option("--start-date", help="Start date (YYYY-MM-DD)")(fn)
        fn = click.option("--period", type=click.Choice(PERIODS), default="weekly" if required_target_value else None, show_default=required_target_value)(fn)
        fn = click.option("--commitment-type", type=click.Choice(COMMITMENT_TYPES), default="time" if required_target_value else None, show_default=required_target_value)(fn)
        fn = click.option("--target-value", required=required_target_value, help="Goal duration (for time) or session count")(fn)
        return fn
    return decorate


@commitments.command("new")
@click.option("--type", "aggregation_type", type=click.Choice(AGGREGATION_TYPES), default="project", show_default=True)
@click.argument("target")
@_commitment_options(required_target_value=True)
def commitments_new(aggregation_type: str, target: str, **options: Any) -> None:
    """Create a commitment. Time values are stored as minutes."""
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
@click.argument("commitment_id", type=int)
@_commitment_options(required_target_value=False)
def commitments_edit(commitment_id: int, **options: Any) -> None:
    """Patch selected commitment fields; target and aggregation cannot change."""
    try:
        client = APIClient()
        existing: dict[str, Any] = {}
        needs_existing = (
            options.get("commitment_type") is None
            and any(options.get(key) is not None for key in ("target_value", "max_balance", "min_balance"))
        ) or options.get("include") or options.get("exclude")
        if needs_existing:
            existing = client.get_commitment(commitment_id).get("commitment", {})
        ctype = options.get("commitment_type") or existing.get("commitment_type", "time")
        aggregation_type = existing.get("aggregation_type", "project")
        data = _new_payload(
            client,
            aggregation_type=aggregation_type,
            target="",
            commitment_type=ctype,
            editing=True,
            **options,
        )
        if options.get("commitment_type") is None:
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
@click.argument("commitment_id", type=int)
@click.option("--yes", "yes", is_flag=True, help="Skip confirmation prompt")
def commitments_delete(commitment_id: int, yes: bool) -> None:
    """Delete a commitment."""
    try:
        if not yes and not click.confirm(f"Delete commitment {commitment_id}?", default=False):
            console.print("[autumn.muted]Cancelled.[/]")
            return
        APIClient().delete_commitment(commitment_id)
        console.print(f"[autumn.ok]Commitment deleted:[/] #[autumn.id]{commitment_id}[/]")
    except APIError as exc:
        console.print(f"[autumn.err]Error:[/] {exc}")
        raise click.Abort()
