from __future__ import annotations

from click.testing import CliRunner

from autumn_cli.commands.reminders_cmd import reminders


def test_reminders_list_does_not_clear_when_pid_check_errors(monkeypatch, tmp_path):
    # If pid liveness check raises, we should conservatively keep entries.
    from autumn_cli.utils import reminders_registry as rr

    reminders_file = tmp_path / "reminders.json"
    monkeypatch.setattr(rr, "REMINDERS_FILE", reminders_file)

    # Initial state in reminders.json
    entries = [
        {"pid": 1, "session_id": 2, "project": "p", "created_at": "t", "mode": "m"}
    ]
    import json

    reminders_file.write_text(json.dumps(entries))

    # Mock load_config to return empty (no migration)
    monkeypatch.setattr(rr, "load_config", lambda: {})

    def boom(pid: int) -> bool:
        raise RuntimeError("nope")

    monkeypatch.setattr(rr, "_is_pid_alive", boom)

    runner = CliRunner()
    result = runner.invoke(reminders, ["list"])
    assert result.exit_code == 0

    # Entry should still be present (conservative behavior).
    data = json.loads(reminders_file.read_text())
    assert data
