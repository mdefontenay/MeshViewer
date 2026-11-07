"""NEW (v2.15): sidebar section "Results" — a solution field from the solver painted on
the boundaries (files that carry one: FUN3D's Tecplot boundary output, .dat).

    Results
      Field          [ yplus                ▾ ]
      Colour the boundaries                    (switch)
      ▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬
      0.02            0.81              1.6
      Min [ auto: 0.02 ]   Max [ auto: 1.6 ]
      max 1.6 · mean 0.7 on the visible boundaries          Values

One hue (light -> dark) for fields that keep one sign; blue -> grey -> red, centred on
zero, for fields that change sign (cp, u, v, w…). The range is the visible boundaries'
min to max unless typed. Remembered per file.
"""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPalette
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from .cfd_panel import _grid, _row
from .cfd_view import DIVERGING, SEQUENTIAL, field_values
from .widgets import MenuSelect, NumberField, Switch, ValuesButton

NAMES = {"yplus": "y+", "cp": "Pressure coefficient cp", "p": "Pressure p", "rho": "Density ρ",
         "mach": "Mach", "u": "Velocity u", "v": "Velocity v", "w": "Velocity w",
         "cf": "Skin friction cf", "cfx": "Skin friction cf x", "cfy": "Skin friction cf y",
         "cfz": "Skin friction cf z", "temperature": "Temperature", "vort": "Vorticity"}
SPEED = "__speed__"                                 # |u, v, w| when the file has u, v, w


def nice_num(v):
    if v is None or not np.isfinite(v):
        return "—"
    a = abs(v)
    return f"{v:.3g}" if a == 0 or 1e-3 <= a < 1e5 else f"{v:.2e}"


