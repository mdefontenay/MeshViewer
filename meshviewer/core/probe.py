"""Probe: solution fields at a point, along a line or over an area — at the step shown, or
at every time step (OpenFOAM). No Qt.

A probe's target (its dict "target", remembered with the file):

    {"kind": "point", "how": "xyz",   "xyz": [x, y, z]}        a point in the model
    {"kind": "point", "how": "nodes", "nodes": [[part, id]…]}  mesh / feature nodes
    {"kind": "point", "how": "cells", "cells": [id…]}          volume cells
    {"kind": "line",  "how": "edges", "edges": [[part, a, b]…]}  mesh / feature edges
    {"kind": "line",  "how": "through", "points": [[x, y, z]…]}  a polyline through the
                                                               cells (between picked nodes)
    {"kind": "area",  "how": "faces", "faces": [[part, [id…]]…]} faces, feature faces
    {"kind": "area",  "how": "parts", "parts": [part…]}        whole boundaries

`sampler(target, parts, volume, transform)` finds the cells once (the mesh doesn't move
between steps) and turns the target into lookups: per source (a part, or VOLUME: the
cells), cell ids with weights and node ids with weights — the cell's value is taken when
the source carries the field on its cells (OpenFOAM: its own value), else its nodes'.
Weights: a point 1, an edge its length, a face its area (lines and areas: length- and
area-weighted means). `Sampler.value(data, field)` -> (mean, min, max) for one step;
`series(sampler, step_data, field, n)` the same at every step, read from the arrays the
case keeps (core/mesh/openfoam.py `step_arrays`, `volume_arrays`): array lookups only.
"""
from __future__ import annotations

from dataclasses import dataclass, field as _field

import numpy as np

from meshviewer.core.field_kinds import SPEED
from meshviewer.core.fields import VELOCITY

VOLUME = None                            # the source of volume cells
THROUGH = 48                             # points sampled along each piece of a polyline
KINDS = ("point", "line", "area")


@dataclass
class _Lookup:
    source: object                       # a part's name, or VOLUME
    cells: np.ndarray                    # cell ids …
    cell_w: np.ndarray                   # … and their weights
    nodes: np.ndarray                    # node ids …
    node_w: np.ndarray                   # … and their weights


@dataclass
class Sampler:
    lookups: list = _field(default_factory=list)
    marker: dict = _field(default_factory=dict)   # what the 3D view draws (render/probes)
    why: str = ""                        # why nothing is probed ("" when something is)

    @property
    def ok(self):
        return bool(self.lookups)

    def value(self, data, field):
        """(mean, min, max) of `field` with data(source) -> (point arrays, cell arrays)
        (mappings of name -> values), or None where no source carries it."""
        vals, wts = [], []
        for lk in self.lookups:
            point, cell = data(lk.source)
            v = _take(cell, field, lk.cells) if len(lk.cells) else None
            w = lk.cell_w
            if v is None:
                v, w = _take(point, field, lk.nodes), lk.node_w
            if v is not None and len(v):
                ok = np.isfinite(v)
                vals.append(v[ok])
                wts.append(w[ok])
        if not vals:
            return None
        v, w = np.concatenate(vals), np.concatenate(wts)
        if not len(v):
            return None
        mean = float(np.sum(v * w) / np.sum(w)) if np.sum(w) > 0 else float(np.mean(v))
        return mean, float(v.min()), float(v.max())

    def sources(self):
        return {lk.source for lk in self.lookups}


def _take(arrays, field, ids):
    """arrays[field][ids] (speed: from the velocity's components), or None."""
    if arrays is None:
        return None
    if field == SPEED:
        names = next((t for t in VELOCITY if all(k in arrays for k in t)), None)
        if names is None:
            return None
        comps = [np.asarray(arrays[k], dtype=float)[ids] for k in names]
        return np.sqrt(sum(c * c for c in comps))
    if field not in arrays:
        return None
    return np.asarray(arrays[field], dtype=float)[ids]


def series(sampler, step_data, field, n, stop=None):
    """(mean, min, max) arrays (n,) of `field` at every step; step_data(i) -> the data
    function of step i (as Sampler.value takes). NaN where a step lacks the field. None
    when stop() says a newer read took over."""
    out = np.full((3, n), np.nan)
    for i in range(n):
        if stop is not None and stop():
            return None
        got = sampler.value(step_data(i), field)
        if got is not None:
            out[:, i] = got
    return out


