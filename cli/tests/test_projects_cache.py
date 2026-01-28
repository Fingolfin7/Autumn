"""Tests for the projects cache module."""

from datetime import datetime, timezone, timedelta

import pytest

from autumn_cli.utils.projects_cache import (
    ProjectsSnapshot,
    load_cached_projects,
    save_cached_projects,
    clear_cached_projects,
    _mem_snapshot,
)


def test_projects_cache_roundtrip(tmp_path, monkeypatch):
    """Test saving and loading projects cache."""
    # Setup: use a temp config file
    config_file = tmp_path / "config.yaml"

    def fake_load_config():
        if config_file.exists():
            import yaml
            return yaml.safe_load(config_file.read_text()) or {}
        return {}

    def fake_save_config(cfg):
        import yaml
        config_file.write_text(yaml.dump(cfg))

    monkeypatch.setattr("autumn_cli.utils.projects_cache.load_config", fake_load_config)
    monkeypatch.setattr("autumn_cli.utils.projects_cache.save_config", fake_save_config)

    # Clear any existing in-memory cache
    import autumn_cli.utils.projects_cache as pc
    pc._mem_snapshot = None

    # Test saving
    projects = [
        {"name": "Project A", "status": "active", "description": "Test project"},
        {"name": "Project B", "status": "paused", "description": ""},
    ]
    save_cached_projects(projects)

    # Verify config file was written
    assert config_file.exists()

    # Test loading (should hit in-memory cache)
    snap = load_cached_projects(ttl_seconds=300)
    assert snap is not None
    assert len(snap.projects) == 2
    assert snap.projects[0]["name"] == "Project A"
    assert snap.projects[1]["name"] == "Project B"

    # Clear in-memory but keep disk cache
    pc._mem_snapshot = None

    # Test loading from disk
    snap = load_cached_projects(ttl_seconds=300)
    assert snap is not None
    assert len(snap.projects) == 2


def test_projects_cache_ttl_expiry(tmp_path, monkeypatch):
    """Test that expired cache is not returned."""
    config_file = tmp_path / "config.yaml"

    def fake_load_config():
        if config_file.exists():
            import yaml
            return yaml.safe_load(config_file.read_text()) or {}
        return {}

    def fake_save_config(cfg):
        import yaml
        config_file.write_text(yaml.dump(cfg))

    monkeypatch.setattr("autumn_cli.utils.projects_cache.load_config", fake_load_config)
    monkeypatch.setattr("autumn_cli.utils.projects_cache.save_config", fake_save_config)

    import autumn_cli.utils.projects_cache as pc
    pc._mem_snapshot = None

    # Save projects
    save_cached_projects([{"name": "Test", "status": "active"}])

    # Should load fine with normal TTL
    snap = load_cached_projects(ttl_seconds=300)
    assert snap is not None

    # Clear in-memory
    pc._mem_snapshot = None

    # Should not load with 0 TTL (expired)
    snap = load_cached_projects(ttl_seconds=0)
    assert snap is None


def test_projects_cache_clear(tmp_path, monkeypatch):
    """Test clearing the cache."""
    config_file = tmp_path / "config.yaml"

    def fake_load_config():
        if config_file.exists():
            import yaml
            return yaml.safe_load(config_file.read_text()) or {}
        return {}

    def fake_save_config(cfg):
        import yaml
        config_file.write_text(yaml.dump(cfg))

    monkeypatch.setattr("autumn_cli.utils.projects_cache.load_config", fake_load_config)
    monkeypatch.setattr("autumn_cli.utils.projects_cache.save_config", fake_save_config)

    import autumn_cli.utils.projects_cache as pc
    pc._mem_snapshot = None

    # Save projects
    save_cached_projects([{"name": "Test", "status": "active"}])

    # Verify it's there
    snap = load_cached_projects(ttl_seconds=300)
    assert snap is not None

    # Clear
    clear_cached_projects()

    # Should be gone from both memory and disk
    snap = load_cached_projects(ttl_seconds=300)
    assert snap is None
