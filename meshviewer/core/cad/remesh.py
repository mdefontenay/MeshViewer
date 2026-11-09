"""Better triangles for one CAD face: no fans of thin slivers.

OpenCASCADE meshes a face from its edges and adds points inside only where the
surface curves; the triangles between them can be long fans of needles (a wing
surface, a symmetry plane around a wing root). Here, in the face's (u, v) parameters
stretched to match real lengths (a metric fitted on the triangles' edges):
  1. points are seeded inside, with a size that grows smoothly away from the edges
     (a quadtree), where the face has room for them;
  2. every inner edge is flipped until the triangulation is Delaunay (Lawson), which
     turns fans into well-shaped triangles.
The face's edge points and OpenCASCADE's inner points are all kept, so neighbouring
faces still join up and the curvature is still followed. If the result is not better,
the face keeps OpenCASCADE's triangles.
"""
from __future__ import annotations

import numpy as np

MIN_ANGLE = 12.0            # degrees: thinner triangles count as thin
FAN = 5                     # thin triangles meeting at a point: a fan, redo the face
GRADING = 1.0               # size grows by this × the distance from the edges
MAX_NEW = 3000              # points added per face, at most
CAP_FRACTION = 6.0          # no point further than face size / this from another
SEED_NODES = 1500           # faces with more points only get the flips (fast)


def min_angles(p):
    """Smallest angle (degrees) of each triangle, p: (n, 3, 3)."""
    e = [p[:, 1] - p[:, 0], p[:, 2] - p[:, 1], p[:, 0] - p[:, 2]]
    out = np.full(len(p), 180.0)
    for a, b in ((0, 2), (1, 0), (2, 1)):
        u, v = e[a], -e[b]
        c = (u * v).sum(1) / (np.linalg.norm(u, axis=1) * np.linalg.norm(v, axis=1) + 1e-300)
        out = np.minimum(out, np.degrees(np.arccos(np.clip(c, -1, 1))))
    return out


def fan_excess(p3, tris):
    """How fan-like a mesh is: thin triangles piled at the same points (beyond 2 each)."""
    thin = min_angles(p3[tris]) < MIN_ANGLE
    if not thin.any():
        return 0
    count = np.bincount(tris[thin].ravel(), minlength=len(p3))
    return int(np.maximum(count - 2, 0).sum())


def has_fans(p3, tris):
    """True when FAN or more thin triangles meet at one point (a fan). Long faces cut in
    a few long triangles (a cylinder's side, a gear tooth) have thin triangles too, but
    look fine and are left alone."""
    thin = min_angles(p3[tris]) < MIN_ANGLE
    if not thin.any():
        return False
    count = np.bincount(tris[thin].ravel(), minlength=len(p3))
    return bool(count.max() >= FAN)


def _edges(tris):
    e = np.sort(np.vstack([tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]]]), axis=1)
    u, n = np.unique(e, axis=0, return_counts=True)
    return u[n == 1]                                   # boundary: used by one triangle


def _inside(q, a, b):
    """Crossing-number test: points q (m, 2) inside the region bounded by segments a-b."""
    inside = np.zeros(len(q), bool)
    for s in range(0, len(a), 2000):
        a1, b1 = a[s:s + 2000], b[s:s + 2000]
        y0, y1 = a1[:, 1][None], b1[:, 1][None]
        qy, qx = q[:, 1][:, None], q[:, 0][:, None]
        cross = (y0 > qy) != (y1 > qy)
        with np.errstate(divide="ignore", invalid="ignore"):
            x = a1[:, 0][None] + (qy - y0) * (b1[:, 0] - a1[:, 0])[None] / (y1 - y0)
        x = np.where(cross, x, np.inf)
        inside ^= (np.count_nonzero(cross & (qx < x), axis=1) % 2).astype(bool)
    return inside


