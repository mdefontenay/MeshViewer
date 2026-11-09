"""CGNS mesh reader (HDF5 layer).

MESH format. Returns {boundary_name: pv.PolyData}, one surface per BC_t node.
Code moved unchanged from the original mesh_viewer.py.
"""
from __future__ import annotations

import numpy as np
import pyvista as pv

from meshviewer.core.model import MissingDependency

try:
    import h5py
except ImportError as exc:  # h5py is only needed for CGNS files
    raise MissingDependency("h5py", "CGNS files") from exc


# CGNS element-type code -> nodes per element (fixed-size types only).
# FIX: QUAD_8 (8), QUAD_9 (9 — was 8), HEXA_20 (20 — was 14), HEXA_27
# (27 — was 25) and the quadratic pyramids / prisms were missing or wrong.
FIXED_NPE = {2: 1, 3: 2, 4: 3, 5: 3, 6: 6, 7: 4, 8: 8, 9: 9, 10: 4, 11: 10,
             12: 5, 13: 14, 14: 6, 15: 15, 16: 18, 17: 8, 18: 20, 19: 27, 21: 13}


def _cgns_label(node):
    for k in ("label", " label"):
        if k in node.attrs:
            v = node.attrs[k]
            if isinstance(v, np.ndarray):
                v = v.tobytes()
            if isinstance(v, bytes):
                return v.decode("ascii", errors="ignore").strip().rstrip("\x00")
            return str(v).strip()
    return ""


def _cgns_dataset(node):
    if node is None:
        return None
    for k in (" data", "data"):
        if k in node and isinstance(node[k], h5py.Dataset):
            return node[k]
    return None


def _cgns_data(node):
    ds = _cgns_dataset(node)
    return ds[()] if ds is not None else None


def _kids(parent, lbl):
    return [
        (name, child)
        for name, child in parent.items()
        if isinstance(child, h5py.Group) and _cgns_label(child) == lbl
    ]


def _parse_cgns_section(elem_node, tcode, n_elem):
    if "ElementConnectivity" not in elem_node:
        return None, None
    conn = np.asarray(_cgns_data(elem_node["ElementConnectivity"]), dtype=np.int64)

    if tcode in FIXED_NPE:
        npe = FIXED_NPE[tcode]
        return conn, np.arange(0, (n_elem + 1) * npe, npe, dtype=np.int64)

    if tcode == 22:  # NGON_n
        eso = _stored_offsets(elem_node, n_elem, len(conn))
        if eso is not None:
            return conn, eso
        new_off, chunks, i, L = [0], [], 0, len(conn)
        while i < L and len(new_off) <= n_elem:
            n = int(conn[i])
            chunks.append(conn[i + 1 : i + 1 + n])
            new_off.append(new_off[-1] + n)
            i += 1 + n
        if len(chunks) != n_elem:
            return None, None
        return np.concatenate(chunks), np.asarray(new_off, dtype=np.int64)

    if tcode == 20:  # MIXED: type code before each element's nodes
        try:
            starts = _mixed_offsets(conn, n_elem, elem_node)
        except ValueError:
            return None, None
        npe = np.diff(np.append(starts, len(conn))) - 1
        keep = np.ones(len(conn), dtype=bool)
        keep[starts] = False                                  # drop the type codes
        return conn[keep], np.concatenate([[0], np.cumsum(npe)]).astype(np.int64)

    return None, None


def _build_face_cells(face_ids, conn, offsets):
    n_faces = len(face_ids)
    if n_faces == 0:
        return np.empty(0, dtype=np.int64)

    starts = offsets[face_ids]
    face_lens = (offsets[face_ids + 1] - starts).astype(np.int64)

    if face_lens.min() == face_lens.max():
        npe = int(face_lens[0])
        verts = conn[(starts[:, None] + np.arange(npe)).ravel()] - 1
        cells = np.empty(n_faces * (npe + 1), dtype=np.int64)
        view = cells.reshape(n_faces, npe + 1)
        view[:, 0] = npe
        view[:, 1:] = verts.reshape(n_faces, npe)
        return cells

    total_v = int(face_lens.sum())
    face_idx = np.repeat(np.arange(n_faces), face_lens)
    within = np.arange(total_v) - np.repeat(np.cumsum(face_lens) - face_lens, face_lens)
    verts = conn[starts[face_idx] + within] - 1

    total = total_v + n_faces
    cells = np.empty(total, dtype=np.int64)
    header_pos = np.concatenate([[0], np.cumsum(face_lens[:-1] + 1)]).astype(np.int64)
    cells[header_pos] = face_lens
    body = np.ones(total, dtype=bool)
    body[header_pos] = False
    cells[body] = verts
    return cells


def _read_bc_ids(bc):
    for key in ("PointList", "ElementList"):
        if key in bc:
            d = _cgns_data(bc[key])
            if d is not None:
                return np.asarray(d, dtype=np.int64).ravel()
    for key in ("PointRange", "ElementRange"):
        if key in bc:
            d = _cgns_data(bc[key])
            if d is not None:
                rng = np.asarray(d, dtype=np.int64).ravel()
                return np.arange(rng[0], rng[1] + 1, dtype=np.int64)
    return None


