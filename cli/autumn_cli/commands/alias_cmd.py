"""Alias commands for Autumn CLI.

Aliases allow short names for projects, contexts, tags, and subprojects.
Subproject aliases are scoped to their parent project.

Config structure in ~/.autumn/config.yaml:
    aliases:
      projects:
        cli: "Autumn CLI"
      contexts:
        home: Personal
      tags:
        c: "Client Work"
      subprojects:
        "Autumn CLI":
          fe: Frontend
          be: Backend
"""

import click
from typing import Optional

from ..config import get_config_value, set_config_value
from ..utils.console import console
from ..api_client import APIClient, APIError


ALIAS_TYPES = ["project", "context", "tag", "subproject"]


def _get_aliases_section(alias_type: str) -> dict:
    """Get the aliases dict for a given type."""
    # Map singular to plural for config key
    type_key = {
        "project": "projects",
        "context": "contexts",
        "tag": "tags",
        "subproject": "subprojects",
    }.get(alias_type, f"{alias_type}s")

    return get_config_value(f"aliases.{type_key}", {}) or {}


def _set_aliases_section(alias_type: str, aliases: dict) -> None:
    """Set the aliases dict for a given type."""
    type_key = {
        "project": "projects",
        "context": "contexts",
        "tag": "tags",
        "subproject": "subprojects",
    }.get(alias_type, f"{alias_type}s")

    set_config_value(f"aliases.{type_key}", aliases)


@click.group()
def alias():
    """Manage aliases for projects, contexts, tags, and subprojects.

    Aliases let you use short names instead of full names:

    \b
      autumn alias add project cli "Autumn CLI"
      autumn start cli  # same as: autumn start "Autumn CLI"

    Subproject aliases are scoped to their parent project:

    \b
      autumn alias add subproject fe Frontend -p "Autumn CLI"
    """
    pass


@alias.command("add")
@click.argument("type", type=click.Choice(ALIAS_TYPES, case_sensitive=False))
@click.argument("alias_name")
@click.argument("target", required=False)
@click.option("-p", "--project", help="Parent project (required for subproject aliases)")
@click.option("--pick", is_flag=True, help="Interactively pick the target")
def alias_add(type: str, alias_name: str, target: Optional[str], project: Optional[str], pick: bool):
    """Add an alias.

    \b
    Examples:
      autumn alias add project cli "Autumn CLI"
      autumn alias add context home Personal
      autumn alias add tag c "Client Work"
      autumn alias add subproject fe Frontend -p "Autumn CLI"
      autumn alias add project myproj --pick
    """
    type = type.lower()

    try:
        client = APIClient()
    except APIError:
        client = None

    # Handle subproject aliases (require project scope)
    if type == "subproject":
        if not project and not pick:
            console.print("[autumn.err]Error:[/] Subproject aliases require a parent project. Use -p/--project or --pick.")
            raise click.Abort()

        if pick and not project:
            if not client:
                console.print("[autumn.err]Error:[/] Cannot use --pick without API connection.")
                raise click.Abort()
            from ..utils.pickers import pick_project
            project = pick_project(client, label="parent project for alias")
            if not project:
                console.print("[autumn.warn]No project selected.[/]")
                raise click.Abort()

        if pick and not target:
            if not client:
                console.print("[autumn.err]Error:[/] Cannot use --pick without API connection.")
                raise click.Abort()
            from ..utils.pickers import pick_subproject
            target = pick_subproject(client, project, label="subproject to alias")
            if not target:
                console.print("[autumn.warn]No subproject selected.[/]")
                raise click.Abort()

        if not target:
            console.print("[autumn.err]Error:[/] Target is required. Provide a target name or use --pick.")
            raise click.Abort()

        # Get existing subproject aliases
        all_sub_aliases = _get_aliases_section("subproject")
        if not isinstance(all_sub_aliases, dict):
            all_sub_aliases = {}

        # Get or create project-specific dict
        project_aliases = all_sub_aliases.get(project, {})
        if not isinstance(project_aliases, dict):
            project_aliases = {}

        project_aliases[alias_name] = target
        all_sub_aliases[project] = project_aliases
        _set_aliases_section("subproject", all_sub_aliases)

        console.print(f"[autumn.ok]Added alias:[/] [bold]{alias_name}[/] → [autumn.subproject]{target}[/]")
        console.print(f"[dim]Scoped to project:[/] [autumn.project]{project}[/]")
        return

    # Handle other alias types (project, context, tag)
    if pick and not target:
        if not client:
            console.print("[autumn.err]Error:[/] Cannot use --pick without API connection.")
            raise click.Abort()

        if type == "project":
            from ..utils.pickers import pick_project
            target = pick_project(client, label="project to alias")
        elif type == "context":
            from ..utils.pickers import pick_context
            target = pick_context(client, label="context to alias")
        elif type == "tag":
            from ..utils.pickers import pick_tag
            target = pick_tag(client, label="tag to alias")

        if not target:
            console.print(f"[autumn.warn]No {type} selected.[/]")
            raise click.Abort()

    if not target:
        console.print("[autumn.err]Error:[/] Target is required. Provide a target name or use --pick.")
        raise click.Abort()

    aliases = _get_aliases_section(type)
    if not isinstance(aliases, dict):
        aliases = {}

    aliases[alias_name] = target
    _set_aliases_section(type, aliases)

    # Style based on type
    style = {
        "project": "autumn.project",
        "context": "autumn.label",
        "tag": "autumn.label",
    }.get(type, "")

    console.print(f"[autumn.ok]Added alias:[/] [bold]{alias_name}[/] → [{style}]{target}[/]")


