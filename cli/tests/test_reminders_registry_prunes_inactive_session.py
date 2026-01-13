from __future__ import annotations

from autumn_cli.utils.reminders_registry import load_entries


def test_load_entries_prunes_inactive_session(monkeypatch):
    # Arrange: config has a single reminder entry.
    monkeypatch.setattr(
        "autumn_cli.utils.reminders_registry.load_config",
        lambda: {
            "reminders": [
                {
                    "pid": 4242,
                    "session_id": 123,
                    "project": "p",
                    "created_at": "2026-01-01T00:00:00Z",
                    "mode": "remind-every",
                    "remind_every": "30s",
                    "remind_poll": "30s",
                }
            ]
        },
    )

    saved = {}

    def _save_config(cfg):
        saved["cfg"] = cfg

    monkeypatch.setattr("autumn_cli.utils.reminders_registry.save_config", _save_config)

    # PID liveness returns True so we exercise the session pruning branch.
    monkeypatch.setattr("autumn_cli.utils.reminders_registry._is_pid_alive", lambda pid: True)

    # Fake API client that raises APIError like the real client does on 404.
    from autumn_cli.api_client import APIError

    class FakeClient:
        def get_timer_status(self, session_id=None, project=None):
            raise APIError("API error: Session not found")

    monkeypatch.setattr("autumn_cli.api_client.APIClient", FakeClient)

    # Act
    entries = load_entries(prune_dead=True)

    # Assert
    assert entries == []
    # ensure we wrote back the pruned list
    assert saved["cfg"]["reminders"] == []
