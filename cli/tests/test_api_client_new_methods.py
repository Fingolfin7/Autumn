"""Tests for new API client methods (Phase 1 features)."""

import pytest
from unittest.mock import ANY, patch, MagicMock


@pytest.fixture
def mock_client():
    """Create an APIClient with mocked requests."""
    with patch("autumn_cli.api_client.get_api_key", return_value="test-key"):
        with patch("autumn_cli.api_client.get_base_url", return_value="http://test"):
            from autumn_cli.api_client import APIClient
            client = APIClient(wake_retry=False)
            return client


class TestCreateSubproject:
    def test_create_subproject_sends_correct_payload(self, mock_client):
        with (
            patch.object(mock_client, "_resolve_project_id", return_value=7),
            patch.object(mock_client, "_request") as mock_req,
        ):
            mock_req.return_value = {"id": 8, "name": "NewSub", "project_id": 7}

            result = mock_client.create_subproject("MyProject", "NewSub", "A description")

            mock_req.assert_called_once_with(
                "POST",
                "/api/v2/projects/7/subprojects/",
                json={"name": "NewSub", "description": "A description"}
            )
            assert result["ok"] is True
            assert result["subproject"]["name"] == "NewSub"

    def test_create_subproject_without_description(self, mock_client):
        with (
            patch.object(mock_client, "_resolve_project_id", return_value=7),
            patch.object(mock_client, "_request") as mock_req,
        ):
            mock_req.return_value = {"id": 8, "name": "NewSub", "project_id": 7}

            mock_client.create_subproject("MyProject", "NewSub")

            mock_req.assert_called_once_with(
                "POST",
                "/api/v2/projects/7/subprojects/",
                json={"name": "NewSub"}
            )


class TestMarkProjectStatus:
    def test_mark_project_status_sends_correct_payload(self, mock_client):
        with (
            patch.object(mock_client, "_resolve_project_id", return_value=7),
            patch.object(mock_client, "_request") as mock_req,
        ):
            mock_req.return_value = {"id": 7, "name": "MyProject", "status": "paused"}

            result = mock_client.mark_project_status("MyProject", "paused")

            mock_req.assert_called_once_with(
                "PATCH",
                "/api/v2/projects/7",
                json={"status": "paused"}
            )
            assert result["status"] == "paused"


class TestRenameProject:
    def test_rename_project_sends_correct_payload(self, mock_client):
        with (
            patch.object(mock_client, "_resolve_project_id", return_value=7),
            patch.object(mock_client, "_request") as mock_req,
        ):
            mock_req.return_value = {"id": 7, "name": "NewName"}

            result = mock_client.rename_project("OldName", "NewName")

            mock_req.assert_called_once_with(
                "PATCH",
                "/api/v2/projects/7",
                json={"name": "NewName"}
            )
            assert result["project"] == "NewName"


class TestRenameSubproject:
    def test_rename_subproject_sends_correct_payload(self, mock_client):
        with (
            patch.object(mock_client, "_resolve_project_id", return_value=7),
            patch.object(mock_client, "_resolve_subproject_ids", return_value=[8]),
            patch.object(mock_client, "_request") as mock_req,
        ):
            mock_req.return_value = {"id": 8, "name": "NewSub", "project_id": 7}

            result = mock_client.rename_subproject("Parent", "OldSub", "NewSub")

            mock_req.assert_called_once_with(
                "PATCH",
                "/api/v2/subprojects/8",
                json={"name": "NewSub"}
            )
            assert result["subproject"] == "NewSub"


class TestDeleteProject:
    def test_delete_project_returns_ok_on_204(self, mock_client):
        with (
            patch.object(mock_client, "_resolve_project_id", return_value=7),
            patch.object(mock_client, "_request", return_value={}) as mock_req,
        ):

            result = mock_client.delete_project("MyProject")

            assert result["ok"] is True
            assert result["deleted"] == "MyProject"
            mock_req.assert_called_once_with(
                "DELETE", "/api/v2/projects/7", retry_safe=True
            )


