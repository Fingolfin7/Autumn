"""Datetime parsing helpers for commands.

We normalize user-friendly inputs (ISO-8601, relative times, keywords) into the
server-accepted format: `%Y-%m-%d %H:%M:%S`.

This is shared by commands like `track` and any future backfill/edit actions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from dateutil.relativedelta import relativedelta, MO, TU, WE, TH, FR, SA, SU


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
          - `tomorrow` (midnight local)
          - `monday`, `tuesday`, ...
          - `next monday`, `next tue`, ...
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

    Recognizes a trailing `(+|-)<int><unit>` where unit is one of s/m/h/d/w (or verbose).
    """

    unit_pat = (
        r"(?:weeks?|wks?|w|days?|d|hours?|hrs?|h|minutes?|mins?|m|seconds?|secs?|s)"
    )

    m = re.fullmatch(
        r"(.+?)([+-])(\d+)(" + unit_pat + r")", s.strip(), flags=re.IGNORECASE
    )
    if not m:
        # Also support pure offset like `-5m` or `+2h`.
        m2 = re.fullmatch(
            r"([+-])(\d+)(" + unit_pat + r")", s.strip(), flags=re.IGNORECASE
        )
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

    mult = 0
    if unit.startswith("w"):
        mult = 7 * 86400
    elif unit.startswith("d"):
        mult = 86400
    elif unit.startswith("h"):
        mult = 3600
    elif unit.startswith("m"):
        mult = 60
    elif unit.startswith("s"):
        mult = 1

    seconds = mult * amount
    delta = timedelta(seconds=seconds)
    return delta if sign == "+" else -delta


def _parse_base(base_str: str, *, now: datetime) -> datetime:
    lower = base_str.strip().lower()

    if lower in {"now"}:
        return now

    if lower in {"today"}:
        return now.replace(hour=0, minute=0, second=0, microsecond=0)

    if lower in {"yesterday"}:
        return (now - timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

    if lower in {"tomorrow"}:
        return (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

    # tomorrow <time>
    if lower.startswith("tomorrow "):
        time_part = lower[9:].strip()
        dt = now + timedelta(days=1)
        # Use same time-only formats
        time_only_formats = ["%H:%M:%S", "%H:%M", "%I:%M%p", "%I%p"]
        parsed_time = None
        for fmt in time_only_formats:
            try:
                parsed_time = datetime.strptime(time_part, fmt).time()
                break
            except ValueError:
                continue
        if parsed_time:
            return dt.replace(
                hour=parsed_time.hour,
                minute=parsed_time.minute,
                second=parsed_time.second,
                microsecond=0,
            )

    # Weekday handling

    weekdays = {
        "mon": MO,
        "monday": MO,
        "tue": TU,
        "tuesday": TU,
        "wed": WE,
        "wednesday": WE,
        "thu": TH,
        "thursday": TH,
        "fri": FR,
        "friday": FR,
        "sat": SA,
        "saturday": SA,
        "sun": SU,
        "sunday": SU,
    }

    # "next <weekday>" or just "<weekday>"
    target_weekday = None
    is_next = False

    if lower.startswith("next "):
        is_next = True
        day_part = lower[5:].strip()
    else:
        day_part = lower

    if day_part in weekdays:
        target_weekday = weekdays[day_part]

        # relativedelta(weekday=MO(1)) means "next Monday" (or today if it's Monday)
        # We want "next Thursday" to always be in the future.
        if is_next:
            dt = now + relativedelta(weekday=target_weekday(+1))
            # If relativedelta gave us today, we want the *next* one
            if dt.date() <= now.date():
                dt = now + relativedelta(weekday=target_weekday(+2))
        else:
            dt = now + relativedelta(weekday=target_weekday(+1))

        return dt.replace(hour=0, minute=0, second=0, microsecond=0)

    # Handle "weekday time" e.g. "thursday 14:30"
    m_day_time = re.match(
        r"(next\s+)?(" + "|".join(weekdays.keys()) + r")\s+(.+)", lower
    )
    if m_day_time:
        is_next = bool(m_day_time.group(1))
        day_part = m_day_time.group(2)
        time_part = m_day_time.group(3)

        target_weekday = weekdays[day_part]
        if is_next:
            dt = now + relativedelta(weekday=target_weekday(+1))
            if dt.date() <= now.date():
                dt = now + relativedelta(weekday=target_weekday(+2))
        else:
            dt = now + relativedelta(weekday=target_weekday(+1))

        # Now parse the time_part and apply it to dt
        # We can try to parse it as a time-only format
        time_only_formats = [
            "%H:%M:%S",
            "%H:%M",
            "%I:%M%p",
            "%I%p",
        ]
        parsed_time = None
        for fmt in time_only_formats:
            try:
                parsed_time = datetime.strptime(time_part, fmt).time()
                break
            except ValueError:
                continue

        if parsed_time:
            dt = dt.replace(
                hour=parsed_time.hour,
                minute=parsed_time.minute,
                second=parsed_time.second,
                microsecond=0,
            )
            # If we didn't use "next" and the time is already passed today, move to next week?
            # Actually, "thursday 10am" said on Thursday 11am usually means NEXT Thursday.
            if not is_next and dt < now:
                dt += relativedelta(weeks=1)
            return dt

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

    # Try time-only formats (implies today or tomorrow)
    time_only_formats = [
        "%H:%M:%S",
        "%H:%M",
        "%I:%M%p",  # 5:30PM
        "%I%p",  # 5PM
    ]
    for fmt in time_only_formats:
        try:
            t = datetime.strptime(base_str, fmt).time()
            # Combine with today
            dt = now.replace(
                hour=t.hour, minute=t.minute, second=t.second, microsecond=0
            )
            # If in the past, move to tomorrow
            if dt < now:
                dt += timedelta(days=1)
            return dt
        except ValueError:
            continue

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
