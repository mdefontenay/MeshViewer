"""The "Section" tab of the Inflation Layers page.

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

The view follows the section plane (checked a few times a second while shown).
Only the walls and the layers are drawn; a layer never starts inside the solid
(tested on the cut) and "Flip side" swaps the side. Layers stop where they would
cross — walls facing each other meet half-way, a concave curve at its centre,
another part where they reach it (collision_caps, trimmed_ring). STEP / IGES / BREP
walls are cut from the CAD curves once the plane stops moving (triangles while it
moves). The flow arrow is three inlet arrows on the upstream edge; the zoom is
remembered per file (view_state / restore_view). The 2D geometry is in
core/geometry2d.py.
"""
from __future__ import annotations

import numpy as np
import pyvista as pv
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPalette, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget
from meshviewer.core.geometry2d import MIN_GAP_PX, _basis, _loops, nice, _inside, offsets, densify, collision_caps, trimmed_ring
from meshviewer.core.polys import bare

# --- layers that cross --------------------------------------------------------


class SectionLegend(QWidget):
    """the legend of the Section tab, same look as the plot's.
    the layers are always shown; "Flow direction" shows / hides the arrow."""
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
        from meshviewer.gui.pages.inflation import series_color
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
        self._pending = None             # a remembered view, for its plane
        self._exact_due = False          # exact CAD cut once the plane stops
        self._rings = None               # trimmed layer rings (cache)
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

    def set_show(self, key, on):
        self.show[key] = bool(on)
        self.update()

    def fit(self):
        self._view = None
        self.update()

    # ---- the zoom, remembered per file ------------------------------------------------
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
            if self._exact_due:          # the plane stopped: the exact CAD cut
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

    # --- the exact cut of CAD faces -----------------------------------------
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
        exact_polys = {}                                         # CAD curves
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
            if wall_part is not None and name != wall_part:      # layers stop there
                obstacles += [q for q, _ in loops]
        wall = p._wall_mesh()
        if wall is None:                 # whole model
            shown = [sc.model.parts[nm] for nm in sc.names if sc.visible.get(nm)]
            wall = pv.merge(shown) if len(shown) > 1 else (shown[0] if shown else None)
        if wall is None or not wall.n_cells:
            self._msg = "No walls to show."
            return
        wall = bare(wall) if not isinstance(wall, pv.PolyData) else wall
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
        if exact:                        # the walls from the CAD curves (smooth)
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
        # a layer must not start inside a solid — check on the cut (normals of
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
        # points along long faces, so the layers can stop part-way along them
        pts, lines, perp = densify(pts, lines, perp, (np.ptp(pts, axis=0).max() or 1.0) / 150)
        off = offsets(pts, lines, perp)
        try:                                                     # layers that cross
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
        from meshviewer.gui.pages.inflation import series_color
        from meshviewer.core.units import show_length
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
                """ring n, without the parts that crossed (cached)."""
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

            def band(d0, d1):                 # no thicker than each point's cap
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
            p.drawText(self.rect(), Qt.AlignCenter, "Fill in Inflation Layers in the CFD tool")
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
        """the flow direction (sidebar ▸ Flow ▸ Direction) seen on the plane.
        three thin inlet arrows on the upstream edge of the view, pointing in
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
