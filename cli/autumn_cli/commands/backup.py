"""Download an account ZIP for disaster recovery."""

import json
import os
import re
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4
from zipfile import BadZipFile, ZipFile

import click

from ..api_client import APIClient, APIError
from ..utils.console import err_console


def _verified_account(path: Path) -> str:
    with ZipFile(path) as archive:
        manifest_info = archive.getinfo("manifest.json")
        if manifest_info.file_size > 32 * 1024 * 1024:
            raise ValueError("The backup manifest is too large.")
        manifest = json.loads(archive.read(manifest_info))
        if not isinstance(manifest, dict) or manifest.get("format") != "autumn-account-backup":
            raise ValueError("The ZIP is missing an Autumn account manifest.")
        if archive.testzip() is not None:
            raise ValueError("A file in the backup failed its integrity check.")
    source = manifest.get("source")
    if not isinstance(source, dict) or not isinstance(source.get("username"), str):
        raise ValueError("The backup manifest has no account name.")
    return source["username"]


@click.command()
@click.option(
    "--dir", "directory", type=click.Path(path_type=Path, file_okay=False),
    help="Write the ZIP here. Defaults to Downloads, or your home directory.",
)
@click.option("--insights/--no-insights", default=True, help="Include Insights chats.", show_default=True)
@click.option("--attachments", is_flag=True, help="Include the files attached to Insights chats.")
def backup(directory: Path | None, insights: bool, attachments: bool) -> None:
    """Save a portable account backup ZIP, suitable for a scheduled job."""
    if attachments and not insights:
        raise click.UsageError("--attachments requires Insights chats.")
    if directory is None:
        downloads = Path.home() / "Downloads"
        directory = downloads if downloads.is_dir() else Path.home()
    directory = directory.expanduser().absolute()
    partial = None
    try:
        client = APIClient(quiet=True)
        directory.mkdir(parents=True, exist_ok=True)
        progress = (
            err_console.status("[autumn.user]🍂 Downloading Autumn backup[/]", spinner="moon", spinner_style="autumn.user")
            if err_console.is_terminal else nullcontext()
        )
        with progress as status:
            with NamedTemporaryFile(dir=directory, prefix=".autumn-backup-", suffix=".part", delete=False) as output:
                partial = Path(output.name)
                client.download_account_backup(output, insights=insights, attachments=attachments)
                output.flush()
                os.fsync(output.fileno())
            if status:
                status.update("[autumn.user]🍂 Checking the backup ZIP[/]")
            account = _verified_account(partial)
            label = re.sub(r"[^\w.-]+", "_", account)[:40].strip("._") or "account"
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%SZ")
            path = directory / f"autumn-backup-{label}-{stamp}-{uuid4().hex[:8]}.zip"
            partial.replace(path)
        click.echo(path)
    except (APIError, OSError, BadZipFile, ValueError, KeyError, RuntimeError) as error:
        raise click.ClickException(f"Could not save an account backup. {error}") from error
    finally:
        if partial is not None:
            partial.unlink(missing_ok=True)
