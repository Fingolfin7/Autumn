"""v2 project/subproject API façade tests."""

from unittest.mock import MagicMock, call

import pytest
import requests

from autumn_cli.api_client import APIClient, APIError


@pytest.fixture
def client():
    return APIClient(
        api_key="key", base_url="https://autumn.example", wake_retry=False
    )


def _project(
    project_id=7,
    name="Deep Work",
    status="active",
    total_minutes=125.5,
    session_count=4,
):
    return {
        "id": project_id,
        "name": name,
        "status": status,
        "description": "Focused work",
        "context": {"id": 3, "name": "Work"},
        "tags": [{"id": 5, "name": "Focus"}],
        "start_date": "2026-01-02",
        "last_activity": "2026-07-15",
        "total_minutes": total_minutes,
        "session_count": session_count,
    }


def _subproject(subproject_id=11, name="Build", project_id=7):
    return {
        "id": subproject_id,
        "name": name,
        "description": "Implementation",
        "project_id": project_id,
        "last_activity": "2026-07-14",
        "total_minutes": 62.25,
        "session_count": 2,
    }


def test_project_translation_has_every_grouped_formatter_field(client):
    result = client._project_v2_to_legacy(_project())

    assert result["id"] == 7
    assert result["name"] == "Deep Work"
    assert result["description"] == "Focused work"
    assert result["status"] == "active"
    assert result["total_time"] == 125.5
    assert result["start_date"] == "2026-01-02"
    assert result["last_updated"] == "2026-07-15"
    assert result["session_count"] == 4
    assert result["avg_session_duration"] == 31.38
    assert result["context"] == "Work"
    assert result["tags"] == ["Focus"]


def test_grouped_rebuild_has_summary_groups_and_name_order(client, monkeypatch):
    resources = [
        _project(1, "Alpha", "active", 60, 2),
        _project(2, "Beta", "paused", 0, 0),
        _project(3, "Gamma", "active", 45, 1),
    ]
    fetch = MagicMock(return_value=resources)
    monkeypatch.setattr(client, "_v2_projects", fetch)
    monkeypatch.setattr(client, "_metadata_ids", MagicMock(return_value=(3, [5])))

    result = client.list_projects_grouped(context="Work", tags=["Focus"])

    fetch.assert_called_once_with({"context_ids": "3", "tag_ids": "5"})
    assert result["summary"] == {
        "active": 2,
        "paused": 1,
        "complete": 0,
        "archived": 0,
        "total": 3,
    }
    assert list(result["projects"]) == ["active", "paused", "complete", "archived"]
    assert [item["name"] for item in result["projects"]["active"]] == [
        "Alpha",
        "Gamma",
    ]
    assert result["projects"]["paused"][0]["avg_session_duration"] == 0


def test_grouped_filters_resolve_v1_metadata_names_to_v2_ids(client, monkeypatch):
    monkeypatch.setattr(
        client,
        "get_discovery_meta",
        MagicMock(
            return_value={
                "contexts": [{"id": 3, "name": "Work"}],
                "tags": [{"id": 5, "name": "Focus"}],
            }
        ),
    )
    request = MagicMock(return_value={"count": 0, "total": 0, "projects": []})
    monkeypatch.setattr(client, "_request", request)

    client.list_projects_grouped(context="work", tags=["FOCUS"])

    request.assert_called_once_with(
        "GET",
        "/api/v2/projects/",
        params={"context_ids": "3", "tag_ids": "5", "limit": 100, "offset": 0},
    )


def test_v2_project_collection_paginates_until_total(client, monkeypatch):
    request = MagicMock(
        side_effect=[
            {"count": 2, "total": 3, "projects": [_project(1, "A"), _project(2, "B")]},
            {"count": 1, "total": 3, "projects": [_project(3, "C")]},
        ]
    )
    monkeypatch.setattr(client, "_request", request)

    result = client._v2_projects({"status": "active"}, page_size=2)

    assert [project["name"] for project in result] == ["A", "B", "C"]
    assert request.call_args_list == [
        call(
            "GET",
            "/api/v2/projects/",
            params={"status": "active", "limit": 2, "offset": 0},
        ),
        call(
            "GET",
            "/api/v2/projects/",
            params={"status": "active", "limit": 2, "offset": 2},
        ),
    ]


