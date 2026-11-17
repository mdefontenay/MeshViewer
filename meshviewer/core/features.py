"""Feature faces, edges and nodes of a surface: what Select ▸ Feature Face, Feature Edge
and Feature Node pick. No Qt, no drawing.

- A **feature face** is a CAD face (cell data "face_id") or, on a mesh, the cells
  reached from one another across edges that bend less than the feature angle and are
  not smooth edges (below).
- **Smooth edges** (meshes): where the surface bends gently, as a cylinder meets the
  sphere on top of it, an edge shows as mesh edges that follow one another in a line
  (aligned) or in one plane that cuts across the surface (coplanar) — the mesher put
  its points on the edge. Three such mesh edges in a row are taken as an edge
  (`_smooth_edges`). Not on a regular grid, where every grid line would be one.
- **Feature edges** are made of the mesh edges where two feature faces meet, where the
  surface ends or where more than two cells share an edge (CAD); on a mesh, of every
  mesh edge bending more than the feature angle, the surface's ends and the smooth
  edges. One goes on through a point where it meets no other (and, CAD, the faces
  either side stay the same).
- On a **mesh** (no CAD faces) a feature edge is **cut only at a corner**: where it
  turns by more than the feature angle at one point, or by more than CORNER_DEG and
  twice as much as next to it (a curve twisting gently in 3D stays one feature edge,
  `_runs`); and where another feature edge meets it partway — of this
  part or of another part of the file (`cut_at_junctions`) — it is cut in two there;
  also where another part's feature edge lying on it ends (a 2D mesh's outline, where
  one boundary gives way to the next).
- On a mesh, a **gap** of a few mesh edges between two feature edges that stop facing
  each other, on one line or in one plane, is **bridged** (`_bridge`): they are one.
- A smooth edge that **zig-zags** (turning one way, then the other, mesh edge after
  mesh edge: the mesher's diagonals, not an edge) is dropped, and so is one with
  both ends in the open (`_anchored`).
- A part made of **lines** only (a 2D mesh's boundaries) has its lines as feature
  edges, and no feature faces.
- A **feature node** is a point where a feature edge ends.

Points at the same place are taken as one (CAD faces are meshed each with their own
points; a mesh's boundaries share theirs), so the edges and nodes go across faces.
"""
from __future__ import annotations

import numpy as np
from vtkmodules.util.numpy_support import vtk_to_numpy

FLAT_TOL_DEG = 2.0        # a bridge (`_bridge`) aligned / coplanar: a point at most this far
                          # off, as seen from the end of the feature edge
CORNER_DEG = 25.0         # a mesh's feature edge kinked by more than this at a point: cut
BRIDGE_EDGES = 8          # a gap of at most this many mesh edges between two feature edges
WIGGLE_DEG = 0.5          # a smooth edge's turn counts (zig-zag) from this (straight: rounding)
WIGGLE_SHARE = 0.5        # ... turning back at this share of its turns or more: a zig-zag
SMOOTH_TOL_DEG = 0.002    # smooth edges: this close to a line / a plane (points the mesher
                          # put on the edge are, but for rounding; others hardly ever)
ACROSS_COS = 0.7          # a smooth edge's plane crosses the surface (not lying on it)
FLAT_COS = np.cos(np.radians(0.01))   # cells this close to parallel: a flat area, where a
                                      # straight line of mesh edges is no edge
GRID_SHARE = 0.1          # more mesh edges than this found smooth: a regular grid, none kept
CREASE_DEG = 1.0          # a smooth edge the surface bends across by this much (each mesh edge)
JUMP = 0.25               # ... or bending differently either side by this share (a cylinder
                          # meeting a sphere); rows that line up by chance do neither
QUIET_DEG = 0.1           # where the surface bends less than this all around: no evidence
FREE_EDGES = 15           # a smooth edge ending in the open, shorter than this: dropped
WEAK_SHARE = 0.5          # a crease bending half the feature angle carries a sharp edge on
CREASE_BITS = 15          # a crease shorter than this ending in the open: mesh noise
LATTICE = 3               # a crease or smooth edge shorter than this between two junctions
_CHUNK = 4_000_000        # numbers per block when comparing the edges at each point


def _precision(pts):
    """Relative rounding of the file's numbers: float32 (many CGNS / STL files, even
    when read as float64) or float64."""
    if np.array_equal(pts.astype(np.float32).astype(pts.dtype), pts):
        return float(np.finfo(np.float32).eps)
    return float(np.finfo(np.float64).eps)


def _unit(v):
    n = np.linalg.norm(v, axis=-1)
    return v / np.where(n > 0, n, 1.0)[..., None]


