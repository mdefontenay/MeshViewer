"""Sidebar section "Results" — a solution field from the solver painted on
the boundaries (files that carry one: FUN3D's Tecplot boundary output, .dat).

    Results
      Field          [ yplus                ▾ ]
      Colours        [ ▬▬▬▬ (the colour map)  ▾ ]
      Show           [ Value | Gradient ]
      Values in      [ —  (as in the file) ▾ ]    fields with a unit (p, ρ, u, T…) only
      Shown in       [ kPa ▾ ]
      Colour the boundaries                    (switch)
      ▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬
      0.02            0.81              1.6
      Min [ auto: 0.02 ] kPa
      Max [ auto: 1.6 ]  kPa

Gradient (F15): |∇f| along the surface, per unit length — large at shocks, leading
edges, separation lines.

The colour map is picked by its colours (rainbow by default). The range is the visible
boundaries' min to max unless typed, and follows when boundaries are shown or hidden.
Remembered per file.
"""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QAction, QActionGroup, QColor, QLinearGradient, QPainter, QPalette
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from meshviewer.gui.forms import _grid, _row
from meshviewer.core.fields import (COLORMAPS, DEFAULT_MAP, SEQUENTIAL, SPEED, field_values,
                                    gradient_magnitude, solution_fields)
from meshviewer.gui.widgets import Capsule, GradientSelect, MenuSelect, NumberField, Switch
from meshviewer.core.units import (NO_UNIT, QUANTITIES, convert_field, field_quantity,
                                   field_scale, nice_num)

GRAD = "__grad__"                    # point array: |∇ field| (kept on the parts)

