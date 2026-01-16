from __future__ import annotations

from click.testing import CliRunner

from autumn_cli.commands.timer import start


class _FakeClient:
    def __init__(self, *args, **kwargs):
        self._checks = 0

    def start_timer(self, project, subprojects, note):
        return {"ok": True, "session": {"id": 123, "note": note, "subs": subprojects or []}}

    def get_timer_status(self, session_id=None, project=None):
        self._checks += 1
        # Default: always active
        return {"ok": True, "session": {"id": 123, "active": True, "end": None, "elapsed": 1}}


def test_start_with_for_sleeps(monkeypatch):
    calls = {"sleep": []}

    # For this test we only care about start_timer; the code will also construct a poll client.
    monkeypatch.setattr("autumn_cli.commands.timer.APIClient", _FakeClient)

    def fake_schedule_in(*, seconds: int, fn, name: str = "reminder"):
        # don't run the callback, just return a dummy
        class T:
            def cancel(self):
                return None

        return T()

    def fake_sleep(seconds: int) -> None:
        calls["sleep"].append(seconds)

    monkeypatch.setattr("autumn_cli.commands.timer.schedule_in", fake_schedule_in)
    monkeypatch.setattr("autumn_cli.commands.timer.sleep_seconds", fake_sleep)

    runner = CliRunner()
    result = runner.invoke(start, ["MyProj", "--for", "5s", "--no-background"])
    assert result.exit_code == 0
    # sleeps for for_seconds + 1
    assert calls["sleep"] == [6]


def test_start_rejects_both_remind_options():
    runner = CliRunner()
    result = runner.invoke(start, ["MyProj", "--remind-in", "5s", "--remind-every", "5s"])
    assert result.exit_code != 0


def test_start_reminders_background_spawns_and_returns(monkeypatch):
    calls = {"spawn": 0}

    monkeypatch.setattr("autumn_cli.commands.timer.APIClient", _FakeClient)

    def fake_spawn(**kwargs):
        calls["spawn"] += 1

    monkeypatch.setattr("autumn_cli.commands.timer.spawn_reminder", fake_spawn)

    runner = CliRunner()
    result = runner.invoke(start, ["MyProj", "--remind-in", "5s"])
    assert result.exit_code == 0
    assert calls["spawn"] == 1



def test_start_reminders_stop_when_session_stops_foreground(monkeypatch):
    """Foreground mode: if the session becomes inactive, the reminder loop should exit and cancel tasks."""

    calls = {"sleep": [], "canceled": 0}

    class _Client(_FakeClient):
        def get_timer_status(self, session_id=None, project=None):
            self._checks += 1
            if self._checks == 1:
                return {"ok": True, "session": {"id": 123, "active": True, "end": None, "elapsed": 1}}
            return {"ok": True, "session": {"id": 123, "active": False, "end": "2026-01-13T00:00:00Z"}}

    monkeypatch.setattr("autumn_cli.commands.timer.APIClient", _Client)

    def fake_schedule_in(*, seconds: int, fn, name: str = "reminder"):
        class T:
            def cancel(self_inner):
                calls["canceled"] += 1

        return T()

    def fake_schedule_every(*, every_seconds: int, fn, name: str = "reminder", start_in_seconds=None):
        class T:
            def cancel(self_inner):
                calls["canceled"] += 1

        return T()

    def fake_sleep(seconds: int) -> None:
        calls["sleep"].append(seconds)
        # no real sleeping in tests

    monkeypatch.setattr("autumn_cli.commands.timer.schedule_in", fake_schedule_in)
    monkeypatch.setattr("autumn_cli.commands.timer.schedule_every", fake_schedule_every)
    monkeypatch.setattr("autumn_cli.commands.timer.sleep_seconds", fake_sleep)

    runner = CliRunner()
    result = runner.invoke(start, ["MyProj", "--remind-in", "5s", "--no-background"])
    assert result.exit_code == 0

    assert calls["canceled"] >= 1
    assert 30 in calls["sleep"]
