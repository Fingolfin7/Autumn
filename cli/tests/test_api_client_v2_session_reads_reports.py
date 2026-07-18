"""v2 completed-session read and report façade tests."""

from unittest.mock import MagicMock, call

import pytest
from click.testing import CliRunner

from autumn_cli.api_client import APIClient
from autumn_cli.commands.sessions import log


def _resource(*, session_id=21, project_id=8, project="Deep Work", note="Focus"):
    return {
        "id": session_id,
        "uuid": f"00000000-0000-0000-0000-{session_id:012d}",
        "version": 4,
        "project": {"id": project_id, "name": project},
        "subproject_allocations": [
            {"subproject_id": 31, "name": "Build", "allocation_bp": 6000},
            {"subproject_id": 32, "name": "Review", "allocation_bp": 4000},
        ],
        "start": "2026-07-16T08:00:00+00:00",
        "end": "2026-07-16T08:45:00+00:00",
        "active": False,
        "duration_minutes": 45.0,
        "elapsed_minutes": None,
        "note": note,
    }


def _legacy(*, session_id=21, project="Deep Work", note="Focus"):
    return {
        "id": session_id,
        "version": 4,
        "project": project,
        "subprojects": ["Build", "Review"],
        "subproject_allocations": [
            {"subproject_id": 31, "name": "Build", "allocation_bp": 6000},
            {"subproject_id": 32, "name": "Review", "allocation_bp": 4000},
        ],
        "start_time": "2026-07-16T08:00:00+00:00",
        "end_time": "2026-07-16T08:45:00+00:00",
        "duration_minutes": 45.0,
        "note": note,
    }


@pytest.fixture
def client():
    return APIClient(
        api_key="key", base_url="https://autumn.example", wake_retry=False
    )


def test_log_activity_resolves_all_name_filters_translates_and_paginates(
    client, monkeypatch
):
    project_ids = {"Deep Work": 8, "Admin": 9}
    monkeypatch.setattr(client, "_resolve_project_id", project_ids.__getitem__)
    monkeypatch.setattr(
        client,
        "get_discovery_meta",
        lambda **kwargs: {
            "contexts": [{"id": 4, "name": "Office"}],
            "tags": [{"id": 6, "name": "Python"}],
        },
    )
    second = _resource(session_id=20, project_id=7, project="Planning", note=None)
    request = MagicMock(
        side_effect=[
            {"count": 1, "total": 2, "sessions": [_resource()]},
            {"count": 1, "total": 2, "sessions": [second]},
        ]
    )
    monkeypatch.setattr(client, "_request", request)

    result = client.log_activity(
        project="Deep Work",
        start_date="2026-07-01",
        end_date="2026-07-16",
        context="office",
        tags=["python"],
        exclude=["Admin"],
    )

    common = {
        "project_ids": "8",
        "start_date": "2026-07-01",
        "end_date": "2026-07-16",
        "context_ids": "4",
        "tag_ids": "6",
        "exclude_project_ids": "9",
        "include": "note",
        "limit": 100,
    }
    assert request.call_args_list == [
        call("GET", "/api/v2/sessions/", params={**common, "offset": 0}),
        call("GET", "/api/v2/sessions/", params={**common, "offset": 1}),
    ]
    assert result == {
        "count": 2,
        "logs": [
            _legacy(),
            _legacy(session_id=20, project="Planning", note=None),
        ],
    }


def test_search_sessions_maps_note_limit_offset_and_exact_legacy_shape(
    client, monkeypatch
):
    monkeypatch.setattr(client, "_resolve_project_id", lambda name: 8)
    request = MagicMock(
        return_value={"count": 1, "total": 8, "sessions": [_resource()]}
    )
    monkeypatch.setattr(client, "_request", request)

    result = client.search_sessions(
        project="Deep Work", note_snippet="Focus", limit=1, offset=5, active=False
    )

    request.assert_called_once_with(
        "GET",
        "/api/v2/sessions/",
        params={
            "project_ids": "8",
            "note_snippet": "Focus",
            "include": "note",
            "limit": 1,
            "offset": 5,
        },
    )
    assert result == {"count": 1, "sessions": [_legacy()]}


