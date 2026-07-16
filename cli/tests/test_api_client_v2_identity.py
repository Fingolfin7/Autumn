"""v2 identity facade tests."""

from unittest.mock import MagicMock

import pytest

from autumn_cli.api_client import APIClient


@pytest.fixture
def client():
    return APIClient(
        api_key="key", base_url="https://autumn.example", wake_retry=False
    )


def test_get_me_uses_v2_and_translates_to_legacy_identity(client, monkeypatch):
    request = MagicMock(
        return_value={
            "api_version": 2,
            "capabilities": ["projects"],
            "user": {"id": 9, "username": "alice", "timezone": "Europe/Prague"},
        }
    )
    monkeypatch.setattr(client, "_request", request)

    result = client.get_me()

    request.assert_called_once_with("GET", "/api/v2/me/")
    assert result == {
        "ok": True,
        "id": 9,
        "username": "alice",
        "email": "",
        "first_name": "",
        "last_name": "",
        "timezone": "Europe/Prague",
    }


def test_cached_me_keeps_account_and_greeting_consumer_shape(client, monkeypatch):
    monkeypatch.setattr(
        client,
        "get_me",
        MagicMock(
            return_value={
                "ok": True,
                "id": 9,
                "username": "alice",
                "email": "",
                "first_name": "",
                "last_name": "",
                "timezone": "Europe/Prague",
            }
        ),
    )
    monkeypatch.setattr("autumn_cli.utils.user_cache.load_cached_user", lambda **kw: None)
    save = MagicMock()
    monkeypatch.setattr("autumn_cli.utils.user_cache.save_cached_user", save)

    result = client.get_cached_me(refresh=True)

    assert result == {
        "user": {
            "id": 9,
            "username": "alice",
            "email": "",
            "first_name": "",
            "last_name": "",
        },
        "cached": False,
    }
    save.assert_called_once_with(result["user"])
