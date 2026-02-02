"""Chart commands for Autumn CLI."""

import click
from typing import Optional
from pathlib import Path
from ..api_client import APIClient, APIError
from ..utils.charts import (
    render_pie_chart,
    render_bar_chart,
    render_scatter_chart,
    render_line_chart,
    render_heatmap,
    render_calendar_chart,
    render_wordcloud_chart,
    render_stacked_area_chart,
    render_cumulative_chart,
    render_treemap_chart,
    render_sunburst_chart,
    render_status_chart,
    render_context_chart,
    render_histogram_chart,
    render_radar_chart,
    render_tag_bubble_chart,
)
from ..utils.resolvers import resolve_context_param, resolve_tag_params, resolve_project_param


# All available chart types
CHART_TYPES = [
    "pie",
    "bar",
    "scatter",
    "line",
    "area",
    "cumulative",
    "calendar",
    "heatmap",
    "wordcloud",
    "treemap",
    "sunburst",
    "status",
    "context",
    "histogram",
    "radar",
    "bubble",
]


@click.command()
@click.option(
    "--type",
    "-T",
    type=click.Choice(CHART_TYPES, case_sensitive=False),
    default="pie",
    help="Chart type (default: pie)",
)
@click.option(
    "--project", "-p", help="Project name (shows subprojects if specified for pie/bar)"
)
@click.option("--context", "-c", help="Filter by context (name or id)")
@click.option("--tag", "-t", multiple=True, help="Filter by tag (repeatable)")
@click.option(
    "--period",
    "-P",
    type=click.Choice(
        ["day", "week", "fortnight", "month", "lunar cycle", "quarter", "year", "all"],
        case_sensitive=False,
    ),
    default=None,
    help="Time period (same options as 'log')",
)
@click.option("--start-date", help="Start date (YYYY-MM-DD)")
@click.option("--end-date", help="End date (YYYY-MM-DD)")
@click.option(
    "--save", type=click.Path(), help="Save chart to file instead of displaying"
)
@click.option(
    "--color-by-project",
    is_flag=True,
    help="Color calendar/heatmap by dominant project instead of single color",
)
@click.option(
    "--pick",
    is_flag=True,
    help="Interactively pick project/context/tags if not provided",
)
def chart(
    type: str,
    project: Optional[str],
    context: Optional[str],
    tag: tuple,
    period: Optional[str],
    start_date: Optional[str],
    end_date: Optional[str],
    save: Optional[str],
    color_by_project: bool,
    pick: bool,
):
    """Render charts visualizing your tracked time.

    \b
    Chart types:
      pie        - Time distribution pie chart (default)
      bar        - Horizontal bar chart of totals
      scatter    - Individual sessions plotted over time
      line       - Daily totals connected with lines
      area       - Stacked area chart showing cumulative daily time
      cumulative - Running total of hours over time
      calendar   - GitHub-style activity calendar
      heatmap    - Activity by day of week and hour
      wordcloud  - Word cloud from session notes
      treemap    - Nested rectangles (Context > Project > Subproject)
      sunburst   - Concentric rings showing hierarchy
      status     - Donut chart by project status
      context    - Bar chart comparing time across contexts
      histogram  - Distribution of session lengths
      radar      - Spider chart comparing top projects
      bubble     - Tag bubble chart (projects vs hours vs avg time)
    """
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
            from ..utils.pickers import pick_project, pick_context, pick_tag

            if not project:
                chosen = pick_project(client)
                project = chosen or project

            if not context:
                chosen = pick_context(client)
                context = chosen or context

            if not tag:
                chosen = pick_tag(client)
                tag = tuple([chosen]) if chosen else tag

        ctx_res = resolve_context_param(context=context, contexts=contexts_payload)
        if ctx_res.warning:
            click.echo(f"Warning: {ctx_res.warning}", err=True)

        tag_resolved, tag_warnings = resolve_tag_params(
            tags=list(tag) if tag else None, known_tags=tags_payload
        )
        for w in tag_warnings:
            click.echo(f"Warning: {w}", err=True)

        resolved_context = ctx_res.value
        resolved_tags = tag_resolved or None

        # Resolve project name (case-insensitive + alias support)
        resolved_project = project
        if project:
            projects_meta = client.get_discovery_projects()
            proj_res = resolve_project_param(project=project, projects=projects_meta.get("projects", []))
            if proj_res.warning:
                click.echo(f"Warning: {proj_res.warning}", err=True)
            resolved_project = proj_res.value or project

        # ===== PIE / BAR charts =====
        if type in ("pie", "bar"):
            if resolved_project:
                data = client.tally_by_subprojects(
                    resolved_project,
                    start_date,
                    end_date,
                    context=resolved_context,
                    tags=resolved_tags,
                )
                title = (
                    f"Time Distribution: {resolved_project} (Subprojects)"
                    if type == "pie"
                    else f"Time Totals: {resolved_project} (Subprojects)"
                )
            else:
                data = client.tally_by_sessions(
                    project_name=None,
                    start_date=start_date,
                    end_date=end_date,
                    context=resolved_context,
                    tags=resolved_tags,
                )
                title = (
                    "Time Distribution: All Projects"
                    if type == "pie"
                    else "Time Totals: All Projects"
                )

            if type == "pie":
                render_pie_chart(data, title=title, save_path=save_path)
            else:
                render_bar_chart(data, title=title, save_path=save_path)

        # ===== Session-based charts =====
        elif type in ("scatter", "line", "area", "cumulative", "calendar", "heatmap", "wordcloud", "histogram"):
            sessions = client.list_sessions(
                project_name=resolved_project,
                start_date=start_date,
                end_date=end_date,
                context=resolved_context,
                tags=resolved_tags,
            )

            if type == "scatter":
                title = "Session Duration Over Time"
                if resolved_project:
                    title += f" - {resolved_project}"
                render_scatter_chart(sessions, title=title, save_path=save_path)

            elif type == "line":
                title = "Daily Duration Over Time"
                if resolved_project:
                    title += f" - {resolved_project}"
                render_line_chart(sessions, title=title, save_path=save_path)

            elif type == "area":
                title = "Stacked Daily Duration"
                if resolved_project:
                    title += f" - {resolved_project}"
                render_stacked_area_chart(sessions, title=title, save_path=save_path)

            elif type == "cumulative":
                title = "Cumulative Time Tracked"
                if resolved_project:
                    title += f" - {resolved_project}"
                render_cumulative_chart(sessions, title=title, save_path=save_path)

            elif type == "calendar":
                title = "Projects Calendar"
                if resolved_project:
                    title += f" - {resolved_project}"
                render_calendar_chart(
                    sessions,
                    title=title,
                    start_date=start_date,
                    end_date=end_date,
                    save_path=save_path,
                    color_by_project=color_by_project,
                )

            elif type == "heatmap":
                title = "Activity Heatmap"
                if resolved_project:
                    title += f" - {resolved_project}"
                render_heatmap(sessions, title=title, save_path=save_path)

            elif type == "wordcloud":
                title = "Session Notes Wordcloud"
                if resolved_project:
                    title += f" - {resolved_project}"
                render_wordcloud_chart(sessions, title=title, save_path=save_path)

            elif type == "histogram":
                title = "Session Length Distribution"
                if resolved_project:
                    title += f" - {resolved_project}"
                render_histogram_chart(sessions, title=title, save_path=save_path)

        # ===== Hierarchy-based charts (treemap, sunburst) =====
        elif type in ("treemap", "sunburst"):
            hierarchy_data = client.get_hierarchy(
                start_date=start_date,
                end_date=end_date,
            )

            if type == "treemap":
                title = "Time Distribution (Treemap)"
                render_treemap_chart(hierarchy_data, title=title, save_path=save_path)

            elif type == "sunburst":
                title = "Time Distribution (Sunburst)"
                render_sunburst_chart(hierarchy_data, title=title, save_path=save_path)

        # ===== Status chart =====
        elif type == "status":
            status_data = client.tally_by_status(context=resolved_context)
            title = "Time by Project Status"
            render_status_chart(status_data, title=title, save_path=save_path)

        # ===== Context chart =====
        elif type == "context":
            context_data = client.tally_by_context(
                start_date=start_date,
                end_date=end_date,
            )
            title = "Time by Context"
            render_context_chart(context_data, title=title, save_path=save_path)

        # ===== Radar chart =====
        elif type == "radar":
            projects_data = client.get_projects_with_stats(
                context=resolved_context,
                tags=resolved_tags,
            )
            title = "Project Comparison (Radar)"
            render_radar_chart(projects_data, title=title, save_path=save_path)

        # ===== Tag bubble chart =====
        elif type == "bubble":
            tag_data = client.tally_by_tags()
            title = "Tags Overview"
            render_tag_bubble_chart(tag_data, title=title, save_path=save_path)

    except APIError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()
