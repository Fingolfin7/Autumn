"""Project commands for Autumn CLI."""

import click
from typing import Optional
from ..api_client import APIClient, APIError
from ..utils.formatters import projects_tables, subprojects_table
from ..utils.console import console

from ..utils.resolvers import resolve_context_param, resolve_tag_params, resolve_project_param


@click.command()
@click.option(
    "--status",
    "-S",
    type=click.Choice(["all", "active", "paused", "complete", "archived"]),
    default="active",
    show_default=True,
    help="Filter by status (use `all` to show every type)",
)
@click.option("--context", "-c", help="Filter by context name")
@click.option(
    "--tag", "-t", multiple=True, help="Filter by tag (can be used multiple times)"
)
@click.option("--start-date", help="Start date (YYYY-MM-DD)")
@click.option("--end-date", help="End date (YYYY-MM-DD)")
@click.option(
    "--pick", is_flag=True, help="Interactively pick context/tags if not provided"
)
@click.option("--desc", "-d", is_flag=True, help="Show project descriptions")
def projects_list(
    status: Optional[str],
    context: Optional[str],
    tag: tuple,
    start_date: Optional[str],
    end_date: Optional[str],
    pick: bool,
    desc: bool,
):
    """List projects grouped by status."""

    try:
        client = APIClient()

        meta = client.get_discovery_meta(ttl_seconds=300, refresh=False)
        contexts_payload = meta.get("contexts", [])
        tags_payload = meta.get("tags", [])

        if pick:
            from ..utils.pickers import pick_context, pick_tag

            if not context:
                chosen = pick_context(client)
                context = chosen or context

            if not tag:
                chosen = pick_tag(client)
                tag = tuple([chosen]) if chosen else tag

        ctx_res = resolve_context_param(context=context, contexts=contexts_payload)
        tag_resolved, _tag_warnings = resolve_tag_params(
            tags=list(tag) if tag else None, known_tags=tags_payload
        )

        result = client.list_projects_grouped(
            start_date=start_date,
            end_date=end_date,
            context=ctx_res.value,
            tags=tag_resolved or None,
        )

        projects_data = result.get("projects", {})
        summary = result.get("summary", {})

        # Filter by status if requested (use "all" to show every type)
        if status and status != "all":
            filtered_projects = {status: projects_data.get(status, [])}
            result["projects"] = filtered_projects

        tables = projects_tables(result, show_descriptions=desc)

        if not tables:
            console.print("[dim]No projects found.[/]")
        else:
            for table in tables:
                console.print(table)
                console.print()
    except APIError as e:
        console.print(f"[autumn.err]Error:[/] {e}")
        raise click.Abort()


@click.command()
@click.argument("project")
@click.option("--desc", "-d", is_flag=True, help="Show subproject descriptions")
def subprojects(project: str, desc: bool):
    """List subprojects for a given project."""

    try:
        client = APIClient()

        # Resolve project name (case-insensitive + alias support)
        projects_meta = client.get_discovery_projects()
        proj_res = resolve_project_param(project=project, projects=projects_meta.get("projects", []))
        if proj_res.warning:
            console.print(f"[autumn.warn]Warning:[/] {proj_res.warning}")
        resolved_project = proj_res.value or project

        # Use list_subprojects endpoint - requesting non-compact to get full metadata
        result = client.list_subprojects(resolved_project, compact=False)

        # If the API explicitly returns ok: false, show the error.
        # Otherwise, assume it's a successful response (either a list or a dict).
        if isinstance(result, dict) and result.get("ok") is False:
            console.print(
                f"[autumn.err]Error:[/] {result.get('error', 'Unknown error')}"
            )
            return

        # Check if result is a list (non-compact) or dict
        if isinstance(result, list):
            subs = result
        else:
            subs = result.get("subprojects") or result.get("subs") or []

        # Fetch session counts by searching all sessions for this project
        # We'll use the search_sessions endpoint with a large limit
        session_counts = {}
        try:
            # Search for sessions for this project to calculate counts
            sessions_res = client.search_sessions(project=resolved_project, limit=1000)
            sessions = sessions_res.get("sessions", [])

            from collections import Counter

            counts = Counter()
            for s in sessions:
                s_subs = s.get("subs") or s.get("subprojects") or []
                for sub_name in s_subs:
                    counts[sub_name] += 1
            session_counts = dict(counts)
        except Exception:
            # Fallback if session search fails
            session_counts = {}

        # Add session_count to subproject objects
        if isinstance(subs, list):
            for sub in subs:
                if isinstance(sub, dict):
                    name = sub.get("name")
                    if name in session_counts:
                        sub["session_count"] = session_counts[name]

        table = subprojects_table(resolved_project, subs, show_descriptions=desc)
        console.print(table)

    except APIError as e:
        console.print(f"[autumn.err]Error:[/] {e}")
        raise click.Abort()


