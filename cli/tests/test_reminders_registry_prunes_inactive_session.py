from __future__ import annotations

from autumn_cli.utils.reminders_registry import load_entries


def test_load_entries_prunes_inactive_session(monkeypatch, tmp_path):
    from autumn_cli.utils import reminders_registry as rr

    reminders_file = tmp_path / "reminders.json"
    monkeypatch.setattr(rr, "REMINDERS_FILE", reminders_file)

    # Initial state in reminders.json
    import json

    entries = [
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
    reminders_file.write_text(json.dumps(entries))

    # Mock load_config to return empty
    monkeypatch.setattr(rr, "load_config", lambda: {})

    # PID liveness returns True so we exercise the session pruning branch.
    monkeypatch.setattr(rr, "_is_pid_alive", lambda pid: True)

    # Fake API client that raises APIError like the real client does on 404.
    from autumn_cli.api_client import APIError

    class FakeClient:
        def get_timer_status(self, session_id=None, project=None):
            raise APIError("API error: Session not found")

    monkeypatch.setattr("autumn_cli.api_client.APIClient", FakeClient)

    # Act
    loaded_entries = rr.load_entries(prune_dead=True)

    # Assert
    assert loaded_entries == []
    # ensure we wrote back the pruned list
    data = json.loads(reminders_file.read_text())
    assert data == []
