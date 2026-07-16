"""Tests for waking a sleeping hosted API before retrying one request."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
import requests

from autumn_cli.api_client import APIClient, APIError


def _session_resource(*, active=True):
    return {
        "id": 11,
        "uuid": "00000000-0000-0000-0000-000000000001",
        "version": 3,
        "project": {"id": 4, "name": "Work"},
        "allocation_mode": "equal",
        "subproject_allocations": [],
        "start": "2026-07-16T08:30:00+00:00",
        "end": None if active else "2026-07-16T09:00:00+00:00",
        "active": active,
        "auto_stop_at": None,
        "duration_minutes": None if active else 30.0,
        "elapsed_minutes": 0.0 if active else None,
        "note": None,
    }


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
    success = _response(payload={"timers": []})
    monkeypatch.setattr(
        requests,
        "request",
        MagicMock(side_effect=[requests.exceptions.ConnectionError("refused"), success]),
    )
    health = _response(200)
    get = MagicMock(return_value=health)
    monkeypatch.setattr(requests, "get", get)

    assert client.get_timer_status() == {"ok": True, "active": 0, "sessions": []}
    assert requests.request.call_count == 2
    get.assert_called_once_with(
        "https://autumn.example/healthz/", timeout=10, verify=True
    )


def test_503_wakes_server_then_retries(monkeypatch):
    client = _client(monkeypatch)
    unavailable = _response(503)
    success = _response(payload={"timers": []})
    request = MagicMock(side_effect=[unavailable, success])
    monkeypatch.setattr(requests, "request", request)
    monkeypatch.setattr(requests, "get", MagicMock(return_value=_response(200)))

    assert client.get_timer_status() == {"ok": True, "active": 0, "sessions": []}
    assert request.call_count == 2


def test_track_session_503_wakes_and_resends_uuid_create(monkeypatch):
    client = _client(monkeypatch)
    monkeypatch.setattr(client, "_resolve_project_id", lambda project: 4)
    request = MagicMock(
        side_effect=[_response(503), _response(payload=_session_resource(active=False))]
    )
    monkeypatch.setattr(requests, "request", request)
    probe = MagicMock(return_value=_response(200))
    monkeypatch.setattr(requests, "get", probe)
    wake_server = MagicMock(return_value=True)
    monkeypatch.setattr(client, "_wake_server", wake_server)

    result = client.track_session(
        "Work", "2026-07-16T09:00:00", "2026-07-16T10:00:00"
    )

    probe.assert_called_once_with(
        "https://autumn.example/healthz/", timeout=5, verify=True
    )
    wake_server.assert_called_once_with()
    assert request.call_count == 2
    assert result["session"]["elapsed"] == 30.0
    assert (
        request.call_args_list[0].kwargs["json"]["uuid"]
        == request.call_args_list[1].kwargs["json"]["uuid"]
    )


def test_stop_timer_503_wakes_and_resends(monkeypatch):
    client = _client(monkeypatch)
    monkeypatch.setattr(
        client,
        "_resolve_active_timer_target",
        lambda session_id, project: _session_resource(),
    )
    request = MagicMock(
        side_effect=[_response(503), _response(payload=_session_resource(active=False))]
    )
    monkeypatch.setattr(requests, "request", request)
    monkeypatch.setattr(requests, "get", MagicMock(return_value=_response(200)))
    wake_server = MagicMock(return_value=True)
    monkeypatch.setattr(client, "_wake_server", wake_server)

    assert client.stop_timer()["duration"] == 30.0

    wake_server.assert_called_once_with()
    assert request.call_count == 2


def test_restart_timer_503_is_not_resent(monkeypatch):
    client = _client(monkeypatch)
    monkeypatch.setattr(
        client,
        "_resolve_active_timer_target",
        lambda session_id, project: _session_resource(),
    )
    request = MagicMock(return_value=_response(503))
    monkeypatch.setattr(requests, "request", request)
    probe = MagicMock(return_value=_response(200))
    monkeypatch.setattr(requests, "get", probe)
    wake_server = MagicMock(return_value=True)
    monkeypatch.setattr(client, "_wake_server", wake_server)

    with pytest.raises(APIError, match="may or may not have been applied"):
        client.restart_timer()

    assert request.call_count == 1
    probe.assert_called_once_with(
        "https://autumn.example/healthz/", timeout=5, verify=True
    )
    wake_server.assert_not_called()


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


def test_wake_retry_disabled_does_not_probe_wake_or_resend_mutation(monkeypatch):
    client = _client(monkeypatch, wake_retry=False)
    request = MagicMock(return_value=_response(503))
    monkeypatch.setattr(requests, "request", request)
    health = MagicMock()
    monkeypatch.setattr(requests, "get", health)
    wake_server = MagicMock(return_value=True)
    monkeypatch.setattr(client, "_wake_server", wake_server)

    with pytest.raises(APIError, match="API error"):
        client.restart_timer()

    assert request.call_count == 1
    health.assert_not_called()
    wake_server.assert_not_called()


def test_start_timer_503_wakes_and_retries_with_same_uuid(monkeypatch):
    client = _client(monkeypatch)
    monkeypatch.setattr(client, "_resolve_project_id", lambda project: 4)
    request = MagicMock(
        side_effect=[
            _response(503),
            _response(payload=_session_resource()),
        ]
    )
    monkeypatch.setattr(requests, "request", request)
    health = MagicMock(return_value=_response(200))
    monkeypatch.setattr(requests, "get", health)
    wake_server = MagicMock(return_value=True)
    monkeypatch.setattr(client, "_wake_server", wake_server)

    result = client.start_timer("Work")

    assert result["session"]["id"] == 11
    assert request.call_count == 2
    assert (
        request.call_args_list[0].kwargs["json"]["uuid"]
        == request.call_args_list[1].kwargs["json"]["uuid"]
    )
    health.assert_called_once_with(
        "https://autumn.example/healthz/", timeout=5, verify=True
    )
    wake_server.assert_called_once_with()


def test_wake_budget_expiry_raises_friendly_error(monkeypatch):
    client = _client(monkeypatch, wake_timeout=0)
    monkeypatch.setattr(
        requests, "request", MagicMock(side_effect=requests.exceptions.ConnectionError("refused"))
    )
    monkeypatch.setattr(requests, "get", MagicMock(return_value=_response(503)))

    with pytest.raises(APIError, match="Server did not wake up in time"):
        client.get_timer_status()


@pytest.mark.parametrize(
    ("method_name", "payload_key"),
    (("start_timer", "start"), ("stop_timer", "end")),
)
def test_timer_instant_is_aware_utc_and_captured_before_probe(
    monkeypatch, method_name, payload_key
):
    client = _client(monkeypatch)
    events = []
    fixed_now = datetime(2026, 7, 16, 8, 30, tzinfo=timezone.utc)

    class FakeDateTime:
        @classmethod
        def now(cls, tz):
            events.append("clock")
            assert tz is timezone.utc
            return fixed_now

    def probe(*args, **kwargs):
        events.append("probe")
        return _response(200)

    monkeypatch.setattr("autumn_cli.api_client.datetime", FakeDateTime)
    monkeypatch.setattr(requests, "get", probe)
    request = MagicMock(return_value=_response(payload=_session_resource()))
    monkeypatch.setattr(requests, "request", request)

    if method_name == "start_timer":
        monkeypatch.setattr(client, "_resolve_project_id", lambda project: 4)
        client.start_timer("Work")
    else:
        monkeypatch.setattr(
            client,
            "_resolve_active_timer_target",
            lambda session_id, project: _session_resource(),
        )
        client.stop_timer()

    payload = request.call_args.kwargs["json"]
    instant = datetime.fromisoformat(payload[payload_key])
    assert instant.utcoffset() == timezone.utc.utcoffset(instant)
    assert instant == fixed_now
    assert events == ["clock", "probe"]


def test_awake_probe_is_cached_across_mutations(monkeypatch):
    client = _client(monkeypatch)
    monkeypatch.setattr(
        client,
        "_resolve_active_timer_target",
        lambda session_id, project: _session_resource(),
    )
    probe = MagicMock(return_value=_response(200))
    monkeypatch.setattr(requests, "get", probe)
    request = MagicMock(return_value=_response(payload=_session_resource()))
    monkeypatch.setattr(requests, "request", request)

    client.restart_timer(project="Work")
    client.restart_timer(project="Work")

    probe.assert_called_once_with(
        "https://autumn.example/healthz/", timeout=5, verify=True
    )
    assert request.call_count == 2
