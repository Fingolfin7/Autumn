"""Metadata discovery commands (contexts / tags)."""

from __future__ import annotations

import click

from ..api_client import APIClient, APIError
from ..utils.console import console
from ..utils.formatters import contexts_table, tags_table
from ..utils.meta_cache import clear_cached_snapshot
from ..utils.projects_cache import clear_cached_projects
from ..utils.recent_activity_cache import clear_cached_activity


@click.group()
def context() -> None:
    """Context-related commands."""


@context.command("list")
@click.option("--json", "json_out", is_flag=True, help="Output raw JSON")
@click.option("--full", is_flag=True, help="Include extra fields")
def context_list(json_out: bool, full: bool) -> None:
    """List available contexts."""
    try:
        client = APIClient()
        result = client.list_contexts(compact=not full)
        if json_out:
            console.print_json(data=result)
            return

        contexts = result.get("contexts", [])
        if not contexts:
            console.print("[dim]No contexts found.[/]")
            return

        console.print(contexts_table(contexts, show_description=full))
    except APIError as e:
        console.print(f"[autumn.err]Error:[/] {e}")
        raise click.Abort()


@click.group()
def tag() -> None:
    """Tag-related commands."""


@tag.command("list")
@click.option("--json", "json_out", is_flag=True, help="Output raw JSON")
@click.option("--full", is_flag=True, help="Include extra fields")
def tag_list(json_out: bool, full: bool) -> None:
    """List available tags."""
    try:
        client = APIClient()
        result = client.list_tags(compact=not full)
        if json_out:
            console.print_json(data=result)
            return

        tags = result.get("tags", [])
        if not tags:
            console.print("[dim]No tags found.[/]")
            return

        console.print(tags_table(tags, show_color=full))
    except APIError as e:
        console.print(f"[autumn.err]Error:[/] {e}")
        raise click.Abort()


@click.group()
def meta() -> None:
    """Metadata cache commands."""


@meta.command("refresh")
def meta_refresh() -> None:
    """Refresh cached contexts/tags/projects (forces a re-fetch on next command)."""
    clear_cached_snapshot()
    clear_cached_projects()
    clear_cached_activity()
    console.print("[autumn.ok]Metadata cache cleared.[/] Next command will re-fetch contexts/tags, projects, and recent activity.")


@meta.command("audit")
def meta_audit() -> None:
    """Recompute and persist totals for all projects and subprojects.

    This fixes any discrepancies between computed totals and actual session data.
    Useful after imports, manual database changes, or if totals seem incorrect.
    """
    try:
        client = APIClient()
        console.print("[dim]Auditing project/subproject totals...[/]")

        result = client.audit_totals()

        if result.get("ok"):
            projects = result.get("projects", {})
            subprojects = result.get("subprojects", {})

            console.print()
            console.print("[autumn.ok]Audit complete.[/]")
            console.print()

            # Projects summary
            proj_count = projects.get("count", 0)
            proj_changed = projects.get("changed", 0)
            proj_delta = projects.get("delta_total", 0)

            delta_sign = "+" if proj_delta >= 0 else ""
            console.print(f"[autumn.label]Projects:[/] {proj_count} checked, {proj_changed} changed (delta: {delta_sign}{proj_delta:.1f} min)")

            # Subprojects summary
            sub_count = subprojects.get("count", 0)
            sub_changed = subprojects.get("changed", 0)
            sub_delta = subprojects.get("delta_total", 0)

            delta_sign = "+" if sub_delta >= 0 else ""
            console.print(f"[autumn.label]Subprojects:[/] {sub_count} checked, {sub_changed} changed (delta: {delta_sign}{sub_delta:.1f} min)")

            # Clear caches since totals may have changed
            clear_cached_projects()
            clear_cached_activity()
        else:
            console.print(f"[autumn.err]Error:[/] {result.get('error', 'Unknown error')}")
            raise click.Abort()
    except APIError as e:
        console.print(f"[autumn.err]Error:[/] {e}")
        raise click.Abort()