class TestDeleteSubproject:
    def test_delete_subproject_returns_ok_on_204(self, mock_client):
        with (
            patch.object(mock_client, "_resolve_project_id", return_value=7),
            patch.object(mock_client, "_resolve_subproject_ids", return_value=[8]),
            patch.object(mock_client, "_request", return_value={}) as mock_req,
        ):

            result = mock_client.delete_subproject("MyProject", "MySub")

            assert result["ok"] is True
            assert result["deleted"] == "MySub"
            assert result["project"] == "MyProject"
            mock_req.assert_called_once_with(
                "DELETE", "/api/v2/subprojects/8", retry_safe=True
            )


class TestDeleteSession:
    def test_delete_session_returns_ok_on_204(self, mock_client):
        with patch("requests.request") as mock_req:
            mock_response = MagicMock()
            mock_response.status_code = 204
            mock_response.content = b""
            mock_response.raise_for_status = MagicMock()
            mock_req.return_value = mock_response

            result = mock_client.delete_session(123)

            assert result["ok"] is True
            assert result["deleted"] == 123


class TestExportData:
    def test_export_data_defaults_to_v2_format2(self, mock_client):
        with (
            patch.object(mock_client, "_resolve_project_id", return_value=9),
            patch.object(mock_client, "_request") as mock_req,
        ):
            mock_req.return_value = {"format": 2, "projects": []}

            mock_client.export_data(
                project="MyProject",
                start_date="2026-01-01",
                end_date="2026-01-31",
                compress=True,
            )

            mock_req.assert_called_once_with(
                "GET",
                "/api/v2/export/",
                params={
                    "project_ids": "9",
                    "start_date": "2026-01-01",
                    "end_date": "2026-01-31",
                    "compress": "true",
                },
            )

    def test_export_data_minimal_call_uses_v2(self, mock_client):
        with patch.object(mock_client, "_request") as mock_req:
            mock_req.return_value = {"format": 2, "projects": []}

            mock_client.export_data()

            mock_req.assert_called_once_with("GET", "/api/v2/export/", params={})

    def test_export_data_legacy_keeps_v1_payload(self, mock_client):
        with patch.object(mock_client, "_request") as mock_req:
            mock_req.return_value = {"sessions": [], "projects": []}

            mock_client.export_data(
                project="MyProject",
                start_date="2026-01-01",
                end_date="2026-01-31",
                compress=True,
                legacy=True,
            )

            mock_req.assert_called_once_with(
                "POST",
                "/api/export/",
                json={
                    "project_name": "MyProject",
                    "start_date": "2026-01-01",
                    "end_date": "2026-01-31",
                    "compress": True,
                    "autumn_compatible": True
                }
            )


class TestImportData:
    def test_import_data_sends_correct_payload(self, mock_client):
        with patch.object(mock_client, "_request") as mock_req:
            mock_req.return_value = {"ok": True, "summary": {}}

            mock_client.import_data(
                data={"Project A": {}},
                force=True,
                tolerance=5,
                autumn_import=True,
                context="Work",
            )

            mock_req.assert_called_once_with(
                "POST",
                "/api/import/",
                json={
                    "data": {"Project A": {}},
                    "force": True,
                    "merge": False,
                    "tolerance": 5,
                    "autumn_import": True,
                    "context": "Work",
                },
            )

    def test_import_data_routes_format2_to_v2_endpoint(self, mock_client):
        with patch.object(mock_client, "_request") as mock_req:
            mock_req.return_value = {"sessions_imported": 1}

            document = {"format": 2, "projects": []}
            mock_client.import_data(data=document, force=True)

            mock_req.assert_called_once_with(
                "POST",
                "/api/v2/import/",
                json={"data": document, "force": True},
            )


