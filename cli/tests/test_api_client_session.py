"""Connection-pooling behavior for the Autumn API client."""

from __future__ import annotations

from unittest.mock import MagicMock

import requests

from autumn_cli.api_client import APIClient


def test_client_reuses_injected_session_for_requests_and_health_probes(monkeypatch) -> None:
    session = MagicMock(spec=requests.Session)
    response = MagicMock()
    response.status_code = 200
    response.content = b"{}"
    response.json.return_value = {"timers": []}
    response.raise_for_status.return_value = None
    session.get.return_value = response
    session.request.return_value = response

    client = APIClient(
        api_key="key",
        base_url="https://autumn.example",
        session=session,
    )

    client._ensure_server_awake()
    client.get_timer_status()
    client.get_timer_status()

    assert session.request.call_count == 2
    session.get.assert_called_once_with(
        "https://autumn.example/healthz/", timeout=5, verify=True
    )