NAMES = {"yplus": "y+", "cp": "Pressure coefficient cp", "p": "Pressure p", "rho": "Density ρ",
         "mach": "Mach", "u": "Velocity u", "v": "Velocity v", "w": "Velocity w",
         "cf": "Skin friction cf", "cfx": "Skin friction cf x", "cfy": "Skin friction cf y",
         "cfz": "Skin friction cf z", "temperature": "Temperature", "vort": "Vorticity"}


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
        p.drawRoundedRect(r, 4, 4)         # (the menu draws its bars with paint_gradient)
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
    units_changed = Signal()                      # a field's units: the plots follow

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
        self.cmap = GradientSelect()
        self.cmap.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        for key, stops in COLORMAPS.items():
            self.cmap.addItem(stops, key)
        self.cmap.setToolTip("Colour map")
        self.cmap.currentIndexChanged.connect(self._update)
        _row(g, 1, "Colours", self.cmap, wide=True)
        grp = QActionGroup(self)
        grp.setExclusive(True)
        self.show_acts = {}
        for key, text, tip in (("value", "Value", "The field itself"),
                               ("gradient", "Gradient",
                                "How fast it changes along the surface, |∇f| per unit length:\n"
                                "large at shocks, leading edges, separation lines")):
            a = QAction(text, self)
            a.setCheckable(True)
            a.setToolTip(tip)
            grp.addAction(a)
            a.triggered.connect(self._field_changed)     # its own range
            self.show_acts[key] = a
        self.show_acts["value"].setChecked(True)
        show = Capsule(list(self.show_acts.values()), name="Segmented")
        g.addWidget(QLabel("Show"), 2, 0)
        g.addWidget(show, 2, 1, 1, 3, Qt.AlignLeft)
        # units of fields that have one (p, ρ, u, T…): what the file's numbers are in,
        # and what to show them in (cp, Mach, y+: none, the rows hide)
        self.file_unit = MenuSelect()
        self.file_unit.setToolTip("The unit of the numbers in the file\n"
                                  "(— : as they are, e.g. non-dimensional)")
        self.shown_unit = MenuSelect()
        self.shown_unit.setToolTip("The unit the scale, Min / Max and the plots use")
        for m in (self.file_unit, self.shown_unit):
            m.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            m.currentIndexChanged.connect(self._unit_changed)
        self._unit_rows = [_row(g, 3, "Values in", self.file_unit, wide=True)[0],
                           _row(g, 4, "Shown in", self.shown_unit, wide=True)[0]]
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
        _, self.lo_unit = _row(g, 0, "Min", self.lo, unit=" ")
        _, self.hi_unit = _row(g, 1, "Max", self.hi, unit=" ")
        lay.addLayout(g)
        self.stats = QLabel("")                        # only when there is nothing to show
        self.stats.setObjectName("InfoLine")
        self.stats.setWordWrap(True)
        self.stats.setVisible(False)
        lay.addWidget(self.stats)
        self._units = {}                               # field -> [file unit, shown unit]
    # ---- binding -------------------------------------------------------------------------
    @staticmethod
    def fields_of(model):
        return solution_fields(model.parts)

    def bind(self, scene):
        if self.scene is not None:
            self.scene.results.clear()
            if self.model_changed in self.scene.visibility_listeners:
                self.scene.visibility_listeners.remove(self.model_changed)
        self.scene = scene
        scene.visibility_listeners.append(self.model_changed)   # auto range: shown boundaries
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
        self.cmap.blockSignals(True)
        k = self.cmap.findData(st.get("cmap") or DEFAULT_MAP)
        self.cmap.setCurrentIndex(k if k >= 0 else 0)
        self.cmap.blockSignals(False)
        Switch.set_silently(self.colour_on, bool(st.get("on", False)))
        self.show_acts["gradient" if st.get("show") == "gradient" else "value"].setChecked(True)
        self._units = {k: list(v) for k, v in (st.get("units") or {}).items()
                       if isinstance(v, (list, tuple)) and len(v) == 2}
        self._sync_units()
        self._update(save=False)

    @staticmethod
    def has_results(model):
        return bool(ResultsPanel.fields_of(model))

    @staticmethod
    def _label(f):
        return "Speed |u, v, w|" if f == SPEED else NAMES.get(f.lower(), f)

    def settings(self):
        return {"field": self.field.currentData(), "lo": self.lo.value(), "hi": self.hi.value(),
                "on": self.colour_on.isChecked(), "cmap": self.cmap.currentData(),
                "show": self.shown, "units": {k: list(v) for k, v in self._units.items()}}

    # ---- units ---------------------------------------------------------------------------
    def unit_of(self, field):
        """(quantity, file unit, shown unit) of a field; quantity None = no unit."""
        q = field_quantity(field)
        if q is None:
            return None, NO_UNIT, NO_UNIT
        fu, su = self._units.get(field, [NO_UNIT, NO_UNIT])
        table = QUANTITIES[q]
        su = su if su in table else next(iter(table))
        return q, (fu if fu in table else NO_UNIT), su

    def shown_values(self, field, vals):
        """Field values in the unit shown (unchanged when the file's has none)."""
        q, fu, su = self.unit_of(field)
        return vals if q is None or not fu else convert_field(vals, q, fu, su)

    def unit_label(self, field):
        q, fu, su = self.unit_of(field)
        return su if q is not None and fu else ""

    def _sync_units(self):
        f = self.field.currentData()
        q, fu, su = self.unit_of(f)
        for lab, m in zip(self._unit_rows, (self.file_unit, self.shown_unit)):
            lab.setVisible(q is not None)
            m.setVisible(q is not None)
        if q is None:
            return
        for m in (self.file_unit, self.shown_unit):
            m.blockSignals(True)
            m.clear()
        self.file_unit.addItem("—  (as in the file)", NO_UNIT)
        for k in QUANTITIES[q]:
            self.file_unit.addItem(k, k)
            self.shown_unit.addItem(k, k)
        self.file_unit.setCurrentIndex(max(0, self.file_unit.findData(fu)))
        self.shown_unit.setCurrentIndex(max(0, self.shown_unit.findData(su)))
        self.shown_unit.setEnabled(bool(fu))
        for m in (self.file_unit, self.shown_unit):
            m.blockSignals(False)

    def _unit_changed(self, *_):
        f = self.field.currentData()
        if f is None or field_quantity(f) is None:
            return
        old = self.unit_of(f)
        self._units[f] = [self.file_unit.currentData(), self.shown_unit.currentData()]
        self.shown_unit.setEnabled(bool(self.file_unit.currentData()))
        new = self.unit_of(f)
        if new != old:                                  # typed Min / Max: same quantity
            for box in (self.lo, self.hi):
                v = box.value()
                if v is not None and old[1] and new[1]:
                    box.setValue(convert_field(convert_field(v, old[0], old[2], old[1]),
                                               new[0], new[1], new[2]))
                elif v is not None:
                    box.setValue(None)
        self._update()
        self.units_changed.emit()

    @property
    def shown(self):
        return "gradient" if self.show_acts["gradient"].isChecked() else "value"

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

    def _ensure_gradient(self, field):
        """|∇ field| stored on the parts (point array GRAD + field) the first time."""
        key = GRAD + field
        for part in self.scene.model.parts.values():
            if key in part.point_data or not part.GetNumberOfPolys():
                continue
            vals, where = field_values(part, field)
            if vals is None:
                continue
            if where == "cell":                       # to the nodes first
                tmp = part.cell_data_to_point_data()
                vals = np.asarray(tmp.point_data[field], dtype=float)
            part.point_data[key] = gradient_magnitude(part, vals)
        return key

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
        self._sync_units()
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
            self.stats.setVisible(True)
            sc.results.clear()
            return
        if f == SPEED:
            self._ensure_speed()
        base = f                                      # its unit
        q, fu, su = self.unit_of(base)
        unit = su if q is not None and fu else ""
        if self.shown == "gradient":
            f = self._ensure_gradient(f)
            k = field_scale(q, fu, su) if unit else 1.0
            conv, back = (lambda v: v * k), (lambda v: v / k)    # noqa: E731
            per = sc.model.units or "length"
            unit = f"{unit}/{per}" if unit else f"/{per}"
        elif unit:
            conv = lambda v: convert_field(v, q, fu, su)          # noqa: E731
            back = lambda v: convert_field(v, q, su, fu)          # noqa: E731
        else:
            conv = back = lambda v: v                             # noqa: E731
        for lab in (self.lo_unit, self.hi_unit):
            lab.setText(unit)
        vals = self._values(f)
        vals = conv(vals[np.isfinite(vals)])
        if not len(vals):
            self.stats.setText("No visible boundary has this field.")
            self.stats.setVisible(True)
            sc.results.clear()
            return
        self.stats.setVisible(False)
        a_lo, a_hi = float(vals.min()), float(vals.max())
        self.lo.setPlaceholderText(f"auto: {nice_num(a_lo)}")
        self.hi.setPlaceholderText(f"auto: {nice_num(a_hi)}")
        lo = self.lo.value() if self.lo.value() is not None else a_lo
        hi = self.hi.value() if self.hi.value() is not None else a_hi
        stops = COLORMAPS.get(self.cmap.currentData(), COLORMAPS[DEFAULT_MAP])
        if hi <= lo:
            hi = lo + (abs(lo) or 1.0) * 1e-6
        self.bar.set(stops, lo, hi)
        if self.colour_on.isChecked():                # the colours work in the file's numbers
            sc.results.show_field(f, back(lo), back(hi), stops)
        else:
            sc.results.clear()