def _size(q, bp, bl, cap=np.inf):
    """Target size at points q: min over edge points of (local edge length + GRADING × distance)."""
    out = np.full(len(q), np.inf)
    for s in range(0, len(bp), 1500):
        d = np.linalg.norm(q[:, None] - bp[None, s:s + 1500], axis=2)
        out = np.minimum(out, (bl[None, s:s + 1500] + GRADING * d).min(1))
    return np.minimum(out, cap)                      # big open areas get points too


def _seeds(lo, hi, bp, bl, factor, cap=np.inf):
    """Quadtree cell centres where the cell is about the target size."""
    side = float(max(hi - lo))
    cen, size, out = np.array([(lo + hi) / 2]), np.array([side]), []
    for _ in range(40):
        if not len(cen):
            break
        h = _size(cen, bp, bl, cap) * factor
        split = size > h
        out.append(cen[~split])
        c, sz = cen[split], size[split] / 2
        off = np.array([[-1, -1], [1, -1], [-1, 1], [1, 1]]) * (sz[:, None, None] / 2)
        cen = (c[:, None, :] + off).reshape(-1, 2)
        size = np.repeat(sz, 4)
        if len(cen) > 4 * MAX_NEW * 16:
            return None
    return np.vstack(out) if out else np.empty((0, 2))


def _seg_dist(q, a, b):
    """Distance from each point q (m, 2) to the nearest segment a-b."""
    out = np.full(len(q), np.inf)
    for s in range(0, len(a), 1500):
        a1, d = a[s:s + 1500], b[s:s + 1500] - a[s:s + 1500]
        L = (d ** 2).sum(1) + 1e-300
        t = np.clip(((q[:, None] - a1[None]) * d[None]).sum(2) / L[None], 0, 1)
        out = np.minimum(out, np.linalg.norm(q[:, None] - (a1[None] + t[..., None] * d[None]), axis=2).min(1))
    return out


def _insert(x, tris, seeds):
    """Split the triangle holding each seed in three. x (n, 2), tris (m, 3) CCW.
    Returns (points, triangles); seeds that land outside or on an edge are left out."""
    pts = np.vstack([x, seeds])
    m = len(tris)
    T = np.zeros((m + 2 * len(seeds), 3), np.int64)
    T[:m] = tris
    for k in range(len(seeds)):
        p = len(x) + k
        q = pts[p]
        A, B, C = pts[T[:m, 0]], pts[T[:m, 1]], pts[T[:m, 2]]
        inside = (((B[:, 0] - A[:, 0]) * (q[1] - A[:, 1]) - (B[:, 1] - A[:, 1]) * (q[0] - A[:, 0]) > 0)
                  & ((C[:, 0] - B[:, 0]) * (q[1] - B[:, 1]) - (C[:, 1] - B[:, 1]) * (q[0] - B[:, 0]) > 0)
                  & ((A[:, 0] - C[:, 0]) * (q[1] - C[:, 1]) - (A[:, 1] - C[:, 1]) * (q[0] - C[:, 0]) > 0))
        hit = np.flatnonzero(inside)
        if not len(hit):
            continue
        i = int(hit[0])
        a, b, c = T[i]
        T[i], T[m], T[m + 1] = (p, a, b), (p, b, c), (p, c, a)
        m += 2
    return pts, T[:m]


def _incircle_f(a, b, c, d):
    """_incircle on plain floats (fast in the flip loop), scaled to be size-free."""
    adx, ady, bdx, bdy, cdx, cdy = a[0] - d[0], a[1] - d[1], b[0] - d[0], b[1] - d[1], \
        c[0] - d[0], c[1] - d[1]
    ad, bd, cd = adx * adx + ady * ady, bdx * bdx + bdy * bdy, cdx * cdx + cdy * cdy
    det = (adx * (bdy * cd - bd * cdy) - ady * (bdx * cd - bd * cdx) + ad * (bdx * cdy - bdy * cdx))
    return det / (max(ad, bd, cd) ** 2 or 1.0)


