"""Project commands for Autumn CLI."""

import click
from typing import Optional
from ..api_client import APIClient, APIError
from ..utils.formatters import projects_tables, subprojects_table
from ..utils.console import console

from ..utils.resolvers import resolve_context_param, resolve_tag_params


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
        # Use list_subprojects endpoint - requesting non-compact to get full metadata
        result = client.list_subprojects(project, compact=False)

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
            sessions_res = client.search_sessions(project=project, limit=1000)
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

        table = subprojects_table(project, subs, show_descriptions=desc)
        console.print(table)

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
