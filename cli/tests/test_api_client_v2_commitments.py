"""v2 commitment API façade tests."""

import re
from pathlib import Path
from unittest.mock import MagicMock, call

import pytest
import requests

from autumn_cli.api_client import APIClient, APIError


@pytest.fixture
def client():
    return APIClient(
        api_key="key", base_url="https://autumn.example", wake_retry=False
    )


def _resource(
    *,
    commitment_id=7,
    version=4,
    name="Deep Work",
    aggregation_type="project",
    active=True,
    pending_revision=None,
):
    return {
        "id": commitment_id,
        "version": version,
        "active": active,
        "aggregation_type": aggregation_type,
        "target": {"kind": aggregation_type, "id": 8, "name": name},
        "commitment_type": "time",
        "period": "weekly",
        "start_date": "2026-07-01",
        "timezone": "Europe/Prague",
        "generation": 2,
        "target_value": 300,
        "banking_enabled": True,
        "max_balance": 600,
        "min_balance": -120,
        "balance": 60,
        "filters": {
            "include_project_ids": [9],
            "exclude_project_ids": [],
            "include_subproject_ids": [],
            "exclude_subproject_ids": [],
            "include_context_ids": [],
            "exclude_context_ids": [],
            "include_tag_ids": [],
            "exclude_tag_ids": [],
        },
        "current_period": {
            "start": "2026-07-13T00:00:00+02:00",
            "end": "2026-07-20T00:00:00+02:00",
            "accrued": 240,
            "target": 300,
            "met": False,
        },
        "pending_revision": pending_revision,
        "ledger_start_at": "2026-07-13T08:00:00+02:00",
    }


def test_list_commitments_uses_v2_and_translates_exact_compact_shape(
    client, monkeypatch
):
    pending = {
        "effective_from": "2026-07-20T00:00:00+02:00",
        "changes": {"target_value": 360},
    }
    request = MagicMock(
        return_value={
            "count": 2,
            "commitments": [
                _resource(pending_revision=pending),
                _resource(commitment_id=8, active=False),
            ],
        }
    )
    monkeypatch.setattr(client, "_request", request)

    result = client.list_commitments(active=True, streak=True, compact=True)

    request.assert_called_once_with(
        "GET", "/api/v2/commitments/", params={"include": "streak"}
    )
    assert result == {
        "ok": True,
        "count": 1,
        "commitments": [
            {
                "id": 7,
                "agg": "project",
                "name": "Deep Work",
                "type": "time",
                "period": "weekly",
                "target": 300,
                "bal": 60,
                "active": True,
                "prog": {"actual": 240, "pct": 80, "status": "in-progress"},
                "pending_revision": pending,
            }
        ],
    }


def test_get_commitment_uses_v2_and_translates_full_legacy_shape(client, monkeypatch):
    request = MagicMock(return_value=_resource())
    monkeypatch.setattr(client, "_request", request)

    result = client.get_commitment(7)

    request.assert_called_once_with("GET", "/api/v2/commitments/7")
    commitment = result["commitment"]
    assert result["ok"] is True
    assert commitment["target_name"] == "Deep Work"
    assert commitment["target_id"] == 8
    assert commitment["target"] == 300
    assert commitment["progress"] == {
        "actual": 240,
        "target": 300,
        "percentage": 80,
        "balance": 60,
        "current_surplus": -60,
        "status": "in-progress",
        "period_start": "2026-07-13T00:00:00+02:00",
        "effective_period_start": "2026-07-13T08:00:00+02:00",
        "period_end": "2026-07-20T00:00:00+02:00",
        "commitment_type": "time",
        "period": "weekly",
    }
    assert commitment["rules"] == ["include projects: 9"]


