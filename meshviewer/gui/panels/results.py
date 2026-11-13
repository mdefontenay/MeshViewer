"""The Results tool — a solution field from the solver painted on
the boundaries (files that carry one: FUN3D's Tecplot boundary output, .dat).

    Results
      Field          [ Velocity u                 ▾ ]   by subject (core/field_kinds)
      Unit in file   [ —  As written             ▾ ]   what the file's numbers are in
      Shown in       [ km/h                       ▾ ]   once the file's unit is known
      (a line saying what applies: no unit, as written, unknown field…)
      ───────────────────────────────────────────
      Color the boundaries                    (switch)
      Color by       [ Value | Gradient ]
      Scale          [ Linear | Log ]               log: by powers of ten (values > 0)
      Colors         [ ▬▬▬▬ (the color map)       ▾ ]
      ▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬
      0.02            0.81              1.6
      Min [ auto: 0.02 ] kPa
      Max [ auto: 1.6 ]  kPa

Units: a field Mesh Viewer knows (core/field_kinds: pressure, Mach, stress…) offers its
quantity's units, or none (Mach, y+, cp); a field it doesn't know, every unit by
quantity; a position, lengths (the file's unit, shown in the toolbar's until another is
picked). Solvers often write non-dimensional numbers: "As written" uses them as they are.

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

from meshviewer.gui.forms import _grid, _row, rule
from meshviewer.core.field_kinds import GROUP_ORDER, KINDS, field_kind
from meshviewer.core.fields import (COLORMAPS, DEFAULT_MAP, SEQUENTIAL, SPEED, field_values,
                                    gradient_magnitude, solution_fields)
from meshviewer.core.plots import AXES, COORD
from meshviewer.gui.widgets import Capsule, GradientSelect, MenuSelect, NumberField, Switch
from meshviewer.core.units import (NO_UNIT, QUANTITIES, QUANTITY_TITLES, convert_field,
                                   field_scale, nice_num, unit_quantity)

GRAD = "__grad__"                    # point array: |∇ field| (kept on the parts)
POS = "__pos_"                       # point array: the X / Y / Z of each node ("__pos_x")

def field_label(f):
    """The menu text of a field: its usual name (core/field_kinds), else as written."""
    if f.startswith(COORD):
        return f"Position {f[len(COORD):].upper()}"
    kind = field_kind(f)
    return kind.title if kind is not None else f


def grouped(fields):
    """[(header, [fields])]: the known fields by subject (field_kinds order), then
    Other (unknown), then Position."""
    order = {k.key: i for i, k in enumerate(KINDS)}
    out = {g: [] for g in GROUP_ORDER}
    other, position = [], []
    for f in fields:
        kind = None if f.startswith(COORD) else field_kind(f)
        if f.startswith(COORD):
            position.append(f)
        elif kind is not None:
            out[kind.group].append(f)
        else:
            other.append(f)
    for items in out.values():
        items.sort(key=lambda f: order[field_kind(f).key])
    return [(g, out[g]) for g in GROUP_ORDER if out[g]] + \
        ([("Other", other)] if other else []) + ([("Position", position)] if position else [])


class ScaleBar(QWidget):
    """The colour scale with three numbers under it: min, middle, max."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.stops, self.lo, self.hi, self.log = SEQUENTIAL, 0.0, 1.0, False
        self.setFixedHeight(28)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set(self, stops, lo, hi, log=False):
        self.stops, self.lo, self.hi, self.log = stops, lo, hi, bool(log and lo > 0)
        self.update()

    def value_at(self, pos):
        """The value at 0…1 along the bar (log: the geometric one)."""
        if self.log:
            return 10 ** (np.log10(self.lo) + pos * (np.log10(self.hi) - np.log10(self.lo)))
        return self.lo + pos * (self.hi - self.lo)

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
            v = self.value_at(pos)
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
        # -- which field, and its unit
        g = _grid()
        self.field = MenuSelect()
        self.field.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.field.setToolTip("Field")
        self.field.currentIndexChanged.connect(self._field_changed)
        _row(g, 0, "Field", self.field, wide=True)
        self.file_unit = MenuSelect()                  # what the file's numbers are in
        self.file_unit.setToolTip("Unit in File")
        self.shown_unit = MenuSelect()                 # what to show them in
        self.shown_unit.setToolTip("Shown In")
        for m in (self.file_unit, self.shown_unit):
            m.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            m.currentIndexChanged.connect(self._unit_changed)
        self._unit_rows = [_row(g, 1, "Unit in file", self.file_unit, wide=True)[0],
                           _row(g, 2, "Shown in", self.shown_unit, wide=True)[0]]
        lay.addLayout(g)
        self.unit_note = QLabel("")                    # what applies to this field's unit
        self.unit_note.setObjectName("InfoLine")
        self.unit_note.setWordWrap(True)
        lay.addWidget(self.unit_note)
        lay.addWidget(rule())

        # -- how the boundaries are colored
        r = QHBoxLayout()
        r.addWidget(QLabel("Color the boundaries"))
        r.addStretch(1)
        self.colour_on = Switch()
        self.colour_on.setToolTip("Color the Boundaries")
        self.colour_on.toggled.connect(self._update)
        r.addWidget(self.colour_on)
        lay.addLayout(r)
        g = _grid()
        grp = QActionGroup(self)
        grp.setExclusive(True)
        self.show_acts = {}
        for key, text in (("value", "Value"), ("gradient", "Gradient")):
            a = QAction(text, self)                    # gradient: |∇f| along the surface
            a.setCheckable(True)
            a.setToolTip(text)
            grp.addAction(a)
            a.triggered.connect(self._field_changed)     # its own range
            self.show_acts[key] = a
        self.show_acts["value"].setChecked(True)
        g.addWidget(QLabel("Color by"), 0, 0)
        g.addWidget(Capsule(list(self.show_acts.values()), name="Segmented"), 0, 1, 1, 3,
                    Qt.AlignLeft)
        grp = QActionGroup(self)
        grp.setExclusive(True)
        self.scale_acts = {}
        for key, text in (("linear", "Linear"), ("log", "Log")):
            a = QAction(text, self)                    # log: by powers of ten
            a.setCheckable(True)
            a.setToolTip(text)
            grp.addAction(a)
            a.triggered.connect(self._scale_changed)
            self.scale_acts[key] = a
        self.scale_acts["linear"].setChecked(True)
        g.addWidget(QLabel("Scale"), 1, 0)
        g.addWidget(Capsule(list(self.scale_acts.values()), name="Segmented"), 1, 1, 1, 3,
                    Qt.AlignLeft)
        self.cmap = GradientSelect()
        self.cmap.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        for key, stops in COLORMAPS.items():
            self.cmap.addItem(stops, key)
        self.cmap.setToolTip("Colors")
        self.cmap.currentIndexChanged.connect(self._update)
        _row(g, 2, "Colors", self.cmap, wide=True)
        lay.addLayout(g)
        self.bar = ScaleBar()
        lay.addWidget(self.bar)
        g = _grid()
        self.lo = NumberField()
        self.lo.setToolTip("Min")
        self.hi = NumberField()
        self.hi.setToolTip("Max")
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
        """The file's fields, then the position of each node: X, Y, Z."""
        fields = solution_fields(model.parts)
        return fields + [COORD + a for a in AXES] if fields else fields

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
        for title, group in grouped(fields):           # by subject, each under its header
            self.field.addSection(title)
            for f in group:
                self.field.addItem(field_label(f), f)
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
        self.scale_acts["log" if st.get("log") else "linear"].setChecked(True)
        self._units = {k: list(v) for k, v in (st.get("units") or {}).items()
                       if isinstance(v, (list, tuple)) and len(v) == 2}
        self._sync_units()
        self._update(save=False)

    def settings(self):
        return {"field": self.field.currentData(), "lo": self.lo.value(), "hi": self.hi.value(),
                "on": self.colour_on.isChecked(), "cmap": self.cmap.currentData(),
                "show": self.shown, "log": self.log,
                "units": {k: list(v) for k, v in self._units.items()}}

    # ---- units ---------------------------------------------------------------------------
    def unit_of(self, field):
        """(quantity, file unit, shown unit) of a field; quantity None = no unit.
        Its quantity: from its name (p, ρ, u, T…), else from the unit picked for it in
        the file; a position: a length, in the file's unit, shown in the one picked (or
        the toolbar's until one is)."""
        fu, su = self._units.get(field, [NO_UNIT, NO_UNIT])
        if field and field.startswith(COORD):
            model = self.scene.model if self.scene is not None else None
            fu = model.units if model is not None and model.units in QUANTITIES["length"] \
                else NO_UNIT
            if su not in QUANTITIES["length"]:
                du = self.scene.measure.display_unit if self.scene is not None else None
                su = du if du in QUANTITIES["length"] else fu
            return ("length", fu, su) if fu else (None, NO_UNIT, NO_UNIT)
        kind = field_kind(field)
        q = kind.quantity if kind is not None else unit_quantity(fu)   # known: no choice
        if q is None:
            return None, NO_UNIT, NO_UNIT
        table = QUANTITIES[q]
        su = su if su in table else (fu if fu in table else next(iter(table)))
        return q, (fu if fu in table else NO_UNIT), su

    def shown_values(self, field, vals):
        """Field values in the unit shown (unchanged when the file's has none)."""
        q, fu, su = self.unit_of(field)
        return vals if q is None or not fu else convert_field(vals, q, fu, su)

    def unit_label(self, field):
        q, fu, su = self.unit_of(field)
        return su if q is not None and fu else ""

    def _sync_units(self):
        """The unit rows for the field shown: Unit in file only where there is a choice,
        Shown in once the file's unit is known, and a line saying what applies."""
        f = self.field.currentData()
        if f is None:
            for w in (*self._unit_rows, self.file_unit, self.shown_unit, self.unit_note):
                w.setVisible(False)
            return
        q, fu, su = self.unit_of(f)
        kind = field_kind(f)
        position = f.startswith(COORD)
        for m in (self.file_unit, self.shown_unit):
            m.blockSignals(True)
            m.clear()
        if position:
            note = (f"Positions are in the file's unit, {fu} (File ▸ File Unit…)." if fu else
                    "The file doesn't say its unit: set it with File ▸ File Unit….")
        elif kind is not None and kind.quantity is None:
            note = f"{kind.title} has no unit."
        else:
            if kind is not None:                      # its quantity's units
                self.file_unit.addItem("—  As written", NO_UNIT)
                for k in QUANTITIES[kind.quantity]:
                    self.file_unit.addItem(k, k)
            else:                                     # unknown: any unit, by quantity
                self.file_unit.addItem("—  No unit", NO_UNIT)
                for quantity, table in QUANTITIES.items():
                    self.file_unit.addSection(QUANTITY_TITLES[quantity])
                    for k in table:
                        self.file_unit.addItem(k, k)
            self.file_unit.setCurrentIndex(max(0, self.file_unit.findData(fu)))
            if fu:
                note = ""
            elif kind is not None:
                note = ("As written in the file (solvers often write it non-dimensional). "
                        "Pick the unit it is in to show it in another.")
            else:
                note = ("Mesh Viewer doesn't know this field: pick its unit if it has one, "
                        "to show it in another.")
        choose = not position and (kind is None or kind.quantity is not None)
        self._unit_rows[0].setVisible(choose)
        self.file_unit.setVisible(choose)
        for k in (QUANTITIES[q] if q and fu else ()):
            self.shown_unit.addItem(k, k)
        self.shown_unit.setCurrentIndex(max(0, self.shown_unit.findData(su)))
        self._unit_rows[1].setVisible(bool(q and fu))
        self.shown_unit.setVisible(bool(q and fu))
        self.unit_note.setText(note)
        self.unit_note.setVisible(bool(note))
        for m in (self.file_unit, self.shown_unit):
            m.blockSignals(False)

    def _unit_changed(self, *_):
        f = self.field.currentData()
        if f is None:
            return
        old = self.unit_of(f)
        fu, su = self.file_unit.currentData(), self.shown_unit.currentData()
        if f.startswith(COORD):
            fu = NO_UNIT                                # (the file's own, not stored)
        elif unit_quantity(fu) != unit_quantity(old[1]) and field_kind(f) is None:
            su = fu                                     # another quantity: shown as written
        self._units[f] = [fu, su]
        new = self.unit_of(f)
        if new[:2] != old[:2]:
            self._sync_units()                          # Shown in: shown, its units
        if new != old:                                  # typed Min / Max: same quantity
            for box in (self.lo, self.hi):
                v = box.value()
                if v is not None and old[1] and new[1] and old[0] == new[0]:
                    box.setValue(convert_field(convert_field(v, old[0], old[2], old[1]),
                                               new[0], new[1], new[2]))
                elif v is not None:
                    box.setValue(None)
        self._update()
        self.units_changed.emit()

    @property
    def log(self):
        return self.scale_acts["log"].isChecked()

    def _scale_changed(self, *_):
        """Linear ↔ log: a typed Min at or below zero means nothing on a log scale."""
        if self.log and self.lo.value() is not None and self.lo.value() <= 0:
            self.lo.setValue(None)
        self._update()

    @property
    def shown(self):
        return "gradient" if self.show_acts["gradient"].isChecked() else "value"

    def model_changed(self):
        self._update(save=False)

    def length_unit_changed(self):
        """The toolbar's unit or the file's changed: a position that follows the toolbar
        (no unit picked for it here), or any position when the file's unit changed, had
        its typed Min / Max in the old one, so they go back to auto."""
        f = self.field.currentData()
        if f and f.startswith(COORD):
            if self.lo.value() is not None or self.hi.value() is not None:
                self.lo.setValue(None)
                self.hi.setValue(None)
            self._sync_units()
            self._update()
        else:
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

    def _ensure_position(self, field):
        """X / Y / Z of every node as a point array (read again each time: the Edit tool
        moves the parts); returns its name."""
        i = AXES.index(field[len(COORD):])
        key = POS + AXES[i]
        for part in self.scene.model.parts.values():
            if part.n_points:
                part.point_data[key] = np.asarray(part.points[:, i], dtype=float)
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
        position = f.startswith(COORD)
        if position:                                  # a length, as the other fields
            f = self._ensure_position(f)
        if position and self.shown == "gradient":     # |∇x| along a surface: no unit
            f = self._ensure_gradient(f)
            unit = ""
            conv = back = lambda v: v                             # noqa: E731
        elif self.shown == "gradient":
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
        log = self.log
        if log:                                       # only what a log scale can show
            vals = vals[vals > 0]
            if not len(vals):
                self.stats.setText("No value above zero here: a log scale can't show it.")
                self.stats.setVisible(True)
                sc.results.clear()
                return
        self.stats.setVisible(False)
        a_lo, a_hi = float(vals.min()), float(vals.max())
        self.lo.setPlaceholderText(f"auto: {nice_num(a_lo)}")
        self.hi.setPlaceholderText(f"auto: {nice_num(a_hi)}")
        lo = self.lo.value() if self.lo.value() is not None else a_lo
        hi = self.hi.value() if self.hi.value() is not None else a_hi
        if log and lo <= 0:                           # (typed): the smallest above zero
            lo = a_lo
        stops = COLORMAPS.get(self.cmap.currentData(), COLORMAPS[DEFAULT_MAP])
        if hi <= lo:
            hi = lo * 10 if log else lo + (abs(lo) or 1.0) * 1e-6
        self.bar.set(stops, lo, hi, log)
        if self.colour_on.isChecked():                # the colours work in the file's numbers
            sc.results.show_field(f, back(lo), back(hi), stops, log)
        else:
            sc.results.clear()