@alias.command("remove")
@click.argument("type", type=click.Choice(ALIAS_TYPES, case_sensitive=False))
@click.argument("alias_name")
@click.option("-p", "--project", help="Parent project (required for subproject aliases)")
def alias_remove(type: str, alias_name: str, project: Optional[str]):
    """Remove an alias.

    \b
    Examples:
      autumn alias remove project cli
      autumn alias remove subproject fe -p "Autumn CLI"
    """
    type = type.lower()

    if type == "subproject":
        if not project:
            console.print("[autumn.err]Error:[/] Subproject aliases require a parent project. Use -p/--project.")
            raise click.Abort()

        all_sub_aliases = _get_aliases_section("subproject")
        if not isinstance(all_sub_aliases, dict):
            console.print(f"[autumn.warn]No subproject aliases found.[/]")
            return

        project_aliases = all_sub_aliases.get(project, {})
        if alias_name not in project_aliases:
            console.print(f"[autumn.warn]Alias '{alias_name}' not found for project '{project}'.[/]")
            return

        del project_aliases[alias_name]
        if project_aliases:
            all_sub_aliases[project] = project_aliases
        else:
            # Remove empty project entry
            del all_sub_aliases[project]

        _set_aliases_section("subproject", all_sub_aliases)
        console.print(f"[autumn.ok]Removed alias:[/] {alias_name} [dim](from {project})[/]")
        return

    aliases = _get_aliases_section(type)
    if not isinstance(aliases, dict) or alias_name not in aliases:
        console.print(f"[autumn.warn]Alias '{alias_name}' not found.[/]")
        return

    del aliases[alias_name]
    _set_aliases_section(type, aliases)
    console.print(f"[autumn.ok]Removed alias:[/] {alias_name}")


@alias.command("list")
@click.option("-t", "--type", "filter_type", type=click.Choice(ALIAS_TYPES, case_sensitive=False), help="Filter by type")
@click.option("--json", "json_out", is_flag=True, help="Output as JSON")
def alias_list(filter_type: Optional[str], json_out: bool):
    """List all configured aliases.

    \b
    Examples:
      autumn alias list
      autumn alias list --type project
      autumn alias list --json
    """
    all_aliases = {}

    types_to_show = [filter_type.lower()] if filter_type else ALIAS_TYPES

    for alias_type in types_to_show:
        aliases = _get_aliases_section(alias_type)
        if aliases:
            all_aliases[alias_type] = aliases

    if json_out:
        console.print_json(data=all_aliases)
        return

    if not all_aliases:
        console.print("[dim]No aliases configured.[/]")
        console.print("[dim]Add one with: autumn alias add project myalias \"My Project\"[/]")
        return

    from rich.table import Table

    # Projects
    if "project" in all_aliases:
        table = Table(title="Project Aliases", show_header=True)
        table.add_column("Alias", style="bold")
        table.add_column("Target", style="autumn.project")
        for alias_name, target in sorted(all_aliases["project"].items()):
            table.add_row(alias_name, target)
        console.print(table)
        console.print()

    # Contexts
    if "context" in all_aliases:
        table = Table(title="Context Aliases", show_header=True)
        table.add_column("Alias", style="bold")
        table.add_column("Target")
        for alias_name, target in sorted(all_aliases["context"].items()):
            table.add_row(alias_name, target)
        console.print(table)
        console.print()

    # Tags
    if "tag" in all_aliases:
        table = Table(title="Tag Aliases", show_header=True)
        table.add_column("Alias", style="bold")
        table.add_column("Target")
        for alias_name, target in sorted(all_aliases["tag"].items()):
            table.add_row(alias_name, target)
        console.print(table)
        console.print()

    # Subprojects (grouped by parent project)
    if "subproject" in all_aliases:
        sub_aliases = all_aliases["subproject"]
        for project_name, project_aliases in sorted(sub_aliases.items()):
            if not project_aliases:
                continue
            table = Table(title=f"Subproject Aliases ({project_name})", show_header=True)
            table.add_column("Alias", style="bold")
            table.add_column("Target", style="autumn.subproject")
            for alias_name, target in sorted(project_aliases.items()):
                table.add_row(alias_name, target)
            console.print(table)
            console.print()
