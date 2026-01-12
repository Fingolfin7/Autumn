"""Cache for recent activity snippets used in the greeting.

We keep this separate from the contexts/tags cache because it is derived from logs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from ..config import load_config, save_config


DEFAULT_TTL_SECONDS = 600  # 10 minutes


@dataclass
class ActivitySnapshot:
    info: Dict[str, Any]
    fetched_at: datetime


_mem_snapshot: Optional[ActivitySnapshot] = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_fresh(ts: Optional[datetime], ttl_seconds: int) -> bool:
    if ts is None:
        return False
    return (_now() - ts) <= timedelta(seconds=ttl_seconds)


def load_cached_activity(ttl_seconds: int = DEFAULT_TTL_SECONDS) -> Optional[ActivitySnapshot]:
    global _mem_snapshot

    if _mem_snapshot is not None and _is_fresh(_mem_snapshot.fetched_at, ttl_seconds):
        return _mem_snapshot

    cfg = load_config() or {}
    block = cfg.get("activity_cache") or {}

    try:
        fetched_at_s = block.get("fetched_at")
        if not fetched_at_s:
            return None
        fetched_at = datetime.fromisoformat(fetched_at_s)
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=timezone.utc)

        if not _is_fresh(fetched_at, ttl_seconds):
            return None

        snap = ActivitySnapshot(info=dict(block.get("info") or {}), fetched_at=fetched_at)
        _mem_snapshot = snap
        return snap
    except Exception:
        return None


def save_cached_activity(info: Dict[str, Any]) -> None:
    global _mem_snapshot

    snap = ActivitySnapshot(info=info, fetched_at=_now())
    _mem_snapshot = snap

    cfg = load_config() or {}
    cfg["activity_cache"] = {
        "fetched_at": snap.fetched_at.isoformat(),
        "info": info,
    }
    save_config(cfg)


def clear_cached_activity() -> None:
    global _mem_snapshot
    _mem_snapshot = None

    cfg = load_config() or {}
    if "activity_cache" in cfg:
        cfg.pop("activity_cache", None)
        save_config(cfg)

