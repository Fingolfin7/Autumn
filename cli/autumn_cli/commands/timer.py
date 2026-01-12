"""Timer commands for Autumn CLI."""

import click
from typing import Optional

from ..api_client import APIClient, APIError
from ..utils.console import console
from ..utils.formatters import format_duration_minutes
from ..utils.log_render import render_active_timers_list


@click.command()
@click.argument("project")
@click.option("--subprojects", "-s", multiple=True, help="Subproject names (can specify multiple)")
@click.option("--note", "-n", help="Note for the session")
def start(project: str, subprojects: tuple, note: Optional[str]):
    """Start a new timer for a project."""
    try:
        client = APIClient()
        subprojects_list = list(subprojects) if subprojects else None
        result = client.start_timer(project, subprojects_list, note)

        if result.get("ok"):
            session = result.get("session", {})
            console.print("[autumn.ok]Timer started.[/]", highlight=True)
            console.print(f"[autumn.label]Project:[/] [autumn.project]{project}[/]")
            subs = session.get("subs") or session.get("subprojects") or []
            if subs:
                console.print(f"[autumn.label]Subprojects:[/] {', '.join(subs)}")
            if session.get("note"):
                console.print(f"[autumn.label]Note:[/] {session.get('note')}")
            console.print(f"[autumn.label]Session ID:[/] {session.get('id')}")
        else:
            console.print(f"[autumn.err]Error:[/] {result.get('error', 'Unknown error')}")
    except APIError as e:
        console.print(f"[autumn.err]Error:[/] {e}")
        raise click.Abort()


@click.command()
@click.option("--session-id", "-i", type=int, help="Specific session ID to stop")
@click.option("--project", "-p", help="Project name to stop timer for")
@click.option("--note", "-n", help="Note to add when stopping")
def stop(session_id: Optional[int], project: Optional[str], note: Optional[str]):
    """Stop the current timer (or a specific one)."""
    try:
        client = APIClient()
        result = client.stop_timer(session_id, project, note)

        if result.get("ok"):
            session = result.get("session", {})
            duration = result.get("duration", session.get("elapsed", 0))
            console.print("[autumn.ok]Timer stopped.[/]", highlight=True)
            console.print(f"[autumn.label]Duration:[/] {format_duration_minutes(duration)}")
            console.print(
                f"[autumn.label]Project:[/] {session.get('p') or session.get('project') or project or ''}"
            )
            if session.get("note"):
                console.print(f"[autumn.label]Note:[/] {session.get('note')}")
        else:
            console.print(f"[autumn.err]Error:[/] {result.get('error', 'Unknown error')}")
    except APIError as e:
        console.print(f"[autumn.err]Error:[/] {e}")
        raise click.Abort()


@click.command()
@click.option("--session-id", "-i", type=int, help="Specific session ID to check")
@click.option("--project", "-p", help="Project name to check timer for")
def status(session_id: Optional[int], project: Optional[str]):
    """Show status of current timer(s)."""
    try:
        client = APIClient()
        result = client.get_timer_status(session_id, project)

        if result.get("ok"):
            active_count = result.get("active", 0)
            sessions = result.get("sessions", [])

            if active_count == 0:
                console.print("[autumn.muted]No active timers.[/]", highlight=True)
                return

            console.print(f"[autumn.label]Active timers:[/] [autumn.ok]{active_count}[/]", highlight=True)
            console.print(render_active_timers_list(sessions))
        else:
            console.print(f"[autumn.err]Error:[/] {result.get('error', 'Unknown error')}")
    except APIError as e:
        console.print(f"[autumn.err]Error:[/] {e}")
        raise click.Abort()


@click.command()
@click.option("--session-id", "-i", type=int, help="Specific session ID to restart")
@click.option("--project", "-p", help="Project name to restart timer for")
def restart(session_id: Optional[int], project: Optional[str]):
    """Restart a timer (reset start time to now).

    If you have multiple active timers, target one with --session-id or --project.
    """
    try:
        client = APIClient()
        result = client.restart_timer(session_id, project)

        if result.get("ok"):
            session = result.get("session", {})
            console.print("[autumn.ok]Timer restarted.[/]", highlight=True)
            console.print(f"[autumn.label]Session ID:[/] {session.get('id')}")
            console.print(
                f"[autumn.label]Project:[/] {session.get('p') or session.get('project') or project or ''}"
            )
        else:
            console.print(f"[autumn.err]Error:[/] {result.get('error', 'Unknown error')}")
    except APIError as e:
        console.print(f"[autumn.err]Error:[/] {e}")
        raise click.Abort()


@click.command()
@click.option("--session-id", "-i", type=int, help="Specific session ID to delete")
def delete(session_id: Optional[int]):
    """Delete a timer without saving a session."""
    try:
        client = APIClient()
        result = client.delete_timer(session_id)

        if result.get("ok"):
            deleted_id = result.get("deleted")
            console.print(f"[autumn.warn]Timer deleted[/] (Session ID: {deleted_id})", highlight=True)
        else:
            console.print(f"[autumn.err]Error:[/] {result.get('error', 'Unknown error')}")
    except APIError as e:
        console.print(f"[autumn.err]Error:[/] {e}")
        raise click.Abort()
