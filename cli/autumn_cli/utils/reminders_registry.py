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
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List
from ..config import CONFIG_DIR, load_config, save_config


REMINDERS_FILE = CONFIG_DIR / "reminders.json"


@dataclass(frozen=True)
class ReminderEntry:
    pid: int
    session_id: int | None
    project: str
    created_at: str
    mode: str  # remind-in | remind-every | auto-stop | mixed
    status: str = "pending"  # pending | firing | completed
    remind_in: str | None = None
    remind_every: str | None = None
    auto_stop_for: str | None = None
    remind_poll: str | None = None
    next_fire_at: str | None = None
    remind_message: str | None = None
    notify_title: str | None = None


def _now_iso() -> str:
    return datetime.now().isoformat()


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


def _session_active(session_id: int | None) -> bool:
    """Check if a session is currently active on the backend."""
    if session_id is None:
        # Standalone reminder (not attached to a session) -> always "active"
        # (The daemon itself will exit if it finishes its task)
        return True

    try:
        from ..api_client import APIClient, APIError

        client = APIClient()
    except Exception:
        # If we can't create a client, be conservative and assume active.
        return True

    try:
        # Use unfiltered status check (list all active) to handle stopped sessions robustly.
        st = client.get_timer_status(session_id=None)
        if not isinstance(st, dict) or not st.get("ok"):
            return False

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
            # Not found in active list -> Inactive
            return False

        # Fallback: check legacy single-session shape
        one = st.get("session")
        if isinstance(one, dict):
            if "active" in one:
                return bool(one.get("active"))
            return one.get("end") in (None, "")

        return bool(st.get("active", 0))
    except Exception as e:
        # If the backend raises for "session not found", prune.
        try:
            from ..api_client import APIError

            if isinstance(e, APIError):
                msg = str(e).lower()
                if "not found" in msg:
                    return False
        except Exception:
            pass

        # Otherwise, if we can't check, don't prune.
        return True


def load_entries(*, prune_dead: bool = True) -> List[ReminderEntry]:
    # 1. Load from reminders.json if exists
    raw_list = []
    if REMINDERS_FILE.exists():
        try:
            with open(REMINDERS_FILE, "r") as f:
                raw_list = json.load(f)
        except Exception:
            raw_list = []

    # 2. Migration: Check config.yaml for legacy reminders
    cfg = load_config() or {}
    legacy_reminders = cfg.get("reminders")
    migrated = False
    if legacy_reminders and isinstance(legacy_reminders, list):
        # Merge legacy into raw_list (avoid duplicates later)
        raw_list.extend(legacy_reminders)
        # Clear legacy and save config
        del cfg["reminders"]
        save_config(cfg)
        migrated = True

    if not isinstance(raw_list, list):
        raw_list = []

    # Parse entries
    entries: List[ReminderEntry] = []

    for e in raw_list:
        if not isinstance(e, dict):
            continue
        try:
            pid_raw = e.get("pid")
            if pid_raw is None:
                continue
            sid_raw = e.get("session_id")
            entry = ReminderEntry(
                pid=int(pid_raw),
                session_id=int(sid_raw) if sid_raw is not None else None,
                project=str(e.get("project") or ""),
                created_at=str(e.get("created_at") or ""),
                mode=str(e.get("mode") or ""),
                status=str(e.get("status") or "pending"),
                remind_in=(str(e.get("remind_in")) if e.get("remind_in") else None),
                remind_every=(
                    str(e.get("remind_every")) if e.get("remind_every") else None
                ),
                auto_stop_for=(
                    str(e.get("auto_stop_for")) if e.get("auto_stop_for") else None
                ),
                remind_poll=(
                    str(e.get("remind_poll")) if e.get("remind_poll") else None
                ),
                next_fire_at=(
                    str(e.get("next_fire_at")) if e.get("next_fire_at") else None
                ),
                remind_message=(
                    str(e.get("remind_message")) if e.get("remind_message") else None
                ),
                notify_title=(
                    str(e.get("notify_title")) if e.get("notify_title") else None
                ),
            )

            entries.append(entry)
        except Exception:
            continue

    # De-duplicate: keep the newest per (pid, session_id) pair.
    dedup: dict[tuple[int, int | None], ReminderEntry] = {}
    for e in entries:
        key = (int(e.pid), e.session_id)
        prev = dedup.get(key)
        if prev is None or (e.created_at and e.created_at > prev.created_at):
            dedup[key] = e
    entries = list(dedup.values())

    # If we migrated but no pruning happened, ensure we write to reminders.json
    if migrated and not prune_dead:
        save_entries(entries)

    if prune_dead:
        alive: List[ReminderEntry] = []

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

        if migrated or len(alive) != len(entries):
            save_entries(alive)
        return alive

    return entries


