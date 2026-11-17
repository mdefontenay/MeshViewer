"""Measure Selected: what the last picked element is, in numbers. No Qt.

    title, rows = details(scene.elements)      # rows: [(label, text)], in the toolbar's unit

    Node          coordinates, distance to the origin, the boundaries / parts it is on
    Edge          length, its ends, midpoint, ΔX ΔY ΔZ, the angle between the faces at it,
                  the direction (straight) or the plane's normal (in one plane), and for
                  a circle or an arc its radius, diameter and center
    Face          area, normal (mean), centroid, perimeter
    Mesh triangle area, centroid, quality (skewness, aspect ratio, scaled Jacobian), its
                  boundary
    Volume cell   volume, type, centroid, quality

    fields = field_values(scene.elements)      # the solution fields over what is picked

Field values (files with solution fields): over everything picked with Select ▾ (or the
parts selected, Part): at a node its value (several nodes: their mean); along edges the
length-weighted mean; over triangles, faces and parts the area-weighted mean; a volume
cell its own value (else the mean of its corners). In the file's numbers: the panel
shows them in the units chosen in Contours.
"""
from __future__ import annotations

import numpy as np
import pyvista as pv
from vtkmodules.vtkCommonCore import vtkIdList

from meshviewer.core import element_info as ei
from meshviewer.core import quality
from meshviewer.core.field_kinds import SPEED
from meshviewer.core.fields import field_values as _values_of, solution_fields
from meshviewer.core.polys import bare
from meshviewer.core.units import fmt


def _fmt(v):
    return fmt(float(v)) if v is not None and np.isfinite(v) else "—"


class _Units:
    def __init__(self, scene):
        self.s, unit = scene.measure.unit_scale()
        self.tiny = 1e-9 * scene._diag()           # rounding noise: 0
        self.u = f" {unit}" if unit else ""
        self.u2 = f" {unit}²" if unit else ""
        self.u3 = f" {unit}³" if unit else ""

    def length(self, v):
        return f"{_fmt(v * self.s)}{self.u}"

    def xyz(self, p):
        p = np.asarray(p, dtype=float)
        x, y, z = np.where(np.abs(p) < self.tiny, 0.0, p) * self.s
        return f"{_fmt(x)}, {_fmt(y)}, {_fmt(z)}{self.u}"


def _vec(v):
    return ", ".join(_fmt(round(float(x), 6) + 0.0) for x in v)


def details(el):
    """(title, rows) for the last picked element, or None."""
    sc = el.scene
    if el.kind == "part" or not el.items:
        return None
    u = _Units(sc)
    name, key = el.items[-1]
    k = el.kind
    if k == "volume_cell":
        return _volume_cell(el, key, u)
    poly = sc.model.parts.get(name)
    if poly is None:
        return None
    pts = np.asarray(poly.points, dtype=float)
    if k in ("mesh_node", "feature_node"):
        return _node(sc, name, pts[key], u)
    if k in ("mesh_edge", "feature_edge"):
        seg = np.array([key]) if k == "mesh_edge" else el.features(name).curve_segments(key)
        return _edge(el, name, poly, ei.ordered_path(seg, pts), u)
    if k == "mesh_cell":
        return _mesh_cell(sc, name, poly, key, u)
    if k == "feature_face":
        return _face(name, poly.extract_cells(el.features(name).face_cells(key)), u)
    return None


def _node(sc, name, p, u):
    tol = 1e-9 * sc._diag()
    on = [n for n, poly in sc.model.parts.items()
          if np.any(np.all(np.abs(np.asarray(poly.points) - p) <= tol, axis=1))]
    words = sc.model.item_words
    rows = [("Coordinates", u.xyz(p)),
            ("Distance to origin", u.length(np.linalg.norm(p))),
            (words[0].capitalize() if len(on) == 1 else words[1].capitalize(),
             ", ".join(on) or name)]
    return f"Node · {name}", rows


