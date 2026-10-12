"""Tests for the search/related API sync and the friendlier command interface."""

from __future__ import annotations

import datetime as _dt
import json
from unittest.mock import MagicMock

import click
import pytest
import requests
from click.testing import CliRunner

from autumn_cli.api_client import APIClient, APIError
from autumn_cli.cli import cli
from autumn_cli.commands import sessions as sessions_cmd
from autumn_cli.commands.commitments import CommitmentPeriod, _adjust_amount
from autumn_cli.utils.periods import normalize_period, parse_date_arg, period_to_dates
from autumn_cli.utils.resolvers import resolve_project_param


PROJECTS = [
    {"name": "Autumn CLI"},
    {"name": "AutumnWeb"},
    {"name": "Garden"},
]


# --- project name resolution -------------------------------------------------


def test_partial_project_name_needs_opt_in():
    result = resolve_project_param(project="gard", projects=PROJECTS)
    assert result.value == "gard"
    assert "Unknown project" in result.warning


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("gard", "Garden"), ("autumnw", "AutumnWeb"), ("web", "AutumnWeb"), ("CLI", "Autumn CLI")],
)
def test_unique_prefix_or_substring_resolves_with_a_note(raw, expected):
    result = resolve_project_param(project=raw, projects=PROJECTS, partial=True)
    assert result.value == expected
    assert result.warning is None
    assert expected in result.note


def test_ambiguous_partial_name_lists_candidates_instead_of_guessing():
    result = resolve_project_param(project="autumn", projects=PROJECTS, partial=True)
    assert result.value == "autumn"
    assert "Did you mean: Autumn CLI, AutumnWeb?" in result.warning


def test_typo_suggests_close_names():
    result = resolve_project_param(project="Gardne", projects=PROJECTS, partial=True)
    assert "Did you mean: Garden?" in result.warning


# --- periods and dates -------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("w", "week"),
        ("2w", "fortnight"),
        ("Lunar", "lunar cycle"),
        ("lunar  cycle", "lunar cycle"),
        ("today", "today"),
        ("nonsense", None),
    ],
)
def test_normalize_period_accepts_aliases(raw, expected):
    assert normalize_period(raw) == expected


def test_yesterday_period_is_a_single_day():
    start, end = period_to_dates("yesterday")
    assert start == end
    assert start == (_dt.date.today() - _dt.timedelta(days=1)).isoformat()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2026-01-05", "2026-01-05"),
        ("01-05-2026", "2026-01-05"),
        ("yesterday", "2026-10-11"),
        ("monday", "2026-10-12"),  # today is a Monday: today counts
        ("sun", "2026-10-11"),
        ("3d ago", "2026-10-09"),
        ("-2w", "2026-09-28"),
    ],
)
def test_parse_date_arg_understands_natural_dates(raw, expected):
    assert parse_date_arg(raw, today=_dt.date(2026, 10, 12)) == expected


def test_parse_date_arg_rejects_gibberish():
    with pytest.raises(ValueError, match="Could not understand date"):
        parse_date_arg("someday")


# --- track windows -------------------------------------------------------------


class _FakeDateTime(_dt.datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 10, 12, 18, 0, 0)


@pytest.fixture
def frozen_now(monkeypatch):
    monkeypatch.setattr("autumn_cli.commands.sessions.datetime", _FakeDateTime)


def test_track_duration_alone_ends_now(frozen_now):
    assert sessions_cmd._resolve_track_window(None, None, 45 * 60) == (
        "2026-10-12 17:15:00",
        "2026-10-12 18:00:00",
    )


def test_track_start_plus_duration(frozen_now):
    assert sessions_cmd._resolve_track_window("14:00", None, 2 * 3600) == (
        "2026-10-12 14:00:00",
        "2026-10-12 16:00:00",
    )


def test_track_end_minus_duration(frozen_now):
    assert sessions_cmd._resolve_track_window(None, "5pm", 1800) == (
        "2026-10-12 16:30:00",
        "2026-10-12 17:00:00",
    )


