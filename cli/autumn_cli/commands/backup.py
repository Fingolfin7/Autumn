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
from ..config import get_active_account_name, get_active_account
from ..utils.backup_schedule import BackupSchedule, WEEKDAYS, install_schedule, remove_schedule, show_schedule
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


def backup_options(command):
    command = click.option(
        "--attachments", is_flag=True, help="Include chat files. Requires --insights.",
    )(command)
    command = click.option(
        "--insights/--no-insights", default=False, help="Include Insights chats.", show_default=True,
    )(command)
    return click.option(
        "--dir", "directory", type=click.Path(path_type=Path, file_okay=False),
        help="Write the ZIP here. Defaults to Downloads, or your home directory.",
    )(command)


def output_directory(directory: Path | None, insights: bool, attachments: bool) -> Path:
    if attachments and not insights:
        raise click.UsageError("--attachments requires --insights.")
    if directory is None:
        downloads = Path.home() / "Downloads"
        directory = downloads if downloads.is_dir() else Path.home()
    return directory.expanduser().absolute()


@click.group(invoke_without_command=True)
@backup_options
@click.pass_context
def backup(ctx: click.Context, directory: Path | None, insights: bool, attachments: bool) -> None:
    """Save a portable account backup ZIP or manage its schedule."""
    if ctx.invoked_subcommand is not None:
        if directory is not None or insights or attachments:
            raise click.UsageError("Put the backup options after 'schedule set'.")
        return
    directory = output_directory(directory, insights, attachments)
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


@backup.group()
def schedule() -> None:
    """Manage this account's scheduled backups on this computer."""


def _scheduled_account() -> str:
    account = get_active_account_name()
    if account is None:
        raise click.ClickException("Save an Autumn account with 'autumn auth login' before scheduling backups.")
    return account


@schedule.command("set")
@click.option("--at", type=click.DateTime(formats=["%H:%M"]), required=True, help="Local time in 24-hour HH:MM format.")
@click.option("--on", "weekday", type=click.Choice(WEEKDAYS, case_sensitive=False), help="Back up weekly on this day. Defaults to daily.")
@backup_options
def set_backup_schedule(at: datetime, weekday: str | None, directory: Path | None, insights: bool, attachments: bool) -> None:
    """Install or replace a daily or weekly schedule."""
    account = _scheduled_account()
    if not (get_active_account() or {}).get("api_key"):
        raise click.ClickException("This saved account needs an API key. Sign in with 'autumn auth login'.")
    target = output_directory(directory, insights, attachments)
    try:
        install_schedule(BackupSchedule(account, target, at.time(), weekday, insights, attachments))
    except OSError as error:
        raise click.ClickException(f"Could not save the backup schedule. {error}") from error
    cadence = f"every {weekday.capitalize()}" if weekday else "daily"
    click.echo(f"Scheduled {account} backups {cadence} at {at:%H:%M} local time.")
    click.echo(f"Destination: {target}")
    click.echo("Scheduled backups run while you're signed in to this computer.")


@schedule.command("show")
def show_backup_schedule() -> None:
    """Show the schedule and its status from the operating system."""
    click.echo(show_schedule(_scheduled_account()))


@schedule.command("remove")
def remove_backup_schedule() -> None:
    """Remove the schedule and keep the ZIP files already saved."""
    account = _scheduled_account()
    try:
        remove_schedule(account)
    except OSError as error:
        raise click.ClickException(f"Could not remove the backup schedule. {error}") from error
    click.echo(f"Removed the backup schedule for {account}.")
