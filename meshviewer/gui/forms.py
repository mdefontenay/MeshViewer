"""Form helpers shared by the sidebar panels: a label, the 4-column grid
(label · field · unit · "?") and its rows, a link-style button."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QLabel, QPushButton

from meshviewer.gui.widgets import UnitField


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
