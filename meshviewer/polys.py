"""Small NumPy helpers on surface meshes, shared by Export and the Info section."""
from __future__ import annotations

import numpy as np
from vtkmodules.util.numpy_support import vtk_to_numpy


def faces_by_size(poly):
    """{n vertices: (m, n) int array} for the polygons of a surface (vectorised)."""
    polys = poly.GetPolys()
    if polys is None or polys.GetNumberOfCells() == 0:
        return {}
    off = vtk_to_numpy(polys.GetOffsetsArray()).astype(np.int64)
    conn = vtk_to_numpy(polys.GetConnectivityArray()).astype(np.int64)
    n, start = np.diff(off), off[:-1]
    return {int(k): conn[start[n == k][:, None] + np.arange(k)] for k in np.unique(n)}


def edge_lengths(poly):
    """(shortest, longest) polygon edge of a surface, or (None, None)."""
    pts = np.asarray(poly.points, dtype=float)
    lo, hi = np.inf, -np.inf
    for k, f in faces_by_size(poly).items():
        a, b = f, np.roll(f, -1, axis=1)
        length = np.linalg.norm(pts[a] - pts[b], axis=2)
        lo, hi = min(lo, float(length.min())), max(hi, float(length.max()))
    return (lo, hi) if np.isfinite(lo) else (None, None)
