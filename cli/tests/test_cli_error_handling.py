from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest
import requests
from click.testing import CliRunner

import autumn_cli.config as cfg
from autumn_cli.api_client import APIClient, APIError
from autumn_cli.cli import cli, main
from autumn_cli.errors import ConfigError


class _LoginFailureClient:
    def __init__(self, *args, **kwargs):
        pass

    def get_token_with_password(self, username, password):
        raise APIError("Login failed: Unable to log in with provided credentials.")


def _disable_health_check(monkeypatch):
    monkeypatch.setattr(
        "autumn_cli.utils.reminders_registry.check_reminders_health", lambda: []
    )


def test_bad_password_is_a_clean_cli_failure(monkeypatch):
    _disable_health_check(monkeypatch)
    monkeypatch.setattr("autumn_cli.cli.APIClient", _LoginFailureClient)

    result = CliRunner().invoke(
        cli,
        [
            "auth",
            "login",
            "--username",
            "kuda",
            "--password",
            "wrong",
            "--base-url",
            "https://autumn.example",
        ],
    )

    assert result.exit_code == 1
    assert "Error: Login failed: Unable to log in" in result.output
    assert "Traceback" not in result.output
    assert not isinstance(result.exception, APIError)


def test_console_entrypoint_hides_expected_traceback(monkeypatch, capsys):
    _disable_health_check(monkeypatch)
    monkeypatch.setattr("autumn_cli.cli.APIClient", _LoginFailureClient)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "autumn",
            "auth",
            "login",
            "--username",
            "kuda",
            "--password",
            "wrong",
            "--base-url",
            "https://autumn.example",
        ],
    )

    with pytest.raises(SystemExit) as exit_info:
        main()

    captured = capsys.readouterr()
    assert exit_info.value.code == 1
    assert "Error: Login failed: Unable to log in" in captured.err
    assert "Traceback" not in captured.err


def test_password_error_payload_is_flattened(monkeypatch):
    client = APIClient(
        api_key="temporary",
        base_url="https://autumn.example",
        wake_retry=False,
    )
    response = MagicMock(status_code=400, text="")
    response.json.return_value = {
        "non_field_errors": ["Unable to log in with provided credentials."]
    }
    monkeypatch.setattr(client, "_http", MagicMock(return_value=response))

    with pytest.raises(APIError) as error:
        client.get_token_with_password("kuda", "wrong")

    message = str(error.value)
    assert message == "Login failed: Unable to log in with provided credentials."
    assert "{" not in message


def test_password_login_converts_network_error(monkeypatch):
    client = APIClient(
        api_key="temporary",
        base_url="https://autumn.example",
        wake_retry=False,
    )
    monkeypatch.setattr(
        requests,
        "request",
        MagicMock(side_effect=requests.exceptions.ConnectTimeout("timed out")),
    )

    with pytest.raises(APIError, match="Request timed out"):
        client.get_token_with_password("kuda", "x")


def test_password_login_rejects_malformed_success(monkeypatch):
    client = APIClient(api_key="temporary", base_url="https://autumn.example")
    response = MagicMock(status_code=200)
    response.json.side_effect = ValueError("not json")
    monkeypatch.setattr(client, "_http", MagicMock(return_value=response))

    with pytest.raises(APIError, match="invalid JSON response"):
        client.get_token_with_password("kuda", "x")


@pytest.mark.parametrize(
    ("type_name", "value"),
    (("int", "nope"), ("float", "many"), ("bool", "perhaps"), ("json", "{")),
)
def test_config_set_invalid_typed_value_is_a_usage_error(
    monkeypatch, tmp_path, type_name, value
):
    _disable_health_check(monkeypatch)
    monkeypatch.setattr(cfg, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(cfg, "CONFIG_FILE", tmp_path / "config.yaml")

    result = CliRunner().invoke(
        cli, ["config", "set", "test.value", value, "--type", type_name]
    )

    assert result.exit_code == 2
    assert f"Could not parse as {type_name}" in result.output
    assert "Traceback" not in result.output


def test_invalid_background_reminder_is_not_spawned(monkeypatch):
    _disable_health_check(monkeypatch)
    detached = MagicMock()
    monkeypatch.setattr(
        "autumn_cli.utils.reminder_spawner.spawn_detached_python_module", detached
    )

    result = CliRunner().invoke(
        cli, ["remind", "in", "eventually", "--message", "Stretch", "--background"]
    )

    assert result.exit_code == 1
    assert "Error: Invalid --remind-in duration" in result.output
    detached.assert_not_called()


def test_unknown_reminder_placeholder_is_rejected_before_spawn(monkeypatch):
    _disable_health_check(monkeypatch)
    detached = MagicMock()
    monkeypatch.setattr(
        "autumn_cli.utils.reminder_spawner.spawn_detached_python_module", detached
    )

    result = CliRunner().invoke(
        cli,
        ["remind", "every", "20m", "--message", "Hello {unknown}"],
    )

    assert result.exit_code == 1
    assert "Unsupported reminder message field" in result.output
    detached.assert_not_called()


def test_api_false_result_uses_nonzero_exit(monkeypatch):
    _disable_health_check(monkeypatch)

    class _FailedStopClient:
        def __init__(self, *args, **kwargs):
            pass

        def stop_timer(self, *args, **kwargs):
            return {"ok": False, "error": "No active timer found."}

    monkeypatch.setattr("autumn_cli.commands.timer.APIClient", _FailedStopClient)

    result = CliRunner().invoke(cli, ["stop"])

    assert result.exit_code == 1
    assert "Error: No active timer found." in result.output


def test_config_write_failure_is_clean(monkeypatch):
    _disable_health_check(monkeypatch)

    def _fail_write(*args, **kwargs):
        raise ConfigError("Could not save configuration file: access denied")

    monkeypatch.setattr("autumn_cli.commands.config_cmd.set_config_value", _fail_write)

    result = CliRunner().invoke(cli, ["config", "set", "x", "y"])

    assert result.exit_code == 1
    assert "Error: Could not save configuration file: access denied" in result.output
    assert "Traceback" not in result.output


def test_invalid_configured_base_url_is_an_api_error():
    with pytest.raises(APIError, match="Invalid base URL"):
        APIClient(api_key="key", base_url="autumn.example")
