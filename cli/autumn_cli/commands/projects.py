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
@click.option("--search", "-q", help="Search projects by name")
def projects_list(
    status: Optional[str],
    context: Optional[str],
    tag: tuple,
    start_date: Optional[str],
    end_date: Optional[str],
    pick: bool,
    desc: bool,
    search: Optional[str],
):
    """List projects grouped by status."""

    try:
        client = APIClient()

        # If search is provided, use the search endpoint instead
        if search:
            # When searching, status filter is optional (pass None for "all")
            search_status = None if status == "all" else status
            result = client.search_projects(search, status=search_status)
            projects = result.get("projects", [])

            if not projects:
                console.print(f"[dim]No projects found matching '{search}'.[/]")
                return

            # Display search results as a simple list
            from rich.table import Table
            table = Table(title=f"Projects matching '{search}'", show_header=True)
            table.add_column("Project", style="autumn.project")
            table.add_column("Status")
            if desc:
                table.add_column("Description")

            for proj in projects:
                name = proj.get("name") or proj.get("project")
                proj_status = proj.get("status", "")
                description = proj.get("description", "") if desc else None

                # Style status
                status_style = {
                    "active": "autumn.ok",
                    "paused": "autumn.paused",
                    "complete": "autumn.warn",
                    "archived": "dim",
                }.get(proj_status, "")

                row = [name, f"[{status_style}]{proj_status}[/]"]
                if desc:
                    row.append(description or "")
                table.add_row(*row)

            console.print(table)
            return

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
@click.option("--search", "-q", help="Search subprojects by name")
def subprojects(project: str, desc: bool, search: Optional[str]):
    """List subprojects for a given project."""

    try:
        client = APIClient()

        # Resolve project name (case-insensitive + alias support)
        projects_meta = client.get_discovery_projects()
        proj_res = resolve_project_param(project=project, projects=projects_meta.get("projects", []))
        if proj_res.warning:
            console.print(f"[autumn.warn]Warning:[/] {proj_res.warning}")
        resolved_project = proj_res.value or project

        # If search is provided, use the search endpoint
        if search:
            result = client.search_subprojects(resolved_project, search)
            subs = result.get("subprojects", [])

            if not subs:
                console.print(f"[dim]No subprojects found matching '{search}' in {resolved_project}.[/]")
                return

            # Display search results
            from rich.table import Table
            table = Table(title=f"Subprojects matching '{search}' in {resolved_project}", show_header=True)
            table.add_column("Subproject", style="autumn.subproject")
            if desc:
                table.add_column("Description")

            for sub in subs:
                name = sub.get("name") if isinstance(sub, dict) else sub
                description = sub.get("description", "") if isinstance(sub, dict) and desc else None

                row = [name]
                if desc:
                    row.append(description or "")
                table.add_row(*row)

            console.print(table)
            return

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

        # API now returns session_count and total_minutes directly in non-compact mode
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


