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


def test_accounts_roundtrip_and_switch_share_global_base_url(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(cfg, "CONFIG_FILE", tmp_path / "config.yaml")

    cfg.set_base_url("https://autumn.example")
    cfg.save_account(
        account_name="alice",
        api_key="token-a",
        user={"username": "alice", "email": "alice@example.com"},
    )
    cfg.save_account(
        account_name="bob",
        api_key="token-b",
        user={"username": "bob", "email": "bob@example.com"},
    )

    assert cfg.get_active_account_name() == "bob"
    assert cfg.get_api_key() == "token-b"
    assert cfg.get_base_url() == "https://autumn.example"

    cfg.switch_account("alice")

    assert cfg.get_active_account_name() == "alice"
    assert cfg.get_api_key() == "token-a"
    assert cfg.get_base_url() == "https://autumn.example"


def test_remove_active_account_promotes_next_saved_account(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(cfg, "CONFIG_FILE", tmp_path / "config.yaml")

    cfg.save_account(account_name="alice", api_key="token-a", user={"username": "alice"})
    cfg.save_account(account_name="bob", api_key="token-b", user={"username": "bob"})

    removed = cfg.remove_account("bob")

    assert removed is True
    assert cfg.get_active_account_name() == "alice"
    assert cfg.get_api_key() == "token-a"


def test_legacy_cache_and_aliases_migrate_into_active_account_scope(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(cfg, "CONFIG_FILE", tmp_path / "config.yaml")

    cfg.save_config(
        {
            "aliases": {"projects": {"aw": "AutumnWeb"}},
            "meta_cache": {"fetched_at": "2026-04-17T10:00:00+00:00", "contexts": [], "tags": []},
        }
    )
    cfg.set_api_key("token-a")
    cfg.save_config(
        {
            **cfg.load_config(),
            "user_cache": {
                "fetched_at": "2026-04-17T10:00:00+00:00",
                "user": {"username": "alice"},
            },
        }
    )

    migrated = cfg.load_config()
    legacy = cfg.load_account_cache("meta_cache")
    assert legacy is not None
    assert legacy["fetched_at"] == "2026-04-17T10:00:00+00:00"

    cfg.save_account_cache(
        "meta_cache",
        {"fetched_at": "2026-04-17T11:00:00+00:00", "contexts": [{"name": "Deep"}], "tags": []},
    )

    stored = cfg.load_config()
    assert migrated["active_account"] == "alice"
    assert "aliases" not in stored
    assert "meta_cache" not in stored
    assert stored["account_aliases"]["alice"]["projects"]["aw"] == "AutumnWeb"
    assert stored["account_caches"]["alice"]["meta_cache"]["fetched_at"] == "2026-04-17T11:00:00+00:00"

    cfg.clear_account_cache("meta_cache")
    stored_after_clear = cfg.load_config()
    assert "account_caches" not in stored_after_clear or "meta_cache" not in stored_after_clear["account_caches"].get("alice", {})
