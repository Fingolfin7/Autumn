"""Contract tests for the APIClient-backed MCP server."""

import importlib.util
import inspect
from pathlib import Path
from unittest.mock import Mock

import pytest


pytest.importorskip("mcp", reason="install the optional 'mcp' extra to run MCP tests")

from autumn_cli import mcp_server
from autumn_cli.api_client import APIError


def _load_legacy_module():
    path = Path(__file__).parent / "fixtures" / "legacy_autumn_mcp.py"
    spec = importlib.util.spec_from_file_location("legacy_autumn_mcp", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _registry(server):
    """Return FastMCP's name -> Tool mapping across supported SDK releases."""
    manager = getattr(server, "_tool_manager", None)
    tools = getattr(manager, "_tools", None)
    if isinstance(tools, dict):
        return tools
    tools = getattr(server, "_tools", None)
    if isinstance(tools, dict):
        return tools
    raise AssertionError("Unsupported FastMCP tool registry layout")


def _tool_callable(tool):
    for attribute in ("fn", "function", "callback"):
        value = getattr(tool, attribute, None)
        if callable(value):
            return value
    raise AssertionError(f"Could not find callable for tool {tool!r}")


def test_legacy_tool_inventory_and_parameter_parity():
    legacy = _registry(_load_legacy_module().mcp)
    current = _registry(mcp_server.mcp)

    missing = set(legacy) - set(current)
    print(f"legacy={len(legacy)} current={len(current)} missing={sorted(missing)}")
    assert not missing

    for name, legacy_tool in legacy.items():
        old = inspect.signature(_tool_callable(legacy_tool)).parameters
        new = inspect.signature(_tool_callable(current[name])).parameters
        expected = {key: value for key, value in old.items() if key != "compact"}
        assert list(new) == list(expected), name
        for parameter, old_value in expected.items():
            assert new[parameter].default == old_value.default, (name, parameter)


@pytest.fixture
def client(monkeypatch):
    fake = Mock()
    monkeypatch.setattr(mcp_server, "_client", fake)
    return fake


def test_timer_tools_delegate_and_preserve_results(client):
    client.get_timer_status.return_value = {"active": 1}
    client.start_timer.return_value = {"ok": True, "session": {"id": 1}}
    client.stop_timer.return_value = {"ok": True, "duration": 12}

    assert mcp_server.status(session_id=1, project="Work") == {
        "active": 1,
        "unit": "minutes",
    }
    assert mcp_server.start("Work", ["Build"], "note") == {
        "ok": True,
        "session": {"id": 1},
        "unit": "minutes",
    }
    assert mcp_server.stop("done", 1, "Work") == {
        "ok": True,
        "duration": 12,
        "unit": "minutes",
    }
    client.get_timer_status.assert_called_once_with(session_id=1, project="Work")
    client.start_timer.assert_called_once_with("Work", subprojects=["Build"], note="note")
    client.stop_timer.assert_called_once_with(session_id=1, project="Work", note="done")


def test_log_and_projects_delegate_with_translated_arguments(client):
    client.log_activity.return_value = {"count": 0, "logs": []}
    client.list_projects_grouped.return_value = {"projects": {}}

    assert mcp_server.log(period="month", project="Work", context="Desk", tags=["Focus"]) == {
        "count": 0,
        "logs": [],
        "unit": "minutes",
    }
    assert mcp_server.projects(start_date="2026-01-01", tags=["Focus"]) == {
        "projects": {}
    }
    client.log_activity.assert_called_once_with(
        period="month", project="Work", start_date=None, end_date=None,
        context="Desk", tags=["Focus"]
    )
    client.list_projects_grouped.assert_called_once_with(
        start_date="2026-01-01", end_date=None, context=None, tags=["Focus"]
    )


def test_reports_export_commitments_and_audit_delegate(client):
    client.tally_by_subprojects.return_value = [{"name": "Build", "total_time": 5}]
    client.get_hierarchy.return_value = {"name": "All", "children": []}
    client.export_data.return_value = {"format": 2}
    client.list_commitments.return_value = {"commitments": [{"id": 7}]}
    client.audit_totals.return_value = {"detail": "Deprecated; totals are computed dynamically."}

    assert mcp_server.tally_by_subprojects("Work", context="Desk") == [
        {"name": "Build", "total_time": 5}
    ]
    assert mcp_server.hierarchy("2026-01-01", "2026-02-01")["name"] == "All"
    assert mcp_server.export_data(project="Work", compress=True) == {"format": 2}
    assert mcp_server.list_commitments(active=True, streak=True) == {
        "commitments": [{"id": 7}]
    }
    assert "Deprecated" in mcp_server.audit_totals()["detail"]

    client.tally_by_subprojects.assert_called_once_with(
        "Work", start_date=None, end_date=None, context="Desk", tags=None
    )
    client.get_hierarchy.assert_called_once_with(
        start_date="2026-01-01", end_date="2026-02-01"
    )
    client.export_data.assert_called_once_with(
        project="Work", start_date=None, end_date=None, context=None, tags=None,
        compress=True, autumn_compatible=True
    )
    client.list_commitments.assert_called_once_with(
        active=True, aggregation_type=None, progress=True, streak=True
    )
    client.audit_totals.assert_called_once_with()


def test_api_error_is_returned_in_legacy_json_error_shape(client):
    client.start_timer.side_effect = APIError("Project not found: Missing")
    assert mcp_server.start("Missing") == {"error": "Project not found: Missing"}


def test_api_token_alias_creates_lazy_shared_client(monkeypatch):
    constructor = Mock(return_value=Mock())
    monkeypatch.setattr(mcp_server, "APIClient", constructor)
    monkeypatch.setattr(mcp_server, "_client", None)
    monkeypatch.delenv("AUTUMN_API_KEY", raising=False)
    monkeypatch.setenv("AUTUMN_API_TOKEN", "legacy-token")
    monkeypatch.setenv("AUTUMN_API_BASE", "https://autumn.example")

    first = mcp_server._get_client()
    assert mcp_server._get_client() is first
    constructor.assert_called_once_with(
        api_key="legacy-token", base_url="https://autumn.example", quiet=True
    )


def test_me_delegates_v2_identity_marker(client):
    client.get_me.return_value = {"username": "mushu", "api_version": "v2"}
    assert mcp_server.me()["api_version"] == "v2"
    client.get_me.assert_called_once_with()