def test_flat_listing_preserves_compact_and_full_legacy_shapes(client, monkeypatch):
    fetch = MagicMock(return_value=[_project()])
    monkeypatch.setattr(client, "_v2_projects", fetch)

    compact = client.list_projects_flat(status="active")
    full = client.list_projects_flat(search="deep", compact=False)

    assert compact == {"count": 1, "projects": ["Deep Work"]}
    assert full["count"] == 1
    assert full["projects"][0]["name"] == "Deep Work"
    assert full["projects"][0]["total_time"] == 125.5
    assert fetch.call_args_list == [
        call({"status": "active"}),
        call({"search": "deep"}),
    ]


def test_create_project_resolves_metadata_and_posts_non_retry_safe(client, monkeypatch):
    monkeypatch.setattr(client, "_metadata_ids", MagicMock(return_value=(3, [5, 6])))
    request = MagicMock(return_value=_project())
    monkeypatch.setattr(client, "_request", request)

    result = client.create_project(
        "Deep Work", "Focused work", context="Work", tags=["Focus", "CLI"]
    )

    request.assert_called_once_with(
        "POST",
        "/api/v2/projects/",
        json={
            "name": "Deep Work",
            "description": "Focused work",
            "context_id": 3,
            "tag_ids": [5, 6],
        },
    )
    assert result["name"] == "Deep Work"
    assert result["total_time"] == 125.5


def test_discovery_cache_refresh_flattens_v2_grouped_equivalent(client, monkeypatch):
    translated = client._project_v2_to_legacy(_project())
    monkeypatch.setattr(
        client,
        "list_projects_grouped",
        MagicMock(
            return_value={
                "projects": {
                    "active": [translated],
                    "paused": [],
                    "complete": [],
                    "archived": [],
                }
            }
        ),
    )
    save = MagicMock()
    monkeypatch.setattr("autumn_cli.utils.projects_cache.save_cached_projects", save)

    result = client.get_discovery_projects(refresh=True)

    assert result["cached"] is False
    assert result["projects"][0]["id"] == 7
    assert result["projects"][0]["total_time"] == 125.5
    assert result["projects"][0]["tags"] == ["Focus"]
    save.assert_called_once_with(result["projects"])


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"context": "Missing"}, "Unknown context: Missing"),
        ({"tags": ["Missing"]}, "Unknown tags: Missing"),
    ],
)
def test_create_project_unknown_metadata_is_friendly(client, monkeypatch, kwargs, message):
    monkeypatch.setattr(
        client,
        "get_discovery_meta",
        lambda **unused: {"contexts": [], "tags": []},
    )

    with pytest.raises(APIError, match=f"^{message}$"):
        client.create_project("New", **kwargs)


def test_get_project_translates_detail_and_subprojects(client, monkeypatch):
    monkeypatch.setattr(client, "_resolve_project_id", lambda name: 7)
    resource = _project()
    resource["subprojects"] = [_subproject()]
    request = MagicMock(return_value=resource)
    monkeypatch.setattr(client, "_request", request)

    result = client.get_project("Deep Work")

    request.assert_called_once_with("GET", "/api/v2/projects/7")
    assert result["context"] == "Work"
    assert result["tags"] == ["Focus"]
    assert result["subprojects"][0]["name"] == "Build"
    assert result["subprojects"][0]["total_time"] == 62.25
    assert result["subprojects"][0]["avg_session_duration"] == 31.12


def test_merge_projects_resolves_names_and_posts_v2_payload(client, monkeypatch):
    monkeypatch.setattr(
        client, "_resolve_project_id", MagicMock(side_effect=[7, 8])
    )
    response = {"id": 9, "name": "Merged"}
    request = MagicMock(return_value=response)
    monkeypatch.setattr(client, "_request", request)

    result = client.merge_projects("One", "Two", "Merged")
    assert result["message"] == "Successfully merged One and Two into Merged"
    assert result["project"]["name"] == "Merged"
    request.assert_called_once_with(
        "POST",
        "/api/v2/projects/merge/",
        json={"source_ids": [7, 8], "new_name": "Merged"},
    )


