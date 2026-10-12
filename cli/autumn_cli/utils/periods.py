"""Shared period and date parsing utilities.

We keep this consistent across commands (log, chart, etc.).

Contract:
- Input: period string (case-insensitive, short aliases accepted)
- Output: (start_date, end_date) as YYYY-MM-DD strings
- If period == 'all': returns (None, None)

If start_date/end_date are explicitly provided by the caller, they should take
precedence; this module is only for deriving dates from a period choice.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Optional, Tuple


PERIODS = (
    "today",
    "yesterday",
    "day",
    "week",
    "fortnight",
    "month",
    "lunar cycle",
    "quarter",
    "year",
    "all",
)

# Shorthands users reach for; values are canonical period names.
PERIOD_ALIASES = {
    "d": "day",
    "w": "week",
    "7d": "week",
    "2w": "fortnight",
    "14d": "fortnight",
    "m": "month",
    "30d": "month",
    "lunar": "lunar cycle",
    "lunar-cycle": "lunar cycle",
    "lunar_cycle": "lunar cycle",
    "q": "quarter",
    "y": "year",
    "ever": "all",
}

_WEEKDAYS = {
    "mon": 0, "monday": 0,
    "tue": 1, "tues": 1, "tuesday": 1,
    "wed": 2, "wednesday": 2,
    "thu": 3, "thur": 3, "thurs": 3, "thursday": 3,
    "fri": 4, "friday": 4,
    "sat": 5, "saturday": 5,
    "sun": 6, "sunday": 6,
}

_AGO_RE = re.compile(r"^(\d+)\s*([a-z]+)\s+ago$")


def normalize_period(period: Optional[str]) -> Optional[str]:
    """Return the canonical period name, or None if ``period`` is not one."""
    if not period:
        return None
    p = " ".join(period.strip().lower().split())
    p = PERIOD_ALIASES.get(p, p)
    return p if p in PERIODS else None


def period_to_dates(period: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    p = normalize_period(period)
    if not p or p == "all":
        return None, None

    today = date.today()
    end = today.strftime("%Y-%m-%d")

    if p in ("day", "today"):
        start = end
    elif p == "yesterday":
        start = end = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    elif p == "week":
        start = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    elif p == "fortnight":
        start = (today - timedelta(days=14)).strftime("%Y-%m-%d")
    elif p in ("month", "lunar cycle"):
        start = (today - timedelta(days=30)).strftime("%Y-%m-%d")
    elif p == "quarter":
        quarter_start_month = ((today.month - 1) // 3) * 3 + 1
        start = today.replace(month=quarter_start_month, day=1).strftime("%Y-%m-%d")
    else:  # year
        start = today.replace(month=1, day=1).strftime("%Y-%m-%d")

    return start, end


def parse_date_arg(raw: str, *, today: Optional[date] = None) -> str:
    """Parse a user-supplied filter date into ``YYYY-MM-DD``.

    Accepts ``YYYY-MM-DD`` (and the legacy ``MM-DD-YYYY``), ``today``,
    ``yesterday``, weekday names (the most recent one, today included),
    ``3d ago`` / ``2 weeks ago``, and offsets such as ``-7d`` or
    ``today-2w``. Raises ValueError for anything else.
    """
    s = " ".join((raw or "").strip().lower().split())
    if not s:
        raise ValueError("Empty date")
    base = today or date.today()

    for fmt in ("%Y-%m-%d", "%m-%d-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    if s in _WEEKDAYS:
        days_back = (base.weekday() - _WEEKDAYS[s]) % 7
        return (base - timedelta(days=days_back)).strftime("%Y-%m-%d")

    ago = _AGO_RE.match(s)
    if ago:
        s = f"-{ago.group(1)}{ago.group(2)}"

    from .datetime_parse import parse_user_datetime

    now = datetime.combine(base, datetime.now().time())
    try:
        parsed = parse_user_datetime(s, now=now).dt
    except ValueError:
        raise ValueError(
            f"Could not understand date '{raw}'. Use YYYY-MM-DD, today, "
            "yesterday, a weekday, '3d ago', or an offset like -2w."
        ) from None
    return parsed.strftime("%Y-%m-%d")
