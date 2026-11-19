"""The probes' markers in the 3D view: a dot per point, the lines, the areas tinted, each
probe named on a tag ("Probe 1") — for every probe shown (its eye). Drawn over the model
(render/layers.py: a point inside the cells stays visible), in the accent color, one
actor per kind for all probes, not pickable; in Save Screenshot too. No Qt.

    scene.probe_marks.show([(name, marker), …])     marker: core/probe.py Sampler.marker
"""
from __future__ import annotations

import numpy as np
import pyvista as pv
from vtkmodules.vtkRenderingCore import vtkActor, vtkBillboardTextActor3D, vtkPolyDataMapper

POINT_PX = 12
LINE_PX = 4.0
TINT = 0.35                            # an area's tint (opacity)


class ProbeMarks:
    def __init__(self, scene):
        self.scene = scene
        self.p = scene.p
        self._actors = []
        self.shown = []                    # [(name, marker)]

    def show(self, marks):
        lay = self.scene.overlays
        for a in self._actors:
            lay.remove(a)
        self._actors = []
        self.shown = list(marks)
        color = pv.Color(self.scene.accent).float_rgb
        parts = self.scene.model.parts
        pts, lines, faces = [], [], []
        for name, m in marks:
            if m.get("points") is not None and len(m["points"]):
                pts.append(np.asarray(m["points"], dtype=float))
            if m.get("lines") is not None and len(m["lines"]):
                lines.append(np.asarray(m["lines"], dtype=float))
            for n, ids in m.get("faces") or ():
                if n in parts:
                    faces.append(parts[n].extract_cells(np.asarray(ids))
                                 .extract_surface(algorithm="dataset_surface"))
            if m.get("label_at") is not None:
                self._label(name, m["label_at"], color)
        if faces:
            surf = faces[0] if len(faces) == 1 else pv.merge(faces)
            a = self._add(surf, color)
            a.GetProperty().SetOpacity(TINT)
        if lines:
            seg = np.vstack(lines).reshape(-1, 3)
            cells = np.column_stack([np.full(len(seg) // 2, 2),
                                     np.arange(len(seg)).reshape(-1, 2)]).ravel()
            self._add(pv.PolyData(seg, lines=cells), color).GetProperty() \
                .SetLineWidth(LINE_PX)
        if pts:                                        # a white ring, the color inside
            for c, size, ahead in (((1, 1, 1), POINT_PX + 5, 0), (color, POINT_PX, -40)):
                a = self._add(pv.PolyData(np.vstack(pts)), c)
                prop = a.GetProperty()
                prop.SetRepresentationToPoints()
                prop.SetPointSize(size)
                prop.SetRenderPointsAsSpheres(True)
                a.GetMapper().SetRelativeCoincidentTopologyPointOffsetParameter(ahead)
        self.p.render()

    def _add(self, poly, color):
        m = vtkPolyDataMapper()
        m.SetInputData(poly)
        m.ScalarVisibilityOff()
        a = vtkActor()
        a.SetMapper(m)
        a.GetProperty().SetColor(*color)
        a.GetProperty().SetLighting(False)
        a.PickableOff()
        self.scene.overlays.add(a)
        self._actors.append(a)
        return a

    def _label(self, name, at, color):
        label = vtkBillboardTextActor3D()
        label.SetInput(f" {name} ")
        label.SetPosition(*np.asarray(at, dtype=float))
        label.SetDisplayOffset(10, 8)                  # beside the dot, not over it
        tp = label.GetTextProperty()
        tp.SetFontSize(13)
        tp.SetBold(True)
        tp.SetColor(1, 1, 1)
        tp.SetBackgroundColor(*color)
        tp.SetBackgroundOpacity(0.92)
        tp.SetFrame(False)
        label.PickableOff()
        self.scene.overlays.add(label, text=True)
        self._actors.append(label)

    def restyle(self):
        """The accent changed: drawn again in it."""
        if self.shown:
            self.show(self.shown)
