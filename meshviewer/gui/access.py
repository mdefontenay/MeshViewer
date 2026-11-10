"""Accessibility basics: what VoiceOver reads, and Increase Contrast.

    name_controls(window)   every switch and icon-only button gets a name VoiceOver can
                            read: its hover text, else the label next to it
    (Increase contrast: gui/style.py colors(), from gui/macos.increase_contrast())

Called when a window or a tool is built; a control that already has a name keeps it.
"""
from __future__ import annotations

from PySide6.QtWidgets import QAbstractButton, QFormLayout, QLabel, QLineEdit


def _from_tip(w):
    tip = (w.toolTip() or "").split("\n")[0]
    return tip.split("  (")[0].strip()              # "Fit View  (⌘0)" -> "Fit View"


def _from_label(w):
    """The QLabel just before w in its layout (a form row, or a row of widgets)."""
    parent = w.parentWidget()
    lay = parent.layout() if parent is not None else None
    if lay is None:
        return ""
    if isinstance(lay, QFormLayout):
        lab = lay.labelForField(w)
        if isinstance(lab, QLabel):
            return lab.text().rstrip(":")
    for i in range(lay.count()):
        item = lay.itemAt(i)
        if item.widget() is w:
            for j in range(i - 1, -1, -1):
                prev = lay.itemAt(j).widget()
                if isinstance(prev, QLabel) and prev.text():
                    return prev.text().rstrip(":")
            for j in range(i + 1, lay.count()):        # "[switch] Light and shadow"
                nxt = lay.itemAt(j).widget()
                if isinstance(nxt, QLabel) and nxt.text():
                    return nxt.text()
    return ""


def name_controls(root):
    n = 0
    for w in root.findChildren(QAbstractButton):
        if w.accessibleName() or (w.text() and w.text().strip()):
            continue
        if isinstance(w.parentWidget(), QLineEdit):    # a text field's ⊗ button
            w.setAccessibleName("Clear")
            continue
        name = _from_tip(w) or _from_label(w)
        if not name and getattr(w, "defaultAction", None) and w.defaultAction():
            name = w.defaultAction().text().replace("&", "")
        if name:
            w.setAccessibleName(name)
            n += 1
    return n
