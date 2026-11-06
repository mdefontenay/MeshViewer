"""Edit section of the sidebar (v2.23; v2.24 move / undo / original; v2.26 laid
out as a small table: one row per axis, a column per kind of change).

    Pivot   [    Origin    |    Centre    ]      what Rotate and Mirror turn about
             Rotate                  Mirror
    X       [ −90° | +90° | 180° ]  [x → −x]
    Y       [ −90° | +90° | 180° ]  [y → −y]
    Z       [ −90° | +90° | 180° ]  [z → −z]
    Move    [X 0] [Y 0] [Z 0]       [ Move ]
    Show original edges                (switch)
    Last: …                      [ Undo | Reset ]

Exact CAD (STEP, IGES, BREP) only shows a grey note instead.
"""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import (
    QAbstractSpinBox, QGridLayout, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget,
)

from .. import transform as xf
from .widgets import Capsule, NoWheelSpinBox, Switch

SIDE_WIDTH = 60          # the Mirror / Move column


class _Distance(NoWheelSpinBox):
    """Move distance shown without trailing zeros ("X 0", "X 2.5"), so it fits."""

    def textFromValue(self, v):
        t = f"{v:.{self.decimals()}f}".rstrip("0").rstrip(".")
        return "0" if t in ("", "-0") else t


def _info(text=""):
    lab = QLabel(text)
    lab.setObjectName("InfoLine")
    lab.setWordWrap(True)
    return lab


def _wide(actions, width=None):
    """A capsule that fills its cell, every button the same width."""
    c = Capsule(actions, name="Segmented")
    c.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    if width:
        c.setFixedWidth(width)
    for b in c.buttons:
        b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    return c


def _header(text):
    lab = QLabel(text)
    lab.setObjectName("AxisLabel")
    lab.setAlignment(Qt.AlignCenter)
    return lab


def _action(parent, text, tip, slot=None, checkable=False):
    a = QAction(text, parent)
    a.setToolTip(tip)
    a.setCheckable(checkable)
    if slot is not None:
        a.triggered.connect(slot)
    return a


