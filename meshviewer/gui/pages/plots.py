"""The tab of a plot under the 3D view (F13), drawn like the Inflation Layers
plots (inflation.py: same grid, ticks, axis titles, hover).

    Root                                             ● wing  ● tip  ○ reference
    Section · plane Y = 0.35 m · cp along x/c
    ┌───────────────────────────────────────────────────────────────────────┐
    │   −cp (Negative up) … one line per cut loop, in its boundary's colour │
    └───────────────────────────────────────────────────────────────────────┘

One page for every plot: the window shows the one whose tab is chosen
(show(m, r, …)). Hover a line for its point under the cursor, anywhere along it (between
the points where the plane crosses mesh edges, the line is straight). The plot's Axes
(min / max, log, flip: cp is drawn with y flipped, negative up) set how it is drawn; the
wheel zooms, a drag pans, a double-click fits (written back to its Axes).

Save Screenshot on a plot's tab saves this page (`save_picture`): PNG or JPEG drawn at
the scale asked, SVG as vector shapes — the page painted into a QSvgGenerator, so the
lines, the frame and the text are SVG paths and text, crisp at any size.
"""
from __future__ import annotations

import numpy as np
from pathlib import Path

from PySide6.QtCore import QPointF, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPainterPath, QPalette, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QToolTip, QVBoxLayout, QWidget

from meshviewer.core import plots
from meshviewer.core.units import nice_num, nice_step
from meshviewer.gui.forms import PAGE_MARGINS
from meshviewer.gui.pages.inflation import _Plot


