import subprocess

import pytest
from click.testing import CliRunner

from autumn_cli import config
from autumn_cli.api_client import APIClient, APIError
from autumn_cli.cli import cli
from autumn_cli.utils import pickers, projects_cache, reminders_registry
from autumn_cli.utils.formatters import format_datetime


@pytest.fixture
def runner(tmp_path, monkeypatch):
    monkeypatch.delenv("AUTUMN_API_KEY", raising=False)
    monkeypatch.delenv("AUTUMN_API_BASE", raising=False)
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path / "settings")
    monkeypatch.setattr(config, "CONFIG_FILE", config.CONFIG_DIR / "config.yaml")
    monkeypatch.setattr(reminders_registry, "check_reminders_health", lambda: [])
    monkeypatch.setattr(projects_cache, "_mem_snapshot", None)
    config.save_config({
        "base_url": "https://first.example",
        "active_account": "alice",
        "accounts": {
            "alice": {"api_key": "first-token", "username": "alice"},
            "bob": {"api_key": "second-token", "username": "bob"},
        },
        "account_aliases": {"alice": {"projects": {"local": "AutumnWeb"}}},
    })
    return CliRunner()


def _project(project_id, name):
    return {"id": project_id, "name": name, "status": "active"}


def _invoke(runner, *args):
    result = runner.invoke(cli, args)
    assert result.exit_code == 0, (result.output, result.exception)
    return result.output


def test_here_is_scoped_by_checkout_server_and_account(runner, tmp_path, monkeypatch):
    checkout = tmp_path / "Autumn checkout"
    nested = checkout / "src" / "feature"
    nested.mkdir(parents=True)
    subprocess.run(["git", "init", "--quiet", str(checkout)], check=True)
    monkeypatch.chdir(nested)
    projects = [_project(11, "AutumnWeb"), _project(22, "Other Project")]
    starts = []
    picker_calls = []

    def request(client, method, path, **kwargs):
        if path == "/api/v2/me/":
            return {"user": {"id": 2 if client.api_key == "second-token" else 1}}
        if path == "/api/v2/projects/":
            return {"projects": projects}
        if path == "/api/v2/projects/11":
            return projects[0]
        if path == "/api/v2/projects/22":
            return projects[1]
        assert (method, path) == ("POST", "/api/v2/timers/")
        starts.append(kwargs["json"]["project_id"])
        return {"id": 30}

    def pick_project(client, *, statuses):
        picker_calls.append(statuses)
        return "Other Project"

    monkeypatch.setattr(APIClient, "_request", request)
    monkeypatch.setattr(pickers, "pick_project", pick_project)
    monkeypatch.setattr(pickers, "pick_subproject", lambda *args: None)

    output = _invoke(runner, "here", "local")
    assert "Linked" in output and "AutumnWeb" in output
    monkeypatch.chdir(checkout)
    _invoke(runner, "start")
    projects[0]["name"] = "Renamed AutumnWeb"
    monkeypatch.chdir(nested)
    assert "Renamed AutumnWeb" in _invoke(runner, "start")
    _invoke(runner, "start", "Other Project")
    assert starts == [11, 11, 22]
    assert picker_calls == []
    _invoke(runner, "start", "--pick")

    config.switch_account("bob")
    _invoke(runner, "start")
    _invoke(runner, "here", "Other Project")
    _invoke(runner, "start")
    config.switch_account("alice")
    _invoke(runner, "start")
    monkeypatch.setenv("AUTUMN_API_KEY", "second-token")
    _invoke(runner, "start")
    monkeypatch.setenv("AUTUMN_API_BASE", "https://second.example/")
    _invoke(runner, "start")
    monkeypatch.delenv("AUTUMN_API_BASE")
    monkeypatch.delenv("AUTUMN_API_KEY")
    monkeypatch.chdir(tmp_path)
    _invoke(runner, "start")

    assert starts == [11, 11, 22, 22, 22, 22, 11, 22, 22, 22]
    assert len(picker_calls) == 4


@pytest.mark.parametrize(
    ("names", "message"),
    [
        (["Web Red", "Web Blue"], "unique project"),
        (["Web", "WEB"], "Project name is ambiguous"),
    ],
)
def test_here_validates_checkout_and_project_before_saving(
    runner, tmp_path, monkeypatch, names, message
):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(cli, ["here", "web"])
    assert result.exit_code == 1
    assert "inside a Git checkout" in result.output

    subprocess.run(["git", "init", "--quiet"], check=True)
    monkeypatch.setattr(
        APIClient,
        "_request",
        lambda *_args, **_kwargs: {"projects": [_project(i, name) for i, name in enumerate(names, 1)]},
    )
    result = runner.invoke(cli, ["here", "web"])
    assert result.exit_code == 1
    assert message in result.output
    assert "checkout_projects" not in config.load_config()


