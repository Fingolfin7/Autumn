from __future__ import annotations

from click.testing import CliRunner

from autumn_cli.commands.sessions import delete_session, log, track
from autumn_cli.commands.meta import meta_audit
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


class _LogClient:
    def __init__(self, *args, **kwargs):
        pass

    def get_discovery_meta(self, ttl_seconds=300, refresh=False):
        return {"contexts": [], "tags": []}

    def log_activity(
        self,
        period=None,
        project=None,
        start_date=None,
        end_date=None,
        context=None,
        tags=None,
        exclude=None,
    ):
        return {
            "count": 1,
            "logs": [
                {
                    "id": 404,
                    "project": "MyProj",
                    "subprojects": ["meals"],
                    "start_time": "2026-01-01T10:00:00",
                    "end_time": "2026-01-01T10:30:00",
                    "duration_minutes": 30,
                    "note": "Breakfast",
                }
            ],
        }


class _DeleteSessionClient:
    def __init__(self, *args, **kwargs):
        pass

    def delete_session(self, session_id):
        return {"ok": True, "deleted": session_id}


class _AuditClient:
    def __init__(self, *args, **kwargs):
        pass

    def audit_totals(self, dry_run=False):
        return {
            "ok": True,
            "dry_run": dry_run,
            "projects": {"count": 3, "changed": 1, "delta": 9.0},
            "subprojects": {"count": 5, "changed": 2, "delta": -3.5},
            "changed_projects": [
                {"id": 1, "name": "Autumn", "before": 10.0, "after": 19.0, "delta": 9.0}
            ],
            "changed_subprojects": [
                {
                    "id": 2,
                    "name": "CLI",
                    "project": "Autumn",
                    "before": 5.0,
                    "after": 1.5,
                    "delta": -3.5,
                }
            ],
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


def test_log_output_hides_session_ids_by_default(monkeypatch):
    printed = []

    monkeypatch.setattr("autumn_cli.commands.sessions.APIClient", _LogClient)
    monkeypatch.setattr(
        "autumn_cli.commands.sessions.console.print",
        lambda *args, **kwargs: printed.append(" ".join(str(a) for a in args)),
    )

    runner = CliRunner()
    result = runner.invoke(log, ["--raw"])
    assert result.exit_code == 0
    assert any("Breakfast" in line for line in printed)
    assert not any("#404" in line for line in printed)


def test_log_output_can_show_session_ids(monkeypatch):
    printed = []

    monkeypatch.setattr("autumn_cli.commands.sessions.APIClient", _LogClient)
    monkeypatch.setattr(
        "autumn_cli.commands.sessions.console.print",
        lambda *args, **kwargs: printed.append(" ".join(str(a) for a in args)),
    )

    runner = CliRunner()
    result = runner.invoke(log, ["--raw", "--show-ids"])
    assert result.exit_code == 0
    assert any("#404" in line for line in printed)


def test_delete_session_output_uses_session_id(monkeypatch):
    printed = []

    monkeypatch.setattr("autumn_cli.commands.sessions.APIClient", _DeleteSessionClient)
    monkeypatch.setattr(
        "autumn_cli.commands.sessions.console.print",
        lambda *args, **kwargs: printed.append(" ".join(str(a) for a in args)),
    )

    runner = CliRunner()
    result = runner.invoke(delete_session, ["404", "--yes"])
    assert result.exit_code == 0
    assert any("Session deleted" in line for line in printed)
    assert any("Session ID: 404" in line for line in printed)


def test_audit_output_uses_delta_key_from_api_docs(monkeypatch):
    printed = []

    monkeypatch.setattr("autumn_cli.commands.meta.APIClient", _AuditClient)
    monkeypatch.setattr("autumn_cli.commands.meta.clear_cached_projects", lambda: None)
    monkeypatch.setattr("autumn_cli.commands.meta.clear_cached_activity", lambda: None)
    monkeypatch.setattr(
        "autumn_cli.commands.meta.console.print",
        lambda *args, **kwargs: printed.append(" ".join(str(a) for a in args)),
    )

    runner = CliRunner()
    result = runner.invoke(meta_audit, [])
    assert result.exit_code == 0
    assert any("delta: +9.0 min" in line for line in printed)
    assert any("delta: -3.5 min" in line for line in printed)
    assert any("Autumn" in line and "10.0 -> 19.0" in line for line in printed)
    assert any("CLI" in line and "5.0 -> 1.5" in line for line in printed)


def test_audit_dry_run_labels_preview(monkeypatch):
    printed = []
    cleared = {"projects": 0, "activity": 0}

    monkeypatch.setattr("autumn_cli.commands.meta.APIClient", _AuditClient)
    monkeypatch.setattr(
        "autumn_cli.commands.meta.clear_cached_projects",
        lambda: cleared.__setitem__("projects", cleared["projects"] + 1),
    )
    monkeypatch.setattr(
        "autumn_cli.commands.meta.clear_cached_activity",
        lambda: cleared.__setitem__("activity", cleared["activity"] + 1),
    )
    monkeypatch.setattr(
        "autumn_cli.commands.meta.console.print",
        lambda *args, **kwargs: printed.append(" ".join(str(a) for a in args)),
    )

    runner = CliRunner()
    result = runner.invoke(meta_audit, ["--dry-run"])
    assert result.exit_code == 0
    assert any("Audit preview complete" in line for line in printed)
    assert any("Dry run only" in line for line in printed)
    assert cleared == {"projects": 0, "activity": 0}
