"""2D OpenFOAM cases: one cell thick between `empty` patches (core/mesh/openfoam.py).

The cells are the empty faces on one of the two planes, with the values of the cells
behind them (OWNER: each empty face's cell, from the owner list); the other patches
become the edges they leave on that plane, with their faces' values. Both are turned so
the plane is XY (z = 0), all facing +Z.

The geometry never changes from one time step to another: `two_d` also gives the map
from what the reader gives (the cells, the patches) to the flat parts' arrays
(`flat_arrays`): another step's fields without building the parts again.
"""
from __future__ import annotations

import numpy as np
import pyvista as pv

ZONE = "internalMesh"                               # the 2D cells' part
OWNER = "__owner"                                   # an empty face's cell


def _cells(poly):
    """(offsets (n + 1), node ids) of the polygons of a surface (copies)."""
    from vtkmodules.util.numpy_support import vtk_to_numpy
    ca = poly.GetPolys()
    return (np.array(vtk_to_numpy(ca.GetOffsetsArray()), dtype=np.int64),
            np.array(vtk_to_numpy(ca.GetConnectivityArray()), dtype=np.int64))


def _plane_axes(n):
    """Two in-plane directions (u, v): the other two axes when the plane is square to
    one, so a usual 2D case keeps its x and y."""
    k = int(np.argmax(np.abs(n)))
    if abs(n[k]) > 1 - 1e-9:
        u, v = np.eye(3)[[i for i in range(3) if i != k]]
        return u, v
    u = np.cross(n, np.eye(3)[int(np.argmin(np.abs(n)))])
    u /= np.linalg.norm(u)
    return u, np.cross(n, u)


def two_d(patches, types, cells=None):
    """(the flat parts, their map) when the case is one cell thick between `empty`
    patches, else (None, None). cells: gives the cells with their fields (None: none)."""
    empty = [n for n in patches if types.get(n) == "empty"]
    if not empty:
        return None, None
    sheets = [patches[n] for n in empty]
    p0 = np.asarray(sheets[0].get_cell(0).points)
    n = np.zeros(3)
    for a, b in zip(p0, np.roll(p0, -1, axis=0)):    # the first face's (Newell) normal
        n += np.cross(a, b)
    if not np.linalg.norm(n):
        return None, None
    n /= np.linalg.norm(n)
    every = np.vstack([np.asarray(p.points) for p in patches.values()])
    d = every @ n
    lo, hi = float(d.min()), float(d.max())
    tol = 1e-6 * max(float(np.ptp(every, axis=0).max()), 1e-30)
    if hi - lo <= tol or not np.all(np.minimum(abs(d - lo), abs(d - hi)) <= tol):
        return None, None
    u, v = _plane_axes(n)
    flat = lambda pts: np.column_stack([pts @ u, pts @ v, np.zeros(len(pts))])  # noqa: E731
    zone, zmap = _zone(sheets, n, lo, tol, flat, cells() if cells is not None else None)
    out, lmap = {ZONE: zone}, {}
    for name, poly in patches.items():
        if name in empty:
            continue
        lines, m = _edges(poly, n, lo, tol, flat)
        if lines is not None:
            key = _unique(name, out)
            out[key] = lines
            lmap[key] = (name, *m)
    return out, ({"zone": zmap, "lines": lmap} if zmap is not None else None)


def flat_arrays(fmap, patches, grid):
    """{flat part: ({point arrays}, {cell arrays})} of another step, from the reader's
    patches and cells (their fields only) through the map `two_d` gave."""
    owner, node, cell_of, counts = fmap["zone"]
    cell = {k: np.asarray(grid.cell_data[k])[owner] for k in grid.cell_data.keys()} \
        if grid is not None else {}
    point = {k: np.bincount(node, weights=np.asarray(v, dtype=float)[cell_of],
                            minlength=len(counts)) / counts for k, v in cell.items()}
    out = {ZONE: (point, cell)}
    for name, (patch, two, pid) in fmap["lines"].items():
        p = patches.get(patch)
        if p is not None:
            out[name] = ({k: np.asarray(p.point_data[k])[pid] for k in p.point_data.keys()},
                         {k: np.asarray(p.cell_data[k])[two] for k in p.cell_data.keys()
                          if k != OWNER})
    return out


