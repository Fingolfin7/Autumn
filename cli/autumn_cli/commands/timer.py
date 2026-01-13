"""Timer commands for Autumn CLI."""

import click
from typing import Optional

from ..api_client import APIClient, APIError
from ..utils.console import console
from ..utils.formatters import format_duration_minutes
from ..utils.log_render import render_active_timers_list
from ..utils.duration_parse import parse_duration_to_seconds
from ..utils.notify import send_notification
from ..utils.scheduler import schedule_in, schedule_every, sleep_seconds
from ..utils.background import spawn_detached_python_module
from ..utils.reminders_registry import add_entry


@click.command()
@click.argument("project")
@click.option("--subprojects", "-s", multiple=True, help="Subproject names (can specify multiple)")
@click.option("--note", "-n", help="Note for the session")
@click.option("--for", "for_", help="Auto-stop after a duration (e.g. 25m, 1h30m)")
@click.option("--remind-in", help="Send a reminder after a duration (e.g. 30m)")
@click.option("--remind-every", help="Send periodic reminders every duration (e.g. 15m)")
@click.option(
    "--remind-message",
    default="Timer running: {project} ({elapsed})",
    show_default=True,
    help="Reminder message template. Available: {project}, {elapsed}",
)
@click.option(
    "--notify-title",
    default="Autumn",
    show_default=True,
    help="Notification title for reminders/auto-stop",
)
@click.option(
    "--remind-poll",
    default="30s",
    show_default=True,
    help="How often to poll timer status to stop reminders when the timer ends (e.g. 30s, 1m)",
)
@click.option(
    "--background/--no-background",
    default=True,
    show_default=True,
    help="Run reminders/auto-stop in a detached background process (non-blocking)",
)
def start(
    project: str,
    subprojects: tuple,
    note: Optional[str],
    for_: Optional[str],
    remind_in: Optional[str],
    remind_every: Optional[str],
    remind_message: str,
    notify_title: str,
    remind_poll: str,
    background: bool,
):
    """Start a new timer for a project.

    Optional timing features (cross-platform, in-process):
      - Auto-stop after a duration: `--for 25m`
      - One-shot reminder: `--remind-in 30m`
      - Periodic reminders: `--remind-every 15m`

    Reminder threads are tied to the timer's lifetime: if the session stops or is
    deleted, reminders self-cancel automatically.
    """

    # Parse durations early so we fail fast.
    def _parse_opt(name: str, raw: Optional[str]) -> Optional[int]:
        if not raw:
            return None
        try:
            return parse_duration_to_seconds(raw)
        except ValueError as e:
            raise click.BadParameter(str(e), param_hint=name)

    for_seconds = _parse_opt("--for", for_)
    remind_in_seconds = _parse_opt("--remind-in", remind_in)
    remind_every_seconds = _parse_opt("--remind-every", remind_every)

    if remind_in_seconds is not None and remind_every_seconds is not None:
        raise click.BadParameter("Use either --remind-in or --remind-every (not both)")

    try:
        poll_seconds = parse_duration_to_seconds(remind_poll)
    except ValueError as e:
        raise click.BadParameter(str(e), param_hint="--remind-poll")

    # Don't allow extremely aggressive polling by default.
    if poll_seconds < 5:
        raise click.BadParameter("Polling interval must be >= 5s", param_hint="--remind-poll")

    try:
        client = APIClient()
        subprojects_list = list(subprojects) if subprojects else None
        result = client.start_timer(project, subprojects_list, note)

        if not result.get("ok"):
            console.print(f"[autumn.err]Error:[/] {result.get('error', 'Unknown error')}")
            return

        session = result.get("session", {})
        session_id = session.get("id")

        console.print("[autumn.ok]Timer started.[/]", highlight=True)
        console.print(f"[autumn.label]Project:[/] [autumn.project]{project}[/]")
        subs = session.get("subs") or session.get("subprojects") or []
        if subs:
            console.print(f"[autumn.label]Subprojects:[/] {', '.join(subs)}")
        if session.get("note"):
            console.print(f"[autumn.label]Note:[/] {session.get('note')}")
        console.print(f"[autumn.label]Session ID:[/] {session_id}")

        # Nothing time-based requested.
        if for_seconds is None and remind_in_seconds is None and remind_every_seconds is None:
            return

        # If background mode is enabled, spawn a worker and return immediately.
        if background:
            # Determine mode label for listing.
            mode_parts = []
            if remind_in:
                mode_parts.append("remind-in")
            if remind_every:
                mode_parts.append("remind-every")
            if for_:
                mode_parts.append("auto-stop")
            mode = "+".join(mode_parts) if mode_parts else "unknown"

            args = [
                "--session-id",
                str(session_id),
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
            if remind_in:
                args += ["--remind-in", str(remind_in)]
            if remind_every:
                args += ["--remind-every", str(remind_every)]
            if for_:
                args += ["--for", str(for_)]

            proc = spawn_detached_python_module("autumn_cli.commands.reminder_daemon", args)
            try:
                add_entry(
                    pid=int(proc.pid),
                    session_id=int(session_id),
                    project=str(project),
                    mode=mode,
                    remind_in=(str(remind_in) if remind_in else None),
                    remind_every=(str(remind_every) if remind_every else None),
                    auto_stop_for=(str(for_) if for_ else None),
                    remind_poll=str(remind_poll),
                )
            except Exception:
                pass

            console.print("[autumn.muted]Scheduled reminders in background.[/]")
            return

        tasks = []

        # Reuse one client for polling. This also makes tests deterministic.
        poll_client = APIClient()

        def _is_session_active() -> bool:
            """Check if the started session is still active (exists & running).

            The status endpoint has two shapes:

            1) Filtered by session_id: returns
               {"ok": true, "session": {"id": ..., "active": true, "end": null, ...}}

            2) Unfiltered: returns
               {"ok": true, "active": <count>, "sessions": [ ... ]}

            We support both.
            """
            try:
                st = poll_client.get_timer_status(session_id=session_id)
                if not st.get("ok"):
                    return False

                # Preferred: single-session shape
                one = st.get("session")
                if isinstance(one, dict):
                    try:
                        if int(one.get("id")) != int(session_id):
                            return False
                    except Exception:
                        # If we can't compare ids, fall back to active flag
                        pass

                    active_flag = one.get("active")
                    if active_flag is not None:
                        return bool(active_flag)

                    # Fallback: consider active if end is null
                    return one.get("end") in (None, "")

                # Fallback: multi-session shape
                sessions = st.get("sessions")
                if isinstance(sessions, list):
                    for s in sessions:
                        sid = s.get("id") if isinstance(s, dict) else None
                        try:
                            if sid is not None and int(sid) == int(session_id):
                                # Some payloads may include an active flag.
                                if "active" in s:
                                    return bool(s.get("active"))
                                return True
                        except Exception:
                            continue
                    return False

                # Last-resort fallback
                return bool(st.get("active", 0))

            except Exception:
                # If the check fails, be conservative and keep running.
                return True

        # Helpers
        def _elapsed_str() -> str:
            try:
                st = poll_client.get_timer_status(session_id=session_id)
                if not st.get("ok"):
                    return "?"

                one = st.get("session")
                if isinstance(one, dict):
                    mins = one.get("elapsed") or one.get("dur") or 0
                    return format_duration_minutes(mins)

                sessions = st.get("sessions") or []
                if sessions:
                    chosen = None
                    for s in sessions:
                        sid = s.get("id")
                        try:
                            if sid is not None and int(sid) == int(session_id):
                                chosen = s
                                break
                        except Exception:
                            continue
                    s0 = chosen or sessions[0]
                    mins = s0.get("elapsed") or s0.get("dur") or 0
                    return format_duration_minutes(mins)
            except Exception:
                pass
            return "?"

        def _send_reminder() -> None:
            # Only notify if the session still exists.
            if not _is_session_active():
                return
            msg = (remind_message or "").format(project=project, elapsed=_elapsed_str())
            send_notification(title=notify_title, message=msg)

        # One-shot reminder
        if remind_in_seconds is not None:
            tasks.append(schedule_in(seconds=remind_in_seconds, fn=_send_reminder, name="remind-in"))

        # Periodic reminders
        if remind_every_seconds is not None:
            tasks.append(
                schedule_every(
                    every_seconds=remind_every_seconds,
                    fn=_send_reminder,
                    name="remind-every",
                    start_in_seconds=remind_every_seconds,
                )
            )

        # Auto-stop
        if for_seconds is not None:

            def _auto_stop() -> None:
                try:
                    APIClient().stop_timer(session_id=session_id, note=None)
                except Exception:
                    # If stopping fails, we still try to notify.
                    pass
                send_notification(title=notify_title, message=f"Auto-stopped timer: {project}")

            tasks.append(schedule_in(seconds=for_seconds, fn=_auto_stop, name="auto-stop"))

        # Keep this process alive until:
        # - auto-stop triggers (if configured), or
        # - the session is no longer active (stopped/deleted), or
        # - user interrupts.
        if for_seconds is not None:
            sleep_seconds(for_seconds + 1)
            return

        # Reminders only: poll for session lifetime.
        console.print(
            "[autumn.muted]Reminders active for this timer. They will stop automatically when the timer stops.[/]"
        )
        try:
            while True:
                if not _is_session_active():
                    for t in tasks:
                        try:
                            t.cancel()
                        except Exception:
                            pass
                    console.print("[autumn.muted]Timer ended. Reminders stopped.[/]")
                    return
                sleep_seconds(poll_seconds)
        except KeyboardInterrupt:
            for t in tasks:
                try:
                    t.cancel()
                except Exception:
                    pass
            console.print("[autumn.muted]Reminder process stopped.[/]")

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
