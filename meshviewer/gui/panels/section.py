"""The Section tool: on/off, then

    Plane
               Normal to [ X | Y | Z ] [ ✎ ]        [ Flip ]
               Origin    [x] [y] [z]     (✎ Edit Plane: the exact plane, any direction)
               Normal    [x] [y] [z]
               Position  ───●───────            [ Center ]
    Show       Fill cut faces · Show plane

laid out like a section plot (panels/plots.py) so the two read the same."""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QWidget

from meshviewer.gui.forms import (
    _grid, button, buttons, caption, column, note, rule, segmented, switch_row, xyz_fields,
)
from meshviewer.gui.widgets import NoWheelSlider, SpinField, Switch

SLIDER_STEPS = 1000
CAPS_DELAY_MS = 150      # recompute the filled cut this long after the last change


def edit_plane_action(parent):
    """The ✎ button right of X | Y | Z (Section, section plots): shows the plane's
    origin and normal under Normal to, to set it exactly, in any direction."""
    from meshviewer.gui.icons import icon
    a = QAction(icon("pencil"), "Edit Plane", parent)
    a.setCheckable(True)
    a.setToolTip("Edit Plane")
    return a


def _spin(lo, hi, step):
    s = SpinField(lo, hi, 3)
    s.setSingleStep(step)
    s.setKeyboardTracking(False)          # update on Enter / focus out, not each keystroke
    s.setMinimumWidth(56)
    return s


class SectionPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.section = None
        self._caps_timer = QTimer(self, singleShot=True, interval=CAPS_DELAY_MS)
        self._caps_timer.timeout.connect(self._update_caps)

        lay = column(self)

        # On/off switch: shown in the collapsible header by the sidebar.
        self.enable = Switch()
        self.enable.setToolTip("Cut the model with a plane")
        self.enable.toggled.connect(self._enable)
        self.hint = note("Off — switch on to cut the model with a plane.")
        lay.addWidget(self.hint)

        # ---- details (only shown when the section is on) -----------------
        # Same layout as a section plot: Plane (normal to, position), then the
        # exact numbers, then what is shown.
        self.details = QWidget()
        d = column(self.details)

        d.addWidget(caption("Plane"))
        g = _grid()
        axes, cap = segmented(self, [(i, axis, f"Normal along +{axis}, through the center")
                                     for i, axis in enumerate("XYZ")], self._axis)
        next(iter(axes.values())).actionGroup().setExclusionPolicy(
            QActionGroup.ExclusionPolicy.ExclusiveOptional)
        self.axis_actions = list(axes.values())
        flip = button(self, "Flip", lambda: self._do(lambda s: s.flip()), "Show the other half")
        center = button(self, "Center", lambda: self._do(lambda s: s.set_plane(origin=s.center)),
                        "Move the plane to the model center")
        self.edit_plane = edit_plane_action(self)        # ✎: origin and normal, any way
        row = QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(cap)
        row.addWidget(buttons(self.edit_plane))
        row.addStretch(1)
        row.addWidget(buttons(flip))
        g.addWidget(QLabel("Normal to"), 0, 0)
        g.addLayout(row, 0, 1, 1, 3)
        self.slider = NoWheelSlider(Qt.Horizontal)
        self.slider.setRange(-SLIDER_STEPS // 2, SLIDER_STEPS // 2)
        self.slider.setToolTip("Slide the plane along its normal")
        self.slider.valueChanged.connect(self._slid)
        row = QHBoxLayout()
        row.setSpacing(6)
        row.addWidget(self.slider, 1)
        row.addWidget(buttons(center))
        g.addWidget(QLabel("Position"), 2, 0)
        g.addLayout(row, 2, 1, 1, 3)

        self.origin = [_spin(-1e9, 1e9, 1.0) for _ in range(3)]
        # any length (not rescaled to 1): only the direction matters
        self.normal = [_spin(-1e9, 1e9, 0.1) for _ in range(3)]
        self.advanced = xyz_fields((     # the exact plane, any direction
            ("Origin", self.origin, "A point on the plane"),
            ("Normal", self.normal, "Direction the plane faces — that half is hidden")))
        for box in self.origin + self.normal:
            box.valueChanged.connect(self._typed)
        self.advanced.setVisible(False)
        self.edit_plane.toggled.connect(self.advanced.setVisible)
        g.addWidget(self.advanced, 1, 0, 1, 4)     # right under Normal to
        d.addLayout(g)
        d.addWidget(rule())

        d.addWidget(caption("Show"))
        self.fill = Switch()
        self.fill.toggled.connect(self._fill_toggled)
        self.handle = Switch(True)
        self.handle.toggled.connect(lambda on: self.section and self.section.set_handle(on))
        self._labels = {}
        for text, sw, tip in (("Fill cut faces", self.fill, "Solid color on the cut"),
                              ("Show plane", self.handle,
                               "Show the plane; drag it or its arrow in the 3D view")):
            row = switch_row(text, sw, tip)
            self._labels[sw] = row.label
            d.addWidget(row)

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
        for box, v in zip(self.origin + self.normal, [*s.origin, *s.normal_raw]):
            box.blockSignals(True)
            box.setValue(float(v))
            box.blockSignals(False)
        self.slider.blockSignals(True)
        self.slider.setValue(int(round(s.offset / s.diag * SLIDER_STEPS)))
        self.slider.blockSignals(False)
        n = np.asarray(s.normal, dtype=float)
        n = n / (np.linalg.norm(n) or 1.0)
        for k, act in enumerate(self.axis_actions):       # X / Y / Z lit when it is one
            act.setChecked(bool(abs(abs(n[k]) - 1.0) < 1e-9))

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
        """Mesh files with volume cells fill the cut with the cut cells;
        their edges follow the Mesh edges toggle. Same label either way."""
        if self.section and self.section.has_volume:
            tip = ("Fill the cut with the volume cells the plane goes through.\n"
                   "Their edges show when Mesh Edges (toolbar) is on.\n"
                   "The cells are read from the file the first time.")
        else:
            tip = "Solid color on the cut"
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
        self.sync()
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