def test_merge_subprojects_resolves_names_and_posts_v2_payload(client, monkeypatch):
    monkeypatch.setattr(client, "_resolve_subproject_ids", MagicMock(return_value=[11, 12]))
    response = _subproject(13, "Merged")
    request = MagicMock(return_value=response)
    monkeypatch.setattr(client, "_request", request)

    result = client.merge_subprojects(7, "Build", "Test", "Merged")
    assert result["message"] == "Successfully merged Build and Test into Merged"
    assert result["subproject"]["name"] == "Merged"
    request.assert_called_once_with(
        "POST",
        "/api/v2/subprojects/merge/",
        json={"project_id": 7, "source_ids": [11, 12], "new_name": "Merged"},
    )


def test_project_resolution_uses_v2_search_and_ttl_cache(client, monkeypatch):
    fetch = MagicMock(return_value=[_project()])
    monkeypatch.setattr(client, "_v2_projects", fetch)

    assert client._resolve_project_id("deep work") == 7
    assert client._resolve_project_id("DEEP WORK") == 7
    fetch.assert_called_once_with({"search": "deep work"})


def test_project_resolution_scans_full_list_for_ambiguous_search(client, monkeypatch):
    fetch = MagicMock(
        side_effect=[
            [_project(7, "Deep Work"), _project(8, "Deep Work Notes")],
            [_project(7, "Deep Work"), _project(8, "Deep Work Notes")],
        ]
    )
    monkeypatch.setattr(client, "_v2_projects", fetch)

    assert client._resolve_project_id("DEEP WORK") == 7
    assert fetch.call_args_list == [call({"search": "DEEP WORK"}), call()]


def test_project_resolution_rejects_casefold_ambiguity(client, monkeypatch):
    monkeypatch.setattr(
        client,
        "_v2_projects",
        MagicMock(
            side_effect=[
                [_project(7, "Alpha"), _project(8, "ALPHA")],
                [_project(7, "Alpha"), _project(8, "ALPHA")],
            ]
        ),
    )

    with pytest.raises(APIError, match="^Project name is ambiguous: alpha$"):
        client._resolve_project_id("alpha")


def test_project_resolution_missing_is_friendly(client, monkeypatch):
    monkeypatch.setattr(client, "_v2_projects", lambda params=None: [])

    with pytest.raises(APIError, match="^Project not found: Missing$"):
        client._resolve_project_id("Missing")


def test_delete_project_conflict_envelope_uses_friendly_server_message(client, monkeypatch):
    monkeypatch.setattr(client, "_resolve_project_id", lambda name: 7)
    response = MagicMock()
    response.status_code = 409
    response.content = b'{"error": {}}'
    response.json.return_value = {
        "error": {
            "code": "conflict",
            "message": "Project is targeted by a commitment.",
            "details": None,
        }
    }
    response.raise_for_status.side_effect = requests.exceptions.HTTPError("409")
    monkeypatch.setattr(requests, "request", MagicMock(return_value=response))

    with pytest.raises(APIError, match=r"^Project is targeted by a commitment\.$"):
        client.delete_project("Deep Work")


def test_grouped_listing_applies_v1_window_semantics_client_side(client, monkeypatch):
    resources = [
        # wholly inside the window
        {"id": 1, "name": "In", "status": "active", "start_date": "2026-01-10",
         "last_activity": "2026-01-20", "total_minutes": 10.0, "session_count": 1,
         "description": "", "context": None, "tags": []},
        # starts before the window -> excluded
        {"id": 2, "name": "Early", "status": "active", "start_date": "2025-12-01",
         "last_activity": "2026-01-15", "total_minutes": 10.0, "session_count": 1,
         "description": "", "context": None, "tags": []},
        # activity after the window -> excluded
        {"id": 3, "name": "Late", "status": "active", "start_date": "2026-01-12",
         "last_activity": "2026-03-01", "total_minutes": 10.0, "session_count": 1,
         "description": "", "context": None, "tags": []},
        # no sessions: last_activity null falls back to start_date -> included
        {"id": 4, "name": "Empty", "status": "active", "start_date": "2026-01-11",
         "last_activity": None, "total_minutes": 0.0, "session_count": 0,
         "description": "", "context": None, "tags": []},
    ]
    monkeypatch.setattr(client, "_v2_projects", lambda params: resources)
    monkeypatch.setattr(client, "_metadata_ids", lambda **kw: (None, []))

    grouped = client.list_projects_grouped(
        start_date="2026-01-01", end_date="2026-01-31"
    )

    names = [p["name"] for p in grouped["projects"]["active"]]
    assert names == ["In", "Empty"]
    assert grouped["summary"]["total"] == 2