class CrossSectionPlot(_Plot):
    """The plot of a section: its curves, the reference points, hover anywhere along a
    line. Its axes (`view`, from the plot's Axes): typed ranges, log, flipped. The wheel
    zooms around the cursor, a drag pans, a double-click fits (`ranges_changed`)."""
    PAD_L, PAD_R, PAD_T, PAD_B = 70, 24, 14, 40
    EMPTY = "The plane misses the visible boundaries"
    ranges_changed = Signal(object)      # (x0, x1, y0, y1) in the units shown, None = auto

    def __init__(self, parent=None):
        super().__init__(parent)
        self.curves, self.ref = [], []
        self.titles = ("", "")
        self._r = None                   # ((x0, x1), (y0, y1)) on the axes (log10 if log)
        self.view = {}
        self._drag = None

    # ---- data <-> the axes (log10 for a log axis) <-> pixels ---------------------------
    def _log(self, axis):
        return bool(self.view.get(f"{axis}_log"))

    def _flip(self, axis):
        return bool(self.view.get("x_flip" if axis == "x" else "y_flip"))

    def _t(self, v, axis):
        v = np.asarray(v, dtype=float)
        if not self._log(axis):
            return v
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.where(v > 0, np.log10(np.where(v > 0, v, 1.0)), np.nan)

    def _data(self, t, axis):
        return 10.0 ** t if self._log(axis) else t

    def set_data(self, curves, ref, x_title, y_title, view=None):
        """curves: [(x (n,), y (n,), QColor, part)], ref: [(x, y)] (shown units);
        view: x_min … y_max (None = auto), x_log, y_log, x_flip, y_flip."""
        self.curves, self.ref = curves, ref
        self.titles = (x_title, y_title)
        self.view = dict(view or {})
        xs = [c[0] for c in curves] + ([np.array([p[0] for p in ref])] if ref else [])
        ys = [c[1] for c in curves] + ([np.array([p[1] for p in ref])] if ref else [])
        self._r = None
        self._why = None
        if curves:
            tx = self._t(np.concatenate(xs), "x")
            ty = self._t(np.concatenate(ys), "y")
            tx, ty = tx[np.isfinite(tx)], ty[np.isfinite(ty)]
            if len(tx) and len(ty):
                self._r = (self._auto(tx, "x", 0.02), self._auto(ty, "y", 0.04))
                self._r = tuple(self._typed(rng, axis) for rng, axis in zip(self._r, "xy"))
            else:                                         # a log axis, nothing above 0
                self._why = "No values above 0 for the log scale (Axes ▸ Log)"
        self.hover = None
        self.update()

    def _auto(self, t, axis, pad):
        t0, t1 = float(t.min()), float(t.max())
        d = t1 - t0
        if not d > 1e-9 * max(1.0, abs(t0), abs(t1)):         # one value: a little room
            d = 0.1 * abs(t0) or 1.0
            t0, t1 = t0 - d / 2, t1 + d / 2
        if axis == "y" and not self._log("y"):                # round to the ticks
            step = nice_step(d * 1.1, 5)
            return (np.floor((t0 - pad * d) / step) * step, np.ceil((t1 + pad * d) / step) * step)
        return (t0 - pad * d, t1 + pad * d)

    def _typed(self, rng, axis):
        """A typed Min / Max replaces the auto end (a log axis: only above 0)."""
        out = list(rng)
        for i, end in enumerate(("min", "max")):
            v = self.view.get(f"{axis}_{end}")
            if v is not None and (not self._log(axis) or v > 0):
                out[i] = float(self._t(v, axis))
        if not out[1] > out[0]:
            return rng
        return tuple(out)

    def _ranges(self):
        return self._r

    def _frac(self, v, axis):
        (lo, hi) = self._r[0 if axis == "x" else 1]
        f = (np.asarray(self._t(v, axis), dtype=float) - lo) / (hi - lo)
        return 1.0 - f if self._flip(axis) else f

    def _pxa(self, x, y):
        """Pixels (arrays) of data points; NaN where a log axis can't show them."""
        w = self.width() - self.PAD_L - self.PAD_R
        h = self.height() - self.PAD_T - self.PAD_B
        return (self.PAD_L + self._frac(x, "x") * w,
                self.PAD_T + (1.0 - self._frac(y, "y")) * h)

    def _px(self, x, y):
        a, b = self._pxa(x, y)
        return QPointF(float(a), float(b))

    def _at(self, px, py):
        """The axes' coordinates (log10 on a log axis) under a pixel."""
        (x0, x1), (y0, y1) = self._r
        w = self.width() - self.PAD_L - self.PAD_R
        h = self.height() - self.PAD_T - self.PAD_B
        fx = (px - self.PAD_L) / max(w, 1)
        fy = 1.0 - (py - self.PAD_T) / max(h, 1)
        fx = 1.0 - fx if self._flip("x") else fx
        fy = 1.0 - fy if self._flip("y") else fy
        return x0 + fx * (x1 - x0), y0 + fy * (y1 - y0)

    def _ticks(self, axis, n):
        """[(data value, label)] inside the range: decades (and 2, 5 when few) on a log
        axis, nice steps otherwise."""
        (t0, t1) = self._r[0 if axis == "x" else 1]
        out = []
        if self._log(axis):
            mults = (1,) if t1 - t0 > 3 else (1, 2, 5)
            for k in range(int(np.floor(t0)) - 1, int(np.ceil(t1)) + 1):
                for m in mults:
                    t = np.log10(m) + k
                    if t0 - 1e-9 <= t <= t1 + 1e-9:
                        out.append((10.0 ** t, nice_num(10.0 ** t)))
            return out
        step = nice_step(t1 - t0, n)
        t = np.ceil(t0 / step) * step
        for _ in range(80):
            if t > t1 + 1e-9 * step:
                break
            out.append((t, nice_num(0.0 if abs(t) < 1e-9 * step else t)))
            t += step
        return out

    def _frame(self, p, y_title, x_title, y_ticks, x_ticks):
        """Grid lines at every tick, the numbers, the two axis titles."""
        left, right = self.PAD_L, self.width() - self.PAD_R
        top, base = self.PAD_T, self.height() - self.PAD_B
        for v, text in y_ticks:
            _, y = self._pxa(left, v)
            y = float(y)
            p.setPen(QPen(self._grid, 1))
            p.drawLine(QPointF(left, y), QPointF(right, y))
            p.setPen(self._muted)
            p.drawText(QRectF(4, y - 7, left - 14, 14), Qt.AlignRight | Qt.AlignVCenter, text)
        for v, text in x_ticks:
            q, _ = self._pxa(v, 1.0)
            q = float(q)
            p.setPen(QPen(self._grid, 1))
            p.drawLine(QPointF(q, top), QPointF(q, base))
            p.setPen(self._muted)
            p.drawText(QRectF(q - 30, base + 6, 60, 14), Qt.AlignHCenter, text)
        p.setPen(self._text)
        p.drawText(QRectF(left, self.height() - 16, right - left, 14), Qt.AlignHCenter, x_title)
        p.save()
        p.translate(12, (top + base) / 2)
        p.rotate(-90)
        p.drawText(QRectF(-(base - top) / 2, -7, base - top, 14), Qt.AlignCenter, y_title)
        p.restore()

    def _hover_at(self, p, x, q, c):
        cross = QColor(self._text)
        cross.setAlphaF(0.25)
        p.setPen(QPen(cross, 1))
        p.drawLine(QPointF(x, self.PAD_T), QPointF(x, self.height() - self.PAD_B))
        p.setPen(QPen(self.palette().color(QPalette.Window), 2))
        p.setBrush(c)
        p.drawEllipse(q, 4.5, 4.5)

    def paintEvent(self, _):
        p = self._begin()
        if self._r is None:
            return self._empty(p, getattr(self, "_why", None))
        self._frame(p, self.titles[1], self.titles[0], self._ticks("y", 5), self._ticks("x", 8))
        p.save()                                       # zoomed in: only inside the axes
        p.setClipRect(QRectF(self.PAD_L, self.PAD_T, self.width() - self.PAD_L - self.PAD_R,
                             self.height() - self.PAD_T - self.PAD_B))
        for x, y, c, _part in self.curves:
            px, py = self._pxa(x, y)
            ok = np.isfinite(px) & np.isfinite(py)
            if ok.sum() < 2:
                continue
            path = QPainterPath()
            first = True
            for a, b, good in zip(px, py, ok):
                if not good:
                    first = True
                    continue
                q = QPointF(float(a), float(b))
                path.moveTo(q) if first else path.lineTo(q)
                first = False
            p.setPen(QPen(c, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)
        if self.ref:
            p.setPen(QPen(self._text, 1.4))
            p.setBrush(Qt.NoBrush)
            for a, b in self.ref:
                q = self._px(a, b)
                if np.isfinite(q.x()) and np.isfinite(q.y()):
                    p.drawEllipse(q, 3.2, 3.2)
        p.restore()
        if self.hover is not None:
            a, b, c, _part = self.hover
            q = self._px(a, b)
            if np.isfinite(q.x()) and np.isfinite(q.y()):
                self._hover_at(p, q.x(), q, c)

    def _nearest(self, pos):
        """The point of a line nearest the cursor (within 30 px): anywhere along its
        segments, the values in between taken linearly."""
        best = None
        cx, cy = pos.x(), pos.y()
        for x, y, c, part in self.curves:
            x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
            if not len(x):
                continue
            px, py = self._pxa(x, y)
            ok = np.isfinite(px) & np.isfinite(py)
            if len(x) > 1:                           # segments between good points
                seg = np.flatnonzero(ok[:-1] & ok[1:])
                ax, ay = px[seg], py[seg]
                dx, dy = px[seg + 1] - ax, py[seg + 1] - ay
                dd = dx * dx + dy * dy
                t = np.clip(((cx - ax) * dx + (cy - ay) * dy) / np.where(dd > 0, dd, 1), 0, 1)
                d = (ax + t * dx - cx) ** 2 + (ay + t * dy - cy) ** 2
                if len(d):
                    i = int(np.argmin(d))
                    if best is None or d[i] < best[0]:
                        k, u = seg[i], float(t[i])
                        a = x[k] + u * (x[k + 1] - x[k])
                        b = y[k] + u * (y[k + 1] - y[k])
                        best = (float(d[i]), (float(a), float(b), c, part))
            lone = np.flatnonzero(ok)                # points with no segment: themselves
            if len(lone):
                d = (px[lone] - cx) ** 2 + (py[lone] - cy) ** 2
                i = int(np.argmin(d))
                if best is None or d[i] < best[0]:
                    best = (float(d[i]), (float(x[lone[i]]), float(y[lone[i]]), c, part))
        return best[1] if best and best[0] < 30 ** 2 else None

    # ---- zoom, pan, fit --------------------------------------------------------------
    def _emit_ranges(self):
        (x0, x1), (y0, y1) = self._r
        self.ranges_changed.emit((self._data(x0, "x"), self._data(x1, "x"),
                                  self._data(y0, "y"), self._data(y1, "y")))

    def wheelEvent(self, e):
        if self.locked():                              # 🔒 Lock: no zoom
            e.ignore()
            return
        if self._r is None:
            return
        f = 0.85 ** (e.angleDelta().y() / 120.0)
        cx, cy = self._at(e.position().x(), e.position().y())
        (x0, x1), (y0, y1) = self._r
        self._r = ((cx + (x0 - cx) * f, cx + (x1 - cx) * f),
                   (cy + (y0 - cy) * f, cy + (y1 - cy) * f))
        self.update()
        self._emit_ranges()
        e.accept()

    def drawn_ranges(self):
        """(x0, x1, y0, y1) as drawn, in the units shown (None: nothing drawn)."""
        if self._r is None:
            return None
        (x0, x1), (y0, y1) = self._r
        return (float(self._data(x0, "x")), float(self._data(x1, "x")),
                float(self._data(y0, "y")), float(self._data(y1, "y")))

    def locked(self):
        return bool(self.view.get("lock")) if hasattr(self, "view") else False

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and self._r is not None and not self.locked():
            self._drag = (e.position(), self._r)

    def mouseReleaseEvent(self, e):
        if self._drag is not None and self._r is not self._drag[1]:
            self._emit_ranges()
        self._drag = None

    def mouseDoubleClickEvent(self, e):
        if not self.locked():
            self.ranges_changed.emit((None, None, None, None))   # fit

    def mouseMoveEvent(self, e):
        if self._r is None:
            return
        if self._drag is not None and e.buttons() & Qt.LeftButton:
            start, (rx, ry) = self._drag
            ax, ay = self._at(start.x(), start.y())
            bx, by = self._at(e.position().x(), e.position().y())
            self._r = ((rx[0] - (bx - ax), rx[1] - (bx - ax)),
                       (ry[0] - (by - ay), ry[1] - (by - ay)))
            self._drag = (start, (rx, ry))
            self.update()
            return
        h = self._nearest(e.position())
        if h != self.hover:
            self.hover = h
            self.update()
        if h is None:
            QToolTip.hideText()
            return
        a, b, _c, part = h
        QToolTip.showText(e.globalPosition().toPoint(),
                          f"{part}\n{self.titles[0]}  {nice_num(a)}\n"
                          f"{self.titles[1]}  {nice_num(b)}", self)


class _Legend(QWidget):
    """A dot + name per boundary, a ring for the reference points."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.items = []
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.setFixedHeight(18)

    def set_items(self, items):                     # [(name, QColor or None = ring)]
        self.items = items
        fm = self.fontMetrics()
        self.setFixedWidth(sum(fm.horizontalAdvance(n) + 26 for n, _ in items) + 4)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        text = self.palette().color(QPalette.WindowText)
        x = 2
        for name, c in self.items:
            if c is None:
                p.setPen(QPen(text, 1.4))
                p.setBrush(Qt.NoBrush)
            else:
                p.setPen(Qt.NoPen)
                p.setBrush(c)
            p.drawEllipse(QPointF(x + 5, 9), 4, 4)
            p.setPen(text)
            w = self.fontMetrics().horizontalAdvance(name)
            p.drawText(QRectF(x + 14, 0, w + 4, 18), Qt.AlignVCenter | Qt.AlignLeft, name)
            x += w + 26
        p.end()


def _kept(lo, hi):
    """values -> True where lo < v < hi (None: open on that side)."""
    def kept(v):
        v = np.asarray(v, dtype=float)
        ok = np.isfinite(v)
        if lo is not None:
            ok = ok & (v > lo)
        if hi is not None:
            ok = ok & (v < hi)
        return ok
    return kept


class PlotPage(QWidget):
    ranges_changed = Signal(int, object)         # plot id, (x0, x1, y0, y1): zoom / pan / fit

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PlotPage")
        self.setAttribute(Qt.WA_StyledBackground, True)     # the page color, not black
        self.ident = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(*PAGE_MARGINS)
        lay.setSpacing(4)
        top = QHBoxLayout()
        self.title = QLabel("")
        self.title.setObjectName("PageTitle")
        top.addWidget(self.title)
        top.addStretch(1)
        self.legend = _Legend()
        top.addWidget(self.legend, 0, Qt.AlignBottom)
        lay.addLayout(top)
        self.subtitle = QLabel("")
        self.subtitle.setObjectName("InfoLine")
        lay.addWidget(self.subtitle)
        lay.addSpacing(8)
        self.plot = CrossSectionPlot()
        self.plot.ranges_changed.connect(
            lambda rng: self.ident is not None and self.ranges_changed.emit(self.ident, rng))
        lay.addWidget(self.plot, 1)

    def show(self, m, r, colors, scale, unit, value_unit=None):
        """m: the plot, r: its compute() result, colors: part -> hex,
        (scale, unit): file lengths -> shown; value_unit: (convert, label) of a field's
        values (Contours ▸ Unit in file / Shown in), or None."""
        self.ident = m["id"]
        self.title.setText(m["name"])
        coord = r["value"].startswith(plots.COORD)
        conv, vlabel = value_unit or ((lambda v: v), "")
        if coord:
            conv, vlabel = (lambda v: v * scale), unit
        xs = 1.0 if r["chord_on"] else scale
        u = f" ({unit})" if unit else ""
        x_title = "x/c" if r["chord_on"] else f"{r['along'].upper()}{u}"
        y_title = plots.value_title(r["value"]) + (f" ({vlabel})" if vlabel else "")
        n = np.asarray(r["normal"], dtype=float)
        k = int(np.argmax(np.abs(n)))
        if abs(abs(n[k]) - 1) < 1e-9:
            where = (f"{plots.AXES[k].upper()} = " + nice_num(r["origin"][k] * scale)
                     + (f" {unit}" if unit else ""))
        else:
            where = ("through (" + ", ".join(nice_num(v * scale) for v in r["origin"])
                     + ")" + (f" {unit}" if unit else "") + ", normal ("
                     + ", ".join(nice_num(v) for v in (m.get("normal") or n)) + ")")
        self.subtitle.setText(f"{plots.KINDS[m['kind']]['title']} · plane {where} · "
                              f"{y_title} along {x_title}")
        curves = [(c["x"] * xs, np.asarray(conv(c["y"]), dtype=float),
                   QColor(colors.get(c["part"], "#8e8e93")), c["part"]) for c in r["curves"]]
        ref = [tuple(p[:2]) for p in (m.get("ref") or {}).get("points", [])]
        vk = _kept(m.get("value_min"), m.get("value_max"))     # the data filters
        ak = _kept(m.get("along_min"), m.get("along_max"))
        curves = [(x, np.where(vk(y) & ak(x), y, np.nan), col, part)
                  for x, y, col, part in curves]
        ref = [(a, b) for a, b in ref if vk(b) and ak(a)]
        if m.get("swap"):                             # Swap Axes: the value across
            curves = [(y, x, col, part) for x, y, col, part in curves]
            ref = [(y, x) for x, y in ref]
            x_title, y_title = y_title, x_title
        view = {k: m.get(k) for k in ("x_min", "x_max", "y_min", "y_max", "x_log", "y_log",
                                      "x_flip", "lock")}
        view["y_flip"] = plots.y_flipped(m, r["value"])   # as set now (cp: negative up)
        self.plot.set_data(curves, ref, x_title, y_title, view)
        names = []
        for c in r["curves"]:
            if c["part"] not in [n for n, _ in names]:
                names.append((c["part"], QColor(colors.get(c["part"], "#8e8e93"))))
        if ref:
            names.append((m["ref"]["name"], None))
        self.legend.set_items(names)

    # ---- Save Screenshot ---------------------------------------------------------------
    def _paint_into(self, p):
        """The page and its children painted with painter `p` (an SVG or an image)."""
        from PySide6.QtCore import QPoint
        from PySide6.QtGui import QRegion
        self.render(p, QPoint(0, 0), QRegion(),
                    QWidget.RenderFlag.DrawChildren | QWidget.RenderFlag.DrawWindowBackground)

    def save_picture(self, path, scale=2):
        """This page as a picture, by the extension: .svg vector shapes, .jpg / .jpeg a
        JPEG, else a PNG (.png added) -> the path written."""
        path = Path(path)
        ext = path.suffix.lower()
        w, h = self.width(), self.height()
        if ext == ".svg":
            from PySide6.QtSvg import QSvgGenerator
            gen = QSvgGenerator()
            gen.setFileName(str(path))
            gen.setSize(QSize(w, h))
            gen.setViewBox(QRect(0, 0, w, h))
            gen.setTitle(self.title.text())
            gen.setDescription("Mesh Viewer plot")
            p = QPainter(gen)
            p.fillRect(QRect(0, 0, w, h), self.palette().color(QPalette.Window))
            self._paint_into(p)
            p.end()
            return path
        k = max(1, int(scale))
        img = QImage(w * k, h * k, QImage.Format_ARGB32)
        img.setDevicePixelRatio(k)
        img.fill(self.palette().color(QPalette.Window))
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        self._paint_into(p)
        p.end()
        if ext in (".jpg", ".jpeg"):
            img.convertToFormat(QImage.Format_RGB32).save(str(path), "JPG", 92)
        else:
            if ext != ".png":
                path = path.with_name(path.name + ".png")
            img.save(str(path), "PNG")
        return path
