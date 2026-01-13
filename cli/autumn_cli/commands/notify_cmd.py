"""Notification commands.

This is intentionally simple: it's mostly a wiring layer over utils.notify.
"""

from __future__ import annotations

import click

from ..utils.console import console
from ..utils.notify import send_notification


@click.command("notify")
@click.option("--title", default="Autumn", show_default=True, help="Notification title")
@click.option("--message", required=True, help="Notification message")
@click.option("--subtitle", help="Notification subtitle (macOS only)")
@click.option("--quiet", is_flag=True, help="Don't print anything; just exit 0/1")
def notify_cmd(title: str, message: str, subtitle: str | None, quiet: bool) -> None:
    """Send a desktop notification (best-effort, cross-platform)."""

    res = send_notification(title=title, message=message, subtitle=subtitle)

    if quiet:
        if not res.ok:
            raise click.Abort()
        return

    if res.ok:
        console.print(f"[autumn.ok]Notification sent[/] ({res.method})")
        return

    if not res.supported:
        console.print(f"[autumn.warn]Notifications not available[/] ({res.method}). {res.error or ''}".rstrip())
        raise click.Abort()

    console.print(f"[autumn.err]Failed to send notification[/] ({res.method}). {res.error or ''}".rstrip())
    raise click.Abort()

