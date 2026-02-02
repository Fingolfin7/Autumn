"""Simple cache for projects discovery.

This avoids calling /api/projects on every single command invocation.

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
class ProjectsSnapshot:
    projects: List[Dict[str, Any]]
    fetched_at: datetime


_mem_snapshot: Optional[ProjectsSnapshot] = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _is_fresh(ts: Optional[datetime], ttl_seconds: int) -> bool:
    if ts is None:
        return False
    return (_now() - ts) <= timedelta(seconds=ttl_seconds)


def load_cached_projects(ttl_seconds: int = DEFAULT_TTL_SECONDS) -> Optional[ProjectsSnapshot]:
    """Load a snapshot from in-memory first, then from persisted config."""
    global _mem_snapshot

    if _mem_snapshot is not None and _is_fresh(_mem_snapshot.fetched_at, ttl_seconds):
        return _mem_snapshot

    cfg = load_config() or {}
    cache = cfg.get("projects_cache") or {}

    try:
        fetched_at_s = cache.get("fetched_at")
        if not fetched_at_s:
            return None
        fetched_at = datetime.fromisoformat(fetched_at_s)
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=timezone.utc)

        if not _is_fresh(fetched_at, ttl_seconds):
            return None

        snap = ProjectsSnapshot(
            projects=list(cache.get("projects") or []),
            fetched_at=fetched_at,
        )
        _mem_snapshot = snap
        return snap
    except (ValueError, TypeError, KeyError):
        return None


def save_cached_projects(projects: List[Dict[str, Any]]) -> None:
    """Persist snapshot to config and in-memory."""
    global _mem_snapshot

    snap = ProjectsSnapshot(projects=projects, fetched_at=_now())
    _mem_snapshot = snap

    cfg = load_config() or {}
    cfg["projects_cache"] = {
        "fetched_at": snap.fetched_at.isoformat(),
        "projects": projects,
    }
    save_config(cfg)


def clear_cached_projects() -> None:
    """Clear persisted + in-memory snapshot."""
    global _mem_snapshot
    _mem_snapshot = None

    cfg = load_config() or {}
    if "projects_cache" in cfg:
        cfg.pop("projects_cache", None)
        save_config(cfg)
