"""View ▸ Customize Toolbar… (also on a right-click on the toolbar): which groups of
buttons the toolbar shows. A sheet; the choice is for every window
(settings "toolbar/hidden"). Everything stays in the menus either way.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QLabel, QLayout, QPushButton, QVBoxLayout,
)

from meshviewer.gui.store import settings

# key, what the user sees — in toolbar order
ITEMS = (
    ("sidebar", "Sidebar"),
    ("views", "Views: Fit, Isometric, X, Y, Z, Perspective"),
    ("show", "Show (edges, faces, axes, grid…)"),
    ("units", "Units"),
    ("export", "Export"),
    ("screenshot", "Screenshot"),
    ("settings", "Settings"),
    ("inspector", "Inspector"),
)
DEFAULT_HIDDEN = ("settings",)


def hidden_items():
    v = settings().value("toolbar/hidden", None)
    if v is None:
        return set(DEFAULT_HIDDEN)
    if isinstance(v, str):                       # QSettings gives one item as a str
        v = [v] if v else []
    return {k for k in v if k in dict(ITEMS)}


def set_hidden_items(keys):
    keys = [k for k, _ in ITEMS if k in set(keys)]
    settings().setValue("toolbar/hidden", keys or "")


class CustomizeToolbar(QDialog):
    changed = Signal()                           # a box ticked: the toolbars follow

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("Customize Toolbar")
        self.setWindowModality(Qt.WindowModal)   # a sheet on macOS
        lay = QVBoxLayout(self)
        lay.setSizeConstraint(QLayout.SetFixedSize)
        lay.setContentsMargins(20, 18, 20, 14)
        lay.setSpacing(8)
        title = QLabel("Show in the toolbar")
        title.setStyleSheet("font-size: 15px; font-weight: 600;")
        lay.addWidget(title)
        hidden = hidden_items()
        self.boxes = {}
        for key, text in ITEMS:
            b = QCheckBox(text)
            b.setChecked(key not in hidden)
            b.toggled.connect(self._save)
            self.boxes[key] = b
            lay.addWidget(b)
        note = QLabel("Everything is in the menus too.")
        note.setObjectName("InfoLine")
        lay.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        self.restore = QPushButton("Restore Defaults")
        buttons.addButton(self.restore, QDialogButtonBox.ResetRole)
        self.restore.clicked.connect(self._defaults)
        buttons.accepted.connect(self.accept)
        lay.addWidget(buttons)

    def _defaults(self):
        for key, b in self.boxes.items():
            b.blockSignals(True)
            b.setChecked(key not in DEFAULT_HIDDEN)
            b.blockSignals(False)
        self._save()

    def _save(self, *_):
        set_hidden_items([k for k, b in self.boxes.items() if not b.isChecked()])
        self.changed.emit()
