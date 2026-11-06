"""Side-panel block for measurements. Measuring is on while this section is open.
v2.9: Distance · Point · Angle · Area (and volume)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .measure import AXIS_COLORS, fmt
from .widgets import Capsule, Switch


def _exclusive(parent, names, slot):
    group = QActionGroup(parent)
    group.setExclusive(True)
    actions = []
    for key, text in names:
        a = QAction(text, parent)
        a.setCheckable(True)
        a.setData(key)
        group.addAction(a)
        actions.append(a)
    group.triggered.connect(lambda a: slot(a.data()))
    return actions


def _label(name, text=""):
    lbl = QLabel(text)
    lbl.setObjectName(name)
    return lbl


class MeasurePanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.measure = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 0, 4, 0)
        lay.setSpacing(8)

        # v2.9: + Point and Angle; "Area & Volume" is just "Area" (both are shown)
        self.mode_actions = _exclusive(self, [("distance", "Distance"), ("point", "Point"),
                                              ("angle", "Angle"), ("area", "Area")],
                                       self._mode)
        tips = ("Click two points: distance and ΔX, ΔY, ΔZ",
                "Click a point: its distance from the origin (0, 0, 0), its X / Y / Z,\n"
                "and its distance to the section plane",
                "Click two faces: the angle between them",
                "Click parts (or CAD faces): area, and volume when they close up")
        for a, tip in zip(self.mode_actions, tips):
            a.setToolTip(tip)
        self.mode_actions[0].setChecked(True)
        lay.addWidget(Capsule(self.mode_actions, name="Segmented"))

        # Distance: snap. Area: what a click picks.
        self.snap_row, sr = QWidget(), QHBoxLayout()
        self.snap_row.setLayout(sr)
        sr.setContentsMargins(0, 0, 0, 0)
        sr.addWidget(QLabel("Snap to vertices"))
        sr.addStretch(1)
        self.snap = Switch()
        self.snap.toggled.connect(lambda on: self.measure and setattr(self.measure, "snap", on))
        sr.addWidget(self.snap)
        lay.addWidget(self.snap_row)

        self.pick_row, pr = QWidget(), QHBoxLayout()
        self.pick_row.setLayout(pr)
        pr.setContentsMargins(0, 0, 0, 0)
        pr.addWidget(QLabel("Pick"))
        pr.addStretch(1)
        self.pick_actions = _exclusive(self, [("parts", "Parts"), ("faces", "CAD faces")],
                                       self._pick)
        self.pick_actions[0].setChecked(True)
        pr.addWidget(Capsule(self.pick_actions, name="Segmented"))
        lay.addWidget(self.pick_row)

        # ---- result card --------------------------------------------------------
        self.card = QFrame()
        self.card.setObjectName("ResultCard")
        self.card_lay = QVBoxLayout(self.card)
        self.card_lay.setContentsMargins(12, 10, 12, 10)
        self.card_lay.setSpacing(2)
        lay.addWidget(self.card)
        self._card_widgets = []

        self.units_note = _label("InfoLine", "")
        self.units_note.setWordWrap(True)
        lay.addWidget(self.units_note)

        clear = QAction("Clear", self)
        clear.triggered.connect(lambda: self.measure and self.measure.clear())
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(Capsule([clear], name="Segmented"))
        lay.addLayout(row)
        self._mode_widgets("distance")

    # ---- binding ---------------------------------------------------------------
    def bind(self, scene):
        self.measure = scene.measure
        self.measure.on_changed = self.show_result
        self._has_faces = scene.model.source is not None    # exact CAD: face picking
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
        self.snap_row.setVisible(mode in ("distance", "point"))

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
        h.addWidget(_label("Caption", caption))
        h.addStretch(1)
        if tag:
            h.addWidget(_label("Tag", tag))
        self._add(top)
        big = _label("MutedValue" if muted else "BigValue", value)
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
            val = _label("ValueLabel", fmt(v, u))
            val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            val.setTextInteractionFlags(Qt.TextSelectableByMouse)
            g.addWidget(dot, row, 0)
            g.addWidget(_label("AxisLabel", name), row, 1)
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
            if "distance" not in r:
                self._headline("Distance", "—", tag=f"{len(pts)} / 2 points", muted=True)
                return
            self._headline("Distance", fmt(r["distance"], u))
            self._xyz_grid([("ΔX", r["dx"]), ("ΔY", r["dy"]), ("ΔZ", r["dz"])], u)
        elif r.get("mode") == "point":                          # v2.9
            if "xyz" not in r:
                self._headline("Point", "—", tag="click the model", muted=True)
                return
            self._headline("From origin", fmt(r["distance"], u))
            self._xyz_grid([("X", r["xyz"][0]), ("Y", r["xyz"][1]), ("Z", r["xyz"][2])], u)
            if "to_plane" in r:
                spacer = QWidget()
                spacer.setFixedHeight(6)
                self._add(spacer)
                side = "on the cut-away side" if r["to_plane"] > 0 else "on the shown side"
                self._headline("To section plane", fmt(r["to_plane"], u), tag=side)
        elif r.get("mode") == "angle":                          # v2.9
            if "planes" not in r:
                self._headline("Angle", "—", tag=f"{r['n']} / 2 faces", muted=True)
                return
            self._headline("Angle", f"{r['planes']:.2f}°", tag="between the faces")
            note = _label("InfoLine", f"Between their normals: {r['normals']:.2f}°")
            note.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self._add(note)
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
            sel = _label("SelectionCount", f'{r["count"]} {what}{on} selected')
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