class TestAuditTotals:
    def test_audit_totals_calls_correct_endpoint(self, mock_client):
        with patch.object(mock_client, "_request") as mock_req:
            mock_req.return_value = {
                "ok": True,
                "projects": {"count": 3, "changed": 1, "delta_total": 9.0},
                "subprojects": {"count": 5, "changed": 2, "delta_total": 18.0}
            }

            result = mock_client.audit_totals()

            mock_req.assert_called_once_with("POST", "/api/audit/")
            assert result["ok"] is True
            assert result["projects"]["changed"] == 1

    def test_audit_totals_dry_run_sends_payload(self, mock_client):
        with patch.object(mock_client, "_request") as mock_req:
            mock_req.return_value = {"ok": True, "dry_run": True}

            result = mock_client.audit_totals(dry_run=True)

            mock_req.assert_called_once_with(
                "POST", "/api/audit/", json={"dry_run": True}
            )
            assert result["dry_run"] is True


class TestStartTimer:
    def test_start_timer_sends_stop_after_when_provided(self, mock_client):
        resource = {
            "id": 5,
            "project": {"id": 7, "name": "MyProject"},
            "subproject_allocations": [],
            "start": "2026-07-16T08:00:00+00:00",
            "end": None,
            "active": True,
            "auto_stop_at": None,
            "duration_minutes": None,
            "elapsed_minutes": 0.0,
            "note": None,
        }
        with (
            patch.object(mock_client, "_resolve_project_id", return_value=7),
            patch.object(mock_client, "_request", return_value=resource) as mock_req,
        ):

            result = mock_client.start_timer("MyProject", stop_after="25m")

            mock_req.assert_called_once_with(
                "POST", "/api/v2/timers/",
                json={
                    "project_id": 7,
                    "start": ANY,
                    "stop_after_minutes": "25m",
                    "uuid": ANY,
                },
                retry_safe=True,
            )
            assert result == {
                "ok": True,
                "session": {
                    "id": 5,
                    "p": "MyProject",
                    "pid": 7,
                    "subs": [],
                    "start": "2026-07-16T08:00:00+00:00",
                    "end": None,
                    "stop_at": None,
                    "active": True,
                    "elapsed": 0.0,
                    "note": None,
                },
            }


class TestExcludeFilters:
    def test_log_activity_sends_exclude_param(self, mock_client):
        with (
            patch.object(mock_client, "_resolve_project_id", side_effect=[9, 10]),
            patch.object(mock_client, "_request") as mock_req,
        ):
            mock_req.return_value = {"count": 0, "total": 0, "sessions": []}

            mock_client.log_activity(exclude=["Admin", "Meta"])

            mock_req.assert_called_once_with(
                "GET",
                "/api/v2/sessions/",
                params={
                    "exclude_project_ids": "9,10",
                    "include": "note",
                    "limit": 100,
                    "offset": 0,
                },
            )

    def test_search_sessions_sends_exclude_param(self, mock_client):
        with (
            patch.object(mock_client, "_resolve_project_id", return_value=9),
            patch.object(mock_client, "_request") as mock_req,
        ):
            mock_req.return_value = {"count": 0, "total": 0, "sessions": []}

            mock_client.search_sessions(exclude=["Admin"])

            mock_req.assert_called_once_with(
                "GET",
                "/api/v2/sessions/",
                params={
                    "exclude_project_ids": "9",
                    "include": "note",
                    "limit": 100,
                    "offset": 0,
                },
            )

    def test_list_projects_grouped_sends_exclude_param(self, mock_client):
        with (
            patch.object(mock_client, "_resolve_project_id", return_value=9),
            patch.object(mock_client, "_request") as mock_req,
        ):
            mock_req.return_value = {"count": 0, "total": 0, "projects": []}

            mock_client.list_projects_grouped(exclude=["Admin"])

            mock_req.assert_called_once_with(
                "GET",
                "/api/v2/projects/",
                params={"exclude_project_ids": "9", "limit": 100, "offset": 0},
            )

    def test_list_sessions_sends_exclude_param(self, mock_client):
        with (
            patch.object(mock_client, "_resolve_project_id", return_value=9),
            patch.object(mock_client, "_request") as mock_req,
        ):
            mock_req.return_value = {"count": 0, "total": 0, "sessions": []}

            mock_client.list_sessions(exclude=["Admin"])

            mock_req.assert_called_once_with(
                "GET",
                "/api/v2/sessions/",
                params={
                    "exclude_project_ids": "9",
                    "include": "note",
                    "limit": 100,
                    "offset": 0,
                },
            )


