from __future__ import annotations

from autumn_cli.utils import reminders_registry as rr


def test_registry_repairs_non_dict_config(monkeypatch):
    # Simulate a corrupted config where the YAML root is a list.
    state = []

    def fake_load_config():
        # This intentionally returns a non-dict.
        return state

    saved = {}

    def fake_save_config(cfg):
        saved.clear()
        saved.update(cfg)

    monkeypatch.setattr(rr, "load_config", fake_load_config)
    monkeypatch.setattr(rr, "save_config", fake_save_config)

    # Loading entries should not crash and should repair by saving a dict with reminders list.
    entries = rr.load_entries(prune_dead=False)
    assert entries == []
    assert "reminders" in saved
    assert saved["reminders"] == []

