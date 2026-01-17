"""Chart rendering utilities using matplotlib and seaborn."""

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.colors as mcolors
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import seaborn as sns
import pandas as pd
import numpy as np

# Import our timezone-aware parser
from .formatters import parse_utc_to_local

# Set style
sns.set_style("whitegrid")
try:
    plt.style.use("seaborn-v0_8-darkgrid")
except OSError:
    # Fallback for older matplotlib versions
    try:
        plt.style.use("seaborn-darkgrid")
    except OSError:
        # Final fallback
        pass


def generate_color(index: int, total: int) -> tuple:
    """Generate HSL-like color similar to webapp (converted to RGB).

    Python's stdlib uses HLS (hue, lightness, saturation), not HSL.
    """
    import colorsys

    hue = (index * 360.0) / max(total, 1)
    # Old code used HSL with s=1.0, l=0.7.
    # In colorsys.hls_to_rgb: (h, l, s)
    r, g, b = colorsys.hls_to_rgb(hue / 360.0, 0.7, 1.0)
    return int(r * 255), int(g * 255), int(b * 255)


def render_pie_chart(
    data: List[Dict], title: Optional[str] = None, save_path: Optional[str] = None
):
    """Render a pie chart from project/subproject totals."""
    if not data:
        print("No data to display.")
        return

    labels = [item["name"] for item in data]
    values = [item["total_time"] / 60.0 for item in data]  # Convert minutes to hours

    colors = [generate_color(i, len(data)) for i in range(len(data))]

    fig, ax = plt.subplots(figsize=(10, 8))

    wedges, texts, autotexts = ax.pie(
        values,
        labels=labels,
        autopct="%1.1f%%",
        colors=[tuple(c / 255.0 for c in color) for color in colors],
        startangle=90,
    )

    # Improve text readability
    for autotext in autotexts:
        autotext.set_color("white")
        autotext.set_fontweight("bold")

    ax.set_title(title or "Project Time Distribution", fontsize=14, fontweight="bold")

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        print(f"Chart saved to {save_path}")
    else:
        plt.show()

    plt.close()


def render_bar_chart(
    data: List[Dict], title: Optional[str] = None, save_path: Optional[str] = None
):
    """Render a horizontal bar chart from project/subproject totals."""
    if not data:
        print("No data to display.")
        return

    # Sort by value for better visualization
    sorted_data = sorted(data, key=lambda x: x["total_time"])

    labels = [item["name"] for item in sorted_data]
    values = [
        item["total_time"] / 60.0 for item in sorted_data
    ]  # Convert minutes to hours

    colors = [generate_color(i, len(sorted_data)) for i in range(len(sorted_data))]

    fig, ax = plt.subplots(figsize=(10, max(6, len(data) * 0.5)))

    bars = ax.barh(
        labels, values, color=[tuple(c / 255.0 for c in color) for color in colors]
    )

    # Add value labels on bars
    for i, (bar, val) in enumerate(zip(bars, values)):
        width = bar.get_width()
        ax.text(
            width,
            bar.get_y() + bar.get_height() / 2,
            f" {val:.2f}h",
            ha="left",
            va="center",
            fontweight="bold",
        )

    ax.set_xlabel("Total Time (hours)", fontsize=12)
    ax.set_title(title or "Project Totals", fontsize=14, fontweight="bold")
    ax.grid(axis="x", alpha=0.3)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        print(f"Chart saved to {save_path}")
    else:
        plt.show()

    plt.close()