class TestChartDateParams:
    def test_tally_by_context_uses_v2_iso_date_format(self, mock_client):
        with patch.object(mock_client, "_request") as mock_req:
            mock_req.return_value = {"by": "context", "entries": []}

            mock_client.tally_by_context(
                start_date="2026-01-15",
                end_date="2026-01-31",
            )

            mock_req.assert_called_once_with(
                "GET",
                "/api/v2/reports/tallies/",
                params={
                    "by": "context",
                    "start_date": "2026-01-15",
                    "end_date": "2026-01-31",
                },
            )

    def test_get_hierarchy_uses_v2_iso_date_format(self, mock_client):
        with patch.object(mock_client, "_request") as mock_req:
            mock_req.return_value = {}

            mock_client.get_hierarchy(
                start_date="2026-01-15",
                end_date="2026-01-31",
            )

            mock_req.assert_called_once_with(
                "GET",
                "/api/v2/reports/hierarchy/",
                params={"start_date": "2026-01-15", "end_date": "2026-01-31"},
            )


class TestGetProjectTotals:
    def test_get_project_totals_sends_correct_params(self, mock_client):
        with (
            patch.object(mock_client, "_resolve_project_id", return_value=7),
            patch.object(mock_client, "_request") as mock_req,
        ):
            def side_effect(method, endpoint, params=None, **kwargs):
                if endpoint == "/api/v2/reports/totals/":
                    return {"total_minutes": 123.4, "session_count": 5}
                return {"by": "subproject", "entries": []}

            mock_req.side_effect = side_effect

            result = mock_client.get_project_totals(
                "MyProject",
                start_date="2026-01-01",
                end_date="2026-01-31"
            )

            mock_req.assert_any_call(
                "GET",
                "/api/v2/reports/totals/",
                params={
                    "project_ids": "7",
                    "start_date": "2026-01-01",
                    "end_date": "2026-01-31"
                }
            )
            assert result == {"project": "MyProject", "total": 123.4, "subs": []}


class TestSearchProjects:
    def test_search_projects_sends_correct_params(self, mock_client):
        with patch.object(mock_client, "_request") as mock_req:
            mock_req.return_value = {"count": 0, "total": 0, "projects": []}

            mock_client.search_projects("web", status="active")

            mock_req.assert_called_once_with(
                "GET",
                "/api/v2/projects/",
                params={"search": "web", "status": "active", "limit": 100, "offset": 0}
            )


class TestGetProject:
    def test_get_project_calls_correct_endpoint(self, mock_client):
        with (
            patch.object(mock_client, "_resolve_project_id", return_value=7),
            patch.object(mock_client, "_request") as mock_req,
        ):
            mock_req.return_value = {"id": 7, "name": "MyProject", "status": "active", "subprojects": []}

            result = mock_client.get_project("MyProject")

            mock_req.assert_called_once_with("GET", "/api/v2/projects/7")
            assert result["name"] == "MyProject"

    def test_get_project_resolves_name_to_numeric_v2_url(self, mock_client):
        with (
            patch.object(mock_client, "_resolve_project_id", return_value=11) as resolve,
            patch.object(mock_client, "_request") as mock_req,
        ):
            mock_req.return_value = {"id": 11, "name": "My Project", "subprojects": []}

            mock_client.get_project("My Project")

            resolve.assert_called_once_with("My Project")
            mock_req.assert_called_once_with("GET", "/api/v2/projects/11")