def _smooth_edges(p, e_lo, e_hi, inner, sharp, cells, normal, angle, eps=1e-16,
                  bend=None, cell_places=None, tol_deg=SMOOTH_TOL_DEG):
    """Which mesh edges (e_lo, e_hi: places, points p) lie on a smooth edge.

    Mesh edges going on from one another at a point (turning less than `angle`)
    make paths through the mesh. Three edges in a row on such a path, aligned or in
    one plane that the surface crosses, are a smooth edge; aligned ones only where the
    surface bends nearby (on a flat face a straight line of mesh edges is no edge).
    `cells`: (n, 2) the cells either side of each edge (-1: none); `normal`: theirs.
    `inner`: the edges with a cell either side (the others are feature edges
    already); `sharp`: the feature edges already found — a smooth edge must end on
    one or close on itself (`_anchored`). `eps`: the precision of the file's numbers
    (float32 files are rounded more)."""
    n_e = len(e_lo)
    found = np.zeros(n_e, dtype=bool)
    if n_e < 3:
        return found
    at = np.r_[e_lo, e_hi]                       # half edges: (point, edge, which end)
    edge = np.r_[np.arange(n_e), np.arange(n_e)]
    end = np.r_[np.zeros(n_e, np.int64), np.ones(n_e, np.int64)]
    out = _unit(p[np.r_[e_hi, e_lo]] - p[at])    # direction away from the point
    by = np.argsort(at, kind="stable")
    at_s = at[by]
    firsts = np.flatnonzero(np.r_[True, at_s[1:] != at_s[:-1]])
    deg = np.diff(np.r_[firsts, len(at_s)])
    cos_turn = -np.cos(np.radians(angle))
    mine, other = [], []                         # half edge, the edge going on from it
    for d in np.unique(deg):
        if d < 2:
            continue
        group = firsts[deg == d]
        step = max(1, _CHUNK // (d * d))
        for i in range(0, len(group), step):
            idx = by[group[i:i + step, None] + np.arange(d)]      # (n, d) half edges
            u = out[idx]
            c = np.einsum("nik,njk->nij", u, u)
            c[:, np.arange(d), np.arange(d)] = np.inf
            g, x, y = np.nonzero(c < cos_turn)
            mine.append(idx[g, x])
            other.append(edge[idx[g, y]])
    if not mine:
        return found
    mine, other = np.concatenate(mine), np.concatenate(other)
    # every (edge before, edge, edge after): the ones going on at each end, crossed
    ends = []
    for e in (0, 1):
        sel = end[mine] == e
        k_e, o_e = edge[mine][sel], other[sel]
        o = np.argsort(k_e, kind="stable")
        n = np.bincount(k_e, minlength=n_e)
        ends.append((o_e[o], n, np.cumsum(n) - n))
    (a_s, n0, s0), (b_s, n1, s1) = ends
    many = n0 * n1
    k = np.repeat(np.arange(n_e), many)
    if not len(k):
        return found
    within = np.arange(len(k)) - np.repeat(np.cumsum(many) - many, many)
    a = a_s[s0[k] + within // n1[k]]
    b = b_s[s1[k] + within % n1[k]]
    p1, p2 = p[e_lo[k]], p[e_hi[k]]
    p0 = p[np.where(e_lo[a] == e_lo[k], e_hi[a], e_lo[a])]
    p3 = p[np.where(e_lo[b] == e_hi[k], e_hi[b], e_lo[b])]
    u0, u1, u2 = _unit(p1 - p0), _unit(p2 - p1), _unit(p3 - p2)
    # how far off a line / plane rounding alone can put points of these edges
    short = np.minimum(np.minimum(np.linalg.norm(p1 - p0, axis=1),
                                  np.linalg.norm(p2 - p1, axis=1)),
                       np.linalg.norm(p3 - p2, axis=1))
    sin_tol = np.maximum(np.sin(np.radians(tol_deg)),
                         8 * eps * float(np.abs(p).max()) / np.maximum(short, 1e-300))
    t01, t12 = np.cross(u0, u1), np.cross(u1, u2)
    s01, s12 = np.linalg.norm(t01, axis=1), np.linalg.norm(t12, axis=1)
    aligned = (s01 < sin_tol) & (s12 < sin_tol)
    curved = (s01 >= sin_tol) & (s12 >= sin_tol)
    plane = _unit(t01)
    coplanar = curved & (np.abs(np.einsum("ij,ij->i", plane, u2)) < sin_tol)
    by_k = normal[np.maximum(cells[k, 0], 0)]
    across = np.abs(np.einsum("ij,ij->i", plane, by_k)) < ACROSS_COS
    around = np.stack([cells[a], cells[k], cells[b]], axis=1).reshape(len(k), -1)
    dots = np.abs(np.einsum("tcj,tj->tc", normal[np.maximum(around, 0)], by_k))
    flat = np.where(around >= 0, dots, 1.0).min(axis=1) > FLAT_COS
    good = (aligned & ~flat) | (coplanar & across)
    for e in (k, a, b):
        found[e[good]] = True
    found &= inner
    if found.sum() > GRID_SHARE * max(1, inner.sum()):
        found[:] = False                          # a regular grid: every line is straight
        return found
    if bend is not None and cell_places is not None:
        found = _distinct(found, e_lo, e_hi, sharp, p, bend, cells, cell_places)
    if found.any():                  # gaps the mesh leaves in a smooth edge: bridged
        found |= _bridge(sharp | found, e_lo, e_hi, p, angle)
    return _anchored(found, e_lo, e_hi, sharp, p, angle)


def _hysteresis(strong, weak, e_lo, e_hi, p, angle, rounds=64):
    """Sharp edges carried on across mesh edges that bend a little less: a weak edge
    (bending `weak`) joins when it goes straight on (turning less than `angle`) from
    an edge already in, one mesh edge further each round. A trailing edge whose bend
    wavers around the feature angle is then one line, not dashes."""
    acc = strong.copy()
    cand = np.flatnonzero(weak & ~strong)
    cos_turn = -np.cos(np.radians(angle))
    for _ in range(rounds):
        if not len(cand):
            break
        a = np.flatnonzero(acc)
        at, far = np.r_[e_lo[a], e_hi[a]], np.r_[e_hi[a], e_lo[a]]
        o = np.argsort(at, kind="stable")
        at_s, far_s = at[o], far[o]
        newly = np.zeros(len(cand), dtype=bool)
        for here, there in ((e_lo, e_hi), (e_hi, e_lo)):
            p0 = here[cand]
            lo = np.searchsorted(at_s, p0, "left")
            n = np.searchsorted(at_s, p0, "right") - lo
            q = np.repeat(np.arange(len(cand)), n)
            pos = np.repeat(lo, n) + (np.arange(len(q)) - np.repeat(np.cumsum(n) - n, n))
            mine = _unit(p[there[cand]] - p[p0])[q]
            theirs = _unit(p[far_s[pos]] - p[p0[q]])
            newly[q[np.einsum("ij,ij->i", mine, theirs) < cos_turn]] = True
        if not newly.any():
            break
        acc[cand[newly]] = True
        cand = cand[~newly]
    return acc


def _bridge(net, e_lo, e_hi, p, angle, steps=BRIDGE_EDGES, tol_deg=FLAT_TOL_DEG,
            run=LATTICE):
    """Mesh edges filling the gaps between feature edges (`net`, mesh edges) that
    stop facing each other. From a point where one stops (its last `run` mesh edges at
    least, the line or plane they lie in): a path of at most `steps` mesh edges, none
    of `net`, each going on from the last (turning less than `angle`, the same way
    round as the feature edge turns), its points on that line (aligned) or in that
    plane (coplanar) within `tol_deg` as seen from the end, to where another feature
    edge stops — lying on the same line / plane, the path going on into it. The
    shortest such paths, each end bridged once."""
    n_p, n_e = len(p), len(e_lo)
    add = np.zeros(n_e, dtype=bool)
    f = np.flatnonzero(net)
    if not len(f):
        return add
    deg = np.bincount(np.r_[e_lo[f], e_hi[f]], minlength=n_p)
    ends = np.flatnonzero(deg == 1)
    if len(ends) < 2:
        return add
    at = np.r_[e_lo, e_hi]                            # the mesh edges at each point
    o = np.argsort(at, kind="stable")
    nb_s, ed_s = np.r_[e_hi, e_lo][o], o % n_e
    start = np.searchsorted(at[o], np.arange(n_p + 1))
    nb_l, ed_l, st_l, net_l, deg_l = (nb_s.tolist(), ed_s.tolist(), start.tolist(),
                                      net.tolist(), deg.tolist())
    back = np.full((len(ends), run + 1), -1, dtype=np.int64)    # behind each end
    for i, P in enumerate(ends.tolist()):
        cur, prev, k = P, -1, 0
        back[i, 0] = P
        while k < run:
            nxt = [(nb_l[j], ed_l[j]) for j in range(st_l[cur], st_l[cur + 1])
                   if net_l[ed_l[j]] and ed_l[j] != prev]
            if len(nxt) != 1:
                break
            (cur, prev), k = nxt[0], k + 1
            back[i, k] = cur
            if deg_l[cur] != 2:
                break
    ok = back[:, -1] >= 0                             # a feature edge, not a stub
    ends, back = ends[ok], back[ok]
    if len(ends) < 2:
        return add
    m = len(ends)
    sin_tol, cos_turn = np.sin(np.radians(tol_deg)), np.cos(np.radians(angle))
    q = p[back]                                       # (m, run + 1, 3): the end first
    q0 = q[:, 0]
    t = _unit(q0 - q[:, 1])                           # going out of the end
    behind = q[:, 2:] - q0[:, None]
    c = np.cross(t[:, None], behind)
    off = np.linalg.norm(c, axis=2) > sin_tol * np.linalg.norm(behind, axis=2)
    planar = off.any(axis=1)                          # else on a line
    normal = _unit(c[np.arange(m), np.argmax(off, axis=1)])
    d_in = _unit(q[:, :-1] - q[:, 1:])                # along it, towards the end
    turns = np.einsum("ijk,ik->i", np.cross(d_in[:, 1:], d_in[:, :-1]), normal)
    way = np.where(turns < 0, -1.0, 1.0)              # the way round it turns
    end_of = np.full(n_p, -1, dtype=np.int64)
    end_of[ends] = np.arange(m)

    def dev(s, x):
        """How far off the line / plane of end s points x are (sine, as seen from it)."""
        v = x - q0[s]
        far = np.maximum(np.linalg.norm(v, axis=-1), 1e-300)
        h = np.where(planar[s], np.abs(np.einsum("...k,...k->...", v, normal[s])),
                     np.linalg.norm(np.cross(t[s], v), axis=-1))
        return h / far

    src, cur, d_prev = np.arange(m), ends.copy(), t.copy()
    levels = []                                       # each step: (mesh edges, from which)
    seen = set((src * n_p + cur).tolist())
    found, done = [], set()                           # (end, end, mesh edges); ends done
    for _ in range(steps):
        if not len(cur):
            break
        cnt = start[cur + 1] - start[cur]
        st = np.repeat(np.arange(len(cur)), cnt)
        pos = np.repeat(start[cur], cnt) + (np.arange(len(st)) - np.repeat(np.cumsum(cnt) - cnt, cnt))
        x, e, s = nb_s[pos], ed_s[pos], src[st]
        v = p[x] - p[cur[st]]
        d = _unit(v)
        good = (~net[e] & (np.linalg.norm(v, axis=1) > 0)
                & (np.einsum("ij,ij->i", d, d_prev[st]) > cos_turn))
        way_ok = np.einsum("ij,ij->i", np.cross(d_prev[st], d), normal[s]) * way[s] >= -sin_tol
        good &= ~planar[s] | way_ok
        good &= dev(s, p[x]) <= sin_tol
        # another end reached: on the same line / plane, the path going on into it
        r = end_of[x]
        hit = good & (r >= 0) & (x != ends[s])
        if hit.any():
            h = np.flatnonzero(hit)
            rh, sh, dh = r[h], s[h], d[h]
            into = -t[rh]
            fine = np.einsum("ij,ij->i", dh, into) > cos_turn
            fine &= ~planar[sh] | (np.einsum("ij,ij->i", np.cross(dh, into), normal[sh])
                                   * way[sh] >= -sin_tol)
            fine &= (dev(sh[:, None], q[rh, 1:]) <= sin_tol).all(axis=1)
            h = h[fine]
            h = h[np.argsort(-np.einsum("ij,ij->i", d[h], -t[r[h]]), kind="stable")]
            for j in h.tolist():                      # the smoothest way in first
                if int(s[j]) in done:                 # its shortest one only
                    continue
                path, k = [int(e[j])], int(st[j])
                for lv in range(len(levels) - 1, -1, -1):
                    path.append(int(levels[lv][0][k]))
                    k = int(levels[lv][1][k])
                done.add(int(s[j]))
                found.append((int(s[j]), int(r[j]), path))
        go = good & (deg[x] == 0)                     # on, across no feature edge
        if done:
            go &= ~np.isin(s, list(done))
        go_i = []                                     # the straightest first: it keeps
        straight = np.einsum("ij,ij->i", d, d_prev[st])  # the point
        g = np.flatnonzero(go)
        g = g[np.argsort(-straight[g], kind="stable")]
        for j, key in zip(g.tolist(), (s * n_p + x)[g].tolist()):
            if key not in seen:
                seen.add(key)
                go_i.append(j)
        go_i = np.array(go_i, dtype=np.int64)
        levels.append((e[go_i], st[go_i]))
        src, cur, d_prev = s[go_i], x[go_i], d[go_i]
    used = set()
    for a, b, path in sorted(found, key=lambda z: (len(z[2]), z[0])):
        if a in used or b in used:
            continue
        used.update((a, b))
        add[path] = True
    return add


def _tidy(crease, fixed, e_lo, e_hi, n_p, shortest=CREASE_BITS):
    """Drop the crease bits that are mesh noise: a piece of creases (between points
    where three or more feature edges meet) shorter than `shortest` mesh edges, with
    an end in the open — branching off a line, or loose; and one under LATTICE mesh
    edges between two junctions (a knot of creases where a coarse mesh turns a tight
    corner, such as a wing tip's trailing edge). `fixed`: edges never dropped (where
    the surface ends), which the creases may lean on."""
    net = crease | fixed
    while True:
        f = np.flatnonzero(net)
        if not len(f):
            return crease & net
        ends = np.r_[e_lo[f], e_hi[f]]
        deg = np.bincount(ends, minlength=n_p)
        piece = _pieces(f, e_lo, e_hi, np.zeros(n_p, dtype=bool), n_p)
        size = np.bincount(piece)
        held = np.zeros(len(size), dtype=bool)
        held[piece[fixed[f]]] = True
        free = np.zeros(len(size), dtype=bool)
        open_end = deg == 1
        free[piece[open_end[e_lo[f]] | open_end[e_hi[f]]]] = True
        tiny = ~free & ~held & (size < LATTICE)        # between two junctions: a knot
        drop = ((free & ~held & (size < shortest)) | tiny)[piece]
        if not drop.any():
            return crease & net
        net[f[drop]] = False


def _pieces(f, e_lo, e_hi, on_sharp, n_p):
    """Label of each mesh edge `f` (indices) by piece: joined at points where only
    two of them meet, off any sharp edge."""
    ends = np.r_[e_lo[f], e_hi[f]]
    deg = np.bincount(ends, minlength=n_p)
    joint = (deg != 2) | on_sharp
    by = np.argsort(ends, kind="stable")
    ends_s, idx_s = ends[by], by % len(f)
    firsts = np.flatnonzero(np.r_[True, ends_s[1:] != ends_s[:-1]])
    go = ~joint[ends_s[firsts]]
    return components(len(f), idx_s[firsts[go]], idx_s[firsts[go] + 1])


def _distinct(found, e_lo, e_hi, sharp, p, bend, cells, cell_places):
    """Keep the pieces of smooth edge that the surface tells apart: it bends across
    them by CREASE_DEG or more (a rounded leading edge, a fillet's middle), or it bends
    differently on either side (JUMP: one row of mesh edges away, along the line — a
    cylinder, straight along its length, meeting a sphere). Rows of points that line up
    by chance on a smooth surface have the same bend across and on either side."""
    k = np.flatnonzero(found)
    if not len(k):
        return found
    n_p, n_e = len(p), len(e_lo)
    on_sharp = np.zeros(n_p, dtype=bool)
    on_sharp[e_lo[sharp]] = on_sharp[e_hi[sharp]] = True
    u, v = e_lo[k], e_hi[k]
    mid, e = (p[u] + p[v]) / 2, _unit(p[v] - p[u])
    # incident mesh edges of every point
    at = np.r_[e_lo, e_hi]
    by = np.argsort(at, kind="stable")
    start = np.searchsorted(at[by], np.arange(n_p))
    deg = np.bincount(at, minlength=n_p)
    beside = []
    for s in (0, 1):
        cp = cell_places[np.maximum(cells[k, s], 0)]
        d = np.linalg.norm(p[np.maximum(cp, 0)] - mid[:, None], axis=2)
        d[(cp < 0) | (cp == u[:, None]) | (cp == v[:, None])] = -1
        w = cp[np.arange(len(k)), np.argmax(d, axis=1)]            # the far point
        q = np.repeat(np.arange(len(k)), deg[w])
        pos = np.repeat(start[w], deg[w]) + (np.arange(len(q)) - np.repeat(
            np.cumsum(deg[w]) - deg[w], deg[w]))
        g = by[pos] % n_e                                          # a mesh edge at w
        other = np.where(e_lo[g] == w[q], e_hi[g], e_lo[g])
        score = np.abs(np.einsum("ij,ij->i", _unit(p[other] - p[w[q]]), e[q]))
        score[(other == u[q]) | (other == v[q]) | (cells[g, 1] < 0)] = -1
        o = np.lexsort((-score, q))                                # most parallel first
        first = o[np.r_[True, q[o][1:] != q[o][:-1]]]
        b = np.full(len(k), np.nan)
        ok = score[first] > 0.8                                    # within 37°
        b[q[first][ok]] = bend[g[first][ok]]
        b[cells[k, s] < 0] = np.nan
        beside.append(b)
    across = bend[k]
    total = beside[0] + beside[1] + across
    jump = np.abs(beside[0] - beside[1]) / np.maximum(total, 1e-12)
    jump[total < QUIET_DEG] = 0.0                         # hardly bends: tells nothing
    piece = _pieces(k, e_lo, e_hi, on_sharp, n_p)
    keep = np.zeros(piece.max() + 1, dtype=bool)
    for c in range(len(keep)):
        sel = piece == c
        j = jump[sel]
        j = j[~np.isnan(j)]
        keep[c] = (np.median(across[sel]) >= CREASE_DEG
                   or (len(j) > 0 and np.median(j) >= JUMP))
    out = np.zeros_like(found)
    out[k[keep[piece]]] = True
    return out


def _chains(f, e_lo, e_hi, piece):
    """The places of each piece (`piece`: label of each mesh edge `f`, a path or a
    loop), in order along it: a list of (places, closed), by label."""
    out = []
    order = np.argsort(piece, kind="stable")
    cut = np.flatnonzero(np.diff(piece[order])) + 1
    for group in np.split(f[order], cut):
        lo, hi = e_lo[group].tolist(), e_hi[group].tolist()
        at = {}
        for i, (a, b) in enumerate(zip(lo, hi)):
            at.setdefault(a, []).append(i)
            at.setdefault(b, []).append(i)
        start = next((q for q, es in at.items() if len(es) == 1), lo[0])
        places, used, cur = [start], set(), start
        while True:
            nxt = [i for i in at[cur] if i not in used]
            if not nxt:
                break
            i = nxt[0]
            used.add(i)
            cur = hi[i] if lo[i] == cur else lo[i]
            places.append(cur)
        out.append((np.array(places), len(places) > 2 and places[0] == places[-1]))
    return out


def _zigzag(q, closed):
    """Whether the polyline q (k + 1, 3) zig-zags: it turns one way, then back, at
    WIGGLE_SHARE of its turns or more (two at least), or at three turns or more with
    half its turning undone by the turns back (a row of mesh diagonals rippling across
    a face). A smooth curve turns one way (an S: once back), a straight line not at
    all (rounding: under WIGGLE_DEG)."""
    d = np.diff(q, axis=0)
    d = _unit(d[np.linalg.norm(d, axis=1) > 0])
    if closed:
        d = np.r_[d, d[:1]]
    if len(d) < 4:
        return False
    b = np.cross(d[:-1], d[1:])                         # the way each turn goes
    theta = np.arctan2(np.linalg.norm(b, axis=1), np.einsum("ij,ij->i", d[:-1], d[1:]))
    sig = theta > np.radians(WIGGLE_DEG)
    b, theta = b[sig], theta[sig]
    if len(theta) < 3:
        return False
    back = np.einsum("ij,ij->i", b[:-1], b[1:]) < 0     # turning the other way
    n_back = int(back.sum())
    if n_back < 2:
        return False
    sign = np.r_[1.0, np.cumprod(np.where(back, -1.0, 1.0))]
    total, net = float(theta.sum()), abs(float((sign * theta).sum()))
    return n_back >= WIGGLE_SHARE * len(back) or (n_back >= 3 and net <= 0.5 * total)


def _anchored(found, e_lo, e_hi, sharp, p, angle, shortest=LATTICE):
    """Tidy the smooth edges, piece by piece (a piece: between points where three or
    more meet, or a sharp edge). A real edge runs from feature edge to feature edge,
    or closes on itself; rows of points that line up by chance stop in the middle of a
    face. Dropped first: a piece that zig-zags (`_zigzag`: mesh diagonals rippling
    across a face). Then: a piece with both ends in the open (floating: it meets no
    sharp edge, surface end or other smooth edge) unless it closes on itself; a piece
    shorter than FREE_EDGES mesh edges with an end in the open (a row branching off
    an edge; a longer one is an edge whose end the mesh doesn't show, and stays); a
    piece shorter than `shortest` mesh edges between points where smooth edges meet
    (a lattice of rows crossing); a smooth edge turning by more than `angle` where
    nothing else meets it (a smooth edge has no corner). Again until nothing
    changes."""
    n_p = len(p)
    on_sharp = np.zeros(n_p, dtype=bool)
    on_sharp[e_lo[sharp]] = on_sharp[e_hi[sharp]] = True
    f = np.flatnonzero(found)
    if len(f):
        piece = _pieces(f, e_lo, e_hi, on_sharp, n_p)
        wavy = np.array([_zigzag(p[pl], closed) for pl, closed in
                         _chains(f, e_lo, e_hi, piece)])
        f = f[~wavy[piece]]
    while len(f):
        ends = np.r_[e_lo[f], e_hi[f]]
        deg = np.bincount(ends, minlength=n_p)
        piece = _pieces(f, e_lo, e_hi, on_sharp, n_p)
        size = np.bincount(piece)
        kind = np.where(on_sharp, 2, np.where(deg == 1, 0, np.where(deg >= 3, 1, 3)))
        ends_of = np.zeros((len(size), 4), dtype=np.int64)  # in the open, junction, sharp
        for side in (e_lo[f], e_hi[f]):
            np.add.at(ends_of, (piece, kind[side]), 1)
        free, joint, anchored = ends_of[:, 0], ends_of[:, 1], ends_of[:, 2]
        drop = (((size < shortest) & (anchored < 2) & (free == 0))
                | ((free > 0) & (size < FREE_EDGES))         # short, ending in the open
                | (free >= 2))                               # floating: both ends open
        drop = drop[piece]
        # a corner inside a piece: two smooth mesh edges, nothing else, turning sharply
        by = np.argsort(ends, kind="stable")
        ends_s, idx_s = ends[by], by % len(f)
        firsts = np.flatnonzero(np.r_[True, ends_s[1:] != ends_s[:-1]])
        place = ends_s[firsts]
        go = (deg[place] == 2) & ~on_sharp[place]
        s1, s2, at = idx_s[firsts[go]], idx_s[firsts[go] + 1], place[go]
        u1 = p[np.where(e_lo[f[s1]] == at, e_hi[f[s1]], e_lo[f[s1]])] - p[at]
        u2 = p[np.where(e_lo[f[s2]] == at, e_hi[f[s2]], e_lo[f[s2]])] - p[at]
        corner = np.einsum("ij,ij->i", _unit(u1), _unit(u2)) > -np.cos(np.radians(angle))
        drop[s1[corner]] = drop[s2[corner]] = True
        if not drop.any():
            break
        f = f[~drop]
    out = np.zeros_like(found)
    out[f] = True
    return out


def components(n, a, b):
    """Label of the group of each of n items joined by the pairs (a[i], b[i]):
    0, 1, 2… in order of the items' first appearance."""
    lab = np.arange(n)
    a, b = np.asarray(a, dtype=np.int64), np.asarray(b, dtype=np.int64)
    while len(a):
        la, lb = lab[a], lab[b]
        if np.array_equal(la, lb):
            break
        m = np.minimum(la, lb)
        np.minimum.at(lab, la, m)        # the larger root points to the smaller
        np.minimum.at(lab, lb, m)
        while True:                      # every item straight to its root
            up = lab[lab]
            if np.array_equal(up, lab):
                break
            lab = up
    return np.unique(lab, return_inverse=True)[1].reshape(-1)


def place_tolerance(bounds):
    """How close two points are to be one place, for a model of these bounds."""
    b = np.asarray(bounds, dtype=float).reshape(3, 2)
    return float(np.ptp(b, axis=1).max() or 1.0) * 1e-7


def _runs(p, angle, corner=CORNER_DEG):
    """Where to cut a polyline of points p (k + 1, 3): the indices of the inner points
    at a corner — turning by more than `angle`, or a kink: by more than `corner` and
    twice as much as at the points either side (a coarse mesh's curve turns about as
    much at each point). A curve turning gently, in a plane or twisting in 3D, stays
    whole. Zero-length mesh edges are skipped."""
    d = np.diff(p, axis=0)
    length = np.linalg.norm(d, axis=1)
    idx = np.flatnonzero(length > 0)
    if len(idx) < 2:
        return []
    u = d[idx] / length[idx, None]
    turn = np.degrees(np.arccos(np.clip(np.einsum("ij,ij->i", u[:-1], u[1:]), -1, 1)))
    beside = np.maximum(np.r_[0.0, turn[:-1]], np.r_[turn[1:], 0.0])
    cut = (turn > angle) | ((turn > corner) & (turn >= 2 * beside))
    return idx[1:][cut].tolist()


class Features:
    """The feature faces, edges and nodes of one surface (`pyvista.PolyData`).
    `tol`: points closer than this are one place (default: from the surface's size)."""

    def __init__(self, poly, angle=30.0, tol=None):
        pts = np.array(poly.points, dtype=float)
        self._pts = pts
        self._angle = angle
        n_cells = poly.n_cells
        self.region = np.full(n_cells, -1, dtype=np.int64)      # cell -> feature face
        self.seg = np.zeros((0, 2), dtype=np.int64)            # mesh edges (point ids)
        self.seg_faces = np.zeros((0, 2), dtype=np.int64)      # faces either side (-1)
        self.curve = np.zeros(0, dtype=np.int64)               # mesh edge -> feature edge
        self.nodes = np.zeros(0, dtype=np.int64)               # point ids
        self._node_places = np.zeros(0, dtype=np.int64)
        self.flat = "face_id" not in poly.cell_data              # a mesh: straight / planar
        self.face_ids = None                                     # CAD: each face's face_id
        self._ends = np.zeros((0, 2), dtype=np.int64)            # mesh edges (places)
        if not len(pts):
            return
        # one id per place: points at the same spot are one
        if tol is None:
            tol = float(np.ptp(pts, axis=0).max() or 1.0) * 1e-7
        q = np.round(pts / tol).astype(np.int64)
        keys, same = np.unique(q, axis=0, return_inverse=True)
        same = same.reshape(-1)
        rep = np.zeros(len(keys), dtype=np.int64)
        rep[same] = np.arange(len(pts))                             # a point of each place
        self._same, self._rep, self._keys = same, rep, keys
        polys = poly.GetPolys()
        if polys is None or polys.GetNumberOfCells() == 0:
            self._lines_only(poly)
            return
        off = np.array(vtk_to_numpy(polys.GetOffsetsArray()), dtype=np.int64)
        conn = np.array(vtk_to_numpy(polys.GetConnectivityArray()), dtype=np.int64)
        first = poly.GetNumberOfVerts() + poly.GetNumberOfLines()   # cell id of polygon 0
        n_poly = len(off) - 1
        sizes = np.diff(off)
        cell_of = np.repeat(np.arange(n_poly), sizes)              # polygon of each corner
        nxt = np.arange(len(conn)) + 1
        nxt[off[1:] - 1] = off[:-1]                                 # last corner -> first

        a, b = same[conn], same[conn[nxt]]
        ok = a != b
        a, b, cell = a[ok], b[ok], cell_of[ok]
        lo, hi = np.minimum(a, b), np.maximum(a, b)
        key = lo * (len(rep) + 1) + hi
        order = np.argsort(key, kind="stable")
        key_s = key[order]
        starts = np.flatnonzero(np.r_[True, key_s[1:] != key_s[:-1]])
        counts = np.diff(np.r_[starts, len(key_s)])
        e_lo, e_hi = lo[order][starts], hi[order][starts]

        # ---- feature faces
        if not self.flat:
            region = np.asarray(poly.cell_data["face_id"])[first:first + n_poly]
            self.face_ids, region = np.unique(region, return_inverse=True)   # face -> id
            region = region.reshape(-1)
        else:
            p0, p1 = pts[conn], pts[conn[nxt]]
            normal = np.zeros((n_poly, 3))
            np.add.at(normal, cell_of, np.cross(p0, p1))            # Newell's normals
            length = np.linalg.norm(normal, axis=1)
            normal /= np.where(length > 0, length, 1.0)[:, None]
            two = np.flatnonzero(counts == 2)
            o1, o2 = order[starts[two]], order[starts[two] + 1]
            c1, c2 = cell[o1], cell[o2]
            # cells turning the same way walk a shared edge in opposite directions
            fwd = a < b
            sign = np.where(fwd[o1] == fwd[o2], -1.0, 1.0)
            cos = sign * np.einsum("ij,ij->i", normal[c1], normal[c2])
            cells = np.full((len(counts), 2), -1, dtype=np.int64)  # either side of an edge
            cells[two, 0], cells[two, 1] = c1, c2
            cells[counts == 1, 0] = cell[order][starts][counts == 1]
            eps = _precision(pts)
            bend = np.zeros(len(counts))                            # degrees, across each edge
            bend[two] = np.degrees(np.arccos(np.clip(cos, -1, 1)))
            p_place = pts[rep]
            ends_ = counts != 2                                     # where the surface ends
            crease = _hysteresis(bend > angle, bend > angle * WEAK_SHARE, e_lo, e_hi,
                                 p_place, angle)
            crease = _tidy(crease, ends_, e_lo, e_hi, len(rep))
            crease |= _bridge(crease | ends_, e_lo, e_hi, p_place, angle)   # gaps in a crease
            sharp = ends_ | crease
            # faces: bounded by every edge bending over the feature angle (also the
            # bits too small to draw), so they don't leak through a gap
            bent = sharp[two] | (bend[two] > angle)
            cell_places = np.full((n_poly, int(sizes.max())), -1, dtype=np.int64)
            cell_places[cell_of, np.arange(len(conn)) - np.repeat(off[:-1], sizes)] = same[conn]
            smooth_edge = _smooth_edges(p_place, e_lo, e_hi, counts == 2, sharp, cells,
                                        normal, angle, eps, bend, cell_places)
            joined = ~bent & ~smooth_edge[two]
            region = components(n_poly, c1[joined], c2[joined])
        self.region[first:first + n_poly] = region

        # ---- feature edges: faces differ either side, the surface ends, or > 2 cells
        r_sorted = region[cell[order]]
        r_min = np.minimum.reduceat(r_sorted, starts)
        r_max = np.maximum.reduceat(r_sorted, starts)
        r_max = np.where(counts == 1, -1, r_max)
        if self.flat:                               # a mesh: every sharp or smooth edge
            feat = sharp | smooth_edge
        else:
            feat = (counts != 2) | (r_min != r_max)
        self._ends = np.stack([e_lo[feat], e_hi[feat]], axis=1)      # places
        self.seg = rep[self._ends]
        self.seg_faces = np.stack([r_min[feat], r_max[feat]], axis=1)
        self._build()

    def _lines_only(self, poly):
        """A part made of lines (a 2D mesh's boundaries): its lines are its feature
        edges, cut at corners; no feature faces."""
        lines = poly.GetLines()
        if lines is None or lines.GetNumberOfCells() == 0:
            return
        off = np.array(vtk_to_numpy(lines.GetOffsetsArray()), dtype=np.int64)
        conn = np.array(vtk_to_numpy(lines.GetConnectivityArray()), dtype=np.int64)
        if len(conn) < 2:
            return
        cell_of = np.repeat(np.arange(len(off) - 1), np.diff(off))
        a, b = self._same[conn[:-1]], self._same[conn[1:]]
        ok = (cell_of[:-1] == cell_of[1:]) & (a != b)            # within one polyline
        ends = np.unique(np.sort(np.stack([a[ok], b[ok]], axis=1), axis=1), axis=0)
        self._ends = ends
        self.seg = self._rep[ends]
        self.seg_faces = np.full((len(ends), 2), -1, dtype=np.int64)
        self._build()

    # ---- feature edges and nodes ---------------------------------------------------
    def _build(self, cuts=()):
        """Group the mesh edges into feature edges, also cut at the places `cuts`."""
        ends, faces = self._ends, self.seg_faces
        m = len(ends)
        if not m:
            return
        n_places = len(self._rep)
        flat_ends = ends.reshape(-1)
        deg = np.bincount(flat_ends, minlength=n_places)
        # each place with two mesh edges: both of them (to walk along)
        by = np.argsort(flat_ends, kind="stable")
        seg_s = by // 2
        firsts = np.flatnonzero(np.r_[True, flat_ends[by][1:] != flat_ends[by][:-1]])
        place = flat_ends[by][firsts]
        two = deg[place] == 2
        s1, s2 = seg_s[firsts[two]], seg_s[firsts[two] + 1]
        through = np.zeros(n_places, dtype=bool)
        # CAD: a curve ends where the faces either side change; a mesh: only where
        # feature edges meet (its faces can change along a crease that fades out)
        go = (faces[s1] == faces[s2]).all(axis=1) if not self.flat else np.ones(len(s1), bool)
        through[place[two][go]] = True                       # an edge goes on through here
        through[np.asarray(cuts, dtype=np.int64)] = False
        other = np.full((n_places, 2), -1, dtype=np.int64)
        other[place[two], 0], other[place[two], 1] = s1, s2
        if not self.flat:                                    # CAD: whole curves
            keep = through[place[two]]
            self.curve = components(m, s1[keep], s2[keep])
        else:
            self.curve = self._walk(ends, through, other)
        node = np.unique(flat_ends[~through[flat_ends]])
        step = self.curve[s1] != self.curve[s2]           # cut inside a chain: a node too
        node = np.union1d(node, place[two][step])
        self._node_places = node
        self.nodes = self._rep[node]

    def _walk(self, ends, through, other):
        """Feature edges of a mesh: along each chain of mesh edges, cut at its corners
        (`_runs`)."""
        m = len(ends)
        curve = np.full(m, -1, dtype=np.int64)
        pts = self._pts[self._rep]                           # one point per place
        n_curve = 0

        def follow(s, at):
            """Mesh edges and places from place `at` along edge `s` to an end."""
            segs, places = [s], [at]
            while True:
                nxt = ends[s, 1] if ends[s, 0] == at else ends[s, 0]
                places.append(nxt)
                if not through[nxt] or nxt == places[0]:
                    return segs, places
                o = other[nxt]
                s = o[1] if o[0] == s else o[0]
                if curve[s] >= 0 or s in segs[-1:]:
                    return segs, places
                at = nxt
                segs.append(s)

        def assign(segs, places):
            nonlocal n_curve
            cuts = set(_runs(pts[places], self._angle))
            for i, s in enumerate(segs):
                if i in cuts:
                    n_curve += 1
                curve[s] = n_curve
            n_curve += 1

        for s in range(m):                                   # open chains: from an end
            if curve[s] >= 0:
                continue
            for k in (0, 1):
                if not through[ends[s, k]]:
                    segs, places = follow(s, ends[s, k])
                    assign(segs, places)
                    break
        for s in range(m):                                   # closed loops
            if curve[s] < 0:
                segs, places = follow(s, ends[s, 0])
                if len(segs) > 2:                            # start at its sharpest corner
                    p = pts[places[:-1]]
                    d_in = p - np.roll(p, 1, axis=0)
                    d_out = np.roll(p, -1, axis=0) - p
                    cos = np.einsum("ij,ij->i", d_in, d_out) / np.maximum(
                        np.linalg.norm(d_in, axis=1) * np.linalg.norm(d_out, axis=1), 1e-300)
                    k = int(np.argmin(cos))
                    segs = segs[k:] + segs[:k]
                    places = places[k:-1] + places[:k] + [places[k]]
                assign(segs, places)
        return np.unique(curve, return_inverse=True)[1].reshape(-1)

    def end_keys(self):
        """(m, 2, 3) integer positions of the mesh edges' ends (`cut_at_junctions`)."""
        return self._keys[self._ends] if len(self._ends) else np.zeros((0, 2, 3), np.int64)

    # ---- what a click picks --------------------------------------------------------
    def face_of(self, cell):
        """Feature face of a cell (-1: not a polygon)."""
        if cell is None or not 0 <= cell < len(self.region):
            return -1
        return int(self.region[cell])

    def face_cells(self, face):
        return np.flatnonzero(self.region == face)

    def curve_segments(self, curve):
        """(k, 2) point ids of the mesh edges of a feature edge."""
        return self.seg[self.curve == curve]

    def nearest_curve(self, pts, pos, face=-1):
        """Feature edge nearest to the 3D point `pos`: among the edges of feature face
        `face` when it has some, else among all. None when there are none."""
        idx = np.arange(len(self.seg))
        if face >= 0:
            mine = np.flatnonzero((self.seg_faces == face).any(axis=1))
            if len(mine):
                idx = mine
        if not len(idx):
            return None
        p0, p1 = pts[self.seg[idx, 0]], pts[self.seg[idx, 1]]
        d = p1 - p0
        dd = np.einsum("ij,ij->i", d, d)
        t = np.clip(np.einsum("ij,ij->i", np.asarray(pos) - p0, d) / np.where(dd > 0, dd, 1),
                    0, 1)
        dist = np.linalg.norm(p0 + t[:, None] * d - pos, axis=1)
        return int(self.curve[idx[int(np.argmin(dist))]])

    def nearest_node(self, pts, pos, face=-1):
        """Point id of the feature node nearest to `pos`: among the corners of feature
        face `face` when it has some, else among all. None when there are none."""
        nodes = self.nodes
        if face >= 0 and len(nodes):
            mine = self.seg[(self.seg_faces == face).any(axis=1)].reshape(-1)
            on = np.isin(self._node_places, self._same[mine])
            if on.any():
                nodes = nodes[on]
        if not len(nodes):
            return None
        return int(nodes[int(np.argmin(np.linalg.norm(pts[nodes] - pos, axis=1)))])


def cut_at_junctions(features):
    """Feature edges of several parts of one mesh (each `Features` made with the same
    `tol`): one met partway by a feature edge of another part is cut in two there.
    Feature edges lying on each other (a border two boundaries share) are one, so
    they cut nothing."""
    feats = [f for f in features if f.flat and len(f._ends)]
    if len(feats) < 2:
        return
    keys = [f.end_keys().reshape(-1, 3) for f in feats]
    _, gid = np.unique(np.concatenate(keys), axis=0, return_inverse=True)
    gid = gid.reshape(-1)
    pairs, at = [], 0
    for k in keys:
        g = gid[at:at + len(k)].reshape(-1, 2)
        pairs.append(np.sort(g, axis=1))
        at += len(k)
    edges = np.unique(np.concatenate(pairs), axis=0)       # every mesh edge once
    deg = np.bincount(edges.reshape(-1), minlength=gid.max() + 1)
    meet = deg > 2                                          # three or more ways out
    for g in pairs:                                         # or one part's edges end
        own = np.bincount(g.reshape(-1), minlength=len(meet))   # (a 2D mesh's boundary
        meet |= own == 1                                        # ends along the outline)
    at = 0
    for f, k in zip(feats, keys):
        g = gid[at:at + len(k)]
        at += len(k)
        places = f._ends.reshape(-1)
        cuts = np.unique(places[meet[g]])
        if len(cuts):
            f._build(cuts)
