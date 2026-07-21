from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, call

import pytest
from click.testing import CliRunner

from autumn_cli.api_client import APIClient, APIError
from autumn_cli.cli import cli
from autumn_cli.commands.note import _compose_note, note
from autumn_cli.commands.timer import stop
from autumn_cli.utils.log_render import format_subprojects_bracketed
from autumn_cli.utils.splits import parse_split, resolve_split_selection


def _client():
    return APIClient(
        api_key="key", base_url="https://autumn.example", wake_retry=False
    )


def _resource(*, active=False, note="old", version=4):
    return {
        "id": 21,
        "version": version,
        "project": {"id": 8, "name": "Deep Work"},
        "subproject_allocations": [
            {"subproject_id": 31, "name": "api", "allocation_bp": 6000},
            {"subproject_id": 32, "name": "frontend", "allocation_bp": 4000},
        ],
        "start": "2026-07-16T08:00:00+00:00",
        "end": None if active else "2026-07-16T09:00:00+00:00",
        "active": active,
        "duration_minutes": None if active else 60,
        "elapsed_minutes": 15 if active else None,
        "note": note,
    }


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("api=60, frontend = 40", (("api", 60), ("frontend", 40))),
        ("even", ()),
        (" EVEN ", ()),
    ],
)
def test_parse_split_valid_pairs_and_even(raw, expected):
    parsed = parse_split(raw)
    assert parsed.percentages == expected
    assert parsed.even is (not expected)


@pytest.mark.parametrize("raw", ["api=0", "api=101", "api=1.5", "api=x"])
def test_parse_split_rejects_bad_percent(raw):
    with pytest.raises(ValueError, match="integers from 1 to 100"):
        parse_split(raw)


def test_parse_split_rejects_total_over_100():
    with pytest.raises(ValueError, match="total more than 100"):
        parse_split("api=60,frontend=41")


class _ResolutionClient:
    def list_subprojects(self, project):
        return {"subprojects": [{"name": "api"}, {"name": "frontend"}]}

    def resolve_subproject_allocations(self, project, allocations):
        ids = {"api": 31, "frontend": 32}
        missing = [name for name, _bp in allocations if name not in ids]
        if missing:
            raise APIError(f"Unknown subprojects: {', '.join(missing)}")
        return [(ids[name], bp) for name, bp in allocations]


def test_split_names_must_match_explicit_subprojects():
    with pytest.raises(ValueError, match="must name the same subprojects"):
        resolve_split_selection(
            _ResolutionClient(),
            "Deep Work",
            ["api", "frontend"],
            parse_split("api=100"),
        )


def test_unknown_split_subproject_keeps_friendly_api_error():
    with pytest.raises(APIError, match="Unknown subprojects: missing"):
        resolve_split_selection(
            _ResolutionClient(), "Deep Work", [], parse_split("missing=100")
        )


def test_stop_track_and_edit_allocation_payloads_replace_subproject_ids(monkeypatch):
    client = _client()
    allocations = [(31, 6000), (32, 4000)]

    stop_request = MagicMock(
        side_effect=[
            {**_resource(active=True), "version": 4},
            _resource(active=False),
        ]
    )
    monkeypatch.setattr(client, "_request", stop_request)
    client.stop_timer(session_id=21, allocations=allocations)
    stop_payload = stop_request.call_args_list[1].kwargs["json"]
    assert stop_payload["subproject_allocations"] == [
        {"subproject_id": 31, "allocation_bp": 6000},
        {"subproject_id": 32, "allocation_bp": 4000},
    ]
    assert "subproject_ids" not in stop_payload

    monkeypatch.setattr(client, "_resolve_project_id", lambda project: 8)
    track_request = MagicMock(return_value=_resource())
    monkeypatch.setattr(client, "_request", track_request)
    client.track_session(
        "Deep Work",
        "2026-07-16T08:00:00+00:00",
        "2026-07-16T09:00:00+00:00",
        ["api", "frontend"],
        allocations=allocations,
    )
    track_payload = track_request.call_args.kwargs["json"]
    assert track_payload["subproject_allocations"][0]["allocation_bp"] == 6000
    assert "subproject_ids" not in track_payload

    edit_request = MagicMock(side_effect=[_resource(), _resource()])
    monkeypatch.setattr(client, "_request", edit_request)
    client.edit_session(21, subprojects=["api", "frontend"], allocations=allocations)
    edit_payload = edit_request.call_args_list[1].kwargs["json"]
    assert edit_payload["subproject_allocations"][1]["allocation_bp"] == 4000
    assert "subproject_ids" not in edit_payload


