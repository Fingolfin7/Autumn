"""Helpers for confirming server-managed timer auto-stops."""

from __future__ import annotations

from typing import Any, Callable, Optional


def _session_is_active(status: Any, session_id: Optional[int]) -> Optional[bool]:
    """Read an active flag from either supported timer-status response shape.

    ``None`` means the response could not be interpreted; callers should avoid
    turning an uncertain network response into a stop request.
    """
    if not isinstance(status, dict) or not status.get("ok"):
        return False

    session = status.get("session")
    if isinstance(session, dict):
        if "active" in session:
            return bool(session.get("active"))
        return session.get("end") in (None, "")

    sessions = status.get("sessions")
    if isinstance(sessions, list):
        for session in sessions:
            if not isinstance(session, dict):
                continue
            try:
                if session_id is not None and int(session.get("id")) != int(session_id):
                    continue
            except (TypeError, ValueError):
                continue
            return bool(session.get("active", session.get("end") in (None, "")))
        return False

    if "active" in status:
        return bool(status.get("active"))
    return None


def session_still_active_after_auto_stop(
    client: Any,
    session_id: Optional[int],
    *,
    attempts: int = 4,
    poll_seconds: int = 10,
    sleep: Callable[[int], None],
) -> bool:
    """Poll server status after an auto-stop deadline.

    Timer status checks trigger lazy expiry on the server. Return ``True`` only
    if the session remains positively active after the polling window, so the
    caller can use its single belt-and-braces ``stop_timer`` fallback.
    """
    if session_id is None:
        return False

    last_known_active = False
    for attempt in range(attempts):
        try:
            active = _session_is_active(
                client.get_timer_status(session_id=session_id), session_id
            )
        except Exception:
            active = None

        if active is False:
            return False
        if active is True:
            last_known_active = True

        if attempt < attempts - 1:
            sleep(poll_seconds)

    return last_known_active
