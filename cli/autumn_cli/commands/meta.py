"""Metadata discovery commands (contexts / tags)."""

from __future__ import annotations

import click

from ..api_client import APIClient, APIError
from ..utils.console import console
from ..utils.formatters import contexts_table, tags_table
from ..utils.meta_cache import clear_cached_snapshot
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
    """Refresh cached contexts/tags (forces a re-fetch on next command)."""
    clear_cached_snapshot()
    clear_cached_activity()
    console.print("[autumn.ok]Metadata cache cleared.[/] Next command will re-fetch contexts/tags and recent activity.")
