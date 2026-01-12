"""Simple cache for contexts/tags discovery.

This avoids calling /api/contexts and /api/tags on every single command invocation.

Cache strategy:
- In-memory cache for the current process
- Optional persisted cache in the CLI config file (YAML) to speed up repeated calls
- TTL-based invalidation

If anything goes wrong (no config, parse issues), we fall back to live requests.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from ..config import load_config, save_config


DEFAULT_TTL_SECONDS = 300  # 5 minutes


@dataclass
class MetaSnapshot:
    contexts: List[Dict[str, Any]]
    tags: List[Dict[str, Any]]
    fetched_at: datetime


_mem_snapshot: Optional[MetaSnapshot] = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_fresh(ts: Optional[datetime], ttl_seconds: int) -> bool:
    if ts is None:
        return False
    return (_now() - ts) <= timedelta(seconds=ttl_seconds)


def load_cached_snapshot(ttl_seconds: int = DEFAULT_TTL_SECONDS) -> Optional[MetaSnapshot]:
    """Load a snapshot from in-memory first, then from persisted config."""
    global _mem_snapshot

    if _mem_snapshot is not None and _is_fresh(_mem_snapshot.fetched_at, ttl_seconds):
        return _mem_snapshot

    cfg = load_config() or {}
    meta = cfg.get("meta_cache") or {}

    try:
        fetched_at_s = meta.get("fetched_at")
        if not fetched_at_s:
            return None
        fetched_at = datetime.fromisoformat(fetched_at_s)
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=timezone.utc)

        if not _is_fresh(fetched_at, ttl_seconds):
            return None

        snap = MetaSnapshot(
            contexts=list(meta.get("contexts") or []),
            tags=list(meta.get("tags") or []),
            fetched_at=fetched_at,
        )
        _mem_snapshot = snap
        return snap
    except Exception:
        return None


def save_cached_snapshot(contexts: List[Dict[str, Any]], tags: List[Dict[str, Any]]) -> None:
    """Persist snapshot to config and in-memory."""
    global _mem_snapshot

    snap = MetaSnapshot(contexts=contexts, tags=tags, fetched_at=_now())
    _mem_snapshot = snap

    cfg = load_config() or {}
    cfg["meta_cache"] = {
        "fetched_at": snap.fetched_at.isoformat(),
        "contexts": contexts,
        "tags": tags,
    }
    save_config(cfg)


def clear_cached_snapshot() -> None:
    """Clear persisted + in-memory snapshot."""
    global _mem_snapshot
    _mem_snapshot = None

    cfg = load_config() or {}
    if "meta_cache" in cfg:
        cfg.pop("meta_cache", None)
        save_config(cfg)
