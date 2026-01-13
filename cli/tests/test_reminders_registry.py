from __future__ import annotations

from autumn_cli.utils import reminders_registry as rr


def test_registry_add_and_remove(monkeypatch):
    # Keep everything in-memory by stubbing config load/save.
    state = {}

    def fake_load_config():
        return dict(state)

    def fake_save_config(cfg):
        state.clear()
        state.update(cfg)

    monkeypatch.setattr(rr, "load_config", fake_load_config)
    monkeypatch.setattr(rr, "save_config", fake_save_config)

    # Don't prune as part of add_entry (avoid pid liveness checks)
    monkeypatch.setattr(rr, "_is_pid_alive", lambda pid: True)

    rr.clear_entries()
    e = rr.add_entry(pid=1234, session_id=99, project="Test", mode="remind-in")
    assert e.pid == 1234

    entries = rr.load_entries(prune_dead=False)
    assert len(entries) == 1

    removed = rr.remove_entry_by_pid(1234)
    assert removed is True

    entries2 = rr.load_entries(prune_dead=False)
    assert entries2 == []

