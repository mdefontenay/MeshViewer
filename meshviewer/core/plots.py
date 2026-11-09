"""Measurements that become plots under the 3D view (F13). No Qt.

A measurement is a plain dict (JSON-friendly, remembered per file):

    {"id": 2, "name": "Root", "kind": "section", ...the kind's own settings}

KINDS lists the ways to measure; each has defaults() and compute(). Only the cross
section for now — a new kind adds an entry here, an editor in gui/panels/plots.py and,
if it draws differently, a plot in gui/pages/plots.py.

Cross section ("section"):
    the visible boundaries cut by a plane normal to X, Y or Z, at a position (None = the
    middle of the model); along the cut, a value — a solution field (cp, Mach…) or a
    position (X, Y, Z: the shape) — against a coordinate in the plane (auto: the longer
    way of the cut), optionally divided by the chord (x/c). One curve per cut loop.

    m = new_measurement("section", "Root", ident=1, model=model)
    r = compute(m, model.parts, visible_names)
    r["curves"]: [{"part", "x" (n,), "y" (n,), "xyz" (n, 3)}, …]
    to_csv(m, r, scale) / read_csv(text) -> reference points [(x, y), …]
"""
from __future__ import annotations

import csv
import io
import re

import numpy as np
import pyvista as pv
from vtkmodules.vtkFiltersCore import vtkStripper

from meshviewer.core.fields import SPEED, field_values, solution_fields
from meshviewer.core.polys import bare

AXES = "xyz"
COORD = "coord:"                     # value "coord:z" = the Z position along the cut


def _bounds(parts, names):
    b = np.array([parts[n].bounds for n in names if parts[n].n_points]).reshape(-1, 6)
    if not len(b):
        return np.zeros(6)
    return np.array([b[:, 0].min(), b[:, 1].max(), b[:, 2].min(), b[:, 3].max(),
                     b[:, 4].min(), b[:, 5].max()])


def values_of(parts):
    """What a cross section can plot: the solution fields, then X / Y / Z."""
    return list(solution_fields(parts)) + [COORD + a for a in AXES]


def value_title(v):
    if v and v.startswith(COORD):
        return v[len(COORD):].upper()
    if v == SPEED:
        return "Speed"
    return {"cp": "cp", "mach": "Mach", "rho": "ρ", "yplus": "y+"}.get((v or "").lower(), v)


# ---- cross section ----------------------------------------------------------------------
def _section_defaults(model):
    names = list(model.parts)
    b = _bounds(model.parts, names).reshape(3, 2)
    span = b[:, 1] - b[:, 0]
    fields = solution_fields(model.parts)
    lower = {f.lower(): f for f in fields}
    field = lower.get("cp") or (fields[0] if fields else COORD + AXES[int(np.argmin(span))])
    return {"axis": AXES[int(np.argmax(span))],          # a wing: across the span
            "pos": None, "normal": None, "value": field, "along": None, "chord": False,
            "flip": None, "ref": None, "show": True}


def in_plane(axis):
    return [a for a in AXES if a != axis]


def _point_values(poly, value):
    """One value per node of the cut surface (cell fields moved to the nodes)."""
    if value.startswith(COORD):
        return np.asarray(poly.points[:, AXES.index(value[len(COORD):])], dtype=float)
    if value == SPEED:
        uvw = [_point_values(poly, k) for k in ("u", "v", "w")]
        if any(c is None for c in uvw):
            return None
        return np.sqrt(sum(c * c for c in uvw))
    vals, where = field_values(poly, value)
    if vals is None:
        return None
    if where == "cell":
        tmp = bare(poly)
        tmp.cell_data["v"] = vals
        return np.asarray(tmp.cell_data_to_point_data().point_data["v"], dtype=float)
    return vals


def _loops(lines):
    """The cut's segments joined into polylines: [point ids in order, …]."""
    s = vtkStripper()
    s.SetInputData(lines)
    s.JoinContiguousSegmentsOn()
    s.Update()
    out = pv.wrap(s.GetOutput())
    if not out.n_cells:
        return out, []
    arr = np.asarray(out.lines)
    loops, i = [], 0
    while i < len(arr):
        n = int(arr[i])
        loops.append(arr[i + 1:i + 1 + n])
        i += n + 1
    return out, loops


def plane_normal(m):
    """Unit normal: the one typed (Advanced), else the axis'."""
    n = m.get("normal")
    if n is not None:
        n = np.asarray(n, dtype=float)
        if np.linalg.norm(n) > 1e-300:
            return n / np.linalg.norm(n)
    n = np.zeros(3)
    n[AXES.index(m["axis"])] = 1.0
    return n


def main_axis(n):
    """The axis the normal is closest to (its Along buttons, its name)."""
    return AXES[int(np.argmax(np.abs(n)))]


def aligned(m):
    """Normal to one of X / Y / Z (not tilted)?"""
    n = plane_normal(m)
    return bool(np.max(np.abs(n)) > 1 - 1e-9)


def position_range(m, parts, names):
    """(lowest, highest) position along the normal that still touches the model."""
    b = _bounds(parts, names).reshape(3, 2)
    corners = np.array([[x, y, z] for x in b[0] for y in b[1] for z in b[2]])
    d = corners @ plane_normal(m)
    return float(d.min()), float(d.max())


def section_plane(m, parts, names):
    """(origin, normal) of the cut. The plane is n·x = pos; pos None = through the
    middle of the visible model. origin: the plane's point nearest that middle."""
    n = plane_normal(m)
    c = _bounds(parts, names).reshape(3, 2).mean(axis=1)
    d = float(n @ c) if m.get("pos") is None else float(m["pos"])
    return c + (d - float(n @ c)) * n, n


