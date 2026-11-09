"""Cell quality of a mesh (the sidebar's "Cell quality"). No Qt.

    values = compute(dataset, "skew")       # one number per cell
    stats  = summarize(values, "skew", threshold)

Works on volume cells (tetra, pyramid, prism, hexa) and, for files without
them, on surface cells (triangles, quads). The numbers come from VTK's Verdict
library (vtkMeshQuality) except the aspect ratio, computed here the same way
for every cell type (longest edge / shortest edge).

Measures (`bad` = which side of the threshold is bad):
    skew      Skewness, equiangle      0 ideal … 1 degenerate        bad if >
    aspect    Aspect ratio, edges      1 ideal … large = stretched    bad if >
    jacobian  Scaled Jacobian          1 ideal … ≤ 0 inverted/folded  bad if <
    size      Volume (area for surfaces); ≤ 0 = inverted cell        bad if ≤
"""
from __future__ import annotations

import numpy as np
import pyvista as pv
from vtkmodules.util.numpy_support import vtk_to_numpy
from vtkmodules.vtkFiltersVerdict import vtkMeshQuality

METRICS = {
    "skew": dict(label="Skewness", verdict="EquiangleSkew", bad=">", default=0.9, log=False,
                 tip="Equiangle skewness: 0 = ideal shape, 1 = flat / degenerate.\n"
                     "Above about 0.9 usually hurts the solver."),
    "aspect": dict(label="Aspect ratio", verdict=None, bad=">", default=100.0, log=True,
                   tip="Longest edge / shortest edge (1 = ideal).\n"
                       "Boundary-layer prisms are stretched on purpose."),
    "jacobian": dict(label="Scaled Jacobian", verdict="ScaledJacobian", bad="<", default=0.2,
                     log=False, tip="1 = ideal, 0 = degenerate, below 0 = inverted or folded."),
    "size": dict(label="Volume", verdict="Volume", bad="<=", default=0.0, log=True,
                 tip="Cell volume (area for surface meshes). 0 or below = inverted cell."),
}
TYPES = ("Tet", "Pyramid", "Wedge", "Hex", "Triangle", "Quad")

# Edges of each linear cell, in VTK's local node numbers
_EDGES = {
    pv.CellType.TETRA: [(0, 1), (1, 2), (2, 0), (0, 3), (1, 3), (2, 3)],
    pv.CellType.PYRAMID: [(0, 1), (1, 2), (2, 3), (3, 0), (0, 4), (1, 4), (2, 4), (3, 4)],
    pv.CellType.WEDGE: [(0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3), (0, 3), (1, 4), (2, 5)],
    pv.CellType.HEXAHEDRON: [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4),
                             (0, 4), (1, 5), (2, 6), (3, 7)],
    pv.CellType.TRIANGLE: [(0, 1), (1, 2), (2, 0)],
    pv.CellType.QUAD: [(0, 1), (1, 2), (2, 3), (3, 0)],
}


def label(key, surface=False):
    return "Area" if key == "size" and surface else METRICS[key]["label"]


def _verdict(ds, measure, surface):
    q = vtkMeshQuality()
    q.SetInputData(ds)
    if surface and measure == "Volume":
        measure = "Area"
    for t in TYPES:
        setter = getattr(q, f"Set{t}QualityMeasureTo{measure}", None)
        if setter is not None:
            setter()
    q.Update()
    return vtk_to_numpy(q.GetOutput().GetCellData().GetArray("Quality")).astype(float)


def _edge_ratio(ds):
    """Longest / shortest edge of every cell (NaN for other cell types)."""
    grid = ds if isinstance(ds, pv.UnstructuredGrid) else ds.cast_to_unstructured_grid()
    out = np.full(grid.n_cells, np.nan)
    pts = np.asarray(grid.points, dtype=float)
    types = np.asarray(grid.celltypes)
    for ctype, conn in grid.cells_dict.items():
        edges = _EDGES.get(ctype)
        if edges is None:
            continue
        a, b = np.array(edges).T
        length = np.linalg.norm(pts[conn[:, a]] - pts[conn[:, b]], axis=2)
        with np.errstate(divide="ignore", invalid="ignore"):
            out[types == ctype] = length.max(axis=1) / length.min(axis=1)
    return out


