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

            session_points.append(
                {
                    "date": end_time,
                    "duration": duration_hours,
                    "project": project,
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

            data_list.append({"date": date_val, "duration": duration_hours})

        except (ValueError, AttributeError):
            continue

    if not data_list and not (start_date and end_date):
        print("No data to display and no date range specified.")
        return

    # Create DataFrame
    df = pd.DataFrame(data_list)
    if not df.empty:
        # Sum duration by date
        daily_series = df.groupby("date")["duration"].sum()
    else:
        daily_series = pd.Series(dtype=float)

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

    # Create the grid
    # TRANSPOSED: (n_weeks, 7)
    heatmap_data = np.full(
        (n_weeks, 7), np.nan
    )  # Fill with NaN initially to distinguish outside range if needed

    # Fill grid
    for date, duration in daily_series.items():
        # Calculate position relative to first_monday
        delta_days = (date - first_monday).days
        week_idx = delta_days // 7
        day_idx = delta_days % 7  # 0=Mon, 6=Sun

        if 0 <= week_idx < n_weeks:
            # TRANSPOSED: [week_idx, day_idx]
            heatmap_data[week_idx, day_idx] = duration

    # --- 4. Plotting ---
    # Aspect ratio adjustment: Tall if many weeks, wide if few
    # We want roughly square cells.
    # Height = n_weeks * scale, Width = 7 * scale
    fig, ax = plt.subplots(figsize=(8, max(4, n_weeks * 0.4)))

    # Create a custom colormap (white to green)
    cmap = sns.light_palette("green", as_cmap=True)

    # Let's make a mask for out-of-range days
    mask = np.zeros_like(heatmap_data, dtype=bool)

    # Iterate through the grid coordinates to set mask for dates outside [start_ts, end_ts]
    for w in range(n_weeks):
        for d in range(7):
            current_date = first_monday + pd.Timedelta(days=w * 7 + d)
            if current_date < start_ts or current_date > end_ts:
                # TRANSPOSED
                mask[w, d] = True
            elif np.isnan(heatmap_data[w, d]):
                # Should not happen given reindex fill_value=0, but just in case
                heatmap_data[w, d] = 0

    # Plot
    # We need to invert Y axis so 1st Week is top
    mesh = ax.pcolormesh(heatmap_data, cmap=cmap, edgecolors="white", linewidth=1)

    # Masked areas (outside range) - plot as grey/transparent
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

    # Remove all spines
    for spine in ax.spines.values():
        spine.set_visible(False)

    # X-axis labels (Days) - Mon to Sun
    ax.set_xticks([0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5])
    ax.set_xticklabels(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
    ax.tick_params(axis="x", length=0)
    # Move x-axis labels to top if preferred? Standard is bottom. Let's keep bottom for now.
    ax.xaxis.tick_top()  # Actually top is better for calendar headers

    # Y-axis labels (Dates)
    # We want to label the weeks.
    # Label the Monday of each week on the left.
    week_labels = []
    week_ticks = []

    # Decide label granularity
    # If range is small (< 12 weeks), show date of each Monday
    show_dates = n_weeks < 20

    if show_dates:
        # Show date for every week
        step = 1
        for i in range(0, n_weeks, step):
            # Date of the Monday for this row
            monday_date = first_monday + pd.Timedelta(days=i * 7)
            # Use concise date format "Jan 1"
            label = monday_date.strftime("%b %d")
            week_ticks.append(i + 0.5)
            week_labels.append(label)
    else:
        # Show Month labels at start of each month
        # We iterate rows (weeks)
        for w in range(n_weeks):
            monday_date = first_monday + pd.Timedelta(days=w * 7)
            # Check if this week starts a new month or is first week
            if w == 0 or monday_date.day <= 7:  # Approximate "start of month" logic
                # Better: check if month changed from previous week
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
            # Get integer coordinates (column, row)
            # pcolormesh coordinates: x=[0..7], y=[0..n_weeks] (inverted)
            if event.xdata is None or event.ydata is None:
                return

            x_idx = int(event.xdata)  # Day (0-6)
            y_idx = int(event.ydata)  # Week (0-N)

            # Check bounds
            if 0 <= x_idx < 7 and 0 <= y_idx < n_weeks:
                # Calculate date
                # TRANSPOSED: x=Day, y=Week
                target_date = first_monday + pd.Timedelta(days=y_idx * 7 + x_idx)

                # Check if we have data for this date
                val = heatmap_data[y_idx, x_idx]

                # Check if it's a valid date (not masked out)
                if not mask[y_idx, x_idx] and not np.isnan(val):
                    annot.xy = (x_idx + 0.5, y_idx + 0.5)
                    text = f"{target_date.strftime('%Y-%m-%d')}\n{val:.2f} hours"
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