def _flip_all(pts, T, most=200_000):
    """Lawson flips until Delaunay; the outline (edges with one triangle) never flips."""
    T = T.copy()
    P = [tuple(q) for q in pts.tolist()]
    owner = {}
    for i, (a, b, c) in enumerate(T.tolist()):
        owner[(a, b)], owner[(b, c)], owner[(c, a)] = i, i, i
    stack = [e for e in owner if (e[1], e[0]) in owner and e[0] < e[1]]
    if stack:                                          # start from the edges that fail
        e = np.array(stack)
        t = T[[owner[(u, v)] for u, v in stack]]
        o = T[[owner[(v, u)] for u, v in stack]]
        a = t[(t != e[:, :1]) & (t != e[:, 1:])]
        w = o[(o != e[:, :1]) & (o != e[:, 1:])]
        if len(a) == len(e) and len(w) == len(e):
            A, B, C, D = pts[e[:, 0]], pts[e[:, 1]], pts[a], pts[w]
            ad, bd, cd = ((A - D) ** 2).sum(1), ((B - D) ** 2).sum(1), ((C - D) ** 2).sum(1)
            det = ((A[:, 0] - D[:, 0]) * ((B[:, 1] - D[:, 1]) * cd - bd * (C[:, 1] - D[:, 1]))
                   - (A[:, 1] - D[:, 1]) * ((B[:, 0] - D[:, 0]) * cd - bd * (C[:, 0] - D[:, 0]))
                   + ad * ((B[:, 0] - D[:, 0]) * (C[:, 1] - D[:, 1])
                           - (B[:, 1] - D[:, 1]) * (C[:, 0] - D[:, 0])))
            fail = det / np.maximum(np.maximum(ad, bd), cd) ** 2 > 1e-12
            stack = [stack[i] for i in np.flatnonzero(fail)]
    flips = 0
    while stack and flips < most:
        u, v = stack.pop()
        t, o = owner.get((u, v)), owner.get((v, u))
        if t is None or o is None:
            continue
        ta, tb, tc = T[t].tolist()
        a = tc if ta in (u, v) and tb in (u, v) else (tb if ta in (u, v) else ta)
        oa, ob, oc = T[o].tolist()
        w = oc if oa in (u, v) and ob in (u, v) else (ob if oa in (u, v) else oa)
        if _incircle_f(P[u], P[v], P[a], P[w]) <= 1e-12:
            continue
        # quad u, w, v, a (counter-clockwise): diagonal u-v -> a-w
        for e in ((u, v), (v, u), (v, a), (a, u), (u, w), (w, v)):
            owner.pop(e, None)
        T[t], T[o] = (u, w, a), (w, v, a)
        owner[(u, w)], owner[(w, a)], owner[(a, u)] = t, t, t
        owner[(w, v)], owner[(v, a)], owner[(a, w)] = o, o, o
        stack += [(u, w), (w, v), (v, a), (a, u)]
        flips += 1
    return T


def _metric(uv, p3, tris):
    """L (2 × 2) with |Δuv @ L| ≈ |Δp| over the triangles' edges (least squares)."""
    e = np.vstack([tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]]])
    d = uv[e[:, 1]] - uv[e[:, 0]]
    l2 = ((p3[e[:, 1]] - p3[e[:, 0]]) ** 2).sum(1)
    A = np.column_stack([d[:, 0] ** 2, 2 * d[:, 0] * d[:, 1], d[:, 1] ** 2])
    (m11, m12, m22), *_ = np.linalg.lstsq(A, l2, rcond=None)
    M = np.array([[m11, m12], [m12, m22]])
    w, V = np.linalg.eigh(M)
    if w.min() <= 0:                                   # not positive: per-axis scales
        s = [np.sqrt(np.median(l2[np.abs(d[:, k]) > 0] / d[np.abs(d[:, k]) > 0, k] ** 2))
             if np.any(np.abs(d[:, k]) > 0) else 1.0 for k in (0, 1)]
        return np.diag(s)
    return V @ np.diag(np.sqrt(w))


