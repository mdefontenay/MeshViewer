"""Screenshot sheet: image size + background (as shown on screen, or transparent).

v2.16: the Light / Dark / Custom backgrounds were removed — "As Shown" already
uses whatever background is set in Appearance."""
from __future__ import annotations

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QLayout,
    QVBoxLayout, QWidget,
)

from .widgets import Capsule, MenuSelect

BACKGROUNDS = (("current", "As Shown"), ("transparent", "Transparent"))


class ScreenshotDialog(QDialog):
    def __init__(self, parent, width, height):
        super().__init__(parent)
        self.setWindowTitle("Save Screenshot")
        self.setWindowModality(Qt.WindowModal)          # a sheet on macOS
        st = QSettings("local", "Mesh Viewer")

        lay = QVBoxLayout(self)
        lay.setSizeConstraint(QLayout.SetFixedSize)
        lay.setContentsMargins(20, 18, 20, 14)
        lay.setSpacing(12)
        title = QLabel("Save Screenshot")
        title.setStyleSheet("font-size: 15px; font-weight: 600;")
        lay.addWidget(title)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)

        self.size = MenuSelect()
        for k in (1, 2, 3, 4):
            self.size.addItem(f"{k}×   —   {width * k} × {height * k} px", k)
        self.size.setCurrentIndex(max(0, min(3, st.value("shot/scale", 2, type=int) - 1)))
        form.addRow("Resolution", self.size)

        bg_row = QWidget()
        bl = QHBoxLayout(bg_row)
        bl.setContentsMargins(0, 0, 0, 0)
        group = QActionGroup(self)
        self.bg_actions = {}
        for key, text in BACKGROUNDS:
            a = QAction(text, self)
            a.setCheckable(True)
            a.setData(key)
            group.addAction(a)
            self.bg_actions[key] = a
        bl.addWidget(Capsule(list(self.bg_actions.values()), name="Segmented"))
        bl.addStretch(1)
        form.addRow("Background", bg_row)
        lay.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Cancel | QDialogButtonBox.Save)
        buttons.button(QDialogButtonBox.Save).setText("Save…")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)
        self.save_button = buttons.button(QDialogButtonBox.Save)

        saved = st.value("shot/bg", "current")         # old "light" / "dark" / "custom" -> As Shown
        self.bg_actions.get(saved, self.bg_actions["current"]).setChecked(True)

    # ---- values ---------------------------------------------------------------
    @property
    def scale(self):
        return self.size.currentData()

    @property
    def background(self):
        return next(k for k, a in self.bg_actions.items() if a.isChecked())

    def _accept(self):
        st = QSettings("local", "Mesh Viewer")
        st.setValue("shot/scale", self.scale)
        st.setValue("shot/bg", self.background)
        self.accept()