def render_scatter_chart(
    sessions: List[Dict], title: Optional[str] = None, save_path: Optional[str] = None
):
    """Render a scatter plot of sessions over time."""
    if not sessions:
        print("No data to display.")
        return

    # Parse session data
    session_points = []

    # Pre-scan to check if we have a single project context
    unique_projects = set()
    for s in sessions:
        p = s.get("project") or s.get("p", "Unknown")
        unique_projects.add(p)

    use_subproject = len(unique_projects) == 1 or (title and " - " in title)

    for s in sessions:
        # Handle both compact and full formats
        start_time_str = s.get("start_time") or s.get("start", "")
        end_time_str = s.get("end_time") or s.get("end", "")

        if not start_time_str or not end_time_str:
            continue  # Skip sessions without end time

        try:
            # Convert UTC times to local timezone
            start_time = parse_utc_to_local(start_time_str)
            end_time = parse_utc_to_local(end_time_str)

            if not start_time or not end_time:
                continue

            # Calculate duration - prefer provided duration if available, otherwise compute
            duration_minutes = (
                s.get("duration_minutes") or s.get("duration") or s.get("dur")
            )
            if duration_minutes is not None:
                duration_hours = duration_minutes / 60.0
            else:
                duration_hours = (end_time - start_time).total_seconds() / 3600.0

            project = s.get("project") or s.get("p", "Unknown")

            # Determine display group (Project or Subproject)
            if use_subproject:
                subs = s.get("subprojects")
                if subs and isinstance(subs, list) and len(subs) > 0:
                    display_group = ", ".join(subs)
                elif subs and isinstance(subs, str):
                    display_group = subs
                else:
                    # Strict: Do NOT use note as fallback
                    display_group = "No Subproject"
            else:
                display_group = project

            session_points.append(
                {
                    "date": end_time,
                    "duration": duration_hours,
                    "project": display_group,  # Use display_group as the 'project' key for coloring
                }
            )
        except (ValueError, AttributeError) as e:
            # Skip invalid sessions
            continue

    # Group by project
    projects = {}
    for point in session_points:
        proj = point["project"]
        if proj not in projects:
            projects[proj] = {"dates": [], "durations": []}
        projects[proj]["dates"].append(point["date"])
        projects[proj]["durations"].append(point["duration"])

    # Sort projects by name
    sorted_projects = sorted(projects.items())

    fig, ax = plt.subplots(figsize=(12, 8))

    # Plot each project with different color
    for i, (project_name, data) in enumerate(sorted_projects):
        color = generate_color(i, len(sorted_projects))
        ax.scatter(
            data["dates"],
            data["durations"],
            label=project_name,
            alpha=0.6,
            s=50,
            color=tuple(c / 255.0 for c in color),
        )

    ax.set_xlabel("Date", fontsize=12)
    ax.set_ylabel("Duration (hours)", fontsize=12)
    ax.set_title(title or "Session Duration Over Time", fontsize=14, fontweight="bold")
    ax.legend(bbox_to_anchor=(1.05, 1), loc="upper left")
    ax.grid(True, alpha=0.3)

    # Format x-axis dates
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.xticks(rotation=45)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        print(f"Chart saved to {save_path}")
    else:
        plt.show()

    plt.close()


