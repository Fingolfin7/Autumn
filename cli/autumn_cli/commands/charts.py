"""Chart commands for Autumn CLI."""

import click
from typing import Optional
from pathlib import Path
from ..api_client import APIClient, APIError
from ..utils.charts import (
    render_pie_chart, 
    render_bar_chart, 
    render_scatter_chart, 
    render_heatmap,
    render_calendar_chart,
    render_wordcloud_chart,
)
from ..utils.resolvers import resolve_context_param, resolve_tag_params


@click.command()
@click.option(
    "--type",
    "-t",
    type=click.Choice(["pie", "bar", "scatter", "calendar", "wordcloud", "heatmap"], case_sensitive=False),
    default="pie",
    help="Chart type (default: pie)",
)
@click.option("--project", "-p", help="Project name (shows subprojects if specified for pie/bar)")
@click.option("--context", "-c", help="Filter by context (name or id)")
@click.option("--tag", "-g", multiple=True, help="Filter by tag (repeatable)")
@click.option(
    "--period",
    "-pd",
    type=click.Choice(
        ["day", "week", "fortnight", "month", "lunar cycle", "quarter", "year", "all"],
        case_sensitive=False,
    ),
    default=None,
    help="Time period (same options as 'log')",
)
@click.option("--start-date", help="Start date (YYYY-MM-DD)")
@click.option("--end-date", help="End date (YYYY-MM-DD)")
@click.option("--save", type=click.Path(), help="Save chart to file instead of displaying")
@click.option("--pick", is_flag=True, help="Interactively pick project/context/tags if not provided")
def chart(
    type: str,
    project: Optional[str],
    context: Optional[str],
    tag: tuple,
    period: Optional[str],
    start_date: Optional[str],
    end_date: Optional[str],
    save: Optional[str],
    pick: bool,
):
    """Render charts. Default type is pie. Also accepts: bar, scatter, calendar, wordcloud, heatmap."""
    type = type.lower()  # Normalize case

    # Derive start/end from period if not explicitly supplied
    if (not start_date or not end_date) and period and period.lower() != "all":
        from ..utils.periods import period_to_dates

        derived_start, derived_end = period_to_dates(period)
        start_date = start_date or derived_start
        end_date = end_date or derived_end

    try:
        client = APIClient()

        if save:
            save_path = Path(save)
            save_path.parent.mkdir(parents=True, exist_ok=True)
        else:
            save_path = None

        meta = client.get_discovery_meta(ttl_seconds=300, refresh=False)
        contexts_payload = meta.get("contexts", [])
        tags_payload = meta.get("tags", [])

        if pick:
            from ..utils.pickers import pick_from_names, normalize_repeatable

            if not project:
                # Pick project from grouped endpoint
                grouped = client.list_projects_grouped()
                all_projects = []
                for bucket in (grouped.get("projects") or {}).values():
                    for p in bucket or []:
                        name = p.get("name") or p.get("project")
                        if name:
                            all_projects.append(name)
                all_projects = sorted(set(all_projects))
                chosen = pick_from_names(label="project", names=all_projects)
                project = chosen or project

            if not context:
                ctx_names = [c.get("name") for c in contexts_payload if c.get("name")]
                chosen = pick_from_names(label="context", names=sorted(ctx_names))
                context = chosen or context

            if not tag:
                tag_names = [t.get("name") for t in tags_payload if t.get("name")]
                chosen = pick_from_names(label="tag", names=sorted(tag_names))
                tag = tuple([chosen]) if chosen else tag

        ctx_res = resolve_context_param(context=context, contexts=contexts_payload)
        if ctx_res.warning:
            click.echo(f"Warning: {ctx_res.warning}", err=True)

        tag_resolved, tag_warnings = resolve_tag_params(tags=list(tag) if tag else None, known_tags=tags_payload)
        for w in tag_warnings:
            click.echo(f"Warning: {w}", err=True)

        resolved_context = ctx_res.value
        resolved_tags = tag_resolved or None

        if type in ("pie", "bar"):
            # Use tally endpoints for pie/bar
            if project:
                # Show subprojects for specific project
                data = client.tally_by_subprojects(
                    project,
                    start_date,
                    end_date,
                    context=resolved_context,
                    tags=resolved_tags,
                )
                title = f"Time Distribution: {project} (Subprojects)" if type == "pie" else f"Time Totals: {project} (Subprojects)"
            else:
                # Show all projects
                data = client.tally_by_sessions(
                    project_name=None,
                    start_date=start_date,
                    end_date=end_date,
                    context=resolved_context,
                    tags=resolved_tags,
                )
                title = "Time Distribution: All Projects" if type == "pie" else "Time Totals: All Projects"
            
            if type == "pie":
                render_pie_chart(data, title=title, save_path=save_path)
            else:  # bar
                render_bar_chart(data, title=title, save_path=save_path)
        
        elif type in ("scatter", "calendar", "heatmap", "wordcloud"):
            # Use list_sessions for scatter/calendar/heatmap/wordcloud
            sessions = client.list_sessions(
                project_name=project,
                start_date=start_date,
                end_date=end_date,
                context=resolved_context,
                tags=resolved_tags,
            )

            if type == "scatter":
                title = f"Session Duration Over Time"
                if project:
                    title += f" - {project}"
                render_scatter_chart(sessions, title=title, save_path=save_path)
            
            elif type == "calendar":
                title = "Projects Calendar"
                if project:
                    title += f" - {project}"
                render_calendar_chart(sessions, title=title, save_path=save_path)
            
            elif type == "heatmap":
                title = "Activity Heatmap"
                if project:
                    title += f" - {project}"
                render_heatmap(sessions, title=title, save_path=save_path)
            
            elif type == "wordcloud":
                title = "Session Notes Wordcloud"
                if project:
                    title += f" - {project}"
                render_wordcloud_chart(sessions, title=title, save_path=save_path)
    except APIError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()
