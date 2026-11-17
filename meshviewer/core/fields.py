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


# Contours colour maps: key -> stops low -> high. Rainbow first: the usual CFD default
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


def _rgb_rows(stops):
    return np.array([[int(c[i:i + 2], 16) for i in (1, 3, 5)] for c in stops], float)


def ramp_t(values, lo, hi, log=False):
    """Where values sit on lo..hi, 0…1 (clamped; NaN stays NaN). log: by powers of ten
    (lo > 0; values at or below zero go to 0)."""
    v = np.asarray(values, dtype=float)
    if log and lo > 0 and hi > lo:
        with np.errstate(divide="ignore", invalid="ignore"):
            lv = np.where(v > 0, np.log10(np.where(v > 0, v, 1.0)), -np.inf)
        a, b = np.log10(lo), np.log10(hi)
        t = np.clip((np.where(np.isneginf(lv), a, lv) - a) / ((b - a) or 1.0), 0.0, 1.0)
    else:
        t = np.clip((v - lo) / ((hi - lo) or 1.0), 0.0, 1.0)
    return np.where(np.isfinite(v), t, np.nan)


def band_colors(stops, n):
    """The n colors of a stepped scale: the map's two ends and n − 2 between."""
    cols = _rgb_rows(stops)
    xs = np.linspace(0.0, 1.0, len(stops))
    at = np.linspace(0.0, 1.0, n) if n > 1 else np.array([0.5])
    return np.stack([np.interp(at, xs, cols[:, k]) for k in range(3)], axis=1)


def ramp_table(stops, edges=None, n=1024):
    """(n, 3) uint8: the colors from 0 to 1 — smooth (edges None), or in bands between
    the positions `edges` (0…1, both ends included), one color each (`band_colors`).
    The 3D view's lookup table and the color bar both read it."""
    t = (np.arange(n) + 0.5) / n
    if edges is None or len(edges) < 2:
        cols = _rgb_rows(stops)
        xs = np.linspace(0.0, 1.0, len(stops))
        out = np.stack([np.interp(t, xs, cols[:, k]) for k in range(3)], axis=1)
    else:
        e = np.asarray(edges, dtype=float)
        band = np.clip(np.searchsorted(e, t, side="right") - 1, 0, len(e) - 2)
        out = band_colors(stops, len(e) - 1)[band]
    return out.round().astype(np.uint8)


def ramp_rgb(values, lo, hi, stops, log=False, edges=None):
    """Colour (n, 3) uint8 for values on lo..hi (clamped); NaN -> grey. log: by powers of
    ten (lo > 0; values at or below zero take the lowest colour). edges: in bands
    (`ramp_table`)."""
    t = ramp_t(values, lo, hi, log)
    if edges is None or len(edges) < 2:
        cols = _rgb_rows(stops)
        xs = np.linspace(0.0, 1.0, len(stops))
        out = np.stack([np.interp(np.nan_to_num(t), xs, cols[:, k]) for k in range(3)], axis=1)
    else:
        e = np.asarray(edges, dtype=float)
        band = np.clip(np.searchsorted(e, np.nan_to_num(t), side="right") - 1, 0, len(e) - 2)
        out = band_colors(stops, len(e) - 1)[band]
    out[~np.isfinite(t)] = [int(NAN_COLOR[i:i + 2], 16) for i in (1, 3, 5)]
    return out.round().astype(np.uint8)


# ---- the color bar's ticks -----------------------------------------------------------------
TICKS = (2, 15)                       # the fewest and most ticks on the color bar


_LOG_STEPS = ((1,), (1, 3), (1, 2, 5), (1, 2, 3, 4, 5, 6, 7, 8, 9))


def _round_log(lo, hi, count):
    """Round values (1 · 2 · 5 × 10ⁿ…) strictly inside lo..hi, as many as fit in
    count − 2 (the ends are ticks too): the densest set that fits, else every k-th
    decade."""
    a, b = np.log10(lo), np.log10(hi)
    room = max(count - 2, 0)
    best = []
    for steps in _LOG_STEPS:
        vals = [m * 10.0 ** k for k in range(int(np.floor(a)), int(np.ceil(b)) + 1)
                for m in steps]
        vals = [v for v in vals if lo * (1 + 1e-9) < v < hi * (1 - 1e-9)]
        if len(vals) > room:
            if not best and vals:                  # decades alone too many: every k-th
                k = int(np.ceil(len(vals) / max(room, 1)))
                best = vals[::k][:room]
            break
        best = vals
    span = b - a
    return [v for v in best if 0.04 < (np.log10(v) - a) / span < 0.96]


def ticks(lo, hi, count=5, log=False, tick_log=False):
    """[(position 0…1 up the bar, value)] from lo to hi, ends included.
    Tick spacing Linear (tick_log False): exactly `count` ticks evenly up the bar, each
    with the value at its place (geometric on a log color scale).
    Log (tick_log, lo > 0): spaced logarithmically across the range — on a linear color
    scale `count` values evenly in log10, each where it falls (crowded near the bottom);
    on a log color scale the round values (1 · 2 · 5 × 10ⁿ…, at most `count`) where they
    fall, as a log axis is marked (evenly in log10 would sit where Linear puts them)."""
    count = int(np.clip(round(count), *TICKS))
    log = log and lo > 0 and hi > lo
    if tick_log and lo > 0 and hi > lo:
        if log:
            inside = _round_log(lo, hi, count)
            if inside or count == 2:
                values = np.array([lo, *inside, hi], dtype=float)
                return [(float(p), float(v))
                        for p, v in zip(ramp_t(values, lo, hi, True), values)]
        values = 10 ** np.linspace(np.log10(lo), np.log10(hi), count)
        values[0], values[-1] = lo, hi                  # exact ends (no rounding)
        pos = ramp_t(values, lo, hi, log)
        return [(float(p), float(v)) for p, v in zip(pos, values)]
    pos = np.linspace(0.0, 1.0, count)
    if log:
        values = 10 ** (np.log10(lo) + pos * (np.log10(hi) - np.log10(lo)))
    else:
        values = lo + pos * (hi - lo)
    values[0], values[-1] = lo, hi
    return [(float(p), float(v)) for p, v in zip(pos, values)]


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
