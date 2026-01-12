"""Shared period parsing utilities.

We keep this consistent across commands (log, chart, etc.).

Contract:
- Input: period string (case-insensitive)
- Output: (start_date, end_date) as YYYY-MM-DD strings
- If period == 'all': returns (None, None)

If start_date/end_date are explicitly provided by the caller, they should take
precedence; this module is only for deriving dates from a period choice.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional, Tuple


def period_to_dates(period: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    if not period:
        return None, None

    p = period.strip().lower()
    if p == "all":
        return None, None

    today = date.today()
    end = today.strftime("%Y-%m-%d")

    if p == "day":
        start = today.strftime("%Y-%m-%d")
    elif p == "week":
        start = (today - timedelta(days=7)).strftime("%Y-%m-%d")
    elif p == "fortnight":
        start = (today - timedelta(days=14)).strftime("%Y-%m-%d")
    elif p == "month":
        start = (today - timedelta(days=30)).strftime("%Y-%m-%d")
    elif p == "lunar cycle":
        start = (today - timedelta(days=30)).strftime("%Y-%m-%d")
    elif p == "quarter":
        quarter_start_month = ((today.month - 1) // 3) * 3 + 1
        start = today.replace(month=quarter_start_month, day=1).strftime("%Y-%m-%d")
    elif p == "year":
        start = today.replace(month=1, day=1).strftime("%Y-%m-%d")
    else:
        # Unknown period: don't override
        return None, None

    return start, end