def test_track_time_only_on_another_day(frozen_now):
    assert sessions_cmd._resolve_track_window(
        "9am", "11:30", None, _dt.date(2026, 10, 11)
    ) == ("2026-10-11 09:00:00", "2026-10-11 11:30:00")


def test_track_start_alone_ends_now(frozen_now):
    assert sessions_cmd._resolve_track_window("16:00", None, None) == (
        "2026-10-12 16:00:00",
        "2026-10-12 18:00:00",
    )


@pytest.mark.parametrize(
    ("start", "end", "seconds", "message"),
    [
        (None, None, None, "Say how long"),
        (None, "10:00", None, "Add --start or a duration"),
        ("9:00", "10:00", 600, "at most two"),
        ("now", "now-1h", None, "must end after"),
    ],
)
def test_track_window_errors(frozen_now, start, end, seconds, message):
    with pytest.raises(click.UsageError, match=message):
        sessions_cmd._resolve_track_window(start, end, seconds)


def test_track_command_accepts_positional_duration(monkeypatch, frozen_now):
    received = {}

    class Client:
        def get_discovery_projects(self, **kwargs):
            return {"projects": PROJECTS}

        def track_session(self, project, start, end, subprojects=None, note=None):
            received.update(project=project, start=start, end=end, note=note)
            return {"ok": True, "session": {"id": 9, "elapsed": 45}}

    monkeypatch.setattr(sessions_cmd, "APIClient", Client)
    result = CliRunner().invoke(cli, ["track", "gard", "45m", "-n", "Weeding"])

    assert result.exit_code == 0, result.output
    assert received == {
        "project": "Garden",
        "start": "2026-10-12 17:15:00",
        "end": "2026-10-12 18:00:00",
        "note": "Weeding",
    }


# --- log: bare words, search and related -----------------------------------------


class _LogClient:
    calls: list = []

    def __init__(self, *args, **kwargs):
        pass

    def get_discovery_meta(self, **kwargs):
        return {"contexts": [], "tags": []}

    def get_discovery_projects(self, **kwargs):
        return {"projects": PROJECTS}

    def log_activity(self, **kwargs):
        type(self).calls.append(kwargs)
        return {
            "count": 2,
            "logs": [
                {
                    "id": 1, "project": "Garden", "subprojects": [],
                    "start_time": "2026-10-12T08:00:00+00:00",
                    "end_time": "2026-10-12T09:00:00+00:00",
                    "duration_minutes": 60, "note": "planted bulbs", "match": "direct",
                },
                {
                    "id": 2, "project": "Garden", "subprojects": [],
                    "start_time": "2026-09-01T08:00:00+00:00",
                    "end_time": "2026-09-01T09:00:00+00:00",
                    "duration_minutes": 60, "note": "tulips", "match": "related",
                },
            ],
            "related_status": "included",
        }


@pytest.fixture
def log_client(monkeypatch):
    _LogClient.calls = []
    monkeypatch.setattr(sessions_cmd, "APIClient", _LogClient)
    return _LogClient


def test_log_bare_words_become_period_and_project(log_client):
    result = CliRunner().invoke(cli, ["log", "gard", "yesterday"])
    assert result.exit_code == 0, result.output
    call = log_client.calls[0]
    assert call["project"] == "Garden"
    assert call["start_date"] == call["end_date"] == (
        _dt.date.today() - _dt.timedelta(days=1)
    ).isoformat()


def test_log_search_defaults_to_all_time_and_separates_related(log_client):
    result = CliRunner().invoke(cli, ["log", "-q", "bulbs", "--related"])
    assert result.exit_code == 0, result.output
    call = log_client.calls[0]
    assert call["search"] == "bulbs" and call["related"] is True
    assert call["start_date"] is None and call["end_date"] is None
    assert "Related by meaning" in result.output
    # The related row is listed after the direct one, in its own section,
    # using the same date-grouped layout as the rest of the log.
    assert result.output.index("planted bulbs") < result.output.index("tulips")
    related_part = result.output[result.output.index("Related by meaning"):]
    assert "September 2026" in related_part and " to " in related_part