def _extract_zone_cgns(zname, zone, debug):
    bcs = {}
    gcs = _kids(zone, "GridCoordinates_t")
    if not gcs:
        return bcs
    gc = gcs[0][1]
    ds_x = _cgns_dataset(gc.get("CoordinateX"))
    if ds_x is None or "CoordinateY" not in gc or "CoordinateZ" not in gc:
        return bcs
    pts = np.empty((ds_x.shape[0], 3), dtype=np.float64)
    pts[:, 0] = ds_x[()]
    pts[:, 1] = _cgns_data(gc["CoordinateY"])
    pts[:, 2] = _cgns_data(gc["CoordinateZ"])

    zbcs = _kids(zone, "ZoneBC_t")
    if not zbcs:
        return bcs
    bc_specs = [(n, ids) for n, b in _kids(zbcs[0][1], "BC_t")
                if (ids := _read_bc_ids(b)) is not None and len(ids)]
    if not bc_specs:
        return bcs

    sections = []
    for sname, e in _kids(zone, "Elements_t"):
        et = _cgns_data(e)
        if et is None or "ElementRange" not in e:
            continue
        er = np.ravel(_cgns_data(e["ElementRange"]))
        sections.append((sname, e, int(np.ravel(et)[0]), int(er[0]), int(er[1])))

    section_cache = {}
    for bc_name, ids in bc_specs:
        lo, hi = int(ids.min()), int(ids.max())
        sec = next(((sn, e, t, s, ee) for sn, e, t, s, ee in sections
                    if lo >= s and hi <= ee), None)
        if sec is None:
            if debug:
                print(f"  BC {bc_name}: no section covers [{lo}..{hi}]")
            continue
        sname, e, tcode, s_start, s_end = sec

        if sname not in section_cache:
            if debug:
                print(f"  parsing section {sname!r} (type={tcode}, {s_end - s_start + 1} elems)")
            conn, offsets = _parse_cgns_section(e, tcode, s_end - s_start + 1)
            if conn is None:
                if debug:
                    print("    parse failed")
                continue
            section_cache[sname] = (s_start, conn, offsets)

        sec_start, conn, offsets = section_cache[sname]
        face_ids = ids - sec_start
        cells = _build_face_cells(face_ids, conn, offsets)

        try:
            poly = pv.PolyData(pts, faces=cells).clean()
            key = bc_name if bc_name not in bcs else f"{zname}/{bc_name}"
            bcs[key] = poly
            if debug:
                print(f"  BC {bc_name}: {len(face_ids)} faces -> "
                      f"{poly.n_points} pts, {poly.n_cells} cells")
        except Exception as exc:
            if debug:
                print(f"  BC {bc_name}: build failed: {exc}")

    return bcs


def read_cgns(path, debug=True):
    bcs = {}
    with h5py.File(str(path), "r") as f:
        for _, base in _kids(f, "CGNSBase_t"):
            for zname, zone in _kids(base, "Zone_t"):
                bcs.update(_extract_zone_cgns(zname, zone, debug))
    return bcs


# --- volume cells, read only when the cut mesh is shown ------------------
def _volume_types():
    from meshviewer.core.mesh.volume import HEXA, PYRAMID, TETRA, WEDGE
    # CGNS code -> (VTK cell type, corner nodes). Quadratic cells keep their corners.
    return {10: (TETRA, 4), 11: (TETRA, 4), 12: (PYRAMID, 5), 13: (PYRAMID, 5),
            21: (PYRAMID, 5), 14: (WEDGE, 6), 15: (WEDGE, 6), 16: (WEDGE, 6),
            17: (HEXA, 8), 18: (HEXA, 8), 19: (HEXA, 8)}


def _stored_offsets(e, n_elem, n_conn):
    """ElementStartOffset (CGNS 4) if it is usable: 0, increasing, ends at the
    connectivity's length. Some exporters fill it with junk (e.g. the type code)."""
    if "ElementStartOffset" not in e:
        return None
    off = np.asarray(_cgns_data(e["ElementStartOffset"]), dtype=np.int64).ravel()
    if (len(off) < n_elem + 1 or off[0] != 0 or off[n_elem] != n_conn
            or not np.all(np.diff(off[:n_elem + 1]) > 0)):
        return None
    return off[:n_elem + 1]


