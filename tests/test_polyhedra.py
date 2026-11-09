"""NGON_n / NFACE_n polyhedra read back as tetra, pyramids, prisms, hexa (B7)."""
import numpy as np
import pyvista as pv

from conftest import check, run


def _as_polyhedra(grid, flip_every_other=True):
    """Every cell -> its faces (node lists), some faces reversed like a real file."""
    fconn, foff, cf, coff = [], [0], [], [0]
    for c in range(grid.n_cells):
        for j, face in enumerate(grid.get_cell(c).faces):
            ids = list(face.point_ids)
            if flip_every_other and (c + j) % 2:
                ids = ids[::-1]
            cf.append(len(foff) - 1)
            fconn += ids
            foff.append(len(fconn))
        coff.append(len(cf))
    return np.array(fconn), np.array(foff), np.array(cf), np.array(coff)


def test(app, files):
    from meshviewer.core.mesh.polyhedra import standard_cells
    from meshviewer.core.mesh.volume import build_grid, orient_each
    from meshviewer.core.quality import compute
    pts = np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0],
                    [0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1], [0.5, 0.5, 1.7]], float)
    cells = {pv.CellType.HEXAHEDRON: np.array([[0, 1, 2, 3, 4, 5, 6, 7]]),
             pv.CellType.TETRA: np.array([[0, 1, 3, 4]]),
             pv.CellType.WEDGE: np.array([[0, 1, 4, 3, 2, 7]]),
             pv.CellType.PYRAMID: np.array([[4, 5, 6, 7, 8]])}
    ref = pv.UnstructuredGrid(cells, pts)
    want = sorted(np.round(np.abs(compute(ref, "size")), 6))
    blocks, skipped = standard_cells(*_as_polyhedra(ref))
    g = build_grid(pts, orient_each(blocks, pts))
    vol = compute(g, "size")
    check(skipped == 0 and g.n_cells == 4, f"4 cells rebuilt ({skipped} skipped)")
    check(sorted(np.round(vol, 6)) == want, f"same volumes {sorted(np.round(vol, 4))}")
    check((vol > 0).all(), "all the right way out")
    tets = pv.ImageData(dimensions=(4, 4, 4)).cast_to_unstructured_grid().triangulate()
    blocks, _ = standard_cells(*_as_polyhedra(tets))
    g = build_grid(tets.points, orient_each(blocks, tets.points))
    check(abs(compute(g, "size").sum() - 27) < 1e-9 and (compute(g, "size") > 0).all(),
          f"{g.n_cells} tetra fill the box")
    from meshviewer.core import formats
    m = formats.load(files["ngon"], debug=False)
    v = m.volume()
    check(v is not None and v.n_cells == 216, "NGON/NFACE CGNS: volume cells read")


if __name__ == "__main__":
    run(test)
