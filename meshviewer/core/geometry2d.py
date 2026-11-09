"""2D geometry of the cross section: the cut as loops in the plane, wall offsets,
layer collisions. Pure NumPy (used by gui/pages/section_cut.py)."""
from __future__ import annotations

import numpy as np


MIN_GAP_PX = 2.0                    # layers closer than this merge into a solid band


def _basis(n):
    """Screen axes on the plane (right, up), looking at it from the normal's side
    (the side the section hides), so the kept half is seen face-on."""
    n = np.asarray(n, float) / np.linalg.norm(n)
    up = np.array([0.0, 0.0, 1.0])
    if abs(n @ up) > 0.95:
        up = np.array([0.0, 1.0, 0.0])
    v = up - (up @ n) * n
    v /= np.linalg.norm(v)
    u = np.cross(v, n)
    return u, v


def _loops(poly, origin, u, v):
    """Cut lines -> [(N×2 points, closed?)] in plane coordinates."""
    if poly is None or not poly.n_cells:
        return []
    s = poly.strip()
    pts = (np.asarray(s.points) - origin) @ np.column_stack([u, v])
    out = []
    lines = np.asarray(s.lines)
    i = 0
    while i < len(lines):
        k = lines[i]
        ids = lines[i + 1:i + 1 + k]
        i += 1 + k
        if k >= 2:
            out.append((pts[ids], ids[0] == ids[-1]))
    return out


def nice(x):
    """1, 2 or 5 × 10^n just under x."""
    if x <= 0:
        return 1.0
    e = 10 ** np.floor(np.log10(x))
    for m in (5, 2, 1):
        if m * e <= x:
            return m * e
    return e


def _inside(q, loops):
    """Even-odd test: which points q (N×2) lie inside the closed loops."""
    res = np.zeros(len(q), bool)
    px, py = q[:, :1], q[:, 1:]
    for loop in loops:
        x1, y1 = loop[:-1, 0], loop[:-1, 1]
        x2, y2 = loop[1:, 0], loop[1:, 1]
        for k in range(0, len(q), 2000):                 # bounded memory
            sx, sy = px[k:k + 2000], py[k:k + 2000]
            cross = ((y1 > sy) != (y2 > sy)) & \
                (sx < (x2 - x1) * (sy - y1) / np.where(y2 == y1, 1e-300, y2 - y1) + x1)
            res[k:k + 2000] ^= cross.sum(axis=1) % 2 == 1
    return res


def offsets(pts, segs, perp):
    """Per point: the direction to push the outline by 1 (averaged, mitred)."""
    acc = np.zeros_like(pts)
    np.add.at(acc, segs[:, 0], perp)
    np.add.at(acc, segs[:, 1], perp)
    norm = np.linalg.norm(acc, axis=1)
    pn = np.divide(acc, norm[:, None], out=np.zeros_like(acc), where=norm[:, None] > 0)
    cosa = np.ones(len(pts))
    for col in (0, 1):
        np.minimum.at(cosa, segs[:, col], np.einsum("ij,ij->i", pn[segs[:, col]], perp))
    return pn / np.maximum(cosa, 0.35)[:, None]


def _samples(a, b, h, most=6000):
    """Points along the segments a→b, about h apart (at most `most` of them)."""
    ln = np.linalg.norm(b - a, axis=1)
    k = np.maximum(1, np.ceil(ln / max(h, 1e-300))).astype(int)
    if k.sum() > most:
        k = np.maximum(1, (k * most / k.sum()).astype(int))
    seg = np.repeat(np.arange(len(a)), k)
    start = np.repeat(np.cumsum(k) - k, k)
    t = (np.arange(k.sum()) - start) / np.repeat(k, k)
    return a[seg] + (b[seg] - a[seg]) * t[:, None]


def densify(pts, segs, perp, h, most=4000):
    """Split segments longer than h (each new piece keeps its segment's side), so the
    layer thickness can change along a long flat face (e.g. where it faces a wall)."""
    a, b = pts[segs[:, 0]], pts[segs[:, 1]]
    ln = np.linalg.norm(b - a, axis=1)
    k = np.maximum(1, np.ceil(ln / max(h, 1e-300))).astype(int)
    extra = int((k - 1).sum())
    if extra == 0:
        return pts, segs, perp
    if extra > most:
        k = np.maximum(1, np.ceil((k - 1) * most / extra).astype(int) + 1)
        k = np.where(ln > h, k, 1)
    new_pts, new_segs, new_perp = [pts], [], []
    nxt = len(pts)
    for s_, kk in enumerate(k):
        i, j = segs[s_]
        if kk == 1:
            new_segs.append([(i, j)])
            new_perp.append(perp[s_:s_ + 1])
            continue
        t = np.arange(1, kk)[:, None] / kk
        mid = a[s_] + (b[s_] - a[s_]) * t
        ids = np.arange(nxt, nxt + kk - 1)
        nxt += kk - 1
        chain = np.concatenate([[i], ids, [j]])
        new_pts.append(mid)
        new_segs.append(np.column_stack([chain[:-1], chain[1:]]))
        new_perp.append(np.repeat(perp[s_:s_ + 1], kk, axis=0))
    return (np.vstack(new_pts), np.vstack(new_segs).astype(int), np.vstack(new_perp))


