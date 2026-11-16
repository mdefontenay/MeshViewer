"""The Plots tool — plots under the 3D view (F13).

    Plots
      [ New Plot… ]
      ▾ Root                                (opening it shows its plot)
        ┌ Plane ─────────────────────────────────────┐
        │ Normal to  [ X | Y | Z ] [ ✎ ]              │
        │ Origin     [x] [y] [z]   (✎ Edit Plane)     │
        │ Normal     [x] [y] [z]                      │
        │ Position   [ auto: 0.35 ] m                 │
        │            ───●──────────  (slider)         │
        │ Plot ──────────────────────────────────────  │
        │ Values     [ Pressure coefficient cp ▾ ]    │
        │ Along      [ X | Z ]        [ Normalize ]   │
        │ ▸ Axes          X        Y                  │
        │   Min        [auto]   [auto]                │
        │   Max        [auto]   [auto]                │
        │   Log          ○        ○                   │
        │   Flip         ○        ●  (cp: y flipped)  │
        │                              Fit            │
        │ Points ─────────────── [ Import… | Export… ]│
        └─────────────────────────────────────────────┘
                                      [ Rename… | Delete ]
      ▸ Tip

Every plot has its tab under the 3D view (window.py) and a fold-out here,
named by the user. The kind of plot picks its editor: EDITORS (only "section"
for now; a new kind adds an editor here and an entry in core/plots.py KINDS).
The panel computes the plots (core.plots.compute) and says so with `changed`.
The plots live on the scene (scene.plots: a list of dicts, remembered per file).
Axes (and the plot itself: the wheel zooms, a drag pans, a double-click fits) only
change how the plot is drawn: `view_changed`, no new cut.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFrame, QGridLayout, QHBoxLayout, QLayout, QLineEdit,
    QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from meshviewer.core import plots
from meshviewer.core.units import nice_num
from meshviewer.gui.access import name_controls
from meshviewer.gui.panels.section import edit_plane_action
from meshviewer.gui.forms import (
    _grid, _label, button, buttons, caption, group_head, link, note, rule, segmented,
    label_width, sheet_title, xyz_fields,
)
from meshviewer.gui.sheets import ask_open, ask_save, ask_text, save_folder
from meshviewer.gui.widgets import (
    Capsule, CollapsibleSection, IconToggle, MenuSelect, NoWheelSlider, NumberField, Switch,
)

SLIDER_STEPS = 1000


def value_label(v):
    """Menu text of a value: the field's usual name (as in Results), 'Position X' for X."""
    from meshviewer.gui.panels.results import field_label
    if v.startswith(plots.COORD):
        return f"Position {v[len(plots.COORD):].upper()} (the shape)"
    return field_label(v)


