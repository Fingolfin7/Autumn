"""Helper to spawn background reminder processes."""

from __future__ import annotations

from datetime import datetime, timedelta
from string import Formatter
from typing import Optional

from ..utils.background import spawn_detached_python_module
from ..utils.console import console
from ..utils.duration_parse import parse_duration_to_seconds
from ..utils.reminders_registry import add_entry
from ..errors import ReminderError


def _parse_reminder_duration(value: Optional[str], label: str) -> Optional[int]:
    if not value:
        return None
    try:
        return parse_duration_to_seconds(value)
    except ValueError as error:
        raise ReminderError(f"Invalid {label} duration '{value}': {error}") from None


def _validate_message_template(message: str) -> None:
    try:
        fields = [field for _, field, _, _ in Formatter().parse(message) if field]
    except ValueError as error:
        raise ReminderError(f"Invalid reminder message template: {error}") from None

    unsupported = sorted(
        {field for field in fields if field not in {"project", "elapsed"}}
    )
    if unsupported:
        raise ReminderError(
            "Unsupported reminder message field(s): "
            f"{', '.join(unsupported)}. Use only {{project}} and {{elapsed}}."
        )


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

    remind_in_seconds = _parse_reminder_duration(remind_in, "--remind-in")
    remind_every_seconds = _parse_reminder_duration(remind_every, "--remind-every")
    _parse_reminder_duration(auto_stop_for, "--for")
    poll_seconds = _parse_reminder_duration(remind_poll, "--remind-poll")
    if poll_seconds is not None and poll_seconds < 5:
        raise ReminderError("--remind-poll must be at least 5 seconds.")
    _validate_message_template(str(remind_message or ""))

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
    if remind_in_seconds is not None:
        next_fire_at = (
            datetime.now() + timedelta(seconds=remind_in_seconds)
        ).isoformat()
    elif remind_every_seconds is not None:
        next_fire_at = (
            datetime.now() + timedelta(seconds=remind_every_seconds)
        ).isoformat()

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

    try:
        proc = spawn_detached_python_module("autumn_cli.commands.reminder_daemon", args)
    except OSError as error:
        raise ReminderError(f"Could not start background reminder: {error}") from None

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
            status="pending",
        )

    except (OSError, IOError):
        pass

    if not quiet:
        console.print("[autumn.muted]Scheduled reminders in background.[/]")
