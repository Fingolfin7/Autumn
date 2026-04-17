from click.testing import CliRunner

import autumn_cli.config as cfg
from autumn_cli.cli import cli


def test_auth_accounts_lists_saved_accounts(tmp_path, monkeypatch):
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
    cfg.switch_account("alice")

    runner = CliRunner()
    result = runner.invoke(cli, ["auth", "accounts"])

    assert result.exit_code == 0
    assert "Base URL: https://autumn.example" in result.output
    assert "* alice: alice (alice@example.com)" in result.output
    assert "  bob: bob (bob@example.com)" in result.output


def test_auth_switch_changes_active_account(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(cfg, "CONFIG_FILE", tmp_path / "config.yaml")

    cfg.save_account(account_name="alice", api_key="token-a", user={"username": "alice"})
    cfg.save_account(account_name="bob", api_key="token-b", user={"username": "bob"})
    cfg.switch_account("alice")

    monkeypatch.setattr(
        "autumn_cli.cli._clear_auth_caches",
        lambda: None,
    )

    class _FakeClient:
        def get_cached_me(self, ttl_seconds=0, refresh=True):
            return {"user": {"username": "bob"}}

    monkeypatch.setattr("autumn_cli.cli.APIClient", _FakeClient)

    runner = CliRunner()
    result = runner.invoke(cli, ["auth", "switch", "bob"])

    assert result.exit_code == 0
    assert "Switched to bob (bob)." in result.output
    assert cfg.get_active_account_name() == "bob"
    assert cfg.get_api_key() == "token-b"


def test_auth_switch_unknown_account_errors(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(cfg, "CONFIG_FILE", tmp_path / "config.yaml")

    runner = CliRunner()
    result = runner.invoke(cli, ["auth", "switch", "missing"])

    assert result.exit_code != 0
    assert "Unknown account 'missing'" in result.output


def test_auth_status_counts_legacy_single_account_config(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(cfg, "CONFIG_FILE", tmp_path / "config.yaml")

    cfg.set_base_url("https://autumn.example")
    cfg.set_api_key("legacy-token")
    cfg.save_config(
        {
            **cfg.load_config(),
            "user_cache": {
                "fetched_at": "2026-04-17T10:00:00+00:00",
                "user": {"username": "alice", "email": "alice@example.com"},
            },
        }
    )

    class _FakeClient:
        def get_timer_status(self):
            return {"ok": True}

    monkeypatch.setattr("autumn_cli.cli.APIClient", _FakeClient)

    runner = CliRunner()
    result = runner.invoke(cli, ["auth", "status"])

    assert result.exit_code == 0
    assert "Active account: alice" in result.output
    assert "Saved accounts: 1" in result.output


def test_auth_accounts_lists_legacy_single_account_config(tmp_path, monkeypatch):
    monkeypatch.setattr(cfg, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(cfg, "CONFIG_FILE", tmp_path / "config.yaml")

    cfg.set_base_url("https://autumn.example")
    cfg.set_api_key("legacy-token")
    cfg.save_config(
        {
            **cfg.load_config(),
            "user_cache": {
                "fetched_at": "2026-04-17T10:00:00+00:00",
                "user": {"username": "alice", "email": "alice@example.com"},
            },
        }
    )

    runner = CliRunner()
    result = runner.invoke(cli, ["auth", "accounts"])

    assert result.exit_code == 0
    assert "* alice: alice (alice@example.com)" in result.output
