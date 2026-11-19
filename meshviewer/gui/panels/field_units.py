"""A field's units in a tool: Unit in file · Shown in (each ending with Custom…) and a
line saying what applies — for a contour (gui/panels/contour_editor.py) and a probe
(gui/panels/probe_editor.py). The choice belongs to the file, one per field, kept by
Contours (`ContoursPanel.unit_of`, `set_units`): Plots, Probe and Measure Selected show
values the same way.

    units = FieldUnits(card, lambda: contours_panel, lambda: field, grid, row)
    card_layout.addWidget(units.note)
    units.sync()                 the menus for the field now
"""
from __future__ import annotations

from PySide6.QtWidgets import QSizePolicy

from meshviewer.core.field_kinds import field_kind
from meshviewer.core.plots import COORD
from meshviewer.core.units import CUSTOM, NO_UNIT, QUANTITIES, QUANTITY_TITLES, is_custom
from meshviewer.gui.forms import _row, note
from meshviewer.gui.sheets import ask_text
from meshviewer.gui.widgets import MenuSelect

CUSTOM_ITEM = "__custom_unit__"                  # Custom… in a unit menu: type one


class FieldUnits:
    def __init__(self, owner, units, field, grid, row):
        """owner: the widget (sheets open on its window); units() -> the ContoursPanel;
        field() -> the field shown; its two rows go in `grid` from `row`."""
        self.owner, self.units, self.field = owner, units, field
        self.file_unit = MenuSelect()                  # what the file's numbers are in
        self.file_unit.setToolTip("Unit in File")
        self.shown_unit = MenuSelect()                 # what to show them in
        self.shown_unit.setToolTip("Shown In")
        for m in (self.file_unit, self.shown_unit):
            m.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            m.currentIndexChanged.connect(self._changed)
        self.rows = [_row(grid, row, "Unit in file", self.file_unit, wide=True)[0],
                     _row(grid, row + 1, "Shown in", self.shown_unit, wide=True)[0]]
        self.note = note()                             # what applies to this field's unit

    def sync(self):
        """The rows for the field: Unit in file only where there is a choice, Shown in
        once the file's unit is known, and a line saying what applies."""
        f, panel = self.field(), self.units()
        if f is None or panel is None:
            for w in (*self.rows, self.file_unit, self.shown_unit, self.note):
                w.setVisible(False)
            return
        q, fu, su = panel.unit_of(f)
        kind = field_kind(f)
        position = f.startswith(COORD)
        for m in (self.file_unit, self.shown_unit):
            m.blockSignals(True)
            m.clear()
        if position:
            text = (f"Positions are in the file's unit, {fu} (File ▸ File Unit…)." if fu else
                    "The file doesn't say its unit: set it with File ▸ File Unit….")
        elif kind is not None and kind.quantity is None:
            text = f"{kind.title} has no unit."
        else:
            if kind is not None:                      # its quantity's units (kinematic p:
                self.file_unit.addItem("—  As written", NO_UNIT)   # m²/s², as the file says)
                for k in QUANTITIES.get(q) or QUANTITIES[kind.quantity]:
                    self.file_unit.addItem(k, k)
            else:                                     # unknown: any unit, by quantity
                self.file_unit.addItem("—  No unit", NO_UNIT)
                for quantity, table in QUANTITIES.items():
                    self.file_unit.addSection(QUANTITY_TITLES[quantity])
                    for k in table:
                        self.file_unit.addItem(k, k)
            _add_custom(self.file_unit, fu)
            self.file_unit.setCurrentIndex(max(0, self.file_unit.findData(fu)))
            if q == CUSTOM:
                text = f"{fu} is a unit of your own: the values are shown as written."
            elif is_custom(su):
                text = f"Shown as written, labeled {su}."
            elif fu:
                text = ""
            elif kind is not None:
                text = ("As written in the file (solvers often write it non-dimensional). "
                        "Pick the unit it is in to show it in another.")
            else:
                text = ("Mesh Viewer doesn't know this field: pick its unit if it has one, "
                        "to show it in another.")
        choose = not position and (kind is None or kind.quantity is not None)
        self.rows[0].setVisible(choose)
        self.file_unit.setVisible(choose)
        for k in (QUANTITIES[q] if q in QUANTITIES and fu else [fu] if q == CUSTOM else ()):
            self.shown_unit.addItem(k, k)
        if q and fu:
            _add_custom(self.shown_unit, su if su != fu else None)
        self.shown_unit.setCurrentIndex(max(0, self.shown_unit.findData(su)))
        self.rows[1].setVisible(bool(q and fu))
        self.shown_unit.setVisible(bool(q and fu))
        self.note.setText(text)
        self.note.setVisible(bool(text))
        for m in (self.file_unit, self.shown_unit):
            m.blockSignals(False)

    def _changed(self, *_):
        f, panel = self.field(), self.units()
        if f is None or panel is None:
            return
        fu, su = self.file_unit.currentData(), self.shown_unit.currentData()
        if CUSTOM_ITEM in (fu, su):                     # Custom…: type one (a sheet)
            which = "file" if fu == CUSTOM_ITEM else "shown"
            sheet = ask_text(self.owner.window(), "Custom Unit", "Unit", "",
                             lambda text: self.set_custom(which, text))
            sheet.rejected.connect(self.sync)           # Cancel: as it was
            return
        panel.set_units(f, fu, su)

    def set_custom(self, which, text):
        """A unit typed for this file: the one its numbers are in ("file") or the one
        they are labeled with ("shown")."""
        f, panel, text = self.field(), self.units(), (text or "").strip()
        if f is None or panel is None or not text:
            self.sync()
            return
        _q, fu, _su = panel.unit_of(f)
        if which == "file":
            panel.set_units(f, text, NO_UNIT)
        else:
            panel.set_units(f, fu, text)


def _add_custom(menu, unit):
    """The unit typed for this file (if it is one), then Custom…, under a line."""
    menu.addSection("")
    if is_custom(unit):
        menu.addItem(unit, unit)
    menu.addItem("Custom…", CUSTOM_ITEM)
