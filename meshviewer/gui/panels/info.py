"""Sidebar section "Info" — what's in the file, at a glance.

    Extent                       mm         <- the unit, or "file units"
         from        to        size
    X    −20         100       120
    Y    −10         30        40
    Z    0           35        35

    Faces           3,650
                    3,100 triangles · 550 quads
    Points          1,122
    Edge length     0.2 to 0.28 mm
                    shortest to longest
    Volume cells    2,750                  (meshes; read on demand)
                    1,250 tetra · 750 pyramid · …

Recomputed when the section opens, the model moves (Edit) or the units change.
"""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget,
)

from meshviewer.core.mesh.volume import NAMES
from meshviewer.core.polys import edge_lengths, faces_by_size
from meshviewer.core.units import fmt
from meshviewer.gui.dialogs.units import FILE_UNITS
from meshviewer.gui.widgets import MenuSelect

KINDS = {3: ("triangle", "triangles"), 4: ("quad", "quads")}


def _n(v):
    return fmt(v) if v is not None else "—"


def _label(text, name):
    lab = QLabel(text)
    lab.setObjectName(name)
    return lab


class InfoPanel(QWidget):
    file_unit_changed = Signal(str)            # the file's unit, picked here

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = None
        self._active = False
        self._edges = None                     # cached (shortest, longest) edge
        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 0, 2, 0)
        lay.setSpacing(10)

        # ---- the file's unit (asked the first time the file is opened) -----------------
        fu = QHBoxLayout()
        fu.addWidget(_label("File unit", "ValueLabel"))
        fu.addStretch(1)
        self.file_unit = MenuSelect()
        for key, text in FILE_UNITS:
            self.file_unit.addItem(text, key)
        self.file_unit.setToolTip("File Unit")
        self.file_unit.currentIndexChanged.connect(
            lambda _i: self.scene is not None and self.file_unit_changed.emit(
                self.file_unit.currentData()))
        fu.addWidget(self.file_unit)
        lay.addLayout(fu)

        # ---- extent: a small table, one row per axis ----------------------------
        head = QHBoxLayout()
        head.addWidget(_label("Extent", "Caption"))
        head.addStretch(1)
        self.unit = _label("", "AxisLabel")
        head.addWidget(self.unit)
        lay.addLayout(head)
        g = QGridLayout()
        g.setContentsMargins(0, 0, 0, 0)
        g.setHorizontalSpacing(10)
        g.setVerticalSpacing(2)
        for c, text in enumerate(("from", "to", "size"), start=1):
            h = _label(text, "AxisLabel")
            h.setAlignment(Qt.AlignRight)
            g.addWidget(h, 0, c)
        self.extent = []
        for r, axis in enumerate("XYZ", start=1):
            g.addWidget(_label(axis, "AxisLabel"), r, 0)
            cells = []
            for c in range(1, 4):
                v = _label("—", "ValueLabel")
                v.setAlignment(Qt.AlignRight)
                v.setTextInteractionFlags(Qt.TextSelectableByMouse)
                g.addWidget(v, r, c)
                cells.append(v)
            self.extent.append(cells)
        g.setColumnStretch(1, 1)
        g.setColumnStretch(2, 1)
        g.setColumnStretch(3, 1)
        lay.addLayout(g)

        # ---- counts: big number + a grey line explaining it ------------------------
        g = QGridLayout()
        g.setContentsMargins(0, 0, 0, 0)
        g.setHorizontalSpacing(10)
        g.setVerticalSpacing(1)
        self.rows = {}
        r = 0
        for key, text in (("faces", "Faces"), ("points", "Points"), ("edges", "Edge length"),
                          ("cells", "Volume cells")):
            name = _label(text, "ValueLabel")
            value = _label("—", "ValueLabel")
            value.setAlignment(Qt.AlignRight)
            value.setTextInteractionFlags(Qt.TextSelectableByMouse)
            note = _label("", "InfoLine")
            note.setAlignment(Qt.AlignRight)
            note.setWordWrap(True)
            g.addWidget(name, r, 0)
            g.addWidget(value, r, 1)
            g.addWidget(note, r + 1, 0, 1, 2)
            self.rows[key] = (name, value, note)
            r += 2
        g.setColumnStretch(1, 1)
        lay.addLayout(g)

        self.read = QPushButton("Count volume cells")
        self.read.setObjectName("LinkButton")
        self.read.setFlat(True)
        self.read.setCursor(Qt.PointingHandCursor)
        self.read.setToolTip("Read the 3D cells from the file (can take a moment)")
        self.read.clicked.connect(self._read_volume)
        lay.addWidget(self.read, 0, Qt.AlignRight)

    def bind(self, scene):
        self.scene = scene
        self._edges = None
        if self._active:
            self.refresh()

    def activate(self, on):
        self._active = bool(on)
        if on:
            self.refresh()

    def model_changed(self):
        """The model moved or was re-meshed: edges / bounds may differ."""
        self._edges = None
        if self._active:
            self.refresh()

    def refresh(self):
        sc = self.scene
        if sc is None or not self._active:
            return
        s, unit = sc.measure.unit_scale()
        i = self.file_unit.findData(sc.model.units)
        if i >= 0 and i != self.file_unit.currentIndex():
            self.file_unit.blockSignals(True)
            self.file_unit.setCurrentIndex(i)
            self.file_unit.blockSignals(False)
        self.unit.setText(unit or "file units")
        b = np.array(sc.model_bounds(), dtype=float).reshape(3, 2) * s
        for cells, (lo, hi) in zip(self.extent, b):
            for cell, v in zip(cells, (lo, hi, hi - lo)):
                cell.setText(_n(v))
        u = f" {unit}" if unit else ""

        counts, n_points = {}, 0
        for poly in sc.model.parts.values():
            n_points += poly.n_points
            for k, f in faces_by_size(poly).items():
                counts[k] = counts.get(k, 0) + len(f)
        self._row("faces", f"{sum(counts.values()):,}", " · ".join(
            f"{c:,} {KINDS.get(k, (f'{k}-sided', f'{k}-sided'))[c != 1]}"
            for k, c in sorted(counts.items())) if len(counts) > 1 else "")
        self._row("points", f"{n_points:,}", "")

        if self._edges is None:
            lo, hi = np.inf, -np.inf
            for poly in sc.model.parts.values():
                a, z = edge_lengths(poly)
                if a is not None:
                    lo, hi = min(lo, a), max(hi, z)
            self._edges = (lo, hi) if np.isfinite(lo) else (None, None)
        lo, hi = self._edges
        self._row("edges", f"{_n(lo * s)} to {_n(hi * s)}{u}" if lo is not None else "—",
                  "shortest to longest, on the surface")

        sec = sc.section
        volume = sc.model.kind == "mesh" and sec.has_volume
        loaded = sec._volume is not None and sec._volume is not False
        for w in self.rows["cells"]:
            w.setVisible(volume)
        self.read.setVisible(volume and not loaded)
        if volume and loaded:
            types, n = np.unique(sec._volume.celltypes, return_counts=True)
            self._row("cells", f"{sec._volume.n_cells:,}", " · ".join(
                f"{c:,} {NAMES.get(t, t)}" for t, c in zip(types, n)))
        elif volume:
            self._row("cells", "not read yet", "")

    def _row(self, key, value, note):
        _, v, n = self.rows[key]
        v.setText(value)
        n.setText(note)
        n.setVisible(bool(note))

    def _read_volume(self):
        if self.scene is None:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.scene.quality.dataset()          # reads the cells (same lock as Cell quality)
        finally:
            QApplication.restoreOverrideCursor()
        self.refresh()
