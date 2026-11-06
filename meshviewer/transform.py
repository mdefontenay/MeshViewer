"""Rotate / mirror / move a whole model (Edit section). No Qt in here.

An edit state is (R, t): new point = R @ original point + t.
  R  3×3 — 90° turns and mirrors only swap coordinates and flip signs (entries
     exactly 0 / ±1); v2.27: any angle (cos / sin entries)
  t  translation (floats)
The geometry is always recomputed from the ORIGINAL points with the total
(R, t), so edits never pile up rounding errors, Undo / Reset are exact, and the
surfaces and the volume cells get bit-identical node coordinates (needed to
match them up again on export).

v2.23: rotations and mirrors. v2.24: translation, pivot (origin or model
centre), undo history.
"""
from __future__ import annotations

import numpy as np
import pyvista as pv

# +90° about each axis (right-hand rule: thumb along +axis)
_R90 = {"x": [[1, 0, 0], [0, 0, -1], [0, 1, 0]],
        "y": [[0, 0, 1], [0, 1, 0], [-1, 0, 0]],
        "z": [[0, -1, 0], [1, 0, 0], [0, 0, 1]]}

# Node order that keeps a mirrored cell from turning inside out.
_MIRROR_ORDER = {pv.CellType.TETRA: [0, 2, 1, 3],
                 pv.CellType.PYRAMID: [0, 3, 2, 1, 4],
                 pv.CellType.WEDGE: [0, 2, 1, 3, 5, 4],
                 pv.CellType.HEXAHEDRON: [0, 3, 2, 1, 4, 7, 6, 5]}


def identity():
    return np.eye(3)


def _snap(r):
    """Entries within 1e-12 of 0 / ±1 made exact (e.g. after +30° then −30°)."""
    r = np.array(r, dtype=float)
    for v in (0.0, 1.0, -1.0):
        r[np.abs(r - v) < 1e-12] = v
    return r + 0.0                                  # no "-0.0"


def rotation(axis: str, degrees: float):
    """Turn about the x / y / z axis (right-hand rule). Multiples of 90° are exact."""
    d = float(degrees) % 360.0
    if d % 90.0 == 0.0:
        turns = int(d // 90)
        return np.linalg.matrix_power(np.array(_R90[axis], dtype=float), turns) + 0.0
    a = np.deg2rad(d)
    c, s = np.cos(a), np.sin(a)
    i, j = {"x": (1, 2), "y": (2, 0), "z": (0, 1)}[axis]
    r = identity()
    r[i, i], r[i, j], r[j, i], r[j, j] = c, -s, s, c
    return r


def mirror(axis: str):
    """Mirror across the plane normal to `axis` (e.g. "x": x -> -x)."""
    m = identity()
    m["xyz".index(axis), "xyz".index(axis)] = -1
    return m


def about(r, pivot):
    """(R, t) that turns / mirrors about `pivot` instead of the origin."""
    p = np.asarray(pivot, dtype=float)
    r = np.asarray(r, dtype=float)
    return r, p - r @ p


def compose(edit, state):
    """Apply `edit` (R_e, t_e) after `state` (R, t)."""
    (re, te), (r, t) = edit, state
    re = np.asarray(re, dtype=float)
    return (_snap(re @ np.asarray(r, dtype=float)),
            re @ np.asarray(t, dtype=float) + np.asarray(te, dtype=float))


def delta(old, new):
    """(R_d, t_d) taking geometry from state `old` to state `new`."""
    (r0, t0), (r1, t1) = old, new
    rd = _snap(np.asarray(r1, dtype=float) @ np.asarray(r0, dtype=float).T)   # inverse = transpose
    return rd, np.asarray(t1, dtype=float) - rd @ np.asarray(t0, dtype=float)


def is_identity(r, t=(0.0, 0.0, 0.0)) -> bool:
    return bool(np.array_equal(np.asarray(r), identity()) and not np.any(np.asarray(t)))


def flips(r) -> bool:
    """Mirrors (odd number of them) turn surfaces inside out."""
    return round(float(np.linalg.det(r))) < 0


def move_points(points, r, t=(0.0, 0.0, 0.0)):
    pts = np.asarray(points)
    out = pts @ np.asarray(r).T
    if np.any(np.asarray(t)):
        out = out + np.asarray(t, dtype=float)
    return (out + 0.0).astype(pts.dtype, copy=False)       # +0.0: no "-0.0"


def set_surface(poly: pv.PolyData, original_points, r, t, flipped_now: bool):
    """In place: points = R·original + t; flip faces if the mirror state changes.
    Returns the new "flipped" state."""
    poly.points = move_points(original_points, r, t)
    for name in ("Normals", "Normals_"):
        poly.point_data.pop(name, None)
        poly.cell_data.pop(name, None)
    want = flips(r)
    if want != flipped_now:
        poly.flip_faces(inplace=True)
    return want


def grid_from(original: pv.UnstructuredGrid, r, t=(0.0, 0.0, 0.0)) -> pv.UnstructuredGrid:
    """A moved copy of the ORIGINAL volume grid (mirrored cells reordered)."""
    if is_identity(r, t):
        return original
    pts = move_points(original.points, r, t)
    if not flips(r):
        # a NEW grid (a shallow copy would share — and overwrite — the file's points)
        return pv.UnstructuredGrid(original.cells, original.celltypes, pts)
    cells = {}
    for ctype, conn in original.cells_dict.items():
        order = _MIRROR_ORDER.get(ctype)
        cells[ctype] = conn[:, order] if order is not None else conn
    return pv.UnstructuredGrid(cells, pts)