_LONG_NOTE = "word " * 100  # 500 characters


@pytest.fixture
def long_note_client(monkeypatch):
    class _LongNoteClient(_LogClient):
        def log_activity(self, **kwargs):
            result = super().log_activity(**kwargs)
            result["logs"] = [dict(result["logs"][0], note=_LONG_NOTE.strip())]
            result["count"] = 1
            return result

    _LogClient.calls = []
    monkeypatch.setattr(sessions_cmd, "APIClient", _LongNoteClient)
    return _LongNoteClient


def _config(monkeypatch, values):
    import autumn_cli.config as config_module

    monkeypatch.setattr(
        config_module, "get_config_value", lambda key, default=None: values.get(key, default)
    )


def test_log_notes_are_full_by_default(long_note_client, monkeypatch):
    _config(monkeypatch, {})
    result = CliRunner().invoke(cli, ["log", "--raw"])
    assert result.exit_code == 0, result.output
    assert result.output.count("word") == 100
    assert "…" not in result.output


def test_log_max_note_length_truncates_at_a_word(long_note_client, monkeypatch):
    _config(monkeypatch, {})
    result = CliRunner().invoke(cli, ["log", "--raw", "-m", "22"])
    assert result.exit_code == 0, result.output
    assert "word word word word …" in result.output
    assert result.output.count("word") == 4


def test_log_truncate_uses_the_configured_length(long_note_client, monkeypatch):
    _config(monkeypatch, {"log.max_note_length": "12"})
    result = CliRunner().invoke(cli, ["log", "--raw", "--truncate"])
    assert result.exit_code == 0, result.output
    assert result.output.count("word") == 2


def test_log_config_can_turn_truncation_on_and_flag_turns_it_off(long_note_client, monkeypatch):
    _config(monkeypatch, {"log.truncate_notes": "true"})
    truncated = CliRunner().invoke(cli, ["log", "--raw"])
    assert truncated.exit_code == 0, truncated.output
    assert "…" in truncated.output and truncated.output.count("word") < 100

    full = CliRunner().invoke(cli, ["log", "--raw", "--no-truncate"])
    assert full.exit_code == 0, full.output
    assert full.output.count("word") == 100


def test_log_markdown_notes_truncate_too(long_note_client, monkeypatch):
    _config(monkeypatch, {})
    result = CliRunner().invoke(cli, ["log", "-m", "22"])
    assert result.exit_code == 0, result.output
    assert result.output.count("word") == 4


def test_log_rejects_zero_note_length(long_note_client, monkeypatch):
    _config(monkeypatch, {})
    result = CliRunner().invoke(cli, ["log", "-m", "0"])
    assert result.exit_code != 0
    assert "must be at least 1" in result.output
    assert long_note_client.calls == []


def test_log_rejects_subproject_without_project(log_client):
    result = CliRunner().invoke(cli, ["log", "-s", "Frontend"])
    assert result.exit_code != 0
    assert "--subproject needs --project" in result.output


# --- API client ----------------------------------------------------------------------


def _response(status=200, body=None, headers=None, url="https://autumn.example/x"):
    response = requests.Response()
    response.status_code = status
    response._content = json.dumps(body if body is not None else {}).encode()
    response.headers.update(headers or {})
    response.url = url
    response.reason = "Bad Request" if status >= 400 else "OK"
    return response


@pytest.fixture
def http():
    return MagicMock()


@pytest.fixture
def client(http):
    return APIClient(
        api_key="key", base_url="https://autumn.example", session=http, wake_retry=False
    )