@click.command()
@click.argument("project")
@click.option("--subproject", "-s", help="Create a subproject instead (requires existing project)")
@click.option("--description", "-d", help="Project/subproject description")
@click.option("--pick", is_flag=True, help="Interactively pick parent project for subproject")
def new_project(project: str, subproject: Optional[str], description: Optional[str], pick: bool):
    """Create a new project or subproject.

    To create a project: autumn new "My Project"
    To create a subproject: autumn new "My Project" -s "Subproject Name"
    """
    try:
        client = APIClient()

        if subproject or pick:
            # Creating a subproject - project arg is the parent
            parent_project = project

            if pick:
                from ..utils.pickers import pick_project
                picked = pick_project(client, label="parent project")
                if picked:
                    parent_project = picked
                elif not project:
                    console.print("[autumn.warn]No parent project selected.[/]")
                    raise click.Abort()

            # Resolve parent project name
            projects_meta = client.get_discovery_projects()
            proj_res = resolve_project_param(project=parent_project, projects=projects_meta.get("projects", []))
            if proj_res.warning:
                console.print(f"[autumn.warn]Warning:[/] {proj_res.warning}")
            resolved_parent = proj_res.value or parent_project

            if not subproject:
                subproject = click.prompt("Subproject name")

            result = client.create_subproject(resolved_parent, subproject, description)

            if result.get("ok") is False:
                console.print(f"[autumn.err]Error:[/] {result.get('error', 'Unknown error')}")
                raise click.Abort()

            console.print(f"[autumn.ok]Subproject created:[/] [autumn.subproject]{subproject}[/]")
            console.print(f"[autumn.label]Parent:[/] [autumn.project]{resolved_parent}[/]")
            if description:
                console.print(f"[autumn.label]Description:[/] {description}")
        else:
            # Creating a project
            result = client.create_project(project, description)

            console.print(f"[autumn.ok]Project created:[/] [autumn.project]{project}[/]")
            if description:
                console.print(f"[autumn.label]Description:[/] {description}")
    except APIError as e:
        console.print(f"[autumn.err]Error:[/] {e}")
        raise click.Abort()


VALID_STATUSES = ["active", "paused", "complete", "archived"]


@click.command()
@click.argument("project", required=False)
@click.argument("status", required=False, type=click.Choice(VALID_STATUSES, case_sensitive=False))
@click.option("--pick", is_flag=True, help="Interactively pick project")
def mark(project: Optional[str], status: Optional[str], pick: bool):
    """Mark a project's status (active, paused, complete, archived).

    Examples:
        autumn mark "Old Project" complete
        autumn mark "Side Project" paused
        autumn mark --pick  # interactive selection
    """
    try:
        client = APIClient()

        # Interactive picker for project
        if pick or not project:
            from ..utils.pickers import pick_project
            picked = pick_project(client, label="project to mark")
            if picked:
                project = picked
            elif not project:
                console.print("[autumn.warn]No project selected.[/]")
                raise click.Abort()

        # Resolve project name
        projects_meta = client.get_discovery_projects()
        proj_res = resolve_project_param(project=project, projects=projects_meta.get("projects", []))
        if proj_res.warning:
            console.print(f"[autumn.warn]Warning:[/] {proj_res.warning}")
        resolved_project = proj_res.value or project

        # Prompt for status if not provided
        if not status:
            console.print("[autumn.label]Select status:[/]")
            for i, s in enumerate(VALID_STATUSES, 1):
                console.print(f"  {i}) {s}")
            choice = click.prompt("Enter number (1-4)", type=int)
            if 1 <= choice <= len(VALID_STATUSES):
                status = VALID_STATUSES[choice - 1]
            else:
                console.print("[autumn.err]Invalid choice.[/]")
                raise click.Abort()

        result = client.mark_project_status(resolved_project, status)

        if result.get("ok"):
            console.print(f"[autumn.ok]Project marked:[/] [autumn.project]{resolved_project}[/] → [autumn.label]{status}[/]")
        else:
            console.print(f"[autumn.err]Error:[/] {result.get('error', 'Unknown error')}")
            raise click.Abort()
    except APIError as e:
        console.print(f"[autumn.err]Error:[/] {e}")
        raise click.Abort()