def test_non_even_rendering_shows_percentages_and_even_stays_plain():
    non_even = {
        "subs": ["api", "frontend"],
        "subproject_allocations": [
            {"name": "api", "allocation_bp": 6000},
            {"name": "frontend", "allocation_bp": 4000},
        ],
    }
    even = {
        "subs": ["api", "frontend"],
        "subproject_allocations": [
            {"name": "api", "allocation_bp": 5000},
            {"name": "frontend", "allocation_bp": 5000},
        ],
    }
    assert "api 60%" in format_subprojects_bracketed(non_even)
    assert "·" in format_subprojects_bracketed(non_even)
    assert format_subprojects_bracketed(even) == (
        "[[autumn.subproject]api[/], [autumn.subproject]frontend[/]]"
    )


def test_update_timer_note_patches_active_timer_with_if_match(monkeypatch):
    client = _client()
    request = MagicMock(return_value=_resource(active=True, note="updated", version=5))
    monkeypatch.setattr(client, "_request", request)
    result = client.update_timer_note(21, "updated", 4)
    request.assert_called_once_with(
        "PATCH",
        "/api/v2/timers/21/",
        json={"note": "updated"},
        headers={"If-Match": "4"},
    )
    assert result["session"]["note"] == "updated"


def test_note_composition_append_replace_and_no_stamp():
    assert _compose_note(
        "old", "text", replace=False, stamp=True, hhmm="12:34"
    )[0] == "old\n\n— 12:34 — text"
    assert _compose_note(
        "old", "text", replace=True, stamp=False, hhmm="12:34"
    )[0] == "text"
    assert _compose_note(
        "old", "text", replace=False, stamp=False, hhmm="12:34"
    )[0] == "old\n\ntext"


class _FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        value = cls(2026, 7, 18, 12, 34)
        return value.astimezone() if tz is None else value.replace(tzinfo=tz)


class _NoteClient:
    calls = []
    conflict_once = False
    fetches = 0

    def __init__(self, *args, **kwargs):
        pass

    def get_timer_status(self, session_id=None, project=None):
        type(self).fetches += 1
        note_text = "old" if type(self).fetches == 1 else "old from server"
        return {
            "ok": True,
            "active": 1,
            "sessions": [
                {
                    "id": 21,
                    "version": 4 + type(self).fetches,
                    "p": "Deep Work",
                    "start": "2026-07-18T10:00:00+00:00",
                    "note": note_text,
                }
            ],
        }

    def update_timer_note(self, session_id, new_note, version):
        type(self).calls.append((session_id, new_note, version))
        if type(self).conflict_once:
            type(self).conflict_once = False
            raise APIError("conflict", code="version_conflict")
        return {
            "ok": True,
            "session": {"id": session_id, "p": "Deep Work", "note": new_note},
        }


def _reset_note_client():
    _NoteClient.calls = []
    _NoteClient.conflict_once = False
    _NoteClient.fetches = 0


def test_note_command_appends_with_frozen_local_time(monkeypatch):
    _reset_note_client()
    monkeypatch.setattr("autumn_cli.commands.note.APIClient", _NoteClient)
    monkeypatch.setattr("autumn_cli.commands.note.datetime", _FixedDateTime)
    result = CliRunner().invoke(note, ["multiple", "words"])
    assert result.exit_code == 0
    assert _NoteClient.calls == [(21, "old\n\n— 12:34 — multiple words", 5)]


def test_note_command_replace_defaults_to_no_stamp(monkeypatch):
    _reset_note_client()
    monkeypatch.setattr("autumn_cli.commands.note.APIClient", _NoteClient)
    monkeypatch.setattr("autumn_cli.commands.note.datetime", _FixedDateTime)
    result = CliRunner().invoke(note, ["replacement", "--replace"])
    assert result.exit_code == 0
    assert _NoteClient.calls == [(21, "replacement", 5)]


def test_note_command_no_stamp_appends_plain_fragment(monkeypatch):
    _reset_note_client()
    monkeypatch.setattr("autumn_cli.commands.note.APIClient", _NoteClient)
    monkeypatch.setattr("autumn_cli.commands.note.datetime", _FixedDateTime)
    result = CliRunner().invoke(note, ["plain", "--no-stamp"])
    assert result.exit_code == 0
    assert _NoteClient.calls == [(21, "old\n\nplain", 5)]


