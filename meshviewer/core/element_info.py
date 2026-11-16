"""What Measure Selected says about a picked node, edge, face or cell: the geometry
behind it. No Qt, no drawing.

    path = ordered_path(segments)            # mesh edges of a feature edge, in order
    straight(path), planar(path)             # a line? (its direction) a plane? (its normal)
    fit_circle(path)                         # a circle / arc: center, radius, normal
    point_at_length(path, 0.5)               # the midpoint along it
    dihedral(n1, n2)                         # the angle between two faces at an edge
"""
from __future__ import annotations

import numpy as np

REL_TOL = 1e-4          # straight / planar / round: points this close, × the edge's size
CELL_TYPES = {10: "Tetrahedron", 12: "Hexahedron", 13: "Prism", 14: "Pyramid",
              42: "Polyhedron", 5: "Triangle", 9: "Quad", 7: "Polygon"}


def ordered_path(seg, pts):
    """(n, 3) points along mesh edges `seg` (k, 2 point ids) from one end to the other
    (a closed loop ends where it starts). Points at the same place are one."""
    seg = np.asarray(seg, dtype=np.int64)
    if not len(seg):
        return np.zeros((0, 3))
    pts = np.asarray(pts, dtype=float)
    span = float(np.ptp(pts[seg.reshape(-1)], axis=0).max() or 1.0)
    key = np.round(pts[seg.reshape(-1)] / (span * 1e-9)).astype(np.int64)
    _, place = np.unique(key, axis=0, return_inverse=True)
    place = place.reshape(-1, 2)
    first = {}
    for p, i in zip(place.reshape(-1), seg.reshape(-1)):
        first.setdefault(int(p), int(i))
    nbr = {}
    for a, b in place:
        nbr.setdefault(int(a), []).append(int(b))
        nbr.setdefault(int(b), []).append(int(a))
    ends = [p for p, n in nbr.items() if len(n) == 1]
    start = ends[0] if ends else int(place[0, 0])
    order, prev, cur = [start], None, start
    for _ in range(len(seg)):
        nxt = [q for q in nbr[cur] if q != prev]
        if not nxt or (nxt[0] == start and len(order) > 2):
            if nxt and nxt[0] == start:
                order.append(start)                     # closed: back to the start
            break
        prev, cur = cur, nxt[0]
        order.append(cur)
    return pts[[first[p] for p in order]]


def length(path):
    return float(np.linalg.norm(np.diff(path, axis=0), axis=1).sum()) if len(path) > 1 else 0.0


def point_at_length(path, frac=0.5):
    """The point `frac` of the way along the path."""
    if len(path) < 2:
        return path[0] if len(path) else np.zeros(3)
    d = np.linalg.norm(np.diff(path, axis=0), axis=1)
    cum = np.r_[0.0, np.cumsum(d)]
    target = frac * cum[-1]
    i = int(np.clip(np.searchsorted(cum, target) - 1, 0, len(d) - 1))
    t = (target - cum[i]) / d[i] if d[i] > 0 else 0.0
    return path[i] + t * (path[i + 1] - path[i])


def _size(path):
    return float(np.linalg.norm(np.ptp(path, axis=0))) or 1.0


def straight(path):
    """The unit direction from the first point to the last when every point is on
    that line, else None."""
    if len(path) < 2:
        return None
    d = path[-1] - path[0]
    n = np.linalg.norm(d)
    if n <= 0:
        return None
    d = d / n
    off = path - path[0]
    dist = np.linalg.norm(off - np.outer(off @ d, d), axis=1)
    return d if dist.max() <= REL_TOL * _size(path) else None


def planar(path):
    """The unit normal of the plane every point lies in (not a straight line), else None."""
    if len(path) < 3:
        return None
    c = path.mean(axis=0)
    _, s, vt = np.linalg.svd(path - c)
    if s[1] <= REL_TOL * max(s[0], 1e-300):         # all on a line
        return None
    n = vt[2]
    return n if np.abs((path - c) @ n).max() <= REL_TOL * _size(path) else None


def fit_circle(path):
    """{"center", "radius", "normal", "closed"} when the points lie on one circle
    (an arc or a whole circle), else None."""
    pts = path[:-1] if len(path) > 3 and np.allclose(path[0], path[-1]) else path
    if len(pts) < 3:
        return None
    n = planar(pts)
    if n is None:
        return None
    c0 = pts.mean(axis=0)
    u = pts[0] - c0
    u -= (u @ n) * n
    u /= np.linalg.norm(u) or 1.0
    v = np.cross(n, u)
    x, y = (pts - c0) @ u, (pts - c0) @ v
    a = np.column_stack([2 * x, 2 * y, np.ones_like(x)])     # x² + y² = 2ax + 2by + c
    sol, *_ = np.linalg.lstsq(a, x * x + y * y, rcond=None)
    cx, cy, k = sol
    r2 = k + cx * cx + cy * cy
    if r2 <= 0:
        return None
    r = float(np.sqrt(r2))
    dev = np.abs(np.hypot(x - cx, y - cy) - r)
    if dev.max() > REL_TOL * 10 * r or r > 1e3 * _size(pts):   # a line, nearly
        return None
    closed = bool(np.allclose(path[0], path[-1]))
    return {"center": c0 + cx * u + cy * v, "radius": r, "normal": n, "closed": closed}


def dihedral(n1, n2):
    """The angle between two faces meeting at an edge (degrees): 180 = flat, 90 = a
    box's corner; their normals pointing the same way out."""
    n1 = np.asarray(n1, dtype=float)
    n2 = np.asarray(n2, dtype=float)
    c = float(n1 @ n2 / ((np.linalg.norm(n1) * np.linalg.norm(n2)) or 1.0))
    return 180.0 - float(np.degrees(np.arccos(np.clip(c, -1.0, 1.0))))


def cell_type_name(vtk_type):
    return CELL_TYPES.get(int(vtk_type), f"Cell type {int(vtk_type)}")
