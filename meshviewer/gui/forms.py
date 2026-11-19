"""Form pieces shared by the tools (right sidebar), pages and sheets — one look for each
kind of thing:

    inputs      _grid / _row        label · field · unit · "?" (4 columns, groups align)
                pair                two fields on one row:  [a] word │ [b] word
                xyz_fields          X / Y / Z boxes under their letters (Origin, Normal)
                switch_row          a label, the switch at the right
                segmented           one-of-many buttons in a capsule
                button / buttons    plain buttons in a capsule (Flip, Clear, Undo | Reset)
                link                a link-style button (Zoom, Pick…, Back to Auto Length)
    groups      caption             a small gray title over a group
                group_head          that title with buttons at the right (Formulas, Values)
                rule                a thin line between two groups
    read-outs   readout_grid / readout   gray key · value (right, selectable) · note
                note                a gray line that wraps (off, empty or what applies)
                set_state           ok / warn / bad color of a note; status_mark: ✓ / ⚠
    sheets      sheet_title         the bold title on top of a sheet
    pages       PAGE_MARGINS        around a page under the 3D view (title: #PageTitle)

A tool's own column: `column(widget)` (no margins: the tool's card pads it).
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import (
    QGridLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from meshviewer.gui.style import STATUS
from meshviewer.gui.widgets import Capsule, UnitField
from meshviewer.gui.widgets.basics import rule  # noqa: F401  (part of the forms set)

SPACING = 6                    # between the rows of a tool
PAGE_MARGINS = (22, 18, 22, 18)    # a page under the 3D view (Inflation Layers, a plot)


def _label(text, name=None):
    lab = QLabel(text)
    if name:
        lab.setObjectName(name)
    return lab


def column(widget, spacing=SPACING):
    """The vertical layout of a tool, a group or a card's content: no margins."""
    lay = QVBoxLayout(widget)
    lay.setContentsMargins(0, 0, 0, 0)
    lay.setSpacing(spacing)
    return lay


# ---- inputs ---------------------------------------------------------------------------

def _grid():
    g = QGridLayout()
    g.setContentsMargins(0, 0, 0, 0)
    g.setHorizontalSpacing(6)
    g.setVerticalSpacing(5)
    g.setColumnStretch(1, 1)
    g.setColumnMinimumWidth(0, label_width())    # groups align
    g.setColumnMinimumWidth(2, 38)               # unit column, same in both groups
    g.setColumnMinimumWidth(3, 16)               # "?" column
    return g


def label_width():
    """The label column of every form grid (as wide as its longest usual label)."""
    return QLabel("Sound speed").sizeHint().width()


def _row(g, r, text, widget, unit=None, extra=None, wide=False, align=None):
    """Label, field, unit, "?" -> (label, unit label). a UnitField puts its
    unit menu in the unit columns; wide = the field spans them (no unit);
    align: the field keeps its size (a capsule), Qt.AlignLeft."""
    lab = QLabel(text)
    g.addWidget(lab, r, 0)
    if align is not None:
        g.addWidget(widget, r, 1, 1, 3 if wide else 1, align)
    else:
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


def pair(a, a_word, b, b_word):
    """Two fields in one row: [a] word │ [b] word (Mach / Speed, Layers / Rate)."""
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(4)
    h.addWidget(a, 1)
    if a_word:
        h.addWidget(_label(a_word, "AxisLabel"))
    h.addWidget(_label("│", "AxisLabel"))
    h.addWidget(b, 1)
    if b_word:
        h.addWidget(_label(b_word, "AxisLabel"))
    return w


def xyz_fields(rows, top=2):
    """X / Y / Z boxes under their letters, a row per (label, [3 boxes], tip), the labels
    in the form grid's label column. -> the widget (to put under a grid row)."""
    w = QWidget()
    g = QGridLayout(w)
    g.setContentsMargins(0, top, 0, 0)
    g.setHorizontalSpacing(4)
    g.setVerticalSpacing(4)
    g.setColumnMinimumWidth(0, label_width())
    for c, axis in enumerate("XYZ", start=1):
        lbl = _label(axis, "AxisLabel")
        lbl.setAlignment(Qt.AlignCenter)
        g.addWidget(lbl, 0, c)
        g.setColumnStretch(c, 1)
    for r, (text, boxes, tip) in enumerate(rows, start=1):
        lbl = QLabel(text)
        lbl.setToolTip(tip)
        g.addWidget(lbl, r, 0)
        for c, box in enumerate(boxes, start=1):
            box.setToolTip(tip)
            box.setMinimumWidth(40)
            g.addWidget(box, r, c)
    return w


