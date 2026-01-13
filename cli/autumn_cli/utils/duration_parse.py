"""Parse human-friendly durations.

We accept compact forms:
  - `90s`, `5m`, `2h`, `1d`, `1w`
  - Combined: `1h30m`, `2h5m10s`, `1w2d`
  - Also allow spaces: `1h 30m`

Returns total seconds as an int.
"""

from __future__ import annotations

import re


_DURATION_RE = re.compile(r"(?P<num>\d+)\s*(?P<unit>[smhdw])", flags=re.IGNORECASE)


def parse_duration_to_seconds(raw: str) -> int:
    s = (raw or "").strip()
    if not s:
        raise ValueError("Empty duration")

    # allow e.g. "1:30"? not for now (keep explicit units to avoid ambiguity)

    matches = list(_DURATION_RE.finditer(s.replace(" ", "")))
    if not matches:
        raise ValueError(f"Invalid duration: {raw}")

    # Ensure we consumed the full string.
    consumed = "".join(m.group(0) for m in matches)
    if consumed.lower() != s.replace(" ", "").lower():
        raise ValueError(f"Invalid duration: {raw}")

    mult = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 7 * 86400}
    total = 0
    for m in matches:
        n = int(m.group("num"))
        u = m.group("unit").lower()
        total += n * mult[u]

    if total <= 0:
        raise ValueError("Duration must be > 0")

    return int(total)