@click.command()
@click.argument("old_name", required=False)
@click.argument("new_name", required=False)
@click.option("--project", "-p", help="Parent project (for renaming subprojects)")
@click.option("--pick", is_flag=True, help="Interactively pick project/subproject")
def rename(old_name: Optional[str], new_name: Optional[str], project: Optional[str], pick: bool):
    """Rename a project or subproject.

    Rename project: autumn rename "Old Name" "New Name"
    Rename subproject: autumn rename "OldSub" "NewSub" -p "Parent Project"
    """
    try:
        client = APIClient()

        if project or pick:
            # Renaming a subproject
            if pick:
                from ..utils.pickers import pick_project, pick_subproject
                if not project:
                    project = pick_project(client, label="parent project")
                    if not project:
                        console.print("[autumn.warn]No project selected.[/]")
                        raise click.Abort()

            # Resolve parent project
            projects_meta = client.get_discovery_projects()
            proj_res = resolve_project_param(project=project, projects=projects_meta.get("projects", []))
            if proj_res.warning:
                console.print(f"[autumn.warn]Warning:[/] {proj_res.warning}")
            resolved_project = proj_res.value or project

            if pick and not old_name:
                from ..utils.pickers import pick_subproject
                old_name = pick_subproject(client, resolved_project, label="subproject to rename")
                if not old_name:
                    console.print("[autumn.warn]No subproject selected.[/]")
                    raise click.Abort()

            if not old_name:
                old_name = click.prompt("Current subproject name")
            if not new_name:
                new_name = click.prompt("New subproject name")

            result = client.rename_subproject(resolved_project, old_name, new_name)

            if result.get("ok"):
                console.print(f"[autumn.ok]Subproject renamed:[/] [autumn.subproject]{old_name}[/] → [autumn.subproject]{new_name}[/]")
                console.print(f"[autumn.label]Project:[/] [autumn.project]{resolved_project}[/]")
            else:
                console.print(f"[autumn.err]Error:[/] {result.get('error', 'Unknown error')}")
                raise click.Abort()
        else:
            # Renaming a project
            if pick and not old_name:
                from ..utils.pickers import pick_project
                old_name = pick_project(client, label="project to rename")
                if not old_name:
                    console.print("[autumn.warn]No project selected.[/]")
                    raise click.Abort()

            if not old_name:
                old_name = click.prompt("Current project name")
            if not new_name:
                new_name = click.prompt("New project name")

            # Resolve old project name
            projects_meta = client.get_discovery_projects()
            proj_res = resolve_project_param(project=old_name, projects=projects_meta.get("projects", []))
            if proj_res.warning:
                console.print(f"[autumn.warn]Warning:[/] {proj_res.warning}")
            resolved_old = proj_res.value or old_name

            result = client.rename_project(resolved_old, new_name)

            if result.get("ok"):
                console.print(f"[autumn.ok]Project renamed:[/] [autumn.project]{resolved_old}[/] → [autumn.project]{new_name}[/]")
            else:
                console.print(f"[autumn.err]Error:[/] {result.get('error', 'Unknown error')}")
                raise click.Abort()
    except APIError as e:
        console.print(f"[autumn.err]Error:[/] {e}")
        raise click.Abort()


@click.command("delete-project")
@click.argument("project", required=False)
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
@click.option("--pick", is_flag=True, help="Interactively pick project")
def delete_project(project: Optional[str], yes: bool, pick: bool):
    """Delete a project and all its sessions.

    WARNING: This is destructive and cannot be undone!
    """
    try:
        client = APIClient()

        if pick or not project:
            from ..utils.pickers import pick_project
            picked = pick_project(client, label="project to delete")
            if picked:
                project = picked
            elif not project:
                console.print("[autumn.warn]No project selected.[/]")
                raise click.Abort()

        # Resolve project name
        projects_meta = client.get_discovery_projects()
        proj_res = resolve_project_param(project=project, projects=projects_meta.get("projects", []))
        if proj_res.warning:
            console.print(f"[autumn.warn]Warning:[/] {proj_res.warning}")
        resolved_project = proj_res.value or project

        if not yes:
            console.print(f"[autumn.warn]WARNING:[/] This will permanently delete project [autumn.project]{resolved_project}[/] and all its sessions!")
            confirm = click.confirm("Are you sure?", default=False)
            if not confirm:
                console.print("[dim]Cancelled.[/]")
                return

        result = client.delete_project(resolved_project)

        if result.get("ok"):
            console.print(f"[autumn.ok]Deleted project:[/] [autumn.project]{resolved_project}[/]")
        else:
            console.print(f"[autumn.err]Error:[/] {result.get('error', 'Unknown error')}")
            raise click.Abort()
    except APIError as e:
        console.print(f"[autumn.err]Error:[/] {e}")
        raise click.Abort()


