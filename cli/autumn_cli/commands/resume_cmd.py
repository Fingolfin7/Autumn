"""Resume the most recently worked-on project."""

from __future__ import annotations

import click

from ..api_client import APIClient, APIError
from ..utils.console import console


@click.command("resume")
@click.option(
    "--stop-current/--no-stop-current",
    default=False,
    help="If a timer is currently active, stop it before resuming.",
)
@click.option(
    "--with-subprojects/--no-with-subprojects",
    default=False,
    help="Also resume the last session's subprojects (if any).",
)
def resume(stop_current: bool, with_subprojects: bool) -> None:
    """Start a new timer for the most recently worked-on project."""
    try:
        client = APIClient()

        # If we already have an active timer, either stop it or refuse.
        status = client.get_timer_status()
        if status.get("ok") and status.get("active", 0):
            if not stop_current:
                raise APIError(
                    "An active timer is running. Use --stop-current to stop it before resuming."
                )
            client.stop_timer()

        # Find the most recent completed session.
        # The /api/sessions/search/ endpoint requires at least one filter, so we
        # use the log endpoint instead.
        result = client.log_activity(period="week")
        logs = result.get("logs", [])
        if not logs:
            raise APIError("No recent sessions found to resume.")

        s0 = logs[0]
        project = s0.get("p") or s0.get("project")
        if not project:
            raise APIError("Could not determine last project.")

        subprojects = None
        if with_subprojects:
            subprojects = s0.get("subs") or s0.get("subprojects") or None
            # normalize empty list
            if subprojects == []:
                subprojects = None

        started = client.start_timer(project, subprojects=subprojects)
        if started.get("ok"):
            sess = started.get("session", {})
            console.print(f"[autumn.ok]Resumed[/] [autumn.project]{project}[/] (Session ID: {sess.get('id')})")
        else:
            raise APIError(started.get("error", "Failed to resume"))

    except APIError as e:
        console.print(f"[autumn.err]Error:[/] {e}")
        raise click.Abort()
