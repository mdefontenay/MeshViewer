"""The Meshing Control tool (STEP, IGES, BREP): how finely curved CAD faces are
triangulated for display.

    Meshing Control                      Medium      (the level, in the header)
      Coarse  ──────●──────  Fine
      3,650 triangles

The window re-meshes in the background (`level_requested`); the Sidebar binds the level
and the triangle count (sidebar.py, refresh_parts).
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from meshviewer.gui.forms import _label, column, note
from meshviewer.gui.widgets import NoWheelSlider


class MeshingPanel(QWidget):
    level_requested = Signal(int)            # a new level, once the slider is let go

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = None
        lay = column(self, spacing=4)
        row = QHBoxLayout()
        self.slider = NoWheelSlider(Qt.Horizontal)
        self.slider.setPageStep(1)
        self.slider.setToolTip("How finely curved CAD faces are triangulated for display")
        self.slider.valueChanged.connect(self._moved)
        self.slider.sliderReleased.connect(lambda: self._request(self.slider.value()))
        row.addWidget(_label("Coarse", "SmallLabel"))
        row.addWidget(self.slider, 1)
        row.addWidget(_label("Fine", "SmallLabel"))
        lay.addLayout(row)
        self.count = note()                  # "3,650 triangles"
        lay.addWidget(self.count)
        self.value = QLabel("")              # the level's name, in the tool's header
        self.value.setObjectName("ValueLabel")

    def bind(self, scene):
        self.scene = scene
        m = scene.model
        if scene.can_retessellate:
            self.slider.blockSignals(True)
            self.slider.setRange(0, len(m.quality_levels) - 1)
            self.slider.setValue(m.quality)
            self.slider.blockSignals(False)

    def refresh(self, n_triangles):
        """After loading or re-meshing."""
        m = self.scene.model
        self.value.setText(m.quality_levels[m.quality])
        self.count.setText(f"{n_triangles:,} triangles")
        self.slider.setEnabled(True)

    def failed(self):
        """Re-meshing failed: back to the level the model has."""
        self.slider.blockSignals(True)
        self.slider.setValue(self.scene.model.quality)
        self.slider.blockSignals(False)

    def _moved(self, level):
        if self.scene and not self.slider.isSliderDown():   # keyboard / click on track
            self._request(level)
        elif self.scene:
            self.value.setText(self.scene.model.quality_levels[level])

    def _request(self, level):
        if self.scene is not None and level != self.scene.model.quality:
            self.slider.setEnabled(False)
            self.value.setText(self.scene.model.quality_levels[level])
            self.count.setText("Re-meshing…")
            self.level_requested.emit(level)
