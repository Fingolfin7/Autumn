from __future__ import annotations

from autumn_cli.utils import reminders_registry as rr


def test_registry_prunes_placeholder_pid_999(monkeypatch):
    state = {
        "reminders": [
            {"pid": 999, "session_id": 123, "project": "MyProj", "created_at": "t", "mode": "remind-in"},
            {"pid": 55555, "session_id": 1, "project": "Real", "created_at": "t", "mode": "remind-every"},
        ]
    }

    monkeypatch.setattr(rr, "load_config", lambda: dict(state))

    def fake_save_config(cfg):
        state.clear()
        state.update(cfg)

    monkeypatch.setattr(rr, "save_config", fake_save_config)
    monkeypatch.setattr(rr, "_is_pid_alive", lambda pid: True)

    entries = rr.load_entries(prune_dead=True)
    assert all(e.pid != 999 for e in entries)

