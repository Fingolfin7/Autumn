"""Tests for waking a sleeping hosted API before retrying one request."""

from unittest.mock import MagicMock

import pytest
import requests

from autumn_cli.api_client import APIClient, APIError


def _response(status_code=200, payload=None):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = {} if payload is None else payload
    response.raise_for_status.side_effect = (
        requests.exceptions.HTTPError(f"{status_code} error")
        if status_code >= 400
        else None
    )
    return response


def _client(monkeypatch, *, wake_retry=True, wake_timeout=120):
    monkeypatch.setattr("autumn_cli.api_client.get_wake_retry", lambda: wake_retry)
    monkeypatch.setattr(
        "autumn_cli.api_client.get_wake_timeout_seconds", lambda: wake_timeout
    )
    return APIClient(api_key="key", base_url="https://autumn.example", quiet=True)


def test_connection_error_wakes_server_then_retries(monkeypatch):
    client = _client(monkeypatch)
    success = _response(payload={"ok": True})
    monkeypatch.setattr(
        requests,
        "request",
        MagicMock(side_effect=[requests.exceptions.ConnectionError("refused"), success]),
    )
    health = _response(200)
    get = MagicMock(return_value=health)
    monkeypatch.setattr(requests, "get", get)

    assert client.get_timer_status() == {"ok": True}
    assert requests.request.call_count == 2
    get.assert_called_once_with(
        "https://autumn.example/healthz/", timeout=10, verify=True
    )


def test_503_wakes_server_then_retries(monkeypatch):
    client = _client(monkeypatch)
    unavailable = _response(503)
    success = _response(payload={"sessions": []})
    request = MagicMock(side_effect=[unavailable, success])
    monkeypatch.setattr(requests, "request", request)
    monkeypatch.setattr(requests, "get", MagicMock(return_value=_response(200)))

    assert client.get_timer_status() == {"sessions": []}
    assert request.call_count == 2


def test_400_does_not_wake_server(monkeypatch):
    client = _client(monkeypatch)
    monkeypatch.setattr(requests, "request", MagicMock(return_value=_response(400)))
    health = MagicMock()
    monkeypatch.setattr(requests, "get", health)

    with pytest.raises(APIError, match="API error"):
        client.get_timer_status()

    health.assert_not_called()


def test_dns_failure_keeps_friendly_message_without_health_probe(monkeypatch):
    client = _client(monkeypatch)
    monkeypatch.setattr(
        requests,
        "request",
        MagicMock(
            side_effect=requests.exceptions.ConnectionError(
                "NameResolutionError(getaddrinfo failed)"
            )
        ),
    )
    health = MagicMock()
    monkeypatch.setattr(requests, "get", health)

    with pytest.raises(APIError) as error:
        client.get_timer_status()

    assert "DNS" in str(error.value)
    health.assert_not_called()


def test_wake_retry_disabled_fails_fast(monkeypatch):
    client = _client(monkeypatch, wake_retry=False)
    monkeypatch.setattr(
        requests, "request", MagicMock(side_effect=requests.exceptions.ConnectionError("refused"))
    )
    health = MagicMock()
    monkeypatch.setattr(requests, "get", health)

    with pytest.raises(APIError, match="Network error"):
        client.get_timer_status()

    health.assert_not_called()


def test_wake_retry_disabled_does_not_poll_after_503(monkeypatch):
    client = _client(monkeypatch, wake_retry=False)
    monkeypatch.setattr(requests, "request", MagicMock(return_value=_response(503)))
    health = MagicMock()
    monkeypatch.setattr(requests, "get", health)

    with pytest.raises(APIError, match="API error"):
        client.get_timer_status()

    health.assert_not_called()


def test_post_read_timeout_does_not_retry(monkeypatch):
    client = _client(monkeypatch)
    request = MagicMock(side_effect=requests.exceptions.ReadTimeout("timed out"))
    monkeypatch.setattr(requests, "request", request)
    health = MagicMock()
    monkeypatch.setattr(requests, "get", health)

    with pytest.raises(APIError, match="Network error"):
        client.start_timer("Work")

    assert request.call_count == 1
    health.assert_not_called()


def test_wake_budget_expiry_raises_friendly_error(monkeypatch):
    client = _client(monkeypatch, wake_timeout=0)
    monkeypatch.setattr(
        requests, "request", MagicMock(side_effect=requests.exceptions.ConnectionError("refused"))
    )
    monkeypatch.setattr(requests, "get", MagicMock(return_value=_response(503)))

    with pytest.raises(APIError, match="Server did not wake up in time"):
        client.get_timer_status()
