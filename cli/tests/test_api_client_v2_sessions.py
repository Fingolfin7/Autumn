"""v2 timer/session API façade tests."""

from datetime import datetime
from unittest.mock import ANY, MagicMock, call

import pytest
import requests

from autumn_cli.api_client import APIClient, APIError


def _resource(
    *,
    session_id=21,
    version=4,
    project_id=8,
    project="Deep Work",
    active=True,
    note="Focus",
):
    return {
        "id": session_id,
        "uuid": "00000000-0000-0000-0000-000000000021",
        "version": version,
        "project": {"id": project_id, "name": project},
        "subproject_allocations": [
            {"subproject_id": 31, "name": "Build", "allocation_bp": 10000}
        ],
        "start": "2026-07-16T08:00:00+00:00",
        "end": None if active else "2026-07-16T08:45:00+00:00",
        "active": active,
        "auto_stop_at": "2026-07-16T09:00:00+00:00" if active else None,
        "duration_minutes": None if active else 45.0,
        "elapsed_minutes": 12.5 if active else None,
        "note": note,
    }


def _compact(*, active=True):
    return {
        "id": 21,
        "version": 4,
        "p": "Deep Work",
        "pid": 8,
        "subs": ["Build"],
        "subproject_allocations": [
            {"subproject_id": 31, "name": "Build", "allocation_bp": 10000}
        ],
        "start": "2026-07-16T08:00:00+00:00",
        "end": None if active else "2026-07-16T08:45:00+00:00",
        "stop_at": "2026-07-16T09:00:00+00:00" if active else None,
        "active": active,
        "elapsed": 12.5 if active else 45.0,
        "note": "Focus",
    }


@pytest.fixture
def client():
    return APIClient(
        api_key="key", base_url="https://autumn.example", wake_retry=False
    )


def test_get_timer_status_uses_v2_and_translates_exact_legacy_shape(client, monkeypatch):
    request = MagicMock(return_value={"count": 1, "timers": [_resource()]})
    monkeypatch.setattr(client, "_request", request)

    result = client.get_timer_status(session_id=21, project="deep work")

    request.assert_called_once_with("GET", "/api/v2/timers/")
    assert result == {"ok": True, "active": 1, "sessions": [_compact()]}


def test_stop_timer_fetches_newest_then_sends_if_match(client, monkeypatch):
    older = _resource(session_id=20, version=2)
    older["start"] = "2026-07-16T07:00:00+00:00"
    stopped = _resource(active=False)
    request = MagicMock(
        side_effect=[{"count": 2, "timers": [older, _resource()]}, stopped]
    )
    monkeypatch.setattr(client, "_request", request)

    result = client.stop_timer(note="Focus")

    assert request.call_args_list == [
        call("GET", "/api/v2/timers/"),
        call(
            "POST",
            "/api/v2/timers/21/stop/",
            json={"end": ANY, "note": "Focus"},
            retry_safe=True,
            headers={"If-Match": "4"},
        ),
    ]
    assert result == {"ok": True, "session": _compact(active=False), "duration": 45.0}


def test_restart_timer_uses_detail_version_and_is_not_retry_safe(client, monkeypatch):
    request = MagicMock(side_effect=[_resource(), _resource()])
    monkeypatch.setattr(client, "_request", request)

    result = client.restart_timer(session_id=21)

    assert request.call_args_list == [
        call("GET", "/api/v2/sessions/21"),
        call(
            "POST",
            "/api/v2/timers/21/restart/",
            json={"start": ANY},
            headers={"If-Match": "4"},
        ),
    ]
    assert result == {"ok": True, "session": _compact()}


def test_delete_timer_uses_v2_and_fetched_version(client, monkeypatch):
    request = MagicMock(side_effect=[{"count": 1, "timers": [_resource()]}, {}])
    monkeypatch.setattr(client, "_request", request)

    assert client.delete_timer(21) == {"ok": True, "deleted": 21}
    assert request.call_args_list == [
        call("GET", "/api/v2/timers/"),
        call(
            "DELETE",
            "/api/v2/timers/21",
            retry_safe=True,
            headers={"If-Match": "4"},
        ),
    ]


def test_delete_absent_timer_still_calls_idempotent_v2_delete(client, monkeypatch):
    request = MagicMock(side_effect=[{"count": 0, "timers": []}, {}])
    monkeypatch.setattr(client, "_request", request)

    assert client.delete_timer(999) == {"ok": True, "deleted": 999}
    request.assert_has_calls(
        [
            call("GET", "/api/v2/timers/"),
            call(
                "DELETE",
                "/api/v2/timers/999",
                retry_safe=True,
            ),
        ]
    )


def test_track_session_uses_ids_uuid_utc_instants_and_legacy_shape(client, monkeypatch):
    monkeypatch.setattr(client, "_resolve_project_id", lambda name: 8)
    monkeypatch.setattr(
        client,
        "_resolve_subproject_ids",
        lambda project, project_id, names: [31],
    )
    request = MagicMock(return_value=_resource(active=False))
    monkeypatch.setattr(client, "_request", request)

    result = client.track_session(
        "Deep Work",
        "2026-07-16T08:00:00+00:00",
        "2026-07-16T08:45:00+00:00",
        ["Build"],
        "Focus",
    )

    payload = request.call_args.kwargs["json"]
    request.assert_called_once_with(
        "POST", "/api/v2/sessions/", json=payload, retry_safe=True
    )
    assert payload == {
        "project_id": 8,
        "start": "2026-07-16T08:00:00+00:00",
        "end": "2026-07-16T08:45:00+00:00",
        "subproject_ids": [31],
        "note": "Focus",
        "uuid": ANY,
    }
    assert datetime.fromisoformat(payload["start"]).utcoffset().total_seconds() == 0
    assert result == {"ok": True, "session": _compact(active=False)}


