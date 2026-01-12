"""Project commands for Autumn CLI."""

import click
from typing import Optional
from ..api_client import APIClient, APIError
from ..utils.formatters import projects_tables
from ..utils.console import console
from ..utils.resolvers import resolve_context_param, resolve_tag_params


@click.command()
@click.option("--status", type=click.Choice(["active", "paused", "complete", "archived"]), help="Filter by status")
@click.option("--context", "-c", help="Filter by context name")
@click.option("--tag", "-t", multiple=True, help="Filter by tag (can be used multiple times)")
@click.option("--start-date", help="Start date (YYYY-MM-DD)")
@click.option("--end-date", help="End date (YYYY-MM-DD)")
@click.option("--pick", is_flag=True, help="Interactively pick context/tags if not provided")
def projects_list(
    status: Optional[str],
    context: Optional[str],
    tag: tuple,
    start_date: Optional[str],
    end_date: Optional[str],
    pick: bool,
):
    """List projects grouped by status."""
    try:
        client = APIClient()

        meta = client.get_discovery_meta(ttl_seconds=300, refresh=False)
        contexts_payload = meta.get("contexts", [])
        tags_payload = meta.get("tags", [])

        if pick:
            from ..utils.pickers import pick_from_names

            if not context:
                ctx_names = [c.get("name") for c in contexts_payload if c.get("name")]
                chosen = pick_from_names(label="context", names=sorted(ctx_names))
                context = chosen or context

            if not tag:
                tag_names = [t.get("name") for t in tags_payload if t.get("name")]
                chosen = pick_from_names(label="tag", names=sorted(tag_names))
                tag = tuple([chosen]) if chosen else tag

        ctx_res = resolve_context_param(context=context, contexts=contexts_payload)
        tag_resolved, _tag_warnings = resolve_tag_params(tags=list(tag) if tag else None, known_tags=tags_payload)

        result = client.list_projects_grouped(
            start_date=start_date,
            end_date=end_date,
            context=ctx_res.value,
            tags=tag_resolved or None,
        )

        projects_data = result.get("projects", {})
        summary = result.get("summary", {})
        
        # Filter by status if requested
        if status:
            filtered_projects = {status: projects_data.get(status, [])}
            result["projects"] = filtered_projects
        
        # Display colored summary
        console.print("[bold]Projects Summary[/]")
        console.print(f"  [autumn.status.active]Active:[/]   {summary.get('active', 0)}")
        console.print(f"  [autumn.status.paused]Paused:[/]   {summary.get('paused', 0)}")
        console.print(f"  [autumn.status.complete]Complete:[/] {summary.get('complete', 0)}")
        console.print(f"  [autumn.status.archived]Archived:[/] {summary.get('archived', 0)}")
        console.print(f"  [bold]Total:[/]    {summary.get('total', 0)}")
        console.print()

        tables = projects_tables(result)
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
@click.option("--description", "-d", help="Project description")
def new_project(project: str, description: Optional[str]):
    """Create a new project."""
    try:
        client = APIClient()
        result = client.create_project(project, description)
        
        click.echo(f"Project created: {project}")
        if description:
            click.echo(f"  Description: {description}")
    except APIError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()