# ---- the editor of a section plot ---------------------------------------------------------
class SectionEditor(QWidget):
    """Settings of one section plot; edits its dict in place."""
    changed = Signal()
    view_changed = Signal()            # Axes: only how it is drawn

    def __init__(self, panel, m):
        super().__init__()
        self.panel, self.m = panel, m
        self._slide = QTimer(self)                     # the slider: one plot per pause
        self._slide.setSingleShot(True)
        self._slide.setInterval(40)
        self._slide.timeout.connect(self.changed.emit)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 2, 0, 2)
        lay.setSpacing(6)
        card = QFrame()
        card.setObjectName("ResultCard")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(8, 9, 8, 10)
        cl.setSpacing(6)
        lay.addWidget(card)

        # -- where the plane cuts (laid out like the Section section)
        cl.addWidget(caption("Plane"))
        g = _grid()
        self.axis, cap = segmented(self, [(a, a.upper(), f"The plane is normal to {a.upper()}")
                                           for a in plots.AXES], self._axis)
        self.axis_group = next(iter(self.axis.values())).actionGroup()
        self.axis_group.setExclusionPolicy(QActionGroup.ExclusionPolicy.ExclusiveOptional)
        self.edit_plane = edit_plane_action(self)        # ✎: origin and normal, any way
        row = QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(cap)
        row.addWidget(buttons(self.edit_plane))
        row.addStretch(1)
        g.addWidget(_label("Normal to"), 0, 0)
        g.addLayout(row, 0, 1, 1, 3)
        self.pos = NumberField()
        self.pos.setToolTip("Where the plane is, along its normal (the X, Y or Z coordinate "
                            "when normal to one). Empty = the middle")
        self.pos.valueChanged.connect(self._pos_typed)
        self.pos_unit = _label("", "AxisLabel")
        g.addWidget(_label("Position"), 2, 0)
        g.addWidget(self.pos, 2, 1)
        g.addWidget(self.pos_unit, 2, 2)
        self.slider = NoWheelSlider(Qt.Horizontal)
        self.slider.setRange(0, SLIDER_STEPS)
        self.slider.setToolTip("Slide the plane across the model")
        self.slider.valueChanged.connect(self._slid)
        g.addWidget(self.slider, 3, 1, 1, 3)
        self.origin = [NumberField() for _ in range(3)]
        self.normal = [NumberField() for _ in range(3)]
        self.advanced = xyz_fields((                   # origin / normal, as in Section
            ("Origin", self.origin, "A point on the plane"),
            ("Normal", self.normal, "The direction the plane faces (any length)")))
        for b in self.origin:
            b.valueChanged.connect(self._origin_typed)
        for b in self.normal:
            b.valueChanged.connect(self._normal_typed)
        self.advanced.setVisible(False)
        self.edit_plane.toggled.connect(self.advanced.setVisible)
        g.addWidget(self.advanced, 1, 0, 1, 4)         # right under Normal to
        cl.addLayout(g)
        cl.addWidget(rule())

        # -- what is plotted
        cl.addWidget(caption("Plot"))
        g = _grid()
        self.value = MenuSelect()
        self.value.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.value.setToolTip("What is plotted: a solution field, or a position (the shape)")
        self.value.currentIndexChanged.connect(self._value)
        g.addWidget(_label("Values"), 0, 0)
        g.addWidget(self.value, 0, 1, 1, 3)
        self.along_box = QWidget()
        self.along_lay = QHBoxLayout(self.along_box)
        self.along_lay.setContentsMargins(0, 0, 0, 0)
        self.along_lay.setSpacing(6)
        self.chord = QAction("Normalize", self)
        self.chord.setCheckable(True)
        self.chord.setToolTip("Divide by the chord (x/c): the x axis from 0 (leading edge) "
                              "to 1 (trailing edge) of the cut")
        self.chord.toggled.connect(self._chord)
        # X / Y / Z made once; the plane's own axis is hidden (rebuilding the buttons
        # on each change left one of them unlit on macOS)
        self.along, along_cap = segmented(
            self, [(k, k.upper(), f"The plot's x axis: the {k.upper()} position along the cut")
                   for k in plots.AXES], self._along)
        self._along_cap = along_cap
        self.along_lay.addWidget(along_cap)
        self._chord_cap = Capsule([self.chord], name="Segmented")
        self.along_lay.addStretch(1)
        self.along_lay.addWidget(self._chord_cap)
        g.addWidget(_label("Along"), 1, 0)
        g.addWidget(self.along_box, 1, 1, 1, 3)
        cl.addLayout(g)
        cl.addWidget(self._build_axes())
        cl.addWidget(rule())

        # -- compare and save
        imp = button(self, "Import…", self.import_csv,
                     "Reference points from a CSV (test data, another solver): the first\n"
                     "two numbers of each row are x and the value")
        exp = button(self, "Export…", self.export_csv,
                     "The plotted points to a CSV: part, x, value, X, Y, Z")
        cl.addLayout(group_head("Points", buttons(imp, exp)))
        refl = QHBoxLayout()
        self.ref_label = note()
        refl.addWidget(self.ref_label, 1)
        self.ref_remove = link("Remove", "Remove the reference points", self._remove_ref)
        refl.addWidget(self.ref_remove, 0, Qt.AlignTop)
        cl.addLayout(refl)
        self.status = note()                               # only when something is wrong
        cl.addWidget(self.status)

        # -- rename / delete, under the card (like Undo · Reset in Edit)
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        ren = button(self, "Rename…", lambda: self.panel.rename(self.m["id"]))
        dele = button(self, "Delete", lambda: self.panel.remove(self.m["id"]),
                      "Delete this plot and its tab")
        bottom.addWidget(buttons(ren, dele))
        lay.addLayout(bottom)
        self.sync()

    # ---- from the plot's dict to the widgets --------------------------------------------
    @property
    def scene(self):
        return self.panel.scene

    def _scale(self):
        return self.scene.measure.unit_scale() if self.scene else (1.0, "")

    def _names(self):
        sc = self.scene
        return [n for n in sc.names if sc.visible.get(n)] or list(sc.names)

    def _range(self):
        """Positions along the normal that touch the visible boundaries, file units."""
        return plots.position_range(self.m, self.scene.model.parts, self._names())

    def sync_axis(self):
        """X / Y / Z lit when the plane is normal to one (none when tilted)."""
        straight = plots.aligned(self.m)
        main = plots.main_axis(plots.plane_normal(self.m))
        for k, a in self.axis.items():
            a.setChecked(straight and k == main)

    def sync(self):
        if hasattr(self, "axis_range"):
            self.sync_axes()
        m = self.m
        self.sync_axis()
        self.value.blockSignals(True)
        self.value.clear()
        from meshviewer.gui.panels.results import grouped
        for title, group in grouped(plots.values_of(self.scene.model.parts)):
            self.value.addSection(title)                # as Results ▸ Field
            for v in group:
                self.value.addItem(value_label(v), v)
        i = self.value.findData(m.get("value"))
        self.value.setCurrentIndex(i if i >= 0 else 0)
        self.value.blockSignals(False)
        self._build_along()
        self.chord.blockSignals(True)
        self.chord.setChecked(bool(m.get("chord")))
        self.chord.blockSignals(False)
        self.sync_position()
        self.sync_ref()

    def sync_position(self):
        s, unit = self._scale()
        lo, hi = self._range()
        self.pos_unit.setText(unit)
        o, n = plots.section_plane({**self.m, "pos": None}, self.scene.model.parts,
                                   self._names())
        mid = float(n @ o)                             # through the middle
        self.pos.setPlaceholderText(f"auto: {nice_num(mid * s)}")
        p = self.m.get("pos")
        self.pos.blockSignals(True)
        self.pos.setValue(None if p is None else p * s)
        self.pos.blockSignals(False)
        here = mid if p is None else p
        # the visible boundaries can be flat along the normal (a symmetry plane cut
        # across): the range is then ~0 wide, so keep the slider within its ends
        frac = (here - lo) / (hi - lo) if hi > lo else 0.0
        frac = min(max(frac, 0.0), 1.0) if np.isfinite(frac) else 0.0
        self.slider.blockSignals(True)
        self.slider.setValue(int(round(frac * SLIDER_STEPS)))
        self.slider.blockSignals(False)
        o, n = plots.section_plane(self.m, self.scene.model.parts, self._names())
        if self.m.get("normal") is not None:
            n = np.asarray(self.m["normal"], dtype=float)     # as typed, as in Section
        for boxes, vals in ((self.origin, o * s), (self.normal, n)):
            for b, v in zip(boxes, vals):
                b.blockSignals(True)
                b.setValue(float(f"{v:.6g}") if abs(v) > 1e-12 else 0.0)
                b.blockSignals(False)

    def _build_along(self):
        """Only the two axes in the plane."""
        main = plots.main_axis(plots.plane_normal(self.m))
        self._along_cap.show_only([a for k, a in self.along.items() if k != main])

    def sync_result(self, r):
        """After a compute: which way the x axis runs, flip, how many points."""
        for k, a in self.along.items():
            a.setChecked(k == r["along"])
        Switch.set_silently(self.axis_flip["y"], r["flip"])
        self.status.setText("The plane misses the visible boundaries (or they don't "
                            "carry this value)." if r["empty"] else "")
        self.status.setVisible(bool(r["empty"]))

    def sync_ref(self):
        ref = self.m.get("ref")
        self.ref_label.setText(f"{ref['name']} · {len(ref['points'])} points" if ref else "")
        self.ref_label.setVisible(bool(ref))
        self.ref_remove.setVisible(bool(ref))

    # ---- handlers ------------------------------------------------------------------------
    def _set(self, **kw):
        self.m.update(kw)
        self.changed.emit()

    def _axis(self, k):
        if k != self.m["axis"] or self.m.get("normal") is not None:
            self.m["along"] = None
            self.m["pos"] = None                       # the middle of the new axis
            self.m["normal"] = None
            self.m["axis"] = k
        self.sync_axis()
        self._build_along()
        self.sync_position()
        self.changed.emit()

    def _plane_typed(self, origin=None, normal=None):
        plots.set_plane(self.m, origin=origin, normal=normal, parts=self.scene.model.parts,
                        names=self._names())
        self.sync_axis()
        self._build_along()
        self.sync_position()
        self.changed.emit()

    def _origin_typed(self, *_):
        s, _u = self._scale()
        vals = [b.value() for b in self.origin]
        if None not in vals:
            self._plane_typed(origin=[v / s for v in vals])

    def _normal_typed(self, *_):
        vals = [b.value() for b in self.normal]
        if None not in vals and any(vals):
            self._plane_typed(normal=vals)

    def _pos_typed(self, v):
        s, _ = self._scale()
        self.m["pos"] = None if v is None else v / s
        self.sync_position()
        self.changed.emit()

    def _slid(self, i):
        lo, hi = self._range()
        self.m["pos"] = float(lo + (hi - lo) * i / SLIDER_STEPS)
        s, _ = self._scale()
        self.pos.blockSignals(True)
        self.pos.setValue(float(f"{self.m['pos'] * s:.6g}"))
        self.pos.blockSignals(False)
        self._slide.start()                            # plotted when the slider rests 40 ms

    def flush(self):
        """Plot now what the slider asked for (tests)."""
        if self._slide.isActive():
            self._slide.stop()
            self.changed.emit()

    def _value(self, *_):
        self.m["flip"] = None                          # cp: negative up again
        self._set(value=self.value.currentData())

    def _along(self, k):
        self._set(along=k)

    def _chord(self, on):
        self._set(chord=bool(on))

    # ---- Axes: ranges, log, flip (how the plot is drawn) -------------------------------
    def _build_axes(self):
        """▸ Axes: Min / Max (empty = auto), Log and Flip for X and Y; Fit."""
        w = QWidget()
        g = QGridLayout(w)
        g.setContentsMargins(0, 0, 0, 0)
        g.setHorizontalSpacing(6)
        g.setVerticalSpacing(5)
        g.setColumnMinimumWidth(0, label_width())        # as the form grids above
        g.setColumnStretch(1, 1)
        g.setColumnStretch(2, 1)
        for c, k in enumerate("XY", start=1):
            h = _label(k, "AxisLabel")
            h.setAlignment(Qt.AlignCenter)
            g.addWidget(h, 0, c)
        self.axis_range, self.axis_log, self.axis_flip = {}, {}, {}
        for r, (text, end) in enumerate((("Min", "min"), ("Max", "max")), start=1):
            g.addWidget(_label(text), r, 0)
            for c, k in enumerate("xy", start=1):
                f = NumberField(None)
                f.setPlaceholderText("auto")
                f.setToolTip(f"{k.upper()} {end} (empty = auto)")
                f.valueChanged.connect(lambda v, key=f"{k}_{end}": self._view(**{key: v}))
                g.addWidget(f, r, c)
                self.axis_range[f"{k}_{end}"] = f
        for r, (text, store, attr) in enumerate((("Log", "log", self.axis_log),
                                                 ("Flip", "flip", self.axis_flip)),
                                                start=3):
            g.addWidget(_label(text), r, 0)
            for c, k in enumerate("xy", start=1):
                sw = Switch()
                sw.setToolTip(f"{text} {k.upper()}")
                sw.setAccessibleName(f"{text} {k.upper()}")
                key = "flip" if (store, k) == ("flip", "y") else f"{k}_{store}"
                sw.toggled.connect(lambda on, key=key: self._view(**{key: bool(on)}))
                g.addWidget(sw, r, c, Qt.AlignCenter)
                attr[k] = sw
        fit = link("Fit", "Back to the whole plot (auto ranges)", self.fit_view)
        g.addWidget(fit, 5, 2, Qt.AlignRight)
        self.axes_section = CollapsibleSection("Axes", w, "plot_axes", sub=True,
                                               start_open=False)
        return self.axes_section

    def _view(self, **kw):
        """Only how it is drawn: no new cut."""
        self.m.update(kw)
        self.view_changed.emit()

    def fit_view(self):
        self.set_ranges(None, None, None, None)

    def set_ranges(self, x0, x1, y0, y1):
        """The plot zoomed / panned (or Fit): its ranges, the fields follow."""
        self.m.update(x_min=x0, x_max=x1, y_min=y0, y_max=y1)
        self.sync_axes()
        self.view_changed.emit()

    def sync_axes(self):
        for key, f in self.axis_range.items():
            f.blockSignals(True)
            v = self.m.get(key)
            f.setValue(None if v is None else float(f"{v:.6g}"))
            f.blockSignals(False)
        for k in "xy":
            Switch.set_silently(self.axis_log[k], bool(self.m.get(f"{k}_log")))
        Switch.set_silently(self.axis_flip["x"], bool(self.m.get("x_flip")))

    def _remove_ref(self):
        self.m["ref"] = None
        self.sync_ref()
        self.changed.emit()

    def set_reference(self, name, points):
        self.m["ref"] = {"name": name, "points": [list(map(float, p)) for p in points]}
        self.sync_ref()
        self.changed.emit()

    def import_csv(self):
        if self.scene:
            self.scene.end_stuck_drag()
        ask_open(self.window(), "Import Reference Points", "",
                 "CSV or text (*.csv *.txt *.dat);;All files (*)", self._read_csv)

    def _read_csv(self, fn):
        try:
            pts = plots.read_csv(Path(fn).read_text(errors="replace"))
        except OSError as exc:
            self.status.setText(f"Could not read {Path(fn).name}: {exc}")
            self.status.setVisible(True)
            return
        if not pts:
            self.status.setText(f"No numbers found in {Path(fn).name} "
                                "(two columns: x and the value).")
            self.status.setVisible(True)
            return
        self.set_reference(Path(fn).name, pts)

    def export_csv(self):
        r = self.panel.results.get(self.m["id"])
        if not r or r["empty"]:
            return
        base = self.panel.file_stem
        if self.scene:
            self.scene.end_stuck_drag()
        folder = save_folder(getattr(self.window(), "path", None))
        ask_save(self.window(), "Export Plot", folder / f"{base} - {self.m['name']}.csv",
                 "CSV (*.csv)", lambda fn: self._write_csv(fn, r))

    def _write_csv(self, fn, r):
        s, unit = self._scale()
        vu = self.panel.value_unit(r["value"]) if self.panel.value_unit else None
        Path(fn).write_text(plots.to_csv(self.m, r, s, unit, value_unit=vu))