def test_last_reads_one_completed_session_with_the_full_note(runner, monkeypatch):
    queries = []
    end = "2026-11-24T10:30:00Z"
    note = "Found [bold] a clue :memo:\nNext step: rerun the import."

    def request(client, method, path, **kwargs):
        if path == "/api/v2/projects/":
            return {"projects": [_project(11, "AutumnWeb")]}
        assert (method, path) == ("GET", "/api/v2/sessions/")
        queries.append(kwargs["params"])
        return {"sessions": [{"id": 50, "project": _project(11, "AutumnWeb"), "end": end, "note": note}]}

    monkeypatch.setattr(APIClient, "_request", request)
    output = _invoke(runner, "last", "local")

    assert queries == [{"project_ids": "11", "ordering": "newest", "include": "note", "limit": 1}]
    assert "AutumnWeb" in output and "#50" in output
    assert format_datetime(end) in output
    assert note in output


@pytest.mark.parametrize(
    ("sessions", "message"),
    [
        ([], "No saved sessions"),
        ([{"id": 50, "project": _project(1, "Notes"), "note": " "}], "No note."),
    ],
)
def test_last_without_project_handles_empty_history_and_empty_notes(
    runner, monkeypatch, sessions, message
):
    def request(client, method, path, **kwargs):
        assert (method, path) == ("GET", "/api/v2/sessions/")
        assert kwargs["params"] == {"ordering": "newest", "include": "note", "limit": 1}
        return {"sessions": sessions}

    monkeypatch.setattr(APIClient, "_request", request)
    assert message in _invoke(runner, "last")


@pytest.mark.parametrize("with_subprojects", [False, True])
def test_resume_selects_history_before_stopping_the_original_timer(
    runner, monkeypatch, with_subprojects
):
    actions = []
    status = {"ok": True, "active": 2, "sessions": [
        {"id": 30, "start": "2026-11-24T10:20:00Z"},
        {"id": 40, "start": "2026-11-24T10:30:00Z"},
    ]}

    def search(client, *, limit, ordering):
        assert (limit, ordering) == (1, "newest")
        actions.append("search")
        return {"sessions": [{"project": "Previous", "subprojects": ["Research"]}]}

    def stop(client, *, session_id):
        actions.append(("stop", session_id))
        return {"ok": True}

    def start(client, project, subprojects):
        actions.append(("start", project, subprojects))
        return {"ok": True, "session": {"id": 50}}

    monkeypatch.setattr(APIClient, "get_timer_status", lambda client: status)
    monkeypatch.setattr(APIClient, "search_sessions", search)
    monkeypatch.setattr(APIClient, "stop_timer", stop)
    monkeypatch.setattr(APIClient, "start_timer", start)
    flags = ["--with-subprojects"] if with_subprojects else []
    assert "Resumed" in _invoke(runner, "resume", "--stop-current", *flags)
    expected_subs = ["Research"] if with_subprojects else None
    assert actions == ["search", ("stop", 40), ("start", "Previous", expected_subs)]


@pytest.mark.parametrize(
    ("history", "message"),
    [
        ([], "No saved sessions"),
        ([{}], "Could not determine last project"),
        (APIError("The server is unavailable."), "The server is unavailable."),
    ],
)
def test_resume_leaves_the_timer_running_when_history_cannot_be_selected(
    runner, monkeypatch, history, message
):
    status = {"ok": True, "active": 1, "sessions": [{"id": 40}]}

    def search(client, **kwargs):
        if isinstance(history, APIError):
            raise history
        return {"sessions": history}

    def unexpected_write(*args, **kwargs):
        pytest.fail("A history lookup failure must leave the timer running.")

    monkeypatch.setattr(APIClient, "get_timer_status", lambda client: status)
    monkeypatch.setattr(APIClient, "search_sessions", search)
    monkeypatch.setattr(APIClient, "stop_timer", unexpected_write)
    monkeypatch.setattr(APIClient, "start_timer", unexpected_write)

    result = runner.invoke(cli, ["resume", "--stop-current"])
    assert result.exit_code == 1
    assert message in result.output


def test_resume_does_not_start_when_stopping_the_current_timer_fails(runner, monkeypatch):
    status = {"ok": True, "active": 1, "sessions": [{"id": 40}]}

    def unexpected_start(*args, **kwargs):
        pytest.fail("A stop failure must abort the resume.")

    monkeypatch.setattr(APIClient, "get_timer_status", lambda client: status)
    monkeypatch.setattr(
        APIClient, "search_sessions", lambda client, **kwargs: {"sessions": [{"project": "Previous"}]}
    )
    monkeypatch.setattr(
        APIClient, "stop_timer", lambda client, **kwargs: {"ok": False, "error": "Cannot stop timer."}
    )
    monkeypatch.setattr(APIClient, "start_timer", unexpected_start)

    result = runner.invoke(cli, ["resume", "--stop-current"])
    assert result.exit_code == 1
    assert "Cannot stop timer." in result.output
