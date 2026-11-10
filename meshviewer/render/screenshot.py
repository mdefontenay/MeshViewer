"""Scene ▸ Save Screenshot: the view drawn again off-screen at the size asked."""
from __future__ import annotations

import numpy as np
import pyvista as pv

from meshviewer.render.background import ImageBackground
from meshviewer.render.style import THEMES


def _clone_actor(a):
    """A copy of an actor for ANOTHER render window: same data, settings and
    property, but its own mapper (GPU resources can't be shared between
    windows — sharing them crashed)."""
    m = a.GetMapper()
    m2 = m.NewInstance()
    m2.ShallowCopy(m)                                 # colours, scalars, clipping planes
    if m.GetNumberOfInputConnections(0):
        m2.SetInputConnection(m.GetInputConnection(0, 0))
    else:
        m2.SetInputDataObject(m.GetInputDataObject(0, 0))
    if hasattr(m, "GetCompositeDataDisplayAttributes"):
        m2.SetCompositeDataDisplayAttributes(m.GetCompositeDataDisplayAttributes())
    a2 = a.NewInstance()
    a2.ShallowCopy(a)                                 # property, transform, visibility
    a2.SetMapper(m2)
    return a2


class Screenshots:
    def screenshot(self, path, scale=2, background="current"):
        """Save a PNG at `scale`× the view size. background: "current" (exactly
        as on screen) | "transparent" (PNG with alpha).

        The image is rendered in a separate off-screen window at the full target
        size, with text and line widths scaled by the same factor, so it looks
        exactly like the view, only sharper. (VTK's built-in tiled zoom drew the
        axis labels far too big / the grid labels far too small.)"""
        k = max(1, int(scale))
        # Whether grid / axes are drawn light-on-dark ("current" follows Appearance).
        transparent = background == "transparent"
        dark_vis = False if transparent else self._dark   # transparent: for white pages
        w, h = self.p.window_size
        off = pv.Plotter(off_screen=True, window_size=(w * k, h * k))
        widths = []
        try:
            main = self.p.renderer
            r2 = off.renderer
            if transparent:
                off.set_background("white")           # only anti-aliased rims show it
            else:
                r2.SetBackground(main.GetBackground())
                r2.SetBackground2(main.GetBackground2())
                r2.SetGradientBackground(main.GetGradientBackground())
                if self._bg_image is not None:      # same crop: same aspect ratio
                    ImageBackground(r2, self._bg_image.arr)
            cam = pv.Camera()
            cam.DeepCopy(main.GetActiveCamera())
            r2.camera = cam                           # (grid labels follow this camera)
            off.camera_set = True                     # don't let PyVista re-frame it

            for a in self._screenshot_actors():
                prop = a.GetProperty()
                widths.append((prop, prop.GetLineWidth(), prop.GetPointSize()))
                prop.SetLineWidth(prop.GetLineWidth() * k)
                prop.SetPointSize(prop.GetPointSize() * k)
                r2.AddActor(_clone_actor(a))
            t = THEMES[dark_vis]
            if self.state["grid"]:
                g = self._add_grid(off, t["grid"], k)
                g.SetLabelOffset(g.GetLabelOffset() * k)          # offsets are in pixels
                g.SetTitleOffset([v * k for v in np.atleast_1d(g.GetTitleOffset())])
            self._corner_axes(off, line_width=3 * k, color=t["grid"])
            self.measure.add_to(off.ren_win, cam, k, _clone_actor)  # markers, on top
            off.enable_anti_aliasing("ssaa") if k == 1 else None
            off.render()
            off.screenshot(str(path), transparent_background=transparent)
        finally:
            for prop, lw, ps in widths:
                prop.SetLineWidth(lw)
                prop.SetPointSize(ps)
            self.measure.remove_from(off.ren_win)
            off.renderer.RemoveAllViewProps()         # shared actors stay in the main view
            off.close()

    def _screenshot_actors(self):
        """Everything visible in the model view except the grid, axes and handles."""
        sec = self.section
        actors = [self._surf, self._edges, self._outline, *self._face_actors,
                  *sec.cap_actors(), sec._outline, sec._plate, sec._plate_edge,
                  self._bbox_actor]
        return [a for a in actors if a is not None and a.GetVisibility()]
