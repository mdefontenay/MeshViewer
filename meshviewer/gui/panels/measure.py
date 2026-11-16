"""The Measure tool. Measuring is on while the tool is open.
Distance (two points; "From origin": one point from (0, 0, 0)) · Angle · Area (and volume)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from meshviewer.core.units import fmt
from meshviewer.gui.forms import _label, button, buttons, column, note, segmented, switch_row
from meshviewer.gui.widgets import Switch
from meshviewer.render.measure import AXIS_COLORS


class MeasurePanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.measure = None
        lay = column(self)

        # "Area & Volume" is just "Area" (both are shown)
        tips = ("Click two points: the distance and ΔX, ΔY, ΔZ between them.\n"
                "From origin: one point, its X / Y / Z and distance from (0, 0, 0)",
                "Click two faces: the angle between them",
                "Click parts (or CAD faces): area, and volume when they close up")
        modes, cap = segmented(self, [(k, t, tip) for (k, t), tip in zip(
            (("distance", "Distance"), ("angle", "Angle"), ("area", "Area")), tips)],
            self._mode)
        self.mode_actions = list(modes.values())
        self.mode_actions[0].setChecked(True)
        lay.addWidget(cap)

        # Distance: snap, from origin. Area: what a click picks.
        self.snap = Switch()
        self.snap.toggled.connect(lambda on: self.measure and setattr(self.measure, "snap", on))
        self.snap_row = switch_row("Snap to vertices", self.snap)
        lay.addWidget(self.snap_row)

        self.from_origin = Switch()                       # distance from (0, 0, 0)
        self.from_origin.toggled.connect(
            lambda on: self.measure and self.measure.set_from_origin(on))
        self.origin_row = switch_row(
            "From origin", self.from_origin,
            "Each click is one point: its X / Y / Z and its distance from (0, 0, 0)")
        lay.addWidget(self.origin_row)

        picks, cap = segmented(self, [("parts", "Parts"), ("faces", "CAD faces")], self._pick)
        self.pick_actions = list(picks.values())
        self.pick_actions[0].setChecked(True)
        self.pick_row = QWidget()
        pr = QHBoxLayout(self.pick_row)
        pr.setContentsMargins(0, 0, 0, 0)
        pr.addWidget(QLabel("Pick"))
        pr.addStretch(1)
        pr.addWidget(cap)
        lay.addWidget(self.pick_row)

        # ---- result card --------------------------------------------------------
        self.card = QFrame()
        self.card.setObjectName("ResultCard")
        self.card_lay = QVBoxLayout(self.card)
        self.card_lay.setContentsMargins(12, 10, 12, 10)
        self.card_lay.setSpacing(2)
        lay.addWidget(self.card)
        self._card_widgets = []

        self.units_note = note()
        lay.addWidget(self.units_note)

        clear = button(self, "Clear", lambda: self.measure and self.measure.clear())
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(buttons(clear))
        lay.addLayout(row)
        self._mode_widgets("distance")

    # ---- binding ---------------------------------------------------------------
    def bind(self, scene):
        self.measure = scene.measure
        self.measure.on_changed = self.show_result
        self._has_faces = scene.model.source is not None    # exact CAD: face picking
        self.measure.from_origin = self.from_origin.isChecked()
        self.mode_actions[1].setToolTip(
            "Click two lines (or cell edges): the angle between them" if scene.model.dim == 2
            else "Click two faces: the angle between them")
        snap = "Snap to edges" if scene.model.dim == 2 else "Snap to vertices"
        self.snap_row.label.setText(snap)                 # 2D: lines and their ends
        self.snap.setAccessibleName(snap)
        self._mode_widgets(next(a.data() for a in self.mode_actions if a.isChecked()))
        self.show_result(self.measure.result())

    def activate(self, on):
        """Section opened (on) or closed (off)."""
        if not self.measure:
            return
        if on:
            self._mode(next(a.data() for a in self.mode_actions if a.isChecked()))
        else:
            self.measure.set_mode("off")

    # ---- handlers ----------------------------------------------------------------
    def _mode_widgets(self, mode):
        self.pick_row.setVisible(mode == "area" and getattr(self, "_has_faces", False))
        self.snap_row.setVisible(mode == "distance")
        self.origin_row.setVisible(mode == "distance")

    def _mode(self, mode):
        self._mode_widgets(mode)
        if self.measure:
            self.measure.set_mode(mode)

    def _pick(self, key):
        if self.measure:
            self.measure.set_pick_faces(key == "faces")

    # ---- result card ----------------------------------------------------------------
    def _clear_card(self):
        for w in self._card_widgets:
            w.setParent(None)
        self._card_widgets = []

    def _add(self, w):
        self.card_lay.addWidget(w)
        self._card_widgets.append(w)
        return w

    def _headline(self, caption, value, tag=None, muted=False):
        top = QWidget()
        h = QHBoxLayout(top)
        h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(_label(caption, "Caption"))
        h.addStretch(1)
        if tag:
            h.addWidget(_label(tag, "Tag"))
        self._add(top)
        big = _label(value, "MutedValue" if muted else "BigValue")
        big.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._add(big)

    def _xyz_grid(self, rows, u):
        grid_w = QWidget()
        g = QGridLayout(grid_w)
        g.setContentsMargins(0, 4, 0, 0)
        g.setHorizontalSpacing(8)
        g.setVerticalSpacing(3)
        for row, ((name, v), color) in enumerate(zip(rows, AXIS_COLORS)):
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {color}; font-size: 10px;")
            val = _label(fmt(v, u), "ValueLabel")
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            val.setTextInteractionFlags(Qt.TextSelectableByMouse)
            g.addWidget(dot, row, 0)
            g.addWidget(_label(name, "AxisLabel"), row, 1)
            g.addWidget(val, row, 2)
        g.setColumnStretch(2, 1)
        self._add(grid_w)

    def _units_note(self, r):
        u, fu = r.get("units", ""), r.get("file_units", "")
        if not fu and not u:
            text = "No units in this file — values are in the model's own units."
        elif not fu:
            text = f"No units in this file — taken as {u}."
        elif not u:
            text = f"Shown without units (the file is in {fu})."
        else:
            text = ""
        self.units_note.setText(text)
        self.units_note.setVisible(bool(text))

    def show_result(self, r):
        self._clear_card()
        self._units_note(r)
        u = r.get("units", "")
        if r.get("mode") == "distance":
            pts = r.get("points", [])
            if "distance" in r:                                   # two points
                self._headline("Distance", fmt(r["distance"], u), tag="between the points")
                self._xyz_grid([("ΔX", r["dx"]), ("ΔY", r["dy"]), ("ΔZ", r["dz"])], u)
            elif "xyz" in r:                                      # one point
                self._headline("From origin", fmt(r["from_origin"], u), tag="from (0, 0, 0)")
                self._xyz_grid([("X", r["xyz"][0]), ("Y", r["xyz"][1]), ("Z", r["xyz"][2])], u)
                if "to_plane" in r:
                    spacer = QWidget()
                    spacer.setFixedHeight(6)
                    self._add(spacer)
                    side = "on the cut-away side" if r["to_plane"] > 0 else "on the shown side"
                    self._headline("To section plane", fmt(r["to_plane"], u), tag=side)
            else:
                self._headline("Distance", "—", tag=f"{len(pts)} / 2 points", muted=True)
        elif r.get("mode") == "angle":
            what = "lines" if r.get("lines") else "faces"
            if "planes" not in r:
                self._headline("Angle", "—", tag=f"{r['n']} / 2 {what}", muted=True)
                return
            self._headline("Angle", f"{r['planes']:.2f}°", tag=f"between the {what}")
            other = "directions" if r.get("lines") else "normals"
            self._add(note(f"Between their {other}: {r['normals']:.2f}°", selectable=True))
        elif r.get("mode") == "area":
            if not r.get("count"):
                self._headline("Area", "—", tag="nothing selected", muted=True)
                return
            src = lambda exact: "exact" if exact else "from mesh"     # noqa: E731
            sq, cu = (f"{u}²", f"{u}³") if u else ("", "")
            what = r["what"]
            if r["count"] == 1:                                  # "1 face", "1 boundary"
                what = what[:-3] + "y" if what.endswith("ies") else what.rstrip("s")
            on = f' on {r["n_parts"]} parts' if what.startswith("face") and r.get("n_parts", 1) > 1 else ""
            sel = _label(f'{r["count"]} {what}{on} selected', "SelectionCount")
            sel.setContentsMargins(0, 0, 0, 6)
            self._add(sel)
            self._headline("Area", fmt(r["area"], sq), tag=src(r["area_exact"]))
            spacer = QWidget()
            spacer.setFixedHeight(6)
            self._add(spacer)
            if r["closed"]:
                self._headline("Volume", fmt(r["volume"], cu), tag=src(r["volume_exact"]))
            else:
                self._headline("Volume", "Not closed", muted=True)
        else:
            self._headline("Measure", "—", muted=True)
