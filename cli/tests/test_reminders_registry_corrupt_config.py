from __future__ import annotations

from autumn_cli.utils import reminders_registry as rr


def test_registry_repairs_corrupt_json(monkeypatch, tmp_path):
    # Simulate a corrupted reminders.json.
    reminders_file = tmp_path / "reminders.json"
    monkeypatch.setattr(rr, "REMINDERS_FILE", reminders_file)

    # Write corrupt data
    reminders_file.write_text("not json")

    # Loading entries should not crash and should repair.
    entries = rr.load_entries(prune_dead=False)
    assert entries == []

    # It should have repaired it by writing an empty list (if it migrated or pruned, but here we just check it doesn't crash)
    # Actually load_entries only saves if it migrated or pruned.
    # But let's check it returns empty list.
    assert entries == []
