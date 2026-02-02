"""Aggregate chart types: pie, bar, status, context charts."""

from typing import List, Dict, Optional
import matplotlib.pyplot as plt

from .core import generate_color


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


def render_status_chart(
    status_data: List[Dict], title: Optional[str] = None, save_path: Optional[str] = None
):
    """Render a donut chart showing project breakdown by status."""
    if not status_data:
        print("No status data to display.")
        return

    # Fixed colors for each status
    status_colors = {
        "active": "#22c55e",      # Green
        "paused": "#a855f7",      # Purple/Magenta
        "complete": "#eab308",    # Yellow
        "archived": "#6b7280",    # Gray
    }

    labels = []
    sizes = []
    colors = []

    for item in status_data:
        status = item.get("status", "unknown")
        total_time = item.get("total_time", 0) / 60.0  # Convert to hours
        count = item.get("count", 0)

        if total_time > 0:
            labels.append(f"{status.title()}\n({count} projects)")
            sizes.append(total_time)
            colors.append(status_colors.get(status, "#94a3b8"))

    if not sizes:
        print("No data with positive time to display.")
        return

    fig, ax = plt.subplots(figsize=(10, 10))

    wedges, texts, autotexts = ax.pie(
        sizes,
        labels=labels,
        colors=colors,
        autopct=lambda pct: f"{pct:.1f}%\n({pct/100*sum(sizes):.1f}h)",
        startangle=90,
        wedgeprops=dict(width=0.5, edgecolor="white"),
        textprops={"fontsize": 10},
    )

    for autotext in autotexts:
        autotext.set_fontsize(9)
        autotext.set_fontweight("bold")

    ax.set_title(title or "Time by Project Status", fontsize=14, fontweight="bold")

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        print(f"Chart saved to {save_path}")
    else:
        plt.show()

    plt.close()


def render_context_chart(
    context_data: List[Dict], title: Optional[str] = None, save_path: Optional[str] = None
):
    """Render a horizontal bar chart comparing time across contexts."""
    if not context_data:
        print("No context data to display.")
        return

    # Sort by total time
    sorted_data = sorted(context_data, key=lambda x: x.get("total_time", 0))

    labels = [item.get("name", "Unknown") for item in sorted_data]
    values = [item.get("total_time", 0) / 60.0 for item in sorted_data]  # Convert to hours

    if not any(v > 0 for v in values):
        print("No data with positive time to display.")
        return

    colors = [tuple(c / 255.0 for c in generate_color(i, len(sorted_data))) for i in range(len(sorted_data))]

    fig, ax = plt.subplots(figsize=(10, max(6, len(sorted_data) * 0.6)))

    bars = ax.barh(labels, values, color=colors)

    # Add value labels on bars
    for bar, val in zip(bars, values):
        width = bar.get_width()
        ax.text(
            width,
            bar.get_y() + bar.get_height() / 2,
            f" {val:.1f}h",
            ha="left",
            va="center",
            fontweight="bold",
        )

    ax.set_xlabel("Total Time (hours)", fontsize=12)
    ax.set_title(title or "Time by Context", fontsize=14, fontweight="bold")
    ax.grid(axis="x", alpha=0.3)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        print(f"Chart saved to {save_path}")
    else:
        plt.show()

    plt.close()
