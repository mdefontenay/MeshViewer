"""CGNS mesh reader (HDF5 layer).

MESH format. Returns {boundary_name: pv.PolyData}, one surface per BC_t node.
Code moved unchanged from the original mesh_viewer.py.
"""
from __future__ import annotations

import numpy as np
import pyvista as pv

from ..model import MissingDependency

try:
    import h5py
except ImportError as exc:  # h5py is only needed for CGNS files
    raise MissingDependency("h5py", "CGNS files") from exc


# CGNS element-type code -> nodes per element (fixed-size types only).
FIXED_NPE = {3: 2, 5: 3, 6: 6, 7: 4, 9: 8, 10: 4, 11: 10,
             12: 5, 14: 6, 17: 8, 18: 14, 19: 25}


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
        eso = _cgns_data(elem_node["ElementStartOffset"]) if "ElementStartOffset" in elem_node else None
        if eso is not None and len(np.asarray(eso)) >= n_elem + 1:
            return conn, np.asarray(eso, dtype=np.int64)
        new_off, chunks, i, L = [0], [], 0, len(conn)
        while i < L and len(new_off) <= n_elem:
            n = int(conn[i])
            chunks.append(conn[i + 1 : i + 1 + n])
            new_off.append(new_off[-1] + n)
            i += 1 + n
        if len(chunks) != n_elem:
            return None, None
        return np.concatenate(chunks), np.asarray(new_off, dtype=np.int64)

    if tcode == 20:  # MIXED
        new_off, chunks, i, L = [0], [], 0, len(conn)
        for _ in range(n_elem):
            if i >= L:
                break
            npe = FIXED_NPE.get(int(conn[i]))
            if npe is None:
                break
            chunks.append(conn[i + 1 : i + 1 + npe])
            new_off.append(new_off[-1] + npe)
            i += 1 + npe
        if len(chunks) != n_elem:
            return None, None
        return np.concatenate(chunks), np.asarray(new_off, dtype=np.int64)

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
