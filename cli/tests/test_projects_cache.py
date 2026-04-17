"""Tests for the projects cache module."""

import autumn_cli.config as cfg
from autumn_cli.utils.projects_cache import (
    load_cached_projects,
    save_cached_projects,
    clear_cached_projects,
)


def test_projects_cache_roundtrip_active_account_scope(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(cfg, "CONFIG_FILE", tmp_path / "config.yaml")

    import autumn_cli.utils.projects_cache as pc

    pc._mem_snapshot = None
    cfg.save_account(account_name="alice", api_key="token-a", user={"username": "alice"})

    projects = [
        {"name": "Project A", "status": "active", "description": "Test project"},
        {"name": "Project B", "status": "paused", "description": ""},
    ]
    save_cached_projects(projects)

    snap = load_cached_projects(ttl_seconds=300)
    assert snap is not None
    assert len(snap.projects) == 2

    pc._mem_snapshot = None
    snap = load_cached_projects(ttl_seconds=300)
    assert snap is not None
    assert snap.projects[0]["name"] == "Project A"


def test_projects_cache_legacy_schema_migrates_on_load(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(cfg, "CONFIG_FILE", tmp_path / "config.yaml")

    import autumn_cli.utils.projects_cache as pc

    pc._mem_snapshot = None
    cfg.save_config(
        {
            "api_key": "token-a",
            "base_url": "https://autumn.example",
            "user_cache": {
                "fetched_at": "2026-04-17T10:00:00+00:00",
                "user": {"username": "alice"},
            },
            "projects_cache": {
                "fetched_at": "3026-04-17T10:00:00+00:00",
                "projects": [{"name": "Legacy", "status": "active"}],
            },
        }
    )

    stored = cfg.load_config()
    assert "projects_cache" not in stored
    assert stored["account_caches"]["alice"]["projects_cache"]["projects"][0]["name"] == "Legacy"

    snap = load_cached_projects(ttl_seconds=300)
    assert snap is not None
    assert snap.projects[0]["name"] == "Legacy"


def test_projects_cache_clear_clears_active_scope_only(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(cfg, "CONFIG_FILE", tmp_path / "config.yaml")

    import autumn_cli.utils.projects_cache as pc

    pc._mem_snapshot = None
    cfg.save_account(account_name="alice", api_key="token-a", user={"username": "alice"})
    cfg.save_account(account_name="bob", api_key="token-b", user={"username": "bob"})
    cfg.switch_account("alice")
    save_cached_projects([{"name": "Alice", "status": "active"}])
    cfg.switch_account("bob")
    save_cached_projects([{"name": "Bob", "status": "active"}])

    cfg.switch_account("alice")
    clear_cached_projects()

    stored = cfg.load_config()
    assert "projects_cache" not in stored
    assert "projects_cache" not in stored["account_caches"].get("alice", {})
    assert stored["account_caches"]["bob"]["projects_cache"]["projects"][0]["name"] == "Bob"