def _faces_at(poly, a, b, tol):
    """Normals of the cells of `poly` that have a point at `a` and one at `b`."""
    pts = np.asarray(poly.points, dtype=float)
    near_a = np.flatnonzero(np.all(np.abs(pts - a) <= tol, axis=1))
    near_b = set(np.flatnonzero(np.all(np.abs(pts - b) <= tol, axis=1)).tolist())
    poly.BuildLinks()
    out, ids = [], vtkIdList()
    seen = set()
    for i in near_a:
        poly.GetPointCells(int(i), ids)
        for j in range(ids.GetNumberOfIds()):
            c = ids.GetId(j)
            if c in seen:
                continue
            seen.add(c)
            cp = list(poly.get_cell(c).point_ids)
            if len(cp) >= 3 and near_b & set(cp):
                q = pts[cp]
                n = np.cross(q[1] - q[0], q[2] - q[0])
                for m in range(3, len(q)):                # Newell for polygons
                    n = n + np.cross(q[m - 1] - q[0], q[m] - q[0])
                out.append(n)
    return out


def _edge(el, name, poly, path, u):
    sc = el.scene
    if len(path) < 2:
        return None
    rows = [("Length", u.length(ei.length(path)))]
    closed = len(path) > 2 and np.allclose(path[0], path[-1])
    if closed:
        rows.append(("Ends", "a closed loop"))
    else:
        rows += [("Start", u.xyz(path[0])), ("End", u.xyz(path[-1]))]
    rows.append(("Midpoint", u.xyz(ei.point_at_length(path, 0.5))))
    dx, dy, dz = np.ptp(path, axis=0) * u.s
    rows.append(("ΔX, ΔY, ΔZ", f"{_fmt(dx)}, {_fmt(dy)}, {_fmt(dz)}{u.u}"))
    if sc.model.dim == 3:
        mid = len(path) // 2
        a, b = path[max(mid - 1, 0)], path[mid]
        normals = []
        for p in sc.model.parts.values():
            if p.GetNumberOfPolys():
                normals += _faces_at(p, a, b, 1e-9 * sc._diag())
        rows.append(("Dihedral angle", f"{_fmt(ei.dihedral(normals[0], normals[1]))}°"
                     if len(normals) == 2 else "— (not between two faces)"))
    d = ei.straight(path)
    if d is not None:
        rows.append(("Direction", _vec(d)))
    else:
        n = ei.planar(path)
        if n is not None:
            rows.append(("Plane normal", _vec(n)))
    c = ei.fit_circle(path) if d is None else None
    if c is not None:
        rows += [("Circle" if c["closed"] else "Arc", f"radius {u.length(c['radius'])}"),
                 ("Diameter", u.length(2 * c["radius"])),
                 ("Center", u.xyz(c["center"]))]
    return f"Edge · {name}", rows


def _area_centroid(surf):
    sizes = surf.compute_cell_sizes(length=False, volume=False)
    a = np.abs(np.asarray(sizes.cell_data["Area"], dtype=float))
    cen = np.asarray(surf.cell_centers().points, dtype=float)
    total = float(a.sum())
    return total, (a[:, None] * cen).sum(axis=0) / (total or 1.0)


def _face(name, cells, u):
    surf = cells.extract_surface()
    area, cen = _area_centroid(surf)
    nrm = surf.compute_normals(cell_normals=True, point_normals=False, auto_orient_normals=False)
    sizes = surf.compute_cell_sizes(length=False, volume=False)
    w = np.abs(np.asarray(sizes.cell_data["Area"], dtype=float))
    n = (np.asarray(nrm.cell_data["Normals"], dtype=float) * w[:, None]).sum(axis=0)
    flat = np.allclose(np.asarray(nrm.cell_data["Normals"]), n / (np.linalg.norm(n) or 1.0),
                       atol=1e-4)
    n = n / (np.linalg.norm(n) or 1.0)
    rim = surf.extract_feature_edges(boundary_edges=True, feature_edges=False,
                                     manifold_edges=False, non_manifold_edges=False)
    perim = float(np.sum(rim.compute_cell_sizes(area=False, volume=False)
                         .cell_data["Length"])) if rim.n_cells else 0.0
    rows = [("Area", f"{_fmt(area * u.s ** 2)}{u.u2}"),
            ("Normal" if flat else "Mean normal", _vec(n)),
            ("Centroid", u.xyz(cen)),
            ("Perimeter", u.length(perim) if rim.n_cells else "— (closed surface)")]
    return f"Face · {name}", rows


