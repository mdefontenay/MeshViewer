"""What "Cell quality" draws in the 3D view. No Qt widgets.

    qv = scene.quality
    qv.dataset()                    the cells checked: volume cells, or the merged
                                    boundary surface for files without them
    qv.show_bad(ids)                bad cells drawn solid red, the model see-through
    qv.set_colors(rgb)              colour the section cut (volume meshes) or the
                                    surface (surface meshes) by quality; None = off
    qv.after_edit()                 the model moved: redraw at the new place
"""
from __future__ import annotations

import threading

import numpy as np
import pyvista as pv
from vtkmodules.vtkFiltersCore import vtkAppendPolyData
from vtkmodules.vtkFiltersGeometry import vtkDataSetSurfaceFilter
from meshviewer.core.polys import bare

BAD_COLOR = "#ff453a"
GHOST_OPACITY = 0.18
MAX_SHOWN = 300_000            # bad cells drawn at most (the worst ones first)


class QualityView:
    def __init__(self, scene):
        self.scene = scene
        self.p = scene.p
        self._lock = threading.Lock()
        self._surface = None          # merged boundaries (files without volume cells)
        self._bad_ids = None          # cells shown in red
        self._bad_actor = None
        self.rgb = None               # colour per cell, or None
        self._color_actor = None      # surface meshes: the coloured surface

    # ---- what is checked ---------------------------------------------------------
    @property
    def is_volume(self):
        return self.scene.section.has_volume

    def dataset(self):
        """Volume cells (read the first time — may take a while, call it from a
        background job) or the merged boundary surface."""
        with self._lock:
            grid = self.scene.section.volume_grid() if self.is_volume else None
            if grid is not None:
                return grid
            if self._surface is None:
                self._surface = self._merged_surface()
            return self._surface

    def _merged_surface(self):
        app = vtkAppendPolyData()
        for n in self.scene.names:
            poly = self.scene.model.parts[n]
            app.AddInputData(bare(poly))
        app.Update()
        return pv.wrap(app.GetOutput())

    def cell_bounds(self, ids):
        ds = self.dataset()
        sub = ds.extract_cells(np.asarray(ids)[:MAX_SHOWN])
        return sub.bounds if sub.n_cells else None

    # ---- bad cells -------------------------------------------------------------------
    def show_bad(self, ids):
        """ids: cell numbers to draw (worst first), or None to hide them."""
        self._bad_ids = None if ids is None else np.asarray(ids)[:MAX_SHOWN]
        self._draw_bad()
        self.scene.set_ghost(self._bad_ids is not None)

    def _draw_bad(self):
        if self._bad_actor is not None:
            self.p.remove_actor(self._bad_actor, render=False)
            self._bad_actor = None
        if self._bad_ids is not None and len(self._bad_ids):
            f = vtkDataSetSurfaceFilter()          # outer faces of the bad cells
            f.SetInputData(self.dataset().extract_cells(self._bad_ids))
            f.Update()
            surf = pv.wrap(f.GetOutput())
            self._bad_actor = self.p.add_mesh(
                surf, color=BAD_COLOR, show_edges=True, edge_color="#5a0d08", line_width=1,
                lighting=True, pickable=False, reset_camera=False)
            self.scene.section.clip(self._bad_actor)
        self.p.render()

    # ---- colour by quality ------------------------------------------------------------
    def set_colors(self, rgb):
        """rgb: (n cells, 3) uint8 in dataset() order, or None (off)."""
        self.rgb = rgb
        if self.is_volume:
            self.scene.section.update_caps()        # the cut picks the colours up
        else:
            self._draw_colored_surface()

    def _draw_colored_surface(self):
        if self._color_actor is not None:
            self.p.remove_actor(self._color_actor, render=False)
            self._color_actor = None
        sc = self.scene
        if self.rgb is not None:
            surf = self.dataset().copy(deep=False)
            surf.cell_data["QualityRGB"] = self.rgb
            self._color_actor = self.p.add_mesh(
                surf, scalars="QualityRGB", rgb=True, show_edges=sc.state["mesh_edges"],
                edge_color="#202020", pickable=False, reset_camera=False)
            sc.section.clip(self._color_actor)
        sc._apply_lines()                            # hides the plain surface meanwhile
        self.p.render()

    @property
    def hides_surface(self):
        return self.rgb is not None and not self.is_volume

    # ---- the model moved (Edit) or was reloaded -----------------------------------------
    def after_edit(self):
        self._surface = None                         # rebuilt from the moved parts
        if self._bad_ids is not None:
            self._draw_bad()
        if self.rgb is not None and not self.is_volume:
            self._draw_colored_surface()

    def actors(self):
        """For the section plane: everything that should be cut."""
        return [a for a in (self._bad_actor, self._color_actor) if a is not None]

    def clear(self):
        self.show_bad(None)
        self.set_colors(None)
