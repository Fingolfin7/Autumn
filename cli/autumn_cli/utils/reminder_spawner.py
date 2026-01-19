"""Helper to spawn background reminder processes."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from ..utils.background import spawn_detached_python_module
from ..utils.console import console
from ..utils.duration_parse import parse_duration_to_seconds
from ..utils.reminders_registry import add_entry


def spawn_reminder(
    *,
    project: str,
    session_id: Optional[int] = None,
    remind_in: Optional[str] = None,
    remind_every: Optional[str] = None,
    auto_stop_for: Optional[str] = None,
    remind_message: str = "Timer running: {project} ({elapsed})",
    notify_title: str = "Autumn",
    remind_poll: str = "30s",
    quiet: bool = False,
) -> None:
    """Spawn a background reminder daemon."""

    # Determine mode label for listing.
    mode_parts = []
    if remind_in:
        mode_parts.append("remind-in")
    if remind_every:
        mode_parts.append("remind-every")
    if auto_stop_for:
        mode_parts.append("auto-stop")
    mode = "+".join(mode_parts) if mode_parts else "unknown"

    # Calculate initial next_fire_at
    next_fire_at = None
    if remind_in:
        try:
            secs = parse_duration_to_seconds(remind_in)
            next_fire_at = (datetime.now() + timedelta(seconds=secs)).isoformat()
        except Exception:
            pass
    elif remind_every:
        try:
            secs = parse_duration_to_seconds(remind_every)
            next_fire_at = (datetime.now() + timedelta(seconds=secs)).isoformat()
        except Exception:
            pass

    args = [
        "--project",
        str(project),
        "--notify-title",
        str(notify_title),
        "--remind-message",
        str(remind_message),
        "--remind-poll",
        str(remind_poll),
        "--quiet",
    ]

    if session_id is not None:
        args += ["--session-id", str(session_id)]

    if remind_in:
        args += ["--remind-in", str(remind_in)]
    if remind_every:
        args += ["--remind-every", str(remind_every)]
    if auto_stop_for:
        args += ["--for", str(auto_stop_for)]

    proc = spawn_detached_python_module("autumn_cli.commands.reminder_daemon", args)

    try:
        add_entry(
            pid=int(proc.pid),
            session_id=session_id,
            project=str(project),
            mode=mode,
            remind_in=(str(remind_in) if remind_in else None),
            remind_every=(str(remind_every) if remind_every else None),
            auto_stop_for=(str(auto_stop_for) if auto_stop_for else None),
            remind_poll=str(remind_poll),
            next_fire_at=next_fire_at,
            remind_message=(str(remind_message) if remind_message else None),
            notify_title=(str(notify_title) if notify_title else None),
        )

    except Exception:
        pass

    if not quiet:
        console.print("[autumn.muted]Scheduled reminders in background.[/]")