def test_search_sessions_active_variant_uses_timers_and_elapsed_minutes(
    client, monkeypatch
):
    active = _resource()
    active.update(
        {
            "end": None,
            "active": True,
            "duration_minutes": None,
            "elapsed_minutes": 12.5,
        }
    )
    request = MagicMock(return_value={"count": 1, "timers": [active]})
    monkeypatch.setattr(client, "_request", request)

    result = client.search_sessions(active=True)

    request.assert_called_once_with("GET", "/api/v2/timers/")
    expected = _legacy()
    expected.update({"end_time": None, "duration_minutes": 12.5})
    assert result == {"count": 1, "sessions": [expected]}


def test_list_sessions_uses_same_translation_and_fetches_complete_collection(
    client, monkeypatch
):
    request = MagicMock(
        return_value={"count": 1, "total": 1, "sessions": [_resource()]}
    )
    monkeypatch.setattr(client, "_request", request)

    assert client.list_sessions(start_date="2026-07-01") == [_legacy()]
    request.assert_called_once_with(
        "GET",
        "/api/v2/sessions/",
        params={
            "start_date": "2026-07-01",
            "include": "note",
            "limit": 100,
            "offset": 0,
        },
    )


def test_get_project_totals_keeps_minutes_and_legacy_keys(client, monkeypatch):
    monkeypatch.setattr(client, "_resolve_project_id", lambda name: 8)

    def fake_request(method, endpoint, params=None, **kwargs):
        if endpoint == "/api/v2/reports/totals/":
            assert params == {"project_ids": "8", "end_date": "2026-07-16"}
            return {"total_minutes": 123.4567, "session_count": 3}
        assert endpoint == "/api/v2/reports/tallies/"
        assert params == {
            "project_ids": "8",
            "end_date": "2026-07-16",
            "by": "subproject",
        }
        return {"by": "subproject", "entries": []}

    monkeypatch.setattr(client, "_request", fake_request)

    result = client.get_project_totals("Deep Work", end_date="2026-07-16")

    assert result == {"project": "Deep Work", "total": 123.4567, "subs": []}


def test_project_tally_resolves_all_filter_names_and_translates_exactly(
    client, monkeypatch
):
    monkeypatch.setattr(client, "_resolve_project_id", lambda name: 8)
    monkeypatch.setattr(
        client,
        "get_discovery_meta",
        lambda **kwargs: {
            "contexts": [{"id": 4, "name": "Office"}],
            "tags": [{"id": 6, "name": "Python"}],
        },
    )
    request = MagicMock(
        return_value={
            "by": "project",
            "entries": [
                {"id": 8, "name": "Deep Work", "total_minutes": 90.5, "session_count": 2}
            ],
        }
    )
    monkeypatch.setattr(client, "_request", request)

    result = client.tally_by_sessions(
        "Deep Work", context="office", tags=["python"]
    )

    request.assert_called_once_with(
        "GET",
        "/api/v2/reports/tallies/",
        params={"by": "project", "project_ids": "8", "context_ids": "4", "tag_ids": "6"},
    )
    assert result == [{"name": "Deep Work", "total_time": 90.5}]


def test_subproject_tally_collapses_residuals_from_multiple_projects(
    client, monkeypatch
):
    monkeypatch.setattr(client, "_resolve_project_id", lambda name: 8)
    request = MagicMock(
        return_value={
            "by": "subproject",
            "entries": [
                {"kind": "subproject", "id": 31, "name": "Build", "total_minutes": 50},
                {"kind": "residual", "project_id": 8, "name": None, "total_minutes": 10},
                {"kind": "residual", "project_id": 9, "name": None, "total_minutes": 15.5},
            ],
        }
    )
    monkeypatch.setattr(client, "_request", request)

    result = client.tally_by_subprojects("Deep Work")

    request.assert_called_once_with(
        "GET",
        "/api/v2/reports/tallies/",
        params={"by": "subproject", "project_ids": "8"},
    )
    assert result == [
        {"name": "Build", "total_time": 50},
        {"name": "no subproject", "total_time": 25.5},
    ]


