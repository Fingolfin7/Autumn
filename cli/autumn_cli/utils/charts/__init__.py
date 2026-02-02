"""Chart rendering utilities using matplotlib and seaborn.

This package provides various chart types for visualizing time tracking data.
"""

from .core import generate_color
from .aggregates import (
    render_pie_chart,
    render_bar_chart,
    render_status_chart,
    render_context_chart,
)
from .timeseries import (
    render_scatter_chart,
    render_line_chart,
    render_calendar_chart,
    render_heatmap,
    render_stacked_area_chart,
    render_cumulative_chart,
)
from .hierarchy import (
    render_treemap_chart,
    render_sunburst_chart,
)
from .comparison import (
    render_radar_chart,
    render_histogram_chart,
    render_tag_bubble_chart,
)
from .text import render_wordcloud_chart

__all__ = [
    # Core
    "generate_color",
    # Aggregates
    "render_pie_chart",
    "render_bar_chart",
    "render_status_chart",
    "render_context_chart",
    # Timeseries
    "render_scatter_chart",
    "render_line_chart",
    "render_calendar_chart",
    "render_heatmap",
    "render_stacked_area_chart",
    "render_cumulative_chart",
    # Hierarchy
    "render_treemap_chart",
    "render_sunburst_chart",
    # Comparison
    "render_radar_chart",
    "render_histogram_chart",
    "render_tag_bubble_chart",
    # Text
    "render_wordcloud_chart",
]
