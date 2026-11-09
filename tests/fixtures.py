"""Small test files, written once into tests/_data/ (git-ignored):

    box.step         CAD: a box with a cylindrical hole (OCP)
    box.cgns         3D mesh: hex volume (HEXA_8) + wall / farfield quads, BC by element range
    box_ngon.cgns    the same mesh as polyhedra (NGON_n faces + NFACE_n cells, CGNS 4)
    box_mixed.cgns   the same mesh as MIXED sections with a junk ElementStartOffset
    wing.lb8.ugrid   3D surface mesh (+ .mapbc names)
    sphere.dat       Tecplot results: sphere + floor, FEBLOCK, x y z rho u v w p mach cp yplus
    box_gmsh.msh     Gmsh 2.2, 3D: tetra + named boundary triangles (meshio)
    plate_gmsh.msh   Gmsh 2.2, 2D: triangles + named boundary lines
    box_fluent.msh   Fluent text, 3D: hex cells as faces with their two cells
    box_fluent_bin.msh  the same, binary sections
    plate_fluent.msh Fluent text, 2D: quad cells as edges
    profile.dxf      DXF: a closed polyline, a circle, an arc and a line on two layers
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pyvista as pv

DATA = Path(__file__).with_name("_data")


def _hex_box(n=6):
    """Hex mesh of the unit cube, graded towards z = 0 (the wall)."""
    x = np.linspace(0, 1, n + 1)
    z = (np.geomspace(1, 11, n + 1) - 1) / 10            # thin first layer at the wall
    X, Y, Z = np.meshgrid(x, x, z, indexing="ij")
    pts = np.column_stack([X.ravel(), Y.ravel(), Z.ravel()])
    idx = np.arange(len(pts)).reshape(n + 1, n + 1, n + 1)
    i, j, k = np.meshgrid(np.arange(n), np.arange(n), np.arange(n), indexing="ij")
    i, j, k = i.ravel(), j.ravel(), k.ravel()
    hexa = np.column_stack([idx[i, j, k], idx[i + 1, j, k], idx[i + 1, j + 1, k], idx[i, j + 1, k],
                            idx[i, j, k + 1], idx[i + 1, j, k + 1], idx[i + 1, j + 1, k + 1],
                            idx[i, j + 1, k + 1]])
    faces = {"wall": [], "farfield": []}
    for a in range(n):
        for b in range(n):
            faces["wall"].append([idx[a, b, 0], idx[a, b + 1, 0], idx[a + 1, b + 1, 0], idx[a + 1, b, 0]])
            faces["farfield"].append([idx[a, b, n], idx[a + 1, b, n], idx[a + 1, b + 1, n], idx[a, b + 1, n]])
    for c in (0, n):                                         # x = 0, 1 and y = 0, 1 sides
        for a in range(n):
            for b in range(n):
                faces["farfield"].append([idx[c, a, b], idx[c, a + 1, b], idx[c, a + 1, b + 1], idx[c, a, b + 1]])
                faces["farfield"].append([idx[a, c, b], idx[a, c, b + 1], idx[a + 1, c, b + 1], idx[a + 1, c, b]])
    return pts, hexa, {k: np.array(v) for k, v in faces.items()}


def _node(parent, name, label, data=None):
    g = parent.create_group(name)
    g.attrs["label"] = np.bytes_(label)
    g.attrs["name"] = np.bytes_(name)
    if data is not None:
        g.create_dataset(" data", data=data)
    return g


def _cgns(path, ngon=False, mixed=False):
    import h5py
    pts, hexa, faces = _hex_box()
    with h5py.File(path, "w") as f:
        base = _node(f, "Base", "CGNSBase_t", np.array([3, 3], np.int32))
        z = _node(base, "Zone", "Zone_t", np.array([[len(pts), len(hexa), 0]], np.int64))
        gc = _node(z, "GridCoordinates", "GridCoordinates_t")
        for i, a in enumerate("XYZ"):
            _node(gc, "Coordinate" + a, "DataArray_t", pts[:, i])
        zbc = _node(z, "ZoneBC", "ZoneBC_t")
        def section(name, code, cells, first):
            """Elements of one type; mixed=True writes them as MIXED with a junk
            ElementStartOffset (the type code everywhere), as some exporters do."""
            if not mixed:
                e = _node(z, name, "Elements_t", np.array([code, 0], np.int32))
                conn = (cells + 1).ravel()
            else:
                e = _node(z, name, "Elements_t", np.array([20, 0], np.int32))
                conn = np.column_stack([np.full(len(cells), code), cells + 1]).ravel()
                _node(e, "ElementStartOffset", "DataArray_t", np.full(len(cells) + 1, code, np.int32))
            _node(e, "ElementRange", "IndexRange_t", np.array([first, first + len(cells) - 1], np.int64))
            _node(e, "ElementConnectivity", "DataArray_t", conn.astype(np.int64))

        if not ngon:
            section("Hexa", 17, hexa, 1)
            start = len(hexa) + 1
            for name, q in faces.items():
                section(name.upper() + "_2D", 7, q, start)
                bc = _node(zbc, name, "BC_t")
                _node(bc, "PointRange", "IndexRange_t", np.array([start, start + len(q) - 1], np.int64))
                start += len(q)
            return
        # NGON_n: every face once (boundary faces first, then interior), NFACE_n cells
        local = np.array([[0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]])
        allf = hexa[:, local].reshape(-1, 4)
        key = np.sort(allf, axis=1)
        uniq, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
        inv = inv.ravel()
        bkeys = {}
        for name, q in faces.items():
            for row in np.sort(q, axis=1):
                bkeys[tuple(row)] = name
        order = sorted(range(len(uniq)), key=lambda u: (tuple(uniq[u]) not in bkeys, bkeys.get(tuple(uniq[u]), "")))
        newid = np.empty(len(uniq), np.int64)
        newid[order] = np.arange(len(uniq))
        face_nodes = allf[first][order]
        nf = len(face_nodes)
        e = _node(z, "NGON", "Elements_t", np.array([22, 0], np.int32))
        _node(e, "ElementRange", "IndexRange_t", np.array([1, nf], np.int64))
        _node(e, "ElementStartOffset", "DataArray_t", np.arange(0, 4 * nf + 1, 4, dtype=np.int64))
        _node(e, "ElementConnectivity", "DataArray_t", (face_nodes + 1).ravel().astype(np.int64))
        cellf = newid[inv].reshape(len(hexa), 6) + 1               # 1-based face ids
        # sign: + when the face's normal points out of the cell (its first owner)
        owner = np.zeros(nf, bool)
        sign = np.ones_like(cellf)
        for c in range(len(hexa)):
            for j in range(6):
                fid = cellf[c, j] - 1
                if owner[fid]:
                    sign[c, j] = -1
                owner[fid] = True
        e = _node(z, "NFACE", "Elements_t", np.array([23, 0], np.int32))
        _node(e, "ElementRange", "IndexRange_t", np.array([nf + 1, nf + len(hexa)], np.int64))
        _node(e, "ElementStartOffset", "DataArray_t", np.arange(0, 6 * len(hexa) + 1, 6, dtype=np.int64))
        _node(e, "ElementConnectivity", "DataArray_t", (cellf * sign).ravel().astype(np.int64))
        start = 1
        for name, q in sorted(faces.items()):                    # same order as the faces
            bc = _node(zbc, name, "BC_t")
            _node(bc, "PointRange", "IndexRange_t", np.array([start, start + len(q) - 1], np.int64))
            _node(bc, "GridLocation", "GridLocation_t", np.frombuffer(b"FaceCenter", np.int8))
            start += len(q)


def _step(path):
    import cadquery as cq
    cq.exporters.export(cq.Workplane().box(40, 20, 10).faces(">Z").workplane().hole(6), str(path))


def _ugrid(path):
    box = pv.Box(bounds=(0, 4, 0, 1, 0, 0.3), level=6, quads=True).clean()
    pts, quads = box.points, box.faces.reshape(-1, 5)[:, 1:]
    c = box.cell_centers().points
    tags = np.where(c[:, 2] > 0.29, 1, np.where(c[:, 0] > 3.99, 3, 2))
    with open(path, "wb") as f:
        np.array([len(pts), 0, len(quads), 0, 0, 0, 0], "<i8").tofile(f)
        pts.astype("<f8").tofile(f)
        (quads + 1).astype("<i8").tofile(f)
        tags.astype("<i8").tofile(f)
    Path(str(path).replace(".lb8.ugrid", ".mapbc")).write_text(
        "3\n1 5000 upper_skin\n2 5000 lower_and_sides\n3 3000 tip\n")


def _tecplot(path):
    s = pv.Sphere(radius=0.5, theta_resolution=40, phi_resolution=30).triangulate().clean()
    floor = pv.Plane(center=(0, 0, -3), i_size=6, j_size=6, i_resolution=1, j_resolution=1)
    names = "x y z rho u v w p mach cp yplus".split()
    out = ['title="tecplot geometry and solution file"', "variables = " + " ".join(names)]
    for k, (title, m) in enumerate((("SPHERE", s), ("FLOOR", floor))):
        p = m.points
        r = np.linalg.norm(p, axis=1) + 1e-9
        cosx = p[:, 0] / r
        cp = 1 - 2.25 * (1 - cosx ** 2) if title == "SPHERE" else np.zeros(len(p))
        u = 1.5 * np.sqrt(np.clip(1 - cosx ** 2, 0, 1)) + 1e-3
        vals = [p[:, 0], p[:, 1], p[:, 2], np.ones(len(p)), u, 0 * u, 0 * u, 1 + 0.5 * cp,
                u * 0.5, cp, 0.5 + 0.5 * (1 + cosx) / 2]
        quads = m.faces.reshape(-1, m.faces[0] + 1)[:, 1:]
        if quads.shape[1] == 3:
            quads = np.column_stack([quads, quads[:, 2]])
        out.append(f'zone t="boundary {k + 1} {title}", solutiontime= 0.5E+03, strandid={1001 + k}, '
                   f"i={len(p)}, j={len(quads)}, f=feblock")
        for v in vals:
            for i in range(0, len(v), 7):
                out.append(" ".join(f"{x:.12E}" for x in v[i:i + 7]))
        out += [" ".join(str(int(x) + 1) for x in q) for q in quads]
    Path(path).write_text("\n".join(out) + "\n")


def _gmsh3d(path):
    import meshio
    pts, hexa, faces = _hex_box(4)
    tets = pv.UnstructuredGrid({pv.CellType.HEXAHEDRON: hexa}, pts).triangulate()
    tet = tets.cells_dict[pv.CellType.TETRA]
    cells, phys, geo = [("tetra", tet)], [np.full(len(tet), 1)], [np.full(len(tet), 1)]
    for k, (name, q) in enumerate(sorted(faces.items()), start=2):
        tri = np.vstack([q[:, [0, 1, 2]], q[:, [0, 2, 3]]])
        cells.append(("triangle", tri))
        phys.append(np.full(len(tri), k))
        geo.append(np.full(len(tri), k))
    fd = {"fluid": [1, 3], **{n: [k, 2] for k, n in enumerate(sorted(faces), start=2)}}
    m = meshio.Mesh(tets.points, cells, cell_data={"gmsh:physical": phys, "gmsh:geometrical": geo},
                    field_data=fd)
    meshio.write(str(path), m, file_format="gmsh22", binary=False)


def _plate(n=6):
    x = np.linspace(0, 2, 2 * n + 1)
    y = np.linspace(0, 1, n + 1)
    X, Y = np.meshgrid(x, y, indexing="ij")
    pts = np.column_stack([X.ravel(), Y.ravel(), np.zeros(X.size)])
    idx = np.arange(len(pts)).reshape(len(x), len(y))
    quads = np.array([[idx[i, j], idx[i + 1, j], idx[i + 1, j + 1], idx[i, j + 1]]
                      for i in range(len(x) - 1) for j in range(len(y) - 1)])
    wall = np.array([[idx[i, 0], idx[i + 1, 0]] for i in range(len(x) - 1)])
    far = np.array([[idx[i, -1], idx[i + 1, -1]] for i in range(len(x) - 1)]
                   + [[idx[0, j], idx[0, j + 1]] for j in range(len(y) - 1)]
                   + [[idx[-1, j], idx[-1, j + 1]] for j in range(len(y) - 1)])
    return pts, quads, {"wall": wall, "farfield": far}


def _gmsh2d(path):
    import meshio
    pts, quads, lines = _plate()
    tri = np.vstack([quads[:, [0, 1, 2]], quads[:, [0, 2, 3]]])
    cells = [("triangle", tri), ("line", lines["wall"]), ("line", lines["farfield"])]
    tags = [np.full(len(tri), 1), np.full(len(lines["wall"]), 2), np.full(len(lines["farfield"]), 3)]
    m = meshio.Mesh(pts, cells, cell_data={"gmsh:physical": tags, "gmsh:geometrical": tags},
                    field_data={"domain": [1, 2], "wall": [2, 1], "farfield": [3, 1]})
    meshio.write(str(path), m, file_format="gmsh22", binary=False)


def _fluent_text(path, pts, dim, cells, cell_type, face_zones, binary=False):
    """face_zones: [(zone id, bc type, name, faces (k, n) 0-based, c0, c1 1-based)]."""
    out = ['(0 "Mesh Viewer test mesh")', f"(2 {dim})"]
    nf = sum(len(f) for _, _, _, f, _, _ in face_zones)
    out += [f"(10 (0 1 {len(pts):x} 0 {dim}))", f"(12 (0 1 {cells:x} 0))", f"(13 (0 1 {nf:x} 0))"]
    chunks = []
    if binary:                                   # 3010 doubles, 2013 int32
        chunks.append(("\n".join(out) + "\n").encode())
        chunks.append(f"(3010 (1 1 {len(pts):x} 1 {dim})(".encode()
                      + np.ascontiguousarray(pts[:, :dim], "<f8").tobytes() + b"))\n")
        chunks.append(f"(2012 (2 1 {cells:x} 1 {cell_type:x}))\n".encode())
        first = 1
        for zone, bc, name, faces, c0, c1 in face_zones:
            last = first + len(faces) - 1
            body = np.column_stack([faces + 1, c0, c1]).astype("<i4").tobytes()
            chunks.append(f"(2013 ({zone:x} {first:x} {last:x} {bc:x} {faces.shape[1]:x})(".encode()
                          + body + b"))\n")
            first = last + 1
        tail = ["(45 (2 fluid fluid)())"] + [f"(45 ({zone} {BCN.get(bc, 'wall')} {name})())"
                                             for zone, bc, name, *_ in face_zones]
        chunks.append(("\n".join(tail) + "\n").encode())
        Path(path).write_bytes(b"".join(chunks))
        return
    out.append(f"(10 (1 1 {len(pts):x} 1 {dim})(")
    out += [" ".join(f"{v:.10g}" for v in p[:dim]) for p in pts]
    out.append("))")
    out.append(f"(12 (2 1 {cells:x} 1 {cell_type:x}))")
    first = 1
    for zone, bc, name, faces, c0, c1 in face_zones:
        last = first + len(faces) - 1
        out.append(f"(13 ({zone:x} {first:x} {last:x} {bc:x} {faces.shape[1]:x})(")
        out += [" ".join(f"{v:x}" for v in [*(f + 1), a, b]) for f, a, b in zip(faces, c0, c1)]
        out.append("))")
        first = last + 1
    out.append("(45 (2 fluid fluid)())")
    out += [f"(45 ({zone} {BCN.get(bc, 'wall')} {name})())" for zone, bc, name, *_ in face_zones]
    Path(path).write_text("\n".join(out) + "\n")


BCN = {2: "interior", 3: "wall", 9: "pressure-far-field"}


def _fluent3d(path, binary=False):
    pts, hexa, faces = _hex_box(4)
    local = np.array([[0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]])
    allf = hexa[:, local].reshape(-1, 4)
    owner = np.repeat(np.arange(len(hexa)) + 1, 6)
    key = np.sort(allf, axis=1)
    uniq, first, inv, cnt = np.unique(key, axis=0, return_index=True, return_inverse=True,
                                      return_counts=True)
    inv = inv.ravel()
    c0 = np.zeros(len(uniq), int)
    c1 = np.zeros(len(uniq), int)
    for f, o in zip(inv, owner):
        if c0[f] == 0:
            c0[f] = o
        else:
            c1[f] = o
    fnodes = allf[first]
    names = {}
    for name, q in faces.items():
        for row in np.sort(q, axis=1):
            names[tuple(row)] = name
    zone_of = np.array([names.get(tuple(r), "interior") for r in uniq])
    zones = []
    for zid, bc, name in ((3, 2, "interior"), (4, 3, "wall"), (5, 9, "farfield")):
        sel = zone_of == name
        zones.append((zid, bc, name, fnodes[sel], c0[sel], c1[sel]))
    _fluent_text(path, pts, 3, len(hexa), 4, zones, binary)


def _fluent2d(path):
    pts, quads, lines = _plate()
    e = np.vstack([quads[:, [0, 1]], quads[:, [1, 2]], quads[:, [2, 3]], quads[:, [3, 0]]])
    owner = np.tile(np.arange(len(quads)) + 1, 4)
    key = np.sort(e, axis=1)
    uniq, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    inv = inv.ravel()
    c0 = np.zeros(len(uniq), int)
    c1 = np.zeros(len(uniq), int)
    for f, o in zip(inv, owner):
        if c0[f] == 0:
            c0[f] = o
        else:
            c1[f] = o
    enodes = e[first]
    lab = {}
    for name, segs in lines.items():
        for r in np.sort(segs, axis=1):
            lab[tuple(r)] = name
    zone_of = np.array([lab.get(tuple(r), "interior") for r in uniq])
    zones = []
    for zid, bc, name in ((3, 2, "interior"), (4, 3, "wall"), (5, 9, "farfield")):
        sel = zone_of == name
        zones.append((zid, bc, name, enodes[sel], c0[sel], c1[sel]))
    _fluent_text(path, pts, 2, len(quads), 3, zones)


def _dxf(path):
    import ezdxf
    doc = ezdxf.new()
    msp = doc.modelspace()
    doc.layers.add("PROFILE")
    doc.layers.add("HOLES")
    msp.add_lwpolyline([(0, 0), (40, 0), (40, 20), (0, 20)], close=True, dxfattribs={"layer": "PROFILE"})
    msp.add_circle((10, 10), 4, dxfattribs={"layer": "HOLES"})
    msp.add_arc((30, 10), 5, 0, 180, dxfattribs={"layer": "HOLES"})
    msp.add_line((25, 10), (35, 10), dxfattribs={"layer": "HOLES"})
    doc.saveas(str(path))


MAKERS = {"step": ("box.step", _step), "cgns": ("box.cgns", lambda p: _cgns(p)),
          "ngon": ("box_ngon.cgns", lambda p: _cgns(p, ngon=True)),
          "mixed": ("box_mixed.cgns", lambda p: _cgns(p, mixed=True)),
          "ugrid": ("wing.lb8.ugrid", _ugrid), "tecplot": ("sphere.dat", _tecplot),
          "gmsh3d": ("box_gmsh.msh", _gmsh3d), "gmsh2d": ("plate_gmsh.msh", _gmsh2d),
          "fluent3d": ("box_fluent.msh", _fluent3d),
          "fluent3d_bin": ("box_fluent_bin.msh", lambda p: _fluent3d(p, binary=True)), "fluent2d": ("plate_fluent.msh", _fluent2d),
          "dxf": ("profile.dxf", _dxf)}


def files(rebuild=False):
    """{key: path}, making what is missing."""
    DATA.mkdir(exist_ok=True)
    out = {}
    for key, (name, make) in MAKERS.items():
        p = DATA / name
        if rebuild or not p.exists():
            make(p)
        out[key] = p
    return out


if __name__ == "__main__":
    for k, p in files(rebuild=True).items():
        print(k, p, p.stat().st_size)
