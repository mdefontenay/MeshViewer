"""The tab of a probe under the 3D view (cases with several time steps): its field over
time, drawn like a plot (gui/pages/plots.py: same frame, ticks, hover, wheel zoom,
double-click fits), with the step shown as a vertical line.

    Probe 1                                          ● mean  ● min  ● max
    Point · volume cell 1,204 · Pressure p (m²/s²) over time
    ┌──────────────────────────────────────────────┐
    │      ╱╲    │      ╱╲                           │   the line: the step shown
    └──────────────────────────────────────────────┘

The step shown is a dashed line with its time on a tag ("t = 0.27") and a dot on the
curve. A click or a drag on the plot picks the time under the cursor (`time_picked`):
the 3D view and the playback bar go to that step; playing moves the line (`set_playhead`).
"""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPen

from meshviewer.gui.pages.plots import CrossSectionPlot, PlotPage


class ProbePlot(CrossSectionPlot):
    time_picked = Signal(float)          # a click / drag: the time under the cursor
    EMPTY = "Nothing probed yet: pick a target in the probe's card"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.playhead = None             # the time shown (None: none)

    def set_playhead(self, t):
        self.playhead = t
        self.update()

    def paintEvent(self, e):
        """The plot, then the step shown: a dashed line, its time on a tag at the top, a
        dot where it meets the curve."""
        super().paintEvent(e)
        if self._r is None or self.playhead is None:
            return
        from PySide6.QtGui import QPainter
        from meshviewer.core.units import nice_num
        from meshviewer.gui.style import accent
        t = float(self.playhead)
        x = self._px(t, self._data(self._r[1][0], "y")).x()
        if not np.isfinite(x) or not self.PAD_L <= x <= self.width() - self.PAD_R:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        muted = self.palette().color(self.palette().ColorRole.PlaceholderText)
        p.setPen(QPen(muted, 1, Qt.DashLine))
        p.drawLine(QPointF(x, self.PAD_T + 18), QPointF(x, self.height() - self.PAD_B))
        text = f"t = {nice_num(t)}"
        fm = p.fontMetrics()
        w = fm.horizontalAdvance(text) + 10
        box = QRectF(min(max(x - w / 2, self.PAD_L), self.width() - self.PAD_R - w),
                     self.PAD_T, w, 16)
        p.setPen(Qt.NoPen)
        p.setBrush(muted)
        p.drawRoundedRect(box, 4, 4)
        p.setPen(self.palette().color(self.palette().ColorRole.Window))
        p.drawText(box, Qt.AlignCenter, text)
        if self.curves:                                # where it meets the (first) curve
            cx, cy = np.asarray(self.curves[0][0], float), np.asarray(self.curves[0][1], float)
            ok = np.isfinite(cx) & np.isfinite(cy)
            if ok.sum() >= 1:
                y = float(np.interp(t, cx[ok], cy[ok]))
                q = self._px(t, y)
                if np.isfinite(q.y()):
                    p.setPen(QPen(QColor("white"), 1.5))
                    p.setBrush(QColor(accent()))
                    p.drawEllipse(q, 4.5, 4.5)
        p.end()

    def _pick(self, e):
        if self._r is not None:
            t, _ = self._at(e.position().x(), e.position().y())
            self.time_picked.emit(float(self._data(t, "x")))

    def mousePressEvent(self, e):                # a click / drag picks a time (no pan)
        if e.button() == Qt.LeftButton:
            self._pick(e)

    def mouseReleaseEvent(self, e):
        pass

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.LeftButton:
            self._pick(e)
            return
        super().mouseMoveEvent(e)


class ProbePage(PlotPage):
    PLOT = ProbePlot

    def __init__(self, parent=None):
        super().__init__(parent)
        self.view = {}
        self.plot.ranges_changed.disconnect()
        self.plot.ranges_changed.connect(self._zoomed)
        self._last = None

    def show_probe(self, p, times, series, where, y_title, conv):
        """p: the probe; series: {"mean", "min", "max"} (file units) or None; where: what
        it probes; y_title: the field and its unit; conv: file -> shown values."""
        if self.ident != ("probe", p["id"]):
            self.view = {}
        self.ident = ("probe", p["id"])
        self.title.setText(p["name"])
        self.subtitle.setText(f"{where} · {y_title} over time")
        curves = []
        if series is not None:
            t = np.asarray(times, dtype=float)
            spread = (p.get("target") or {}).get("kind") in ("line", "area")
            from meshviewer.gui.style import accent
            main = QColor(accent())
            curves.append((t, np.asarray(conv(series["mean"]), dtype=float), main,
                           "mean" if spread else p["name"]))
            if spread:
                for k, f in (("min", 0.45), ("max", 0.45)):
                    c = QColor(main)
                    c.setAlphaF(f)
                    curves.append((t, np.asarray(conv(series[k]), dtype=float), c, k))
        self._last = (curves, y_title)
        self.plot.set_data(curves, [], "t", y_title, self.view)
        self.legend.set_items([(c[3], c[2]) for c in curves] if len(curves) > 1 else [])

    def set_playhead(self, t):
        self.plot.set_playhead(t)

    def _zoomed(self, rng):
        self.view = {} if rng[0] is None else dict(zip(("x_min", "x_max", "y_min", "y_max"),
                                                      rng))
        if self._last is not None:
            self.plot.set_data(self._last[0], [], "t", self._last[1], self.view)