def save_entries(entries: List[ReminderEntry]) -> None:
    # Ensure config directory exists
    REMINDERS_FILE.parent.mkdir(parents=True, exist_ok=True)

    data = [
        {
            "pid": e.pid,
            "session_id": e.session_id,
            "project": e.project,
            "created_at": e.created_at,
            "mode": e.mode,
            "status": e.status,
            "remind_in": e.remind_in,
            "remind_every": e.remind_every,
            "auto_stop_for": e.auto_stop_for,
            "remind_poll": e.remind_poll,
            "next_fire_at": e.next_fire_at,
            "remind_message": e.remind_message,
            "notify_title": e.notify_title,
        }
        for e in entries
    ]
    with open(REMINDERS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def add_entry(
    *,
    pid: int,
    session_id: int | None,
    project: str,
    mode: str,
    remind_in: str | None = None,
    remind_every: str | None = None,
    auto_stop_for: str | None = None,
    remind_poll: str | None = None,
    next_fire_at: str | None = None,
    remind_message: str | None = None,
    notify_title: str | None = None,
    status: str = "pending",
) -> ReminderEntry:
    entry = ReminderEntry(
        pid=int(pid),
        session_id=int(session_id) if session_id is not None else None,
        project=project,
        created_at=_now_iso(),
        mode=mode,
        status=status,
        remind_in=remind_in,
        remind_every=remind_every,
        auto_stop_for=auto_stop_for,
        remind_poll=remind_poll,
        next_fire_at=next_fire_at,
        remind_message=remind_message,
        notify_title=notify_title,
    )

    # Don't prune here: immediately after spawning, PID-liveness checks can race on some platforms.
    entries = load_entries(prune_dead=False)
    entries.append(entry)
    save_entries(entries)
    return entry


def update_next_fire_at(
    pid: int, next_fire_at: str | None, status: str | None = None
) -> None:
    entries = load_entries(prune_dead=False)
    updated = False
    for i, e in enumerate(entries):
        if int(e.pid) == int(pid):
            entries[i] = ReminderEntry(
                pid=e.pid,
                session_id=e.session_id,
                project=e.project,
                created_at=e.created_at,
                mode=e.mode,
                status=status if status is not None else e.status,
                remind_in=e.remind_in,
                remind_every=e.remind_every,
                auto_stop_for=e.auto_stop_for,
                remind_poll=e.remind_poll,
                next_fire_at=next_fire_at,
                remind_message=e.remind_message,
                notify_title=e.notify_title,
            )

            updated = True
            break

    if updated:
        save_entries(entries)


def remove_entry_by_pid(pid: int) -> bool:
    entries = load_entries(prune_dead=False)
    before = len(entries)
    entries = [e for e in entries if int(e.pid) != int(pid)]
    save_entries(entries)
    return len(entries) != before


def clear_entries() -> None:
    save_entries([])


def check_reminders_health() -> List[str]:
    """Check for missed or orphaned reminders and self-heal recurring ones."""
    from .notify import send_notification
    from .reminder_spawner import spawn_reminder
    from .duration_parse import parse_duration_to_seconds

    # We load WITHOUT pruning first, so we can detect missed ones.
    entries = load_entries(prune_dead=False)
    now = datetime.now()
    messages = []
    overdue_pids = []

    for e in entries:
        is_alive = False
        try:
            is_alive = _is_pid_alive(e.pid)
        except Exception:
            is_alive = True  # Conservative

        if not is_alive:
            # If the process is dead, and not explicitly completed, it was likely missed/lost.
            if e.status == "completed":
                overdue_pids.append(e.pid)
                continue

            missed = False
            # Fallback fire time if next_fire_at is missing (legacy migration or early death)
            fire_time_iso = e.next_fire_at
            if not fire_time_iso and e.remind_in:
                try:
                    from .duration_parse import parse_duration_to_seconds

                    secs = parse_duration_to_seconds(e.remind_in)
                    created = datetime.fromisoformat(e.created_at)
                    fire_time_iso = (created + timedelta(seconds=secs)).isoformat()
                except Exception:
                    pass

            if fire_time_iso:
                try:
                    next_fire = datetime.fromisoformat(fire_time_iso)
                    if next_fire < now:
                        # Only warn if the session is still active (or it's a standalone reminder)
                        if _session_active(e.session_id):
                            msg = (
                                f"[autumn.warn]Missed reminder:[/] [autumn.project]{e.project}[/] "
                                f"(scheduled for {next_fire.strftime('%Y-%m-%d %H:%M:%S')})"
                            )
                            messages.append(msg)

                            # System notification
                            notify_msg = f"Missed: {e.project}"
                            send_notification(
                                title=e.notify_title or "Autumn",
                                message=e.remind_message.format(
                                    project=e.project, elapsed="?"
                                )
                                if e.remind_message
                                else notify_msg,
                            )
                            missed = True
                        else:
                            # Session is stopped; reminder is implicitly cancelled.
                            # We just mark it so it gets pruned.
                            pass
                except Exception:
                    pass

            # If it wasn't strictly "missed" (no fire time found), but it's dead and not completed,
            # we can report it as "lost".
            if not missed and e.status != "completed":
                # messages.append(f"[autumn.warn]Reminder process lost:[/] [autumn.project]{e.project}[/]")
                pass

            # Self-healing for recurring reminders

            if e.remind_every:
                # Check if session is still active
                if _session_active(e.session_id):
                    try:
                        # Calculate next future fire time
                        interval = parse_duration_to_seconds(e.remind_every)
                        last_fire = (
                            datetime.fromisoformat(e.next_fire_at)
                            if e.next_fire_at
                            else datetime.fromisoformat(e.created_at)
                        )

                        next_target = last_fire + timedelta(seconds=interval)
                        while next_target < now:
                            next_target += timedelta(seconds=interval)

                        # Respawn
                        spawn_reminder(
                            project=e.project,
                            session_id=e.session_id,
                            remind_every=e.remind_every,
                            remind_message=e.remind_message
                            or "Timer running: {project} ({elapsed})",
                            notify_title=e.notify_title or "Autumn",
                            remind_poll=e.remind_poll or "30s",
                            quiet=True,
                        )

                        messages.append(
                            f"[autumn.info]Respawned recurring reminder for project [autumn.project]{e.project}[/].[/]"
                        )
                    except Exception as err:
                        messages.append(
                            f"[autumn.error]Failed to respawn reminder for {e.project}: {err}[/]"
                        )

            overdue_pids.append(e.pid)

    # Prune them now that we've reported/respawned them
    if overdue_pids:
        # Reload current entries (which may include the newly respawned ones)
        current_entries = load_entries(prune_dead=False)
        remaining = [e for e in current_entries if e.pid not in overdue_pids]
        save_entries(remaining)

    return messages


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
