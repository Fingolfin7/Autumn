from __future__ import annotations

import pytest

from click.testing import CliRunner

from autumn_cli.commands.remind_cmd import remind


def test_remind_in_schedules_and_sends(monkeypatch):
    calls = {"sleep": [], "notify": []}

    def fake_sleep(seconds: int) -> None:
        calls["sleep"].append(seconds)

    def fake_send_notification(*, title: str, message: str, subtitle=None):
        calls["notify"].append({"title": title, "message": message, "subtitle": subtitle})

        class R:
            ok = True
            supported = True
            method = "test"
            error = None

        return R()

    monkeypatch.setattr("autumn_cli.commands.remind_cmd.sleep_seconds", fake_sleep)
    monkeypatch.setattr("autumn_cli.commands.remind_cmd.send_notification", fake_send_notification)

    runner = CliRunner()
    result = runner.invoke(remind, ["in", "5s", "--message", "hello", "--title", "Autumn"])
    assert result.exit_code == 0
    assert calls["sleep"] == [5]
    assert calls["notify"][0]["message"] == "hello"


def test_remind_in_rejects_bad_duration():
    runner = CliRunner()
    result = runner.invoke(remind, ["in", "nope", "--message", "hello"])
    assert result.exit_code != 0

