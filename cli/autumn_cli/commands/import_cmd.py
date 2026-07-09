"""Import command for Autumn CLI."""

import json
from pathlib import Path
from typing import Any, Dict, Optional

import click

from ..api_client import APIClient, APIError
from ..utils.console import console


def _read_import_file(path: Path) -> tuple[Optional[Dict[str, Any]], str]:
    """Read an export file, returning parsed data or the compressed payload."""
    content = path.read_text(encoding="utf-8")
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        return None, content
    return (parsed, content) if isinstance(parsed, dict) else (None, content)


@click.command(name="import")
@click.argument("file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--force", is_flag=True, help="Delete existing same-named projects first")
@click.option("--merge", is_flag=True, help="Merge into existing projects")
@click.option("--tolerance", type=int, default=2, show_default=True, help="Duplicate-session tolerance in minutes")
@click.option("--autumn-format", "autumn_format", is_flag=True, help="file uses the legacy Autumn CLI export format")
@click.option("--context", type=str, help="Import into this context, created if missing")
@click.option("--yes", "yes", "-y", is_flag=True, help="Skip confirmation prompt")
def import_cmd(
    file: Path,
    force: bool,
    merge: bool,
    tolerance: int,
    autumn_format: bool,
    context: Optional[str],
    yes: bool,
):
    """Import projects and sessions from an export FILE."""
    if force and merge:
        raise click.UsageError("--force and --merge cannot be used together.")

    try:
        parsed_data, compressed_data = _read_import_file(file)
    except (OSError, UnicodeDecodeError) as error:
        raise click.ClickException(f"Could not read import file: {error}")

    if parsed_data is not None:
        console.print(f"Importing {len(parsed_data)} projects from {file}...")
    else:
        console.print(f"Importing compressed export from {file}...")

    if not yes and not click.confirm("Continue with import?", default=False):
        console.print("[dim]Cancelled.[/]")
        return

    try:
        client = APIClient()
        result = client.import_data(
            data=parsed_data,
            data_compressed=None if parsed_data is not None else compressed_data,
            force=force,
            merge=merge,
            tolerance=tolerance,
            autumn_import=autumn_format,
            context=context,
        )
    except APIError as error:
        console.print(f"[autumn.err]Error:[/] {error}")
        raise click.Abort()

    summary = result.get("summary", {})
    console.print("[autumn.ok]Import complete.[/]")
    console.print(f"[autumn.label]Projects created:[/] {summary.get('projects_created', 0)}")
    console.print(f"[autumn.label]Projects updated:[/] {summary.get('projects_updated', 0)}")
    console.print(f"[autumn.label]Sessions imported:[/] {summary.get('sessions_imported', 0)}")

    skipped = summary.get("skipped", [])
    if skipped:
        console.print("[autumn.warn]Skipped projects:[/]")
        for project in skipped:
            console.print(f"[autumn.warn]- {project}[/]")
        console.print("[autumn.warn]Hint: use --merge or --force to include skipped projects.[/]")
