"""Cache for /api/me user metadata.

Used for greetings and account display.
Stored in the same YAML config file as api_key/base_url.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from ..config import load_config, save_config


DEFAULT_TTL_SECONDS = 3600  # 1 hour


@dataclass
class UserSnapshot:
    user: Dict[str, Any]
    fetched_at: datetime


_mem_snapshot: Optional[UserSnapshot] = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_fresh(ts: Optional[datetime], ttl_seconds: int) -> bool:
    if ts is None:
        return False
    return (_now() - ts) <= timedelta(seconds=ttl_seconds)


def load_cached_user(ttl_seconds: int = DEFAULT_TTL_SECONDS) -> Optional[UserSnapshot]:
    global _mem_snapshot

    if _mem_snapshot is not None and _is_fresh(_mem_snapshot.fetched_at, ttl_seconds):
        return _mem_snapshot

    cfg = load_config() or {}
    block = cfg.get("user_cache") or {}

    try:
        fetched_at_s = block.get("fetched_at")
        if not fetched_at_s:
            return None
        fetched_at = datetime.fromisoformat(fetched_at_s)
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=timezone.utc)

        if not _is_fresh(fetched_at, ttl_seconds):
            return None

        snap = UserSnapshot(user=dict(block.get("user") or {}), fetched_at=fetched_at)
        _mem_snapshot = snap
        return snap
    except Exception:
        return None


def save_cached_user(user: Dict[str, Any]) -> None:
    global _mem_snapshot

    snap = UserSnapshot(user=user, fetched_at=_now())
    _mem_snapshot = snap

    cfg = load_config() or {}
    cfg["user_cache"] = {
        "fetched_at": snap.fetched_at.isoformat(),
        "user": user,
    }
    save_config(cfg)


def clear_cached_user() -> None:
    global _mem_snapshot
    _mem_snapshot = None

    cfg = load_config() or {}
    if "user_cache" in cfg:
        cfg.pop("user_cache", None)
        save_config(cfg)

