"""Manage background reminder workers started by `autumn start`.

Commands:
- `autumn reminders list`
- `autumn reminders stop [--pid PID] [--session-id ID] [--all]`

This is best-effort: processes may have already exited.
"""

from __future__ import annotations

import click

from ..utils.console import console
from ..utils.reminders_registry import (
    load_entries,
    kill_pid,
    remove_entry_by_pid,
    clear_entries,
)


@click.group("reminders")
def reminders() -> None:
    """Manage background reminder workers."""


@reminders.command("list")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def list_cmd(as_json: bool) -> None:
    """List active reminder workers."""
    entries = load_entries(prune_dead=True)

    def _details(e) -> str:
        parts = []

        # Prefer a human-friendly label format.
        if getattr(e, "remind_every", None):
            parts.append(f"Every: {e.remind_every}")
        if getattr(e, "remind_in", None):
            parts.append(f"In: {e.remind_in}")
        if getattr(e, "auto_stop_for", None):
            parts.append(f"For: {e.auto_stop_for}")
        if getattr(e, "remind_poll", None):
            parts.append(f"Poll: {e.remind_poll}")
        if getattr(e, "next_fire_at", None):
            parts.append(f"Next: {e.next_fire_at}")

        return " | ".join(parts)

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
                        "remind_in": getattr(e, "remind_in", None),
                        "remind_every": getattr(e, "remind_every", None),
                        "auto_stop_for": getattr(e, "auto_stop_for", None),
                        "remind_poll": getattr(e, "remind_poll", None),
                        "next_fire_at": getattr(e, "next_fire_at", None),
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
        details = _details(e)
        suffix = f"  [autumn.label]Details:[/] {details}" if details else ""
        console.print(
            f"[autumn.label]PID:[/] {e.pid}  [autumn.label]Session:[/] {e.session_id}  "
            f"[autumn.label]Project:[/] [autumn.project]{e.project}[/]  [autumn.label]Mode:[/] {e.mode}"
            f"{suffix}"
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
        targets = [
            e
            for e in entries
            if e.session_id is not None and int(e.session_id) == int(session_id)
        ]

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
