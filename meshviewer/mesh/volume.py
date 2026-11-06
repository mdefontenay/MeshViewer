"""NEW (v2.19): volume cells of a mesh file, for the section's "Show cut mesh".

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


def build_grid(points, blocks):
    """points: (n, 3); blocks: {cell type: list of (m, k) arrays of 0-based node
    indices}. Returns a pv.UnstructuredGrid, or None when there are no cells."""
    cells = {ct: np.vstack(parts).astype(np.int64)
             for ct, parts in blocks.items() if parts and sum(len(p) for p in parts)}
    if not cells:
        return None
    return pv.UnstructuredGrid(cells, np.asarray(points, dtype=np.float64))


def describe(grid) -> str:
    """'1,234,567 cells (tetra 1,000,000 · prism 234,567)' for the log."""
    names = {TETRA: "tetra", PYRAMID: "pyramid", WEDGE: "prism", HEXA: "hexa"}
    types, counts = np.unique(grid.celltypes, return_counts=True)
    parts = " · ".join(f"{names.get(t, t)} {c:,}" for t, c in zip(types, counts))
    return f"{grid.n_cells:,} cells ({parts})"
