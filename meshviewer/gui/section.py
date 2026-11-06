"""Cross-section: a plane that hides one half of the model and fills the cut.

Plane = origin (x, y, z) + normal (x, y, z). The half the normal points to is
hidden. Clipping is done on the GPU (instant); the filled cut faces ("caps")
and cut outline are computed on the CPU, so the UI asks for them only once a
change settles (see update_caps). No Qt in here.

Speed (heavy CAD): only parts whose bounding box touches the plane are cut,
with VTK's fast multi-threaded polydata plane cutter; all caps go into ONE
actor and all outlines into another (instead of one actor per part).
"""
from __future__ import annotations

import numpy as np
import pyvista as pv
from vtkmodules.vtkCommonDataModel import vtkPlane
from vtkmodules.vtkFiltersCore import (
    vtkAppendPolyData, vtkCleanPolyData, vtkPlaneCutter, vtkPolyDataPlaneCutter,
)
from vtkmodules.vtkFiltersGeneral import vtkContourTriangulator


def _darker(hex_color, f=0.78):
    r, g, b = pv.Color(hex_color).float_rgb
    return (r * f, g * f, b * f)


class Section:
    def __init__(self, scene):
        self.scene = scene
        self.p = scene.p
        self.enabled = False
        self.fill = scene.model.is_cad     # closed CAD solids: fill; CFD boxes: outline only
        # NEW (v2.19): meshes with volume cells show the cut cells instead of a fill
        self.has_volume = scene.model.volume is not None
        self._volume = None                # pv.UnstructuredGrid once loaded, False if none
        self._vol_cutter = None            # kept: re-cutting reuses its search tree
        self._vol_cut = None               # actor: cut cells with their edges
        self.show_handle = True
        self.on_widget_moved = None        # UI hook: called with (origin, normal)

        self._plane = vtkPlane()           # shared by every clipped mapper
        self._caps = None                  # one actor with every filled cut face
        self._cap_part = None              # cap cell -> index into scene.names
        self._outline = None               # one actor with all cut lines
        self._widget = None
        self._plate = None                 # our own translucent plane (always drawn)
        self._plate_edge = None
        self.reset_bounds()
        self.origin = self.center.copy()
        self.normal = np.array([1.0, 0.0, 0.0])
        self._apply_plane()

    # ---- geometry helpers ----------------------------------------------
    def reset_bounds(self):
        names = self.scene.names
        b = np.array([self.scene.model.parts[n].bounds for n in names], dtype=float)
        lo = b[:, 0::2].min(axis=0)
        hi = b[:, 1::2].max(axis=0)
        # Per-part box centre + half size, for the "does the plane touch it?" test.
        self._box_c = (b[:, 0::2] + b[:, 1::2]) / 2
        self._box_h = (b[:, 1::2] - b[:, 0::2]) / 2
        self.lo, self.hi = lo, hi
        self.center = (lo + hi) / 2
        self.diag = float(np.linalg.norm(hi - lo)) or 1.0

    @property
    def offset(self):
        """Signed distance of the plane from the model centre, along the normal."""
        return float(np.dot(self.origin - self.center, self.normal))

    # ---- public API ------------------------------------------------------
    def set_enabled(self, on, caps=True):
        """caps=False: clip now (instant), let the caller fill the cut a moment later."""
        self.enabled = bool(on)
        for actor in self.scene.clippable_actors():
            self.clip(actor)
        self._sync_widget()
        self._sync_plate()
        if caps or not on:
            self.update_caps()
        else:
            self.p.render()

    def set_plane(self, origin=None, normal=None, caps=True):
        if origin is not None:
            self.origin = np.asarray(origin, dtype=float)
        if normal is not None:
            n = np.asarray(normal, dtype=float)
            length = np.linalg.norm(n)
            if length < 1e-12:
                return                       # (0,0,0) is not a direction: ignore
            self.normal = n / length
        self._apply_plane()
        self._sync_widget()
        if caps:
            self.update_caps()
        else:
            self._hide_caps()                # stale caps would float in the wrong place
            self.p.render()

    def set_offset(self, d, caps=True):
        self.set_plane(origin=self.center + d * self.normal, caps=caps)

    def flip(self):
        self.set_plane(normal=-self.normal)

    def set_fill(self, on, caps=True):
        self.fill = bool(on)
        if caps:
            self.update_caps()

    def set_handle(self, on):
        self.show_handle = bool(on)
        self._sync_widget()
        self._sync_plate()
        self.p.render()

    def set_accent(self, accent):
        c = pv.Color(accent).float_rgb
        for a in (self._plate, self._plate_edge):
            if a is not None:
                a.GetProperty().SetColor(c)

    def clip(self, actor):
        """Attach / detach the section plane to one actor's mapper."""
        if actor is None:
            return
        m = actor.GetMapper()
        m.RemoveAllClippingPlanes()
        if self.enabled:
            m.AddClippingPlane(self._plane)

    def update_caps(self):
        """Recompute filled cut faces + outline (CPU). Call when a change settles."""
        self._clear_caps()
        if not self.enabled:
            self.p.render()
            return
        plane = vtkPlane()
        # Nudge the cut a hair (1e-6 of the model size) so it never runs exactly
        # through mesh vertices or along a face lying in the plane — those
        # degenerate cuts made the cap triangulation take seconds per part.
        plane.SetOrigin(*(self.origin + self.normal * self.diag * 1e-6))
        plane.SetNormal(*self.normal)
        outlines, caps = vtkAppendPolyData(), vtkAppendPolyData()
        n_lines = n_caps = 0
        cap_part = []
        cut_mesh = self.fill and self._cut_volume(plane)     # NEW (v2.19)

        for i in self._parts_touching_plane():
            name = self.scene.names[i]
            cutter = vtkPolyDataPlaneCutter()
            cutter.SetInputData(self.scene.model.parts[name])
            cutter.SetPlane(plane)
            cutter.Update()
            cut = cutter.GetOutput()
            if cut.GetNumberOfCells() == 0:
                continue
            outlines.AddInputData(cut)
            n_lines += 1
            if self.fill and not cut_mesh:
                cap = self._triangulate(cut)
                if cap.GetNumberOfCells():
                    caps.AddInputData(cap)
                    cap_part.append(np.full(cap.GetNumberOfCells(), i, dtype=np.int32))
                    n_caps += 1

        if n_caps:
            caps.Update()
            mesh = pv.wrap(caps.GetOutput())
            self._cap_part = np.concatenate(cap_part)
            rgb = np.array([_darker(self.scene.colors[n]) for n in self.scene.names]) * 255
            mesh.cell_data["rgb"] = rgb[self._cap_part].astype(np.uint8)
            self._caps = self.p.add_mesh(mesh, scalars="rgb", rgb=True, show_scalar_bar=False,
                                         reset_camera=False, pickable=True)
        if n_lines:
            outlines.Update()
            self._outline = self.p.add_mesh(pv.wrap(outlines.GetOutput()),
                                            color=self.scene.edge_color, line_width=2,
                                            lighting=False, pickable=False, reset_camera=False)
        self.p.render()

    def cap_owner(self, actor, cell_id):
        """Part name for a picked cell of the caps actor (else None)."""
        if actor is not None and actor is self._caps and 0 <= cell_id < len(self._cap_part):
            return self.scene.names[self._cap_part[cell_id]]
        return None

    def cap_actors(self):
        return [a for a in (self._caps, self._vol_cut) if a is not None]

    # ---- NEW (v2.19): cut cells of a volume mesh -------------------------------------
    @property
    def volume_cells(self):
        """Number of 3D cells once loaded (0 = none / not loaded yet)."""
        return self._volume.n_cells if self._volume else 0

    def _cut_volume(self, plane):
        """Show where the plane cuts the volume cells (fill + cell edges).
        Returns False when the file has no volume cells (-> ordinary fill)."""
        if not self.has_volume:
            return False
        if self._volume is None:                       # first time: read the cells
            try:
                self._volume = self.scene.model.volume() or False
            except Exception as exc:                   # unreadable: plain fill instead
                print(f"volume cells could not be read: {exc}")
                self._volume = False
        if not self._volume:
            self.has_volume = False
            return False
        if self._vol_cutter is None:
            self._vol_cutter = vtkPlaneCutter()        # multi-threaded, builds a search tree
            self._vol_cutter.SetInputData(self._volume)
            self._vol_cutter.InterpolateAttributesOff()
        self._vol_cutter.SetPlane(plane)
        self._vol_cutter.Update()
        cut = pv.wrap(self._vol_cutter.GetOutput())
        if cut.n_cells:
            t = self.scene.theme_colors()
            self._vol_cut = self.p.add_mesh(
                cut, color=t["cut_fill"], show_edges=True, edge_color=t["cut_edge"],
                line_width=1, lighting=False, pickable=False, reset_camera=False)
            self.set_moving(self.scene._moving)
        return True

    def set_moving(self, moving):
        """Cell edges off while the view moves (same as the model's edges)."""
        if self._vol_cut is not None:
            self._vol_cut.GetProperty().SetEdgeVisibility(
                not (moving and self.scene.hide_edges_moving))

    def restyle(self):
        """Colours after a light / dark change."""
        t = self.scene.theme_colors()
        if self._vol_cut is not None:
            self._vol_cut.GetProperty().SetColor(pv.Color(t["cut_fill"]).float_rgb)
            self._vol_cut.GetProperty().SetEdgeColor(pv.Color(t["cut_edge"]).float_rgb)
        if self._outline is not None:
            self._outline.GetProperty().SetColor(pv.Color(self.scene.edge_color).float_rgb)

    def rebuild(self):
        """After the parts were replaced (new mesh quality)."""
        self.reset_bounds()
        for actor in self.scene.clippable_actors():
            self.clip(actor)
        if self._widget is not None:
            self._widget.Off()
            self._widget = None
        self._sync_widget()
        self._sync_plate()
        self.update_caps()

    # ---- internals ---------------------------------------------------------
    def _apply_plane(self):
        # VTK keeps the side the plane normal points to; we hide that side instead.
        self._plane.SetOrigin(*self.origin)
        self._plane.SetNormal(*(-self.normal))
        self._sync_plate()

    # ---- the visible plate ----------------------------------------------
    # VTK's widget only drew its plane once you started dragging it (on macOS),
    # so the plate is now a normal actor, updated on every change.
    def _plate_polygon(self):
        """Corners of (plane ∩ slightly enlarged model box), in order."""
        pad = 0.15 * (self.hi - self.lo) + 1e-9 * self.diag   # same size as the drag handle
        lo, hi = self.lo - pad, self.hi + pad
        corners = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1])
                            for z in (lo[2], hi[2])])
        edges = [(a, b) for a in range(8) for b in range(a + 1, 8)
                 if bin(a ^ b).count("1") == 1]               # the 12 box edges
        d = (corners - self.origin) @ self.normal
        pts = []
        for a, b in edges:
            if (d[a] <= 0) != (d[b] <= 0):
                t = d[a] / (d[a] - d[b])
                pts.append(corners[a] + t * (corners[b] - corners[a]))
        if len(pts) < 3:
            return None
        pts = np.array(pts)
        c = pts.mean(axis=0)
        u = np.cross(self.normal, [1.0, 0, 0] if abs(self.normal[0]) < 0.9 else [0, 1.0, 0])
        u /= np.linalg.norm(u)
        v = np.cross(self.normal, u)
        order = np.argsort(np.arctan2((pts - c) @ v, (pts - c) @ u))
        return pts[order]

    def _sync_plate(self):
        want = self.enabled and self.show_handle
        poly = self._plate_polygon() if want else None
        if poly is None:
            for a in (self._plate, self._plate_edge):
                if a is not None:
                    a.SetVisibility(False)
            return
        n = len(poly)
        face = pv.PolyData(poly, faces=np.r_[n, np.arange(n)])
        loop = pv.PolyData(poly, lines=np.r_[n + 1, np.arange(n), 0])
        if self._plate is None:
            color = pv.Color(self.scene.accent).float_rgb
            self._plate = self.p.add_mesh(face, color=color, opacity=0.14, lighting=False,
                                          pickable=False, reset_camera=False)
            self._plate_edge = self.p.add_mesh(loop, color=color, opacity=0.9, line_width=1.5,
                                               lighting=False, pickable=False,
                                               reset_camera=False)
        else:
            self._plate.GetMapper().SetInputData(face)
            self._plate_edge.GetMapper().SetInputData(loop)
        self._plate.SetVisibility(True)
        self._plate_edge.SetVisibility(True)

    def _parts_touching_plane(self):
        """Indices of visible parts whose bounding box crosses the plane (cheap test)."""
        dist = (self._box_c - self.origin) @ self.normal          # centre-to-plane
        reach = np.abs(self._box_h) @ np.abs(self.normal)          # box half-thickness
        hit = np.abs(dist) <= reach
        return [i for i in np.flatnonzero(hit) if self.scene.visible[self.scene.names[i]]]

    def _triangulate(self, cut):
        # Exact point merge (hash-based, fast). A tolerance-based merge here was
        # the real bottleneck: on flat cuts its search grid exploded (seconds/part).
        clean = vtkCleanPolyData()
        clean.SetInputData(cut)
        clean.SetTolerance(0.0)
        t = vtkContourTriangulator()
        t.SetInputConnection(clean.GetOutputPort())
        t.TriangulationErrorDisplayOff()
        t.Update()
        return t.GetOutput()

    def _hide_caps(self):
        for a in (self._caps, self._outline, self._vol_cut):
            if a is not None:
                a.SetVisibility(False)

    def _clear_caps(self):
        for a in (self._caps, self._outline, self._vol_cut):
            if a is not None:
                self.p.remove_actor(a, render=False)
        self._caps = self._outline = self._vol_cut = None
        self._cap_part = None

    def _sync_widget(self):
        want = self.enabled and self.show_handle
        if want and self._widget is None:
            pad = 0.15 * (self.hi - self.lo) + 1e-9
            bounds = np.ravel(np.column_stack([self.lo - pad, self.hi + pad]))
            self._widget = self.p.add_plane_widget(
                self._widget_moved, normal=self.normal, origin=self.origin,
                bounds=bounds, factor=1.0, color=self.scene.accent, implicit=True,
                normal_rotation=True, outline_translation=False,
                interaction_event="always", test_callback=False, outline_opacity=0.0)
            self._widget.AddObserver("EndInteractionEvent", lambda *_: self.update_caps())
            # Arrow + centre handle in the accent colour.
            accent = pv.Color(self.scene.accent).float_rgb
            self._widget.GetPlaneProperty().SetColor(accent)
            self._widget.GetPlaneProperty().SetOpacity(0.02)          # grabbable, not drawn:
            self._widget.GetSelectedPlaneProperty().SetColor(accent)   # our plate is the
            self._widget.GetSelectedPlaneProperty().SetOpacity(0.06)  # visible one
            self._widget.GetEdgesProperty().SetOpacity(0.0)    # VTK draws these red
            self._widget.DrawPlaneOn()
        if self._widget is not None:
            if want:
                self._widget.SetOrigin(*self.origin)
                self._widget.SetNormal(*self.normal)
                self._widget.On()
            else:
                self._widget.Off()

    def _widget_moved(self, normal, origin):
        self.origin = np.asarray(origin, dtype=float)
        n = np.asarray(normal, dtype=float)
        self.normal = n / (np.linalg.norm(n) or 1.0)
        self._apply_plane()
        self._hide_caps()
        if self.on_widget_moved:
            self.on_widget_moved(self.origin, self.normal)
