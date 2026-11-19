"""Layers drawn over the model, always visible (the Measuring Tool's marks, the probes'
markers): layer 1 the marks, layer 2 their labels — each a renderer sharing the view's
camera, made the first time. Save Screenshot copies them into its off-screen window
(`add_to` / `remove_from`, with the origin's actors). No Qt.

    scene.overlays.add(actor, text=False)      on top of the model
    scene.overlays.remove(actor)
"""
from __future__ import annotations

from vtkmodules.vtkRenderingCore import vtkBillboardTextActor3D, vtkRenderer


class Overlays:
    def __init__(self, scene):
        self.scene = scene
        self.p = scene.p
        self._marks = self._text = None
        self.actors = []                            # on the layers now

    def layer(self, text=False):
        if self._marks is None:
            rw = self.p.ren_win
            rw.SetNumberOfLayers(max(3, rw.GetNumberOfLayers()))
            self._marks, self._text = vtkRenderer(), vtkRenderer()
            for lay, n in ((self._marks, 1), (self._text, 2)):
                lay.SetLayer(n)
                lay.InteractiveOff()
                lay.SetActiveCamera(self.p.renderer.GetActiveCamera())
                rw.AddRenderer(lay)
        return self._text if text else self._marks

    def add(self, actor, text=False):
        self.layer(text).AddActor(actor)
        self.actors.append(actor)
        return actor

    def remove(self, actor):
        if actor in self.actors:
            self.actors.remove(actor)
            self.layer().RemoveActor(actor)
            self.layer(text=True).RemoveActor(actor)

    # ---- screenshots: the same marks in an off-screen window -------------------------------
    def add_to(self, ren_win, camera, k, clone=lambda a: a):
        actors = [*self.actors, *self.scene.origin_actors()]
        self._shot = None
        if not actors:
            return
        ren_win.SetNumberOfLayers(3)
        marks, text = vtkRenderer(), vtkRenderer()
        for lay, n in ((marks, 1), (text, 2)):
            lay.SetLayer(n)
            lay.SetActiveCamera(camera)
        saved = []
        for a in actors:
            if isinstance(a, vtkBillboardTextActor3D):
                tp = a.GetTextProperty()
                saved.append((tp, "SetFontSize", tp.GetFontSize()))
                tp.SetFontSize(tp.GetFontSize() * k)
                t2 = vtkBillboardTextActor3D()            # text: a fresh copy
                t2.SetInput(a.GetInput())
                t2.SetPosition(a.GetPosition())
                t2.SetTextProperty(tp)
                text.AddActor(t2)
            else:
                prop = a.GetProperty()
                saved += [(prop, "SetLineWidth", prop.GetLineWidth()),
                          (prop, "SetPointSize", prop.GetPointSize())]
                prop.SetLineWidth(prop.GetLineWidth() * k)
                prop.SetPointSize(prop.GetPointSize() * k)
                marks.AddActor(clone(a))
        ren_win.AddRenderer(marks)
        ren_win.AddRenderer(text)
        self._shot = (marks, text, saved)

    def remove_from(self, ren_win):
        shot = getattr(self, "_shot", None)
        if shot is None:
            return
        marks, text, saved = shot
        for obj, setter, v in saved:
            getattr(obj, setter)(v)
        for lay in (marks, text):
            lay.RemoveAllViewProps()
            ren_win.RemoveRenderer(lay)
        self._shot = None
