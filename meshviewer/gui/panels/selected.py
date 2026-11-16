"""The Measure Selected tool (Measure tab, below the Measuring Tool): what Select ▾ last
picked, in numbers (render/element_details.py).

    Edge · Wing                      the kind and its part
    Length              412.5 mm
    Start / End / Midpoint …
    Dihedral angle      90°
    Arc                 radius 12 mm
    Show diameter                    (switch; a circle or an arc: its diameter and center)

With Part picked in Select ▾, or nothing picked, a gray line says what to do.
"""
from __future__ import annotations

from PySide6.QtWidgets import QWidget

from meshviewer.gui.forms import _label, column, note, readout, readout_grid, switch_row
from meshviewer.gui.widgets import Switch
from meshviewer.render.element_details import details

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
        self.refresh()

    def bind(self, scene):
        self.scene = scene
        self.diameter.blockSignals(True)
        self.diameter.setChecked(scene.elements.show_diameter)
        self.diameter.blockSignals(False)
        self.refresh()

    def _diameter(self, on):
        if self.scene is not None:
            self.scene.elements.set_show_diameter(on)

    def refresh(self):
        """After a pick (Elements.on_changed) or a change of unit."""
        for w in self._cells:
            w.deleteLater()
        self._cells = []
        got = None
        if self.scene is not None:
            try:
                got = details(self.scene.elements)
            except Exception as exc:                        # noqa: BLE001
                print(f"Measure Selected: {exc}")
        self.title.setVisible(got is not None)
        self.note.setVisible(got is None)
        self.grid_w.setVisible(got is not None)
        circle = got is not None and any(k in ("Circle", "Arc") for k, _ in got[1])
        self.diameter_row.setVisible(bool(circle))
        if got is None:
            return
        title, rows = got
        self.title.setText(title)
        for r, (k, v) in enumerate(rows):
            a, b, _ = readout(self.grid, r, k, v)
            self._cells += [a, b]
