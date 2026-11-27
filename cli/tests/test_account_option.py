import json
from io import BytesIO
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
import sys
from threading import Barrier, BrokenBarrierError, Thread
from unittest.mock import Mock
from zipfile import ZipFile

import pytest
import requests
import yaml
from click.testing import CliRunner

from autumn_cli import config
from autumn_cli.api_client import APIClient
from autumn_cli.cli import cli
from autumn_cli.utils import meta_cache, projects_cache, reminders_registry


def backup_zip():
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("manifest.json", json.dumps({
            "format": "autumn-account-backup",
            "version": 1,
            "source": {"username": "bob"},
        }))
    return buffer.getvalue()


def test_scoped_backup_streams_zip_and_prints_only_file_path(accounts, monkeypatch):
    data = backup_zip()
    response = Mock(status_code=200, headers={"Content-Type": "application/zip"})
    response.iter_content.return_value = [data[:5], data[5:]]
    request = Mock(return_value=response)
    monkeypatch.setattr(APIClient, "_http", request)
    before = accounts.read_bytes()
    destination = accounts.parent / "out"
    result = CliRunner().invoke(cli, ["--account", "bob", "backup", "--attachments", "--dir", str(destination)])

    assert result.exit_code == 0, result.output
    path = Path(result.stdout.strip())
    assert path.name.startswith("autumn-backup-bob-")
    assert list(destination.iterdir()) == [path]
    assert path.read_bytes() == data
    assert request.call_args.args == ("GET", "https://saved.example/api/v2/backup/")
    assert request.call_args.kwargs["headers"]["Authorization"] == "Token token-b"
    assert request.call_args.kwargs["params"] == {"include_insights": "true", "include_attachments": "true"}
    assert request.call_args.kwargs["stream"] is True
    response.close.assert_called_once_with()
    assert accounts.read_bytes() == before


def test_interrupted_backup_leaves_no_zip(accounts, monkeypatch):
    def chunks(*args, **kwargs):
        yield b"partial content"
        raise requests.exceptions.ChunkedEncodingError("connection dropped")

    response = Mock(status_code=200, headers={"Content-Type": "application/zip"})
    response.iter_content.side_effect = chunks
    monkeypatch.setattr(APIClient, "_http", Mock(return_value=response))
    destination = accounts.parent / "out"
    result = CliRunner().invoke(cli, ["backup", "--dir", str(destination)])

    assert result.exit_code == 1
    assert not list(destination.iterdir())
    assert "Could not save an account backup" in result.output
    response.close.assert_called_once_with()