def _quality_rows(ds, surface):
    rows = []
    for key in ("skew", "aspect", "jacobian"):
        try:
            v = float(quality.compute(ds, key)[0])
        except Exception:                                   # noqa: BLE001
            v = float("nan")
        rows.append((quality.label(key, surface), _fmt(v)))
    return rows


def _mesh_cell(sc, name, poly, cell, u):
    one = poly.extract_cells([cell]).extract_surface()
    area, cen = _area_centroid(one)
    n_pts = poly.get_cell(cell).n_points
    kind = {3: "Triangle", 4: "Quad"}.get(n_pts, f"{n_pts}-sided polygon")
    idx = sc.names.index(name) + 1 if name in sc.names else 0
    rows = [("Area", f"{_fmt(area * u.s ** 2)}{u.u2}"),
            ("Centroid", u.xyz(cen)),
            ("Type", kind)]
    rows += _quality_rows(pv.PolyData(one.points, one.faces), True)
    rows.append((sc.model.item_words[0].capitalize(), f"{name}  (#{idx})"))
    return f"Mesh {kind.lower()} {cell:,}", rows


def _volume_cell(el, cell, u):
    grid = el.volume_grid()
    if grid is None or not 0 <= cell < grid.n_cells:
        return None
    one = grid.extract_cells([cell])
    vol = abs(float(one.compute_cell_sizes(length=False, area=False).cell_data["Volume"][0]))
    cen = np.asarray(one.points, dtype=float).mean(axis=0)
    rows = [("Volume", f"{_fmt(vol * u.s ** 3)}{u.u3}"),
            ("Type", ei.cell_type_name(grid.celltypes[cell])),
            ("Centroid", u.xyz(cen))]
    rows += _quality_rows(one, False)
    return f"Volume cell {cell:,}", rows


# ---- solution field values over what is picked --------------------------------------------
def _arrays(ds, field):
    """(values, "point" | "cell") of a field on a surface or a grid; speed from u, v, w."""
    if field == SPEED:
        parts = [_values_of(ds, k) for k in ("u", "v", "w")]
        if all(v is not None for v, _ in parts) and len({w for _, w in parts}) == 1:
            u, v, w = (np.asarray(a, dtype=float) for a, _ in parts)
            return np.sqrt(u * u + v * v + w * w), parts[0][1]
        return None, None
    return _values_of(ds, field)


def _at_points(poly, field):
    """The field at every point (a cell field: averaged to the points)."""
    vals, where = _arrays(poly, field)
    if vals is None:
        return None
    if where == "point":
        return np.asarray(vals, dtype=float)
    tmp = bare(poly)
    tmp.cell_data["f"] = np.asarray(vals, dtype=float)
    return np.asarray(tmp.cell_data_to_point_data().point_data["f"], dtype=float)


def _at_cells(poly, field):
    """The field on every cell (a point field: the mean of each cell's points)."""
    vals, where = _arrays(poly, field)
    if vals is None:
        return None
    if where == "cell":
        return np.asarray(vals, dtype=float)
    tmp = bare(poly)
    tmp.point_data["f"] = np.asarray(vals, dtype=float)
    return np.asarray(tmp.point_data_to_cell_data().cell_data["f"], dtype=float)