def test_search_sessions_sends_search_related_and_ordering(client, http):
    http.request.return_value = _response(
        body={
            "count": 1,
            "total": 1,
            "sessions": [
                {"id": 4, "project": {"id": 1, "name": "Garden"}, "subproject_allocations": [],
                 "start": "2026-10-12T08:00:00Z", "end": "2026-10-12T09:00:00Z",
                 "active": False, "duration_minutes": 60, "note": "x", "match": "related"},
            ],
        },
        headers={"X-Autumn-Related": "included"},
    )

    result = client.search_sessions(search="bulbs", related=True, ordering="newest", limit=5)

    params = http.request.call_args.kwargs["params"]
    assert params["search"] == "bulbs"
    assert params["related"] == "true"
    assert params["ordering"] == "newest"
    assert result["sessions"][0]["match"] == "related"
    assert result["related_status"] == "included"


def test_related_is_not_sent_without_search(client, http):
    http.request.return_value = _response(body={"count": 0, "total": 0, "sessions": []})
    client.search_sessions(related=True, limit=5)
    assert "related" not in http.request.call_args.kwargs["params"]


def test_heatmap_uses_server_aggregation(client, http):
    http.request.return_value = _response(
        body=[{"weekday": 0, "hour": 21, "average_hours": 0.5}]
    )
    cells = client.get_heatmap_cells(start_date="2026-10-01")
    assert http.request.call_args.kwargs["url"].endswith("/api/v2/reports/charts/")
    params = http.request.call_args.kwargs["params"]
    assert params["chart_type"] == "heatmap"
    assert params["aggregate"] == "true"
    assert params["start_date"] == "2026-10-01"
    assert cells == [{"weekday": 0, "hour": 21, "average_hours": 0.5}]


def test_export_resolves_context_and_tag_names(client, http, monkeypatch):
    monkeypatch.setattr(
        client,
        "get_discovery_meta",
        lambda **kwargs: {"contexts": [{"id": 3, "name": "Work"}], "tags": [{"id": 7, "name": "cli"}]},
    )
    http.request.return_value = _response(body={"format": 2, "projects": []})
    client.export_data(context="work", tags=["CLI"], search="garden")
    params = http.request.call_args.kwargs["params"]
    assert params["context_ids"] == "3"
    assert params["tag_ids"] == "7"
    assert params["search"] == "garden"


def test_timer_note_patch_uses_schema_path_without_trailing_slash(client, http):
    http.request.return_value = _response(
        body={"id": 21, "project": {"id": 1, "name": "Garden"}, "active": True}
    )
    client.update_timer_note(21, "note", 3)
    assert http.request.call_args.kwargs["url"] == "https://autumn.example/api/v2/timers/21"


def test_validation_errors_include_field_details(client, http):
    http.request.return_value = _response(
        status=400,
        body={"error": {"code": "validation_error", "message": "Invalid input.",
                        "details": {"end": ["The timestamp is in the future."]}}},
    )
    with pytest.raises(APIError, match=r"Invalid input\. \(end: The timestamp is in the future\.\)"):
        client.get_session(1)


# --- commitments ---------------------------------------------------------------------


@pytest.mark.parametrize(("raw", "minutes"), [("30", 30), ("-30", -30), ("1h30m", 90), ("-45m", -45)])
def test_adjust_amount_accepts_minutes_or_durations(raw, minutes):
    assert _adjust_amount(raw) == minutes


@pytest.mark.parametrize(("raw", "expected"), [("week", "weekly"), ("d", "daily"), ("monthly", "monthly")])
def test_commitment_period_aliases(raw, expected):
    assert CommitmentPeriod().convert(raw, None, None) == expected


# --- root command wiring -------------------------------------------------------------


def test_delete_is_a_hidden_alias_for_discard():
    runner = CliRunner()
    assert "discard" in runner.invoke(cli, ["--help"]).output
    assert "\n  delete " not in runner.invoke(cli, ["--help"]).output
    assert "Throw away a running timer" in runner.invoke(cli, ["delete", "--help"]).output


def test_chart_type_given_twice_must_agree():
    result = CliRunner().invoke(cli, ["chart", "pie", "-T", "bar"])
    assert result.exit_code != 0
    assert "Give the chart type once" in result.output
