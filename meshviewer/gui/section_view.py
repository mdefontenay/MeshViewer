"""NEW (v2.13): the "Cross section" tab of the Inflation page (CFD mode).

The section plane (sidebar ▸ Section) cuts the model; this tab draws that cut in
2D, looking at the plane, and estimates how the inflation layers would sit on
the walls it crosses: each layer is the wall outline pushed out by the total
thickness up to that layer, along the wall's normal (the fluid side). Corners
use a mitred offset, so concave corners can overlap — it is an estimate.

    ┌ Section through wing · normal (1, 0, 0) ─────────────────────────────┐
    │   grey: the cut of the model · dark line: the walls                    │
    │   orange band: the layers (lines where they are ≥ 2 px apart)          │
    │   dashed: boundary layer · dotted: top of the next cell                │
    │ ▬ 1 mm                       scroll to zoom · drag to pan · dbl-click  │
    └────────────────────────────────────────────────────────────────────────┘

The view follows the section plane (it checks a few times a second while shown).
v2.13.1: a flow-direction arrow (toggled from the legend in the card's header).
v2.13.2: only the walls and the layers (the boundary-layer and next-cell lines and
the smoothing are gone); the layers' side no longer trusts the surface normals
alone: a layer never starts inside the solid (tested on the cut); "Flip side" swaps.
v2.14: layers stop where they would cross — two walls facing each other (they meet
half-way), a concave curve (they meet at its centre), or another part (they stop at
it). Each point of the cut gets the largest thickness it can take before its layer
gets closer to another wall than to its own (collision_caps); the rings are trimmed
where they cross. The zoom is remembered per file (view_state / restore_view).
v2.14.2: for STEP / IGES / BREP the walls are cut from the CAD curves themselves (smooth
at any zoom) once the plane stops moving — the triangles while it moves; the flow arrow
is three thin inlet arrows on the upstream edge of the view.
"""
from __future__ import annotations

import numpy as np
import pyvista as pv
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPalette, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

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


# ---- NEW (v2.14): layers that cross --------------------------------------------------------
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


class SectionLegend(QWidget):
    """NEW (v2.13.1): the legend of the Cross section, same look as the plot's.
    v2.13.2: the layers are always shown; "Flow direction" shows / hides the arrow."""
    toggled = Signal(str, bool)
    ITEMS = (("layers", "band", "Inflation layers"), ("flow", "arrow", "Flow direction"))
    TOGGLES = {"flow"}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.on = {"layers": True, "flow": False}
        self.setFixedHeight(22)
        self.setMouseTracking(True)
        fm = self.fontMetrics()
        self.setMinimumWidth(sum(fm.horizontalAdvance(t) + 38 for *_, t in self.ITEMS))
        self._boxes = []

    def set_on(self, key, on):
        self.on[key] = bool(on)
        self.update()

    def paintEvent(self, _):
        from .inflation_view import series_color
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pal = self.palette()
        text, muted = pal.color(QPalette.WindowText), pal.color(QPalette.PlaceholderText)
        fm = p.fontMetrics()
        x = 0.0
        self._boxes = []
        for key, kind, label in self.ITEMS:
            on = self.on[key]
            ink = text if on else muted
            c = series_color(self, "layer")
            if kind == "band":
                if on:
                    p.setPen(Qt.NoPen)
                    p.setBrush(c)
                else:
                    p.setPen(QPen(muted, 1))
                    p.setBrush(Qt.NoBrush)
                p.drawRoundedRect(QRectF(x + 0.5, 6.5, 10, 10), 2, 2)
            elif kind == "arrow":
                p.setPen(QPen(ink, 1.6, Qt.SolidLine, Qt.RoundCap))
                p.drawLine(QPointF(x, 11), QPointF(x + 11, 11))
                p.drawLine(QPointF(x + 11, 11), QPointF(x + 7, 7.5))
                p.drawLine(QPointF(x + 11, 11), QPointF(x + 7, 14.5))
            else:
                pen = QPen(ink, 1.4)
                pen.setStyle(Qt.DashLine if kind == "dash" else Qt.DotLine)
                p.setPen(pen)
                p.drawLine(QPointF(x, 11), QPointF(x + 12, 11))
            p.setPen(ink)
            f = p.font()
            f.setStrikeOut(not on)
            p.setFont(f)
            w = fm.horizontalAdvance(label)
            p.drawText(QRectF(x + 17, 0, w + 4, 22), Qt.AlignVCenter | Qt.AlignLeft, label)
            f.setStrikeOut(False)
            p.setFont(f)
            self._boxes.append((x - 4, x + 17 + w + 6, key))
            x += 17 + w + 20

    def _key_at(self, x):
        return next((k for a, b, k in self._boxes if a <= x <= b and k in self.TOGGLES), None)

    def mouseMoveEvent(self, e):
        k = self._key_at(e.position().x())
        self.setCursor(Qt.PointingHandCursor if k else Qt.ArrowCursor)
        self.setToolTip("Click to show or hide the flow arrow" if k else "")

    def mousePressEvent(self, e):
        for a, b, key in self._boxes:
            if a <= e.position().x() <= b and key in self.TOGGLES:
                self.on[key] = not self.on[key]
                self.update()
                self.toggled.emit(key, self.on[key])
                return