def compute(ds, key):
    """One value per cell of `ds` (pv.UnstructuredGrid of volume cells, or the
    merged boundary surface for files without volume cells)."""
    surface = isinstance(ds, pv.PolyData)
    if key == "aspect":
        return _edge_ratio(ds)
    return _verdict(ds, METRICS[key]["verdict"], surface)


def is_bad(values, key, threshold):
    op = METRICS[key]["bad"]
    with np.errstate(invalid="ignore"):
        if op == ">":
            return values > threshold
        if op == "<":
            return values < threshold
        return values <= threshold


def summarize(values, key, threshold, bins=48):
    """Numbers for the panel: min / mean / max, bad cells, histogram."""
    ok = np.isfinite(values)
    v = values[ok]
    bad = is_bad(values, key, threshold) & ok
    out = {"n": int(values.size), "n_bad": int(bad.sum()),
           "min": float(v.min()) if v.size else None,
           "max": float(v.max()) if v.size else None,
           "mean": float(v.mean()) if v.size else None}
    h = display_values(values, key)
    h = h[np.isfinite(h)]
    if h.size:
        lo, hi = float(h.min()), float(h.max())
        if hi - lo <= 1e-9 * max(1.0, abs(lo)):       # all (nearly) the same: one bar, centred
            pad = abs(lo) * 0.05 or 0.05
            lo, hi = lo - pad, hi + pad
        counts, edges = np.histogram(h, bins=bins, range=(lo, hi))
        out.update(hist=counts, edges=edges)
    return out


def display_values(values, key):
    """What the histogram and the colours use: log10 for wide-range measures
    (aspect ratio, volume — only positive values)."""
    if not METRICS[key]["log"]:
        return values
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(values > 0, np.log10(np.where(values > 0, values, 1.0)), np.nan)


# ---- colours ------------------------------------------------------------------------
# Quality measures: good (green) -> fair (yellow) -> bad (red). Volume / area is a
# size, not a quality: small -> large in blue -> teal -> yellow; inverted = red.
_QUALITY = np.array([[52, 199, 89], [255, 204, 0], [255, 69, 58]], dtype=float)
_SIZE = np.array([[64, 92, 230], [32, 170, 160], [250, 220, 60]], dtype=float)
INVALID = (255, 69, 58)


def _ramp(stops, t):
    t = np.clip(np.asarray(t, dtype=float), 0, 1) * 2
    i = np.minimum(t.astype(int), 1)
    f = (t - i)[:, None]
    return stops[i] * (1 - f) + stops[i + 1] * f


def position(h, key, threshold, lo, hi):
    """0..1 along the colour scale for display values h. Quality measures: 0 at
    the ideal value, 1 (red) at the "bad" threshold and beyond. Volume / area:
    smallest .. largest cell (lo..hi, display values)."""
    h = np.asarray(h, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        if key == "skew":
            t = h / max(threshold, 1e-9)
        elif key == "aspect":
            t = h / max(np.log10(max(threshold, 1.0001)), 1e-9)
        elif key == "jacobian":
            t = (1 - h) / max(1 - threshold, 1e-9)
        else:
            t = (h - lo) / (hi - lo) if hi > lo else np.zeros(h.shape)
    return np.clip(t, 0, 1)


def colors(values, key, threshold, lo, hi):
    """(n, 3) uint8 colour per cell, the same scale as the histogram bars.
    Cells without a value (inverted, degenerate) are red."""
    h = display_values(values, key)
    ok = np.isfinite(h)
    out = np.empty((len(h), 3))
    out[~ok] = INVALID
    stops = _SIZE if key == "size" else _QUALITY
    out[ok] = _ramp(stops, position(h[ok], key, threshold, lo, hi))
    return out.astype(np.uint8)


def bar_colors(edges, key, threshold):
    """Colour of each histogram bar (at its centre), as (r, g, b) tuples."""
    mid = (edges[:-1] + edges[1:]) / 2
    stops = _SIZE if key == "size" else _QUALITY
    rgb = _ramp(stops, position(mid, key, threshold, edges[0], edges[-1]))
    return [tuple(int(c) for c in x) for x in rgb]
