"""Debug helpers for desktop notifications.

The CLI often spawns detached background workers with stdout/stderr redirected to
/dev/null. If notifications fail, it's otherwise hard to diagnose.

This module provides a tiny, dependency-free logger:
- enabled when config key `notify.log_file` is set
- appends one line per event

We keep it separate from `notify.py` to avoid affecting runtime behavior unless
explicitly enabled.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from ..config import get_config_value


def _log_path() -> str | None:
    # Preferred: config value (dotted path)
    try:
        p = get_config_value("notify.log_file")
        if isinstance(p, str) and p.strip():
            return p.strip()
    except Exception:
        pass

    # Back-compat fallback: env var (so existing setups keep working)
    p2 = os.environ.get("AUTUMN_NOTIFY_LOG")
    if p2 is not None and p2.strip():
        return p2.strip()

    return None


def log_notify_event(message: str) -> None:
    path = _log_path()
    if not path:
        return

    try:
        ts = datetime.now(timezone.utc).isoformat()
        line = f"{ts} {message}\n"
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        # Never crash the CLI/daemon due to debug logging.
        return