def test_create_commitment_resolves_target_and_filters_for_v2(client, monkeypatch):
    resolve = MagicMock(side_effect=lambda name: {"Deep Work": 8, "Admin": 9}[name])
    monkeypatch.setattr(client, "_resolve_project_id", resolve)
    request = MagicMock(return_value=_resource())
    monkeypatch.setattr(client, "_request", request)

    result = client.create_commitment(
        {
            "aggregation_type": "project",
            "target": "Deep Work",
            "target_value": 300,
            "commitment_type": "time",
            "period": "weekly",
            "include_projects": ["Admin"],
        }
    )

    request.assert_called_once_with(
        "POST",
        "/api/v2/commitments/",
        json={
            "aggregation_type": "project",
            "project_id": 8,
            "target_value": 300,
            "commitment_type": "time",
            "period": "weekly",
            "filters": {"include_project_ids": [9]},
        },
    )
    assert result["commitment"]["target_name"] == "Deep Work"
    assert result["commitment"]["progress"]["percentage"] == 80


@pytest.mark.parametrize(
    ("aggregation_type", "target", "expected_key", "expected_id", "patch_name"),
    [
        ("subproject", "Build", "subproject_id", 31, "_resolve_commitment_subproject_id"),
        ("context", "Work", "context_id", 3, "_resolve_commitment_context_id"),
    ],
)
def test_create_commitment_resolves_other_named_targets(
    client,
    monkeypatch,
    aggregation_type,
    target,
    expected_key,
    expected_id,
    patch_name,
):
    resolver = MagicMock(return_value=expected_id)
    monkeypatch.setattr(client, patch_name, resolver)
    request = MagicMock(
        return_value=_resource(name=target, aggregation_type=aggregation_type)
    )
    monkeypatch.setattr(client, "_request", request)
    data = {"aggregation_type": aggregation_type, "target": target}
    if aggregation_type == "subproject":
        data["project"] = "Deep Work"

    client.create_commitment(data)

    assert request.call_args.kwargs["json"] == {
        "aggregation_type": aggregation_type,
        expected_key: expected_id,
    }


def test_create_commitment_resolves_named_tag_target(client, monkeypatch):
    resolver = MagicMock(return_value=[5])
    monkeypatch.setattr(client, "_resolve_commitment_tag_ids", resolver)
    request = MagicMock(return_value=_resource(name="Focus", aggregation_type="tag"))
    monkeypatch.setattr(client, "_request", request)

    client.create_commitment({"aggregation_type": "tag", "target": "Focus"})

    assert request.call_args.kwargs["json"] == {
        "aggregation_type": "tag",
        "tag_id": 5,
    }


def test_update_commitment_fetches_version_merges_filters_and_patches_v2(
    client, monkeypatch
):
    updated = _resource(version=5)
    updated["pending_revision"] = {
        "effective_from": "2026-07-20T00:00:00+02:00",
        "changes": {"target_value": 360},
    }
    request = MagicMock(side_effect=[_resource(), updated])
    monkeypatch.setattr(client, "_request", request)
    monkeypatch.setattr(client, "_resolve_project_id", MagicMock(return_value=10))

    result = client.update_commitment(
        7, {"target_value": 360, "exclude_projects": ["Meetings"]}
    )

    assert request.call_args_list == [
        call("GET", "/api/v2/commitments/7"),
        call(
            "PATCH",
            "/api/v2/commitments/7",
            json={
                "target_value": 360,
                "filters": {
                    "include_project_ids": [9],
                    "exclude_project_ids": [10],
                    "include_subproject_ids": [],
                    "exclude_subproject_ids": [],
                    "include_context_ids": [],
                    "exclude_context_ids": [],
                    "include_tag_ids": [],
                    "exclude_tag_ids": [],
                },
            },
            headers={"If-Match": "4"},
        ),
    ]
    assert result["commitment"]["pending_revision"] == updated["pending_revision"]


def test_delete_commitment_uses_retry_safe_v2_delete(client, monkeypatch):
    request = MagicMock(return_value={})
    monkeypatch.setattr(client, "_request", request)

    assert client.delete_commitment(7) == {"ok": True}
    request.assert_called_once_with(
        "DELETE", "/api/v2/commitments/7", retry_safe=True
    )


