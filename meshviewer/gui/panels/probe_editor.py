"""One probe of the Probe tool (gui/panels/probes.py): its fold-out, on a card.

    ▾ Probe 1                                         (eye: its marker in 3D)
      ┌──────────────────────────────────────────────┐
      │ WHERE                                         │
      │ Point · volume cell 1,204                     │   what it probes
      │        X        Y        Z                    │
      │ Point [ 0.3 ] [ 0.5 ] [ 0.5 ]                 │   point: typed (no Z in 2D)
      │ [ Select Vertex Point ]                       │   the next click on a vertex
      │ Follow Select ▾                     (switch)  │   each pick moves it
      │ ──────────────────────────────────────────── │
      │ VALUES                                        │   several time steps:
      │ Field        [ Pressure p              ▾ ]    │     Field ▸ submenus, its units
      │ Unit in file [ m²/s²                   ▾ ]    │
      │ At this step               2.875 m²/s²        │     (line / area: Min, Max)
      │ [ Show Plot | Export CSV… ]                   │     the plot: a tab under the view
      │ ─ or, one step: every field ───────────────── │   one step (.dat, .msh):
      │ Pressure p                 2.875 m²/s²        │     each field's value (line /
      │ …                                             │     area: the weighted mean,
      │ [ Copy Values | Export CSV… ]                 │     min … max)
      └──────────────────────────────────────────────┘
                                    [ Rename… | Delete ]

The editor writes its probe's dict (`p`) and tells the panel, which finds the cells,
reads the time steps and fills the numbers back in (`show_values`).
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

from meshviewer.core.plots import COORD
from meshviewer.core.units import nice_num
from meshviewer.gui.access import name_controls
from meshviewer.gui.forms import (_grid, _row, button, buttons, group_head, note, readout,
                                  readout_grid, rule, show_z, switch_row, xyz_fields)
from meshviewer.gui.panels.contour_editor import field_label, grouped
from meshviewer.gui.panels.field_units import FieldUnits
from meshviewer.gui.widgets import MenuSelect, NumberField, Switch


class ProbeEditor(QWidget):
    changed = Signal()                    # its target or field: find / read again

    def __init__(self, panel, p):
        super().__init__()
        self.panel, self.p = panel, p
        self._rows = []                   # the readout's widgets (made again each time)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 2, 0, 2)
        lay.setSpacing(6)
        card = QFrame()
        card.setObjectName("ResultCard")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(8, 9, 8, 10)
        cl.setSpacing(6)
        lay.addWidget(card)

        # -- where
        cl.addLayout(group_head("Where"))
        self.where = note()
        cl.addWidget(self.where)
        self.xyz = [NumberField() for _ in range(3)]
        for box in self.xyz:
            box.valueChanged.connect(self._typed)
        self.xyz_row = xyz_fields([("Point", self.xyz, "A point in the model: the cell "
                                    "holding it is probed")])
        cl.addWidget(self.xyz_row)
        self.pick = button(self, "Select Vertex Point",
                           lambda: self.panel.pick_vertex(p["id"]), "Select Vertex Point")
        g = _grid()
        g.addWidget(buttons(self.pick), 0, 0, 1, 4)
        cl.addLayout(g)
        self.pick_note = note("Click a vertex in the 3D view.")
        cl.addWidget(self.pick_note)
        self.follow = Switch()
        self.follow.toggled.connect(lambda on: self.panel.set_following(p["id"], on))
        cl.addWidget(switch_row("Follow Select ▾", self.follow,
                                "Each pick in the 3D view moves this probe"))
        cl.addWidget(rule())

        # -- values
        cl.addLayout(group_head("Values"))
        g = _grid()
        self.field = MenuSelect()
        self.field.cascade = True                      # Flow ▸, Pressure ▸ …
        self.field.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.field.setToolTip("Field")
        self.field.currentIndexChanged.connect(self._field_changed)
        self._field_row = _row(g, 0, "Field", self.field, wide=True)[0]
        self.units = FieldUnits(self, lambda: self.panel.units, lambda: self.p.get("field"),
                                g, 1)
        cl.addLayout(g)
        cl.addWidget(self.units.note)
        self.values = readout_grid()
        cl.addLayout(self.values)
        self.status = note()
        cl.addWidget(self.status)
        self.show_plot = button(self, "Show Plot", lambda: self.panel.show_probe.emit(p["id"]),
                                "Show Plot")
        self.copy = button(self, "Copy Values", lambda: self.panel.copy_values(p["id"]),
                           "Copy Values")
        self.export = button(self, "Export CSV…", lambda: self.panel.export_csv(p["id"]),
                             "Export CSV…")
        self.series_buttons = buttons(self.show_plot, self.export)
        self.static_buttons = buttons(self.copy, button(
            self, "Export CSV…", lambda: self.panel.export_csv(p["id"]), "Export CSV…"))
        row = QHBoxLayout()
        row.addWidget(self.series_buttons)
        row.addWidget(self.static_buttons)
        row.addStretch(1)
        cl.addLayout(row)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        bottom.addWidget(buttons(
            button(self, "Rename…", lambda: self.panel.rename(p["id"])),
            button(self, "Delete", lambda: self.panel.remove(p["id"]),
                   "Delete this probe (and its plot)")))
        lay.addLayout(bottom)
        self.sync()
        name_controls(self)

    # ---- from the probe's dict to the widgets ----------------------------------------------
    @property
    def timed(self):
        return self.panel.time_count() > 1

    def sync(self):
        p, t = self.p, self.p.get("target") or {}
        self.where.setText(self.panel.describe(p))
        point = t.get("kind", "point") == "point"
        self.xyz_row.setVisible(point)
        xyz = self.panel.marker_point(p["id"]) if t.get("how") != "xyz" else t.get("xyz")
        for k, box in enumerate(self.xyz):
            box.blockSignals(True)
            box.setValue(None if xyz is None else float(xyz[k]))
            box.blockSignals(False)
        show_z(self.xyz_row, not (self.panel.scene is not None and
                                  self.panel.scene.model.dim == 2))   # (no Z on a 2D file)
        Switch.set_silently(self.follow, self.panel.following == p["id"])
        picking = self.panel.picking is not None and self.panel.picking[0] == p["id"]
        self.pick.setText("Cancel" if picking else "Select Vertex Point")
        self.pick.setToolTip(self.pick.text())
        self.pick_note.setVisible(picking)
        self.field.blockSignals(True)
        self.field.clear()
        for title, group in grouped([f for f in self.panel.fields()
                                     if not f.startswith(COORD)]):
            self.field.addSection(title)
            for f in group:
                self.field.addItem(field_label(f), f)
        i = self.field.findData(p.get("field"))
        self.field.setCurrentIndex(i if i >= 0 else 0)
        p["field"] = self.field.currentData()
        self.field.blockSignals(False)
        timed = self.timed
        for w in (self._field_row, self.field, self.series_buttons):
            w.setVisible(timed)
        self.static_buttons.setVisible(not timed)
        if timed:
            self.units.sync()
        else:
            for w in (*self.units.rows, self.units.file_unit, self.units.shown_unit,
                      self.units.note):
                w.setVisible(False)

    def show_values(self, rows, why=""):
        """rows: [(label, (mean, min, max) or None, unit)] — the field at this step (several
        steps) or every field (one); a line or an area adds min … max."""
        spread = (self.p.get("target") or {}).get("kind") in ("line", "area")
        texts = []
        for label, v, unit in rows:
            if v is None:
                text = "—"
            else:
                u = f" {unit}" if unit else ""
                text = f"{nice_num(v[0])}{u}"
                if spread and v[1] != v[2]:
                    text += f"\n{nice_num(v[1])} … {nice_num(v[2])}"
            texts.append((label, text))
        keys = [label for label, _t in texts]
        if keys == [w.text() for w in self._rows[0::2]]:      # the same rows: new numbers
            for w, (_label, text) in zip(self._rows[1::2], texts):
                w.setText(text)
        else:
            for w in self._rows:                       # (gone now, not when Qt gets to it)
                w.hide()
                w.setParent(None)
                w.deleteLater()
            self._rows = []
            for r, (label, text) in enumerate(texts):
                a, b, _ = readout(self.values, r, label, text)
                self._rows += [a, b]
        self.status.setText(why)
        self.status.setVisible(bool(why))

    # ---- handlers -----------------------------------------------------------------------------
    def _typed(self, *_):
        vals = [box.value() for box in self.xyz]
        if self.panel.scene is not None and self.panel.scene.model.dim == 2:
            vals[2] = 0.0 if vals[2] is None else vals[2]
        if any(v is None for v in vals):
            return
        self.p["target"] = {"kind": "point", "how": "xyz", "xyz": [float(v) for v in vals]}
        self.changed.emit()

    def _field_changed(self, *_):
        self.p["field"] = self.field.currentData()
        self.units.sync()
        self.changed.emit()


def values_text(rows):
    """Tab-separated lines (Copy Values): label, mean, min, max, unit."""
    out = []
    for label, v, unit in rows:
        nums = ["", "", ""] if v is None else [f"{float(x):.10g}" for x in v]
        out.append("\t".join([label, *nums, unit or ""]))
    return "\n".join(out)
