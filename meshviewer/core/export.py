"""Save the open model (with its edits) in another format. No Qt.

    export(fmt, path, parts, volume=None)

parts: {name: pv.PolyData} — the surfaces / boundaries to write (in order).
volume: pv.UnstructuredGrid of the volume cells (mesh files), or None.

    stl        binary STL, everything merged (what most tools want)
    stl_ascii  text STL, one named "solid" per part (keeps the names)
    obj        OBJ, one group per part (+ .mtl with the part colours)
    ply        binary PLY, everything merged, a colour per face
    vtu        VTK unstructured grid: volume cells + boundary faces, with a
               "part" number per cell (0 = volume) — opens in ParaView
    ugrid      FUN3D / AFLR3 UGRID (.lb8.ugrid) + .mapbc with the boundary names
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pyvista as pv
from vtkmodules.vtkFiltersCore import vtkAppendFilter, vtkAppendPolyData

from meshviewer.core.polys import bare, faces_by_size

FORMATS = {   # key: (menu text, file extension)
    "stl": ("STL — binary, all parts merged", ".stl"),
    "stl_ascii": ("STL — text, one named solid per part", ".stl"),
    "obj": ("OBJ — one group per part, with colors", ".obj"),
    "ply": ("PLY — binary, merged, with colors", ".ply"),
    "vtu": ("VTU — volume + boundaries (ParaView)", ".vtu"),
    "ugrid": ("UGRID + .mapbc — FUN3D / AFLR3", ".lb8.ugrid"),
}


def available(kind: str, exact_cad: bool):
    """Format keys that make sense for this model."""
    keys = ["stl", "stl_ascii", "obj", "ply"]
    if not exact_cad:
        keys.append("vtu")
    if kind == "mesh":
        keys.append("ugrid")
    return keys


def export(fmt: str, path, parts: dict, volume=None, colors=None):
    """colors: {part name: "#rrggbb"} — written by OBJ (.mtl beside it)
    and PLY (a colour per face); the other formats have no colours."""
    path = Path(path)
    if not parts:
        raise ValueError("nothing to export (no visible parts)")
    writer = {"stl": _stl_binary, "stl_ascii": _stl_ascii, "obj": _obj, "ply": _ply,
              "vtu": _vtu, "ugrid": _ugrid}[fmt]
    if fmt in ("obj", "ply"):
        writer(path, parts, volume, colors or {})
    else:
        writer(path, parts, volume)
    return path


def _rgb(hex_color):
    h = str(hex_color).lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) if len(h) >= 6 else (190, 190, 190)


# ---- helpers ------------------------------------------------------------------------
def _plain(poly):
    """Geometry only (no colours / ids), triangles and quads kept."""
    out = bare(poly) if poly.n_cells else pv.PolyData()
    return out


def _merged(parts):
    app = vtkAppendPolyData()
    for poly in parts.values():
        app.AddInputData(_plain(poly))
    app.Update()
    return pv.wrap(app.GetOutput())


# ---- writers ------------------------------------------------------------------------
def _stl_binary(path, parts, volume):
    _merged(parts).triangulate().save(str(path), binary=True)


def _stl_ascii(path, parts, volume):
    fmt = ("  facet normal %.7e %.7e %.7e\n    outer loop\n"
           "      vertex %.9e %.9e %.9e\n      vertex %.9e %.9e %.9e\n"
           "      vertex %.9e %.9e %.9e\n    endloop\n  endfacet")
    with open(path, "w") as f:
        for name, poly in parts.items():
            tri = _plain(poly).triangulate()
            solid = "".join(c if c.isprintable() and not c.isspace() else "_" for c in name)
            f.write(f"solid {solid}\n")
            t = faces_by_size(tri).get(3)
            if t is not None and len(t):
                p = np.asarray(tri.points, dtype=float)
                a, b, c = p[t[:, 0]], p[t[:, 1]], p[t[:, 2]]
                nrm = np.cross(b - a, c - a)
                nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-300)
                np.savetxt(f, np.hstack([nrm, a, b, c]), fmt=fmt)
            f.write(f"endsolid {solid}\n")


def _obj(path, parts, volume, colors):
    mtl = path.with_suffix(".mtl")
    with open(mtl, "w") as f:                     # one material (colour) per part
        f.write("# Mesh Viewer export\n")
        for i, name in enumerate(parts):
            r, g, b = (c / 255 for c in _rgb(colors.get(name, "#bebebe")))
            f.write(f"newmtl part{i}\nKd {r:.4f} {g:.4f} {b:.4f}\n"
                    f"Ka 0 0 0\nKs 0.1 0.1 0.1\nNs 20\nd 1\n\n")
    with open(path, "w") as f:
        f.write(f"# Mesh Viewer export\nmtllib {mtl.name}\n")
        base = 1
        for i, (name, poly) in enumerate(parts.items()):
            p = np.asarray(poly.points, dtype=float)
            f.write(f"o {name}\ng {name}\nusemtl part{i}\n")
            np.savetxt(f, p, fmt="v %.9g %.9g %.9g")
            for k, arr in faces_by_size(poly).items():
                np.savetxt(f, arr + base, fmt="f" + " %d" * k)
            base += len(p)


def _ply(path, parts, volume, colors):
    """Binary PLY, everything merged, a colour per face."""
    app = vtkAppendPolyData()
    for name, poly in parts.items():
        s = _plain(poly)
        s.cell_data["RGB"] = np.tile(np.array(_rgb(colors.get(name, "#bebebe")), np.uint8),
                                     (s.n_cells, 1))
        app.AddInputData(s)
    app.Update()
    pv.wrap(app.GetOutput()).save(str(path), binary=True, texture="RGB")


def _vtu(path, parts, volume):
    app = vtkAppendFilter()
    app.MergePointsOn()                       # boundaries share the volume's nodes
    if volume is not None:
        v = pv.UnstructuredGrid(volume.cells, volume.celltypes, volume.points)  # no extra arrays
        v.cell_data["part"] = np.zeros(v.n_cells, dtype=np.int32)
        app.AddInputData(v)
    for i, poly in enumerate(parts.values(), start=1):
        s = _plain(poly)
        s.cell_data["part"] = np.full(s.n_cells, i, dtype=np.int32)
        app.AddInputData(s)
    app.Update()
    grid = pv.wrap(app.GetOutput())
    grid.field_data["part_names"] = np.array(["volume", *parts.keys()])
    grid.save(str(path), binary=True)


def _ugrid(path, parts, volume):
    """Little-endian 8-byte UGRID: header, nodes, triangles, quads, boundary
    tags, then tetra / pyramid / prism / hex cells (node numbers from 1)."""
    base = np.asarray(volume.points, dtype=float) if volume is not None else np.empty((0, 3))
    surfs = []
    for poly in parts.values():
        s = _plain(poly)
        if any(k > 4 for k in faces_by_size(s)):
            s = s.triangulate()                # UGRID boundaries: triangles and quads only
        surfs.append(s)
    # One shared node list: the volume's nodes first, then any boundary node not
    # in it (matched exactly by coordinates).
    surf_pts = [np.asarray(s.points, dtype=float) for s in surfs]
    allp = np.vstack([base, *surf_pts]) + 0.0
    _, first, inv = np.unique(allp, axis=0, return_index=True, return_inverse=True)
    inv = np.ravel(inv)
    nb = len(base)
    new_ids = np.full(len(first), -1, dtype=np.int64)
    in_base = first < nb
    new_ids[in_base] = first[in_base]
    extra = np.flatnonzero(~in_base)
    new_ids[extra] = nb + np.arange(len(extra))
    points = np.vstack([base, allp[first[extra]]]) if len(extra) else base
    gid = new_ids[inv]

    tris, quads, ttag, qtag = [], [], [], []
    off = nb
    for tag, (s, sp) in enumerate(zip(surfs, surf_pts), start=1):
        ids = gid[off: off + len(sp)]
        off += len(sp)
        by = faces_by_size(s)
        if 3 in by:
            tris.append(ids[by[3]])
            ttag.append(np.full(len(by[3]), tag))
        if 4 in by:
            quads.append(ids[by[4]])
            qtag.append(np.full(len(by[4]), tag))
    cat = lambda lst, k: np.vstack(lst) if lst else np.empty((0, k), dtype=np.int64)  # noqa: E731
    tri, quad = cat(tris, 3), cat(quads, 4)
    tt = np.concatenate(ttag) if ttag else np.empty(0, dtype=np.int64)
    qt = np.concatenate(qtag) if qtag else np.empty(0, dtype=np.int64)

    cells = volume.cells_dict if volume is not None else {}
    vol = []
    for ctype, k in ((pv.CellType.TETRA, 4), (pv.CellType.PYRAMID, 5),
                     (pv.CellType.WEDGE, 6), (pv.CellType.HEXAHEDRON, 8)):
        c = np.asarray(cells.get(ctype, np.empty((0, k), dtype=np.int64)))
        if ctype == pv.CellType.PYRAMID:
            c = c[:, [1, 0, 4, 2, 3]]          # VTK pyramid -> UGRID node order
        vol.append(c)

    i8 = np.dtype("<i8")
    with open(path, "wb") as f:
        np.array([len(points), len(tri), len(quad), *[len(c) for c in vol]], i8).tofile(f)
        np.asarray(points, dtype="<f8").tofile(f)
        (tri + 1).astype(i8).tofile(f)
        (quad + 1).astype(i8).tofile(f)
        tt.astype(i8).tofile(f)
        qt.astype(i8).tofile(f)
        for c in vol:
            (c + 1).astype(i8).tofile(f)
    # .mapbc beside it: boundary names (type 0 = not set; FUN3D users fill it in)
    name = path.name
    stem = name[: -len(".lb8.ugrid")] if name.lower().endswith(".lb8.ugrid") else path.stem
    lines = [str(len(parts))] + [f"{i} 0 {n}" for i, n in enumerate(parts, start=1)]
    (path.parent / f"{stem}.mapbc").write_text("\n".join(lines) + "\n")