def collision_caps(pts, segs, off, obstacles=(), eps=1e-3):
    """Per point of the cut: the largest thickness d its layer can take.

    The layer at point P is P + off·d. It has crossed another layer when it gets
    closer than d to another part of the walls: |off·d − v| < d for a point W of
    the walls (v = W − P) — the smallest root of that quadratic. Walls that face
    each other meet half-way; a concave curve stops at its centre. Obstacles
    (other parts, [N×2 polylines]) stop the layer where its ray hits them."""
    n = len(pts)
    cap = np.full(n, np.inf)
    if n == 0 or not len(segs):
        return cap
    a, b = pts[segs[:, 0]], pts[segs[:, 1]]
    span = float(np.ptp(pts, axis=0).max()) or 1.0
    w = np.vstack([pts, _samples(a, b, span / 400)])
    A = np.einsum("ij,ij->i", off, off) - (1 - eps) ** 2
    step = max(1, int(3e6 // max(len(w), 1)))
    for k in range(0, n, step):
        o, P, Ak = off[k:k + step], pts[k:k + step], A[k:k + step, None]
        v = w[None, :, :] - P[:, None, :]
        av = np.einsum("ij,imj->im", o, v)
        vv = np.einsum("imj,imj->im", v, v)
        disc = av * av - Ak * vv
        ok = (av > 0) & (disc > 0) & (vv > (span * 1e-9) ** 2)
        d1 = np.where(ok, vv / np.where(ok, av + np.sqrt(np.maximum(disc, 0)), 1.0), np.inf)
        cap[k:k + step] = d1.min(axis=1)
    if len(obstacles):                                # rays against other parts
        c = np.vstack([q[:-1] for q in obstacles])
        e = np.vstack([q[1:] for q in obstacles])
        de = e - c
        step = max(1, int(3e6 // max(len(c), 1)))
        for k in range(0, n, step):
            o, P = off[k:k + step, None, :], pts[k:k + step, None, :]
            den = o[..., 0] * de[None, :, 1] - o[..., 1] * de[None, :, 0]
            w_ = c[None] - P
            safe = np.where(np.abs(den) > 1e-300, den, 1.0)
            d = (w_[..., 0] * de[None, :, 1] - w_[..., 1] * de[None, :, 0]) / safe
            t = (w_[..., 0] * o[..., 1] - w_[..., 1] * o[..., 0]) / safe
            hit = (np.abs(den) > 1e-300) & (t >= 0) & (t <= 1) & (d > span * 1e-7)
            cap[k:k + step] = np.minimum(cap[k:k + step],
                                         np.where(hit, d, np.inf).min(axis=1))
    return cap


def _dist_to_segments(q, a, b):
    """Shortest distance from each point q (K×2) to the segments a→b."""
    ab = b - a
    l2 = np.maximum(np.einsum("ij,ij->i", ab, ab), 1e-300)
    out = np.full(len(q), np.inf)
    step = max(1, int(2e6 // max(len(a), 1)))
    for k in range(0, len(q), step):
        d = q[k:k + step, None, :] - a[None]
        t = np.clip(np.einsum("kmj,mj->km", d, ab) / l2, 0, 1)
        r = d - t[..., None] * ab[None]
        out[k:k + step] = np.sqrt(np.einsum("kmj,kmj->km", r, r).min(axis=1))
    return out


def trimmed_ring(pts, segs, off, cap, depth, obstacles=(), eps=1e-3):
    """The cut pushed out by `depth`, without the parts that crossed: (x0, y0, x1, y1)
    arrays of segments, in plane coordinates. A segment with one end past its cap is
    cut where it starts to cross (bisection)."""
    q = pts + off * depth
    ok = cap >= depth
    i, j = segs[:, 0], segs[:, 1]
    both = ok[i] & ok[j]
    one = ok[i] ^ ok[j]
    p0, p1 = [q[i[both]]], [q[j[both]]]
    if one.any():
        good = np.where(ok[i[one]][:, None], q[i[one]], q[j[one]])
        bad = np.where(ok[i[one]][:, None], q[j[one]], q[i[one]])
        a, b = pts[segs[:, 0]], pts[segs[:, 1]]
        loops = [o for o in obstacles if len(o) > 3 and np.allclose(o[0], o[-1])]
        lo, hi = np.zeros(len(good)), np.ones(len(good))
        for _ in range(12):                           # where the segment starts to cross
            mid = (lo + hi) / 2
            m = good + (bad - good) * mid[:, None]
            fine = _dist_to_segments(m, a, b) >= depth * (1 - eps)
            if loops:
                fine &= ~_inside(m, loops)
            lo = np.where(fine, mid, lo)
            hi = np.where(fine, hi, mid)
        p0.append(good)
        p1.append(good + (bad - good) * lo[:, None])
    p0, p1 = np.vstack(p0), np.vstack(p1)
    return p0, p1