@click.command("delete-sub")
@click.argument("project", required=False)
@click.argument("subproject", required=False)
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
@click.option("--pick", is_flag=True, help="Interactively pick project/subproject")
def delete_sub(project: Optional[str], subproject: Optional[str], yes: bool, pick: bool):
    """Delete a subproject from a project.

    WARNING: This is destructive and cannot be undone!
    """
    try:
        client = APIClient()

        if pick or not project:
            from ..utils.pickers import pick_project
            picked = pick_project(client, label="parent project")
            if picked:
                project = picked
            elif not project:
                console.print("[autumn.warn]No project selected.[/]")
                raise click.Abort()

        # Resolve project name
        projects_meta = client.get_discovery_projects()
        proj_res = resolve_project_param(project=project, projects=projects_meta.get("projects", []))
        if proj_res.warning:
            console.print(f"[autumn.warn]Warning:[/] {proj_res.warning}")
        resolved_project = proj_res.value or project

        if pick or not subproject:
            from ..utils.pickers import pick_subproject
            picked = pick_subproject(client, resolved_project, label="subproject to delete")
            if picked:
                subproject = picked
            elif not subproject:
                console.print("[autumn.warn]No subproject selected.[/]")
                raise click.Abort()

        if not yes:
            console.print(f"[autumn.warn]WARNING:[/] This will permanently delete subproject [autumn.subproject]{subproject}[/] from [autumn.project]{resolved_project}[/]!")
            confirm = click.confirm("Are you sure?", default=False)
            if not confirm:
                console.print("[dim]Cancelled.[/]")
                return

        result = client.delete_subproject(resolved_project, subproject)

        if result.get("ok"):
            console.print(f"[autumn.ok]Deleted subproject:[/] [autumn.subproject]{subproject}[/] from [autumn.project]{resolved_project}[/]")
        else:
            console.print(f"[autumn.err]Error:[/] {result.get('error', 'Unknown error')}")
            raise click.Abort()
    except APIError as e:
        console.print(f"[autumn.err]Error:[/] {e}")
        raise click.Abort()


@click.command()
@click.argument("project", required=False)
@click.option("--start-date", help="Start date filter (YYYY-MM-DD)")
@click.option("--end-date", help="End date filter (YYYY-MM-DD)")
@click.option("--pick", is_flag=True, help="Interactively pick project")
def totals(project: Optional[str], start_date: Optional[str], end_date: Optional[str], pick: bool):
    """Show time totals for a project and its subprojects.

    Examples:
        autumn totals "My Project"
        autumn totals "My Project" --start-date 2026-01-01
        autumn totals --pick
    """
    try:
        client = APIClient()

        if pick or not project:
            from ..utils.pickers import pick_project
            picked = pick_project(client, label="project")
            if picked:
                project = picked
            elif not project:
                console.print("[autumn.warn]No project selected.[/]")
                raise click.Abort()

        # Resolve project name
        projects_meta = client.get_discovery_projects()
        proj_res = resolve_project_param(project=project, projects=projects_meta.get("projects", []))
        if proj_res.warning:
            console.print(f"[autumn.warn]Warning:[/] {proj_res.warning}")
        resolved_project = proj_res.value or project

        result = client.get_project_totals(resolved_project, start_date=start_date, end_date=end_date)

        project_name = result.get("project", resolved_project)
        total_minutes = result.get("total", 0)
        subs = result.get("subs", [])

        # Format total time
        hours = int(total_minutes // 60)
        mins = int(total_minutes % 60)
        if hours > 0:
            total_str = f"{hours}h {mins}m"
        else:
            total_str = f"{mins}m"

        console.print(f"[autumn.label]Project:[/] [autumn.project]{project_name}[/]")
        console.print(f"[autumn.label]Total:[/] [autumn.duration]{total_str}[/] ({total_minutes:.1f} minutes)")

        if subs:
            console.print()
            console.print("[autumn.label]Subprojects:[/]")
            for sub_name, sub_minutes in subs:
                sub_hours = int(sub_minutes // 60)
                sub_mins = int(sub_minutes % 60)
                if sub_hours > 0:
                    sub_str = f"{sub_hours}h {sub_mins}m"
                else:
                    sub_str = f"{sub_mins}m"
                pct = (sub_minutes / total_minutes * 100) if total_minutes > 0 else 0
                console.print(f"  [autumn.subproject]{sub_name}[/]: [autumn.duration]{sub_str}[/] ({pct:.1f}%)")
    except APIError as e:
        console.print(f"[autumn.err]Error:[/] {e}")
        raise click.Abort()
