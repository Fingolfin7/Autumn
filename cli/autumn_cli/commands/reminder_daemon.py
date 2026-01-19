"""Background reminder/auto-stop worker.

This is run as a separate process so reminder scheduling can be non-blocking.

We keep it dependency-free and portable:
- Spawned via the current Python interpreter
- Communicates only via stdout/stderr (optional)

It polls timer status and optionally stops the timer after a duration.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta

import click

from ..api_client import APIClient
from ..api_client import APIError
from ..utils.duration_parse import parse_duration_to_seconds
from ..utils.notify import send_notification
from ..utils.formatters import format_duration_minutes
from ..utils.scheduler import sleep_seconds
from ..utils.reminders_registry import update_next_fire_at


@dataclass(frozen=True)
class Plan:
    session_id: int | None
    project: str
    notify_title: str
    remind_in_seconds: int | None
    remind_every_seconds: int | None
    for_seconds: int | None
    remind_message: str
    poll_seconds: int


def _is_session_active(client: APIClient, session_id: int | None) -> bool:
    """Return True only when we can confidently tell the session is active.

    The reminders worker should self-terminate when:
    - the session is stopped (inactive/end set)
    - the session is deleted / not found

    If the status check fails due to a transient error, we default to *inactive*
    after an "ok: false" response, but still treat exceptions conservatively.
    """
    # Standalone reminder (no session) -> always "active" until task done.
    if session_id is None:
        return True

    try:
        # Fetch all active sessions. This avoids ambiguity where querying by ID
        # might raise an APIError (e.g. 404) if the session is stopped, which
        # we might mistakenly swallow as a network error.
        st = client.get_timer_status(session_id=None)
        if not isinstance(st, dict):
            return False

        # If the server responded but indicates failure, assume the session isn't active.
        if not st.get("ok"):
            return False

        # Look for our session in the active list
        sessions = st.get("sessions")
        if isinstance(sessions, list):
            for s in sessions:
                if not isinstance(s, dict):
                    continue
                sid = s.get("id")
                try:
                    if sid is not None and int(sid) == int(session_id):
                        if "active" in s:
                            return bool(s.get("active"))
                        # If it's returned in the active list, treat as active.
                        return True
                except Exception:
                    continue
            # If we successfully parsed the list and didn't find it, it's not active.
            return False

        # Fallback: check legacy single-session shape or active count
        one = st.get("session")
        if isinstance(one, dict):
            try:
                sid_one = one.get("id")
                if sid_one is not None and int(sid_one) != int(session_id):
                    return False
            except Exception:
                pass
            if "active" in one:
                return bool(one.get("active"))
            return one.get("end") in (None, "")

        return bool(st.get("active", 0))

    except APIError as e:
        # If the server tells us the session doesn't exist anymore, exit.
        msg = str(e).lower()
        if "not found" in msg or "session" in msg and "not" in msg and "found" in msg:
            return False
        # Otherwise, be conservative.
        return True
    except Exception:
        # Network errors shouldn't keep stale reminders running forever.
        # But we also don't want to kill reminders on a single blip.
        # Conservative choice here: assume active.
        return True


def _elapsed_str(client: APIClient, session_id: int | None) -> str:
    if session_id is None:
        return "?"
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
@click.option("--session-id", type=int, required=False)
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
    session_id: int | None,
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

    # Schedule bookkeeping
    start_time = datetime.now()

    next_remind_dt = (
        (start_time + timedelta(seconds=float(plan.remind_in_seconds)))
        if plan.remind_in_seconds is not None
        else None
    )
    next_every_dt = (
        (start_time + timedelta(seconds=float(plan.remind_every_seconds)))
        if plan.remind_every_seconds is not None
        else None
    )
    stop_at_dt = (
        (start_time + timedelta(seconds=float(plan.for_seconds)))
        if plan.for_seconds is not None
        else None
    )

    def log(msg: str) -> None:
        if not quiet:
            click.echo(msg, err=True)

    def get_imminent_iso() -> str | None:
        cands = [
            dt for dt in [next_remind_dt, next_every_dt, stop_at_dt] if dt is not None
        ]
        if not cands:
            return None
        return min(cands).isoformat()

    log(f"[autumn] reminder-daemon started (session_id={plan.session_id})")

    # Initial registry update
    update_next_fire_at(os.getpid(), get_imminent_iso())

    while True:
        now = datetime.now()

        if not _is_session_active(client, plan.session_id):
            log("[autumn] session ended; exiting")
            update_next_fire_at(os.getpid(), None)
            return

        # Auto-stop
        if stop_at_dt is not None and now >= stop_at_dt:
            try:
                client.stop_timer(session_id=plan.session_id, note=None)
            except Exception as e:
                log(f"[autumn] auto-stop failed: {e}")
            send_notification(
                title=plan.notify_title, message=f"Auto-stopped timer: {plan.project}"
            )
            log("[autumn] auto-stopped; exiting")
            update_next_fire_at(os.getpid(), None)
            return

        # One-shot remind
        if next_remind_dt is not None and now >= next_remind_dt:
            msg = (plan.remind_message or "").format(
                project=plan.project, elapsed=_elapsed_str(client, plan.session_id)
            )
            send_notification(title=plan.notify_title, message=msg)
            next_remind_dt = None

            # If this daemon was started only for a one-shot reminder, we're done.
            if next_every_dt is None and stop_at_dt is None:
                log("[autumn] remind-in fired; exiting")
                update_next_fire_at(os.getpid(), None)
                return

            update_next_fire_at(os.getpid(), get_imminent_iso())

        # Periodic remind
        if next_every_dt is not None and now >= next_every_dt:
            msg = (plan.remind_message or "").format(
                project=plan.project, elapsed=_elapsed_str(client, plan.session_id)
            )
            send_notification(title=plan.notify_title, message=msg)

            # Wall-clock alignment: add exactly N seconds to the PREVIOUS target
            if plan.remind_every_seconds is not None:
                next_every_dt += timedelta(seconds=float(plan.remind_every_seconds))

            # If we somehow drifted more than one interval, catch up
            while (
                next_every_dt is not None
                and next_every_dt <= now
                and plan.remind_every_seconds is not None
            ):
                next_every_dt += timedelta(seconds=float(plan.remind_every_seconds))

            update_next_fire_at(os.getpid(), get_imminent_iso())

        # Sleep until the next due event, but cap by poll_seconds.
        waits: list[float] = []
        if next_remind_dt is not None and next_remind_dt > now:
            waits.append((next_remind_dt - now).total_seconds())
        if next_every_dt is not None and next_every_dt > now:
            waits.append((next_every_dt - now).total_seconds())
        if stop_at_dt is not None and stop_at_dt > now:
            waits.append((stop_at_dt - now).total_seconds())

        wake = min(waits) if waits else float(plan.poll_seconds)
        # Ensure forward progress and don't sleep longer than poll interval.
        wake = max(1.0, min(float(wake), float(plan.poll_seconds)))

        sleep_seconds(int(wake))


if __name__ == "__main__":
    # Allow `python -m autumn_cli.commands.reminder_daemon ...`
    main()
