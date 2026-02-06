from __future__ import annotations

from click.testing import CliRunner

from autumn_cli.commands.sessions import track
from autumn_cli.commands.timer import start, stop, status


class _TimerClient:
    def __init__(self, *args, **kwargs):
        pass

    def get_discovery_projects(self, ttl_seconds=300, refresh=False):
        return {"projects": [{"name": "MyProj", "status": "active"}], "cached": True}

    def list_subprojects(self, project, compact=True):
        return {"subprojects": []}

    def start_timer(self, project, subprojects, note):
        return {"ok": True, "session": {"id": 101, "subs": subprojects or [], "note": note}}

    def stop_timer(self, session_id=None, project=None, note=None):
        return {
            "ok": True,
            "duration": 39,
            "session": {
                "id": 101,
                "p": project or "MyProj",
                "subs": ["meals"],
                "note": note,
            },
        }


class _TrackClient:
    def __init__(self, *args, **kwargs):
        pass

    def get_discovery_projects(self, ttl_seconds=300, refresh=False):
        return {"projects": [{"name": "First Ascent", "status": "active"}], "cached": True}

    def list_subprojects(self, project, compact=True):
        return {"subprojects": [{"name": "meals"}]}

    def track_session(self, project, start, end, subprojects=None, note=None):
        return {
            "ok": True,
            "session": {
                "id": 202,
                "elapsed": 39,
                "subs": subprojects or [],
                "note": note,
            },
        }


class _StatusClient:
    def __init__(self, *args, **kwargs):
        pass

    def get_timer_status(self, session_id=None, project=None):
        return {
            "ok": True,
            "active": 1,
            "sessions": [{"id": 303, "p": "MyProj", "subs": ["meals"], "elapsed": 5}],
        }


def test_start_output_uses_status_style(monkeypatch):
    printed = []

    monkeypatch.setattr("autumn_cli.commands.timer.APIClient", _TimerClient)
    monkeypatch.setattr(
        "autumn_cli.commands.timer.console.print",
        lambda *args, **kwargs: printed.append(" ".join(str(a) for a in args)),
    )

    runner = CliRunner()
    result = runner.invoke(start, ["MyProj"])
    assert result.exit_code == 0
    assert any("Started [autumn.project]MyProj[/] []" in line for line in printed)
    assert any("Session ID: #[autumn.id]101[/]" in line for line in printed)


def test_stop_output_uses_status_style(monkeypatch):
    printed = []

    monkeypatch.setattr("autumn_cli.commands.timer.APIClient", _TimerClient)
    monkeypatch.setattr(
        "autumn_cli.commands.timer.console.print",
        lambda *args, **kwargs: printed.append(" ".join(str(a) for a in args)),
    )

    runner = CliRunner()
    result = runner.invoke(stop, ["-i", "101", "-p", "MyProj"])
    assert result.exit_code == 0
    assert any("Stopped [autumn.project]MyProj[/] [[autumn.subproject]meals[/]]" in line for line in printed)
    assert any("Session ID: #[autumn.id]101[/]" in line for line in printed)


def test_track_output_uses_status_style(monkeypatch):
    printed = []

    monkeypatch.setattr("autumn_cli.commands.sessions.APIClient", _TrackClient)
    monkeypatch.setattr(
        "autumn_cli.commands.sessions.console.print",
        lambda *args, **kwargs: printed.append(" ".join(str(a) for a in args)),
    )

    runner = CliRunner()
    result = runner.invoke(
        track,
        [
            "First Ascent",
            "-s",
            "meals",
            "--start",
            "2026-02-06 15:00:00",
            "--end",
            "2026-02-06 15:39:00",
        ],
    )
    assert result.exit_code == 0
    assert any("Tracked [autumn.project]First Ascent[/] [[autumn.subproject]meals[/]], [autumn.duration]39 minutes[/]" in line for line in printed)
    assert any("Session ID: #[autumn.id]202[/]" in line for line in printed)


def test_status_output_uses_colored_session_id(monkeypatch):
    printed = []

    monkeypatch.setattr("autumn_cli.commands.timer.APIClient", _StatusClient)
    monkeypatch.setattr(
        "autumn_cli.commands.timer.console.print",
        lambda *args, **kwargs: printed.append(" ".join(str(a) for a in args)),
    )

    runner = CliRunner()
    result = runner.invoke(status, [])
    assert result.exit_code == 0
    assert any("Session ID: #[autumn.id]303[/]" in line for line in printed)
