"""Side-panel block for the cross-section: on/off, origin, normal, position."""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractSpinBox, QApplication, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout,
    QWidget,
)

from .widgets import Capsule, NoWheelSlider, NoWheelSpinBox, Switch

SLIDER_STEPS = 1000
CAPS_DELAY_MS = 150      # recompute the filled cut this long after the last change


def _spin(lo, hi, step, decimals):
    s = NoWheelSpinBox()
    s.setRange(lo, hi)
    s.setSingleStep(step)
    s.setDecimals(decimals)
    s.setButtonSymbols(QAbstractSpinBox.NoButtons)
    s.setAlignment(Qt.AlignRight)
    s.setKeyboardTracking(False)          # update on Enter / focus out, not each keystroke
    s.setMinimumWidth(56)
    return s


class SectionPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.section = None
        self._caps_timer = QTimer(self, singleShot=True, interval=CAPS_DELAY_MS)
        self._caps_timer.timeout.connect(self._update_caps)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        # On/off switch: shown in the collapsible header by the sidebar.
        self.enable = Switch()
        self.enable.setToolTip("Cut the model with a plane")
        self.enable.toggled.connect(self._enable)
        self.hint = QLabel("Off — switch on to cut the model with a plane.")
        self.hint.setObjectName("InfoLine")
        self.hint.setWordWrap(True)
        lay.addWidget(self.hint)

        # ---- details (only shown when the section is on) -----------------
        self.details = QWidget()
        d = QVBoxLayout(self.details)
        d.setContentsMargins(2, 0, 4, 0)
        d.setSpacing(8)

        grid = QGridLayout()
        grid.setHorizontalSpacing(4)
        grid.setVerticalSpacing(4)
        for c, axis in enumerate("XYZ", start=1):
            lbl = QLabel(axis)
            lbl.setObjectName("AxisLabel")
            lbl.setAlignment(Qt.AlignCenter)
            grid.addWidget(lbl, 0, c)
        self.origin = [_spin(-1e9, 1e9, 1.0, 3) for _ in range(3)]
        self.normal = [_spin(-1.0, 1.0, 0.1, 3) for _ in range(3)]
        for row, (label, boxes, tip) in enumerate((
                ("Origin", self.origin, "A point on the plane"),
                ("Normal", self.normal, "Direction the plane faces — that half is hidden"))):
            lbl = QLabel(label)
            lbl.setToolTip(tip)
            grid.addWidget(lbl, row + 1, 0)
            for c, box in enumerate(boxes, start=1):
                box.setToolTip(tip)
                box.valueChanged.connect(self._typed)
                grid.addWidget(box, row + 1, c)
        d.addLayout(grid)

        pos = QHBoxLayout()
        pos.addWidget(QLabel("Position"))
        self.slider = NoWheelSlider(Qt.Horizontal)
        self.slider.setRange(-SLIDER_STEPS // 2, SLIDER_STEPS // 2)
        self.slider.setToolTip("Slide the plane along its normal")
        self.slider.valueChanged.connect(self._slid)
        pos.addWidget(self.slider, 1)
        d.addLayout(pos)

        btns = QHBoxLayout()
        btns.setSpacing(6)
        axis_actions, tool_actions = [], []
        for text, tip, fn, bucket in (
                ("X", "Normal along +X, through the centre", lambda: self._axis(0), axis_actions),
                ("Y", "Normal along +Y, through the centre", lambda: self._axis(1), axis_actions),
                ("Z", "Normal along +Z, through the centre", lambda: self._axis(2), axis_actions),
                ("Flip", "Show the other half", lambda: self._do(lambda s: s.flip()), tool_actions),
                ("Center", "Move the plane to the model centre",
                 lambda: self._do(lambda s: s.set_plane(origin=s.center)), tool_actions)):
            a = QAction(text, self)
            a.setToolTip(tip)
            a.triggered.connect(fn)
            bucket.append(a)
        btns.addWidget(Capsule(axis_actions, name="Segmented"))
        btns.addStretch(1)
        btns.addWidget(Capsule(tool_actions, name="Segmented"))
        d.addLayout(btns)

        self.fill = Switch()
        self.fill.toggled.connect(self._fill_toggled)
        self.handle = Switch(True)
        self.handle.toggled.connect(lambda on: self.section and self.section.set_handle(on))
        self._labels = {}
        for text, sw, tip in (("Fill cut faces", self.fill, "Solid colour on the cut"),
                              ("Show plane", self.handle,
                               "Show the plane; drag it or its arrow in the 3D view")):
            row = QHBoxLayout()
            lbl = QLabel(text)
            lbl.setToolTip(tip)
            self._labels[sw] = lbl
            row.addWidget(lbl)
            row.addStretch(1)
            row.addWidget(sw)
            d.addLayout(row)

        lay.addWidget(self.details)
        self.details.setVisible(False)

    # ---- binding ------------------------------------------------------------
    def bind(self, section):
        self.section = section
        section.on_widget_moved = lambda *_: (self.sync(), self._caps_later())
        step = section.diag / 200
        for box in self.origin:
            box.setSingleStep(step)
            box.setDecimals(max(0, min(4, int(np.ceil(-np.log10(step))) + 1)))
        Switch.set_silently(self.enable, section.enabled)
        Switch.set_silently(self.fill, section.fill)
        self._sync_fill_label()
        Switch.set_silently(self.handle, section.show_handle)
        self.details.setVisible(section.enabled)
        self.hint.setVisible(not section.enabled)
        self.sync()

    def sync(self):
        """Copy the plane's current values into the boxes and slider."""
        s = self.section
        if s is None:
            return
        for box, v in zip(self.origin + self.normal, [*s.origin, *s.normal]):
            box.blockSignals(True)
            box.setValue(float(v))
            box.blockSignals(False)
        self.slider.blockSignals(True)
        self.slider.setValue(int(round(s.offset / s.diag * SLIDER_STEPS)))
        self.slider.blockSignals(False)

    # ---- handlers -----------------------------------------------------------
    def _enable(self, on):
        self.details.setVisible(on)
        self.hint.setVisible(not on)
        if self.section:
            # Clip instantly; fill the cut a moment later so the switch feels immediate.
            self.section.set_enabled(on, caps=False)
            self.sync()
            if on:
                self._caps_later()

    def _sync_fill_label(self):
        """Mesh files with volume cells fill the cut with the cut cells (v2.19);
        their edges follow Display ▸ Mesh edges (v2.21). Same label either way."""
        if self.section and self.section.has_volume:
            tip = ("Fill the cut with the volume cells the plane goes through.\n"
                   "Their edges show when Display ▸ Mesh edges is on.\n"
                   "The cells are read from the file the first time.")
        else:
            tip = "Solid colour on the cut"
        self._labels[self.fill].setToolTip(tip)

    def _fill_toggled(self, on):
        if self.section:
            self.section.set_fill(on, caps=False)
            self._update_caps()              # busy cursor: may read the volume cells

    def _typed(self, *_):
        if not self.section:
            return
        o = [b.value() for b in self.origin]
        n = [b.value() for b in self.normal]
        self.section.set_plane(origin=o, normal=n, caps=False)
        self.sync()                         # shows the normalised normal
        self._caps_later()

    def _slid(self, v):
        if not self.section:
            return
        self.section.set_offset(v / SLIDER_STEPS * self.section.diag, caps=False)
        self.sync()
        self._caps_later()

    def _axis(self, i):
        n = np.zeros(3)
        n[i] = 1.0
        self._do(lambda s: s.set_plane(origin=s.center, normal=n))

    def _do(self, fn):
        if self.section:
            fn(self.section)
            self.sync()

    def _update_caps(self):
        if not self.section:
            return
        QApplication.setOverrideCursor(Qt.BusyCursor)
        try:
            self.section.update_caps()
        finally:
            QApplication.restoreOverrideCursor()
        self._sync_fill_label()

    def _caps_later(self):
        self._caps_timer.start()