def test_restart_commitment_uses_required_balance_payload_and_is_not_retry_safe(
    client, monkeypatch
):
    restarted = _resource(version=1)
    restarted["generation"] = 3
    request = MagicMock(return_value=restarted)
    monkeypatch.setattr(client, "_request", request)

    result = client.restart_commitment(
        7,
        keep_balance=False,
        changes={"period": "monthly", "timezone": "UTC"},
    )

    request.assert_called_once_with(
        "POST",
        "/api/v2/commitments/7/restart/",
        json={
            "keep_balance": False,
            "changes": {"period": "monthly", "timezone": "UTC"},
        },
    )
    assert result["commitment"]["generation"] == 3


def test_adjust_commitment_uses_v2_and_returns_legacy_envelope(client, monkeypatch):
    adjustment = {
        "seq": 4,
        "amount": -30,
        "effective_at": "2026-07-16T10:00:00+02:00",
        "reason": "Correction",
        "balance": 30,
    }
    request = MagicMock(return_value=adjustment)
    monkeypatch.setattr(client, "_request", request)

    result = client.adjust_commitment(7, amount=-30, reason="Correction")

    request.assert_called_once_with(
        "POST",
        "/api/v2/commitments/7/adjustments/",
        json={"amount": -30, "reason": "Correction"},
    )
    assert result == {"ok": True, "adjustment": adjustment}


def test_list_commitment_periods_uses_v2_query_and_preserves_rows(client, monkeypatch):
    period = {
        "generation": 2,
        "period_start": "2026-07-06",
        "period_end": "2026-07-13",
        "accrued": 310,
        "session_count": 5,
        "carryover_in": 10,
        "balance_out": 20,
        "closed_at": "2026-07-13T00:00:00+02:00",
        "revision_id": 4,
    }
    request = MagicMock(return_value={"count": 1, "total": 1, "periods": [period]})
    monkeypatch.setattr(client, "_request", request)

    result = client.list_commitment_periods(7, generation=2, limit=20, offset=0)

    request.assert_called_once_with(
        "GET",
        "/api/v2/commitments/7/periods/",
        params={"generation": 2, "limit": 20, "offset": 0},
    )
    assert result == {"ok": True, "count": 1, "total": 1, "periods": [period]}


def test_restart_required_envelope_names_the_cli_restart_command(client, monkeypatch):
    response = MagicMock()
    response.status_code = 400
    response.content = b'{"error": {}}'
    response.json.return_value = {
        "error": {
            "code": "restart_required",
            "message": "period requires restart",
            "details": None,
        }
    }
    response.raise_for_status.side_effect = requests.exceptions.HTTPError("400")
    monkeypatch.setattr(requests, "request", MagicMock(return_value=response))

    with pytest.raises(
        APIError,
        match=r"requires restarting the commitment.*autumn commitments restart",
    ):
        client._request(
            "PATCH", "/api/v2/commitments/7", json={"period": "monthly"}
        )


def test_commitment_version_conflict_uses_established_friendly_error(
    client, monkeypatch
):
    response = MagicMock()
    response.status_code = 409
    response.content = b'{"error": {}}'
    response.json.return_value = {
        "error": {
            "code": "version_conflict",
            "message": "Version mismatch",
            "details": {"current": _resource(version=5)},
        }
    }
    response.raise_for_status.side_effect = requests.exceptions.HTTPError("409")
    monkeypatch.setattr(requests, "request", MagicMock(return_value=response))

    with pytest.raises(
        APIError,
        match=r"The commitment changed on the server.*Re-run the command",
    ):
        client._request(
            "PATCH", "/api/v2/commitments/7", json={"target_value": 360}
        )


def test_only_allowed_non_v2_api_urls_remain():
    package = Path(__file__).parents[1] / "autumn_cli"
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in package.rglob("*.py")
    )
    routes = set(re.findall(r'["\'](/api/[^"\']+)', source))
    non_v2 = {route for route in routes if not route.startswith("/api/v2/")}

    assert non_v2 == {"/api/export/", "/api/import/", "/api/audit/"}