def show_z(widget, on):
    """xyz_fields' Z column shown or hidden (a 2D file: X / Y only)."""
    g = widget.layout()
    for r in range(g.rowCount()):
        item = g.itemAtPosition(r, 3)
        if item is not None and item.widget() is not None:
            item.widget().setVisible(on)


def switch_row(text, switch, tip=None):
    """A label with its switch at the right -> the row (a widget, to hide; .label)."""
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    lab = QLabel(text)
    if tip:
        lab.setToolTip(tip)
        if not switch.toolTip():
            switch.setToolTip(tip)
    if not switch.accessibleName():
        switch.setAccessibleName(text)
    h.addWidget(lab)
    h.addStretch(1)
    h.addWidget(switch)
    w.label = lab
    return w


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


def button(parent, text, slot=None, tip=""):
    """A plain (not checkable) action, for `buttons`."""
    a = QAction(text, parent)
    a.setToolTip(tip)
    if slot is not None:
        a.triggered.connect(slot)
    return a


def buttons(*actions):
    """Plain buttons side by side in one capsule (Flip · Clear · Undo | Reset)."""
    return Capsule(list(actions), name="Segmented")


def link(text, tip, slot):
    """A link-style button: an action in passing (Zoom, Pick…, Back to Auto Length)."""
    b = QPushButton(text)
    b.setObjectName("LinkButton")
    b.setFlat(True)
    b.setCursor(Qt.PointingHandCursor)
    b.setToolTip(tip)
    b.clicked.connect(slot)
    return b


_link = link


# ---- groups ---------------------------------------------------------------------------

def caption(text):
    """A small gray title over a group of controls."""
    return _label(text, "Caption")


def group_head(title, *widgets):
    """A gray title over a group, its buttons (Formulas, Values, a capsule) on the right."""
    h = QHBoxLayout()
    h.setContentsMargins(0, 4, 0, 0)
    h.setSpacing(10)
    h.addWidget(caption(title))
    h.addStretch(1)
    for b in widgets:
        h.addWidget(b)
    return h


# ---- read-outs ------------------------------------------------------------------------

def note(text="", selectable=False):
    """A gray line that wraps: a tool that is off, an empty state, what applies."""
    lab = _label(text, "InfoLine")
    lab.setWordWrap(True)
    if selectable:
        lab.setTextInteractionFlags(Qt.TextSelectableByMouse)
    return lab


def readout_grid():
    """A grid of computed numbers: gray key · value, for `readout`."""
    g = QGridLayout()
    g.setContentsMargins(0, 0, 0, 0)
    g.setHorizontalSpacing(10)
    g.setVerticalSpacing(3)
    g.setColumnStretch(1, 1)
    return g


def readout(g, r, key, value="—", with_note=False):
    """A computed number at row r: gray key, value on the right (selectable); with_note:
    a gray line under it (row r + 1). -> (key, value, note or None)."""
    k = _label(key, "AxisLabel")
    v = _label(value, "ValueLabel")
    v.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    v.setWordWrap(True)
    v.setTextInteractionFlags(Qt.TextSelectableByMouse)
    g.addWidget(k, r, 0, Qt.AlignTop)
    g.addWidget(v, r, 1)
    n = None
    if with_note:
        n = note()
        n.setAlignment(Qt.AlignRight)
        g.addWidget(n, r + 1, 0, 1, 2)
    return k, v, n


def set_state(label, state=None):
    """Color a note by its state: "ok", "warn", "bad", or None (gray)."""
    if label.property("state") != (state or ""):
        label.setProperty("state", state or "")
        label.style().unpolish(label)
        label.style().polish(label)


def status_mark(ok, warn_mark="⚠"):
    """✓ (green) or ⚠ (orange), for a rich-text note."""
    if ok:
        return f"<span style='color:{STATUS['ok']}'>✓</span>"
    return f"<span style='color:{STATUS['warn']}'>{warn_mark}</span>"


# ---- sheets ---------------------------------------------------------------------------

def sheet_title(text):
    """The bold title on top of a sheet (Export, Screenshot, File Unit, New Plot…)."""
    return _label(text, "SheetTitle")
