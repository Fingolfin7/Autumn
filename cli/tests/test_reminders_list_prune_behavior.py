from __future__ import annotations

from click.testing import CliRunner

from autumn_cli.commands.reminders_cmd import reminders


def test_reminders_list_does_not_clear_when_pid_check_errors(monkeypatch):
    # If pid liveness check raises, we should conservatively keep entries.
    from autumn_cli.utils import reminders_registry as rr

    state = {"reminders": [{"pid": 1, "session_id": 2, "project": "p", "created_at": "t", "mode": "m"}]}

    monkeypatch.setattr(rr, "load_config", lambda: dict(state))

    def fake_save_config(cfg):
        state.clear()
        state.update(cfg)

    monkeypatch.setattr(rr, "save_config", fake_save_config)

    def boom(pid: int) -> bool:
        raise RuntimeError("nope")

    monkeypatch.setattr(rr, "_is_pid_alive", boom)

    runner = CliRunner()
    result = runner.invoke(reminders, ["list"])
    assert result.exit_code == 0

    # Entry should still be present (conservative behavior).
    assert state.get("reminders")