EDITORS = {"section": SectionEditor}


# ---- New Plot sheet -------------------------------------------------------------------------
class NewPlotDialog(QDialog):
    def __init__(self, parent, name):
        super().__init__(parent)
        self.setWindowTitle("New Plot")
        self.setWindowModality(Qt.WindowModal)          # a sheet on macOS
        lay = QVBoxLayout(self)
        lay.setSizeConstraint(QLayout.SetFixedSize)
        lay.setContentsMargins(20, 18, 20, 14)
        lay.setSpacing(10)
        lay.addWidget(sheet_title("New Plot"))
        g = _grid()
        self.name = QLineEdit(name)
        self.name.selectAll()
        self.name.setMinimumWidth(220)
        g.addWidget(_label("Name"), 0, 0)
        g.addWidget(self.name, 0, 1, 1, 3)
        self.kind = MenuSelect()
        for k, spec in plots.KINDS.items():
            self.kind.addItem(spec["title"], k)
        g.addWidget(_label("Type"), 1, 0)
        g.addWidget(self.kind, 1, 1, 1, 3)
        lay.addLayout(g)
        lay.addWidget(note("Its plot opens in a tab under the 3D view."))
        b = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        b.accepted.connect(self.accept)
        b.rejected.connect(self.reject)
        lay.addWidget(b)


