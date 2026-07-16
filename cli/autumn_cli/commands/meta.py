"""Metadata discovery commands (contexts / tags)."""

from __future__ import annotations

import click
from typing import Optional

from ..api_client import APIClient, APIError
from ..utils.console import console
from ..utils.formatters import contexts_table, tags_table
from ..utils.meta_cache import clear_cached_snapshot
from ..utils.projects_cache import clear_cached_projects
from ..utils.recent_activity_cache import clear_cached_activity


def _find_named_item(items: list, name: str, kind: str) -> dict:
    """Find a context/tag by name, providing a useful discovery error."""
    lookup = {
        str(item.get("name", "")).strip().casefold(): item
        for item in items
        if isinstance(item, dict) and item.get("name")
    }
    item = lookup.get(name.strip().casefold())
    if item is not None:
        return item
    available = ", ".join(item.get("name", "") for item in lookup.values()) or "none"
    raise click.UsageError(f"Unknown {kind} '{name}'. Available {kind}s: {available}.")


def _clear_metadata_caches() -> None:
    clear_cached_snapshot()
    clear_cached_projects()
    clear_cached_activity()


def _delta_text(delta: float) -> str:
    sign = "+" if delta >= 0 else ""
    return f"{sign}{delta:.1f} min"


def _print_changed_projects(changed_projects: list[dict]) -> None:
    if not changed_projects:
        return

    console.print()
    console.print("[autumn.label]Changed projects:[/]")
    for item in changed_projects:
        delta = item.get("delta", 0)
        console.print(
            f"  [autumn.project]{item.get('name', item.get('id', 'unknown'))}[/]: "
            f"{item.get('before', 0):.1f} -> {item.get('after', 0):.1f} "
            f"([autumn.duration]{_delta_text(delta)}[/])"
        )


def _print_changed_subprojects(changed_subprojects: list[dict]) -> None:
    if not changed_subprojects:
        return

    console.print()
    console.print("[autumn.label]Changed subprojects:[/]")
    for item in changed_subprojects:
        delta = item.get("delta", 0)
        project = item.get("project")
        project_part = f" in [autumn.project]{project}[/]" if project else ""
        console.print(
            f"  [autumn.subproject]{item.get('name', item.get('id', 'unknown'))}[/]"
            f"{project_part}: {item.get('before', 0):.1f} -> {item.get('after', 0):.1f} "
            f"([autumn.duration]{_delta_text(delta)}[/])"
        )


@click.group()
def context() -> None:
    """Context-related commands."""


@context.command("list")
@click.option("--json", "json_out", is_flag=True, help="Output raw JSON")
@click.option("--compact", is_flag=True, help="Show minimal output (names only)")
@click.option("--desc", "-d", is_flag=True, help="Show descriptions")
def context_list(json_out: bool, compact: bool, desc: bool) -> None:
    """List available contexts with stats."""
    try:
        client = APIClient()
        result = client.list_contexts(compact=compact)
        if json_out:
            console.print_json(data=result)
            return

        contexts = result.get("contexts", [])
        if not contexts:
            console.print("[dim]No contexts found.[/]")
            return

        console.print(contexts_table(contexts, show_description=desc))
    except APIError as e:
        console.print(f"[autumn.err]Error:[/] {e}")
        raise click.Abort()


@context.command("new")
@click.argument("name")
@click.option("--description", "description", help="Optional context description")
def context_new(name: str, description: Optional[str]) -> None:
    """Create a context."""
    try:
        result = APIClient().create_context(name, description)
        _clear_metadata_caches()
        item = result.get("context", {})
        console.print(f"[autumn.ok]Context created:[/] [autumn.project]{item.get('name', name)}[/]")
    except APIError as exc:
        console.print(f"[autumn.err]Error:[/] {exc}")
        raise click.Abort()


