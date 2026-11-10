"""File unit sheet: asked the first time a file is opened — what unit are its numbers in?

STEP and IGES store their unit (the readers convert to mm), DXF may: it is
preselected. Other files store none: Settings ▸ Units says what to preselect (meshes
in meters, triangle CAD in millimeters at first) and whether to ask at all. The answer is remembered per file; File Unit… (File menu, the toolbar's unit menu,
or Info ▸ File unit) opens this sheet again.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QLayout, QVBoxLayout

from meshviewer.gui.widgets import Capsule

FILE_UNITS = (("mm", "mm"), ("cm", "cm"), ("m", "m"), ("in", "in"), ("ft", "ft"))


def default_unit(model, prefs=None):
    """The unit to preselect: the file's own, else Settings ▸ Units (m for meshes and mm
    for triangle CAD, unless changed there)."""
    if model.units:
        return model.units
    prefs = prefs or {}
    return prefs.get("unit_cad", "mm") if model.is_cad else prefs.get("unit_mesh", "m")


class FileUnitDialog(QDialog):
    chosen = Signal(str)

    def __init__(self, parent, file_name, unit, said=""):
        """unit: preselected · said: the unit the file itself states ("" = none)."""
        super().__init__(parent)
        self.setWindowTitle("File Unit")
        self.setWindowModality(Qt.WindowModal)          # a sheet on macOS
        lay = QVBoxLayout(self)
        lay.setSizeConstraint(QLayout.SetFixedSize)
        lay.setContentsMargins(20, 18, 20, 14)
        lay.setSpacing(10)
        title = QLabel(f"What unit is “{file_name}” in?")
        title.setStyleSheet("font-size: 15px; font-weight: 600;")
        lay.addWidget(title)
        note = QLabel(f"The file says {said}." if said else
                      "This file doesn't say. Change it any time in the toolbar's unit menu.")
        note.setObjectName("InfoLine")
        lay.addWidget(note)
        row = QHBoxLayout()
        group = QActionGroup(self)
        self.actions = {}
        for key, text in FILE_UNITS:
            a = QAction(text, self)
            a.setCheckable(True)
            group.addAction(a)
            self.actions[key] = a
        self.actions.get(unit, self.actions["mm"]).setChecked(True)
        row.addWidget(Capsule(list(self.actions.values()), name="Segmented"))
        row.addStretch(1)
        lay.addLayout(row)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(self._ok)
        lay.addWidget(buttons)

    @property
    def unit(self):
        return next(k for k, a in self.actions.items() if a.isChecked())

    def _ok(self):
        self.chosen.emit(self.unit)
        self.accept()

    def reject(self):                                   # Esc: keep the preselected unit
        self.chosen.emit(self.unit)
        super().reject()
