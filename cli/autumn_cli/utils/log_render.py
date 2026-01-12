"""Old-CLI-inspired rendering for sessions / logs.

We deliberately avoid big ASCII tables here and instead render each session as a
compact colored block. This tends to read better in terminals and matches the
"vibes" of the older implementation.

Two main render modes:
- Logs: grouped by date (date header + sessions below)
- Active timers (status): show current duration (no End time)
"""

from __future__ import annotations

from collections import OrderedDict
from datetime import datetime
from textwrap import wrap
from typing import Dict, Any, Iterable, List, Optional

from .formatters import (
    format_duration_minutes,
    format_log_date_header,
    format_time_hms,
    format_day_total_minutes,
    format_datetime,
)


def _normalize_ws(text: str) -> str:
    return (text or "").strip().replace("\r", " ").replace("\n", " ")


def _session_start_iso(session: Dict[str, Any]) -> str:
    return session.get("start") or session.get("start_time") or ""


def _session_end_iso(session: Dict[str, Any]) -> str:
    return session.get("end") or session.get("end_time") or ""


def _parse_iso(dt: str) -> Optional[datetime]:
    if not dt:
        return None
    try:
        return datetime.fromisoformat(dt.replace("Z", "+00:00"))
    except Exception:
        return None


def _session_date_key(session: Dict[str, Any]) -> str:
    """Date key for grouping. Falls back to 'Unknown date'."""
    iso = _session_start_iso(session)
    parsed = _parse_iso(iso)
    if parsed:
        return parsed.date().isoformat()
    # If the API sends a non-ISO string, try a cheap split.
    if iso and "T" in iso:
        return iso.split("T", 1)[0]
    return "Unknown date"


def _duration_minutes(session: Dict[str, Any]) -> float:
    dur = (
        session.get("dur")
        or session.get("duration_minutes")
        or session.get("elapsed_minutes")
        or session.get("elapsed")
        or 0
    )
    try:
        return float(dur or 0)
    except Exception:
        return 0.0


def _session_project(session: Dict[str, Any]) -> str:
    return session.get("project") or session.get("p") or ""


def _session_subs(session: Dict[str, Any]) -> List[str]:
    subs = session.get("subprojects") or session.get("subs") or []
    return list(subs) if subs else []


def _wrap_note(note: str, *, width: int = 90) -> List[str]:
    note = _normalize_ws(note)
    if not note:
        return []
    return wrap(note, width=width, break_long_words=False)


def _format_subs_bracketed(subs: List[str]) -> str:
    """Format subprojects as `[sub1, sub2]` with each element colored."""
    if not subs:
        return "[]"
    inner = ", ".join([f"[autumn.subproject]{s}[/]" for s in subs])
    return f"[{inner}]"


def render_session_block(session: Dict[str, Any]) -> str:
    """Render a single session entry (for logs)."""
    sid = session.get("id")
    project = session.get("p") or session.get("project") or ""
    subs = session.get("subs") or session.get("subprojects") or []

    start_raw = _session_start_iso(session)
    end_raw = session.get("end") or session.get("end_time")

    note = _normalize_ws(session.get("note") or "")

    start = format_datetime(start_raw) if start_raw else "-"
    end = format_datetime(end_raw) if end_raw else "Active"
    dur_str = format_duration_minutes(_duration_minutes(session))

    active = end_raw in (None, "", 0)
    header_style = "autumn.ok" if active else "autumn.title"

    lines = [
        f"[{header_style}]• #{sid}[/]  [autumn.project]{project}[/]  [autumn.muted]({dur_str})[/]",
        f"  [autumn.label]Start:[/] [autumn.time]{start}[/]",
        f"  [autumn.label]End:[/]   [autumn.time]{end}[/]",
    ]

    if subs:
        lines.append(f"  [autumn.label]Subs:[/]  [autumn.subproject]{', '.join(subs)}[/]")

    if note:
        lines.append(f"  [autumn.label]Note:[/]  [autumn.note]{note}[/]")

    return "\n".join(lines)