@context.command("rename")
@click.argument("old")
@click.argument("new")
def context_rename(old: str, new: str) -> None:
    """Rename a context (case-insensitive lookup)."""
    try:
        client = APIClient()
        item = _find_named_item(client.list_contexts(compact=False).get("contexts", []), old, "context")
        client.update_context(item["id"], name=new)
        _clear_metadata_caches()
        console.print(f"[autumn.ok]Context renamed:[/] [autumn.project]{item['name']}[/] → [autumn.project]{new}[/]")
    except APIError as exc:
        console.print(f"[autumn.err]Error:[/] {exc}")
        raise click.Abort()


@context.command("edit")
@click.argument("name")
@click.option("--description", "description", help="New description (pass an empty string to clear)")
def context_edit(name: str, description: Optional[str]) -> None:
    """Update a context's description."""
    if description is None:
        raise click.UsageError("Specify --description to update the context.")
    try:
        client = APIClient()
        item = _find_named_item(client.list_contexts(compact=False).get("contexts", []), name, "context")
        client.update_context(item["id"], description=description)
        _clear_metadata_caches()
        console.print(f"[autumn.ok]Context updated:[/] [autumn.project]{item['name']}[/]")
    except APIError as exc:
        console.print(f"[autumn.err]Error:[/] {exc}")
        raise click.Abort()


@context.command("delete")
@click.argument("name")
@click.option("--yes", "yes", is_flag=True, help="Skip confirmation prompt")
def context_delete(name: str, yes: bool) -> None:
    """Delete a context; its projects retain their other data."""
    try:
        client = APIClient()
        item = _find_named_item(client.list_contexts(compact=False).get("contexts", []), name, "context")
        if not yes and not click.confirm(
            f"Delete context '{item['name']}'? Projects will keep their data but lose this context.",
            default=False,
        ):
            console.print("[autumn.muted]Cancelled.[/]")
            return
        client.delete_context(item["id"])
        _clear_metadata_caches()
        console.print(f"[autumn.ok]Context deleted:[/] [autumn.project]{item['name']}[/]")
    except APIError as exc:
        console.print(f"[autumn.err]Error:[/] {exc}")
        raise click.Abort()


@click.group()
def tag() -> None:
    """Tag-related commands."""


@tag.command("list")
@click.option("--json", "json_out", is_flag=True, help="Output raw JSON")
@click.option("--compact", is_flag=True, help="Show minimal output (names only)")
@click.option("--color", is_flag=True, help="Show tag colors")
def tag_list(json_out: bool, compact: bool, color: bool) -> None:
    """List available tags with stats."""
    try:
        client = APIClient()
        result = client.list_tags(compact=compact)
        if json_out:
            console.print_json(data=result)
            return

        tags = result.get("tags", [])
        if not tags:
            console.print("[dim]No tags found.[/]")
            return

        console.print(tags_table(tags, show_color=color))
    except APIError as e:
        console.print(f"[autumn.err]Error:[/] {e}")
        raise click.Abort()


@tag.command("new")
@click.argument("name")
@click.option("--color", "color", help="Optional tag color (max 20 characters)")
def tag_new(name: str, color: Optional[str]) -> None:
    """Create a tag."""
    try:
        result = APIClient().create_tag(name, color)
        _clear_metadata_caches()
        item = result.get("tag", {})
        console.print(f"[autumn.ok]Tag created:[/] [autumn.note]{item.get('name', name)}[/]")
    except APIError as exc:
        console.print(f"[autumn.err]Error:[/] {exc}")
        raise click.Abort()


@tag.command("rename")
@click.argument("old")
@click.argument("new")
def tag_rename(old: str, new: str) -> None:
    """Rename a tag (case-insensitive lookup)."""
    try:
        client = APIClient()
        item = _find_named_item(client.list_tags(compact=False).get("tags", []), old, "tag")
        client.update_tag(item["id"], name=new)
        _clear_metadata_caches()
        console.print(f"[autumn.ok]Tag renamed:[/] [autumn.note]{item['name']}[/] → [autumn.note]{new}[/]")
    except APIError as exc:
        console.print(f"[autumn.err]Error:[/] {exc}")
        raise click.Abort()


