"""Datetime parsing helpers for commands.

We normalize user-friendly inputs (ISO-8601, relative times, keywords) into the
server-accepted format: `%Y-%m-%d %H:%M:%S`.

This is shared by commands like `track` and any future backfill/edit actions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional


SERVER_FMT = "%Y-%m-%d %H:%M:%S"


@dataclass(frozen=True)
class ParseResult:
    dt: datetime
    source: str


def parse_user_datetime(raw: str, *, now: Optional[datetime] = None) -> ParseResult:
    """Parse a datetime string.

    Accepted inputs:
      - Absolute: `YYYY-MM-DD`, `YYYY-MM-DD HH:MM[:SS[.ffffff]]`, ISO forms with `T`.
      - Timezone: `Z` or `±HH:MM` suffixes (converted to *local* then tz dropped).
      - Keywords:
          - `now`
          - `today` (midnight local)
          - `yesterday` (midnight local)
      - Relative offsets (applies to now if no base is specified):
          - `+5m`, `-2h`, `-1d`, `+30s`
      - Base + offset:
          - `now-5m`, `today+2h`, `2026-01-10 12:00+90m`

    Returns a timezone-naive datetime in local time.
    """

    s = (raw or "").strip()
    if not s:
        raise ValueError("Empty datetime")

    base_now = (now or datetime.now()).astimezone().replace(tzinfo=None)

    # Split into base + optional offset suffix.
    base_str, offset = _split_offset(s)

    base = _parse_base(base_str, now=base_now)
    if offset is not None:
        base = base + offset

    return ParseResult(dt=base, source=s)


def format_server_datetime(dt: datetime) -> str:
    """Format a datetime to the server-accepted string format."""
    if dt.tzinfo is not None:
        dt = dt.astimezone().replace(tzinfo=None)
    return dt.strftime(SERVER_FMT)


def _split_offset(s: str) -> tuple[str, Optional[timedelta]]:
    """Return (base, offset) where offset is a timedelta or None.

    Recognizes a trailing `(+|-)<int><unit>` where unit is one of s/m/h/d/w.
    """

    import re

    m = re.fullmatch(r"(.+?)([+-])(\d+)([smhdw])", s.strip(), flags=re.IGNORECASE)
    if not m:
        # Also support pure offset like `-5m` or `+2h`.
        m2 = re.fullmatch(r"([+-])(\d+)([smhdw])", s.strip(), flags=re.IGNORECASE)
        if not m2:
            return s, None
        sign, amount_s, unit = m2.group(1), m2.group(2), m2.group(3)
        delta = _offset_to_delta(sign, amount_s, unit)
        return "now", delta

    base, sign, amount_s, unit = m.group(1).strip(), m.group(2), m.group(3), m.group(4)
    delta = _offset_to_delta(sign, amount_s, unit)
    return base, delta


def _offset_to_delta(sign: str, amount_s: str, unit: str) -> timedelta:
    amount = int(amount_s)
    unit = unit.lower()
    seconds = {
        "s": 1,
        "m": 60,
        "h": 3600,
        "d": 86400,
        "w": 7 * 86400,
    }[unit] * amount
    delta = timedelta(seconds=seconds)
    return delta if sign == "+" else -delta


def _parse_base(base_str: str, *, now: datetime) -> datetime:
    lower = base_str.strip().lower()

    if lower in {"now"}:
        return now

    if lower in {"today"}:
        return now.replace(hour=0, minute=0, second=0, microsecond=0)

    if lower in {"yesterday"}:
        return (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

    # Normalize common UTC marker for Python parsing.
    candidate = base_str.strip()
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"

    # Prefer ISO parsing (handles offsets / fractional seconds)
    dt: Optional[datetime]
    try:
        dt = datetime.fromisoformat(candidate)
    except ValueError:
        dt = None

    if dt is None:
        formats = [
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
        ]
        for fmt in formats:
            try:
                dt = datetime.strptime(base_str, fmt)
                break
            except ValueError:
                continue

    if dt is None:
        raise ValueError(f"Could not parse datetime: {base_str}")

    # If timezone-aware, convert to local time then drop tzinfo.
    if dt.tzinfo is not None:
        dt = dt.astimezone().replace(tzinfo=None)

    return dt