def render_calendar_chart(
    sessions: List[Dict],
    title: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    save_path: Optional[str] = None,
    color_by_project: bool = False,
):
    """Render a GitHub-style calendar heatmap using pandas and matplotlib."""

    # --- 1. Process Data using Pandas ---
    data_list = []
    for s in sessions:
        start_time_str = s.get("start_time") or s.get("start", "")
        end_time_str = s.get("end_time") or s.get("end", "")

        if not start_time_str or not end_time_str:
            continue

        try:
            # Convert to local time
            start_time = parse_utc_to_local(start_time_str)
            if not start_time:
                continue

            # Normalize to date (midnight)
            date_val = pd.Timestamp(start_time.date())

            # Calculate duration in hours
            duration_minutes = (
                s.get("duration_minutes") or s.get("duration") or s.get("dur")
            )
            if duration_minutes is not None:
                duration_hours = float(duration_minutes) / 60.0
            else:
                end_time = parse_utc_to_local(end_time_str)
                duration_hours = (end_time - start_time).total_seconds() / 3600.0

            project_name = s.get("project") or s.get("p", "Unknown")

            data_list.append(
                {"date": date_val, "duration": duration_hours, "project": project_name}
            )

        except (ValueError, AttributeError):
            continue

    if not data_list and not (start_date and end_date):
        print("No data to display and no date range specified.")
        return

    # Create DataFrame
    df = pd.DataFrame(data_list)

    # Check if we should breakdown by subproject
    use_subproject = False
    if not df.empty and color_by_project:
        unique_projs = df["project"].unique()
        # If user asked for specific project OR only 1 project exists in data
        if (title and " - " in title) or len(unique_projs) == 1:
            use_subproject = True

            def get_subproject_label(row):
                # Priority 1: Use 'subprojects' list if available
                subs = row.get("subprojects")
                if subs and isinstance(subs, list) and len(subs) > 0:
                    return ", ".join(subs)
                elif subs and isinstance(subs, str):
                    return subs

                # Strict: Do NOT use note as fallback
                return "No Subproject"

            df["display_group"] = df.apply(get_subproject_label, axis=1)
        else:
            df["display_group"] = df["project"]
    elif not df.empty:
        df["display_group"] = df["project"]
    elif not df.empty:
        df["display_group"] = df["project"]

    if not df.empty:
        # Sum duration by date
        daily_series = df.groupby("date")["duration"].sum()

        # If coloring by project/subproject
        if color_by_project:
            # Group by date and display_group (project or subproject)
            project_daily = (
                df.groupby(["date", "display_group"])["duration"].sum().reset_index()
            )
            # Find row with max duration for each date
            dominant_projects = project_daily.loc[
                project_daily.groupby("date")["duration"].idxmax()
            ]
            dominant_projects = dominant_projects.set_index("date")["display_group"]
        else:
            dominant_projects = pd.Series(dtype=str)

    else:
        daily_series = pd.Series(dtype=float)
        dominant_projects = pd.Series(dtype=str)

    # --- 2. Determine Date Range ---
    if start_date:
        start_ts = pd.Timestamp(start_date)
    elif not daily_series.empty:
        start_ts = daily_series.index.min()
    else:
        # Default to beginning of current year if nothing else
        start_ts = pd.Timestamp(f"{datetime.now().year}-01-01")

    if end_date:
        end_ts = pd.Timestamp(end_date)
    elif not daily_series.empty:
        end_ts = daily_series.index.max()
    else:
        end_ts = pd.Timestamp(datetime.now().date())

    # Ensure start is before end
    if start_ts > end_ts:
        start_ts, end_ts = end_ts, start_ts

    # Reindex series to cover the full range (filling missing days with 0)
    full_range = pd.date_range(start=start_ts, end=end_ts, freq="D")
    daily_series = daily_series.reindex(full_range, fill_value=0.0)

    if color_by_project and not dominant_projects.empty:
        dominant_projects = dominant_projects.reindex(full_range, fill_value=None)

    # --- 3. Build Grid for Heatmap ---
    # Transposed grid: Rows = Weeks, Cols = Days (Mon-Sun)

    # Calculate dimensions
    # Find the Monday of the first week
    first_monday = start_ts - pd.Timedelta(days=start_ts.dayofweek)
    # Find the Sunday of the last week
    last_sunday = end_ts + pd.Timedelta(days=6 - end_ts.dayofweek)

    # Total weeks
    total_days = (last_sunday - first_monday).days + 1
    n_weeks = total_days // 7

    # Decide orientation based on duration
    # > 13 weeks (1 quarter): Horizontal (Weeks on X-axis)
    # <= 13 weeks: Vertical (Weeks on Y-axis)
    horizontal_layout = n_weeks > 13

    # Create the grid
    # Logic is easier if we build (n_weeks, 7) first then transpose if needed
    heatmap_data = np.full(
        (n_weeks, 7), np.nan
    )  # Fill with NaN initially to distinguish outside range if needed

    # Grid for project names if needed
    project_grid = np.full((n_weeks, 7), None, dtype=object)

    # Fill grid
    for date, duration in daily_series.items():
        # Calculate position relative to first_monday
        delta_days = (date - first_monday).days
        week_idx = delta_days // 7
        day_idx = delta_days % 7  # 0=Mon, 6=Sun

        if 0 <= week_idx < n_weeks:
            heatmap_data[week_idx, day_idx] = duration

            if color_by_project and not dominant_projects.empty:
                proj = dominant_projects.get(date)
                if proj:
                    project_grid[week_idx, day_idx] = proj

    # --- 4. Plotting ---
    if horizontal_layout:
        # Transpose data for horizontal layout: (7, n_weeks)
        heatmap_data = heatmap_data.T
        project_grid = project_grid.T

        # Wide figure: scaling height slightly up to ensure square cells fit
        # Width: ~0.2 inches per week
        # Height: ~4 inches constant (7 rows isn't much)
        fig_width = max(12, n_weeks * 0.25)
        fig_height = 4  # Increased from 3 to give room
        fig, ax = plt.subplots(figsize=(fig_width, fig_height))

        # Mask logic for horizontal
        mask = np.zeros_like(heatmap_data, dtype=bool)
        for w in range(n_weeks):
            for d in range(7):
                current_date = first_monday + pd.Timedelta(days=w * 7 + d)
                if current_date < start_ts or current_date > end_ts:
                    mask[d, w] = True
                elif np.isnan(heatmap_data[d, w]):
                    heatmap_data[d, w] = 0
    else:
        # Vertical layout: (n_weeks, 7)
        # Tall figure
        fig, ax = plt.subplots(figsize=(8, max(4, n_weeks * 0.4)))

        # Mask logic for vertical
        mask = np.zeros_like(heatmap_data, dtype=bool)
        for w in range(n_weeks):
            for d in range(7):
                current_date = first_monday + pd.Timedelta(days=w * 7 + d)
                if current_date < start_ts or current_date > end_ts:
                    mask[w, d] = True
                elif np.isnan(heatmap_data[w, d]):
                    heatmap_data[w, d] = 0

    # Store legend handles if using multiple colors
    legend_patches = []

    if color_by_project and not df.empty:
        # --- Multi-color Rendering ---

        # 1. Identify all unique projects/groups to assign colors
        unique_projects = sorted(df["display_group"].unique())
        proj_to_color = {
            p: generate_color(i, len(unique_projects))
            for i, p in enumerate(unique_projects)
        }

        # 2. Create an RGBA image array
        if horizontal_layout:
            rgba_grid = np.zeros((7, n_weeks, 4))
        else:
            rgba_grid = np.zeros((n_weeks, 7, 4))

        # Find max duration for normalization of alpha/intensity
        max_dur = np.nanmax(heatmap_data)
        if max_dur == 0:
            max_dur = 1.0

        if horizontal_layout:
            for d in range(7):
                for w in range(n_weeks):
                    if mask[d, w]:
                        rgba_grid[d, w] = (0.92, 0.93, 0.94, 1.0)
                    else:
                        duration = heatmap_data[d, w]
                        proj = project_grid[d, w]
                        if duration > 0 and proj:
                            r, g, b = proj_to_color.get(proj, (0, 128, 0))
                            intensity = min(duration / max_dur, 1.0)
                            alpha = 0.2 + (0.8 * intensity)
                            rgba_grid[d, w] = (r / 255.0, g / 255.0, b / 255.0, alpha)
                        else:
                            rgba_grid[d, w] = (0.92, 0.93, 0.94, 1.0)
        else:
            for w in range(n_weeks):
                for d in range(7):
                    if mask[w, d]:
                        rgba_grid[w, d] = (0.92, 0.93, 0.94, 1.0)
                    else:
                        duration = heatmap_data[w, d]
                        proj = project_grid[w, d]
                        if duration > 0 and proj:
                            r, g, b = proj_to_color.get(proj, (0, 128, 0))
                            intensity = min(duration / max_dur, 1.0)
                            alpha = 0.2 + (0.8 * intensity)
                            rgba_grid[w, d] = (r / 255.0, g / 255.0, b / 255.0, alpha)
                        else:
                            rgba_grid[w, d] = (0.92, 0.93, 0.94, 1.0)

        # Render using imshow (most reliable for pixel grids)
        # We set grid lines at integer boundaries to avoid crosshair artifacts

        if horizontal_layout:
            extent = [0, n_weeks, 7, 0]  # Left, Right, Bottom, Top
        else:
            extent = [0, 7, n_weeks, 0]

        mesh = ax.imshow(
            rgba_grid,
            aspect="equal",
            interpolation="nearest",
            origin="upper",
            extent=extent,
        )

        # Add white grid lines at INTEGER boundaries
        # This fixes the "crosshair" issue by placing lines between pixels, not through them
        grid_linewidth = 1 if horizontal_layout else 2

        if horizontal_layout:
            ax.set_xticks(np.arange(0, n_weeks + 1, 1), minor=True)
            ax.set_yticks(np.arange(0, 8, 1), minor=True)
        else:
            ax.set_xticks(np.arange(0, 8, 1), minor=True)
            ax.set_yticks(np.arange(0, n_weeks + 1, 1), minor=True)

        ax.grid(which="minor", color="white", linestyle="-", linewidth=grid_linewidth)
        ax.tick_params(which="minor", bottom=False, left=False)
        ax.grid(which="major", visible=False)

        # Create legend
        import matplotlib.patches as mpatches

        # Use a list to track added labels to avoid duplicates
        added_labels = set()
        legend_patches = []

        for proj, color_tuple in proj_to_color.items():
            if proj not in added_labels:
                r, g, b = color_tuple
                patch = mpatches.Patch(
                    color=(r / 255.0, g / 255.0, b / 255.0, 1.0), label=proj
                )
                legend_patches.append(patch)
                added_labels.add(proj)

        # Dynamic legend positioning
        if horizontal_layout and len(legend_patches) > 5:
            # Place at bottom if chart is wide and legend is long
            ax.legend(
                handles=legend_patches,
                loc="upper center",
                bbox_to_anchor=(0.5, -0.15),
                ncol=min(6, len(legend_patches)),  # Multi-column
                title="Dominant Project",
            )
        else:
            ax.legend(
                handles=legend_patches,
                bbox_to_anchor=(1.05, 1),
                loc="upper left",
                title="Dominant Project",
            )

        # Invert Y axis to match matrix coordinates (row 0 at top)
        ax.invert_yaxis()

        # Add white grid lines at INTEGER boundaries
        # This fixes the "crosshair" issue by placing lines between pixels, not through them
        grid_linewidth = 1 if horizontal_layout else 2

        if horizontal_layout:
            ax.set_xticks(np.arange(0, n_weeks + 1, 1), minor=True)
            ax.set_yticks(np.arange(0, 8, 1), minor=True)
        else:
            ax.set_xticks(np.arange(0, 8, 1), minor=True)
            ax.set_yticks(np.arange(0, n_weeks + 1, 1), minor=True)

        ax.grid(which="minor", color="white", linestyle="-", linewidth=grid_linewidth)
        ax.tick_params(which="minor", bottom=False, left=False)
        ax.grid(which="major", visible=False)

    else:
        # --- Standard Green Scale Rendering ---
        ax.grid(False)
        cmap = sns.light_palette("green", as_cmap=True)
        mesh = ax.pcolormesh(heatmap_data, cmap=cmap, edgecolors="white", linewidth=1)

        if mask.any():
            masked_data = np.ma.masked_where(~mask, mask)
            ax.pcolormesh(
                masked_data,
                cmap=mcolors.ListedColormap(["#f0f0f0"]),
                edgecolors="white",
                linewidth=1,
            )

        ax.invert_yaxis()

    # --- 5. Formatting ---
    ax.set_aspect("equal")
    for spine in ax.spines.values():
        spine.set_visible(False)

    if horizontal_layout:
        # Horizontal Labels
        # Y-axis: Days
        ax.set_yticks([0.5, 2.5, 4.5, 6.5])
        ax.set_yticklabels(["Mon", "Wed", "Fri", "Sun"])
        ax.tick_params(axis="y", length=0)

        # X-axis: Months
        month_labels = []
        month_ticks = []
        current = first_monday
        while current <= last_sunday:
            if current.day == 1 or current == first_monday:
                delta = (current - first_monday).days
                col = delta // 7
                month_name = current.strftime("%b")
                if not month_labels or (
                    month_labels[-1] != month_name and col > month_ticks[-1] + 2
                    if month_ticks
                    else True
                ):
                    month_ticks.append(col + 0.5)
                    month_labels.append(month_name)
            current += pd.Timedelta(days=1)

        ax.set_xticks(month_ticks)
        ax.set_xticklabels(month_labels)
        ax.tick_params(axis="x", length=0)

    else:
        # Vertical Labels (Schedule View)
        # X-axis: Days
        ax.set_xticks([0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5])
        ax.set_xticklabels(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
        ax.tick_params(axis="x", length=0)
        ax.xaxis.tick_top()

        # Y-axis: Weeks/Dates
        week_labels = []
        week_ticks = []
        show_dates = n_weeks < 20

        if show_dates:
            step = 1
            for i in range(0, n_weeks, step):
                monday_date = first_monday + pd.Timedelta(days=i * 7)
                label = monday_date.strftime("%b %d")
                week_ticks.append(i + 0.5)
                week_labels.append(label)
        else:
            for w in range(n_weeks):
                monday_date = first_monday + pd.Timedelta(days=w * 7)
                if w == 0 or monday_date.day <= 7:
                    prev_monday = monday_date - pd.Timedelta(days=7)
                    if w == 0 or monday_date.month != prev_monday.month:
                        week_ticks.append(w + 0.5)
                        week_labels.append(monday_date.strftime("%b"))

        ax.set_yticks(week_ticks)
        ax.set_yticklabels(week_labels)
        ax.tick_params(axis="y", length=0)

    # Title
    ax.set_title(
        title or "Activity Calendar", loc="left", fontsize=14, fontweight="bold", pad=20
    )

    # --- 6. Interaction (Hover Effect) ---
    annot = ax.annotate(
        "",
        xy=(0, 0),
        xytext=(10, 10),
        textcoords="offset points",
        bbox=dict(boxstyle="round", fc="white", ec="gray", alpha=0.9),
        arrowprops=dict(arrowstyle="->"),
    )
    annot.set_visible(False)

    def hover(event):
        if event.inaxes == ax:
            if event.xdata is None or event.ydata is None:
                return

            x_idx = int(event.xdata)
            y_idx = int(event.ydata)

            # Check bounds and Map coords to (week, day)
            if horizontal_layout:
                # X = Week, Y = Day
                if 0 <= x_idx < n_weeks and 0 <= y_idx < 7:
                    w_idx, d_idx = x_idx, y_idx
                else:
                    return
            else:
                # X = Day, Y = Week
                if 0 <= x_idx < 7 and 0 <= y_idx < n_weeks:
                    w_idx, d_idx = y_idx, x_idx
                else:
                    return

            # Calculate date
            target_date = first_monday + pd.Timedelta(days=w_idx * 7 + d_idx)

            # Get data (heatmap_data is already transposed if needed)
            val = heatmap_data[y_idx, x_idx]

            # Mask logic
            is_masked = False
            if target_date < start_ts or target_date > end_ts:
                is_masked = True

            if not is_masked and not np.isnan(val):
                # Get project label
                proj_label = ""
                # project_grid is also transposed if horizontal
                if color_by_project and project_grid[y_idx, x_idx]:
                    proj_label = f"\nMain: {project_grid[y_idx, x_idx]}"

                annot.xy = (x_idx + 0.5, y_idx + 0.5)
                text = (
                    f"{target_date.strftime('%Y-%m-%d')}\n{val:.2f} hours{proj_label}"
                )
                annot.set_text(text)
                annot.set_visible(True)
                fig.canvas.draw_idle()
                return

        if annot.get_visible():
            annot.set_visible(False)
            fig.canvas.draw_idle()

    fig.canvas.mpl_connect("motion_notify_event", hover)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        print(f"Chart saved to {save_path}")
    else:
        plt.show()

    plt.close()


def render_wordcloud_chart(
    sessions: List[Dict], title: Optional[str] = None, save_path: Optional[str] = None
):
    """Render a wordcloud from session notes."""
    try:
        from wordcloud import WordCloud
    except ImportError:
        print("Error: wordcloud library is required for wordcloud charts.")
        print("Install it with: pip install wordcloud")
        return

    if not sessions:
        print("No data to display.")
        return

    # Extract notes from sessions
    notes_text = " ".join([s.get("note", "") or "" for s in sessions if s.get("note")])

    if not notes_text.strip():
        print("No notes found in sessions.")
        return

    # Create wordcloud
    wordcloud = WordCloud(
        width=800,
        height=400,
        background_color="white",
        max_words=100,
        colormap="viridis",
    ).generate(notes_text)

    fig, ax = plt.subplots(figsize=(12, 6))
    ax.imshow(wordcloud, interpolation="bilinear")
    ax.axis("off")
    ax.set_title(
        title or "Session Notes Wordcloud", fontsize=14, fontweight="bold", pad=20
    )

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        print(f"Chart saved to {save_path}")
    else:
        plt.show()

    plt.close()


def render_heatmap(
    sessions: List[Dict], title: Optional[str] = None, save_path: Optional[str] = None
):
    """Render a calendar heatmap showing activity by day of week and hour."""
    if not sessions:
        print("No data to display.")
        return

    # Parse session data and aggregate by day of week and hour
    activity_data = {}

    for s in sessions:
        # Handle both compact and full formats
        start_time_str = s.get("start_time") or s.get("start", "")
        if not start_time_str:
            continue

        try:
            # Convert UTC time to local timezone
            start_time = parse_utc_to_local(start_time_str)
            if not start_time:
                continue

            day_of_week = start_time.weekday()  # 0 = Monday, 6 = Sunday
            hour = start_time.hour

            # Get duration in minutes
            duration_minutes = (
                s.get("duration_minutes") or s.get("duration") or s.get("dur", 0)
            )
            if duration_minutes is None:
                duration_minutes = 0

            key = (day_of_week, hour)
            activity_data[key] = activity_data.get(key, 0) + duration_minutes
        except (ValueError, AttributeError):
            # Skip invalid sessions
            continue

    # Create matrix for heatmap
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    hours = list(range(24))

    matrix = []
    for day in range(7):
        row = []
        for hour in hours:
            minutes = activity_data.get((day, hour), 0)
            row.append(minutes / 60.0)  # Convert to hours
        matrix.append(row)

    # Create heatmap
    fig, ax = plt.subplots(figsize=(14, 6))

    sns.heatmap(
        matrix,
        xticklabels=hours,
        yticklabels=days,
        cmap="YlOrRd",
        annot=False,
        fmt=".1f",
        cbar_kws={"label": "Hours"},
        ax=ax,
    )

    ax.set_xlabel("Hour of Day", fontsize=12)
    ax.set_ylabel("Day of Week", fontsize=12)
    ax.set_title(
        title or "Activity Heatmap (Hours by Day/Hour)", fontsize=14, fontweight="bold"
    )

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        print(f"Chart saved to {save_path}")
    else:
        plt.show()

    plt.close()
