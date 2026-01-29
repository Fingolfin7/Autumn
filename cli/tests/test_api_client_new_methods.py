"""Tests for new API client methods (Phase 1 features)."""

import pytest
from unittest.mock import patch, MagicMock


@pytest.fixture
def mock_client():
    """Create an APIClient with mocked requests."""
    with patch("autumn_cli.api_client.get_api_key", return_value="test-key"):
        with patch("autumn_cli.api_client.get_base_url", return_value="http://test"):
            from autumn_cli.api_client import APIClient
            client = APIClient()
            return client


class TestCreateSubproject:
    def test_create_subproject_sends_correct_payload(self, mock_client):
        with patch.object(mock_client, "_request") as mock_req:
            mock_req.return_value = {"ok": True, "subproject": {"name": "NewSub"}}

            result = mock_client.create_subproject("MyProject", "NewSub", "A description")

            mock_req.assert_called_once_with(
                "POST",
                "/api/create_subproject/",
                json={"parent_project": "MyProject", "name": "NewSub", "description": "A description"}
            )
            assert result["ok"] is True

    def test_create_subproject_without_description(self, mock_client):
        with patch.object(mock_client, "_request") as mock_req:
            mock_req.return_value = {"ok": True}

            mock_client.create_subproject("MyProject", "NewSub")

            mock_req.assert_called_once_with(
                "POST",
                "/api/create_subproject/",
                json={"parent_project": "MyProject", "name": "NewSub"}
            )


class TestMarkProjectStatus:
    def test_mark_project_status_sends_correct_payload(self, mock_client):
        with patch.object(mock_client, "_request") as mock_req:
            mock_req.return_value = {"ok": True, "project": "MyProject", "status": "paused"}

            result = mock_client.mark_project_status("MyProject", "paused")

            mock_req.assert_called_once_with(
                "POST",
                "/api/mark/",
                json={"project": "MyProject", "status": "paused"}
            )
            assert result["status"] == "paused"


class TestRenameProject:
    def test_rename_project_sends_correct_payload(self, mock_client):
        with patch.object(mock_client, "_request") as mock_req:
            mock_req.return_value = {"ok": True, "project": "NewName"}

            result = mock_client.rename_project("OldName", "NewName")

            mock_req.assert_called_once_with(
                "POST",
                "/api/rename/",
                json={"type": "project", "project": "OldName", "new_name": "NewName"}
            )
            assert result["project"] == "NewName"


class TestRenameSubproject:
    def test_rename_subproject_sends_correct_payload(self, mock_client):
        with patch.object(mock_client, "_request") as mock_req:
            mock_req.return_value = {"ok": True, "project": "Parent", "subproject": "NewSub"}

            result = mock_client.rename_subproject("Parent", "OldSub", "NewSub")

            mock_req.assert_called_once_with(
                "POST",
                "/api/rename/",
                json={"type": "subproject", "project": "Parent", "subproject": "OldSub", "new_name": "NewSub"}
            )
            assert result["subproject"] == "NewSub"


class TestDeleteProject:
    def test_delete_project_returns_ok_on_204(self, mock_client):
        with patch("requests.request") as mock_req:
            mock_response = MagicMock()
            mock_response.status_code = 204
            mock_response.raise_for_status = MagicMock()
            mock_req.return_value = mock_response

            result = mock_client.delete_project("MyProject")

            assert result["ok"] is True
            assert result["deleted"] == "MyProject"


class TestDeleteSubproject:
    def test_delete_subproject_returns_ok_on_204(self, mock_client):
        with patch("requests.request") as mock_req:
            mock_response = MagicMock()
            mock_response.status_code = 204
            mock_response.raise_for_status = MagicMock()
            mock_req.return_value = mock_response

            result = mock_client.delete_subproject("MyProject", "MySub")

            assert result["ok"] is True
            assert result["deleted"] == "MySub"
            assert result["project"] == "MyProject"


class TestExportData:
    def test_export_data_sends_correct_payload(self, mock_client):
        with patch.object(mock_client, "_request") as mock_req:
            mock_req.return_value = {"sessions": [], "projects": []}

            result = mock_client.export_data(
                project="MyProject",
                start_date="2026-01-01",
                end_date="2026-01-31",
                compress=True
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

    def test_export_data_minimal_call(self, mock_client):
        with patch.object(mock_client, "_request") as mock_req:
            mock_req.return_value = {"sessions": [], "projects": []}

            mock_client.export_data()

            mock_req.assert_called_once_with(
                "POST",
                "/api/export/",
                json={"autumn_compatible": True}
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


class TestGetProjectTotals:
    def test_get_project_totals_sends_correct_params(self, mock_client):
        with patch.object(mock_client, "_request") as mock_req:
            mock_req.return_value = {"project": "MyProject", "total": 123.4, "subs": []}

            result = mock_client.get_project_totals(
                "MyProject",
                start_date="2026-01-01",
                end_date="2026-01-31"
            )

            mock_req.assert_called_once_with(
                "GET",
                "/api/totals/",
                params={
                    "project": "MyProject",
                    "compact": "true",
                    "start_date": "2026-01-01",
                    "end_date": "2026-01-31"
                }
            )
            assert result["total"] == 123.4


class TestSearchProjects:
    def test_search_projects_sends_correct_params(self, mock_client):
        with patch.object(mock_client, "_request") as mock_req:
            mock_req.return_value = {"projects": []}

            mock_client.search_projects("web", status="active")

            mock_req.assert_called_once_with(
                "GET",
                "/api/search_projects/",
                params={"search_term": "web", "status": "active"}
            )


class TestGetProject:
    def test_get_project_calls_correct_endpoint(self, mock_client):
        with patch.object(mock_client, "_request") as mock_req:
            mock_req.return_value = {"name": "MyProject", "status": "active"}

            result = mock_client.get_project("MyProject")

            mock_req.assert_called_once_with("GET", "/api/get_project/MyProject/")
            assert result["name"] == "MyProject"

    def test_get_project_url_encodes_special_chars(self, mock_client):
        with patch.object(mock_client, "_request") as mock_req:
            mock_req.return_value = {"name": "My Project"}

            mock_client.get_project("My Project")

            # URL encoding: space becomes %20
            mock_req.assert_called_once_with("GET", "/api/get_project/My%20Project/")
