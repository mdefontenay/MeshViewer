"""Colours and sizes of the 3D view, shared by the scene's modules."""
from __future__ import annotations

from functools import lru_cache

import pyvista as pv


PART_COLORS = [   # no black / very dark colours: they hide the shading
    "#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4",
    "#46f0f0", "#f032e6", "#bcf60c", "#008080", "#9a6324",
    "#fabebe", "#aaffc3", "#e6beff", "#ffd8b1", "#a9a9a9",
    "#ffe119", "#808000", "#5fa8ff", "#ff8c69", "#c49c94",
]
FEATURE_ANGLE = 30.0        # degrees; sharper creases are drawn as feature edges
SELECT_COLOR = "#0a84ff"    # fallback; the system accent colour is used when known
HEAVY_OUTLINE = 300_000     # triangles; a bigger selection's outline hides while moving
CLICK_TOLERANCE_PX = 4      # a press+release closer than this is a click, not a drag
AXIS_FONT_DEFAULT = 16       # grid label points (Appearance slider: 10 = original size … 28)
EDGE_WIDTHS = {"thin": 1.0, "medium": 1.5, "thick": 2.0}   # feature edge lines, pixels
AXES_MODES = ("off", "axes", "grid", "both")               # Display ▸ Axes

# Viewport colours (background gradient bottom -> top, grid, feature edges)
THEMES = {
    False: dict(bg="#e8ebf0", bg_top="#ffffff", grid="#7a7a80", edge="#111111",    # light
                cut_fill="#d9dde4"),                        # cut volume mesh
    True:  dict(bg="#1c1c1e", bg_top="#3a3a3e", grid="#9a9aa2", edge="#0a0a0a",    # dark
                cut_fill="#6b6e76"),
}


@lru_cache(maxsize=None)
def rgb(color):
    """"#rrggbb" or a colour name as (r, g, b), 0–1."""
    return pv.Color(color).float_rgb


def is_dark_color(hex_color):
    r, g, b = rgb(hex_color)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b < 0.5


@lru_cache(maxsize=None)
def lighter(hex_color, f=0.30):
    r, g, b = rgb(hex_color)
    return (r + (1 - r) * f, g + (1 - g) * f, b + (1 - b) * f)