class EditPanel(QWidget):
    edit_requested = Signal(object, object, str)   # R (3×3 int), t (3 floats), label
    undo_requested = Signal()
    reset_requested = Signal()
    original_toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        self.unsupported = _info()                 # exact CAD: just a note
        lay.addWidget(self.unsupported)

        self.tools = QWidget()
        self.tools.setObjectName("EditTools")       # tighter button padding (style.py)
        g = QGridLayout(self.tools)
        g.setContentsMargins(2, 0, 2, 0)
        g.setHorizontalSpacing(6)
        g.setVerticalSpacing(5)
        g.setColumnStretch(1, 1)
        lay.addWidget(self.tools)

        # Pivot (shared by Rotate and Mirror)
        pg = QActionGroup(self)
        pg.setExclusive(True)
        self.pivot = {
            "origin": _action(self, "Origin", "Rotate and mirror about (0, 0, 0)", checkable=True),
            "centre": _action(self, "Centre", "Rotate and mirror about the model's centre",
                              checkable=True)}
        for a in self.pivot.values():
            pg.addAction(a)
        self.pivot["origin"].setChecked(True)
        lab = QLabel("Pivot")
        lab.setToolTip("What Rotate and Mirror turn about")
        g.addWidget(lab, 0, 0)
        g.addWidget(_wide(list(self.pivot.values())), 0, 1, 1, 2)
        g.setRowMinimumHeight(1, 4)                # a little air under Pivot

        # Table: a row per axis — Rotate (3 buttons) | Mirror
        g.addWidget(_header("Rotate"), 2, 1)
        g.addWidget(_header("Mirror"), 2, 2)
        self.turns, self.mirrors = {}, {}
        for row, k in enumerate("xyz", start=3):
            K = k.upper()
            lab = QLabel(K)
            lab.setToolTip(f"Rotate about {K}, or mirror along {K}")
            g.addWidget(lab, row, 0)
            acts = []
            for deg, text in ((-90, "−90°"), (90, "+90°"), (180, "180°")):
                a = _action(self, text, f"Rotate {text} about {K} (right-hand rule)",
                            lambda _=False, kk=k, d=deg: self._rotate(kk, d))
                acts.append(a)
                self.turns[(k, deg)] = a
            g.addWidget(_wide(acts), row, 1)
            self.mirrors[k] = _action(self, f"{k} → −{k}", f"Mirror along {K}: {k} becomes −{k}",
                                      lambda _=False, kk=k: self._mirror(kk))
            g.addWidget(_wide([self.mirrors[k]], SIDE_WIDTH), row, 2)

        # Move: three distances in the Rotate column, the button in the Mirror column
        g.setRowMinimumHeight(6, 4)
        boxes = QWidget()
        bl = QHBoxLayout(boxes)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(3)
        self.move = []
        for k in "xyz":
            b = _Distance()
            b.setRange(-1e9, 1e9)
            b.setDecimals(3)
            b.setPrefix(f"{k.upper()} ")
            b.setButtonSymbols(QAbstractSpinBox.NoButtons)
            b.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            b.setMinimumWidth(40)
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            b.setToolTip(f"Distance along {k.upper()}")
            self.move.append(b)
            bl.addWidget(b)
        self.move_label = QLabel("Move")
        g.addWidget(self.move_label, 7, 0)
        g.addWidget(boxes, 7, 1)
        self.move_go = _action(self, "Move", "Move the model by these distances", self._translate)
        g.addWidget(_wide([self.move_go], SIDE_WIDTH), 7, 2)

        # Compare with the file + history (same section: no divider, v2.26)
        self.original = Switch()
        self.original.setToolTip("Grey feature edges of the file as it was opened, to compare")
        self.original.toggled.connect(self.original_toggled.emit)
        orow = QHBoxLayout()
        orow.setContentsMargins(2, 2, 2, 0)
        self.original_label = QLabel("Show original edges")
        orow.addWidget(self.original_label)
        orow.addStretch(1)
        orow.addWidget(self.original)
        lay.addLayout(orow)

        self.status = _info("No changes")
        self.undo = _action(self, "Undo", "Undo the last change", self.undo_requested.emit)
        self.reset = _action(self, "Reset", "Back to the file as opened", self.reset_requested.emit)
        srow = QHBoxLayout()
        srow.setContentsMargins(2, 0, 2, 0)
        srow.addWidget(self.status, 1)
        self.undo_capsule = Capsule([self.undo, self.reset], name="Segmented")   # like Clear
        srow.addWidget(self.undo_capsule)
        lay.addLayout(srow)
        self.refresh()

    # ---- binding / state ------------------------------------------------------------
    def bind(self, scene):
        self.scene = scene
        m = scene.model
        ok = m.editable
        for w in (self.tools, self.original, self.original_label, self.status,
                  self.undo_capsule):
            w.setVisible(ok)
        self.unsupported.setVisible(not ok)
        self.unsupported.setText(
            "" if ok else f"Editing isn't available for {m.fmt} files: they hold exact CAD "
                          f"geometry. Export as STL, open that file, and edit it.")
        step = 10 ** np.floor(np.log10(max(scene.section.diag, 1e-9) / 20))
        for b in self.move:
            b.setSingleStep(float(step))
            b.setValue(0.0)
        unit = m.units or "file units"
        self.move_label.setToolTip(f"Distances in {unit}")
        for b in self.move:
            b.setToolTip(f"Distance along {b.prefix().strip()} ({unit})")
        Switch.set_silently(self.original, scene.state.get("original", False))
        self.refresh()

    def refresh(self):
        """Last change text + which buttons work."""
        sc = self.scene
        edited = bool(sc and sc.model.edited)
        self.undo.setEnabled(bool(sc and sc.last_edit))
        self.reset.setEnabled(edited)
        self.status.setText(f"Last: {sc.last_edit}" if edited and sc.last_edit
                            else ("Edited" if edited else "No changes"))

    # ---- actions ----------------------------------------------------------------------
    def _emit(self, r, label):
        t = np.zeros(3)
        if self.pivot["centre"].isChecked() and self.scene is not None:
            b = np.asarray(self.scene.model_bounds(), dtype=float).reshape(3, 2)
            r, t = xf.about(r, b.mean(axis=1))
            label += " (centre)"
        self.edit_requested.emit(r, t, label)

    def _rotate(self, k, deg):
        text = "180°" if abs(deg) == 180 else f"{'+' if deg > 0 else '−'}90°"
        self._emit(xf.rotation(k, deg), f"rotate {text} about {k.upper()}")

    def _mirror(self, k):
        self._emit(xf.mirror(k), f"mirror {k} → −{k}")

    def _translate(self):
        t = np.array([b.value() for b in self.move], dtype=float)
        if not np.any(t):
            return
        unit = f" {self.scene.model.units}" if self.scene and self.scene.model.units else ""
        self.edit_requested.emit(xf.identity(), t,
                                 "move " + ", ".join(f"{v:g}" for v in t) + unit)
        for b in self.move:
            b.setValue(0.0)
