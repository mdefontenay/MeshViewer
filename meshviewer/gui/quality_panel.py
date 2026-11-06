"""NEW (v2.9): sidebar section "Cell quality" (mesh files only).

    Measure            [ Skewness              ▾ ]
    ▁▂▅█▇▅▃▂▁ ▏         histogram, coloured like the 3D view; click / drag to
    0        mean 0.14   0.97                     set the threshold
    Bad if  >  [ 0.9 ]
    132 bad cells (0.4 %)                          Zoom
    Show bad cells                                 (switch)
    Colour by quality                              (switch)
    ✓ No inverted cells
    2,750 volume cells checked

Numbers are computed in the background (the volume cells are read the first
time), once per measure, then kept.
"""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPalette, QPen
from PySide6.QtWidgets import (
    QAbstractSpinBox, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from .. import quality as Q
from .jobs import run_job
from .style import accent
from .widgets import MenuSelect, NoWheelSpinBox, Switch

DECIMALS = {"skew": 3, "aspect": 1, "jacobian": 3, "size": 9}
RANGES = {"skew": (0, 1), "aspect": (1, 1e12), "jacobian": (-1, 1), "size": (-1e12, 1e12)}


def _num(v):
    """Short number for labels: 0.137, 12.4, 3.2e-07."""
    if v is None or not np.isfinite(v):
        return "—"
    a = abs(v)
    if a == 0:
        return "0"
    if a >= 1e5 or a < 1e-3:
        return f"{v:.2g}"
    return f"{v:.3g}"


class _Threshold(NoWheelSpinBox):
    def textFromValue(self, v):
        t = f"{v:.{self.decimals()}f}".rstrip("0").rstrip(".")
        return "0" if t in ("", "-0") else t


class Histogram(QWidget):
    """Bars (square-root height, so a few bad cells still show), the bad side
    shaded, the threshold as a line. Click or drag to move the threshold."""
    threshold_picked = Signal(float)          # in display units (log10 for log measures)

    HEIGHT, LABELS = 58, 14

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(self.HEIGHT + self.LABELS)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)
        self.counts = self.edges = None
        self.colors, self.threshold, self.bad_side = [], None, ">"
        self.labels = ("", "", "")

    def set_data(self, counts, edges, colors, threshold, bad_side, labels):
        self.counts, self.edges, self.colors = counts, edges, colors
        self.threshold, self.bad_side, self.labels = threshold, bad_side, labels
        self.update()

    def clear(self):
        self.counts = None
        self.update()

    def _x(self, v):
        lo, hi = self.edges[0], self.edges[-1]
        return (v - lo) / (hi - lo) * (self.width() - 2) + 1

    def _value(self, x):
        lo, hi = self.edges[0], self.edges[-1]
        return lo + (x - 1) / max(self.width() - 2, 1) * (hi - lo)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pal = self.palette()
        base = QColor(pal.color(QPalette.WindowText))
        frame = QColor(base)
        frame.setAlphaF(0.06)
        p.setPen(Qt.NoPen)
        p.setBrush(frame)
        p.drawRoundedRect(QRectF(0, 0, self.width(), self.HEIGHT), 5, 5)
        if self.counts is None or not len(self.counts):
            return
        n = len(self.counts)
        w = (self.width() - 2) / n
        top = max(np.sqrt(self.counts.max()), 1)
        for i, c in enumerate(self.counts):
            if not c:
                continue
            h = max(2.0, np.sqrt(c) / top * (self.HEIGHT - 6))
            p.setBrush(QColor(*self.colors[i]))
            p.drawRect(QRectF(1 + i * w + 0.5, self.HEIGHT - 2 - h, max(w - 1, 1), h))
        if self.threshold is not None and np.isfinite(self.threshold):
            x = float(np.clip(self._x(self.threshold), 0, self.width()))
            shade = QColor(255, 69, 58, 34)
            p.setBrush(shade)
            if self.bad_side == ">":
                p.drawRect(QRectF(x, 0, self.width() - x, self.HEIGHT))
            else:
                p.drawRect(QRectF(0, 0, x, self.HEIGHT))
            p.setPen(QPen(QColor(accent()), 1.5))
            p.drawLine(QPointF(x, 0), QPointF(x, self.HEIGHT))
        p.setPen(pal.color(QPalette.PlaceholderText))
        f = p.font()
        f.setPixelSize(10)
        p.setFont(f)
        r = QRectF(0, self.HEIGHT + 1, self.width(), self.LABELS)
        for text, align in zip(self.labels, (Qt.AlignLeft, Qt.AlignHCenter, Qt.AlignRight)):
            p.drawText(r, align | Qt.AlignVCenter, text)

    def mousePressEvent(self, e):
        if self.edges is not None and e.button() == Qt.LeftButton:
            self.threshold_picked.emit(float(self._value(e.position().x())))

    def mouseMoveEvent(self, e):
        if self.edges is None:
            return
        if e.buttons() & Qt.LeftButton:
            self.threshold_picked.emit(float(self._value(e.position().x())))
        if self.counts is not None:
            i = int(np.clip((e.position().x() - 1) / max(self.width() - 2, 1) * len(self.counts),
                            0, len(self.counts) - 1))
            self.setToolTip(f"{self.counts[i]:,} cells")