def test_track_session_preserves_legacy_date_format_and_cross_midnight(client, monkeypatch):
    monkeypatch.setattr(client, "_resolve_project_id", lambda name: 8)
    request = MagicMock(return_value=_resource(active=False))
    monkeypatch.setattr(client, "_request", request)

    client.track_session("Deep Work", "07-16-2026 23:45:00", "07-16-2026 00:15:00")

    payload = request.call_args.kwargs["json"]
    start = datetime.fromisoformat(payload["start"])
    end = datetime.fromisoformat(payload["end"])
    assert (end - start).total_seconds() == 30 * 60


def test_edit_session_gets_version_then_patches_v2(client, monkeypatch):
    current = _resource(active=False)
    edited = _resource(active=False, project_id=9, project="Planning")
    request = MagicMock(side_effect=[current, edited])
    monkeypatch.setattr(client, "_request", request)
    monkeypatch.setattr(client, "_resolve_project_id", lambda name: 9)
    monkeypatch.setattr(
        client,
        "_resolve_subproject_ids",
        lambda project, project_id, names: [41],
    )

    result = client.edit_session(
        21,
        project="Planning",
        subprojects=["Outline"],
        start="2026-07-16T09:00:00+00:00",
        note="Revised",
    )

    assert request.call_args_list == [
        call("GET", "/api/v2/sessions/21"),
        call(
            "PATCH",
            "/api/v2/sessions/21",
            json={
                "project_id": 9,
                "subproject_ids": [41],
                "start": "2026-07-16T09:00:00+00:00",
                "note": "Revised",
            },
            headers={"If-Match": "4"},
        ),
    ]
    assert result["session"]["p"] == "Planning"
    assert result["session"]["elapsed"] == 45.0
    assert set(result["session"]) == {
        "id",
        "p",
        "pid",
        "subs",
        "start",
        "end",
        "stop_at",
        "active",
        "elapsed",
        "note",
        "version",
        "subproject_allocations",
    }


def test_delete_session_uses_retry_safe_v2_delete(client, monkeypatch):
    request = MagicMock(return_value={})
    monkeypatch.setattr(client, "_request", request)

    assert client.delete_session(21) == {"ok": True, "deleted": 21}
    request.assert_called_once_with(
        "DELETE", "/api/v2/sessions/21", retry_safe=True
    )


def test_project_and_subproject_name_resolution_uses_v2_resources(client, monkeypatch):
    request = MagicMock(
        side_effect=[
            {
                "count": 1,
                "total": 1,
                "projects": [{"id": 8, "name": "Deep Work"}],
            },
            {"id": 8, "name": "Deep Work", "subprojects": [{"id": 31, "name": "Build"}]},
        ]
    )
    monkeypatch.setattr(client, "_request", request)

    assert client._resolve_project_id("deep work") == 8
    assert client._resolve_subproject_ids("Deep Work", 8, ["build"]) == [31]
    assert client._resolve_subproject_ids("Deep Work", 8, ["Build"]) == [31]
    assert request.call_args_list == [
        call(
            "GET",
            "/api/v2/projects/",
            params={"search": "deep work", "limit": 100, "offset": 0},
        ),
        call("GET", "/api/v2/projects/8"),
    ]


def test_unknown_project_keeps_friendly_error(client, monkeypatch):
    monkeypatch.setattr(client, "_v2_projects", lambda params=None: [])
    with pytest.raises(APIError, match="^Project not found: Missing$"):
        client._resolve_project_id("Missing")


def test_v2_version_conflict_envelope_is_friendly(client, monkeypatch):
    response = MagicMock()
    response.status_code = 409
    response.content = b'{"error": {}}'
    response.json.return_value = {
        "error": {
            "code": "version_conflict",
            "message": "Version mismatch",
            "details": {"current": _resource()},
        }
    }
    response.raise_for_status.side_effect = requests.exceptions.HTTPError("409")
    monkeypatch.setattr(requests, "request", MagicMock(return_value=response))

    with pytest.raises(
        APIError,
        match=r"The timer changed on the server \(someone else edited it\?\)\. Re-run the command\.",
    ):
        client._request("PATCH", "/api/v2/sessions/21", json={"note": "x"})


def test_v2_uuid_conflict_uses_server_message(client, monkeypatch):
    response = MagicMock()
    response.status_code = 409
    response.content = b'{"error": {}}'
    response.json.return_value = {
        "error": {
            "code": "uuid_conflict",
            "message": "That UUID belongs to a different session.",
            "details": None,
        }
    }
    response.raise_for_status.side_effect = requests.exceptions.HTTPError("409")
    monkeypatch.setattr(requests, "request", MagicMock(return_value=response))

    with pytest.raises(APIError, match="^That UUID belongs to a different session\\.$"):
        client._request("POST", "/api/v2/sessions/", json={})
