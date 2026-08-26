"""Behavioral coverage for the fast configuration path."""

from __future__ import annotations

import autumn_cli.config as cfg


def _use_temp_config(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(cfg, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(cfg, "CONFIG_FILE", tmp_path / "config.yaml")


def test_load_config_cache_returns_independent_copies(tmp_path, monkeypatch) -> None:
    _use_temp_config(monkeypatch, tmp_path)
    cfg.save_config({"nested": {"value": 1}})

    first = cfg.load_config()
    first["nested"]["value"] = 99

    assert cfg.load_config() == {
        "nested": {"value": 1},
        "base_url": "http://localhost:8000",
    }


def test_load_config_cache_notices_external_file_change(tmp_path, monkeypatch) -> None:
    _use_temp_config(monkeypatch, tmp_path)
    cfg.save_config({"marker": "first"})
    assert cfg.load_config()["marker"] == "first"

    cfg.CONFIG_FILE.write_text("marker: second-and-longer\n", encoding="utf-8")

    assert cfg.load_config()["marker"] == "second-and-longer"
