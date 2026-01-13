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
            )
            entries.append(entry)
        except Exception:
            continue

    # If we detected a non-list/invalid structure, ensure we write back a clean list.
    if not isinstance(raw, list):
        save_entries(entries)

    if prune_dead:
        alive: List[ReminderEntry] = []
        for e in entries:
            try:
                if _is_pid_alive(e.pid):
                    alive.append(e)
            except Exception:
                # Be conservative: if we cannot check, keep the entry.
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
        }
        for e in entries
    ]
    save_config(cfg)


def add_entry(*, pid: int, session_id: int, project: str, mode: str) -> ReminderEntry:
    entry = ReminderEntry(pid=int(pid), session_id=int(session_id), project=project, created_at=_now_iso(), mode=mode)
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