class ScaleBar(QWidget):
    """The colour scale with three numbers under it: min, middle, max."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.stops, self.lo, self.hi = SEQUENTIAL, 0.0, 1.0
        self.setFixedHeight(28)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set(self, stops, lo, hi):
        self.stops, self.lo, self.hi = stops, lo, hi
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(1, 1, self.width() - 2, 9)
        g = QLinearGradient(r.topLeft(), r.topRight())
        for i, c in enumerate(self.stops):
            g.setColorAt(i / (len(self.stops) - 1), QColor(c))
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawRoundedRect(r, 4, 4)
        f = p.font()
        f.setPixelSize(10)
        p.setFont(f)
        p.setPen(self.palette().color(QPalette.PlaceholderText))
        for pos, al in ((0.0, Qt.AlignLeft), (0.5, Qt.AlignHCenter), (1.0, Qt.AlignRight)):
            v = self.lo + pos * (self.hi - self.lo)
            x = r.left() + pos * r.width()
            box = QRectF(x - (0 if pos == 0 else 60 if pos == 0.5 else 120), 13, 120, 14)
            p.drawText(box, al | Qt.AlignVCenter, nice_num(v))
        p.end()


class ResultsPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 0, 2, 0)
        lay.setSpacing(6)
        g = _grid()
        self.field = MenuSelect()
        self.field.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.field.setToolTip("Solution field from the file, at the boundary nodes")
        self.field.currentIndexChanged.connect(self._field_changed)
        _row(g, 0, "Field", self.field, wide=True)
        lay.addLayout(g)
        r = QHBoxLayout()
        r.addWidget(QLabel("Colour the boundaries"))
        r.addStretch(1)
        self.colour_on = Switch()
        self.colour_on.setToolTip("Paint the visible boundaries with this field")
        self.colour_on.toggled.connect(self._update)
        r.addWidget(self.colour_on)
        lay.addLayout(r)
        self.bar = ScaleBar()
        lay.addWidget(self.bar)
        g = _grid()
        self.lo = NumberField()
        self.lo.setToolTip("Bottom of the colour scale. Empty = the smallest value")
        self.hi = NumberField()
        self.hi.setToolTip("Top of the colour scale. Empty = the largest value")
        for b in (self.lo, self.hi):
            b.valueChanged.connect(self._update)
        _row(g, 0, "Min", self.lo)
        _row(g, 1, "Max", self.hi)
        lay.addLayout(g)
        r = QHBoxLayout()
        self.stats = QLabel("")
        self.stats.setObjectName("InfoLine")
        self.stats.setWordWrap(True)
        r.addWidget(self.stats, 1)
        self.values = ValuesButton("Results", tip="Min, max and mean of each field")
        r.addWidget(self.values, 0, Qt.AlignTop)
        lay.addLayout(r)

    # ---- binding -------------------------------------------------------------------------
    @staticmethod
    def fields_of(model):
        names = []
        for part in model.parts.values():
            for k in list(part.point_data.keys()) + list(part.cell_data.keys()):
                if k not in names and not k.startswith("vtk") and k not in ("face_id",):
                    if np.asarray(part.point_data[k] if k in part.point_data
                                  else part.cell_data[k]).ndim == 1:
                        names.append(k)
        if {"u", "v", "w"} <= set(names):
            names.append(SPEED)
        return names

    def bind(self, scene):
        if self.scene is not None:
            self.scene.results.clear()
        self.scene = scene
        fields = self.fields_of(scene.model)
        st = getattr(scene, "results_settings", None) or {}
        self.field.blockSignals(True)
        self.field.clear()
        for f in fields:
            self.field.addItem(self._label(f), f)
        default = st.get("field") or ("yplus" if "yplus" in fields else
                                      fields[0] if fields else None)
        i = self.field.findData(default)
        self.field.setCurrentIndex(i if i >= 0 else 0)
        self.field.blockSignals(False)
        self.lo.setValue(st.get("lo"))
        self.hi.setValue(st.get("hi"))
        Switch.set_silently(self.colour_on, bool(st.get("on", False)))
        self._update(save=False)

    @staticmethod
    def has_results(model):
        return bool(ResultsPanel.fields_of(model))

    @staticmethod
    def _label(f):
        return "Speed |u, v, w|" if f == SPEED else NAMES.get(f.lower(), f)

    def settings(self):
        return {"field": self.field.currentData(), "lo": self.lo.value(), "hi": self.hi.value(),
                "on": self.colour_on.isChecked()}

    def model_changed(self):
        self._update(save=False)

    # ---- values ----------------------------------------------------------------------------
    def _values(self, field, visible_only=True):
        """All values of a field on the (visible) boundaries."""
        sc = self.scene
        out = []
        for n in sc.names:
            if visible_only and not sc.visible.get(n):
                continue
            part = sc.model.parts[n]
            if field == SPEED:
                u, _ = field_values(part, "u")
                v, _ = field_values(part, "v")
                w, _ = field_values(part, "w")
                if u is not None and v is not None and w is not None:
                    out.append(np.sqrt(u * u + v * v + w * w))
                continue
            vals, _ = field_values(part, field)
            if vals is not None:
                out.append(vals)
        return np.concatenate(out) if out else np.zeros(0)

    def _ensure_speed(self):
        """|u, v, w| stored on the parts the first time it is asked for."""
        for part in self.scene.model.parts.values():
            if SPEED not in part.point_data:
                u, wu = field_values(part, "u")
                v, _ = field_values(part, "v")
                w, _ = field_values(part, "w")
                if u is not None and v is not None and w is not None and wu == "point":
                    part.point_data[SPEED] = np.sqrt(u * u + v * v + w * w)

    # ---- handlers ----------------------------------------------------------------------------
    def _field_changed(self, *_):
        self.lo.setValue(None)                       # a new field: its own range
        self.hi.setValue(None)
        self._update()

    def _update(self, *_, save=True):
        sc = self.scene
        if sc is None:
            return
        f = self.field.currentData()
        if save:
            sc.results_settings = self.settings()
        if f is None:
            self.stats.setText("No solution fields in this file.")
            sc.results.clear()
            return
        if f == SPEED:
            self._ensure_speed()
        vals = self._values(f)
        vals = vals[np.isfinite(vals)]
        if not len(vals):
            self.stats.setText("No visible boundary has this field.")
            sc.results.clear()
            return
        a_lo, a_hi = float(vals.min()), float(vals.max())
        self.lo.setPlaceholderText(f"auto: {nice_num(a_lo)}")
        self.hi.setPlaceholderText(f"auto: {nice_num(a_hi)}")
        lo = self.lo.value() if self.lo.value() is not None else a_lo
        hi = self.hi.value() if self.hi.value() is not None else a_hi
        signed = a_lo < 0 < a_hi
        if signed and self.lo.value() is None and self.hi.value() is None:
            m = max(abs(a_lo), abs(a_hi))            # centred on zero
            lo, hi = -m, m
        stops = DIVERGING if signed else SEQUENTIAL
        if hi <= lo:
            hi = lo + (abs(lo) or 1.0) * 1e-6
        self.bar.set(stops, lo, hi)
        self.stats.setText(f"max {nice_num(a_hi)} · mean {nice_num(float(vals.mean()))} · "
                           f"min {nice_num(a_lo)} on the visible boundaries (node values)")
        if self.colour_on.isChecked():
            sc.results.show_field(f, lo, hi, stops)
        else:
            sc.results.clear()
        rows = []
        for k in self.fields_of(sc.model):
            v = self._values(k) if k != SPEED or SPEED in next(iter(
                sc.model.parts.values())).point_data else np.zeros(0)
            v = v[np.isfinite(v)] if len(v) else v
            if len(v):
                rows += [(self._label(k), None, None), ("max", nice_num(float(v.max())), ""),
                         ("mean", nice_num(float(v.mean())), ""),
                         ("min", nice_num(float(v.min())), "")]
        self.values.set_rows(rows)
