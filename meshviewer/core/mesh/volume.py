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
NAMES = {TETRA: "tetra", PYRAMID: "pyramid", WEDGE: "prism", HEXA: "hexa"}


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