def render_active_timer_block(session: Dict[str, Any]) -> str:
    """Render a single active timer entry (for `autumn status`).

    Status only shows active timers, so we omit End and emphasize current duration.
    """
    sid = session.get("id")
    project = session.get("p") or session.get("project") or ""
    subs = session.get("subs") or session.get("subprojects") or []

    start_raw = _session_start_iso(session)
    note = _normalize_ws(session.get("note") or "")

    start = format_datetime(start_raw) if start_raw else "-"
    dur_str = format_duration_minutes(_duration_minutes(session))

    lines = [
        f"[autumn.ok]▶ #{sid}[/]  [autumn.project]{project}[/]  [autumn.ok]{dur_str}[/]",
        f"  [autumn.label]Started:[/] [autumn.time]{start}[/]",
    ]

    if subs:
        lines.append(f"  [autumn.label]Subs:[/]    [autumn.subproject]{', '.join(subs)}[/]")
    if note:
        lines.append(f"  [autumn.label]Note:[/]    [autumn.note]{note}[/]")

    return "\n".join(lines)


def render_sessions_list(sessions: Iterable[Dict[str, Any]]) -> str:
    """Render logs grouped by date header in the old CLI style."""
    sessions_list = list(sessions)
    if not sessions_list:
        return "[autumn.muted]No sessions found.[/]"

    grouped: "OrderedDict[str, List[Dict[str, Any]]]" = OrderedDict()
    day_totals: Dict[str, float] = {}

    for s in sessions_list:
        key = _session_date_key(s)
        grouped.setdefault(key, []).append(s)
        day_totals[key] = day_totals.get(key, 0.0) + _duration_minutes(s)

    lines: List[str] = []

    first_header = True
    for date_key in reversed(list(grouped.keys())):
        day_sessions = grouped[date_key]
        header = format_log_date_header(date_key)
        total_str = format_day_total_minutes(day_totals.get(date_key, 0.0))

        # Blank line above each new date header (except the first)
        if not first_header:
            lines.append("")
        first_header = False

        # Date header should be plain (uncolored) text, but underlined. Day total stays blue.
        lines.append(f"[underline]{header}[/] [autumn.time]({total_str})[/]")

        def _sort_key(sess: Dict[str, Any]):
            end_iso = _session_end_iso(sess)
            start_iso = _session_start_iso(sess)
            return end_iso or start_iso

        for s in sorted(day_sessions, key=_sort_key, reverse=True):
            start = format_time_hms(_session_start_iso(s))
            end = format_time_hms(_session_end_iso(s))
            dur_str = format_duration_minutes(_duration_minutes(s))
            project = _session_project(s)
            subs = _session_subs(s)
            note = _normalize_ws(s.get("note") or "")

            subs_bracket = _format_subs_bracketed(subs)

            base = (
                f"[autumn.time]{start}[/] to [autumn.time]{end}[/]\t"
                f"{dur_str}  [autumn.project]{project}[/] "
                f"{subs_bracket}"
            )

            if not note:
                lines.append(base)
                continue

            wrapped = _wrap_note(note, width=90)
            # First line keeps the arrow; subsequent lines indent under the note.
            lines.append(base + f" -> [autumn.note]{wrapped[0]}[/]")
            for extra in wrapped[1:]:
                lines.append(f"{' ' * 6}[autumn.note]{extra}[/]")

    return "\n".join(lines)


def render_active_timers_list(sessions: Iterable[Dict[str, Any]]) -> str:
    """Render active timer status in the old CLI style."""
    sessions_list = list(sessions)
    if not sessions_list:
        return "[autumn.muted]No active timers.[/]"

    lines: List[str] = []
    for s in sessions_list:
        project = _session_project(s)
        subs = _session_subs(s)
        dur_str = format_duration_minutes(_duration_minutes(s))

        subs_bracket = _format_subs_bracketed(subs)

        lines.append(
            f"Started [autumn.project]{project}[/] {subs_bracket}, "
            f"[autumn.time]{dur_str}[/] ago"
        )

    return "\n".join(lines)
