from __future__ import annotations

from click.testing import CliRunner

from autumn_cli.commands.reminders_cmd import reminders


def test_reminders_list_empty(monkeypatch):
    monkeypatch.setattr("autumn_cli.commands.reminders_cmd.load_entries", lambda prune_dead=True: [])
    runner = CliRunner()
    result = runner.invoke(reminders, ["list"])
    assert result.exit_code == 0


def test_reminders_list_json_includes_new_fields(monkeypatch):
    class E:
        pid = 1
        session_id = 2
        project = "p"
        created_at = "t"
        mode = "remind-every"
        remind_in = None
        remind_every = "30s"
        auto_stop_for = None
        remind_poll = "30s"

    monkeypatch.setattr("autumn_cli.commands.reminders_cmd.load_entries", lambda prune_dead=True: [E()])
    runner = CliRunner()

    # JSON output
    result = runner.invoke(reminders, ["list", "--json"])
    assert result.exit_code == 0
    assert '"remind_every": "30s"' in result.output
    assert '"remind_poll": "30s"' in result.output

    # Human output
    result2 = runner.invoke(reminders, ["list"])
    assert result2.exit_code == 0
    assert "Details:" in result2.output
    assert "Every: 30s" in result2.output
    assert "Poll: 30s" in result2.output


def test_reminders_stop_all(monkeypatch):
    calls = {"killed": 0, "removed": 0, "cleared": 0}

    class E:
        def __init__(self, pid, session_id):
            self.pid = pid
            self.session_id = session_id
            self.project = "P"
            self.created_at = "t"
            self.mode = "remind-in"
            self.remind_in = "5s"
            self.remind_every = None
            self.auto_stop_for = None
            self.remind_poll = "30s"

    monkeypatch.setattr("autumn_cli.commands.reminders_cmd.load_entries", lambda prune_dead=False: [E(1, 10), E(2, 11)])
    monkeypatch.setattr(
        "autumn_cli.commands.reminders_cmd.kill_pid",
        lambda pid: calls.__setitem__("killed", calls["killed"] + 1) or True,
    )
    monkeypatch.setattr(
        "autumn_cli.commands.reminders_cmd.remove_entry_by_pid",
        lambda pid: calls.__setitem__("removed", calls["removed"] + 1) or True,
    )
    monkeypatch.setattr("autumn_cli.commands.reminders_cmd.clear_entries", lambda: calls.__setitem__("cleared", calls["cleared"] + 1))

    runner = CliRunner()
    result = runner.invoke(reminders, ["stop", "--all"])
    assert result.exit_code == 0
    assert calls["killed"] == 2
    assert calls["removed"] == 2
    assert calls["cleared"] == 1
