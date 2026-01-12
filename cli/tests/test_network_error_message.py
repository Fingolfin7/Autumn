import pytest

from autumn_cli.api_client import APIClient, APIError


class _FakeResp:
    status_code = 500


def test_dns_error_message_is_readable(monkeypatch):
    import requests

    def _boom(*args, **kwargs):
        raise requests.exceptions.ConnectionError(
            "NameResolutionError(… getaddrinfo failed …)"
        )

    monkeypatch.setattr(requests, "request", _boom)
    monkeypatch.setattr("autumn_cli.api_client.get_api_key", lambda: "k")
    monkeypatch.setattr("autumn_cli.api_client.get_base_url", lambda: "https://example.invalid")

    c = APIClient()
    with pytest.raises(APIError) as e:
        c.get_timer_status()

    msg = str(e.value)
    assert "DNS" in msg or "dns" in msg
    assert "base_url" in msg