def _walk_mixed(conn, n_elem):
    """Start of each element (at its type code) of a MIXED list: type, nodes, type, …
    Runs of the same type are found at once (cheap even for millions of cells)."""
    starts = np.empty(n_elem, dtype=np.int64)
    i = k = 0
    L = len(conn)
    while k < n_elem and i < L:
        code = int(conn[i])
        npe = FIXED_NPE.get(code)
        if npe is None:
            raise ValueError(f"unknown element type {code} in a MIXED section")
        step = npe + 1
        m = min(n_elem - k, (L - i) // step)
        pos = i + step * np.arange(m, dtype=np.int64)
        bad = np.flatnonzero(conn[pos] != code)              # first element of another type
        run = int(bad[0]) if len(bad) else m
        run = max(run, 1)
        starts[k:k + run] = pos[:run]
        k += run
        i += run * step
    if k != n_elem:
        raise ValueError("MIXED section shorter than its element range")
    return starts


def _mixed_offsets(conn, n_elem, e):
    """Start of each element (at its type code) in a MIXED section."""
    off = _stored_offsets(e, n_elem, len(conn))
    return off[:n_elem] if off is not None else _walk_mixed(conn, n_elem)


def _nface_cells(zname, sname, e, ngon, base, blocks, pts, debug):
    """NFACE_n cells built on the zone's NGON_n faces -> tetra / pyramid / prism / hexa."""
    from meshviewer.core.mesh.polyhedra import standard_cells
    from meshviewer.core.mesh.volume import orient_each
    if ngon is None:
        if debug:
            print(f"  {zname}/{sname}: polyhedra without NGON_n faces — not shown")
        return
    er = np.ravel(_cgns_data(e["ElementRange"]))
    faces, coff = _parse_cgns_section(e, 22, int(er[1] - er[0] + 1))   # same layout as NGON
    if faces is None:
        if debug:
            print(f"  {zname}/{sname}: could not read the polyhedra")
        return
    first, fconn, foff = ngon
    cells, skipped = standard_cells(fconn, foff, np.abs(faces) - first, coff)
    for ctype, parts in orient_each(cells, pts).items():
        blocks.setdefault(ctype, []).extend(c + base for c in parts)
    if debug:
        n = sum(len(c) for parts in cells.values() for c in parts)
        print(f"  {zname}/{sname}: {n:,} polyhedra read as tetra / pyramid / prism / hexa"
              + (f", {skipped:,} other polyhedra not shown" if skipped else ""))


def read_volume(path, debug=True):
    """All 3D cells of every unstructured zone as one pv.UnstructuredGrid
    (None if there are none). Polyhedra (NFACE_n) are read when they are tetra,
    pyramids, prisms or hexa (see polyhedra.py)."""
    from meshviewer.core.mesh.volume import build_grid, describe

    vtypes = _volume_types()
    blocks, all_pts, base = {}, [], 0
    with h5py.File(str(path), "r") as f:
        for _, b in _kids(f, "CGNSBase_t"):
            for zname, zone in _kids(b, "Zone_t"):
                gcs = _kids(zone, "GridCoordinates_t")
                if not gcs or "CoordinateX" not in gcs[0][1]:
                    continue
                gc = gcs[0][1]
                pts = np.column_stack([np.ravel(_cgns_data(gc[f"Coordinate{a}"])) for a in "XYZ"])
                ngon = None                                    # (first id, conn, offsets)
                for sname, e in _kids(zone, "Elements_t"):
                    et = _cgns_data(e)
                    if et is not None and int(np.ravel(et)[0]) == 22 and "ElementRange" in e:
                        er = np.ravel(_cgns_data(e["ElementRange"]))
                        conn, off = _parse_cgns_section(e, 22, int(er[1] - er[0] + 1))
                        if conn is not None:
                            ngon = (int(er[0]), conn - 1, off)
                for sname, e in _kids(zone, "Elements_t"):
                    et = _cgns_data(e)
                    if et is None or "ElementRange" not in e or "ElementConnectivity" not in e:
                        continue
                    tcode = int(np.ravel(et)[0])
                    if tcode == 23:                            # NFACE_n: polyhedra
                        _nface_cells(zname, sname, e, ngon, base, blocks, pts, debug)
                        continue
                    if tcode not in vtypes and tcode != 20:
                        continue
                    er = np.ravel(_cgns_data(e["ElementRange"]))
                    n_elem = int(er[1] - er[0] + 1)
                    conn = np.asarray(_cgns_data(e["ElementConnectivity"]), dtype=np.int64)
                    if tcode in vtypes:                       # one cell type
                        ctype, corners = vtypes[tcode]
                        c = conn.reshape(n_elem, FIXED_NPE[tcode])[:, :corners]
                        blocks.setdefault(ctype, []).append(c - 1 + base)
                    else:                                      # MIXED: type code per cell
                        starts = _mixed_offsets(conn, n_elem, e)
                        codes = conn[starts]
                        for code in np.unique(codes):
                            if int(code) not in vtypes:
                                continue                       # faces / edges in the mix
                            ctype, corners = vtypes[int(code)]
                            s = starts[codes == code] + 1
                            c = conn[s[:, None] + np.arange(corners)]
                            blocks.setdefault(ctype, []).append(c - 1 + base)
                all_pts.append(pts)
                base += len(pts)
    if not all_pts:
        return None
    grid = build_grid(np.vstack(all_pts), blocks)
    if debug and grid is not None:
        print(f"  volume: {describe(grid)}")
    return grid