@click.command("project")
@click.argument("name", required=False)
@click.option("--pick", is_flag=True, help="Interactively pick project")
def project_details(name: Optional[str], pick: bool):
    """Show detailed information about a single project.

    Examples:
        autumn project "My Project"
        autumn project --pick
    """
    try:
        client = APIClient()

        if pick or not name:
            from ..utils.pickers import pick_project
            picked = pick_project(client, label="project")
            if picked:
                name = picked
            elif not name:
                console.print("[autumn.warn]No project selected.[/]")
                raise click.Abort()

        # Resolve project name
        projects_meta = client.get_discovery_projects()
        proj_res = resolve_project_param(project=name, projects=projects_meta.get("projects", []))
        if proj_res.warning:
            console.print(f"[autumn.warn]Warning:[/] {proj_res.warning}")
        resolved_name = proj_res.value or name

        result = client.get_project(resolved_name)

        # Extract project details
        project_name = result.get("name") or result.get("project") or resolved_name
        status = result.get("status", "unknown")
        description = result.get("description", "")
        total_minutes = result.get("total_time") or result.get("total") or 0
        session_count = result.get("session_count", 0)
        avg_session = result.get("avg_session_duration") or result.get("avg_session", 0)
        context_name = result.get("context") or result.get("context_name")
        tags = result.get("tags", [])
        created = result.get("created") or result.get("created_at")
        subprojects_list = result.get("subprojects", [])

        # Format total time
        hours = int(total_minutes // 60)
        mins = int(total_minutes % 60)
        if hours > 0:
            total_str = f"{hours}h {mins}m"
        else:
            total_str = f"{mins}m"

        # Format avg session
        avg_mins = int(avg_session)
        avg_str = f"{avg_mins}m" if avg_mins > 0 else "-"

        # Status styling
        status_style = {
            "active": "autumn.ok",
            "paused": "autumn.paused",
            "complete": "autumn.warn",
            "archived": "dim",
        }.get(status, "")

        console.print(f"[autumn.label]Project:[/] [autumn.project]{project_name}[/]")
        console.print(f"[autumn.label]Status:[/] [{status_style}]{status}[/]")

        if description:
            console.print(f"[autumn.label]Description:[/] {description}")

        console.print(f"[autumn.label]Total time:[/] [autumn.duration]{total_str}[/] ({total_minutes:.1f} minutes)")
        console.print(f"[autumn.label]Sessions:[/] {session_count}")
        console.print(f"[autumn.label]Avg session:[/] {avg_str}")

        if context_name:
            console.print(f"[autumn.label]Context:[/] {context_name}")

        if tags:
            tag_names = [t.get("name") if isinstance(t, dict) else t for t in tags]
            console.print(f"[autumn.label]Tags:[/] {', '.join(tag_names)}")

        if created:
            console.print(f"[autumn.label]Created:[/] [autumn.time]{created}[/]")

        if subprojects_list:
            sub_names = [s.get("name") if isinstance(s, dict) else s for s in subprojects_list]
            console.print(f"[autumn.label]Subprojects:[/] {len(sub_names)}")
            for sub in sub_names[:10]:  # Show first 10
                console.print(f"  [autumn.subproject]{sub}[/]")
            if len(sub_names) > 10:
                console.print(f"  [dim]... and {len(sub_names) - 10} more[/]")

    except APIError as e:
        console.print(f"[autumn.err]Error:[/] {e}")
        raise click.Abort()


@click.command()
@click.argument("project1", required=False)
@click.argument("project2", required=False)
@click.option("--into", required=False, help="Name for the merged project")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
@click.option("--pick", is_flag=True, help="Interactively pick projects")
def merge(project1: Optional[str], project2: Optional[str], into: Optional[str], yes: bool, pick: bool):
    """Merge two projects into a new one.

    All sessions and subprojects from both projects will be moved to the new project.
    The original projects will be deleted.

    Examples:
        autumn merge "Project A" "Project B" --into "Combined Project"
        autumn merge --pick --into "Merged"
    """
    try:
        client = APIClient()
        projects_meta = client.get_discovery_projects()
        all_projects = projects_meta.get("projects", [])

        if pick or not project1:
            from ..utils.pickers import pick_project
            picked = pick_project(client, label="first project to merge")
            if picked:
                project1 = picked
            elif not project1:
                console.print("[autumn.warn]No project selected.[/]")
                raise click.Abort()

        if pick or not project2:
            from ..utils.pickers import pick_project
            picked = pick_project(client, label="second project to merge")
            if picked:
                project2 = picked
            elif not project2:
                console.print("[autumn.warn]No project selected.[/]")
                raise click.Abort()

        # Resolve project names
        proj1_res = resolve_project_param(project=project1, projects=all_projects)
        if proj1_res.warning:
            console.print(f"[autumn.warn]Warning:[/] {proj1_res.warning}")
        resolved_p1 = proj1_res.value or project1

        proj2_res = resolve_project_param(project=project2, projects=all_projects)
        if proj2_res.warning:
            console.print(f"[autumn.warn]Warning:[/] {proj2_res.warning}")
        resolved_p2 = proj2_res.value or project2

        if not into:
            into = click.prompt("Name for the merged project")

        if not yes:
            console.print(f"[autumn.warn]WARNING:[/] This will merge [autumn.project]{resolved_p1}[/] and [autumn.project]{resolved_p2}[/] into [autumn.project]{into}[/].")
            console.print("[autumn.warn]The original projects will be deleted![/]")
            confirm = click.confirm("Are you sure?", default=False)
            if not confirm:
                console.print("[dim]Cancelled.[/]")
                return

        result = client.merge_projects(resolved_p1, resolved_p2, into)

        message = result.get("message", "Projects merged successfully")
        console.print(f"[autumn.ok]{message}[/]")

        new_proj = result.get("project", {})
        if new_proj:
            console.print(f"[autumn.label]New project:[/] [autumn.project]{new_proj.get('name', into)}[/]")

    except APIError as e:
        console.print(f"[autumn.err]Error:[/] {e}")
        raise click.Abort()


@click.command("merge-subs")
@click.argument("project", required=False)
@click.argument("subproject1", required=False)
@click.argument("subproject2", required=False)
@click.option("--into", required=False, help="Name for the merged subproject")
@click.option("--yes", "-y", is_flag=True, help="Skip confirmation prompt")
@click.option("--pick", is_flag=True, help="Interactively pick project/subprojects")
def merge_subs(project: Optional[str], subproject1: Optional[str], subproject2: Optional[str], into: Optional[str], yes: bool, pick: bool):
    """Merge two subprojects into a new one within a project.

    All sessions from both subprojects will be moved to the new subproject.
    The original subprojects will be deleted.

    Examples:
        autumn merge-subs "My Project" "Frontend" "UI" --into "Frontend UI"
        autumn merge-subs --pick --into "Merged"
    """
    try:
        client = APIClient()
        projects_meta = client.get_discovery_projects()
        all_projects = projects_meta.get("projects", [])

        if pick or not project:
            from ..utils.pickers import pick_project
            picked = pick_project(client, label="parent project")
            if picked:
                project = picked
            elif not project:
                console.print("[autumn.warn]No project selected.[/]")
                raise click.Abort()

        # Resolve project name
        proj_res = resolve_project_param(project=project, projects=all_projects)
        if proj_res.warning:
            console.print(f"[autumn.warn]Warning:[/] {proj_res.warning}")
        resolved_project = proj_res.value or project

        # Get project ID - we need to fetch the project details
        proj_details = client.get_project(resolved_project)
        project_id = proj_details.get("id")
        if not project_id:
            console.print(f"[autumn.err]Error:[/] Could not find project ID for '{resolved_project}'")
            raise click.Abort()

        if pick or not subproject1:
            from ..utils.pickers import pick_subproject
            picked = pick_subproject(client, resolved_project, label="first subproject to merge")
            if picked:
                subproject1 = picked
            elif not subproject1:
                console.print("[autumn.warn]No subproject selected.[/]")
                raise click.Abort()

        if pick or not subproject2:
            from ..utils.pickers import pick_subproject
            picked = pick_subproject(client, resolved_project, label="second subproject to merge")
            if picked:
                subproject2 = picked
            elif not subproject2:
                console.print("[autumn.warn]No subproject selected.[/]")
                raise click.Abort()

        if not into:
            into = click.prompt("Name for the merged subproject")

        if not yes:
            console.print(f"[autumn.warn]WARNING:[/] This will merge [autumn.subproject]{subproject1}[/] and [autumn.subproject]{subproject2}[/] into [autumn.subproject]{into}[/]")
            console.print(f"[autumn.warn]within project [autumn.project]{resolved_project}[/]. The original subprojects will be deleted![/]")
            confirm = click.confirm("Are you sure?", default=False)
            if not confirm:
                console.print("[dim]Cancelled.[/]")
                return

        result = client.merge_subprojects(project_id, subproject1, subproject2, into)

        message = result.get("message", "Subprojects merged successfully")
        console.print(f"[autumn.ok]{message}[/]")

    except APIError as e:
        console.print(f"[autumn.err]Error:[/] {e}")
        raise click.Abort()
