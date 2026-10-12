"""Notification commands.

This is intentionally simple: it's mostly a wiring layer over utils.notify.
"""

from __future__ import annotations

import click

from ..utils.console import console
from ..utils.notify import send_notification


@click.command("notify")
@click.argument("message_words", metavar="[MESSAGE]...", nargs=-1)
@click.option("--title", default="Autumn", show_default=True, help="Notification title")
@click.option("--message", help="Notification message (or give it as words)")
@click.option("--subtitle", help="Notification subtitle (macOS only)")
@click.option("--quiet", is_flag=True, help="Don't print anything; just exit 0/1")
def notify_cmd(
    message_words: tuple, title: str, message: str | None, subtitle: str | None, quiet: bool
) -> None:
    """Send a desktop notification (best-effort, cross-platform).

    \b
    Example:
      autumn notify "Build finished"
    """
    joined = " ".join(message_words).strip()
    if joined and message and joined != message:
        raise click.UsageError("Give the message once: as words or with --message.")
    message = joined or message
    if not message:
        raise click.UsageError("Give a message, e.g. `autumn notify \"Build finished\"`.")

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

