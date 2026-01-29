"""Export command for Autumn CLI."""

import click
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..api_client import APIClient, APIError
from ..config import get_config_value
from ..utils.console import console
from ..utils.resolvers import resolve_context_param, resolve_tag_params, resolve_project_param


def _format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.2f} MB"


def _count_items(data: dict) -> tuple[int, int]:
    """Count sessions and projects in export data, handling various response formats."""
    sessions_count = 0
    projects_count = 0

    # Format 1: Top-level keys are project names (Autumn export format)
    # Each project has 'Session History' or 'Sessions' containing session list
    if data and isinstance(data, dict):
        first_key = next(iter(data.keys()), None)
        first_val = data.get(first_key) if first_key else None

        if isinstance(first_val, dict) and any(k in first_val for k in ("Session History", "Sessions", "Start Date")):
            # This is the Autumn export format: {project_name: {Session History: [...]}}
            projects_count = len(data)
            for proj_data in data.values():
                if isinstance(proj_data, dict):
                    for session_key in ("Session History", "Sessions"):
                        if session_key in proj_data:
                            sessions = proj_data[session_key]
                            if isinstance(sessions, list):
                                sessions_count += len(sessions)
                            elif isinstance(sessions, dict):
                                sessions_count += len(sessions)
                            break
            return sessions_count, projects_count

    # Format 2: Standard API format with sessions/projects arrays
    for key in ("sessions", "session_data", "data"):
        if key in data and isinstance(data[key], list):
            sessions_count = len(data[key])
            break

    for key in ("projects", "project_data"):
        if key in data and isinstance(data[key], list):
            projects_count = len(data[key])
            break

    return sessions_count, projects_count


def _get_default_export_dir() -> Path:
    """Get the default export directory.

    Priority:
    1. Config value `export.default_dir` if set
    2. User's Downloads folder
    """
    configured = get_config_value("export.default_dir")
    if configured:
        path = Path(configured).expanduser()
        if path.is_dir():
            return path

    # Default to Downloads folder (cross-platform)
    downloads = Path.home() / "Downloads"
    if downloads.is_dir():
        return downloads

    # Fallback to home directory if Downloads doesn't exist
    return Path.home()


def _generate_export_filename(project: Optional[str] = None) -> str:
    """Generate a timestamped export filename."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if project:
        # Sanitize project name for filename
        safe_project = "".join(c if c.isalnum() or c in "._-" else "_" for c in project)
        return f"autumn_export_{safe_project}_{timestamp}.json"
    return f"autumn_export_{timestamp}.json"


@click.command()
@click.option("--project", "-p", help="Filter by project name")
@click.option("--start-date", help="Start date (YYYY-MM-DD)")
@click.option("--end-date", help="End date (YYYY-MM-DD)")
@click.option("--context", "-c", help="Filter by context (ID only for export)")
@click.option("--tag", "-t", multiple=True, help="Filter by tag ID (repeatable)")
@click.option("--output", "-o", help="Output file path (overrides default directory)")
@click.option("--dir", "-d", "export_dir", help="Output directory (default: ~/Downloads or config)")
@click.option("--stdout", is_flag=True, help="Output to stdout instead of file")
@click.option("--compress", is_flag=True, help="Compress output")
@click.option("--pick", is_flag=True, help="Interactively pick project")
def export(
    project: Optional[str],
    start_date: Optional[str],
    end_date: Optional[str],
    context: Optional[str],
    tag: tuple,
    output: Optional[str],
    export_dir: Optional[str],
    stdout: bool,
    compress: bool,
    pick: bool,
):
    """Export sessions and projects data as JSON.

    By default, exports to ~/Downloads with a timestamped filename.
    Use --stdout to print to terminal instead.

    Examples:
        autumn export                           # Export to Downloads folder
        autumn export -p "My Project"           # Export filtered by project
        autumn export -o backup.json            # Export to specific file
        autumn export -d ~/backups              # Export to custom directory
        autumn export --stdout                  # Print to terminal
        autumn export --stdout | jq .sessions   # Pipe to jq

    Configure default directory: autumn config set export.default_dir "~/backups"

    Note: Context and tags must be specified by ID (not name) for export filtering.
    """
    try:
        client = APIClient()

        resolved_project = None
        if pick:
            from ..utils.pickers import pick_project
            picked = pick_project(client, label="project to export")
            if picked:
                resolved_project = picked

        if project and not resolved_project:
            # Resolve project name
            projects_meta = client.get_discovery_projects()
            proj_res = resolve_project_param(project=project, projects=projects_meta.get("projects", []))
            if proj_res.warning:
                console.print(f"[autumn.warn]Warning:[/] {proj_res.warning}")
            resolved_project = proj_res.value or project

        # Parse context as integer if provided
        context_id = None
        if context:
            try:
                context_id = int(context)
            except ValueError:
                console.print(f"[autumn.warn]Warning:[/] Context must be an integer ID for export. Got '{context}'")

        # Parse tags as integers if provided
        tag_ids = None
        if tag:
            tag_ids = []
            for t in tag:
                try:
                    tag_ids.append(int(t))
                except ValueError:
                    console.print(f"[autumn.warn]Warning:[/] Tag must be an integer ID for export. Skipping '{t}'")

        result = client.export_data(
            project=resolved_project,
            start_date=start_date,
            end_date=end_date,
            context=context_id,
            tags=tag_ids,
            compress=compress,
            autumn_compatible=False,  # Use standard format for full data
        )

        # Format output
        json_output = json.dumps(result, indent=2, ensure_ascii=False)
        json_bytes = json_output.encode("utf-8")

        if stdout:
            # Output to stdout with proper UTF-8 encoding (fixes Windows encoding issues)
            sys.stdout.buffer.write(json_bytes)
            sys.stdout.buffer.write(b"\n")
            sys.stdout.buffer.flush()
        else:
            # Determine output path
            if output:
                output_path = Path(output).expanduser()
            else:
                # Use specified directory or default
                if export_dir:
                    directory = Path(export_dir).expanduser()
                else:
                    directory = _get_default_export_dir()

                # Ensure directory exists
                directory.mkdir(parents=True, exist_ok=True)

                # Generate filename
                filename = _generate_export_filename(resolved_project)
                output_path = directory / filename

            # Write file
            with open(output_path, "wb") as f:
                f.write(json_bytes)

            # Get file size
            file_size = output_path.stat().st_size

            console.print(f"[autumn.ok]Exported to:[/] {output_path}")
            console.print(f"[autumn.label]Size:[/] {_format_file_size(file_size)}")

            # Show summary
            if isinstance(result, dict):
                sessions_count, projects_count = _count_items(result)
                console.print(f"[autumn.label]Sessions:[/] {sessions_count}")
                console.print(f"[autumn.label]Projects:[/] {projects_count}")

    except APIError as e:
        console.print(f"[autumn.err]Error:[/] {e}")
        raise click.Abort()
    except IOError as e:
        console.print(f"[autumn.err]Error writing file:[/] {e}")
        raise click.Abort()
