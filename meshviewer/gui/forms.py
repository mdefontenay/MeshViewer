"""Form helpers shared by the sidebar panels and dialogs: a label, the 4-column grid
(label · field · unit · "?") and its rows, a link-style button, a caption, a divider
line and one-of-many buttons."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QPushButton, QSizePolicy

from meshviewer.gui.widgets import Capsule, UnitField


def _label(text, name=None):
    lab = QLabel(text)
    if name:
        lab.setObjectName(name)
    return lab


def _grid():
    g = QGridLayout()
    g.setContentsMargins(0, 0, 0, 0)
    g.setHorizontalSpacing(6)
    g.setVerticalSpacing(5)
    g.setColumnStretch(1, 1)
    g.setColumnMinimumWidth(0, QLabel("Sound speed").sizeHint().width())  # groups align
    g.setColumnMinimumWidth(2, 38)               # unit column, same in both groups
    g.setColumnMinimumWidth(3, 16)               # "?" column
    return g


def _row(g, r, text, widget, unit=None, extra=None, wide=False):
    """Label, field, unit, "?" -> (label, unit label). a UnitField puts its
    unit menu in the unit columns; wide = the field spans them (no unit)."""
    lab = QLabel(text)
    g.addWidget(lab, r, 0)
    g.addWidget(widget, r, 1, 1, 3 if wide else 1)
    u = None
    if isinstance(widget, UnitField):
        g.addWidget(widget.menu, r, 2, 1, 2)
        u = widget.menu
    elif unit:
        u = _label(unit, "AxisLabel")
        g.addWidget(u, r, 2)
    if extra is not None:
        g.addWidget(extra, r, 3)
    return lab, u


def _link(text, tip, slot):
    b = QPushButton(text)
    b.setObjectName("LinkButton")
    b.setFlat(True)
    b.setCursor(Qt.PointingHandCursor)
    b.setToolTip(tip)
    b.clicked.connect(slot)
    return b


def caption(text):
    """A small grey title over a group of controls."""
    return _label(text, "Caption")


def rule():
    """A thin line between two groups of controls."""
    line = QFrame()
    line.setObjectName("Divider")
    line.setFixedHeight(1)
    return line


def segmented(parent, items, slot=None, expand=False):
    """One-of-many buttons in a capsule -> ({key: action}, the capsule).
    items: (key, text) or (key, text, tooltip); slot(key) is called on a click;
    expand: the buttons share the whole width."""
    group = QActionGroup(parent)
    group.setExclusive(True)
    actions = {}
    for key, text, *tip in items:
        a = QAction(text, parent)
        a.setCheckable(True)
        a.setData(key)
        a.setToolTip(tip[0] if tip else "")
        if slot is not None:
            a.triggered.connect(lambda _=False, k=key: slot(k))
        group.addAction(a)
        actions[key] = a
    capsule = Capsule(list(actions.values()), name="Segmented")
    if expand:
        for w in (capsule, *capsule.buttons):
            w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    return actions, capsule
