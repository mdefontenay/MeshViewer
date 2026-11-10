"""Small NumPy helpers on surface meshes, shared by Export and the Info section."""
from __future__ import annotations

from contextlib import contextmanager

import numpy as np
from vtkmodules.util.numpy_support import vtk_to_numpy
from vtkmodules.vtkCommonCore import vtkSMPTools

vtkSMPTools.SetBackend("STDThread")     # VTK filters (normals, cuts…) on every CPU core
SMALL_PART = 20_000                     # cells; below, threads cost more than they save


@contextmanager
def one_thread(small=True):
    """Run VTK filters on one thread inside the block (when `small`). Starting the worker
    threads costs ~1 ms per filter run: nothing on a big part, most of the time on
    hundreds of small ones."""
    if small:
        vtkSMPTools.SetBackend("Sequential")
    try:
        yield
    finally:
        vtkSMPTools.SetBackend("STDThread")


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


def bare(poly, points=None):
    """A new surface with the points and faces of `poly` only (no data arrays).

    VTK shares the structure itself (copy_structure), with no NumPy views in between:
    building it from views of another surface's arrays (PolyData(part.points,
    faces=part.faces)) let VTK keep pointers into NumPy memory that could be freed —
    rare, random crashes (moving a section plot quickly). `points`: new
    coordinates for the same faces (copied)."""
    import pyvista as pv
    out = pv.PolyData()
    out.copy_structure(poly)
    if points is not None:
        out.points = np.array(points, dtype=float)
    return out
