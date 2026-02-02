"""Comparison chart types: radar, histogram, bubble."""

from typing import List, Dict, Optional
import matplotlib.pyplot as plt
import numpy as np

from .core import generate_color


def render_histogram_chart(
    sessions: List[Dict], title: Optional[str] = None, save_path: Optional[str] = None
):
    """Render a histogram showing distribution of session lengths."""
    if not sessions:
        print("No data to display.")
        return

    # Extract session durations
    durations = []

    for s in sessions:
        duration_minutes = (
            s.get("duration_minutes") or s.get("duration") or s.get("dur")
        )
        if duration_minutes is not None and duration_minutes > 0:
            durations.append(duration_minutes)

    if not durations:
        print("No valid session durations to display.")
        return

    fig, ax = plt.subplots(figsize=(12, 8))

    # Define bins (in minutes): 0-15, 15-30, 30-60, 60-120, 120+
    bins = [0, 15, 30, 60, 120, 180, 240, max(max(durations) + 1, 300)]
    bin_labels = ["0-15m", "15-30m", "30m-1h", "1-2h", "2-3h", "3-4h", "4h+"]

    counts, edges, patches = ax.hist(
        durations,
        bins=bins,
        color="steelblue",
        edgecolor="white",
        alpha=0.8,
    )

    # Add count labels on top of bars
    for count, patch in zip(counts, patches):
        if count > 0:
            ax.text(
                patch.get_x() + patch.get_width() / 2,
                patch.get_height(),
                f"{int(count)}",
                ha="center",
                va="bottom",
                fontweight="bold",
            )

    # Set x-tick labels
    ax.set_xticks([(edges[i] + edges[i + 1]) / 2 for i in range(len(edges) - 1)])
    ax.set_xticklabels(bin_labels[: len(edges) - 1])

    ax.set_xlabel("Session Duration", fontsize=12)
    ax.set_ylabel("Number of Sessions", fontsize=12)
    ax.set_title(title or "Session Length Distribution", fontsize=14, fontweight="bold")
    ax.grid(axis="y", alpha=0.3)

    # Add stats annotation
    avg_duration = sum(durations) / len(durations)
    median_duration = sorted(durations)[len(durations) // 2]
    stats_text = f"Sessions: {len(durations)}\nAvg: {avg_duration:.0f}m\nMedian: {median_duration:.0f}m"
    ax.annotate(
        stats_text,
        xy=(0.95, 0.95),
        xycoords="axes fraction",
        ha="right",
        va="top",
        fontsize=10,
        bbox=dict(boxstyle="round", fc="white", ec="gray", alpha=0.9),
    )

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        print(f"Chart saved to {save_path}")
    else:
        plt.show()

    plt.close()


def render_radar_chart(
    projects_data: List[Dict], title: Optional[str] = None, save_path: Optional[str] = None
):
    """Render a radar/spider chart comparing top projects across dimensions."""
    if not projects_data:
        print("No project data to display.")
        return

    # Sort by total time and take top 5
    sorted_projects = sorted(projects_data, key=lambda x: x.get("total_time", 0), reverse=True)[:5]

    if not sorted_projects:
        print("No projects to display.")
        return

    # Dimensions: total_time, session_count, avg_session_length, subproject_count, recency
    dimensions = ["Total Time", "Sessions", "Avg Length", "Subprojects", "Recency"]
    num_dims = len(dimensions)

    # Normalize values to 0-1 scale
    max_time = max(p.get("total_time", 1) for p in sorted_projects) or 1
    max_sessions = max(p.get("session_count", 1) for p in sorted_projects) or 1
    max_subprojects = max(p.get("subproject_count", 1) for p in sorted_projects) or 1
    max_days = max(p.get("days_since_update", 1) for p in sorted_projects) or 1

    # Calculate angles for radar
    angles = [n / float(num_dims) * 2 * np.pi for n in range(num_dims)]
    angles += angles[:1]  # Close the polygon

    fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(polar=True))

    for i, project in enumerate(sorted_projects):
        name = project.get("name", "Unknown")

        # Normalize values
        time_norm = project.get("total_time", 0) / max_time
        sessions_norm = project.get("session_count", 0) / max_sessions

        # Calculate average session length
        total_time = project.get("total_time", 0)
        session_count = project.get("session_count", 1) or 1
        avg_length = total_time / session_count
        max_avg = max_time / max(1, max_sessions / len(sorted_projects))
        avg_norm = min(avg_length / max(max_avg, 1), 1)

        subprojects_norm = project.get("subproject_count", 0) / max_subprojects

        # Recency: lower days = higher score
        days = project.get("days_since_update", max_days)
        recency_norm = 1 - (days / max_days) if max_days > 0 else 1

        values = [time_norm, sessions_norm, avg_norm, subprojects_norm, recency_norm]
        values += values[:1]  # Close the polygon

        color = tuple(c / 255.0 for c in generate_color(i, len(sorted_projects)))

        ax.plot(angles, values, "o-", linewidth=2, label=name, color=color)
        ax.fill(angles, values, alpha=0.25, color=color)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(dimensions)
    ax.set_ylim(0, 1)

    ax.set_title(title or "Project Comparison (Radar)", fontsize=14, fontweight="bold", pad=20)
    ax.legend(bbox_to_anchor=(1.15, 1), loc="upper left")

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        print(f"Chart saved to {save_path}")
    else:
        plt.show()

    plt.close()


def render_tag_bubble_chart(
    tag_data: List[Dict], title: Optional[str] = None, save_path: Optional[str] = None
):
    """Render a bubble chart where X=project count, Y=total hours, size=avg time per project."""
    if not tag_data:
        print("No tag data to display.")
        return

    # Filter tags with data
    valid_tags = [t for t in tag_data if t.get("total_time", 0) > 0]

    if not valid_tags:
        print("No tags with tracked time to display.")
        return

    fig, ax = plt.subplots(figsize=(12, 10))

    x_values = []  # project_count
    y_values = []  # total_time (hours)
    sizes = []     # avg time per project
    labels = []
    colors = []

    for i, tag in enumerate(valid_tags):
        name = tag.get("name", "Unknown")
        project_count = tag.get("project_count", 0)
        total_hours = tag.get("total_time", 0) / 60.0

        # Average time per project for bubble size
        avg_per_project = total_hours / max(project_count, 1)

        x_values.append(project_count)
        y_values.append(total_hours)
        sizes.append(max(avg_per_project * 50, 100))  # Scale for visibility
        labels.append(name)

        # Use tag color if available, otherwise generate
        tag_color = tag.get("color")
        if tag_color:
            colors.append(tag_color)
        else:
            color = generate_color(i, len(valid_tags))
            colors.append(tuple(c / 255.0 for c in color))

    scatter = ax.scatter(x_values, y_values, s=sizes, c=colors, alpha=0.6, edgecolors="white", linewidth=2)

    # Add labels
    for i, label in enumerate(labels):
        ax.annotate(
            label,
            (x_values[i], y_values[i]),
            textcoords="offset points",
            xytext=(0, 10),
            ha="center",
            fontsize=9,
            fontweight="bold",
        )

    ax.set_xlabel("Number of Projects", fontsize=12)
    ax.set_ylabel("Total Hours", fontsize=12)
    ax.set_title(title or "Tags Overview (Bubble size = avg hours/project)", fontsize=14, fontweight="bold")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        print(f"Chart saved to {save_path}")
    else:
        plt.show()

    plt.close()
