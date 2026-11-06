"""Edit section of the sidebar (v2.8; v2.8.1 move / undo / original; v2.8.4 laid
out like Onshape's Transform: choose the kind, fill it in, Apply).

    Transform  [ Rotate               ▾ ]     Rotate · Mirror · Move by X, Y, Z
    Axis       [  X  |  Y  |  Z  ]            (Rotate, Mirror)
    Angle      [                90° ]         (Rotate: any angle)
    Pivot      [ Origin | Centre ]            (Rotate, Mirror)
    X / Y / Z  [            0 mm ]            (Move)
    [                 Apply                ]
    Changes (2)                 [ Undo | Reset ]
      1  Rotate 90° about Z
      2  Move 10, 0, 0 mm
    Show original edges                (switch)

Exact CAD (STEP, IGES, BREP) only shows a grey note instead.
"""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import (
    QAbstractSpinBox, QGridLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout,
    QWidget,
)

from .. import transform as xf
from .widgets import Capsule, MenuSelect, NoWheelSpinBox, Switch

KINDS = (("rotate", "Rotate"), ("mirror", "Mirror"), ("move", "Move by X, Y, Z"))
HISTORY_SHOWN = 8          # older changes fold into "… n earlier"


class _Number(NoWheelSpinBox):
    """Value shown without trailing zeros ("90°", "2.5 mm")."""

    def textFromValue(self, v):
        t = f"{v:.{self.decimals()}f}".rstrip("0").rstrip(".")
        return "0" if t in ("", "-0") else t


def _number(lo, hi, decimals, suffix=""):
    b = _Number()
    b.setRange(lo, hi)
    b.setDecimals(decimals)
    b.setSuffix(suffix)
    b.setButtonSymbols(QAbstractSpinBox.NoButtons)
    b.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    return b


def _info(text=""):
    lab = QLabel(text)
    lab.setObjectName("InfoLine")
    lab.setWordWrap(True)
    return lab


def _segmented(parent, items, tips):
    group = QActionGroup(parent)
    group.setExclusive(True)
    acts = {}
    for key, text in items:
        a = QAction(text, parent)
        a.setCheckable(True)
        a.setToolTip(tips.get(key, ""))
        group.addAction(a)
        acts[key] = a
    c = Capsule(list(acts.values()), name="Segmented")
    c.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    for b in c.buttons:
        b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    next(iter(acts.values())).setChecked(True)
    return acts, c


