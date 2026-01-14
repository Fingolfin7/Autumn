import autumn_cli.config as cfg


def test_greeting_weights_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(cfg, "CONFIG_FILE", tmp_path / "config.yaml")

    # defaults
    assert 0.0 <= cfg.get_greeting_general_weight() <= 1.0
    assert 0.0 <= cfg.get_greeting_activity_weight() <= 1.0
    assert 0.0 <= cfg.get_greeting_moon_cameo_weight() <= 1.0

    cfg.set_greeting_general_weight(0.4)
    cfg.set_greeting_activity_weight(0.4)
    cfg.set_greeting_moon_cameo_weight(0.05)

    assert cfg.get_greeting_general_weight() == 0.4
    assert cfg.get_greeting_activity_weight() == 0.4
    assert cfg.get_greeting_moon_cameo_weight() == 0.05


def test_greeting_weights_sum_clamps(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(cfg, "CONFIG_FILE", tmp_path / "config.yaml")

    cfg.set_greeting_general_weight(0.4)
    cfg.set_greeting_activity_weight(0.4)
    cfg.set_greeting_moon_cameo_weight(0.2)

    # This would make total > 1.0; it should clamp the other weights.
    cfg.set_greeting_general_weight(0.8)

    g = cfg.get_greeting_general_weight()
    a = cfg.get_greeting_activity_weight()
    m = cfg.get_greeting_moon_cameo_weight()

    assert abs(g - 0.8) < 1e-9
    assert g + a + m <= 1.0 + 1e-9



def test_set_config_value_dotted_path(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(cfg, "CONFIG_FILE", tmp_path / "config.yaml")

    cfg.set_config_value("a.b.c", 123)
    assert cfg.get_config_value("a.b.c") == 123

