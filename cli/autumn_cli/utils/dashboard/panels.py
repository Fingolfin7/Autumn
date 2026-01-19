from __future__ import annotations
from typing import Dict, List, Any, Optional
from datetime import datetime

from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.console import RenderableType
from rich.text import Text
from rich.progress import ProgressBar

from .state import DashboardState
from ..formatters import format_duration_minutes


def render_header(state: DashboardState) -> Panel:
    if state.active_session:
        p = state.active_session.get("p") or state.active_session.get("project")
        subs = (
            state.active_session.get("subs")
            or state.active_session.get("subprojects")
            or []
        )
        start_str = state.active_session.get("start")

        elapsed_str = "00:00:00"
        if start_str:
            try:
                # Basic local ticking clock logic
                start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                delta = datetime.now().astimezone() - start_dt
                hours, rem = divmod(int(delta.total_seconds()), 3600)
                mins, secs = divmod(rem, 60)
                elapsed_str = f"{hours:02d}:{mins:02d}:{secs:02d}"
            except Exception:
                pass

        subs_str = f" ({', '.join(subs)})" if subs else ""
        content = Text.assemble(
            ("[ACTIVE] ", "bold green"),
            (f"{p}{subs_str}", "autumn.project"),
            (" • ", "white"),
            (elapsed_str, "cyan bold"),
        )
    else:
        content = Text("[NO ACTIVE TIMER]", style="dim")

    now = datetime.now().strftime("%d %b, %H:%M")
    return Panel(
        content,
        title="AUTUMN DASH",
        subtitle=now,
        title_align="left",
        subtitle_align="right",
    )


def render_tally_panel(state: DashboardState) -> Panel:
    table = Table.grid(padding=(0, 1))
    table.add_column("Project", style="autumn.project", no_wrap=True)
    table.add_column("Progress", width=12)
    table.add_column("Time", style="autumn.duration", justify="right")

    total_week_mins = sum(p.get("total_time", 0) for p in state.weekly_tally)

    for p in state.weekly_tally[:5]:
        name = p.get("name", "Unknown")
        mins = p.get("total_time", 0)
        pct = (mins / total_week_mins) if total_week_mins > 0 else 0

        bar = ProgressBar(total=1.0, completed=pct, width=10, pulse=False)
        table.add_row(name, bar, format_duration_minutes(mins))

    return Panel(table, title="WEEKLY TALLY")


def render_intensity_panel(state: DashboardState) -> Panel:
    table = Table.grid(padding=(0, 1))
    table.add_column("Day", style="autumn.label", width=4)
    table.add_column("Bar", width=20)
    table.add_column("Hours", style="autumn.duration", justify="right")

    # Show last 7 days from state
    max_mins = max(state.daily_intensity.values()) if state.daily_intensity else 0
    max_mins = max(max_mins, 480)  # Normalize to 8h at least for scale

    for day, mins in state.daily_intensity.items():
        pct = (mins / max_mins) if max_mins > 0 else 0
        bar = ProgressBar(total=1.0, completed=pct, width=18, pulse=False)
        table.add_row(day, bar, f"{mins / 60:.1f}h")

    return Panel(table, title="DAILY INTENSITY (HOURS)")


def render_subprojects_panel(state: DashboardState) -> Panel:
    title = (
        f"TOP SUBPROJECTS ({state.most_active_project})"
        if state.most_active_project
        else "TOP SUBPROJECTS"
    )
    table = Table.grid(padding=(0, 1))
    table.add_column("Subproject", style="autumn.subproject", no_wrap=True)
    table.add_column("Progress", width=12)
    table.add_column("Time", style="autumn.duration", justify="right")

    total_proj_mins = sum(s.get("total_time", 0) for s in state.top_subprojects)

    for s in state.top_subprojects:
        name = s.get("name", "Unknown")
        mins = s.get("total_time", 0)
        pct = (mins / total_proj_mins) if total_proj_mins > 0 else 0

        bar = ProgressBar(total=1.0, completed=pct, width=10, pulse=False)
        table.add_row(name, bar, format_duration_minutes(mins))

    return Panel(table, title=title)


def render_trends_panel(state: DashboardState) -> Panel:
    table = Table.grid(padding=(0, 1))
    table.add_column("Stat", style="autumn.label")
    table.add_column("Value", justify="right")

    t = state.trends
    total_str = f"{t['total_time'] / 60:.1f}h"

    change = t["change_pct"]
    change_color = "green" if change >= 0 else "red"
    change_str = (
        f"[{change_color}]{'+' if change >= 0 else ''}{change:.1f}% vs last week[/]"
    )

    table.add_row("Total Time", total_str)
    table.add_row("Change", change_str)
    table.add_row("Streak", f"{t['streak']} Days")
    table.add_row("Avg/Day", f"{t['avg_daily'] / 60:.1f}h")

    return Panel(table, title="WEEKLY TRENDS")


def render_log_panel(state: DashboardState) -> Panel:
    log_text = Text()
    for entry in state.logs:
        log_text.append(entry + "\n")

    return Panel(log_text, title="TERMINAL LOG", border_style="dim")


def render_dashboard(state: DashboardState) -> Layout:
    layout = Layout()

    layout.split(
        Layout(name="header", size=3),
        Layout(name="main"),
        Layout(name="logs", size=7),
        Layout(name="footer", size=1),
    )

    layout["main"].split_row(Layout(name="left"), Layout(name="right"))

    layout["left"].split(Layout(name="tally"), Layout(name="subs"))

    layout["right"].split(Layout(name="intensity"), Layout(name="trends"))

    layout["header"].update(render_header(state))
    layout["tally"].update(render_tally_panel(state))
    layout["subs"].update(render_subprojects_panel(state))
    layout["intensity"].update(render_intensity_panel(state))
    layout["trends"].update(render_trends_panel(state))
    layout["logs"].update(render_log_panel(state))

    return layout