# ---- the tool -----------------------------------------------------------------------------
class PlotsPanel(QWidget):
    changed = Signal(int)          # a plot is new (id)
    added = Signal(int)
    removed = Signal(int)
    renamed = Signal(int)
    show_plot = Signal(int)        # open its tab
    cuts_changed = Signal()        # an eye clicked: which cuts are drawn in 3D

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = None
        self.file_stem = "plot"
        self.value_unit = None     # field -> (convert, label): Results' units (window.py)
        self.results = {}          # id -> core.plots.compute() result
        self.editors = {}          # id -> (CollapsibleSection, editor)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.new = QPushButton("New Plot…")
        self.new.setObjectName("ApplyButton")
        self.new.setCursor(Qt.PointingHandCursor)
        self.new.setToolTip("Name a new plot and pick its type")
        self.new.clicked.connect(self.ask_new)
        lay.addWidget(self.new)
        self.list = QVBoxLayout()
        self.list.setSpacing(6)
        lay.addLayout(self.list)

    # ---- binding ---------------------------------------------------------------------------
    def bind(self, scene, file_stem="plot"):
        for sec, _ed in list(self.editors.values()):
            self.list.removeWidget(sec)
            sec.hide()
            sec.setParent(None)
            sec.deleteLater()
        self.editors, self.results = {}, {}
        if self.scene is not None and self.model_changed in self.scene.visibility_listeners:
            self.scene.visibility_listeners.remove(self.model_changed)
        self.scene = scene
        self.file_stem = file_stem
        scene.visibility_listeners.append(self.model_changed)   # cut the shown boundaries
        if not hasattr(scene, "plots") or scene.plots is None:
            scene.plots = []
        scene.plots = [m for m in scene.plots if m.get("kind") in plots.KINDS]
        for m in scene.plots:
            self._editor(m, expanded=False)
            self._compute(m["id"], emit=False)

    def plot(self, ident):
        return next((m for m in self.scene.plots if m["id"] == ident), None) if self.scene \
            else None

    def _next_name(self, kind):
        title = plots.KINDS[kind]["title"]
        used = {m["name"] for m in self.scene.plots}
        k = 1
        while f"{title} {k}" in used:
            k += 1
        return f"{title} {k}"

    # ---- add / rename / remove ----------------------------------------------------------------
    def ask_new(self):
        if not self.scene:
            return
        d = NewPlotDialog(self.window(), self._next_name("section"))
        self._dialog = d
        d.accepted.connect(lambda: self.add(d.kind.currentData(),
                                            d.name.text().strip() or self._next_name("section")))
        d.open()

    def add(self, kind, name):
        ident = max((m["id"] for m in self.scene.plots), default=0) + 1
        m = plots.new_plot(kind, name, ident, self.scene.model)
        self.scene.plots.append(m)
        self._editor(m, expanded=True)
        self._compute(ident, emit=False)
        self.added.emit(ident)
        return ident

    def rename(self, ident, name=None):
        m = self.plot(ident)
        if m is None:
            return
        if name is None:
            if self.scene:
                self.scene.end_stuck_drag()
            ask_text(self.window(), "Rename Plot", "Name", m["name"],
                     lambda text: self.rename(ident, text))
            return
        name = name.strip()
        if name:
            m["name"] = name
            self.editors[ident][0].set_title(name)
            self.renamed.emit(ident)

    def remove(self, ident):
        m = self.plot(ident)
        if m is None:
            return
        self.scene.plots.remove(m)
        sec, _ = self.editors.pop(ident)
        self.list.removeWidget(sec)
        sec.hide()
        sec.setParent(None)
        sec.deleteLater()
        self.results.pop(ident, None)
        self.removed.emit(ident)

    def _editor(self, m, expanded):
        ed = EDITORS[m["kind"]](self, m)
        ed.changed.connect(lambda i=m["id"]: self._compute(i))
        ed.view_changed.connect(lambda i=m["id"]: self.changed.emit(i))   # redraw only
        eye = IconToggle(("eye", "eye_off"), "Show this cut in the 3D view",
                         checked=m.get("show", True), eye=True)
        eye.toggled.connect(lambda on, mm=m: (mm.__setitem__("show", bool(on)),
                                              self.cuts_changed.emit()))
        sec = CollapsibleSection(m["name"], ed, f"plot{m['id']}", trailing=eye, remember=False,
                                 start_open=expanded, sub=True)
        sec.header.setToolTip("Click to show or hide its settings (opening one shows its plot)")
        sec.toggled.connect(lambda on, i=m["id"]: on and self.show_plot.emit(i))
        self.list.addWidget(sec)
        self.editors[m["id"]] = (sec, ed)
        name_controls(sec)                             # VoiceOver: its switches and eye

    # ---- computing ----------------------------------------------------------------------------
    def _visible(self):
        sc = self.scene
        return [n for n in sc.names if sc.visible.get(n)]

    def _compute(self, ident, emit=True):
        m = self.plot(ident)
        if m is None:
            return
        r = plots.compute(m, self.scene.model.parts, self._visible())
        self.results[ident] = r
        self.editors[ident][1].sync_result(r)
        if emit:
            self.changed.emit(ident)

    def model_changed(self):
        """Visibility, the model (Edit) or the unit changed: every plot again."""
        if not self.scene:
            return
        for m in self.scene.plots:
            self.editors[m["id"]][1].sync_position()
            self._compute(m["id"])
