"""Persisted registry of background reminder workers.

We keep a small list of spawned reminder-daemon processes in the same YAML config
file used by the CLI.

This allows commands like:
- `autumn reminders list`
- `autumn reminders stop`

Registry entries are best-effort:
- PIDs might be stale (process already exited)
- We prune dead entries on load
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List

from ..config import load_config, save_config


@dataclass(frozen=True)
class ReminderEntry:
    pid: int
    session_id: int
    project: str
    created_at: str
    mode: str  # remind-in | remind-every | auto-stop | mixed
    remind_in: str | None = None
    remind_every: str | None = None
    auto_stop_for: str | None = None
    remind_poll: str | None = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _is_pid_alive(pid: int) -> bool:
    """Best-effort PID liveness check.

    - POSIX: os.kill(pid, 0)
    - Windows: OpenProcess via ctypes

    We keep it conservative: if we can't check, assume alive.
    """

    import os

    if pid <= 0:
        return False

    if os.name != "nt":
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except Exception:
            return True

    # Windows: use ctypes OpenProcess
    try:
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        k32 = getattr(ctypes, "windll", None)
        if k32 is None:
            return True

        kernel32 = k32.kernel32
        open_process = getattr(kernel32, "OpenProcess", None)
        close_handle = getattr(kernel32, "CloseHandle", None)
        if open_process is None or close_handle is None:
            return True

        handle = open_process(PROCESS_QUERY_LIMITED_INFORMATION, 0, int(pid))
        if not handle:
            return False
        close_handle(handle)
        return True
    except Exception:
        return True


def load_entries(*, prune_dead: bool = True) -> List[ReminderEntry]:
    cfg = load_config() or {}

    # Support/repair older or corrupted shapes.
    raw = cfg.get("reminders")
    if raw is None:
        raw_list = []
    elif isinstance(raw, list):
        raw_list = raw
    else:
        # If reminders somehow got saved as a non-list (or config became a list), treat as empty and repair.
        raw_list = []

    # Parse entries
    entries: List[ReminderEntry] = []

    for e in raw_list:
        if not isinstance(e, dict):
            continue
        try:
            entry = ReminderEntry(
                pid=int(e.get("pid")),
                session_id=int(e.get("session_id")),
                project=str(e.get("project") or ""),
                created_at=str(e.get("created_at") or ""),
                mode=str(e.get("mode") or ""),
                remind_in=(str(e.get("remind_in")) if e.get("remind_in") else None),
                remind_every=(str(e.get("remind_every")) if e.get("remind_every") else None),
                auto_stop_for=(str(e.get("auto_stop_for")) if e.get("auto_stop_for") else None),
                remind_poll=(str(e.get("remind_poll")) if e.get("remind_poll") else None),
            )
            entries.append(entry)
        except Exception:
            continue

    # De-duplicate: keep the newest per (pid, session_id) pair.
    # This avoids the registry growing indefinitely if the same worker is re-added.
    dedup: dict[tuple[int, int], ReminderEntry] = {}
    for e in entries:
        key = (int(e.pid), int(e.session_id))
        prev = dedup.get(key)
        if prev is None or (e.created_at and e.created_at > prev.created_at):
            dedup[key] = e
    entries = list(dedup.values())

    # If we detected a non-list/invalid structure, ensure we write back a clean list.
    if not isinstance(raw, list):
        save_entries(entries)

    if prune_dead:
        alive: List[ReminderEntry] = []

        # Optional extra pruning: drop entries whose sessions are no longer active.
        # This covers cases where a background worker didn't exit for any reason.
        try:
            from ..api_client import APIClient, APIError

            client = APIClient()
        except Exception:
            client = None
            APIError = None  # type: ignore[assignment]

        def _session_active(session_id: int) -> bool:
            if client is None:
                return True
            try:
                st = client.get_timer_status(session_id=session_id)
                if not isinstance(st, dict) or not st.get("ok"):
                    return False

                one = st.get("session")
                if isinstance(one, dict):
                    if "active" in one:
                        return bool(one.get("active"))
                    return one.get("end") in (None, "")

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
                                return True
                        except Exception:
                            continue
                    return False

                return bool(st.get("active", 0))
            except Exception as e:
                # If the backend raises for "session not found", prune.
                if APIError is not None and isinstance(e, APIError):
                    msg = str(e).lower()
                    if "not found" in msg:
                        return False

                # Otherwise, if we can't check, don't prune.
                return True

        for e in entries:
            # Heuristic for obviously-stale placeholder test artifacts.
            # Real OS PIDs are rarely this low for long-running background workers.
            if e.pid == 999:
                continue

            # If the process is gone, prune.
            pid_check_uncertain = False
            try:
                if not _is_pid_alive(e.pid):
                    continue
            except Exception:
                # Can't check; keep and do not attempt session pruning.
                pid_check_uncertain = True

            # If PID check is uncertain, keep the entry (best-effort, conservative).
            if pid_check_uncertain:
                alive.append(e)
                continue

            # If the session is no longer active, prune.
            if not _session_active(e.session_id):
                continue

            alive.append(e)

        if len(alive) != len(entries):
            save_entries(alive)
        return alive

    return entries


def save_entries(entries: List[ReminderEntry]) -> None:
    cfg = load_config() or {}

    # If config is corrupted into a list, reset to a dict.
    if not isinstance(cfg, dict):
        cfg = {}

    cfg["reminders"] = [
        {
            "pid": e.pid,
            "session_id": e.session_id,
            "project": e.project,
            "created_at": e.created_at,
            "mode": e.mode,
            "remind_in": e.remind_in,
            "remind_every": e.remind_every,
            "auto_stop_for": e.auto_stop_for,
            "remind_poll": e.remind_poll,
        }
        for e in entries
    ]
    save_config(cfg)


def add_entry(
    *,
    pid: int,
    session_id: int,
    project: str,
    mode: str,
    remind_in: str | None = None,
    remind_every: str | None = None,
    auto_stop_for: str | None = None,
    remind_poll: str | None = None,
) -> ReminderEntry:
    entry = ReminderEntry(
        pid=int(pid),
        session_id=int(session_id),
        project=project,
        created_at=_now_iso(),
        mode=mode,
        remind_in=remind_in,
        remind_every=remind_every,
        auto_stop_for=auto_stop_for,
        remind_poll=remind_poll,
    )
    # Don't prune here: immediately after spawning, PID-liveness checks can race on some platforms.
    entries = load_entries(prune_dead=False)
    entries.append(entry)
    save_entries(entries)
    return entry


def remove_entry_by_pid(pid: int) -> bool:
    entries = load_entries(prune_dead=False)
    before = len(entries)
    entries = [e for e in entries if int(e.pid) != int(pid)]
    save_entries(entries)
    return len(entries) != before


def clear_entries() -> None:
    save_entries([])


def kill_pid(pid: int) -> bool:
    """Terminate a reminder worker by pid.

    On POSIX uses SIGTERM.
    On Windows uses taskkill fallback.
    """

    import os
    import signal
    import subprocess

    if pid <= 0:
        return False

    if os.name != "nt":
        try:
            os.kill(pid, signal.SIGTERM)
            return True
        except ProcessLookupError:
            return False
        except Exception:
            return False

    # Windows
    try:
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except Exception:
        return False