def test_note_command_retries_once_and_recomposes_on_version_conflict(monkeypatch):
    _reset_note_client()
    _NoteClient.conflict_once = True
    monkeypatch.setattr("autumn_cli.commands.note.APIClient", _NoteClient)
    monkeypatch.setattr("autumn_cli.commands.note.datetime", _FixedDateTime)
    result = CliRunner().invoke(note, ["text"])
    assert result.exit_code == 0
    assert _NoteClient.calls == [
        (21, "old\n\n— 12:34 — text", 5),
        (21, "old from server\n\n— 12:34 — text", 6),
    ]


def test_note_no_active_timer_is_friendly(monkeypatch):
    class NoTimerClient:
        def __init__(self, *args, **kwargs):
            pass

        def get_timer_status(self, session_id=None, project=None):
            return {"ok": True, "active": 0, "sessions": []}

    monkeypatch.setattr("autumn_cli.commands.note.APIClient", NoTimerClient)
    result = CliRunner().invoke(note, ["text"])
    assert result.exit_code != 0
    assert "No active timer found" in result.output


def test_cli_note_happy_path(monkeypatch):
    _reset_note_client()
    monkeypatch.setattr("autumn_cli.commands.note.APIClient", _NoteClient)
    monkeypatch.setattr("autumn_cli.commands.note.datetime", _FixedDateTime)
    result = CliRunner().invoke(cli, ["note", "hello", "there"])
    assert result.exit_code == 0
    assert "Note updated" in result.output
    assert _NoteClient.calls[0][1].endswith("— 12:34 — hello there")


class _EditNoteClient:
    received = None

    def __init__(self, *args, **kwargs):
        pass

    def edit_session(self, **kwargs):
        type(self).received = kwargs
        return {
            "ok": True,
            "session": {
                "id": kwargs["session_id"],
                "p": "Deep Work",
                "elapsed": 60,
            },
        }


def test_edit_help_describes_in_place_edits_and_note_append():
    result = CliRunner().invoke(cli, ["edit", "--help"])
    assert result.exit_code == 0
    assert "keeps the same ID" in result.output
    assert "-a, --append-note" in result.output
    assert "autumn note TEXT" in result.output
    assert "new ID" not in result.output


def test_edit_appends_note_with_shorthand_and_reports_unchanged_id(monkeypatch):
    _EditNoteClient.received = None
    monkeypatch.setattr("autumn_cli.commands.sessions.APIClient", _EditNoteClient)

    result = CliRunner().invoke(
        cli, ["edit", "21", "-a", "  Follow-up context  "]
    )

    assert result.exit_code == 0
    assert _EditNoteClient.received["append_note"] == "Follow-up context"
    assert "Session ID:" in result.output
    assert "21 (unchanged)" in result.output


def test_edit_rejects_replace_and_append_together():
    result = CliRunner().invoke(
        cli,
        ["edit", "21", "--note", "Replacement", "--append-note", "Append"],
    )
    assert result.exit_code != 0
    assert "either --note or --append-note" in result.output


class _StopSplitClient:
    received = None

    def __init__(self, *args, **kwargs):
        pass

    def get_timer_status(self, session_id=None, project=None):
        return {
            "ok": True,
            "active": 1,
            "sessions": [
                {
                    "id": 21,
                    "p": "Deep Work",
                    "subs": ["api", "frontend"],
                    "start": "2026-07-18T10:00:00+00:00",
                }
            ],
        }

    def list_subprojects(self, project):
        return {"subprojects": [{"name": "api"}, {"name": "frontend"}]}

    def resolve_subproject_allocations(self, project, allocations):
        ids = {"api": 31, "frontend": 32}
        return [(ids[name], bp) for name, bp in allocations]

    def stop_timer(self, session_id=None, project=None, note=None, allocations=None):
        type(self).received = allocations
        return {
            "ok": True,
            "duration": 60,
            "session": {
                "id": 21,
                "p": "Deep Work",
                "subs": ["api", "frontend"],
                "subproject_allocations": [
                    {"name": "api", "allocation_bp": 6000},
                    {"name": "frontend", "allocation_bp": 4000},
                ],
            },
        }


def test_cli_stop_split_happy_path(monkeypatch):
    _StopSplitClient.received = None
    monkeypatch.setattr("autumn_cli.commands.timer.APIClient", _StopSplitClient)
    result = CliRunner().invoke(cli, ["stop", "--split", "api=60,frontend=40"])
    assert result.exit_code == 0
    assert "Timer stopped" in result.output
    assert _StopSplitClient.received == [(31, 6000), (32, 4000)]
