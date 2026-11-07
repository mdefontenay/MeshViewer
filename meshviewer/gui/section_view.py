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
            return
        new_plane = self._key is None or key is None or key[:4] != self._key[:4]
        self._key = key
        self._compute()
        if new_plane:
            self._view = None            # refit when the plane moves to a new place
        self.update()

    def _compute(self):
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
        context = []
        for name in sc.names:
            if not sc.visible.get(name):
                continue
            try:
                context += _loops(sc.model.parts[name].slice(normal=n, origin=o), o, u, v)
            except Exception:                                    # noqa: BLE001
                pass
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
        off = offsets(pts, lines, perp)
        self._cut = {"context": context, "u": u, "v": v, "n": n, "pts": pts, "segs": lines,
                     "off": off}
        self._msg = ""

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
            pts, segs, off = c["pts"], c["segs"], c["off"]
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

            def band(d0, d1):
                q0, q1 = pts + off * d0, pts + off * d1
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
                    p.drawPath(ring(tops[i]))
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
        """v2.13.1: the flow direction (sidebar ▸ Flow ▸ Direction) seen on the plane,
        in the top-right corner; a dot / cross when it goes through the plane."""
        d = self.panel._dir() if self.panel is not None else np.zeros(3)
        nd = np.linalg.norm(d)
        cx, cy, rad = self.width() - 62.0, 62.0, 34.0
        p.setPen(Qt.NoPen)
        p.setBrush(back)
        p.drawRoundedRect(QRectF(cx - rad - 12, cy - rad - 10, 2 * rad + 24, 2 * rad + 34), 8, 8)
        p.setPen(muted)
        p.drawText(QRectF(cx - 60, cy + rad + 4, 120, 14), Qt.AlignCenter, "Flow")
        if nd == 0:
            p.drawText(QRectF(cx - 60, cy - 7, 120, 14), Qt.AlignCenter, "no direction")
            return
        d = d / nd
        a = np.array([d @ c["u"], d @ c["v"]])
        out = float(d @ c["n"])                       # towards the viewer
        p.setPen(QPen(text, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        if np.linalg.norm(a) < 0.25:                  # mostly through the plane
            p.drawEllipse(QPointF(cx, cy), 13, 13)
            if out > 0:                               # coming out: a dot
                p.setBrush(text)
                p.drawEllipse(QPointF(cx, cy), 3.5, 3.5)
            else:                                     # going in: a cross
                p.drawLine(QPointF(cx - 9, cy - 9), QPointF(cx + 9, cy + 9))
                p.drawLine(QPointF(cx - 9, cy + 9), QPointF(cx + 9, cy - 9))
            return
        a = a / np.linalg.norm(a)
        dx, dy = a[0], -a[1]                          # screen y goes down
        tail = QPointF(cx - dx * rad, cy - dy * rad)
        tip = QPointF(cx + dx * rad, cy + dy * rad)
        p.drawLine(tail, tip)
        for ang in (0.5, -0.5):                       # arrow head
            ca, sa = np.cos(ang), np.sin(ang)
            hx, hy = -(dx * ca - dy * sa), -(dx * sa + dy * ca)
            p.drawLine(tip, QPointF(tip.x() + hx * 11, tip.y() + hy * 11))
        if abs(out) > 0.2:
            p.setPen(muted)
            p.drawText(QRectF(cx - 60, cy + rad - 8, 120, 12), Qt.AlignCenter,
                       f"{abs(out) * 100:.0f} % through the plane")

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
