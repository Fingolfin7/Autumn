"""Resume the most recently worked-on project."""

from __future__ import annotations

import click
from rich.markup import escape

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
    "-s",
    default=False,
    help="Also resume the last session's subprojects (if any).",
)
def resume(stop_current: bool, with_subprojects: bool) -> None:
    """Start a new timer for the most recently worked-on project."""
    stopped_timer_id = None
    try:
        client = APIClient()

        status = client.get_timer_status()
        if not status.get("ok"):
            raise APIError(status.get("error") or "Could not check for running timers.")

        timer_id = None
        if status.get("active", 0):
            if not stop_current:
                raise APIError(
                    "An active timer is running. Use --stop-current to stop it before resuming."
                )
            # Remember the same timer a bare stop would select.
            timer_id = client.newest_timer(status.get("sessions") or []).get("id")
            if timer_id is None:
                raise APIError("Could not identify the current timer.")

        # Select the completed session before the running one can enter history.
        result = client.search_sessions(limit=1, ordering="newest")
        if result.get("ok") is False:
            raise APIError(result.get("error") or "Could not read saved sessions.")
        logs = result.get("sessions", [])
        if not logs:
            raise APIError("No saved sessions found to resume.")

        s0 = logs[0]
        project = s0.get("p") or s0.get("project")
        if not project:
            raise APIError("Could not determine last project.")

        subprojects = None
        if with_subprojects:
            subprojects = s0.get("subs") or s0.get("subprojects") or None

        if timer_id is not None:
            stopped = client.stop_timer(session_id=timer_id)
            if not stopped.get("ok"):
                raise APIError(stopped.get("error") or "Failed to stop the current timer.")
            stopped_timer_id = timer_id

        started = client.start_timer(project, subprojects=subprojects)
        if started.get("ok"):
            sess = started.get("session", {})
            console.print(f"[autumn.ok]Resumed[/] [autumn.project]{escape(project)}[/] (Session ID: {sess.get('id')})")
        else:
            raise APIError(started.get("error", "Failed to resume"))

    except APIError as e:
        if stopped_timer_id is not None:
            console.print(f"Stopped timer #{stopped_timer_id} before the resume failed.")
        console.print(f"[autumn.err]Error:[/] {escape(str(e))}")
        raise click.Abort()
