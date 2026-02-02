"""Core utilities and shared configuration for chart rendering."""

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.colors as mcolors
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
import seaborn as sns
import pandas as pd
import numpy as np
import colorsys

# Import our timezone-aware parser
from ..formatters import parse_utc_to_local

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
    hue = (index * 360.0) / max(total, 1)
    # Old code used HSL with s=1.0, l=0.7.
    # In colorsys.hls_to_rgb: (h, l, s)
    r, g, b = colorsys.hls_to_rgb(hue / 360.0, 0.7, 1.0)
    return int(r * 255), int(g * 255), int(b * 255)


# Re-export commonly used imports for convenience
__all__ = [
    "plt",
    "mdates",
    "mcolors",
    "datetime",
    "timedelta",
    "List",
    "Dict",
    "Optional",
    "Any",
    "sns",
    "pd",
    "np",
    "parse_utc_to_local",
    "generate_color",
]
