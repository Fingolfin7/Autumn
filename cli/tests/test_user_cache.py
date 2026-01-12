from autumn_cli.utils.user_cache import save_cached_user, load_cached_user, clear_cached_user


def test_user_cache_roundtrip(tmp_path, monkeypatch):
    # Redirect config path by monkeypatching module vars
    import autumn_cli.config as cfg

    monkeypatch.setattr(cfg, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(cfg, "CONFIG_FILE", tmp_path / "config.yaml")

    clear_cached_user()

    user = {"username": "alice", "email": "a@example.com"}
    save_cached_user(user)

    snap = load_cached_user(ttl_seconds=3600)
    assert snap is not None
    assert snap.user["username"] == "alice"

