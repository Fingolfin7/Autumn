"""Timed reminders via desktop notifications.

This command is intentionally straightforward:
- `autumn remind in 25m --message "..."`

It runs in-process (sleep) so it's cross-platform.
"""

from __future__ import annotations

import click

from ..utils.console import console
from ..utils.duration_parse import parse_duration_to_seconds
from ..utils.notify import send_notification
from ..utils.scheduler import sleep_seconds


@click.group("remind")
def remind() -> None:
    """Timed reminders (desktop notifications)."""


@remind.command("in")
@click.argument("duration")
@click.option("--title", default="Autumn", show_default=True, help="Notification title")
@click.option("--message", required=True, help="Notification message")
@click.option("--subtitle", help="Notification subtitle (macOS only)")
@click.option("--quiet", is_flag=True, help="Don't print anything; just exit 0/1")
def remind_in(duration: str, title: str, message: str, subtitle: str | None, quiet: bool) -> None:
    """Send a notification after a duration (e.g. 25m, 1h30m)."""

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
        console.print(f"[autumn.warn]Notifications not available[/] ({res.method}). {res.error or ''}".rstrip())
        raise click.Abort()

    console.print(f"[autumn.err]Failed to send notification[/] ({res.method}). {res.error or ''}".rstrip())
    raise click.Abort()

