"""Polyhedral cells (CGNS NGON_n faces + NFACE_n cells) -> ordinary VTK cells.

Most CFD meshes written as polyhedra are really tetrahedra, pyramids, prisms and
hexahedra. Each cell is recognised from its faces (4 triangles = tetra, 1 quad + 4
triangles = pyramid, 2 triangles + 3 quads = prism, 6 quads = hexa) and its nodes are
put in VTK's order, the right way out. Other polyhedra are counted and left out.
"""
from __future__ import annotations

import numpy as np

from meshviewer.core.mesh.volume import HEXA, PYRAMID, TETRA, WEDGE

CHUNK = 400_000                     # cells per batch (keeps the temporary arrays small)


def _face_nodes(fconn, foff, faces, size):
    """(m, j) face ids -> (m, j, size) node ids."""
    return fconn[foff[faces][..., None] + np.arange(size)]


def _not_in(cand, base):
    """First node of each row of cand (m, s) that is not in base (m, k)."""
    out = ~(cand[:, :, None] == base[:, None, :]).any(2)
    return cand[np.arange(len(cand)), out.argmax(1)]


def _partner(base, quads):
    """For each node of base (m, k): its neighbour, across a quad side face, that is
    not in base — the node above it in a prism or a hexa."""
    m = len(base)
    rows = np.arange(m)[:, None]
    has = (quads[:, None, :, :] == base[:, :, None, None]).any(3)        # (m, k, j)
    q = quads[rows, has.argmax(2)]                                       # (m, k, 4)
    p = (q == base[:, :, None]).argmax(2)
    n1 = np.take_along_axis(q, ((p + 1) % 4)[..., None], 2)[..., 0]
    n2 = np.take_along_axis(q, ((p + 3) % 4)[..., None], 2)[..., 0]
    in_base = (n1[:, :, None] == base[:, None, :]).any(2)
    return np.where(in_base, n2, n1)


def _shape(fconn, foff, fid, sizes, ntri, nquad):
    """Nodes of cells that all have ntri triangles and nquad quads (faces sorted by size)."""
    order = np.argsort(sizes, axis=1, kind="stable")                      # triangles first
    fid = np.take_along_axis(fid, order, 1)
    tri = _face_nodes(fconn, foff, fid[:, :ntri], 3) if ntri else None
    quad = _face_nodes(fconn, foff, fid[:, ntri:], 4) if nquad else None
    if nquad == 0:                                                       # tetra
        return TETRA, np.column_stack([tri[:, 0], _not_in(tri[:, 1], tri[:, 0])])
    if ntri == 4:                                                        # pyramid
        return PYRAMID, np.column_stack([quad[:, 0], _not_in(tri[:, 0], quad[:, 0])])
    if ntri == 2:                                                        # prism
        return WEDGE, np.column_stack([tri[:, 0], _partner(tri[:, 0], quad)])
    return HEXA, np.column_stack([quad[:, 0], _partner(quad[:, 0], quad[:, 1:])])


SHAPES = ((4, 0), (4, 1), (2, 3), (0, 6))          # (triangles, quads) per cell type


def standard_cells(fconn, foff, cell_faces, coff):
    """fconn, foff: NGON faces (0-based nodes, start offsets, len = faces + 1).
    cell_faces, coff: NFACE cells (0-based face ids, sign dropped; offsets).
    Returns ({VTK cell type: (m, k) node ids}, number of cells left out)."""
    fsize = np.diff(foff)
    nfc = np.diff(coff)
    cell_of = np.repeat(np.arange(len(nfc)), nfc)
    s = fsize[cell_faces]
    ntri = np.bincount(cell_of, weights=s == 3, minlength=len(nfc)).astype(int)
    nquad = np.bincount(cell_of, weights=s == 4, minlength=len(nfc)).astype(int)
    blocks, used = {}, 0
    for t, q in SHAPES:
        cells = np.flatnonzero((ntri == t) & (nquad == q) & (nfc == t + q))
        for a in range(0, len(cells), CHUNK):
            c = cells[a:a + CHUNK]
            fid = cell_faces[coff[c][:, None] + np.arange(t + q)]
            ctype, conn = _shape(fconn, foff, fid, fsize[fid], t, q)
            blocks.setdefault(ctype, []).append(conn)
        used += len(cells)
    return blocks, len(nfc) - used
