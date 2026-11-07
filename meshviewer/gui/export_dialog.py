"""NEW (v2.8): Export sheet — pick the file format (only those that fit the
open file), whether hidden parts are left out, then where to save.
v2.14 (CAD files): a second tab, "CFD settings" — the inflation layers of CFD mode
for OpenFOAM / Fluent / STAR-CCM+ / Pointwise, or every input and value as a CSV.

    [ 3D model | CFD settings ]
    Format   [ STL — binary …          ▾ ]        Settings for [ OpenFOAM …  ▾ ]
"""
from __future__ import annotations

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QLayout,
    QVBoxLayout, QWidget,
)

from ..cfd_export import FORMATS as CFD_FORMATS
from ..export import FORMATS
from .widgets import Capsule, MenuSelect, Switch

CFD_NOTES = {
    "openfoam": "The addLayersControls block of snappyHexMeshDict: first layer thickness, "
                "expansion ratio and number of layers for your wall patch.",
    "fluent": "The fields of Add Boundary Layers in Fluent Meshing (uniform offset).",
    "starccm": "The fields of the Prism Layer Mesher: layers, stretching, total and "
               "near-wall thickness.",
    "pointwise": "The T-Rex fields: wall spacing, growth rate, max layers.",
    "csv": "Every input and computed value (flow, layers, y+ along the flow), then one "
           "row per layer. Opens in Excel / Numbers.",
}


class ExportDialog(QDialog):
    def __init__(self, parent, keys, has_hidden=False, has_volume=False, edited=False,
                 renamed=False, cfd=None):
        """cfd (v2.14): None (no CFD tab) or {"on": CFD mode on and filled in}."""
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
        head = QHBoxLayout()
        head.addWidget(title)
        head.addStretch(1)
        self.cfd = cfd
        self.tabs = {}
        if cfd is not None:                              # v2.14: 3D model | CFD settings
            group = QActionGroup(self)
            group.setExclusive(True)
            for key, text in (("model", "3D model"), ("cfd", "CFD settings")):
                a = QAction(text, self)
                a.setCheckable(True)
                a.triggered.connect(lambda _=False, k=key: self._show(k))
                group.addAction(a)
                self.tabs[key] = a
            head.addWidget(Capsule(list(self.tabs.values()), name="Segmented"))
        lay.addLayout(head)

        self.model_box = QWidget()
        mb = QVBoxLayout(self.model_box)
        mb.setContentsMargins(0, 0, 0, 0)
        mb.setSpacing(12)
        lay.addWidget(self.model_box)
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
        mb.addLayout(form)

        self.note = QLabel()
        self.note.setObjectName("InfoLine")
        self.note.setWordWrap(True)
        self.note.setMaximumWidth(380)
        mb.addWidget(self.note)
        self.edited = edited
        self.renamed = renamed
        self._update_note()

        # ---- v2.14: CFD settings ---------------------------------------------------------
        self.cfd_box = QWidget()
        cb = QVBoxLayout(self.cfd_box)
        cb.setContentsMargins(0, 0, 0, 0)
        cb.setSpacing(12)
        cform = QFormLayout()
        cform.setLabelAlignment(Qt.AlignRight)
        cform.setHorizontalSpacing(12)
        self.cfd_format = MenuSelect()
        for k, (text, _) in CFD_FORMATS.items():
            self.cfd_format.addItem(text, k)
        last = st.value("export/cfd_format", "openfoam")
        self.cfd_format.setCurrentIndex(max(0, self.cfd_format.findData(last)))
        self.cfd_format.currentIndexChanged.connect(self._update_cfd_note)
        cform.addRow("Settings for", self.cfd_format)
        cb.addLayout(cform)
        self.cfd_note = QLabel()
        self.cfd_note.setObjectName("InfoLine")
        self.cfd_note.setWordWrap(True)
        self.cfd_note.setMaximumWidth(380)
        cb.addWidget(self.cfd_note)
        lay.addWidget(self.cfd_box)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Save)
        self.save_btn = buttons.button(QDialogButtonBox.Save)
        self.save_btn.setText("Export…")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)
        self._show(st.value("export/what", "model") if cfd is not None else "model")

    @property
    def fmt(self):
        return self.format.currentData()

    @property
    def what(self):
        """v2.14: "model" or "cfd"."""
        return "cfd" if self.cfd is not None and self.tabs["cfd"].isChecked() else "model"

    @property
    def cfd_fmt(self):
        return self.cfd_format.currentData()

    def _show(self, key):
        key = key if key in ("model", "cfd") and self.cfd is not None else "model"
        if self.tabs:
            self.tabs[key].setChecked(True)
        self.model_box.setVisible(key == "model")
        self.cfd_box.setVisible(key == "cfd")
        self._update_cfd_note()

    def _update_cfd_note(self, *_):
        if self.cfd is None:
            return
        on = bool(self.cfd.get("on"))
        text = CFD_NOTES.get(self.cfd_fmt, "")
        if not on:
            text = "Switch on CFD mode in the sidebar and fill in the flow and the layers first."
        self.cfd_note.setText(text)
        self.save_btn.setEnabled(on or self.what == "model")

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
        st = QSettings("local", "Mesh Viewer")
        st.setValue("export/format", self.fmt)
        if self.cfd is not None:
            st.setValue("export/what", self.what)
            st.setValue("export/cfd_format", self.cfd_fmt)
        self.accept()
