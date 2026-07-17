"""v2 context/tag management facade tests."""

from unittest.mock import MagicMock, call

import pytest
import requests
from click.testing import CliRunner

from autumn_cli.api_client import APIClient, APIError
from autumn_cli.commands.meta import context, tag


@pytest.fixture
def client():
    return APIClient(
        api_key="key", base_url="https://autumn.example", wake_retry=False
    )


@pytest.mark.parametrize(
    ("method_name", "key", "endpoint"),
    [
        ("list_contexts", "contexts", "/api/v2/contexts/"),
        ("list_tags", "tags", "/api/v2/tags/"),
    ],
)
def test_metadata_lists_use_v2_and_preserve_compact_legacy_shapes(
    client, monkeypatch, method_name, key, endpoint
):
    request = MagicMock(
        return_value={
            "count": 1,
            key: [{"id": 3, "name": "Focus", "project_count": 4}],
        }
    )
    monkeypatch.setattr(client, "_request", request)

    compact = getattr(client, method_name)(compact=True)
    full = getattr(client, method_name)(compact=False)

    assert compact == {"count": 1, key: [{"id": 3, "name": "Focus"}]}
    assert full == {
        "count": 1,
        key: [{"id": 3, "name": "Focus", "project_count": 4}],
    }
    assert request.call_args_list == [call("GET", endpoint), call("GET", endpoint)]


@pytest.mark.parametrize(
    ("method_name", "wrapper", "endpoint"),
    [
        ("create_context", "context", "/api/v2/contexts/"),
        ("create_tag", "tag", "/api/v2/tags/"),
    ],
)
def test_metadata_creates_use_v2_name_payload_and_legacy_wrapper(
    client, monkeypatch, method_name, wrapper, endpoint
):
    resource = {"id": 3, "name": "Focus", "project_count": 0}
    request = MagicMock(return_value=resource)
    monkeypatch.setattr(client, "_request", request)

    result = getattr(client, method_name)("Focus")

    request.assert_called_once_with("POST", endpoint, json={"name": "Focus"})
    assert result == {"ok": True, wrapper: resource}


@pytest.mark.parametrize(
    ("method_name", "wrapper", "endpoint"),
    [
        ("update_context", "context", "/api/v2/contexts/3"),
        ("update_tag", "tag", "/api/v2/tags/3"),
    ],
)
def test_metadata_renames_use_v2_name_payload_and_legacy_wrapper(
    client, monkeypatch, method_name, wrapper, endpoint
):
    resource = {"id": 3, "name": "Focused", "project_count": 4}
    request = MagicMock(return_value=resource)
    monkeypatch.setattr(client, "_request", request)

    result = getattr(client, method_name)(3, name="Focused")

    request.assert_called_once_with("PATCH", endpoint, json={"name": "Focused"})
    assert result == {"ok": True, wrapper: resource}


@pytest.mark.parametrize(
    ("method_name", "endpoint"),
    [
        ("delete_context", "/api/v2/contexts/3"),
        ("delete_tag", "/api/v2/tags/3"),
    ],
)
def test_metadata_deletes_use_retry_safe_v2_delete_and_legacy_shape(
    client, monkeypatch, method_name, endpoint
):
    request = MagicMock(return_value={})
    monkeypatch.setattr(client, "_request", request)

    result = getattr(client, method_name)(3)

    request.assert_called_once_with("DELETE", endpoint, retry_safe=True)
    assert result == {"ok": True}


def _error_response(status, code, message):
    response = MagicMock()
    response.status_code = status
    response.content = b'{"error": {}}'
    response.json.return_value = {
        "error": {"code": code, "message": message, "details": None}
    }
    response.raise_for_status.side_effect = requests.exceptions.HTTPError(str(status))
    return response


