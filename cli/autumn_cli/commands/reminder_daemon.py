"""Background reminder/auto-stop worker.

This is run as a separate process so reminder scheduling can be non-blocking.

We keep it dependency-free and portable:
- Spawned via the current Python interpreter
- Communicates only via stdout/stderr (optional)

It polls timer status and optionally stops the timer after a duration.
"""

from __future__ import annotations

from dataclasses import dataclass

import click

from ..api_client import APIClient
from ..utils.duration_parse import parse_duration_to_seconds
from ..utils.notify import send_notification
from ..utils.formatters import format_duration_minutes
from ..utils.scheduler import sleep_seconds


@dataclass(frozen=True)
class Plan:
    session_id: int
    project: str
    notify_title: str
    remind_in_seconds: int | None
    remind_every_seconds: int | None
    for_seconds: int | None
    remind_message: str
    poll_seconds: int


def _is_session_active(client: APIClient, session_id: int) -> bool:
    try:
        st = client.get_timer_status(session_id=session_id)
        if not st.get("ok"):
            return False

        one = st.get("session")
        if isinstance(one, dict):
            active_flag = one.get("active")
            if active_flag is not None:
                return bool(active_flag)
            return one.get("end") in (None, "")

        sessions = st.get("sessions")
        if isinstance(sessions, list):
            for s in sessions:
                sid = s.get("id") if isinstance(s, dict) else None
                try:
                    if sid is not None and int(sid) == int(session_id):
                        if "active" in s:
                            return bool(s.get("active"))
                        return True
                except Exception:
                    continue
            return False

        return bool(st.get("active", 0))
    except Exception:
        return True


def _elapsed_str(client: APIClient, session_id: int) -> str:
    try:
        st = client.get_timer_status(session_id=session_id)
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


@click.command("reminder-daemon")
@click.option("--session-id", type=int, required=True)
@click.option("--project", required=True)
@click.option("--notify-title", default="Autumn")
@click.option("--remind-in")
@click.option("--remind-every")
@click.option("--for", "for_")
@click.option(
    "--remind-message",
    default="Timer running: {project} ({elapsed})",
)
@click.option("--remind-poll", default="30s")
@click.option("--quiet", is_flag=True, help="Don't print worker logs")
def main(
    session_id: int,
    project: str,
    notify_title: str,
    remind_in: str | None,
    remind_every: str | None,
    for_: str | None,
    remind_message: str,
    remind_poll: str,
    quiet: bool,
) -> None:
    """Worker entrypoint."""

    def parse_opt(raw: str | None) -> int | None:
        if not raw:
            return None
        return parse_duration_to_seconds(raw)

    plan = Plan(
        session_id=session_id,
        project=project,
        notify_title=notify_title,
        remind_in_seconds=parse_opt(remind_in),
        remind_every_seconds=parse_opt(remind_every),
        for_seconds=parse_opt(for_),
        remind_message=remind_message,
        poll_seconds=parse_duration_to_seconds(remind_poll),
    )

    if plan.remind_in_seconds is not None and plan.remind_every_seconds is not None:
        raise click.ClickException("Use either --remind-in or --remind-every")

    if plan.poll_seconds < 5:
        raise click.ClickException("--remind-poll must be >= 5s")

    client = APIClient()

    # Schedule bookkeeping (simple counters, no threads)
    t0 = 0
    next_remind = plan.remind_in_seconds if plan.remind_in_seconds is not None else None
    next_every = plan.remind_every_seconds if plan.remind_every_seconds is not None else None
    stop_at = plan.for_seconds if plan.for_seconds is not None else None

    def log(msg: str) -> None:
        if not quiet:
            click.echo(msg, err=True)

    log(f"[autumn] reminder-daemon started (session_id={plan.session_id})")

    while True:
        if not _is_session_active(client, plan.session_id):
            log("[autumn] session ended; exiting")
            return

        # Auto-stop
        if stop_at is not None and t0 >= stop_at:
            try:
                client.stop_timer(session_id=plan.session_id, note=None)
            except Exception as e:
                log(f"[autumn] auto-stop failed: {e}")
            send_notification(title=plan.notify_title, message=f"Auto-stopped timer: {plan.project}")
            log("[autumn] auto-stopped; exiting")
            return

        # One-shot remind
        if next_remind is not None and t0 >= next_remind:
            msg = (plan.remind_message or "").format(project=plan.project, elapsed=_elapsed_str(client, plan.session_id))
            send_notification(title=plan.notify_title, message=msg)
            next_remind = None

        # Periodic remind
        if next_every is not None and t0 >= next_every:
            msg = (plan.remind_message or "").format(project=plan.project, elapsed=_elapsed_str(client, plan.session_id))
            send_notification(title=plan.notify_title, message=msg)
            next_every += plan.remind_every_seconds or 0

        sleep_seconds(plan.poll_seconds)
        t0 += plan.poll_seconds


if __name__ == "__main__":
    # Allow `python -m autumn_cli.commands.reminder_daemon ...`
    main()
