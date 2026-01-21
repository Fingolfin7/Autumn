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
from typing import Dict, Any, Iterable, List, Optional, Union

from .formatters import (
    format_duration_minutes,
    format_log_date_header,
    format_time_hms,
    format_day_total_minutes,
    format_datetime,
    parse_utc_to_local,
)

from rich.markup import escape as rich_escape
from rich.markdown import Markdown


def _normalize_ws(text: str) -> str:
    return (text or "").strip().replace("\r", " ").replace("\n", " ")


def _session_start_iso(session: Dict[str, Any]) -> str:
    return session.get("start") or session.get("start_time") or ""


def _session_end_iso(session: Dict[str, Any]) -> str:
    return session.get("end") or session.get("end_time") or ""


def _parse_iso(dt: str) -> Optional[datetime]:
    """Parse ISO datetime string from server (UTC) to local timezone."""
    return parse_utc_to_local(dt)


def _session_date_key(session: Dict[str, Any]) -> str:
    """Date key for grouping in local timezone. Falls back to 'Unknown date'."""
    iso = _session_start_iso(session)
    parsed = _parse_iso(iso)
    if parsed:
        # Use local date for grouping
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
    # Avoid surprising breaks when the note is short; wrap only when necessary.
    if len(note) <= width:
        return [note]
    return wrap(note, width=width, break_long_words=False, break_on_hyphens=False)


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

    # Use autumn.duration for duration in single block view
    lines = [
        f"[{header_style}]• #{sid}[/]  [autumn.project]{project}[/]  [autumn.duration]({dur_str})[/]",
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
        f"[autumn.ok]▶ #{sid}[/]  [autumn.project]{project}[/]  [autumn.duration]{dur_str}[/]",
        f"  [autumn.label]Started:[/] [autumn.time]{start}[/]",
    ]


    if subs:
        lines.append(f"  [autumn.label]Subs:[/]    [autumn.subproject]{', '.join(subs)}[/]")
    if note:
        lines.append(f"  [autumn.label]Note:[/]    [autumn.note]{note}[/]")

    return "\n".join(lines)


def render_sessions_list(sessions: Iterable[Dict[str, Any]], *, markdown_notes: bool = False) -> Union[str, List[object]]:
    """Render logs grouped by date header in the old CLI style.

    Args:
        sessions: Session dicts from the API.
        markdown_notes: If True, notes are rendered as Rich Markdown blocks.

    Returns:
        Either a single markup string (default) or a list of Rich renderables
        (strings + Markdown objects) when markdown_notes is enabled.
    """

    def _markdown_note_renderable(note: str) -> object:
        """Render note Markdown using autumn.note as the base style.

        We intentionally return Rich's Markdown renderable directly.
        This preserves hyperlink metadata (OSC 8) so terminals that support it
        can show clickable links.
        """

        return Markdown(note, style="autumn.note")

    sessions_list = list(sessions)
    if not sessions_list:
        empty = "[autumn.muted]No sessions found.[/]"
        return [empty] if markdown_notes else empty

    grouped: "OrderedDict[str, List[Dict[str, Any]]]" = OrderedDict()
    day_totals: Dict[str, float] = {}

    for s in sessions_list:
        key = _session_date_key(s)
        grouped.setdefault(key, []).append(s)
        day_totals[key] = day_totals.get(key, 0.0) + _duration_minutes(s)

    items: List[object] = []

    first_header = True
    for date_key in reversed(list(grouped.keys())):
        day_sessions = grouped[date_key]
        header = format_log_date_header(date_key)
        total_str = format_day_total_minutes(day_totals.get(date_key, 0.0))

        # Blank line above each new date header (except the first)
        if not first_header:
            items.append("")
        first_header = False

        # Date header should be plain (uncolored) text, but underlined. Day total stays blue.
        items.append(f"[underline]{header}[/] [autumn.duration]({total_str})[/]")

        def _sort_key(sess: Dict[str, Any]):

            end_iso = _session_end_iso(sess)
            start_iso = _session_start_iso(sess)
            return end_iso or start_iso

        for s in sorted(day_sessions, key=_sort_key):
            start = format_time_hms(_session_start_iso(s))
            end = format_time_hms(_session_end_iso(s))
            dur_str = format_duration_minutes(_duration_minutes(s))
            project = _session_project(s)
            subs = _session_subs(s)
            note_raw = s.get("note") or ""

            subs_bracket = _format_subs_bracketed(subs)

            base = (
                f"[autumn.time]{start}[/] to [autumn.time]{end}[/]\t"
                f"{dur_str}  [autumn.project]{project}[/] "
                f"{subs_bracket}"
            )

            if not note_raw:
                items.append(base)
                continue

            if not markdown_notes:
                # Notes are sanitized to single-line text; keep them on one line for stable output.
                note = _normalize_ws(note_raw)
                items.append(
                    base
                    + f" -> [autumn.note]{rich_escape(note)}[/]"  # extra escape to avoid breaking formatting due to urls/links
                    + f"[autumn.label][/]"  # hard reset to avoid note colour bleeding
                )
                continue

            # Markdown mode: keep user's original whitespace/newlines for Markdown parsing.
            items.append(base + " ->")
            items.append(_markdown_note_renderable(note_raw))

    return items if markdown_notes else "\n".join([x for x in items if isinstance(x, str)])


def render_active_timers_list(sessions: Iterable[Dict[str, Any]]) -> str:
    """Render active timer status in the old CLI style."""
    sessions_list = list(sessions)
    if not sessions_list:
        return "[autumn.muted]No active timers.[/]"

    lines: List[str] = []
    for s in sessions_list:
        sid = s.get("id")
        sid_suffix = f"\nSession ID: #{sid}" if sid is not None else ""

        project = _session_project(s)
        subs = _session_subs(s)
        dur_str = format_duration_minutes(_duration_minutes(s))

        subs_bracket = _format_subs_bracketed(subs)

        lines.append(
            f"Started [autumn.project]{project}[/] {subs_bracket}, "
            f"[autumn.duration]{dur_str}[/] ago{sid_suffix}"
        )

    return "\n".join(lines)