# ---- finding cells ------------------------------------------------------------------------
class Locator:
    """Which cell holds a point: a volume cell (3D files with cells), else the nearest
    face of a boundary (surfaces, 2D cells). VTK's static locators, made once per
    dataset and kept (`cache`: a dict the caller keeps for the file)."""

    def __init__(self, parts, volume=None, transform=None, cache=None):
        self.parts, self.volume = parts, volume
        self.r, self.t = transform if transform is not None else (np.eye(3), np.zeros(3))
        self.cache = {} if cache is None else cache

    def _locator(self, ds):
        key = (id(ds), ds.n_cells)
        loc = self.cache.get(key)
        if loc is None:
            from vtkmodules.vtkCommonDataModel import vtkStaticCellLocator
            loc = vtkStaticCellLocator()
            loc.SetDataSet(ds)
            loc.BuildLocator()
            self.cache[key] = loc
        return loc

    def find(self, xyz):
        """(source, cell id, the point on it) for a point of the model as shown."""
        p = np.asarray(xyz, dtype=float)
        if self.volume is not None:                   # the cells: in the file's frame
            q = np.asarray(self.r).T @ (p - np.asarray(self.t))
            c = self._locator(self.volume).FindCell(q)
            if c >= 0:
                return VOLUME, int(c), p
        best = None
        for n, part in self.parts.items():
            if not (part.GetNumberOfPolys() or part.GetNumberOfStrips()):
                continue
            from vtkmodules.vtkCommonCore import mutable
            closest, cell, sub, d2 = [0.0, 0.0, 0.0], mutable(0), mutable(0), mutable(0.0)
            self._locator(part).FindClosestPoint(p, closest, cell, sub, d2)
            if int(cell) >= 0 and (best is None or float(d2) < best[0]):
                best = (float(d2), n, int(cell), np.array(closest))
        return None if best is None else (best[1], best[2], best[3])


# ---- the lookups of a target ---------------------------------------------------------------
def _cells_of_node(ds, i):
    return np.asarray(ds.point_cell_ids(int(i)), dtype=np.int64)


def _nodes_of(ds, cells):
    """(the cells' node ids, joined; how many each) — from the connectivity arrays, no
    loop over cells (a whole boundary: thousands)."""
    from vtkmodules.util.numpy_support import vtk_to_numpy
    if ds.IsA("vtkUnstructuredGrid"):
        ca = ds.GetCells()
    else:
        ca = ds.GetPolys() if ds.GetNumberOfPolys() else ds.GetLines()
    off = np.asarray(vtk_to_numpy(ca.GetOffsetsArray()), dtype=np.int64)
    conn = np.asarray(vtk_to_numpy(ca.GetConnectivityArray()), dtype=np.int64)
    n = off[cells + 1] - off[cells]
    at = np.repeat(off[cells], n) + np.arange(n.sum()) - np.repeat(np.cumsum(n) - n, n)
    return conn[at], n


def _point_lookup(source, ds, cells, w=None):
    """Lookups of cells: each its weight (w: an array, default 1), its nodes sharing it."""
    cells = np.asarray(cells, dtype=np.int64)
    w = np.ones(len(cells)) if w is None else np.asarray(w, dtype=float)
    nodes, n = _nodes_of(ds, cells)
    return _Lookup(source, cells, w, nodes, np.repeat(w / np.maximum(n, 1), n))


def _merge(lookups):
    """Lookups of one source joined into one (the same cell or node may come twice)."""
    by = {}
    for lk in lookups:
        by.setdefault(lk.source, []).append(lk)
    return [_Lookup(s, *(np.concatenate([getattr(lk, a) for lk in group])
                         for a in ("cells", "cell_w", "nodes", "node_w")))
            for s, group in by.items()]


