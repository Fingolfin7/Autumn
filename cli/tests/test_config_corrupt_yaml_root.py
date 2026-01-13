from __future__ import annotations

from autumn_cli import config as cfg


def test_load_config_returns_dict_on_non_dict_yaml(monkeypatch, tmp_path):
    # simulate a config file whose YAML root is a list
    p = tmp_path / "config.yaml"
    p.write_text("- not: a-dict\n")

    monkeypatch.setattr(cfg, "CONFIG_FILE", p)
    monkeypatch.setattr(cfg, "CONFIG_DIR", tmp_path)

    loaded = cfg.load_config()
    assert isinstance(loaded, dict)
    assert loaded == {}