def refine(p3, uv, tris, evaluate):
    """p3 (n, 3) and uv (n, 2) nodes, tris (m, 3); evaluate(uv rows) -> 3D points.
    Returns (p3, tris) or None (keep OpenCASCADE's triangles)."""
    tris = np.asarray(tris, np.int64)
    if len(tris) < 2 or not has_fans(p3, tris):
        return None
    L = _metric(uv, p3, tris)
    x = uv @ L                                         # parameters in (about) model units
    bnd = _edges(tris)
    blen3 = np.linalg.norm(p3[bnd[:, 0]] - p3[bnd[:, 1]], axis=1)
    if not len(bnd) or blen3.min() <= 1e-9 * max(blen3.max(), 1e-30):
        return None                                   # degenerate edge (a pole): leave it
    a, b = x[bnd[:, 0]], x[bnd[:, 1]]
    blen = np.linalg.norm(b - a, axis=1)
    # target size around every point: edge points their edges' mean length, inner
    # points their nearest neighbour (rows of close points get company in between)
    nb = np.unique(bnd)
    acc = np.zeros(len(x)), np.zeros(len(x))
    np.add.at(acc[0], bnd.ravel(), np.repeat(blen, 2))
    np.add.at(acc[1], bnd.ravel(), 1)
    size = np.full(len(x), np.inf)
    ee = np.vstack([tris[:, [0, 1]], tris[:, [1, 2]], tris[:, [2, 0]]])
    el = np.linalg.norm(x[ee[:, 0]] - x[ee[:, 1]], axis=1)
    np.minimum.at(size, ee[:, 0], el)
    np.minimum.at(size, ee[:, 1], el)
    size[nb] = acc[0][nb] / acc[1][nb]
    bp, bl = x, size
    e1, e2 = x[tris[:, 1]] - x[tris[:, 0]], x[tris[:, 2]] - x[tris[:, 0]]
    flip = np.count_nonzero(e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0] < 0) > len(tris) / 2
    seeds = np.empty((0, 2))
    lo, hi = x.min(0), x.max(0)
    cap = float(np.linalg.norm(hi - lo)) / CAP_FRACTION
    for factor in ((1.0, 1.6, 2.6, 4.2) if len(x) <= SEED_NODES else ()):   # coarser until few enough
        cand = _seeds(lo, hi, bp, bl, factor, cap)
        if cand is None:
            continue
        cand = cand[_inside(cand, a, b)]
        if len(cand):
            h = _size(cand, bp, bl, cap) * factor
            near = np.full(len(cand), np.inf)          # not too close to existing points
            for s0 in range(0, len(x), 1500):
                near = np.minimum(near, np.linalg.norm(cand[:, None] - x[None, s0:s0 + 1500],
                                                       axis=2).min(1))
            edge_h = _size(cand, x[nb], size[nb], cap) * factor
            cand = cand[(near > 0.6 * h) & (_seg_dist(cand, a, b) > 0.45 * edge_h)]
        if len(cand) <= min(MAX_NEW, 3 * len(x) + 300):
            seeds = cand
            break
    ccw = tris[:, [0, 2, 1]] if flip else tris
    xs, t = _insert(x, ccw, seeds)
    t = _flip_all(xs, t)
    used = np.zeros(len(xs), bool)
    used[t.ravel()] = True
    used[:len(x)] = True
    remap = np.cumsum(used) - 1
    t, new = remap[t], xs[len(x):][used[len(x):]]
    p_new = np.vstack([p3, evaluate(new @ np.linalg.inv(L))]) if len(new) else p3
    if flip:
        t = t[:, [0, 2, 1]]
    if (fan_excess(p_new, t) > 0.5 * fan_excess(p3, tris)
            or (min_angles(p_new[t]) < 1).sum() > (min_angles(p3[tris]) < 1).sum()):
        return None                                   # not clearly better: keep OpenCASCADE's
    return p_new, t