@pytest.mark.parametrize("method_name", ["create_context", "create_tag"])
def test_duplicate_name_conflict_uses_friendly_server_message(
    client, monkeypatch, method_name
):
    monkeypatch.setattr(
        requests,
        "request",
        MagicMock(
            return_value=_error_response(
                409, "conflict", "A context or tag with this name already exists."
            )
        ),
    )

    with pytest.raises(
        APIError, match=r"^A context or tag with this name already exists\.$"
    ):
        getattr(client, method_name)("Focus")


@pytest.mark.parametrize("method_name", ["delete_context", "delete_tag"])
def test_commitment_target_delete_conflict_uses_friendly_server_message(
    client, monkeypatch, method_name
):
    monkeypatch.setattr(
        requests,
        "request",
        MagicMock(
            return_value=_error_response(
                409, "conflict", "This item is targeted by a commitment."
            )
        ),
    )

    with pytest.raises(
        APIError, match=r"^This item is targeted by a commitment\.$"
    ):
        getattr(client, method_name)(3)


def test_discovery_meta_refresh_sources_compact_cache_from_v2(client, monkeypatch):
    request = MagicMock(
        side_effect=[
            {
                "count": 1,
                "contexts": [{"id": 3, "name": "Work", "project_count": 4}],
            },
            {
                "count": 1,
                "tags": [{"id": 5, "name": "Focus", "project_count": 2}],
            },
        ]
    )
    save = MagicMock()
    monkeypatch.setattr(client, "_request", request)
    monkeypatch.setattr("autumn_cli.utils.meta_cache.save_cached_snapshot", save)

    result = client.get_discovery_meta(refresh=True)

    assert request.call_args_list == [
        call("GET", "/api/v2/contexts/"),
        call("GET", "/api/v2/tags/"),
    ]
    assert result == {
        "contexts": [{"id": 3, "name": "Work"}],
        "tags": [{"id": 5, "name": "Focus"}],
        "cached": False,
    }
    save.assert_called_once_with(result["contexts"], result["tags"])


class _MissingMetadataClient:
    def __init__(self, *args, **kwargs):
        pass

    def list_contexts(self, compact=False):
        return {"count": 1, "contexts": [{"id": 3, "name": "Work"}]}

    def list_tags(self, compact=False):
        return {"count": 1, "tags": [{"id": 5, "name": "Focus"}]}


@pytest.mark.parametrize(
    ("command", "args", "message"),
    [
        (context, ["rename", "Missing", "New"], "Unknown context 'Missing'"),
        (tag, ["delete", "Missing", "--yes"], "Unknown tag 'Missing'"),
    ],
)
def test_name_based_mutations_keep_friendly_unknown_name_error(
    monkeypatch, command, args, message
):
    monkeypatch.setattr("autumn_cli.commands.meta.APIClient", _MissingMetadataClient)

    result = CliRunner().invoke(command, args)

    assert result.exit_code == 2
    assert message in result.output


@pytest.mark.parametrize(
    ("callable_name", "args", "kwargs", "endpoint", "payload"),
    [
        ("create_context", ("Work", "Office"), {}, "/api/v2/contexts/",
         {"name": "Work", "description": "Office"}),
        ("update_context", (3,), {"description": "Office"},
         "/api/v2/contexts/3", {"description": "Office"}),
        ("create_tag", ("Focus", "blue"), {}, "/api/v2/tags/",
         {"name": "Focus", "color": "blue"}),
        ("update_tag", (3,), {"color": "blue"}, "/api/v2/tags/3",
         {"color": "blue"}),
    ],
)
def test_context_descriptions_and_tag_colors_pass_through_to_v2(
    client, monkeypatch, callable_name, args, kwargs, endpoint, payload
):
    captured = {}

    def fake_request(method, url, params=None, json=None, **kw):
        captured["url"] = url
        captured["json"] = json
        return {"id": 3, "name": json.get("name", "x"), "project_count": 0}

    monkeypatch.setattr(client, "_request", fake_request)

    getattr(client, callable_name)(*args, **kwargs)

    assert captured["url"] == endpoint
    assert captured["json"] == payload