class EditPanel(QWidget):
    edit_requested = Signal(object, object, str)   # R (3×3), t (3 floats), label
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

        # ---- the transform being set up -------------------------------------------
        self.tools = QWidget()
        g = QGridLayout(self.tools)
        g.setContentsMargins(2, 0, 2, 0)
        g.setHorizontalSpacing(8)
        g.setVerticalSpacing(6)
        g.setColumnStretch(1, 1)
        lay.addWidget(self.tools)
        self._rows = {}                            # key -> (label, widget), shown per kind

        def row(key, label, widget, tip=""):
            r = g.rowCount()
            lab = QLabel(label)
            lab.setToolTip(tip)
            if tip and not widget.toolTip():
                widget.setToolTip(tip)
            g.addWidget(lab, r, 0)
            g.addWidget(widget, r, 1)
            self._rows[key] = (lab, widget)

        self.kind = MenuSelect()
        for key, text in KINDS:
            self.kind.addItem(text, key)
        self.kind.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.kind.currentIndexChanged.connect(self._kind_changed)
        row("kind", "Transform", self.kind)

        self.axis, w = _segmented(self, (("x", "X"), ("y", "Y"), ("z", "Z")), {})
        for a in self.axis.values():
            a.toggled.connect(lambda _on: self._update_hint())
        row("axis", "Axis", w)

        self.angle = _number(-360, 360, 3, "°")
        self.angle.setValue(90)
        self.angle.setToolTip("Any angle; positive turns follow the right-hand rule "
                              "(thumb along +axis)")
        row("angle", "Angle", self.angle)

        self.pivot, w = _segmented(self, (("origin", "Origin"), ("centre", "Centre")),
                                   {"origin": "Turn / mirror about (0, 0, 0)",
                                    "centre": "Turn / mirror about the model's centre"})
        row("pivot", "Pivot", w)

        self.move = []
        for k in "xyz":
            b = _number(-1e9, 1e9, 6)
            self.move.append(b)
            row(f"move_{k}", k.upper(), b, f"Distance along {k.upper()}")

        self.hint = _info()                        # what Mirror does, in words
        g.addWidget(self.hint, g.rowCount(), 1)

        self.apply = QPushButton("Apply")
        self.apply.setObjectName("ApplyButton")
        self.apply.setCursor(Qt.PointingHandCursor)
        self.apply.setToolTip("Apply this transform (Return in a box does the same)")
        self.apply.clicked.connect(self._apply)
        lay.addWidget(self.apply)
        for b in (self.angle, *self.move):
            b.lineEdit().returnPressed.connect(self._apply)

        # ---- what has been done ---------------------------------------------------
        hrow = QHBoxLayout()
        hrow.setContentsMargins(2, 4, 2, 0)
        self.history_title = QLabel("Changes")
        self.history_title.setObjectName("AxisLabel")
        hrow.addWidget(self.history_title, 1)
        self.undo = QAction("Undo", self)
        self.undo.setToolTip("Undo the last change")
        self.undo.triggered.connect(self.undo_requested.emit)
        self.reset = QAction("Reset", self)
        self.reset.setToolTip("Back to the file as opened")
        self.reset.triggered.connect(self.reset_requested.emit)
        self.undo_capsule = Capsule([self.undo, self.reset], name="Segmented")   # like Clear
        hrow.addWidget(self.undo_capsule)
        self.history_head = QWidget()
        self.history_head.setLayout(hrow)
        lay.addWidget(self.history_head)

        self.history = QWidget()
        self.history_lay = QVBoxLayout(self.history)
        self.history_lay.setContentsMargins(4, 0, 2, 0)
        self.history_lay.setSpacing(2)
        lay.addWidget(self.history)
        self.status = _info("No changes yet")      # also the empty list
        self.history_lay.addWidget(self.status)
        self._history_rows = []

        self.original = Switch()
        self.original.setToolTip("Grey feature edges of the file as it was opened, to compare")
        self.original.toggled.connect(self.original_toggled.emit)
        orow = QHBoxLayout()
        orow.setContentsMargins(2, 2, 2, 0)
        self.original_label = QLabel("Show original edges")
        orow.addWidget(self.original_label)
        orow.addStretch(1)
        orow.addWidget(self.original)
        self.original_row = QWidget()
        self.original_row.setLayout(orow)
        lay.addWidget(self.original_row)

        self._kind_changed()
        self.refresh()

    # ---- binding / state ------------------------------------------------------------
    def bind(self, scene):
        self.scene = scene
        m = scene.model
        ok = m.editable
        for w in (self.tools, self.apply, self.history_head, self.history, self.original_row):
            w.setVisible(ok)
        self.unsupported.setVisible(not ok)
        self.unsupported.setText(
            "" if ok else f"Editing isn't available for {m.fmt} files: they hold exact CAD "
                          f"geometry. Export as STL, open that file, and edit it.")
        step = 10 ** np.floor(np.log10(max(scene.section.diag, 1e-9) / 20))
        unit = f" {m.units}" if m.units else ""
        for k, b in zip("XYZ", self.move):
            b.setSingleStep(float(step))
            b.setSuffix(unit)
            b.setValue(0.0)
            b.setToolTip(f"Distance along {k} ({m.units or 'file units'})")
        Switch.set_silently(self.original, scene.state.get("original", False))
        self.refresh()

    @property
    def current_kind(self):
        return self.kind.currentData()

    def _kind_changed(self, *_):
        k = self.current_kind
        show = {"kind": True, "axis": k in ("rotate", "mirror"), "angle": k == "rotate",
                "pivot": k in ("rotate", "mirror"),
                **{f"move_{a}": k == "move" for a in "xyz"}}
        for key, (lab, w) in self._rows.items():
            lab.setVisible(show[key])
            w.setVisible(show[key])
        self._update_hint()

    def _axis_key(self):
        return next(k for k, a in self.axis.items() if a.isChecked())

    def _update_hint(self):
        a = self._axis_key()
        plane = {"x": "YZ", "y": "XZ", "z": "XY"}[a]
        self.hint.setText(f"{a} becomes −{a} (mirror across the {plane} plane)")
        self.hint.setVisible(self.current_kind == "mirror")

    def refresh(self):
        """Changes list + which buttons work."""
        sc = self.scene
        labels = sc.edit_labels if sc is not None else []
        edited = bool(sc and sc.model.edited)
        self.undo.setEnabled(bool(labels))
        self.reset.setEnabled(edited)
        self.history_title.setText(f"Changes ({len(labels)})" if labels else "Changes")
        for w in self._history_rows:
            self.history_lay.removeWidget(w)
            w.hide()
            w.deleteLater()
        self._history_rows = []
        self.status.setVisible(not labels)
        shown = labels[-HISTORY_SHOWN:]
        first = len(labels) - len(shown)
        if first:
            self._add_history_row(f"… {first} earlier")
        for i, text in enumerate(shown, start=first + 1):
            self._add_history_row(f"{i}   {text}")

    def _add_history_row(self, text):
        lab = QLabel(text)
        lab.setObjectName("HistoryLine")
        lab.setWordWrap(True)
        self.history_lay.addWidget(lab)
        self._history_rows.append(lab)

    # ---- Apply ------------------------------------------------------------------------
    def _apply(self):
        k = self.current_kind
        if k == "move":
            self._translate()
            return
        axis = self._axis_key()
        if k == "rotate":
            deg = float(self.angle.value())
            if deg % 360 == 0:
                return
            r, label = xf.rotation(axis, deg), f"Rotate {self.angle.textFromValue(deg)}° " \
                                                f"about {axis.upper()}"
        else:
            r, label = xf.mirror(axis), f"Mirror {axis} → −{axis}"
        t = np.zeros(3)
        if self.pivot["centre"].isChecked() and self.scene is not None:
            b = np.asarray(self.scene.model_bounds(), dtype=float).reshape(3, 2)
            r, t = xf.about(r, b.mean(axis=1))
            label += " (centre)"
        self.edit_requested.emit(r, t, label)

    def _translate(self):
        t = np.array([b.value() for b in self.move], dtype=float)
        if not np.any(t):
            return
        unit = f" {self.scene.model.units}" if self.scene and self.scene.model.units else ""
        self.edit_requested.emit(xf.identity(), t,
                                 "Move " + ", ".join(f"{v:g}" for v in t) + unit)
        for b in self.move:
            b.setValue(0.0)
