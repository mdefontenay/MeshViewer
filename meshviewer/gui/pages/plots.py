"""The tab of a measurement under the 3D view (F13): its plot, drawn like the CFD mode
plots (inflation.py: same grid, ticks, axis titles, hover).

    Root                                             ● wing  ● tip  ○ reference
    Cross section · plane Y = 0.35 m · cp along x/c
    ┌───────────────────────────────────────────────────────────────────────┐
    │   -cp up (flipped) … one line per cut loop, in its boundary's colour  │
    └───────────────────────────────────────────────────────────────────────┘

One page for every measurement: the window shows the one whose tab is chosen
(show(m, r, …)). Hover a line for the point under the cursor.
"""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPalette, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QToolTip, QVBoxLayout, QWidget

from meshviewer.core import plots
from meshviewer.core.units import nice_num, nice_step
from meshviewer.gui.pages.inflation import _Plot


class CrossSectionPlot(_Plot):
    PAD_L, PAD_R, PAD_T, PAD_B = 70, 24, 14, 40
    EMPTY = "The plane misses the visible boundaries"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.curves, self.ref, self.flip = [], [], False
        self.titles = ("", "")
        self._r = None

    def set_data(self, curves, ref, flip, x_title, y_title):
        """curves: [(x (n,), y (n,), QColor, part)], ref: [(x, y)] (shown units)."""
        self.curves, self.ref, self.flip = curves, ref, flip
        self.titles = (x_title, y_title)
        xs = [c[0] for c in curves] + ([np.array([p[0] for p in ref])] if ref else [])
        ys = [c[1] for c in curves] + ([np.array([p[1] for p in ref])] if ref else [])
        if not curves:
            self._r = None
        else:
            x = np.concatenate(xs)
            y = np.concatenate(ys)
            x0, x1 = float(np.nanmin(x)), float(np.nanmax(x))
            y0, y1 = float(np.nanmin(y)), float(np.nanmax(y))
            dx, dy = x1 - x0, y1 - y0
            if not dx > 1e-9 * max(1.0, abs(x0), abs(x1)):     # one x: a little room
                dx = 0.1 * abs(x0) or 1.0
            if not dy > 1e-9 * max(1.0, abs(y0), abs(y1)):     # constant (cp on a ring)
                dy = 0.1 * abs(y0) or 1.0
                y0, y1 = y0 - dy / 2, y1 + dy / 2
            step = nice_step(dy * 1.1, 5)
            self._r = ((x0 - 0.02 * dx, x1 + 0.02 * dx),
                       (np.floor((y0 - 0.04 * dy) / step) * step,
                        np.ceil((y1 + 0.04 * dy) / step) * step))
        self.hover = None
        self.update()

    def _ranges(self):
        return self._r

    def _px(self, x, y):
        (x0, x1), (y0, y1) = self._r
        if self.flip:                               # negative up: the y axis upside down
            y = y0 + y1 - y
        return super()._px(x, y)

    def _frame(self, p, y_title, x_title, y_label, x_ticks):
        """As the CFD plots, but the x ticks stay at the bottom when the y axis is flipped."""
        (x0, x1), (y0, y1) = self._r
        left, right = self.PAD_L, self.width() - self.PAD_R
        top, base = self.PAD_T, self.height() - self.PAD_B
        step = nice_step(y1 - y0, 5)
        gy = y0
        for _ in range(60):                         # (never more than a few)
            if gy > y1 + 1e-9 * step:
                break
            y = self._px(x0, gy).y()
            p.setPen(QPen(self._grid, 1))
            p.drawLine(QPointF(left, y), QPointF(right, y))
            p.setPen(self._muted)
            p.drawText(QRectF(4, y - 7, left - 14, 14), Qt.AlignRight | Qt.AlignVCenter,
                       y_label(0.0 if abs(gy) < 1e-9 * step else gy))
            gy += step
        for x, text in x_ticks:
            q = self._px(x, y0).x()
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

    def paintEvent(self, _):
        p = self._begin()
        if self._r is None:
            return self._empty(p)
        (x0, x1), (y0, y1) = self._r
        step = nice_step(x1 - x0, 8)
        t = np.ceil(x0 / step) * step
        ticks = []
        for _ in range(60):
            if t > x1 + 1e-9 * step:
                break
            ticks.append((t, nice_num(0.0 if abs(t) < 1e-9 * step else t)))
            t += step
        self._frame(p, self.titles[1], self.titles[0], nice_num, ticks)
        if self.flip:                               # say so, top left
            p.setPen(self._muted)
            p.drawText(QRectF(self.PAD_L + 6, self.PAD_T, 200, 14), Qt.AlignLeft,
                       "negative up")
        for x, y, c, _part in self.curves:
            ok = np.isfinite(x) & np.isfinite(y)
            if ok.sum() < 2:
                continue
            path = QPainterPath()
            first = True
            for a, b, good in zip(x, y, ok):
                if not good:
                    first = True
                    continue
                q = self._px(a, b)
                path.moveTo(q) if first else path.lineTo(q)
                first = False
            p.setPen(QPen(c, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)
        if self.ref:
            p.setPen(QPen(self._text, 1.4))
            p.setBrush(Qt.NoBrush)
            for a, b in self.ref:
                p.drawEllipse(self._px(a, b), 3.2, 3.2)
        if self.hover is not None:
            a, b, c, _part = self.hover
            q = self._px(a, b)
            self._hover_at(p, q.x(), q, c)

    def _nearest(self, pos):
        best = None
        for x, y, c, part in self.curves:
            for a, b in zip(x, y):
                if not (np.isfinite(a) and np.isfinite(b)):
                    continue
                q = self._px(a, b)
                d = (q.x() - pos.x()) ** 2 + (q.y() - pos.y()) ** 2
                if best is None or d < best[0]:
                    best = (d, (a, b, c, part))
        return best[1] if best and best[0] < 30 ** 2 else None

    def mouseMoveEvent(self, e):
        if self._r is None:
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


class PlotPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PlotPage")
        self.ident = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 18, 24, 18)
        lay.setSpacing(4)
        top = QHBoxLayout()
        self.title = QLabel("")
        self.title.setStyleSheet("font-size: 17px; font-weight: 600;")
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
        lay.addWidget(self.plot, 1)

    def show(self, m, r, colors, scale, unit, value_unit=None):
        """m: the measurement, r: its compute() result, colors: part -> hex,
        (scale, unit): file lengths -> shown; value_unit: (convert, label) of a field's
        values (Results ▸ Values in / Shown in), or None."""
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
                     + ", ".join(nice_num(v) for v in n) + ")")
        self.subtitle.setText(f"{plots.KINDS[m['kind']]['title']} · plane {where} · "
                              f"{y_title} along {x_title}")
        curves = [(c["x"] * xs, np.asarray(conv(c["y"]), dtype=float),
                   QColor(colors.get(c["part"], "#8e8e93")), c["part"]) for c in r["curves"]]
        ref = [tuple(p) for p in (m.get("ref") or {}).get("points", [])]
        self.plot.set_data(curves, ref, r["flip"], x_title, y_title)
        names = []
        for c in r["curves"]:
            if c["part"] not in [n for n, _ in names]:
                names.append((c["part"], QColor(colors.get(c["part"], "#8e8e93"))))
        if ref:
            names.append((m["ref"]["name"], None))
        self.legend.set_items(names)
