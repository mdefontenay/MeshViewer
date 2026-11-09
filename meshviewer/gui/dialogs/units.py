"""File unit sheet: asked the first time a file is opened — what unit are its numbers in?

STEP and IGES store their unit (the readers convert to mm), DXF may: it is
preselected. Other files store none: meshes are preselected in metres, triangle CAD in
millimetres. The answer is remembered per file; the ✎ button left of the toolbar units
(or Info ▸ File unit) opens this sheet again.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QLayout, QVBoxLayout

from meshviewer.gui.widgets import Capsule

FILE_UNITS = (("mm", "mm"), ("cm", "cm"), ("m", "m"), ("in", "in"), ("ft", "ft"))


def default_unit(model):
    """The unit to preselect: the file's own, else m for meshes, mm for CAD."""
    if model.units:
        return model.units
    return "mm" if model.is_cad else "m"


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
                      "This file doesn't say. Change it any time with ✎ in the toolbar.")
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
