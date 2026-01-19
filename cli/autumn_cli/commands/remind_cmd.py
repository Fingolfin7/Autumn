"""Timed reminders via desktop notifications.

This command is intentionally straightforward:
- `autumn remind in 25m --message "..."`

It runs in-process (sleep) so it's cross-platform.
"""

from __future__ import annotations

import click
from typing import Optional

from ..utils.console import console
from ..utils.duration_parse import parse_duration_to_seconds
from ..utils.datetime_parse import parse_user_datetime
from ..utils.notify import send_notification
from ..utils.scheduler import sleep_seconds
from ..utils.reminder_spawner import spawn_reminder
from ..api_client import APIClient


@click.group("remind")
def remind() -> None:
    """Timed reminders (desktop notifications)."""


def _find_active_session_id() -> Optional[int]:
    """Helper to find an active session ID for auto-binding reminders."""
    try:
        client = APIClient()
        st = client.get_timer_status(session_id=None)
        if st.get("ok"):
            sessions = st.get("sessions")
            if isinstance(sessions, list) and sessions:
                # Return the most recently started active session
                return sessions[0].get("id")

            one = st.get("session")
            if isinstance(one, dict):
                return one.get("id")
    except Exception:
        pass
    return None


@remind.command("in")
@click.argument("duration")
@click.option("--title", default="Autumn", show_default=True, help="Notification title")
@click.option("--message", required=True, help="Notification message")
@click.option("--subtitle", help="Notification subtitle (macOS only)")
@click.option("--quiet", is_flag=True, help="Don't print anything; just exit 0/1")
@click.option("--background", is_flag=True, help="Run in background (non-blocking)")
def remind_in(
    duration: str,
    title: str,
    message: str,
    subtitle: str | None,
    quiet: bool,
    background: bool,
) -> None:
    """Send a notification after a duration (e.g. 25m, 1h30m)."""

    if background:
        spawn_reminder(
            project=f"Reminder: {message}",
            session_id=_find_active_session_id(),
            remind_in=duration,
            remind_message=message,
            notify_title=title,
        )
        return

    try:
        seconds = parse_duration_to_seconds(duration)

    except ValueError as e:
        console.print(f"[autumn.err]Error:[/] {e}")
        raise click.Abort()

    if not quiet:
        console.print(f"[autumn.muted]Reminder scheduled in {duration}...[/]")

    sleep_seconds(seconds)

    res = send_notification(title=title, message=message, subtitle=subtitle)

    if quiet:
        if not res.ok:
            raise click.Abort()
        return

    if res.ok:
        console.print(f"[autumn.ok]Reminder sent[/] ({res.method})")
        return

    if not res.supported:
        console.print(
            f"[autumn.warn]Notifications not available[/] ({res.method}). {res.error or ''}".rstrip()
        )
        raise click.Abort()

    console.print(
        f"[autumn.err]Failed to send notification[/] ({res.method}). {res.error or ''}".rstrip()
    )
    raise click.Abort()


@remind.command("every")
@click.argument("duration")
@click.option("--title", default="Autumn", show_default=True, help="Notification title")
@click.option("--message", required=True, help="Notification message")
def remind_every(duration: str, title: str, message: str) -> None:
    """Send periodic notifications every duration (e.g. 20m).

    This always runs in the background.
    """
    spawn_reminder(
        project=f"Recurring: {message}",
        session_id=_find_active_session_id(),
        remind_every=duration,
        remind_message=message,
        notify_title=title,
    )


@remind.command("at")
@click.argument("time")
@click.option("--title", default="Autumn", show_default=True, help="Notification title")
@click.option("--message", required=True, help="Notification message")
@click.option(
    "--background",
    is_flag=True,
    default=True,
    show_default=True,
    help="Run in background",
)
def remind_at(time: str, title: str, message: str, background: bool) -> None:
    """Send a notification at a specific time (e.g. 14:30, 5pm)."""
    from datetime import datetime

    try:
        now = datetime.now()
        target_dt = parse_user_datetime(time).dt
        diff = (target_dt - now).total_seconds()

        if diff <= 0:
            console.print("[autumn.err]Error:[/] Time must be in the future")
            raise click.Abort()

        remind_in_str = f"{int(diff)}s"

        if background:
            spawn_reminder(
                project=f"Reminder: {message}",
                session_id=_find_active_session_id(),
                remind_in=remind_in_str,
                remind_message=message,
                notify_title=title,
            )
            return

        console.print(
            f"[autumn.muted]Reminder scheduled for {target_dt.strftime('%H:%M:%S')}...[/]"
        )
        sleep_seconds(int(diff))
        send_notification(title=title, message=message)
        console.print("[autumn.ok]Reminder sent[/]")

    except ValueError as e:
        console.print(f"[autumn.err]Error:[/] {e}")
        raise click.Abort()


@remind.command("session")
@click.argument("session_id", type=int)
@click.option("--in", "remind_in", help="One-shot reminder duration (e.g. 30m)")
@click.option("--every", "remind_every", help="Periodic reminder duration (e.g. 15m)")
@click.option("--at", "remind_at", help="Specific time reminder (e.g. 14:30)")
@click.option(
    "--message",
    default="Timer running: {project} ({elapsed})",
    help="Notification message",
)
@click.option("--title", default="Autumn", help="Notification title")
def remind_session(
    session_id: int,
    remind_in: Optional[str],
    remind_every: Optional[str],
    remind_at: Optional[str],
    message: str,
    title: str,
) -> None:
    """Attach a reminder to an existing session."""

    if not (remind_in or remind_every or remind_at):
        raise click.UsageError("Must specify --in, --every, or --at")

    client = APIClient()
    st = client.get_timer_status(session_id=session_id)
    if not st.get("ok"):
        console.print(f"[autumn.err]Error:[/] {st.get('error', 'Unknown error')}")
        raise click.Abort()

    # Verify session exists/active
    # Actually, we can attach to stopped sessions? No, reminders stop when session stops.
    # So we should verify it's active.
    # The response shape: { "ok": true, "session": { ... } } or { "ok": true, "sessions": [...] }
    # Let's try to get project name for the reminder label.
    project_name = "Unknown"

    one = st.get("session")
    if isinstance(one, dict):
        project_name = one.get("p") or one.get("project") or "Unknown"
    else:
        # Fallback if multiple sessions returned or ambiguous
        sessions = st.get("sessions")
        if sessions and isinstance(sessions, list):
            for s in sessions:
                if int(s.get("id")) == int(session_id):
                    project_name = s.get("p") or s.get("project")
                    break

    # Handle remind_at logic here too
    if remind_at:
        try:
            from datetime import datetime

            now = datetime.now()
            target_dt = parse_user_datetime(remind_at).dt
            diff = (target_dt - now).total_seconds()
            if diff <= 0:
                raise click.BadParameter(
                    "Time must be in the future", param_hint="--at"
                )
            remind_in = f"{int(diff)}s"
        except ValueError as e:
            raise click.BadParameter(str(e), param_hint="--at")

    spawn_reminder(
        project=project_name,
        session_id=session_id,
        remind_in=remind_in,
        remind_every=remind_every,
        remind_message=message,
        notify_title=title,
    )
