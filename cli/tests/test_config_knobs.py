import autumn_cli.config as cfg


def test_greeting_weights_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(cfg, "CONFIG_FILE", tmp_path / "config.yaml")

    # defaults
    assert 0.0 <= cfg.get_greeting_activity_weight() <= 1.0
    assert 0.0 <= cfg.get_greeting_moon_cameo_weight() <= 1.0

    cfg.set_greeting_activity_weight(0.9)
    cfg.set_greeting_moon_cameo_weight(0.05)

    assert cfg.get_greeting_activity_weight() == 0.9
    assert cfg.get_greeting_moon_cameo_weight() == 0.05


def test_set_config_value_dotted_path(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(cfg, "CONFIG_FILE", tmp_path / "config.yaml")

    cfg.set_config_value("a.b.c", 123)
    assert cfg.get_config_value("a.b.c") == 123