class QualityPanel(QWidget):
    wants_section = Signal()                   # colour by quality: show the cut
    computed = Signal()                        # new numbers (the volume may now be read)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = None
        self._values = {}                      # measure -> values per cell
        self._job = None
        self._pending = None
        self._active = False
        self._stats = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 0, 2, 0)
        lay.setSpacing(6)

        row = QHBoxLayout()
        row.addWidget(QLabel("Measure"))
        self.metric = MenuSelect()
        for key, m in Q.METRICS.items():
            self.metric.addItem(m["label"], key)
        self.metric.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.metric.currentIndexChanged.connect(self._metric_changed)
        row.addWidget(self.metric, 1)
        lay.addLayout(row)

        self.hist = Histogram()
        self.hist.threshold_picked.connect(self._picked)
        lay.addWidget(self.hist)

        row = QHBoxLayout()
        self.bad_label = QLabel("Bad if >")
        row.addWidget(self.bad_label)
        self.threshold = _Threshold()
        self.threshold.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.threshold.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.threshold.setFixedWidth(80)
        self.threshold.valueChanged.connect(self._threshold_changed)
        row.addWidget(self.threshold)
        row.addStretch(1)
        lay.addLayout(row)

        row = QHBoxLayout()                         # "1,250 bad cells (45 %)     Zoom"
        self.count = QLabel("")
        self.count.setObjectName("ValueLabel")
        row.addWidget(self.count, 1)
        self.zoom = QPushButton("Zoom")
        self.zoom.setObjectName("LinkButton")
        self.zoom.setFlat(True)
        self.zoom.setCursor(Qt.PointingHandCursor)
        self.zoom.setToolTip("Zoom onto the bad cells")
        self.zoom.clicked.connect(self._zoom)
        row.addWidget(self.zoom)
        lay.addLayout(row)

        self.switches = {}
        for key, text, tip in (
                ("bad", "Show bad cells", "Bad cells in red; the model turns see-through"),
                ("color", "Colour by quality", "Volume meshes: colours the section cut.\n"
                                               "Surface meshes: colours the faces.")):
            r = QHBoxLayout()
            lab = QLabel(text)
            lab.setToolTip(tip)
            r.addWidget(lab)
            r.addStretch(1)
            sw = Switch()
            sw.setToolTip(tip)
            sw.toggled.connect(lambda on, k=key: self._switched(k, on))
            r.addWidget(sw)
            lay.addLayout(r)
            self.switches[key] = sw

        self.inverted = QLabel("")
        self.inverted.setObjectName("InfoLine")
        self.inverted.setWordWrap(True)
        lay.addWidget(self.inverted)
        self.status = QLabel("")
        self.status.setObjectName("InfoLine")
        self.status.setWordWrap(True)
        lay.addWidget(self.status)

        self._redraw_later = QTimer(self, singleShot=True, interval=250)
        self._redraw_later.timeout.connect(self._update_view)
        self._metric_changed()

    # ---- binding -----------------------------------------------------------------
    def bind(self, scene):
        if self.scene is not None:
            self.scene.quality.clear()
        self.scene = scene
        self._values = {}
        self._stats = None
        for sw in self.switches.values():
            Switch.set_silently(sw, False)
        self.hist.clear()
        self.count.setText("")
        self.inverted.setText("")
        self.status.setText("Open this section to check the cells.")
        self._metric_changed()
        if self._active:
            self._compute()

    def activate(self, on):
        """Section opened: compute what's missing (the first time only)."""
        self._active = bool(on)
        if on and self.scene is not None:
            self._compute()

    @property
    def key(self):
        return self.metric.currentData()

    # ---- computing ------------------------------------------------------------------
    def _compute(self):
        key = self.key
        if key in self._values:
            self._refresh()
            return
        if self._job is not None:                    # busy: do this one next
            self._pending = key
            return
        qv = self.scene.quality
        first = not self._values
        self.status.setText("Reading volume cells…" if first and qv.is_volume
                            else f"Computing {self.metric.currentText().lower()}…")

        def work():
            ds = qv.dataset()
            out = {key: Q.compute(ds, key)}
            if "size" not in self._values and key != "size":
                out["size"] = Q.compute(ds, "size")        # for the inverted-cell line
            return out
        self._job = run_job(work, self._computed, self._failed)

    def _computed(self, values):
        self._job = None
        self._values.update(values)
        self._refresh()
        self.computed.emit()
        if self._pending and self._pending not in self._values:
            self._pending = None
            self._compute()

    def _failed(self, exc):
        self._job = None
        self.status.setText(f"Could not check the cells: {exc}")

    # ---- UI --------------------------------------------------------------------------
    def _metric_changed(self, *_):
        key = self.key
        m = Q.METRICS[key]
        surface = self.scene is not None and not self.scene.quality.is_volume
        self.metric.setToolTip(m["tip"])
        self.bad_label.setText({">": "Bad if >", "<": "Bad if <", "<=": "Bad if ≤"}[m["bad"]])
        self.threshold.blockSignals(True)
        self.threshold.setDecimals(DECIMALS[key])
        self.threshold.setRange(*RANGES[key])
        self.threshold.setSingleStep({"skew": 0.05, "aspect": 10, "jacobian": 0.05}.get(key, 0))
        self.threshold.setValue(m["default"])
        self.threshold.blockSignals(False)
        self.threshold.setToolTip(f"{Q.label(key, surface)}: {m['tip']}")
        if self.scene is not None and self._active:
            self._compute()

    def _threshold_changed(self, *_):
        if self.key in self._values:
            self._refresh(redraw_now=False)

    def _picked(self, display_value):
        v = 10 ** display_value if Q.METRICS[self.key]["log"] else display_value
        self.threshold.setValue(v)

    def _refresh(self, redraw_now=True):
        key, values = self.key, self._values.get(self.key)
        if values is None or self.scene is None:
            return
        thr = self.threshold.value()
        s = Q.summarize(values, key, thr)
        self._stats = s
        m = Q.METRICS[key]
        if "hist" in s:
            disp_thr = (np.log10(thr) if thr > 0 else -np.inf) if m["log"] else thr
            labels = (_num(s["min"]), f"mean {_num(s['mean'])}", _num(s["max"]))
            self.hist.set_data(s["hist"], s["edges"], Q.bar_colors(s["edges"], key, thr),
                               disp_thr, ">" if m["bad"] == ">" else "<", labels)
        pct = 100 * s["n_bad"] / max(s["n"], 1)
        self.count.setText(f"{s['n_bad']:,} bad cells ({pct:.2g} %)" if s["n_bad"]
                           else "No bad cells")
        self.zoom.setEnabled(s["n_bad"] > 0)
        size = self._values.get("size")
        qv = self.scene.quality
        if size is not None and qv.is_volume:
            n_inv = int(np.count_nonzero(size <= 0))
            self.inverted.setText(f"⚠ {n_inv:,} inverted cells (volume ≤ 0)" if n_inv
                                  else "✓ No inverted cells")
            self.inverted.setStyleSheet("color: #ff453a;" if n_inv else "")
        what = "volume cells" if qv.is_volume else "surface faces (no volume cells in the file)"
        self.status.setText(f"{s['n']:,} {what} checked")
        if redraw_now:
            self._update_view()
        else:
            self._redraw_later.start()               # dragging: redraw when it settles

    def _bad_ids(self):
        key, values = self.key, self._values[self.key]
        bad = np.flatnonzero(Q.is_bad(values, key, self.threshold.value()))
        order = np.argsort(values[bad])                    # worst first
        if Q.METRICS[key]["bad"] == ">":
            order = order[::-1]
        return bad[order]

    def _update_view(self):
        if self.scene is None or self.key not in self._values:
            return
        qv = self.scene.quality
        qv.show_bad(self._bad_ids() if self.switches["bad"].isChecked() else None)
        if self.switches["color"].isChecked() and self._stats and "edges" in self._stats:
            e = self._stats["edges"]
            qv.set_colors(Q.colors(self._values[self.key], self.key, self.threshold.value(),
                                   e[0], e[-1]))
        elif qv.rgb is not None:
            qv.set_colors(None)

    def _switched(self, key, on):
        if self.scene is None:
            return
        if key == "color" and on and self.scene.quality.is_volume:
            self.wants_section.emit()                    # the colours show on the cut
        if self.key in self._values:
            self._update_view()
        else:
            self._compute()

    def _zoom(self):
        if self.scene is None or self.key not in self._values:
            return
        b = self.scene.quality.cell_bounds(self._bad_ids())
        if b is not None:
            self.scene.p.reset_camera(bounds=b)
            self.scene.p.render()