def _zone(sheets, n, lo, tol, flat, grid=None):
    """The empty faces lying on the plane d = lo, flat, all facing +Z; with the fields of
    the cells behind them (grid), on the faces and at the nodes."""
    pts_all, faces_all, owners, base = [], [], [], 0
    for s in sheets:
        off, conn = _cells(s)
        if not len(conn):
            continue
        on = np.abs(np.asarray(s.points) @ n - lo) <= tol
        sizes = np.diff(off)
        keep = np.minimum.reduceat(on[conn], off[:-1]).astype(bool) & (sizes > 0)
        c = conn[keep[np.repeat(np.arange(len(sizes)), sizes)]]
        new_off = np.concatenate([[0], np.cumsum(sizes[keep])])
        pts = flat(np.asarray(s.points))
        c = _facing_up(pts, new_off, c)
        faces_all.append(np.insert(c + base, new_off[:-1], np.diff(new_off)))
        pts_all.append(pts)
        if OWNER in s.cell_data:
            owners.append(np.asarray(s.cell_data[OWNER])[keep])
        base += len(pts)
    zone = pv.PolyData(np.vstack(pts_all), faces=np.concatenate(faces_all)).clean()
    owner = np.concatenate(owners) if owners else None
    if owner is None or len(owner) != zone.n_cells:
        return zone, None
    off, conn = _cells(zone)                           # its nodes: each the mean of its cells
    cell_of = np.repeat(np.arange(zone.n_cells), np.diff(off))
    counts = np.maximum(np.bincount(conn, minlength=zone.n_points), 1)
    zmap = (owner, conn, cell_of, counts)
    if grid is not None:                               # the cells' fields, on it
        point, cell = flat_arrays({"zone": zmap, "lines": {}}, {}, grid)[ZONE]
        for name, a in cell.items():
            zone.cell_data[name] = a
        for name, a in point.items():
            zone.point_data[name] = a
    return zone, zmap


def _facing_up(pts, off, conn):
    """conn with each polygon that runs clockwise in XY turned round."""
    if not len(conn):
        return conn
    idx = np.arange(len(conn))
    nxt = idx + 1
    nxt[off[1:] - 1] = off[:-1]
    x, y = pts[conn, 0], pts[conn, 1]
    area = np.add.reduceat(x * y[nxt] - x[nxt] * y, off[:-1])
    fid = np.repeat(np.arange(len(off) - 1), np.diff(off))
    rev = off[:-1][fid] + off[1:][fid] - 1 - idx          # the same face, backwards
    return np.where((area < 0)[fid], conn[rev], conn)


def _edges(poly, n, lo, tol, flat):
    """Each face of a patch across the two planes -> the edge it leaves on d = lo, with
    the face's values (and the patch's at the nodes)."""
    off, conn = _cells(poly)
    if not len(conn):
        return None, None
    on = np.abs(np.asarray(poly.points) @ n - lo) <= tol
    fid = np.repeat(np.arange(len(off) - 1), np.diff(off))
    m = on[conn]
    two = np.bincount(fid[m], minlength=len(off) - 1) == 2
    sel = m & two[fid]
    segs = conn[sel].reshape(-1, 2)
    if not len(segs):
        return None, None
    lines = pv.PolyData(flat(np.asarray(poly.points)),
                        lines=np.column_stack([np.full(len(segs), 2), segs]).ravel())
    lines.point_data["__pid"] = np.arange(poly.n_points)
    lines = lines.clean()
    pid = np.asarray(lines.point_data.pop("__pid"), dtype=np.int64)
    for k in poly.point_data.keys():
        lines.point_data[k] = np.asarray(poly.point_data[k])[pid]
    for k in poly.cell_data.keys():
        if k != OWNER:
            lines.cell_data[k] = np.asarray(poly.cell_data[k])[two]
    return lines, (two, pid)


def _unique(name, taken):
    k, out = 2, name
    while out in taken:
        out = f"{name} {k}"
        k += 1
    return out
