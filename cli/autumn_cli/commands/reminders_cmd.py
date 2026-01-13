"""Manage background reminder workers started by `autumn start`.

Commands:
- `autumn reminders list`
- `autumn reminders stop [--pid PID] [--session-id ID] [--all]`

This is best-effort: processes may have already exited.
"""

from __future__ import annotations

import click

from ..utils.console import console
from ..utils.reminders_registry import load_entries, kill_pid, remove_entry_by_pid, clear_entries


@click.group("reminders")
def reminders() -> None:
    """Manage background reminder workers."""


@reminders.command("list")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def list_cmd(as_json: bool) -> None:
    """List active reminder workers."""
    entries = load_entries(prune_dead=True)

    if as_json:
        import json

        click.echo(
            json.dumps(
                [
                    {
                        "pid": e.pid,
                        "session_id": e.session_id,
                        "project": e.project,
                        "created_at": e.created_at,
                        "mode": e.mode,
                    }
                    for e in entries
                ],
                indent=2,
            )
        )
        return

    if not entries:
        console.print("[autumn.muted]No active reminder workers.[/]")
        return

    console.print("[autumn.title]Active reminders[/]")
    for e in entries:
        console.print(
            f"[autumn.label]PID:[/] {e.pid}  [autumn.label]Session:[/] {e.session_id}  "
            f"[autumn.label]Project:[/] [autumn.project]{e.project}[/]  [autumn.label]Mode:[/] {e.mode}"
        )


@reminders.command("stop")
@click.option("--pid", type=int, help="Stop a reminder worker by PID")
@click.option("--session-id", type=int, help="Stop reminder workers for a session id")
@click.option("--all", "stop_all", is_flag=True, help="Stop all reminder workers")
def stop_cmd(pid: int | None, session_id: int | None, stop_all: bool) -> None:
    """Stop background reminder workers."""
    if not (pid or session_id or stop_all):
        raise click.BadParameter("Provide --pid, --session-id, or --all")

    entries = load_entries(prune_dead=False)

    targets = []
    if stop_all:
        targets = entries
    elif pid is not None:
        targets = [e for e in entries if int(e.pid) == int(pid)]
    elif session_id is not None:
        targets = [e for e in entries if int(e.session_id) == int(session_id)]

    if not targets:
        console.print("[autumn.muted]No matching reminder workers found.[/]")
        return

    stopped = 0
    for e in targets:
        ok = kill_pid(e.pid)
        remove_entry_by_pid(e.pid)
        if ok:
            stopped += 1

    if stop_all:
        # ensure registry is cleared
        clear_entries()

    console.print(f"[autumn.ok]Stopped {stopped} reminder worker(s).[/]")

