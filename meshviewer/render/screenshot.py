"""Scene ▸ Save Screenshot: the view drawn again off-screen at the size asked, saved as
PNG or JPEG (`save_image`), or as SVG: real vector shapes, polygons and lines
(render/svg.py) — not VTK's GL2PS export, which leaves out what is drawn through a
texture (the contours' colors)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pyvista as pv
from vtkmodules.util.numpy_support import numpy_to_vtk
from vtkmodules.vtkCommonDataModel import vtkImageData
from vtkmodules.vtkIOImage import vtkJPEGWriter, vtkPNGWriter

from meshviewer.render.background import ImageBackground
from meshviewer.render.style import THEMES


FORMATS = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".svg": "SVG"}   # SVG: svg.py
JPEG_QUALITY = 92


def _image_data(img):
    """(h, w, 3 | 4) uint8, top row first -> vtkImageData (bottom row first)."""
    h, w, c = img.shape
    im = vtkImageData()
    im.SetDimensions(w, h, 1)
    arr = numpy_to_vtk(np.ascontiguousarray(img[::-1]).reshape(-1, c), deep=True)
    arr.SetNumberOfComponents(c)
    im.GetPointData().SetScalars(arr)
    return im


def save_image(img, path):
    """Write the picture `img` ((h, w, 3 | 4) uint8) as the file's extension says: PNG,
    JPEG (on white where it is see-through); anything else (but .svg: vector, not from
    pixels): PNG, with .png added. -> the path written."""
    path = Path(path)
    ext = path.suffix.lower()
    if ext not in FORMATS or ext == ".svg":
        path, ext = path.with_name(path.name + ".png"), ".png"
    img = np.asarray(img, dtype=np.uint8)
    if ext in (".jpg", ".jpeg"):
        if img.shape[2] == 4:                         # no transparency in a JPEG: on white
            a = img[..., 3:4].astype(float) / 255.0
            img = (img[..., :3] * a + 255.0 * (1 - a)).round().astype(np.uint8)
        wr = vtkJPEGWriter()
        wr.SetQuality(JPEG_QUALITY)
        wr.ProgressiveOff()
        wr.SetFileName(str(path))
        wr.SetInputData(_image_data(img))
        wr.Write()
    else:
        wr = vtkPNGWriter()
        wr.SetFileName(str(path))
        wr.SetInputData(_image_data(img))
        wr.Write()
    return path


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
        """Save a picture at `scale`× the view size: PNG, JPEG or SVG by the extension
        (`save_image`) -> the path written. background: "current" (exactly as on
        screen) | "transparent" (with alpha; a JPEG gets white).

        The image is rendered in a separate off-screen window at the full target
        size, with text and line widths scaled by the same factor, so it looks
        exactly like the view, only sharper. (VTK's built-in tiled zoom drew the
        axis labels far too big / the grid labels far too small.)"""
        k = max(1, int(scale))
        if Path(path).suffix.lower() == ".svg":          # vector: no off-screen pixels
            from meshviewer.render.svg import svg_text
            Path(path).write_text(svg_text(self, k, background == "transparent"),
                                  encoding="utf-8")
            return Path(path)
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
            if self.state.get("axis_indicator", True):
                self._corner_axes(off, line_width=3 * k, color=t["grid"])
            self.colorbar.add_to(r2, k, dark=dark_vis)   # Contours: its color bar
            self.overlays.add_to(off.ren_win, cam, k, _clone_actor)  # marks, on top
            off.enable_anti_aliasing("ssaa") if k == 1 else None
            off.render()
            img = off.screenshot(None, transparent_background=transparent, return_img=True)
            path = save_image(img, path)
        finally:
            for prop, lw, ps in widths:
                prop.SetLineWidth(lw)
                prop.SetPointSize(ps)
            self.overlays.remove_from(off.ren_win)
            off.renderer.RemoveAllViewProps()         # shared actors stay in the main view
            off.close()
        return path

    def _screenshot_actors(self):
        """Everything visible in the model view except the grid, axes and handles;
        the colors over the parts too (Contours, y+, the walls, cell quality)."""
        sec = self.section
        actors = [self._surf, self._edges, self._outline, *self._face_actors,
                  *sec.cap_actors(), sec._outline, sec._plate, sec._plate_edge,
                  self._bbox_actor, *self.results.actors(), *self.yplus_view.actors(),
                  *self.walls.actors(), *self.quality.actors()]
        return [a for a in actors if a is not None and a.GetVisibility()]
