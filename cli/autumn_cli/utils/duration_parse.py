"""Parse human-friendly durations.

We accept compact forms:
  - `90s`, `5m`, `2h`, `1d`, `1w`
  - Combined: `1h30m`, `2h5m10s`, `1w2d`
  - Also allow spaces: `1h 30m`

Returns total seconds as an int.
"""

from __future__ import annotations

import re


_UNIT_PATTERN = r"(?:weeks?|wks?|w|days?|d|hours?|hrs?|h|minutes?|mins?|m|seconds?|secs?|s)"
_DURATION_RE = re.compile(r"(?P<num>\d+)\s*(?P<unit>" + _UNIT_PATTERN + r")", flags=re.IGNORECASE)


def parse_duration_to_seconds(raw: str) -> int:
    s = (raw or "").strip()
    if not s:
        raise ValueError("Empty duration")

    # Clean up input: remove spaces and commas to allow formats like "1 hour, 30 minutes"
    clean_s = s.replace(" ", "").replace(",", "")

    matches = list(_DURATION_RE.finditer(clean_s))
    if not matches:
        raise ValueError(f"Invalid duration: {raw}")

    # Ensure we consumed the full string.
    consumed = "".join(m.group(0) for m in matches)
    if consumed.lower() != clean_s.lower():
        raise ValueError(f"Invalid duration: {raw}")

    total = 0
    for m in matches:
        n = int(m.group("num"))
        u = m.group("unit").lower()
        
        mult = 0
        if u.startswith("w"):
            mult = 7 * 86400
        elif u.startswith("d"):
            mult = 86400
        elif u.startswith("h"):
            mult = 3600
        elif u.startswith("m"):
            mult = 60
        elif u.startswith("s"):
            mult = 1
            
        total += n * mult

    if total <= 0:

        raise ValueError("Duration must be > 0")

    return int(total)