class SectionView(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.panel = None                # InflationPanel: scene, walls, unit
        self.r = None                    # cfd.inflation result
        self.flip = False                # internal flow: layers on the other side
        self.show = {"flow": False}
        self._key = None
        self._cut = None                 # computed cut (see _compute)
        self._msg = ""
        self._view = None                # (centre x, centre y, pixels per model unit)
        self._drag = None
        self._pending = None             # v2.14: a remembered view, for its plane
        self._exact_due = False          # v2.14.2: exact CAD cut once the plane stops
        self._rings = None               # v2.14: trimmed layer rings (cache)
        self.setMinimumHeight(320)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)
        self._timer = QTimer(self)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self._poll)
        self._timer.start()

    # ---- inputs ------------------------------------------------------------------------
    def set_panel(self, panel):
        self.panel = panel

    def set_result(self, r):
        self.r = r if r and r.get("ok") else None
        self._key = None                 # walls / unit may have changed too
        self._poll()
        self.update()

    def set_flip(self, on):
        self.flip = bool(on)
        self._key = None
        self._poll()

    def set_internal(self, on):
        """v2.13.1: internal flow = the fluid is on the other side of the walls."""
        self.set_flip(on)

    def set_show(self, key, on):
        self.show[key] = bool(on)
        self.update()

    def fit(self):
        self._view = None
        self.update()

    # ---- v2.14: the zoom, remembered per file ------------------------------------------------
    def view_state(self):
        sc = self.panel.scene if self.panel is not None else None
        if self._view is None or sc is None or not sc.section.enabled:
            return None
        return {"view": list(map(float, self._view)),
                "origin": list(map(float, sc.section.origin)),
                "normal": list(map(float, sc.section.normal))}

    def restore_view(self, st):
        """Used when the cut first shows, if the plane is still where it was."""
        self._pending = st if st and st.get("view") else None

    # ---- follow the section plane --------------------------------------------------------
    def _signature(self):
        p = self.panel
        sc = p.scene if p is not None else None
        if sc is None:
            return None
        sec = sc.section
        return (id(sc), sec.enabled, tuple(np.round(sec.origin, 9)), tuple(np.round(sec.normal, 9)),
                repr(p.walls), tuple(sc.visible.get(n) for n in sc.names),
                tuple(np.round(np.ravel(sc.model.transform), 9)) if sc.model.transform is not None
                else None, tuple(np.round(np.ravel(sc.model.offset), 9))
                if getattr(sc.model, "offset", None) is not None else None,
                sc.n_hidden_faces, self.flip, len(sc.names),
                tuple(np.round(p._dir(), 9)))

    def _poll(self):
        if not self.isVisible():
            return
        key = self._signature()
        if key == self._key:
            if self._exact_due:          # v2.14.2: the plane stopped: the exact CAD cut
                self._exact_due = False
                self._compute(exact=True)
                self.update()
            return
        new_plane = self._key is None or key is None or key[:4] != self._key[:4]
        self._key = key
        self._compute()                  # the triangles first: quick while the plane moves
        self._exact_due = self._can_exact()
        if new_plane:
            self._view = None            # refit when the plane moves to a new place
            pend, self._pending = self._pending, None
            if pend and key is not None and key[1] and \
                    np.allclose(pend["origin"], key[2], atol=1e-6) and \
                    np.allclose(pend["normal"], key[3], atol=1e-6):
                self._view = tuple(pend["view"])
        self.update()

    # ---- NEW (v2.14.2): the exact cut of CAD faces -----------------------------------------
    def _can_exact(self):
        p = self.panel
        sc = p.scene if p is not None else None
        return bool(sc is not None and sc.section.enabled and
                    hasattr(sc.model.source, "section") and not sc.model.edited)

    def _exact_poly(self, name, face_ids, o, n):
        """The part's cut from its CAD curves (smooth), as lines in 3D; None if it fails."""
        sc = self.panel.scene
        src = sc.model.source
        orig = {v: k for k, v in sc._alias.items()}.get(name, name)
        edges = src.section(orig, face_ids, o, n, getattr(src, "diag", 1.0) * 2e-6)
        if not edges:
            return None
        pts, lines, k = [], [], 0
        for e in edges:
            pts.append(e)
            lines.append(np.column_stack([np.full(len(e) - 1, 2), np.arange(k, k + len(e) - 1),
                                          np.arange(k + 1, k + len(e))]).ravel())
            k += len(e)
        poly = pv.PolyData(np.vstack(pts), lines=np.concatenate(lines))
        return poly.clean(tolerance=getattr(src, "diag", 1.0) * 1e-7, absolute=True)

    def _compute(self, exact=False):
        self._cut = None
        p = self.panel
        sc = p.scene if p is not None else None
        if sc is None:
            self._msg = "Open a CAD file."
            return
        sec = sc.section
        if not sec.enabled:
            self._msg = ("Turn on Section in the sidebar and move the plane across the walls:\n"
                         "the cut shows here, with the inflation layers drawn on it.")
            return
        o, n = np.asarray(sec.origin, float), np.asarray(sec.normal, float)
        u, v = _basis(n)
        context, obstacles = [], []
        wall_part = p.walls["part"] if p.walls else None          # None: the whole model
        exact_polys = {}                                         # v2.14.2: CAD curves
        if exact:
            for name in ([wall_part] if wall_part else
                         [nm for nm in sc.names if sc.visible.get(nm)]):
                if sc.visible.get(name):
                    try:
                        exact_polys[name] = self._exact_poly(name, None, o, n)
                    except Exception:                            # noqa: BLE001
                        exact_polys[name] = None
        for name in sc.names:
            if not sc.visible.get(name):
                continue
            try:
                ex = exact_polys.get(name)
                loops = _loops(ex if ex is not None else
                               sc.model.parts[name].slice(normal=n, origin=o), o, u, v)
            except Exception:                                    # noqa: BLE001
                continue
            context += loops
            if wall_part is not None and name != wall_part:      # v2.14: layers stop there
                obstacles += [q for q, _ in loops]
        wall = p._wall_mesh()
        if wall is None:                 # whole model
            shown = [sc.model.parts[nm] for nm in sc.names if sc.visible.get(nm)]
            wall = pv.merge(shown) if len(shown) > 1 else (shown[0] if shown else None)
        if wall is None or not wall.n_cells:
            self._msg = "No walls to show."
            return
        wall = pv.PolyData(np.asarray(wall.points), faces=wall.faces) \
            if not isinstance(wall, pv.PolyData) else wall
        wn = wall.compute_normals(cell_normals=True, point_normals=False, split_vertices=False,
                                  consistent_normals=False, auto_orient_normals=False)
        cut = wn.slice(normal=n, origin=o)
        if not cut.n_cells:
            self._msg = "The section plane doesn't cross the walls — move it in the sidebar."
            self._cut = {"context": context, "u": u, "v": v, "n": n, "segs": None}
            return
        cut = cut.clean()
        pts = (np.asarray(cut.points) - o) @ np.column_stack([u, v])
        lines = np.asarray(cut.lines).reshape(-1, 3)[:, 1:] if cut.n_lines else np.zeros((0, 2), int)
        normals = np.asarray(cut.cell_data["Normals"]) if "Normals" in cut.cell_data \
            else np.zeros((len(lines), 3))
        # in-plane normal of each segment, on the side the wall's normal points to
        a, b = pts[lines[:, 0]], pts[lines[:, 1]]
        t = b - a
        ln = np.linalg.norm(t, axis=1)
        keep = ln > 0
        a, b, t, ln, lines, normals = a[keep], b[keep], t[keep], ln[keep], lines[keep], \
            normals[keep]
        perp = np.column_stack([-t[:, 1], t[:, 0]]) / ln[:, None]
        n2 = np.column_stack([normals @ u, normals @ v])
        perp[np.einsum("ij,ij->i", perp, n2) < 0] *= -1
        if exact:                        # v2.14.2: the walls from the CAD curves (smooth)
            ex = self._exact_walls(exact_polys, wall_part, o, n)
            if ex is not None and ex.n_lines:
                e_pts = (np.asarray(ex.points) - o) @ np.column_stack([u, v])
                e_lines = np.asarray(ex.lines).reshape(-1, 3)[:, 1:]
                ea, eb = e_pts[e_lines[:, 0]], e_pts[e_lines[:, 1]]
                et = eb - ea
                eln = np.linalg.norm(et, axis=1)
                ok = eln > 0
                if ok.any():
                    e_lines, ea, eb, et, eln = e_lines[ok], ea[ok], eb[ok], et[ok], eln[ok]
                    e_perp = np.column_stack([-et[:, 1], et[:, 0]]) / eln[:, None]
                    # side: the one of the nearest triangle cut segment
                    tm, em = (a + b) / 2, (ea + eb) / 2
                    near = np.empty(len(em), int)
                    for k in range(0, len(em), 1000):
                        d2 = ((em[k:k + 1000, None, :] - tm[None]) ** 2).sum(-1)
                        near[k:k + 1000] = d2.argmin(axis=1)
                    e_perp[np.einsum("ij,ij->i", e_perp, perp[near]) < 0] *= -1
                    pts, lines, a, b, perp = e_pts, e_lines, ea, eb, e_perp
        # v2.13.2: a layer must not start inside a solid — check on the cut (normals of
        # imported CAD can point inward); open surfaces keep their normal's side
        closed = [q for q, cl in context if cl and len(q) > 3]
        if closed:
            span = np.ptp(pts, axis=0).max() or 1.0
            mid = (a + b) / 2
            bad = _inside(mid + perp * span * 1e-4, closed) & \
                ~_inside(mid - perp * span * 1e-4, closed)
            perp[bad] *= -1
        if self.flip:
            perp = -perp
        # v2.14: points along long faces, so the layers can stop part-way along them
        pts, lines, perp = densify(pts, lines, perp, (np.ptp(pts, axis=0).max() or 1.0) / 150)
        off = offsets(pts, lines, perp)
        try:                                                     # v2.14: layers that cross
            cap = collision_caps(pts, lines, off, obstacles)
        except (MemoryError, ValueError):
            cap = np.full(len(pts), np.inf)
        self._cut = {"context": context, "u": u, "v": v, "n": n, "pts": pts, "segs": lines,
                     "off": off, "cap": cap, "obstacles": obstacles}
        self._rings = None
        self._msg = ""

    def _exact_walls(self, polys, wall_part, o, n):
        """The walls' exact cut: the wall part (or its picked faces), or every part."""
        p = self.panel
        if wall_part is not None:
            if p.walls.get("faces"):
                try:
                    return self._exact_poly(wall_part, p.walls["faces"], o, n)
                except Exception:                                # noqa: BLE001
                    return None
            return polys.get(wall_part)
        got = [q for q in polys.values() if q is not None]
        if not got or len(got) < len(polys):
            return None
        return pv.merge(got) if len(got) > 1 else got[0]

    # ---- view transform ------------------------------------------------------------------
    def _to_m(self):
        f, _ = self.panel._to_metres() if self.panel is not None else (1.0, "")
        return f

    def _fit_view(self):
        c = self._cut
        if c is None:
            return None
        if c.get("segs") is not None:
            p = c["pts"]
            extra = 0.0
            if self.r is not None:        # leave room for the layers
                extra = (self.r["y_tot"] + self.r["y_des"]) / self._to_m()
            lo, hi = p.min(axis=0) - extra, p.max(axis=0) + extra
        elif c["context"]:
            allp = np.vstack([q for q, _ in c["context"]])
            lo, hi = allp.min(axis=0), allp.max(axis=0)
        else:
            return None
        span = np.maximum(hi - lo, 1e-12)
        w, h = max(self.width() - 60, 50), max(self.height() - 80, 50)
        k = min(w / span[0], h / span[1])
        mid = (lo + hi) / 2
        return float(mid[0]), float(mid[1]), float(k)

    def _xf(self):
        if self._view is None:
            self._view = self._fit_view()
        return self._view

    def _px(self, xy, view):
        cx, cy, k = view
        return (self.width() / 2 + (xy[..., 0] - cx) * k,
                self.height() / 2 + 10 - (xy[..., 1] - cy) * k)

    # ---- drawing -------------------------------------------------------------------------
    def paintEvent(self, _):
        from .inflation_view import series_color, show_length
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pal = self.palette()
        text = pal.color(QPalette.WindowText)
        muted = pal.color(QPalette.PlaceholderText)
        font = QFont(p.font())
        font.setPixelSize(11)
        p.setFont(font)
        c = self._cut
        view = self._xf() if c is not None else None
        if view is None:
            p.setPen(muted)
            p.drawText(self.rect(), Qt.AlignCenter, self._msg or "—")
            return

        # the model's cut, for context (light fill + outline)
        fill = QColor(text)
        fill.setAlphaF(0.06)
        edge = QColor(text)
        edge.setAlphaF(0.30)
        path = QPainterPath()
        path.setFillRule(Qt.OddEvenFill)
        for q, closed in c["context"]:
            xs, ys = self._px(q, view)
            path.moveTo(xs[0], ys[0])
            for x, y in zip(xs[1:], ys[1:]):
                path.lineTo(x, y)
            if closed:
                path.closeSubpath()
        p.fillPath(path, fill)
        p.setPen(QPen(edge, 1))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)

        r = self.r
        if c.get("segs") is not None:
            to_m = self._to_m()
            k = view[2]
            pts, segs, off, cap = c["pts"], c["segs"], c["off"], c["cap"]
            layer = series_color(self, "layer")

            def ring(d):
                """Path of the wall cut pushed out by d (model units)."""
                q = pts + off * d
                xs, ys = self._px(q, view)
                pa = QPainterPath()
                for i, j in segs:
                    pa.moveTo(xs[i], ys[i])
                    pa.lineTo(xs[j], ys[j])
                return pa

            def trimmed(n_layer, d):
                """v2.14: ring n, without the parts that crossed (cached)."""
                key = (id(r), id(c))
                if self._rings is None or self._rings[0] != key:
                    self._rings = (key, {})
                cache = self._rings[1]
                if n_layer not in cache:
                    cache[n_layer] = trimmed_ring(pts, segs, off, cap, d, c["obstacles"])
                q0, q1 = cache[n_layer]
                x0, y0 = self._px(q0, view)
                x1, y1 = self._px(q1, view)
                pa = QPainterPath()
                for k_ in range(len(x0)):
                    pa.moveTo(x0[k_], y0[k_])
                    pa.lineTo(x1[k_], y1[k_])
                return pa

            def band(d0, d1):                 # v2.14: no thicker than each point's cap
                q0 = pts + off * np.minimum(d0, cap)[:, None]
                q1 = pts + off * np.minimum(d1, cap)[:, None]
                x0, y0 = self._px(q0, view)
                x1, y1 = self._px(q1, view)
                pa = QPainterPath()
                pa.setFillRule(Qt.WindingFill)
                for i, j in segs:
                    pa.moveTo(x0[i], y0[i])
                    pa.lineTo(x0[j], y0[j])
                    pa.lineTo(x1[j], y1[j])
                    pa.lineTo(x1[i], y1[i])
                    pa.closeSubpath()
                return pa

            if r is not None:
                tops = np.asarray(r["total"]) / to_m             # layer tops, model units
                soft = QColor(layer)
                soft.setAlphaF(0.20)
                p.fillPath(band(0.0, tops[-1]), soft)
                gaps = np.diff(tops) * k                        # px between layer tops
                solid = 0
                while solid < len(gaps) and gaps[solid] < MIN_GAP_PX:
                    solid += 1
                if solid:
                    dense = QColor(layer)
                    dense.setAlphaF(0.65)
                    p.fillPath(band(0.0, tops[solid]), dense)
                line = QColor(layer)
                line.setAlphaF(0.85)
                p.setPen(QPen(line, 1))
                for i in range(max(solid, 1), len(tops)):
                    p.drawPath(trimmed(i, tops[i]))
            # the walls themselves
            p.setPen(QPen(text, 1.6))
            p.drawPath(ring(0.0))

        # header line, scale bar, hint — on a soft backing, so they stay readable
        back = QColor(pal.color(QPalette.Window))
        back.setAlphaF(0.82)
        p.setPen(Qt.NoPen)
        p.setBrush(back)
        p.drawRoundedRect(QRectF(0, 0, min(self.width(), 470), 20), 6, 6)
        p.drawRoundedRect(QRectF(0, self.height() - 34, 170, 34), 6, 6)
        p.drawRoundedRect(QRectF(self.width() - 290, self.height() - 20, 290, 20), 6, 6)
        p.setPen(muted)
        n = c["n"]
        walls = (self.panel.wall_menu.currentText() if self.panel is not None else "") or "walls"
        p.drawText(QRectF(4, 3, self.width() - 8, 14), Qt.AlignLeft | Qt.AlignVCenter,
                   f"Section through {walls} · plane normal ({n[0]:.3g}, {n[1]:.3g}, {n[2]:.3g})"
                   " · layers: estimate")
        if c.get("segs") is None:
            p.drawText(self.rect(), Qt.AlignCenter, self._msg)
        elif r is None:
            p.drawText(self.rect(), Qt.AlignCenter, "Fill in the CFD mode inputs in the sidebar")
        if self.show["flow"]:
            self._draw_flow(p, c, text, muted, back)
        # scale bar (model units shown as metres with the file's unit)
        k = view[2]
        to_m = self._to_m()
        target = 120 / k                                          # model units in ~120 px
        step = nice(target * to_m) / to_m
        x0, yb = 6.0, self.height() - 12.0
        p.setPen(QPen(text, 2))
        p.drawLine(QPointF(x0, yb), QPointF(x0 + step * k, yb))
        p.setPen(text)
        p.drawText(QRectF(x0, yb - 17, 200, 14), Qt.AlignLeft | Qt.AlignVCenter,
                   show_length(step * to_m))
        p.setPen(muted)
        p.drawText(QRectF(0, self.height() - 18, self.width() - 4, 14),
                   Qt.AlignRight | Qt.AlignVCenter,
                   "Scroll to zoom · drag to pan · double-click to fit")

    def _draw_flow(self, p, c, text, muted, back):
        """v2.13.1: the flow direction (sidebar ▸ Flow ▸ Direction) seen on the plane.
        v2.14.2: three thin inlet arrows on the upstream edge of the view, pointing in
        (like streamlines coming in); a small dot / cross symbol when the flow goes
        through the plane."""
        d = self.panel._dir() if self.panel is not None else np.zeros(3)
        nd = np.linalg.norm(d)
        if nd == 0:
            return
        d = d / nd
        a = np.array([d @ c["u"], d @ c["v"]])
        out = float(d @ c["n"])                       # towards the viewer
        ink = QColor(text)
        ink.setAlphaF(0.55)
        w, h = float(self.width()), float(self.height())
        if np.linalg.norm(a) < 0.25:                  # mostly through the plane
            cx, cy = w - 26.0, 44.0
            p.setPen(QPen(ink, 1.5))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QPointF(cx, cy), 10, 10)
            if out > 0:                               # coming out: a dot
                p.setPen(Qt.NoPen)
                p.setBrush(ink)
                p.drawEllipse(QPointF(cx, cy), 3, 3)
            else:                                     # going in: a cross
                p.drawLine(QPointF(cx - 6, cy - 6), QPointF(cx + 6, cy + 6))
                p.drawLine(QPointF(cx - 6, cy + 6), QPointF(cx + 6, cy - 6))
            p.setPen(muted)
            p.drawText(QRectF(cx - 220, cy - 7, 204, 14), Qt.AlignRight | Qt.AlignVCenter,
                       "Flow towards you" if out > 0 else "Flow away from you")
            return
        a = a / np.linalg.norm(a)
        dx, dy = a[0], -a[1]                          # screen y goes down
        px, py = -dy, dx                              # across the flow
        cx, cy = w / 2, h / 2 + 10
        # from the middle to the upstream edge of the view (clear of the header / footer)
        reach = min((cx - 18) / abs(dx) if abs(dx) > 1e-6 else np.inf,
                    (cy - 40) / abs(dy) if abs(dy) > 1e-6 else np.inf)
        bx, by = cx - dx * reach, cy - dy * reach
        length, gap = 44.0, 30.0
        for k in (-1, 0, 1):
            tx, ty = bx + px * gap * k, by + py * gap * k
            tip = QPointF(tx + dx * length, ty + dy * length)
            p.setPen(QPen(ink, 1.5, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(tx, ty), tip)
            head = QPainterPath(tip)                  # small filled head
            for s_ in (1, -1):
                head.lineTo(tip.x() - dx * 8 + px * 4 * s_, tip.y() - dy * 8 + py * 4 * s_)
            head.closeSubpath()
            p.fillPath(head, ink)
        sides = [(bx + px * gap * k + dx * length / 2, by + py * gap * k + dy * length / 2)
                 for k in (1.9, -1.9)]               # the label beside the arrows, in view
        lx, ly = next(((x, y) for x, y in sides if 30 <= y <= h - 44 and 10 <= x <= w - 10),
                      sides[0])
        ly = min(max(ly, 30.0), h - 44)
        p.setPen(muted)
        label = "Flow" + (f" · {abs(out) * 100:.0f} % through the plane" if abs(out) > 0.2
                          else "")
        tw = p.fontMetrics().horizontalAdvance(label) + 8
        rx = min(max(lx - tw / 2, 4.0), w - tw - 4)          # kept in the view
        p.drawText(QRectF(rx, ly - 7, tw, 14), Qt.AlignCenter, label)

    # ---- zoom / pan ----------------------------------------------------------------------
    def wheelEvent(self, e):
        view = self._xf()
        if view is None:
            return
        cx, cy, k = view
        f = 1.0015 ** e.angleDelta().y()
        mx, my = e.position().x(), e.position().y()
        # keep the point under the cursor fixed
        wx = cx + (mx - self.width() / 2) / k
        wy = cy - (my - self.height() / 2 - 10) / k
        k2 = k * f
        self._view = (wx - (mx - self.width() / 2) / k2,
                      wy + (my - self.height() / 2 - 10) / k2, k2)
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self._xf() is not None:
            self._drag = (e.position(), self._view)

    def mouseMoveEvent(self, e):
        if self._drag is None:
            return
        start, (cx, cy, k) = self._drag
        d = e.position() - start
        self._view = (cx - d.x() / k, cy + d.y() / k, k)
        self.update()

    def mouseReleaseEvent(self, _):
        self._drag = None

    def mouseDoubleClickEvent(self, _):
        self.fit()