@pytest.fixture
def accounts(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.yaml")
    monkeypatch.setattr(meta_cache, "_mem_snapshot", None)
    monkeypatch.setattr(projects_cache, "_mem_snapshot", None)
    monkeypatch.setenv("AUTUMN_API_KEY", "env-token")
    monkeypatch.setenv("AUTUMN_API_BASE", "https://env.example")

    def unexpected_reminder_check():
        pytest.fail("Scoped reads must not check the shared reminder registry")

    monkeypatch.setattr(
        reminders_registry, "check_reminders_health", unexpected_reminder_check
    )
    fetched_at = datetime.now(timezone.utc).isoformat()
    config.save_config({
        "base_url": "https://saved.example",
        "active_account": "alice",
        "accounts": {
            "alice": {"api_key": "token-a", "username": "alice"},
            "bob": {"api_key": "token-b", "username": "bob"},
        },
        "account_aliases": {
            "alice": {
                "projects": {"focus": "Alice Build"},
                "contexts": {"studio": "Alice Studio"},
            },
            "bob": {
                "projects": {"focus": "Bob Build"},
                "contexts": {"studio": "Bob Studio"},
            },
        },
        "account_caches": {
            "alice": {
                "meta_cache": {
                    "schema_version": meta_cache.CACHE_SCHEMA_VERSION,
                    "fetched_at": fetched_at,
                    "contexts": [{"id": 7, "name": "Alice Studio"}],
                },
                "projects_cache": {
                    "schema_version": projects_cache.CACHE_SCHEMA_VERSION,
                    "fetched_at": fetched_at,
                    "projects": [{"id": 8, "name": "Alice Build"}],
                },
            },
        },
    })
    return config.CONFIG_FILE


@pytest.mark.parametrize("command", [["log"], ["ls"], ["log", "search"]])
def test_scoped_logs_use_the_named_account_metadata_and_aliases(
    accounts, monkeypatch, command
):
    # Prime the usual account's in-process caches before changing scope.
    assert meta_cache.load_cached_snapshot().contexts[0]["name"] == "Alice Studio"
    assert projects_cache.load_cached_projects().projects[0]["name"] == "Alice Build"
    before = accounts.read_bytes()
    session_queries = []

    def request(client, method, path, params=None):
        assert method == "GET"
        assert client.base_url == "https://saved.example"
        assert client._headers()["Authorization"] == "Token token-b"
        if path == "/api/v2/contexts/":
            return {"contexts": [{"id": 3, "name": "Bob Studio"}]}
        if path == "/api/v2/tags/":
            return {"tags": []}
        if path == "/api/v2/projects/":
            return {"projects": [{"id": 4, "name": "Bob Build", "status": "active"}]}
        assert path == "/api/v2/sessions/"
        session_queries.append(params)
        return {"sessions": []}

    monkeypatch.setattr(APIClient, "_request", request)
    result = CliRunner().invoke(
        cli, ["--account", "bob", *command, "-p", "focus", "-c", "studio"]
    )

    assert result.exit_code == 0, (result.output, result.exception)
    assert len(session_queries) == 1
    assert session_queries[0]["project_ids"] == "4"
    assert session_queries[0]["context_ids"] == "3"
    assert accounts.read_bytes() == before
    assert config.get_active_account_name() == "alice"
    assert config.get_api_key() == "env-token"
    assert config.get_base_url() == "https://env.example"
    assert meta_cache.load_cached_snapshot().contexts[0]["name"] == "Alice Studio"
    assert projects_cache.load_cached_projects().projects[0]["name"] == "Alice Build"


def test_scoped_status_does_not_persist_legacy_migration(accounts, monkeypatch):
    fixture_config = {**config.load_config(), "aliases": {"projects": {"old": "Name"}}}
    accounts.write_text(yaml.safe_dump(fixture_config), encoding="utf-8")
    before = accounts.read_bytes()

    def request(client, method, path):
        assert (client.api_key, method, path) == ("token-b", "GET", "/api/v2/timers/")
        return {"timers": []}

    monkeypatch.setattr(APIClient, "_request", request)
    result = CliRunner().invoke(cli, ["--account", "bob", "status"])

    assert result.exit_code == 0, (result.output, result.exception)
    assert "No active timers" in result.output
    assert accounts.read_bytes() == before


@pytest.mark.parametrize(
    ("account", "command", "message"),
    [
        ("missing", "log", "Unknown account 'missing'"),
        ("bob", "start", "--account applies to log, status, export, and backup"),
    ],
)
def test_scope_errors_leave_config_and_context_unchanged(accounts, account, command, message):
    before = accounts.read_bytes()
    result = CliRunner().invoke(cli, ["--account", account, command])

    assert result.exit_code != 0
    assert message in result.output
    assert accounts.read_bytes() == before
    assert config.get_active_account_name() == "alice"


def test_scoped_exports_name_files_for_the_selected_account(accounts, monkeypatch):
    def request(client, method, path, params=None):
        return {"token": client.api_key}

    monkeypatch.setattr(APIClient, "_request", request)
    runner = CliRunner()
    for account in ("alice", "bob"):
        result = runner.invoke(cli, ["--account", account, "export", "--dir", str(accounts.parent)])
        assert result.exit_code == 0, (result.output, result.exception)

    for account, token in (("alice", "token-a"), ("bob", "token-b")):
        output, = accounts.parent.glob(f"autumn_export_{account}_*.json")
        assert json.loads(output.read_bytes()) == {"token": token}


def test_concurrent_exports_use_different_saved_tokens(accounts, monkeypatch):
    # Hold the first request until both processes have reached the same server.
    barrier = Barrier(2, timeout=15)

    class ExportHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            account = {"Token token-a": "alice", "Token token-b": "bob"}.get(
                self.headers.get("Authorization")
            )
            if self.path != "/api/v2/export/" or account is None:
                self.send_error(400)
                return
            try:
                barrier.wait()
            except BrokenBarrierError:
                self.send_error(500)
                return
            payload = json.dumps({"account": account}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

    cli_root = Path(__file__).resolve().parents[1]
    script = """
import sys
from pathlib import Path
from autumn_cli import config

config.CONFIG_FILE = Path(sys.argv.pop(1))
config.CONFIG_DIR = config.CONFIG_FILE.parent

from autumn_cli.cli import main
main()
"""

    def export(account):
        args = [
            sys.executable, "-c", script, str(accounts), "--account", account,
            "export", "--stdout",
        ]
        return subprocess.run(args, cwd=cli_root, capture_output=True, text=True, timeout=25)

    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    with ThreadingHTTPServer(("127.0.0.1", 0), ExportHandler) as server:
        fixture_config = {**config.load_config(), "base_url": f"http://127.0.0.1:{server.server_port}"}
        accounts.write_text(yaml.safe_dump(fixture_config), encoding="utf-8")
        before = accounts.read_bytes()
        worker = Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(export, ("alice", "bob")))
        finally:
            server.shutdown()
            worker.join()

    for account, result in zip(("alice", "bob"), results):
        assert result.returncode == 0, (result.stdout, result.stderr)
        assert json.loads(result.stdout) == {"account": account}
    assert accounts.read_bytes() == before
    assert config.get_active_account_name() == "alice"
