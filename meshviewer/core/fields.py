"""Values and colours of fields on surfaces: y+ colours, colour scales, ramps.
Pure NumPy."""
from __future__ import annotations

import numpy as np

# arrays that readers / VTK / PyVista add to surfaces: never solution fields
INTERNAL_PREFIXES = ("vtk", "pyvista", "__")
INTERNAL_NAMES = {"face_id", "Normals", "TextureCoordinates", "Texture Coordinates",
                  "RGB", "RGBA", "Colors", "colors"}
from meshviewer.core.field_kinds import SPEED   # noqa: E402  |u, v, w| (u, v, w in the file)


YPLUS_STOPS = ((0.0, "#0a84ff"), (1.0, "#30b350"), (2.0, "#ff9f0a"), (3.0, "#ff453a"))


NAN_COLOR = "#8e8e93"                 # nodes without a measured first cell


def yplus_rgb(ratio):
    """Colour (n, 3) uint8 for y+ / target values (NaN -> grey)."""
    r = np.asarray(ratio, dtype=float)
    xs = [s for s, _ in YPLUS_STOPS]
    cols = np.array([[int(c[i:i + 2], 16) for i in (1, 3, 5)] for _, c in YPLUS_STOPS], float)
    rc = np.clip(np.nan_to_num(r, nan=0.0), xs[0], xs[-1])
    out = np.stack([np.interp(rc, xs, cols[:, k]) for k in range(3)], axis=1)
    out[~np.isfinite(r)] = [int(NAN_COLOR[i:i + 2], 16) for i in (1, 3, 5)]
    return out.astype(np.uint8)


SEQUENTIAL = ("#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b")


# Results colour maps: key -> stops low -> high. Rainbow first: the usual CFD default
# (Fluent, STAR-CCM+…). The menu shows the colours, not names.
COLORMAPS = {
    "rainbow": ("#0000ff", "#0080ff", "#00ffff", "#00ff80", "#00ff00",
                "#80ff00", "#ffff00", "#ff8000", "#ff0000"),
    "coolwarm": ("#3b4cc0", "#6788ee", "#9abbff", "#c9d7f0", "#f7f7f7", "#f6cbb5",
                 "#f49a7b", "#de604d", "#b40426"),
    "thermal": ("#0d0887", "#5302a3", "#8b0aa5", "#b83289", "#db5c68", "#f48849",
                "#febc2a", "#f0f921"),
    "grey": ("#1a1a1a", "#4d4d4d", "#808080", "#b3b3b3", "#e6e6e6"),
    "blues": SEQUENTIAL,
}
DEFAULT_MAP = "rainbow"


def ramp_rgb(values, lo, hi, stops, log=False):
    """Colour (n, 3) uint8 for values on lo..hi (clamped); NaN -> grey. log: by powers of
    ten (lo > 0; values at or below zero take the lowest colour)."""
    v = np.asarray(values, dtype=float)
    if log and lo > 0 and hi > lo:
        with np.errstate(divide="ignore", invalid="ignore"):
            lv = np.where(v > 0, np.log10(np.where(v > 0, v, 1.0)), -np.inf)
        a, b = np.log10(lo), np.log10(hi)
        t = np.clip((np.nan_to_num(lv, nan=a, neginf=a) - a) / ((b - a) or 1.0), 0.0, 1.0)
    else:
        t = np.clip((np.nan_to_num(v, nan=lo) - lo) / ((hi - lo) or 1.0), 0.0, 1.0)
    cols = np.array([[int(c[i:i + 2], 16) for i in (1, 3, 5)] for c in stops], float)
    xs = np.linspace(0.0, 1.0, len(stops))
    out = np.stack([np.interp(t, xs, cols[:, k]) for k in range(3)], axis=1)
    out[~np.isfinite(v)] = [int(NAN_COLOR[i:i + 2], 16) for i in (1, 3, 5)]
    return out.astype(np.uint8)


def field_values(poly, name):
    """(values, "point" | "cell") of a field on a boundary, or (None, None)."""
    if name in poly.point_data:
        return np.asarray(poly.point_data[name], dtype=float), "point"
    if name in poly.cell_data:
        return np.asarray(poly.cell_data[name], dtype=float), "cell"
    return None, None


def solution_fields(parts):
    """Names of the solution fields on the parts ({name: PolyData}): floating-point
    arrays with one value per node or face, not the ids and normals VTK adds.
    Ends with SPEED when u, v, w are there."""
    names = []
    for part in parts.values():
        for data in (part.point_data, part.cell_data):
            for k in data.keys():
                if k in names or k in INTERNAL_NAMES or k.startswith(INTERNAL_PREFIXES):
                    continue
                a = np.asarray(data[k])
                if a.ndim == 1 and np.issubdtype(a.dtype, np.floating):
                    names.append(k)
    if {"u", "v", "w"} <= set(names):
        names.append(SPEED)
    return names


def lighter_rgb(rgb, f=0.30):
    """uint8 RGB rows moved f of the way to white (the selected-part tint)."""
    rgb = np.asarray(rgb, dtype=float)
    return (rgb + (255.0 - rgb) * f).round().astype(np.uint8)


# ---- sharp changes (F15): the gradient of a field over the surface -------------------------
def gradient_magnitude(poly, vals):
    """|∇f| at each node of a surface (per unit length, along the surface), from node
    values: the least-squares gradient of each face, averaged at its nodes."""
    from meshviewer.core.polys import bare
    surf = bare(poly)
    surf.point_data["f"] = np.array(vals, dtype=float)
    g = surf.compute_derivative(scalars="f", gradient="g", preference="point")
    return np.linalg.norm(np.asarray(g.point_data["g"], dtype=float), axis=1)
