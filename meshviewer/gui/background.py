"""Picture behind the 3D view, chosen in Appearance.

The image is drawn as the renderer's own textured background (no extra render
layer, so the measure markers and axes stay exactly as they are). It is
centre-cropped to the window's shape ("fill", like a desktop wallpaper) and
re-cropped whenever the window's proportions change.
"""
from __future__ import annotations

import numpy as np
import pyvista as pv
from vtkmodules.vtkRenderingCore import vtkTexture

MAX_SIDE = 4096          # larger pictures are thinned out (GPU texture limits)


def load_image(path):
    """(rows, cols, channels) uint8 array, row 0 at the bottom (VTK order)."""
    img = pv.read(path)
    arr = np.asarray(img.active_scalars if img.active_scalars is not None
                     else img.point_data[img.point_data.keys()[0]])
    nx, ny = img.dimensions[:2]
    arr = arr.reshape(ny, nx, -1)
    if arr.dtype != np.uint8:                      # 16-bit TIFF / PNG
        hi = float(arr.max()) or 1.0
        arr = (arr.astype(np.float32) * (255.0 / hi)).astype(np.uint8)
    step = int(np.ceil(max(nx, ny) / MAX_SIDE))
    return arr[::step, ::step] if step > 1 else arr


def is_dark_image(arr) -> bool:
    """Mean luminance below half -> use the light grid / axes colours."""
    rgb = arr[..., :3].astype(np.float32) if arr.shape[2] >= 3 else arr[..., :1].astype(np.float32)
    if rgb.shape[2] == 3:
        lum = rgb @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    else:
        lum = rgb[..., 0]
    return float(lum.mean()) / 255.0 < 0.5


def cover_crop(arr, width, height):
    """Centre crop of `arr` with the window's aspect ratio (no stretching)."""
    rows, cols = arr.shape[:2]
    want = width / max(height, 1)
    if cols / rows > want:                         # image wider: trim the sides
        c = max(1, round(rows * want))
        x0 = (cols - c) // 2
        return arr[:, x0:x0 + c]
    r = max(1, round(cols / want))                 # image taller: trim top and bottom
    y0 = (rows - r) // 2
    return arr[y0:y0 + r]


def _texture(arr):
    rows, cols, nc = arr.shape
    img = pv.ImageData(dimensions=(cols, rows, 1))
    img.point_data["rgb"] = np.ascontiguousarray(arr).reshape(-1, nc)
    tex = vtkTexture()
    tex.SetInputData(img)
    tex.InterpolateOn()
    return tex


class ImageBackground:
    """Attach a picture to one renderer; follows its window's size."""

    def __init__(self, renderer, arr):
        self.ren = renderer
        self.arr = arr
        self._aspect = None
        self._obs = renderer.AddObserver("StartEvent", lambda *_: self.update())
        renderer.TexturedBackgroundOn()
        self.update()

    def update(self):
        rw = self.ren.GetRenderWindow()
        if rw is None:
            return
        w, h = rw.GetSize()
        vp = self.ren.GetViewport()
        w, h = max(1, w * (vp[2] - vp[0])), max(1, h * (vp[3] - vp[1]))
        aspect = w / h
        if self._aspect and abs(aspect / self._aspect - 1) < 0.01:
            return
        self._aspect = aspect
        self.ren.SetBackgroundTexture(_texture(cover_crop(self.arr, w, h)))

    def detach(self):
        self.ren.RemoveObserver(self._obs)
        self.ren.TexturedBackgroundOff()
        self.ren.SetBackgroundTexture(None)