def sampler(target, parts, volume=None, transform=None, cache=None):
    """The Sampler of a target dict (see above). volume: the cells as read from the file
    (not moved by Edit; transform = (R, t): how the parts were moved)."""
    kind, how = target.get("kind"), target.get("how")
    out = Sampler()
    try:
        if kind == "point" and how == "xyz":
            out = _at_points(parts, volume, transform, cache, [target["xyz"]])
            out.marker = {"points": np.array([target["xyz"]], dtype=float),
                          "label_at": np.array(target["xyz"], dtype=float)}
        elif kind == "point" and how == "nodes":
            looks, pts = [], []
            for n, i in target["nodes"]:
                ds = parts.get(n)
                if ds is None or not 0 <= int(i) < ds.n_points:
                    continue
                cells = _cells_of_node(ds, i)
                looks.append(_Lookup(n, cells, np.full(len(cells), 1.0 / max(len(cells), 1)),
                                     np.array([int(i)]), np.array([1.0])))
                pts.append(np.asarray(ds.points[int(i)], dtype=float))
            out.lookups = _merge(looks)
            if pts:
                out.marker = {"points": np.array(pts), "label_at": np.mean(pts, axis=0)}
        elif kind == "point" and how == "cells":
            cells = [int(c) for c in target["cells"]
                     if volume is not None and 0 <= int(c) < volume.n_cells]
            if cells:
                out.lookups = [_point_lookup(VOLUME, volume, cells)]
                r, t = transform if transform is not None else (np.eye(3), np.zeros(3))
                pts = np.array([np.asarray(volume.get_cell(c).points).mean(axis=0)
                                for c in cells]) @ np.asarray(r).T + np.asarray(t)
                out.marker = {"points": pts, "label_at": pts.mean(axis=0)}
        elif kind == "line" and how == "edges":
            looks, segs = [], []
            for n, a, b in target["edges"]:
                ds = parts.get(n)
                if ds is None or max(int(a), int(b)) >= ds.n_points:
                    continue
                pa, pb = (np.asarray(ds.points[int(k)], dtype=float) for k in (a, b))
                L = float(np.linalg.norm(pb - pa))
                both = np.intersect1d(_cells_of_node(ds, a), _cells_of_node(ds, b))
                looks.append(_Lookup(n, both, np.full(len(both), L / max(len(both), 1)),
                                     np.array([int(a), int(b)]), np.array([L / 2, L / 2])))
                segs.append((pa, pb))
            out.lookups = _merge(looks)
            if segs:
                seg = np.array(segs)
                out.marker = {"lines": seg, "label_at": seg[len(seg) // 2].mean(axis=0)}
        elif kind == "line" and how == "through":
            pts = np.asarray(target["points"], dtype=float)
            samples = np.vstack([np.linspace(pts[k], pts[k + 1], THROUGH, endpoint=False)
                                 for k in range(len(pts) - 1)] + [pts[-1:]])
            out = _at_points(parts, volume, transform, cache, samples)
            out.marker = {"lines": np.stack([pts[:-1], pts[1:]], axis=1),
                          "points": pts, "label_at": pts.mean(axis=0)}
        elif kind == "area":
            faces = target["faces"] if how == "faces" else \
                [[n, list(range(parts[n].n_cells))] for n in target["parts"] if n in parts]
            looks, drawn = [], []
            for n, ids in faces:
                ds = parts.get(n)
                if ds is None:
                    continue
                ids = np.asarray([i for i in ids if 0 <= int(i) < ds.n_cells], dtype=np.int64)
                if not len(ids):
                    continue
                lines = not ds.GetNumberOfPolys()          # (a 2D case's boundary: lines)
                sizes = ds.extract_cells(ids).compute_cell_sizes(
                    length=lines, area=not lines, volume=False)
                w = np.abs(np.asarray(sizes.cell_data["Length" if lines else "Area"],
                                      dtype=float))
                looks.append(_point_lookup(n, ds, ids, w))
                drawn.append((n, ids))
            out.lookups = _merge(looks)
            if drawn:
                centers = np.vstack([np.asarray(parts[n].extract_cells(ids).points)
                                     for n, ids in drawn])
                out.marker = {"faces": drawn, "label_at": centers.mean(axis=0)}
    except (KeyError, TypeError, ValueError, IndexError) as exc:
        out = Sampler(why=f"This probe's target is no longer in the model ({exc}).")
    if not out.lookups and not out.why:
        out.why = "Nothing of the model is there: pick on it, or type a point inside."
    return out


def _at_points(parts, volume, transform, cache, points):
    """Lookups of the cells holding each point (equal weights)."""
    loc = Locator(parts, volume, transform, cache)
    looks = []
    for p in np.atleast_2d(points):
        got = loc.find(p)
        if got is None:
            continue
        src, cell, _q = got
        ds = volume if src is VOLUME else parts[src]
        looks.append(_point_lookup(src, ds, [cell]))
    return Sampler(lookups=_merge(looks))


# ---- writing ---------------------------------------------------------------------------------
def csv_text(head, rows):
    """A CSV table: head (column names), rows (tuples of numbers or text)."""
    def cell(v):
        if isinstance(v, (float, np.floating)):
            return "" if not np.isfinite(v) else f"{float(v):.10g}"
        return str(v)
    return "\n".join([",".join(head)] + [",".join(cell(v) for v in r) for r in rows]) + "\n"