def set_plane(m, origin=None, normal=None, parts=None, names=None):
    """Advanced: a new origin and / or normal (the other kept); X / Y / Z buttons follow."""
    o0, n0 = section_plane(m, parts, names)
    o = o0 if origin is None else np.asarray(origin, dtype=float)
    n = n0 if normal is None else np.asarray(normal, dtype=float)
    if np.linalg.norm(n) < 1e-300:
        return
    n = n / np.linalg.norm(n)
    m["axis"] = main_axis(n)
    m["normal"] = None if np.max(np.abs(n)) > 1 - 1e-12 and n[AXES.index(m["axis"])] > 0 \
        else [float(v) for v in n]
    m["pos"] = float(plane_normal(m) @ o)
    if m.get("along") == m["axis"]:
        m["along"] = None


def along_axis(m, curves=None, parts=None, names=None):
    """The coordinate on the plot's x axis: chosen, else the longer way of the cut."""
    axis = main_axis(plane_normal(m))
    if m.get("along") in in_plane(axis):
        return m["along"]
    pts = [c["xyz"] for c in curves or []]
    if not pts:
        return in_plane(axis)[0]
    pts = np.concatenate(pts)
    a, b = in_plane(axis)
    ia, ib = AXES.index(a), AXES.index(b)
    return a if np.ptp(pts[:, ia]) >= np.ptp(pts[:, ib]) else b


def _section_compute(m, parts, names):
    origin, normal = section_plane(m, parts, names)
    value = m.get("value") or COORD + "z"
    curves, cut = [], []
    for n in names:
        part = parts[n]
        if not part.n_cells or not part.GetNumberOfPolys() + part.GetNumberOfStrips():
            continue                                   # lines only: nothing to cut
        vals = _point_values(part, value)
        if vals is None:
            continue
        surf = bare(part)                              # VTK shares it; no NumPy in between
        surf.point_data["v"] = np.array(vals, dtype=float)
        sl = surf.slice(normal=normal, origin=origin)
        if not sl.n_points:
            continue
        out, loops = _loops(sl)
        cut.append(out)
        for ids in loops:
            if len(ids) < 2:
                continue
            xyz = np.asarray(out.points[ids], dtype=float)
            curves.append({"part": n, "xyz": xyz,
                           "y": np.asarray(out.point_data["v"][ids], dtype=float)})
    along = along_axis(m, curves)
    k = AXES.index(along)
    lo = min((c["xyz"][:, k].min() for c in curves), default=0.0)
    hi = max((c["xyz"][:, k].max() for c in curves), default=1.0)
    chord = hi - lo
    for c in curves:
        x = c["xyz"][:, k]
        c["x"] = (x - lo) / chord if m.get("chord") and chord > 0 else x
    flip = m.get("flip")
    if flip is None:                                    # cp: negative up, as usual
        flip = value.lower() == "cp"
    lines = pv.merge(cut) if len(cut) > 1 else (cut[0] if cut else None)
    return {"curves": curves, "along": along, "value": value, "chord": chord,
            "chord_on": bool(m.get("chord")) and chord > 0, "flip": bool(flip),
            "origin": origin, "normal": normal, "lines": lines,
            "x0": lo, "empty": not curves}


KINDS = {
    "section": {"title": "Cross section", "defaults": _section_defaults,
                "compute": _section_compute},
}


def new_measurement(kind, name, ident, model):
    return {"id": int(ident), "name": name, "kind": kind, **KINDS[kind]["defaults"](model)}


def compute(m, parts, names):
    """The plot of one measurement over the boundaries `names` (the visible ones)."""
    names = [n for n in names if n in parts]
    return KINDS[m["kind"]]["compute"](m, parts, names)


# ---- CSV ---------------------------------------------------------------------------------
def to_csv(m, r, scale=1.0, unit="", value_unit=None):
    """The curves, one row per point: part, the plot's x and y, then X, Y, Z.
    value_unit: (convert, label) for a field's values (Results ▸ Shown in), or None."""
    coord = r["value"].startswith(COORD)
    xname = "x/c" if r.get("chord_on") else f"{r['along']} ({unit})" if unit else r["along"]
    conv, vlabel = (lambda v: v * scale, unit) if coord else (value_unit or (lambda v: v, ""))
    yname = value_title(r["value"]) + (f" ({vlabel})" if vlabel else "")
    buf = io.StringIO()
    w = csv.writer(buf)
    xyz_unit = f" ({unit})" if unit else ""
    w.writerow(["part", xname, yname, f"X{xyz_unit}", f"Y{xyz_unit}", f"Z{xyz_unit}"])
    xs = 1.0 if r.get("chord_on") else scale
    for c in r["curves"]:
        ys = np.asarray(conv(c["y"]), dtype=float)
        for x, y, p in zip(c["x"], ys, c["xyz"]):
            w.writerow([c["part"], f"{x * xs:.9g}", f"{y:.9g}",
                        *(f"{v * scale:.9g}" for v in p)])
        w.writerow([])                                  # a blank line between loops
    return buf.getvalue()


_NUM = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eEdD][+-]?\d+)?$")


def read_csv(text):
    """Reference points from a CSV / text file: the first two numbers of every row that
    has at least two (header and comment lines are skipped). , ; tab or spaces."""
    pts = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line[0] in "#%!":
            continue
        cells = [c for c in re.split(r"[,;\t ]+", line) if c]
        nums = [float(c.replace("d", "e").replace("D", "e")) for c in cells if _NUM.match(c)]
        if len(nums) >= 2:
            pts.append((nums[0], nums[1]))
    return pts
