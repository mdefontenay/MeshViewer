"""Tecplot ASCII results (.dat), as FUN3D writes them
(project_tec_boundary.dat): the surface of each boundary with the solution at its nodes.

    title="tecplot geometry and solution file"
    variables = x y z rho u v w p mach cp yplus
    zone t="boundary 1 WING", solutiontime= 0.5E+03, strandid=1001, i=40388, j=80574, f=feblock
      <all x> <all y> <all z> <all rho> ... (BLOCK: one variable after the other)
      <j lines of 3 or 4 node numbers>   (quads with a repeated last node are triangles)

Returns {boundary name: pv.PolyData}, each with every variable but x, y, z in its
point data (cell data for variables marked cell-centered). Also reads the newer header
form (nodes= / elements= / datapacking= / zonetype=) and POINT packing. The binary
.plt / .szplt files are not read: write ASCII from the solver (FUN3D does by default).
When a boundary appears more than once (time steps of one strand), the last one is kept.
"""
from __future__ import annotations

import re

import numpy as np
import pyvista as pv

_ZONE = re.compile(r"^[ \t]*zone\b", re.I | re.M)
_NUMBER_LINE = re.compile(r"^[ \t]*[-+.\d]", re.M)


def _keyval(header, *keys):
    """The value of the first key found in a zone header (case-insensitive)."""
    for k in keys:
        m = re.search(rf"(?<![a-z]){k}\s*=\s*(\"[^\"]*\"|\([^)]*\)|[^,\s]+)", header, re.I)
        if m:
            return m.group(1).strip('"')
    return None


def _variables(text):
    m = re.search(r"variables\s*=\s*(.*?)(?=^[ \t]*(zone|title|datasetauxdata)\b)", text,
                  re.I | re.S | re.M)
    if not m:
        raise ValueError("not a Tecplot ASCII file (no VARIABLES line)")
    raw = m.group(1)
    names = re.findall(r'"([^"]*)"', raw) or re.split(r"[\s,]+", raw.strip())
    return [n.strip() for n in names if n.strip()]


def _cell_centered(header, nvar):
    """Variables (0-based) stored per element: VARLOCATION=([4-11]=CELLCENTERED)."""
    out = set()
    m = re.search(r"varlocation\s*=\s*\((.*?)\)\s*(?:,|$)", header, re.I | re.S)
    if not m:
        return out
    for group, where in re.findall(r"\[([^\]]*)\]\s*=\s*(\w+)", m.group(1)):
        if where.lower() != "cellcentered":
            continue
        for part in group.split(","):
            a, _, b = part.partition("-")
            lo, hi = int(a), int(b or a)
            out.update(range(lo - 1, min(hi, nvar)))
    return out


def _name(title, taken):
    """Zone title "boundary 1 WING" -> "WING" (the name after FUN3D's "boundary N")."""
    t = (title or "zone").strip()
    m = re.match(r"boundary\s+\d+\s+(.*)$", t, re.I)
    name = (m.group(1).strip() if m and m.group(1).strip() else t) or "zone"
    return name


def _zone(header, body, names):
    nvar = len(names)
    n = _keyval(header, "nodes", "n", "i")
    e = _keyval(header, "elements", "e", "j")
    if n is None or e is None:
        raise ValueError("only finite-element zones are read (nodes and elements)")
    n, e = int(float(n)), int(float(e))
    packing = (_keyval(header, "datapacking", "f") or "feblock").lower()
    point = "point" in packing
    cells_at = _cell_centered(header, nvar)
    if "d" in body or "D" in body:                       # Fortran 1.0D+00
        body = body.replace("D", "E").replace("d", "e")
    vals = np.array(body.split(), dtype=float)
    sizes = [e if k in cells_at else n for k in range(nvar)]
    used = sum(sizes)
    if len(vals) < used + e * 3:
        raise ValueError(f"zone is short: {len(vals):,} numbers for {used:,} values "
                         f"and {e:,} elements")
    data = {}
    if point and not cells_at:
        block = vals[:n * nvar].reshape(n, nvar)
        for k, nm in enumerate(names):
            data[nm] = block[:, k]
    else:
        at = 0
        for k, nm in enumerate(names):
            data[nm] = vals[at:at + sizes[k]]
            at += sizes[k]
    conn = vals[used:].astype(np.int64)
    per = len(conn) // e if e else 0
    if per not in (3, 4) or per * e != len(conn):
        zt = (_keyval(header, "zonetype", "et") or "").lower()
        per = 3 if "tri" in zt else 4
        conn = conn[:per * e]
    conn = conn.reshape(e, per) - 1
    lower = {k.lower(): k for k in names}
    try:
        pts = np.column_stack([data[lower["x"]], data[lower["y"]], data[lower["z"]]])
    except KeyError as exc:
        raise ValueError("the file has no x, y, z variables") from exc
    if per == 4:
        tri = conn[:, 2] == conn[:, 3]
        faces = [np.column_stack([np.full(int(tri.sum()), 3), conn[tri, :3]]).ravel(),
                 np.column_stack([np.full(int((~tri).sum()), 4), conn[~tri]]).ravel()]
        order = np.concatenate([np.flatnonzero(tri), np.flatnonzero(~tri)])
        poly = pv.PolyData(pts, faces=np.concatenate(faces))
    else:
        order = np.arange(e)
        poly = pv.PolyData(pts, faces=np.column_stack([np.full(e, 3), conn]).ravel())
    for k, nm in enumerate(names):
        if nm.lower() in ("x", "y", "z"):
            continue
        if k in cells_at:
            poly.cell_data[nm] = data[nm][order]
        else:
            poly.point_data[nm] = data[nm]
    return poly


def read_tecplot(path, debug=True):
    text = open(path, "r", errors="replace").read()
    names = _variables(text)
    starts = [m.start() for m in _ZONE.finditer(text)]
    if not starts:
        raise ValueError("no ZONE in this Tecplot file")
    parts, strands = {}, {}
    for z, s in enumerate(starts):
        chunk = text[s:starts[z + 1] if z + 1 < len(starts) else len(text)]
        m = _NUMBER_LINE.search(chunk)
        if not m:
            continue
        header, body = chunk[:m.start()], chunk[m.start():]
        title = _keyval(header, "t") or f"zone {z + 1}"
        name = _name(title, parts)
        poly = _zone(header, body, names)
        key = name                                   # same boundary again: a later time
        if key in strands:
            parts.pop(strands[key], None)
        base, k = name, 2
        while name in parts:
            name = f"{base} {k}"
            k += 1
        parts[name] = poly
        strands[key] = name
    if debug:
        fields = [nm for nm in names if nm.lower() not in ("x", "y", "z")]
        print(f"  {len(parts)} boundaries · fields: {', '.join(fields)}")
    return parts
