"""STL reader (.stl, binary or ASCII).

CAD format. Returns {part_name: pv.PolyData}.
  * Binary STL      -> one part, named after the file.
  * ASCII STL       -> one part per 'solid <name> ... endsolid' block, so
                       multi-body exports keep their bodies separate.
No extra packages needed (pyvista + numpy only).
"""
from __future__ import annotations

import re

import numpy as np
import pyvista as pv

_SOLID_RE = re.compile(rb"^[ \t]*solid\b[ \t]*([^\r\n]*)(.*?)^[ \t]*endsolid\b", re.M | re.S)
_VERTEX_RE = re.compile(rb"vertex\s+(\S+)\s+(\S+)\s+(\S+)")


def _is_binary(path, data_head: bytes, size: int) -> bool:
    # Binary layout: 80-byte header, uint32 count, 50 bytes per triangle.
    # Checking the size is reliable; the 'solid' keyword is not (some binary
    # exporters start their header with 'solid' too).
    if size < 84:
        return False
    n = int(np.frombuffer(data_head[80:84], dtype="<u4")[0])
    return size == 84 + 50 * n


def _triangles_to_poly(verts: np.ndarray) -> pv.PolyData:
    n_tri = len(verts) // 3
    faces = np.empty((n_tri, 4), dtype=np.int64)
    faces[:, 0] = 3
    faces[:, 1:] = np.arange(n_tri * 3, dtype=np.int64).reshape(n_tri, 3)
    # STL repeats every vertex per triangle; clean() merges them so shading
    # and feature edges work.
    return pv.PolyData(verts[: n_tri * 3], faces=faces.ravel()).clean()


def read_stl(path, debug=True):
    size = path.stat().st_size
    with open(path, "rb") as f:
        head = f.read(84)

    if _is_binary(path, head, size):
        if debug:
            print("  binary STL")
        poly = pv.read(str(path)).clean()
        return {path.stem: poly} if poly.n_cells else {}

    if debug:
        print("  ASCII STL")
    data = path.read_bytes()
    parts = {}
    for k, m in enumerate(_SOLID_RE.finditer(data), 1):
        verts = _VERTEX_RE.findall(m.group(2))
        if not verts:
            continue
        verts = np.array(verts).astype(np.float64)
        name = m.group(1).decode("utf-8", errors="replace").strip() or f"solid_{k}"
        if name in parts:
            name = f"{name} ({k})"
        parts[name] = _triangles_to_poly(verts)
        if debug:
            print(f"  {name}: {parts[name].n_cells} triangles")

    # Single unnamed body -> use the file name, like binary STL.
    if len(parts) == 1 and next(iter(parts)).startswith("solid_"):
        parts = {path.stem: next(iter(parts.values()))}
    return parts