class _Mean:
    """Weighted means of several fields, gathered piece by piece."""

    def __init__(self):
        self.sums, self.weights = {}, {}

    def add(self, field, values, weights):
        v = np.asarray(values, dtype=float)
        w = np.broadcast_to(np.asarray(weights, dtype=float), v.shape)
        ok = np.isfinite(v) & np.isfinite(w) & (w > 0)
        if ok.any():
            self.sums[field] = self.sums.get(field, 0.0) + float((v[ok] * w[ok]).sum())
            self.weights[field] = self.weights.get(field, 0.0) + float(w[ok].sum())

    def result(self, fields):
        return [(f, self.sums[f] / self.weights[f]) for f in fields
                if self.weights.get(f, 0.0) > 0]


def _areas(poly):
    sizes = poly.compute_cell_sizes(length=False, volume=False)
    return np.abs(np.asarray(sizes.cell_data["Area"], dtype=float))


def field_values(el):
    """{"fields": [(field, value)], "mean": bool, "n": how many picked, "how": "node" |
    "edge" | "area" | "cell"} for what Select ▾ picked (Part: the selected parts) — or
    None (no solution fields, nothing picked)."""
    sc = el.scene
    fields = solution_fields(sc.model.parts)
    if not fields:
        return None
    k = el.kind
    acc = _Mean()
    if k == "part":
        names = [n for n in sc.selected_parts if n in sc.model.parts]
        if not names:
            return None
        for n in names:
            poly = sc.model.parts[n]
            a = _areas(poly) if poly.n_cells else np.zeros(0)
            for f in fields:
                cv = _at_cells(poly, f)
                if cv is not None and len(cv) == len(a):
                    acc.add(f, cv, a)
        return {"fields": acc.result(fields), "mean": True, "n": len(names), "how": "area"}
    if not el.items:
        return None
    if k == "volume_cell":
        grid = el.volume_grid()
        if grid is None:
            return None
        cells = [int(c) for _, c in el.items if 0 <= int(c) < grid.n_cells]
        for f in fields:
            vals, where = _arrays(grid, f)
            if vals is None:
                continue
            vals = np.asarray(vals, dtype=float)
            for c in cells:
                v = vals[c] if where == "cell" else \
                    np.nanmean(vals[list(grid.get_cell(c).point_ids)])
                acc.add(f, v, 1.0)
        out = acc.result(fields)
        return {"fields": out, "mean": len(cells) > 1, "n": len(cells), "how": "cell"} \
            if out else None
    by_part = {}
    for name, key in el.items:
        if name in sc.model.parts:
            by_part.setdefault(name, []).append(key)
    for name, keys in by_part.items():
        poly = sc.model.parts[name]
        pts = np.asarray(poly.points, dtype=float)
        if k in ("mesh_node", "feature_node"):
            ids = np.asarray([int(i) for i in keys])
            for f in fields:
                pv_ = _at_points(poly, f)
                if pv_ is not None:
                    acc.add(f, pv_[ids], 1.0)
        elif k in ("mesh_edge", "feature_edge"):
            seg = np.vstack([np.asarray([key]).reshape(-1, 2) if k == "mesh_edge"
                             else el.features(name).curve_segments(key) for key in keys])
            seg = seg.astype(int)
            length = np.linalg.norm(pts[seg[:, 1]] - pts[seg[:, 0]], axis=1)
            for f in fields:
                pv_ = _at_points(poly, f)
                if pv_ is not None:
                    acc.add(f, (pv_[seg[:, 0]] + pv_[seg[:, 1]]) / 2, length)
        elif k in ("mesh_cell", "feature_face"):
            cells = np.concatenate([np.asarray([key]) if k == "mesh_cell"
                                    else el.features(name).face_cells(key) for key in keys])
            cells = cells.astype(int)
            a = _areas(poly)[cells]
            for f in fields:
                cv = _at_cells(poly, f)
                if cv is not None:
                    acc.add(f, cv[cells], a)
    out = acc.result(fields)
    if not out:
        return None
    how = {"mesh_node": "node", "feature_node": "node", "mesh_edge": "edge",
           "feature_edge": "edge"}.get(k, "area")
    n = len(el.items)
    return {"fields": out, "mean": how != "node" or n > 1, "n": n, "how": how}
