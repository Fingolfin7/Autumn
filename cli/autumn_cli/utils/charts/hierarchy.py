"""Hierarchy chart types: treemap, sunburst."""

from typing import Dict, Optional
import matplotlib.pyplot as plt

from .core import generate_color


def render_treemap_chart(
    hierarchy_data: Dict, title: Optional[str] = None, save_path: Optional[str] = None
):
    """Render a treemap showing Context -> Project -> Subproject hierarchy."""
    try:
        import squarify
    except ImportError:
        print("Error: squarify library is required for treemap charts.")
        print("Install it with: pip install squarify")
        return

    if not hierarchy_data or "children" not in hierarchy_data:
        print("No hierarchy data to display.")
        return

    # Flatten hierarchy into rectangles with labels and values
    labels = []
    sizes = []
    colors = []

    color_idx = 0
    total_contexts = len(hierarchy_data.get("children", []))

    for context in hierarchy_data.get("children", []):
        context_name = context.get("name", "Unknown")
        context_color = generate_color(color_idx, max(total_contexts, 1))
        color_idx += 1

        for project in context.get("children", []):
            project_name = project.get("name", "Unknown")
            project_total = project.get("total_time", 0) / 60.0  # Convert to hours

            children = project.get("children", [])
            if children:
                for subproject in children:
                    sub_name = subproject.get("name", "Unknown")
                    sub_total = subproject.get("total_time", 0) / 60.0

                    if sub_total > 0:
                        labels.append(f"{context_name}\n{project_name}\n{sub_name}")
                        sizes.append(sub_total)
                        colors.append(tuple(c / 255.0 for c in context_color))
            else:
                if project_total > 0:
                    labels.append(f"{context_name}\n{project_name}")
                    sizes.append(project_total)
                    colors.append(tuple(c / 255.0 for c in context_color))

    if not sizes:
        print("No data with positive time to display.")
        return

    fig, ax = plt.subplots(figsize=(14, 10))

    squarify.plot(sizes=sizes, label=labels, color=colors, alpha=0.8, ax=ax, text_kwargs={"fontsize": 8})

    ax.set_title(title or "Time Distribution (Treemap)", fontsize=14, fontweight="bold")
    ax.axis("off")

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        print(f"Chart saved to {save_path}")
    else:
        plt.show()

    plt.close()


def render_sunburst_chart(
    hierarchy_data: Dict, title: Optional[str] = None, save_path: Optional[str] = None
):
    """Render a sunburst chart showing Context -> Project -> Subproject hierarchy."""
    if not hierarchy_data or "children" not in hierarchy_data:
        print("No hierarchy data to display.")
        return

    # Build data for sunburst (nested pie charts)
    # Level 0: Contexts, Level 1: Projects, Level 2: Subprojects

    context_names = []
    context_values = []
    context_colors = []

    project_names = []
    project_values = []
    project_colors = []

    subproject_names = []
    subproject_values = []
    subproject_colors = []

    color_idx = 0
    total_contexts = len(hierarchy_data.get("children", []))

    for context in hierarchy_data.get("children", []):
        context_name = context.get("name", "Unknown")
        base_color = generate_color(color_idx, max(total_contexts, 1))
        color_idx += 1

        context_total = 0

        for project in context.get("children", []):
            project_name = project.get("name", "Unknown")
            project_total = project.get("total_time", 0) / 60.0

            children = project.get("children", [])
            if children:
                for subproject in children:
                    sub_name = subproject.get("name", "Unknown")
                    sub_total = subproject.get("total_time", 0) / 60.0

                    if sub_total > 0:
                        subproject_names.append(sub_name)
                        subproject_values.append(sub_total)
                        # Lighter shade for subprojects
                        subproject_colors.append(tuple(min(1, c / 255.0 + 0.2) for c in base_color))

                project_sum = sum(sp.get("total_time", 0) for sp in children) / 60.0
                if project_sum > 0:
                    project_names.append(project_name)
                    project_values.append(project_sum)
                    project_colors.append(tuple(c / 255.0 for c in base_color))
                    context_total += project_sum
            else:
                if project_total > 0:
                    project_names.append(project_name)
                    project_values.append(project_total)
                    project_colors.append(tuple(c / 255.0 for c in base_color))
                    context_total += project_total
                    # Add placeholder for subproject ring
                    subproject_names.append("")
                    subproject_values.append(project_total)
                    subproject_colors.append(tuple(min(1, c / 255.0 + 0.2) for c in base_color))

        if context_total > 0:
            context_names.append(context_name)
            context_values.append(context_total)
            context_colors.append(tuple(max(0, c / 255.0 - 0.1) for c in base_color))

    if not context_values:
        print("No data with positive time to display.")
        return

    fig, ax = plt.subplots(figsize=(12, 12))

    # Inner ring: contexts
    ax.pie(
        context_values,
        labels=context_names,
        colors=context_colors,
        radius=0.5,
        wedgeprops=dict(width=0.3, edgecolor="white"),
        labeldistance=0.3,
        textprops={"fontsize": 9, "fontweight": "bold"},
    )

    # Middle ring: projects
    if project_values:
        ax.pie(
            project_values,
            labels=project_names,
            colors=project_colors,
            radius=0.8,
            wedgeprops=dict(width=0.3, edgecolor="white"),
            labeldistance=0.7,
            textprops={"fontsize": 8},
        )

    # Outer ring: subprojects
    if subproject_values and any(v > 0 for v in subproject_values):
        # Filter out empty labels
        filtered_names = [n if n else "" for n in subproject_names]
        ax.pie(
            subproject_values,
            labels=filtered_names,
            colors=subproject_colors,
            radius=1.1,
            wedgeprops=dict(width=0.3, edgecolor="white"),
            labeldistance=1.05,
            textprops={"fontsize": 7},
        )

    ax.set_title(title or "Time Distribution (Sunburst)", fontsize=14, fontweight="bold", pad=20)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        print(f"Chart saved to {save_path}")
    else:
        plt.show()

    plt.close()
