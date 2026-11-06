"""NEW (v2.8): Export sheet — pick the file format (only those that fit the
open file), whether hidden parts are left out, then where to save."""
from __future__ import annotations

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QLayout,
    QVBoxLayout, QWidget,
)

from ..export import FORMATS
from .widgets import MenuSelect, Switch


class ExportDialog(QDialog):
    def __init__(self, parent, keys, has_hidden=False, has_volume=False, edited=False,
                 renamed=False):
        super().__init__(parent)
        self.setWindowTitle("Export")
        self.setWindowModality(Qt.WindowModal)          # a sheet on macOS
        self.has_volume = has_volume
        st = QSettings("local", "Mesh Viewer")

        lay = QVBoxLayout(self)
        lay.setSizeConstraint(QLayout.SetFixedSize)
        lay.setContentsMargins(20, 18, 20, 14)
        lay.setSpacing(12)
        title = QLabel("Export")
        title.setStyleSheet("font-size: 15px; font-weight: 600;")
        lay.addWidget(title)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)
        self.format = MenuSelect()
        for k in keys:
            self.format.addItem(FORMATS[k][0], k)
        last = st.value("export/format", keys[0])
        self.format.setCurrentIndex(max(0, keys.index(last)) if last in keys else 0)
        self.format.currentIndexChanged.connect(self._update_note)
        form.addRow("Format", self.format)

        self.visible_only = Switch(True)
        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.addWidget(self.visible_only)
        hint = QLabel("leave hidden parts out")
        hint.setObjectName("InfoLine")
        rl.addWidget(hint)
        rl.addStretch(1)
        self.visible_row_label = QLabel("Visible only")
        form.addRow(self.visible_row_label, row)
        self.visible_row_label.setVisible(has_hidden)
        row.setVisible(has_hidden)
        lay.addLayout(form)

        self.note = QLabel()
        self.note.setObjectName("InfoLine")
        self.note.setWordWrap(True)
        self.note.setMaximumWidth(380)
        lay.addWidget(self.note)
        self.edited = edited
        self.renamed = renamed
        self._update_note()

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Save)
        buttons.button(QDialogButtonBox.Save).setText("Export…")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

    @property
    def fmt(self):
        return self.format.currentData()

    def _update_note(self, *_):
        k = self.fmt
        if k in ("vtu", "ugrid"):
            text = ("With the volume cells and the boundaries."
                    if self.has_volume else "Boundaries only (this file has no volume cells).")
            if k == "ugrid":
                text += " Boundary names go in the .mapbc beside it (BC types set to 0)."
        elif k == "obj":
            text = "Surfaces only. Part colours go in the .mtl beside it."
        elif k == "ply":
            text = "Surfaces only, with the part colours."
        else:
            text = "Surfaces only."
        done = [w for w, on in (("edits", self.edited), ("new part names", self.renamed)) if on]
        if done:
            text += f" Includes your {' and '.join(done)}."
        self.note.setText(text)

    def _accept(self):
        QSettings("local", "Mesh Viewer").setValue("export/format", self.fmt)
        self.accept()
