"""Chart rendering utilities using matplotlib and seaborn."""

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import seaborn as sns

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


def render_pie_chart(data: List[Dict], title: Optional[str] = None, save_path: Optional[str] = None):
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


def render_bar_chart(data: List[Dict], title: Optional[str] = None, save_path: Optional[str] = None):
    """Render a horizontal bar chart from project/subproject totals."""
    if not data:
        print("No data to display.")
        return
    
    # Sort by value for better visualization
    sorted_data = sorted(data, key=lambda x: x["total_time"])
    
    labels = [item["name"] for item in sorted_data]
    values = [item["total_time"] / 60.0 for item in sorted_data]  # Convert minutes to hours
    
    colors = [generate_color(i, len(sorted_data)) for i in range(len(sorted_data))]
    
    fig, ax = plt.subplots(figsize=(10, max(6, len(data) * 0.5)))
    
    bars = ax.barh(labels, values, color=[tuple(c / 255.0 for c in color) for color in colors])
    
    # Add value labels on bars
    for i, (bar, val) in enumerate(zip(bars, values)):
        width = bar.get_width()
        ax.text(width, bar.get_y() + bar.get_height() / 2,
                f" {val:.2f}h",
                ha="left", va="center", fontweight="bold")
    
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


def render_scatter_chart(sessions: List[Dict], title: Optional[str] = None, save_path: Optional[str] = None):
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
            start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
            end_time = datetime.fromisoformat(end_time_str.replace("Z", "+00:00"))
            
            # Calculate duration - prefer provided duration if available, otherwise compute
            duration_minutes = s.get("duration_minutes") or s.get("duration") or s.get("dur")
            if duration_minutes is not None:
                duration_hours = duration_minutes / 60.0
            else:
                duration_hours = (end_time - start_time).total_seconds() / 3600.0
            
            project = s.get("project") or s.get("p", "Unknown")
            
            session_points.append({
                "date": end_time,
                "duration": duration_hours,
                "project": project,
            })
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


def render_calendar_chart(sessions: List[Dict], title: Optional[str] = None, save_path: Optional[str] = None):
    """Render a calendar heatmap (GitHub contribution style) showing activity by date."""
    if not sessions:
        print("No data to display.")
        return
    
    # Aggregate data by date
    date_totals = {}
    for s in sessions:
        start_time_str = s.get("start_time") or s.get("start", "")
        end_time_str = s.get("end_time") or s.get("end", "")
        
        if not start_time_str or not end_time_str:
            continue
        
        try:
            start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
            end_time = datetime.fromisoformat(end_time_str.replace("Z", "+00:00"))
            
            # Get date as YYYY-MM-DD string
            date_key = start_time.date().isoformat()
            
            # Calculate duration in hours
            duration_minutes = s.get("duration_minutes") or s.get("duration") or s.get("dur")
            if duration_minutes is not None:
                duration_hours = duration_minutes / 60.0
            else:
                duration_hours = (end_time - start_time).total_seconds() / 3600.0
            
            date_totals[date_key] = date_totals.get(date_key, 0) + duration_hours
        except (ValueError, AttributeError):
            continue
    
    if not date_totals:
        print("No valid session data to display.")
        return
    
    # Get date range
    dates = sorted(date_totals.keys())
    if not dates:
        print("No data to display.")
        return
    
    first_date = datetime.fromisoformat(dates[0]).date()
    last_date = datetime.fromisoformat(dates[-1]).date()
    
    # Create a simple calendar visualization using scatter plot
    # X-axis: week of year, Y-axis: day of week
    fig, ax = plt.subplots(figsize=(14, 8))
    
    # Prepare data points
    max_duration = max(date_totals.values()) if date_totals.values() else 1.0
    
    for date_str, duration in date_totals.items():
        date_obj = datetime.fromisoformat(date_str).date()
        # Week number and day of week (0=Monday, 6=Sunday)
        week_num = date_obj.isocalendar()[1]
        day_of_week = date_obj.weekday()  # 0=Monday, 6=Sunday
        
        # Normalize intensity (0 to 1)
        intensity = min(duration / max_duration, 1.0) if max_duration > 0 else 0
        
        # Color based on intensity (green gradient like GitHub)
        color = (0, intensity, 0, intensity * 0.8 + 0.2)  # RGBA: green with varying alpha
        
        ax.scatter(week_num, day_of_week, s=200, c=[color], alpha=intensity * 0.8 + 0.2)
    
    # Set labels
    ax.set_ylabel("Day of Week", fontsize=12)
    ax.set_xlabel("Week of Year", fontsize=12)
    ax.set_title(title or "Projects Calendar", fontsize=14, fontweight="bold")
    ax.set_yticks(range(7))
    ax.set_yticklabels(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
    ax.invert_yaxis()  # Monday at top
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        print(f"Chart saved to {save_path}")
    else:
        plt.show()
    
    plt.close()


def render_wordcloud_chart(sessions: List[Dict], title: Optional[str] = None, save_path: Optional[str] = None):
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
    notes_text = " ".join([
        s.get("note", "") or ""
        for s in sessions
        if s.get("note")
    ])
    
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
    ax.set_title(title or "Session Notes Wordcloud", fontsize=14, fontweight="bold", pad=20)
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        print(f"Chart saved to {save_path}")
    else:
        plt.show()
    
    plt.close()


def render_heatmap(sessions: List[Dict], title: Optional[str] = None, save_path: Optional[str] = None):
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
            start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
            day_of_week = start_time.weekday()  # 0 = Monday, 6 = Sunday
            hour = start_time.hour
            
            # Get duration in minutes
            duration_minutes = s.get("duration_minutes") or s.get("duration") or s.get("dur", 0)
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
    ax.set_title(title or "Activity Heatmap (Hours by Day/Hour)", fontsize=14, fontweight="bold")
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        print(f"Chart saved to {save_path}")
    else:
        plt.show()
    
    plt.close()
