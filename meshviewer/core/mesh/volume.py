"""Volume cells of a mesh file, for the section's "Show cut mesh".

The boundary readers (cgns.py, ugrid.py) only build the surfaces. Their
read_volume(path) functions read the 3D cells (tetrahedra, pyramids, prisms,
hexahedra) on demand — the first time the cut mesh is shown — and hand them
here to become one VTK grid.
"""
from __future__ import annotations

import numpy as np
import pyvista as pv

TETRA, PYRAMID, WEDGE, HEXA = (pv.CellType.TETRA, pv.CellType.PYRAMID,
                               pv.CellType.WEDGE, pv.CellType.HEXAHEDRON)
NAMES = {TETRA: "tetra", PYRAMID: "pyramid", WEDGE: "prism", HEXA: "hexa",
         pv.CellType.POLYHEDRON: "polyhedron"}


def build_grid(points, blocks):
    """points: (n, 3); blocks: {cell type: list of (m, k) arrays of 0-based node
    indices}. Returns a pv.UnstructuredGrid, or None when there are no cells."""
    cells = {ct: np.vstack(parts).astype(np.int64)
             for ct, parts in blocks.items() if parts and sum(len(p) for p in parts)}
    if not cells:
        return None
    pts = np.asarray(points, dtype=np.float64)
    return pv.UnstructuredGrid(_outward(cells, pts), pts)


def _outward(cells, pts):
    """formats disagree on node order — e.g. CGNS prisms are ordered
    the other way round from VTK's — which makes VTK see the cells inside out
    (negative volume). When most cells of a type are inside out, the whole type
    uses the opposite convention: reorder it. A few inverted cells among many
    good ones are real mesh errors and are left as they are (Cell quality shows them)."""
    from meshviewer.core.quality import compute
    from meshviewer.core.transform import MIRROR_ORDER          # turns a cell the other way out
    out = {}
    for ctype, conn in cells.items():
        one = pv.UnstructuredGrid({ctype: conn}, pts)
        vol = compute(one, "size")
        if np.count_nonzero(vol < 0) > vol.size / 2 and ctype in MIRROR_ORDER:
            conn = conn[:, MIRROR_ORDER[ctype]]
            print(f"  {NAMES.get(ctype, ctype)}: node order reversed (opposite convention)")
        out[ctype] = conn
    return out


def orient_each(blocks, pts):
    """Turn every inside-out cell the right way (cells rebuilt from polyhedra each
    have their own orientation)."""
    from meshviewer.core.quality import compute
    from meshviewer.core.transform import MIRROR_ORDER
    out = {}
    for ctype, parts in blocks.items():
        conn = np.vstack(parts).astype(np.int64)
        if ctype in MIRROR_ORDER and len(conn):
            vol = compute(pv.UnstructuredGrid({ctype: conn}, pts), "size")
            bad = vol < 0
            conn[bad] = conn[bad][:, MIRROR_ORDER[ctype]]
        out[ctype] = [conn]
    return out


def describe(grid) -> str:
    """'1,234,567 cells (tetra 1,000,000 · prism 234,567)' for the log."""
    types, counts = np.unique(grid.celltypes, return_counts=True)
    parts = " · ".join(f"{NAMES.get(t, t)} {c:,}" for t, c in zip(types, counts))
    return f"{grid.n_cells:,} cells ({parts})"


# ---- polyhedra: split for the tools that work on ordinary cells ----------------------------
SIZES = {TETRA: 4, PYRAMID: 5, WEDGE: 6, HEXA: 8}


def _arrays(ca):
    from vtkmodules.util.numpy_support import vtk_to_numpy
    return (np.array(vtk_to_numpy(ca.GetOffsetsArray()), dtype=np.int64),
            np.array(vtk_to_numpy(ca.GetConnectivityArray()), dtype=np.int64))


def _ranges(off, which):
    """Positions of the items of rows `which` of a cell array with offsets `off`,
    and the row (0 … len(which) - 1) each belongs to."""
    n = off[which + 1] - off[which]
    row = np.repeat(np.arange(len(which)), n)
    return np.repeat(off[which], n) + np.arange(n.sum()) - np.repeat(np.cumsum(n) - n, n), row


def split_polyhedra(grid):
    """Polyhedral cells (VTK_POLYHEDRON) -> a pyramid or tetra per face, to the cell's
    center, for Cell Quality and Section; the fields go with them (a cell's value to
    each piece, the center's: the cell's). Returns (grid, polyhedra split, carry):
    carry(another grid like `grid`) -> ({point arrays}, {cell arrays}) as on the split
    grid (another time step's fields)."""
    types = np.asarray(grid.celltypes)
    poly = np.flatnonzero(types == pv.CellType.POLYHEDRON)
    if not len(poly):
        return grid, 0, lambda g: _arrays_of(g, None, None)
    coff, cconn = _arrays(grid.GetCells())
    foff, fconn = _arrays(grid.GetPolyhedronFaces())
    loff, lconn = _arrays(grid.GetPolyhedronFaceLocations())
    pts = np.array(grid.points, dtype=np.float64)
    blocks, src = {}, {}

    def add(ctype, conn, cells):
        blocks.setdefault(ctype, []).append(conn)
        src.setdefault(ctype, []).append(cells)
    for ctype, k in SIZES.items():                   # the ordinary cells, as they are
        ids = np.flatnonzero(types == ctype)
        if len(ids):
            add(ctype, cconn[coff[ids][:, None] + np.arange(k)], ids)
    at, row = _ranges(coff, poly)                    # each polyhedron's center: a new point
    n = np.bincount(row, minlength=len(poly))
    center = np.add.reduceat(pts[cconn[at]], np.cumsum(n) - n) / n[:, None]
    apex = len(pts) + np.arange(len(poly))
    at, row = _ranges(loff, poly)                    # their faces
    faces, apex, owner = lconn[at], apex[row], poly[row]
    size = foff[faces + 1] - foff[faces]
    for s in np.unique(size):
        f, a, c = faces[size == s], apex[size == s], owner[size == s]
        nodes = fconn[foff[f][:, None] + np.arange(s)]
        if s == 4:
            add(PYRAMID, np.column_stack([nodes, a]), c)
            continue
        for j in range(1, s - 1):                    # a triangle fan, a tetra each
            add(TETRA, np.column_stack([nodes[:, [0, j, j + 1]], a]), c)
    pts = np.vstack([pts, center])
    cells = orient_each(blocks, pts)
    out = pv.UnstructuredGrid({t: np.vstack(b) for t, b in cells.items()}, pts)
    order = np.concatenate([np.concatenate(src[t]) for t in cells])
    carry = lambda g: _arrays_of(g, order, poly)                 # noqa: E731
    point, cell = carry(grid)
    for k, a in point.items():
        out.point_data[k] = a
    for k, a in cell.items():
        out.cell_data[k] = a
    return out, len(poly), carry


def _arrays_of(grid, order, poly):
    """({point arrays}, {cell arrays}) of `grid`, as on its split copy (order: each new
    cell's source cell; poly: the polyhedra, whose centers were added as points)."""
    cell = {k: np.asarray(grid.cell_data[k]) for k in grid.cell_data.keys()}
    point = {k: np.asarray(grid.point_data[k]) for k in grid.point_data.keys()}
    if order is None:
        return point, cell
    out_point = {}
    for k, a in point.items():
        mid = cell[k][poly] if k in cell else np.zeros((len(poly),) + a.shape[1:], a.dtype)
        out_point[k] = np.concatenate([a, mid.astype(a.dtype)])
    return out_point, {k: a[order] for k, a in cell.items()}
