"""The Measure Selected tool (Measure tab, below the Measuring Tool): what Select ▾ last
picked, in numbers (render/element_details.py).

    Edge · Wing                      the kind and its part
    Length              412.5 mm
    Start / End / Midpoint …
    Dihedral angle      90°
    Arc                 radius 12 mm
    Show diameter                    (switch; a circle or an arc: its diameter and center)
    ───────────────────────────────
    Field Values                     a file with solution fields (Contours' units)
    Avg. Pressure p     101.3 kPa    "Avg.": along edges, over faces / cells / parts
    Avg. Mach number    0.82         (a node: its value, no "Avg.")

With nothing picked (Part: no part selected), a gray line says what to do; with Part,
the selected parts' field values only.
"""
from __future__ import annotations

from PySide6.QtWidgets import QWidget

from meshviewer.core.units import nice_num
from meshviewer.gui.forms import (_label, column, group_head, note, readout, readout_grid,
                                  rule, switch_row)
from meshviewer.gui.panels.contour_editor import field_label
from meshviewer.gui.widgets import Switch
from meshviewer.render.element_details import details, field_values

EMPTY = "Pick a node, an edge, a face or a cell with Select ▾ in the toolbar."


class SelectedPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = None
        lay = column(self)
        self.title = _label("", "ValueLabel")
        lay.addWidget(self.title)
        self.note = note(EMPTY)
        lay.addWidget(self.note)
        self.grid_w = QWidget()
        self.grid = readout_grid()
        self.grid_w.setLayout(self.grid)
        lay.addWidget(self.grid_w)
        self._cells = []
        self.diameter = Switch()               # a circle / arc: draw its diameter
        self.diameter.toggled.connect(self._diameter)
        self.diameter_row = switch_row("Show diameter", self.diameter)
        self.diameter.setToolTip("Show Diameter")
        lay.addWidget(self.diameter_row)
        # the solution fields over what is picked
        self.units = None                      # Contours (shown_values, unit_label): sidebar
        self.fields_box = QWidget()
        fl = column(self.fields_box)
        fl.addWidget(rule())
        fl.addLayout(group_head("Field Values"))
        self.fields_note = note()              # over how many
        fl.addWidget(self.fields_note)
        self.fields_grid = readout_grid()
        fl.addLayout(self.fields_grid)
        lay.addWidget(self.fields_box)
        self._field_cells = []
        self.field_rows = []                   # [(label, text)] shown (tests)
        self.refresh()

    def bind(self, scene):
        if self.scene is not None and self._time_changed in self.scene.time_listeners:
            self.scene.time_listeners.remove(self._time_changed)
        self.scene = scene
        scene.time_listeners.append(self._time_changed)         # another time step
        scene.field_users.append(self._fields_shown)
        self.diameter.blockSignals(True)
        self.diameter.setChecked(scene.elements.show_diameter)
        self.diameter.blockSignals(False)
        self.refresh()

    def _diameter(self, on):
        if self.scene is not None:
            self.scene.elements.set_show_diameter(on)

    def _fields_shown(self):
        """Every field while it lists a pick (None), else none."""
        sc = self.scene
        return None if self.isVisible() and (sc.elements.items or sc.selected_parts) else []

    def _time_changed(self):
        """Another time step: the Field Values of what is picked (nothing: nothing to do)."""
        if self.scene.elements.items or self.scene.selected_parts:
            self.refresh()

    def refresh(self):
        """After a pick (Elements.on_changed, a part selected) or a change of unit."""
        for w in self._cells:
            w.deleteLater()
        self._cells = []
        got = fv = None
        if self.scene is not None:
            sc = self.scene
            if sc.elements.items or sc.selected_parts:
                sc.ensure_fields(None)                  # every field, on the step shown
            try:
                got = details(self.scene.elements)
                fv = field_values(self.scene.elements)
            except Exception as exc:                        # noqa: BLE001
                print(f"Measure Selected: {exc}")
        self._show_fields(fv)
        if got is None and fv is not None and fv["fields"]:   # Part: its fields only
            sc = self.scene
            names = [n for n in sc.selected_parts if n in sc.model.parts]
            words = sc.model.item_words
            got = (f"{words[0].capitalize()} · {names[0]}" if len(names) == 1
                   else f"{len(names)} {words[1].capitalize()}", [])
        self.title.setVisible(got is not None)
        self.note.setVisible(got is None)
        self.grid_w.setVisible(got is not None)
        circle = got is not None and any(k in ("Circle", "Arc") for k, _ in got[1])
        self.diameter_row.setVisible(bool(circle))
        if got is None:
            return
        title, rows = got
        self.title.setText(title)
        self.grid_w.setVisible(bool(rows))
        for r, (k, v) in enumerate(rows):
            a, b, _ = readout(self.grid, r, k, v)
            self._cells += [a, b]

    def _show_fields(self, fv):
        """▸ Field Values: each field's title, value and unit (Contours' units); hidden
        with no fields or nothing picked."""
        for w in self._field_cells:
            w.deleteLater()
        self._field_cells = []
        self.field_rows = []
        on = fv is not None and bool(fv["fields"])
        self.fields_box.setVisible(on)
        if not on:
            return
        for r, (f, v) in enumerate(fv["fields"]):
            unit = ""
            if self.units is not None:
                v = float(self.units.shown_values(f, v))
                unit = self.units.unit_label(f)
            label = f"Avg. {field_label(f)}" if fv["mean"] else field_label(f)
            text = f"{nice_num(v)} {unit}".strip()
            a, b, _ = readout(self.fields_grid, r, label, text)
            self._field_cells += [a, b]
            self.field_rows.append((label, text))
        n, how = fv["n"], fv["how"]
        word = {"node": "nodes", "edge": "edges", "cell": "cells", "area": ""}[how]
        over = (f"Length-weighted over {n} edges." if how == "edge" and n > 1 else
                "Length-weighted along the edge." if how == "edge" else
                f"The mean of {n} {word}." if how in ("node", "cell") and n > 1 else
                "Area-weighted." if how == "area" else "")
        self.fields_note.setText(over)
        self.fields_note.setVisible(bool(over))