@tag.command("edit")
@click.argument("name")
@click.option("--color", "color", help="New color (pass an empty string to clear)")
def tag_edit(name: str, color: Optional[str]) -> None:
    """Update a tag's color."""
    if color is None:
        raise click.UsageError("Specify --color to update the tag.")
    try:
        client = APIClient()
        item = _find_named_item(client.list_tags(compact=False).get("tags", []), name, "tag")
        client.update_tag(item["id"], color=color)
        _clear_metadata_caches()
        console.print(f"[autumn.ok]Tag updated:[/] [autumn.note]{item['name']}[/]")
    except APIError as exc:
        console.print(f"[autumn.err]Error:[/] {exc}")
        raise click.Abort()


@tag.command("delete")
@click.argument("name")
@click.option("--yes", "yes", is_flag=True, help="Skip confirmation prompt")
def tag_delete(name: str, yes: bool) -> None:
    """Delete a tag."""
    try:
        client = APIClient()
        item = _find_named_item(client.list_tags(compact=False).get("tags", []), name, "tag")
        if not yes and not click.confirm(f"Delete tag '{item['name']}'?", default=False):
            console.print("[autumn.muted]Cancelled.[/]")
            return
        client.delete_tag(item["id"])
        _clear_metadata_caches()
        console.print(f"[autumn.ok]Tag deleted:[/] [autumn.note]{item['name']}[/]")
    except APIError as exc:
        console.print(f"[autumn.err]Error:[/] {exc}")
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
@click.option("--dry-run", is_flag=True, help="Preview changes without saving totals")
def meta_audit(dry_run: bool) -> None:
    """Recompute and persist totals for all projects and subprojects.

    This fixes any discrepancies between computed totals and actual session data.
    Useful after imports, manual database changes, or if totals seem incorrect.
    """
    try:
        client = APIClient()
        mode = "dry-run audit" if dry_run else "audit"
        console.print(f"[dim]Running {mode} for project/subproject totals...[/]")

        result = client.audit_totals(dry_run=dry_run)

        if result.get("deprecated"):
            message = result.get(
                "message",
                "Deprecated: totals are always derived from sessions now; "
                "there is nothing to audit.",
            )
            console.print(f"[autumn.warn]{message}[/]")
            return

        if result.get("ok"):
            projects = result.get("projects", {})
            subprojects = result.get("subprojects", {})
            changed_projects = result.get("changed_projects", [])
            changed_subprojects = result.get("changed_subprojects", [])

            console.print()
            if result.get("dry_run") or dry_run:
                console.print("[autumn.ok]Audit preview complete.[/]")
            else:
                console.print("[autumn.ok]Audit complete.[/]")
            console.print()

            # Projects summary
            proj_count = projects.get("count", 0)
            proj_changed = projects.get("changed", 0)
            proj_delta = projects.get("delta", projects.get("delta_total", 0))

            delta_sign = "+" if proj_delta >= 0 else ""
            console.print(f"[autumn.label]Projects:[/] {proj_count} checked, {proj_changed} changed (delta: {delta_sign}{proj_delta:.1f} min)")

            # Subprojects summary
            sub_count = subprojects.get("count", 0)
            sub_changed = subprojects.get("changed", 0)
            sub_delta = subprojects.get("delta", subprojects.get("delta_total", 0))

            delta_sign = "+" if sub_delta >= 0 else ""
            console.print(f"[autumn.label]Subprojects:[/] {sub_count} checked, {sub_changed} changed (delta: {delta_sign}{sub_delta:.1f} min)")

            _print_changed_projects(changed_projects)
            _print_changed_subprojects(changed_subprojects)

            if dry_run:
                console.print()
                console.print("[autumn.muted]Dry run only. No totals were saved.[/]")
            else:
                # Clear caches since totals may have changed
                clear_cached_projects()
                clear_cached_activity()
        else:
            console.print(f"[autumn.err]Error:[/] {result.get('error', 'Unknown error')}")
            raise click.Abort()
    except APIError as e:
        console.print(f"[autumn.err]Error:[/] {e}")
        raise click.Abort()