@pytest.mark.parametrize(
    ("method", "by", "kwargs", "resolved"),
    [
        ("tally_by_context", "context", {"start_date": "2026-07-01"}, {"start_date": "2026-07-01"}),
        ("tally_by_status", "status", {"context": "Office"}, {"context_ids": "4"}),
        ("tally_by_tags", "tag", {}, {}),
    ],
)
def test_remaining_tallies_use_v2_and_normalized_legacy_shape(
    client, monkeypatch, method, by, kwargs, resolved
):
    monkeypatch.setattr(
        client,
        "get_discovery_meta",
        lambda **options: {"contexts": [{"id": 4, "name": "Office"}], "tags": []},
    )
    request = MagicMock(
        return_value={
            "by": by,
            "entries": [{"id": 4, "name": "Office", "total_minutes": 75, "session_count": 2}],
        }
    )
    monkeypatch.setattr(client, "_request", request)

    result = getattr(client, method)(**kwargs)

    request.assert_called_once_with(
        "GET", "/api/v2/reports/tallies/", params={"by": by, **resolved}
    )
    assert result == [{"name": "Office", "total_time": 75}]


def test_hierarchy_drops_residual_children_and_builds_legacy_nesting(
    client, monkeypatch
):
    request = MagicMock(
        return_value={
            "projects": [
                {
                    "id": 8,
                    "name": "Deep Work",
                    "total_minutes": 90,
                    "children": [
                        {"kind": "subproject", "id": 31, "name": "Build", "total_minutes": 60},
                        {"kind": "residual", "id": None, "name": None, "total_minutes": 30},
                    ],
                    "legacy_overallocated": False,
                }
            ]
        }
    )
    monkeypatch.setattr(client, "_request", request)

    result = client.get_hierarchy(start_date="2026-07-01", end_date="2026-07-16")

    request.assert_called_once_with(
        "GET",
        "/api/v2/reports/hierarchy/",
        params={"start_date": "2026-07-01", "end_date": "2026-07-16"},
    )
    assert result == {
        "name": "All",
        "children": [
            {
                "name": "All",
                "context_id": None,
                "children": [
                    {
                        "name": "Deep Work",
                        "project_id": 8,
                        "total_time": 90,
                        "children": [
                            {"name": "Build", "subproject_id": 31, "total_time": 60}
                        ],
                    }
                ],
            }
        ],
    }


def test_log_command_keeps_period_to_explicit_iso_date_conversion(monkeypatch):
    captured = {}

    class FakeClient:
        def get_discovery_meta(self, **kwargs):
            return {"contexts": [], "tags": []}

        def log_activity(self, **kwargs):
            captured.update(kwargs)
            return {"count": 0, "logs": []}

    monkeypatch.setattr("autumn_cli.commands.sessions.APIClient", FakeClient)
    monkeypatch.setattr(
        "autumn_cli.utils.periods.period_to_dates",
        lambda period: ("2026-07-09", "2026-07-16"),
    )

    result = CliRunner().invoke(log, ["--period", "week"])

    assert result.exit_code == 0
    assert captured["period"] is None
    assert captured["start_date"] == "2026-07-09"
    assert captured["end_date"] == "2026-07-16"


def test_get_project_totals_includes_subproject_breakdown(client, monkeypatch):
    calls = []

    def fake_request(method, endpoint, params=None, json=None, **kwargs):
        calls.append((endpoint, dict(params or {})))
        if endpoint == "/api/v2/reports/totals/":
            return {"total_minutes": 120.0, "session_count": 3}
        assert endpoint == "/api/v2/reports/tallies/"
        assert params["by"] == "subproject"
        return {
            "by": "subproject",
            "entries": [
                {"kind": "subproject", "id": 1, "name": "alpha", "total_minutes": 70.0},
                {"kind": "residual", "id": None, "name": None, "total_minutes": 30.0,
                 "project_id": 9},
                {"kind": "residual", "id": None, "name": None, "total_minutes": 20.0,
                 "project_id": 10},
            ],
        }

    monkeypatch.setattr(client, "_request", fake_request)
    monkeypatch.setattr(client, "_resolve_project_id", lambda name: 9)

    result = client.get_project_totals("Alpha Project")

    assert result["total"] == 120.0
    assert ["alpha", 70.0] in result["subs"]
    assert ["no subproject", 50.0] in result["subs"]
    assert len(calls) == 2
