"""The 3D scene: what is drawn and how. No Qt widgets in here.

Takes a Model (from any reader) and a PyVista plotter, and exposes simple
methods the side panel calls: show/hide parts, edges, grid, camera views,
selection, mesh quality, cross-section…

Speed (v2.1.3): all parts are drawn by ONE composite actor (one block per part,
per-block colour and visibility) and all feature edges by another, instead of
one or two actors per part. With hundreds of parts this is several times
faster to rotate. Very heavy models also hide their edge lines while the view
is moving (they come back as soon as you let go).
"""
from __future__ import annotations

import numpy as np
import pyvista as pv
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication
from vtkmodules.vtkCommonCore import vtkSMPTools
from vtkmodules.vtkFiltersCore import vtkAppendPolyData
from vtkmodules.vtkRenderingCore import (
    vtkActor, vtkCellPicker, vtkHardwarePicker, vtkMapper, vtkPolyDataMapper,
)

from ..model import Model
from .background import ImageBackground, is_dark_image, load_image
from .. import transform as xf
from .measure import AXIS_COLORS, Measure
from .cfd_view import FlowView, YplusView
from .quality_view import GHOST_OPACITY, QualityView
from .section import Section

PART_COLORS = [   # no black / very dark colours: they hide the shading
    "#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4",
    "#46f0f0", "#f032e6", "#bcf60c", "#008080", "#9a6324",
    "#fabebe", "#aaffc3", "#e6beff", "#ffd8b1", "#a9a9a9",
    "#ffe119", "#808000", "#5fa8ff", "#ff8c69", "#c49c94",
]
# Let VTK filters (normals, plane cutter, …) use every CPU core.
vtkSMPTools.SetBackend("STDThread")

FEATURE_ANGLE = 30.0        # degrees; sharper creases are drawn as feature edges
SELECT_COLOR = "#0a84ff"    # fallback; the system accent colour is used when known
CLICK_TOLERANCE_PX = 4      # a press+release closer than this is a click, not a drag
AXIS_FONT_DEFAULT = 16       # grid label points (Appearance slider: 10 = original size … 28)
EDGE_WIDTHS = {"thin": 1.0, "medium": 1.5, "thick": 2.0}   # feature edge lines, pixels
AXES_MODES = ("off", "axes", "grid", "both")               # Display ▸ Axes (v2.7.2)

# Viewport colours (background gradient bottom -> top, grid, feature edges)
THEMES = {
    False: dict(bg="#e8ebf0", bg_top="#ffffff", grid="#7a7a80", edge="#111111",    # light
                cut_fill="#d9dde4"),                        # cut volume mesh
    True:  dict(bg="#1c1c1e", bg_top="#3a3a3e", grid="#9a9aa2", edge="#0a0a0a",    # dark
                cut_fill="#6b6e76"),
}


def _label_format(span):
    """printf format for axis numbers: about 3 significant digits over `span`."""
    if not span > 0:
        return "%.2f"
    decimals = int(np.clip(2 - np.floor(np.log10(span)), 0, 6))
    return f"%.{decimals}f"


def _overlay_actor(poly, color, line_width=1.0, point_size=None):
    """Plain unlit actor for the overlay layer (origin marker)."""
    m = vtkPolyDataMapper()
    m.SetInputData(poly)
    m.ScalarVisibilityOff()
    a = vtkActor()
    a.SetMapper(m)
    prop = a.GetProperty()
    prop.SetColor(pv.Color(color).float_rgb)
    prop.SetLineWidth(line_width)
    prop.SetLighting(False)
    if point_size:
        prop.SetRepresentationToPoints()
        prop.SetPointSize(point_size)
        prop.SetRenderPointsAsSpheres(True)
    a.PickableOff()
    return a


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


def _is_dark_color(hex_color):
    r, g, b = pv.Color(hex_color).float_rgb
    return 0.2126 * r + 0.7152 * g + 0.0722 * b < 0.5


def _lighter(hex_color, f=0.30):
    r, g, b = pv.Color(hex_color).float_rgb
    return (r + (1 - r) * f, g + (1 - g) * f, b + (1 - b) * f)


class Scene:
    def __init__(self, plotter: pv.BasePlotter, model: Model, dark: bool = False,
                 accent: str = SELECT_COLOR):
        self.p = plotter
        self.accent = accent        # selection outline + section plane colour
        self.model = model
        self.names = sorted(model.parts, key=str.lower)
        self.colors = {n: PART_COLORS[i % len(PART_COLORS)] for i, n in enumerate(self.names)}
        self.visible = {n: True for n in self.names}
        self.selected_parts: list[str] = []          # multi-selection (parts)
        self.selected_faces: dict[str, set] = {}     # CAD faces (measure mode)
        self.on_pick = None          # UI hook: called with the selected part list after a click

        # Defaults: meshes show element edges, CAD shows sharp (feature) edges.
        self.state = dict(grid=True, parallel=True, mesh_edges=not model.is_cad,
                          feature_edges=model.is_cad, bbox=False, origin=False,
                          original=False, shading=True, faces=True)
        self._dark = dark
        self._ui_dark = dark
        self.bg_mode = ("default", None)          # set by Appearance
        self._origin_actors = []                  # NEW (v2.6): marker at (0, 0, 0)
        self._orig_points = None                  # v2.8.1: file points, kept at the 1st edit
        self._flipped = {}                        # part -> faces flipped (mirrored)
        self._edit_history = []                   # [((R, t) before, label)]
        self._original_actor = None               # grey edges of the file as opened
        self._alias = {}                          # v2.8.3: file's part name -> new name
        self._last_view = None                    # NEW (v2.6): (view, flipped?, camera)
        self._bg_image = None                     # ImageBackground when a picture is shown
        self.axis_font = AXIS_FONT_DEFAULT        # set by Appearance
        self.edge_width = EDGE_WIDTHS["thin"]     # NEW (v2.5.3): feature edge lines (Appearance)
        self.hide_edges_moving = True             # NEW (v2.5.3): smooth rotation (Appearance)
        self.grid_lines = True                    # grid lines on the walls behind the model
        self.axis_lines = True                    # axis frame, ticks, numbers and titles
        self._surf = self._surf_map = None      # composite actor/mapper: all parts
        self._edges = self._edges_map = None    # composite actor/mapper: feature edges
        self._highlights = {}                   # part name -> outline actor
        self._face_actors = []                  # selected CAD faces (fill + rim)
        self._grid_actor = None
        self._bbox_actor = None
        self._moving = False
        self._ghost = False                       # v2.9: see-through while bad cells show

        vtkMapper.SetResolveCoincidentTopologyToPolygonOffset()  # edges drawn over faces
        self._build_surfaces()
        self.section = Section(self)
        self.quality = QualityView(self)          # v2.9: Cell quality overlays
        self.flow = FlowView(self)                # v2.10: CFD ▸ Show flow vectors
        self.yplus_view = YplusView(self)         # v2.11.3: CFD ▸ Colour by y+
        self.cfd_settings = None                  # v2.10: CFD section (remembered per file)
        self.inflation_settings = None            # v2.11: CFD mode (CAD), remembered too
        self.measure = Measure(self)
        self.set_theme(dark, render=False)
        self.set_parallel(self.state["parallel"])
        self.set_feature_edges(self.state["feature_edges"], render=False)
        self._setup_picking()
        self._setup_interaction_lod()
        self.view("iso")

    # ---- parts (one composite actor) -------------------------------------
    def _block(self, name):
        return self.names.index(name) + 1          # block 0 is the root

    def _build_surfaces(self):
        # Normals computed here once (split at sharp CAD corners so they stay crisp).
        blocks = pv.MultiBlock()
        for n in self.names:
            blocks[n] = self.model.parts[n].compute_normals(
                cell_normals=False, split_vertices=self.model.is_cad,
                feature_angle=FEATURE_ANGLE, consistent_normals=False)
        self._surf, self._surf_map = self.p.add_composite(
            blocks, color="#bbbbbb", smooth_shading=True, show_edges=self.state["mesh_edges"],
            edge_color="#202020", reset_camera=False, pickable=True)
        self._surf_map.SetStatic(True)            # geometry never changes in place
        self._surf.GetProperty().SetLighting(self.state["shading"])
        self._surf.GetProperty().SetOpacity(GHOST_OPACITY if self._ghost else 1.0)
        self._apply_lines()                       # v2.8.4: edges-only look survives rebuilds
        for n in self.names:
            self._apply_block(n)

    def _apply_block(self, name):
        attr = self._surf_map.block_attr[self._block(name)]
        attr.visible = self.visible[name]
        attr.color = _lighter(self.colors[name]) if name in self.selected_parts \
            else pv.Color(self.colors[name]).float_rgb
        if self._edges_map is not None:
            self._edges_map.block_attr[self._block(name)].visible = self.visible[name]

    def set_color(self, names, color, render=True):
        """NEW (v2.8.6): new colour for parts (right-click ▸ Colour…)."""
        hex_color = pv.Color(color).hex_rgb
        for n in names:
            if n in self.colors:
                self.colors[n] = hex_color
                self._apply_block(n)
        self.section.recolor()                       # filled cut faces
        if render:
            self.p.render()

    def set_visible(self, name, on, render=True):
        self.visible[name] = bool(on)
        self._apply_block(name)
        self._refresh_highlights()
        if render:
            self._after_visibility_change()

    def isolate(self, names):
        """Show only these part(s) (a name or a list) and zoom to them."""
        keep = {names} if isinstance(names, str) else set(names)
        for n in self.names:
            self.set_visible(n, n in keep, render=False)
        self._after_visibility_change()
        self.zoom_to(names)

    def zoom_to(self, names):
        names = [names] if isinstance(names, str) else list(names)
        b = np.array([self.model.parts[n].bounds for n in names if n in self.model.parts])
        if len(b):
            self.p.reset_camera(bounds=[b[:, 0].min(), b[:, 1].max(), b[:, 2].min(),
                                        b[:, 3].max(), b[:, 4].min(), b[:, 5].max()])
            self.p.render()

    def info(self, name):
        poly = self.model.parts[name]
        return f"{poly.n_cells:,} faces · {poly.n_points:,} points"

    def _after_visibility_change(self):
        if self.section.enabled:
            self.section.update_caps()      # also renders
        else:
            self.p.render()

    # ---- selection: click, ⌘/⇧-click to add (multi-select) --------------------
    @property
    def selected(self):
        """First selected part (or None) — for code that wants just one."""
        return self.selected_parts[0] if self.selected_parts else None

    def select(self, name, render=True):
        """Select one part (None clears). Does not call on_pick."""
        self.set_selection([name] if name else [], render=render)

    def set_selection(self, names, render=True, notify=False):
        old = set(self.selected_parts)
        self.selected_parts = [n for n in dict.fromkeys(names) if n in self.visible]
        for n in old ^ set(self.selected_parts):
            self._apply_block(n)
        self._refresh_highlights()
        if self.measure.mode == "area":
            self.measure._changed()
        if notify and self.on_pick:
            self.on_pick(list(self.selected_parts))
        if render:
            self.p.render()

    def toggle_part(self, name):
        sel = list(self.selected_parts)
        sel.remove(name) if name in sel else sel.append(name)
        self.set_selection(sel)

    def clear_face_selection(self, render=True):
        self.selected_faces = {}
        self._refresh_face_overlay()
        if render:
            self.p.render()

    def toggle_face(self, name, face_id, additive):
        if not additive:
            self.selected_faces = {}
        ids = self.selected_faces.setdefault(name, set())
        ids.symmetric_difference_update({face_id})
        self._refresh_face_overlay()
        self.p.render()

    def _setup_picking(self):
        # Hardware picking: respects hidden parts and the section cut.
        self._hw_picker = vtkHardwarePicker()
        self._picker = vtkCellPicker()             # fallback
        self._picker.SetTolerance(0.0005)
        self._press = None
        iren = self.p.iren
        iren.add_observer("LeftButtonPressEvent", self._on_press)
        iren.add_observer("LeftButtonReleaseEvent", self._on_release)
        # right-click (without dragging) -> context menu for the part under it
        self.on_context = None           # UI hook: (names to act on, part under the cursor)
        self._rpress = None
        iren.add_observer("RightButtonPressEvent", self._on_rpress)
        iren.add_observer("RightButtonReleaseEvent", self._on_rrelease)
        # a click that closes a pop-up menu reaches the 3D view, but its
        # release goes to the menu, so VTK kept zooming / rotating with no button held.
        # On every mouse move: no button down -> end whatever drag VTK thinks is running.
        tag = iren.interactor.AddObserver("MouseMoveEvent", lambda *_: self.end_stuck_drag(), 10.0)
        iren.interactor.GetCommand(tag).PassiveObserverOn()   # still called while VTK holds focus

    def end_stuck_drag(self):
        style = self.p.iren.interactor.GetInteractorStyle()
        if style is None or style.GetState() == 0:           # 0 = VTKIS_NONE
            return
        if QGuiApplication.mouseButtons() != Qt.NoButton:
            return                                           # a real drag
        for up in (style.OnLeftButtonUp, style.OnMiddleButtonUp, style.OnRightButtonUp):
            up()
        self._press = self._rpress = None

    def _on_rpress(self, *_):
        self._rpress = self.p.iren.get_event_position()

    def _on_rrelease(self, *_):
        if self._rpress is None or self.on_context is None:
            return
        (x0, y0), (x1, y1) = self._rpress, self.p.iren.get_event_position()
        self._rpress = None
        if abs(x1 - x0) > CLICK_TOLERANCE_PX or abs(y1 - y0) > CLICK_TOLERANCE_PX:
            return                          # right-drag zooms; not a click
        name = self.pick(x1, y1)
        if name and name in self.selected_parts and len(self.selected_parts) > 1:
            names = list(self.selected_parts)     # act on the whole selection
        else:
            names = [name] if name else []
        self.on_context(names, [name] if name else [])   # NEW (v2.4.3): + clicked part

    def _on_press(self, *_):
        self._press = self.p.iren.get_event_position()

    def _on_release(self, *_):
        if self._press is None:
            return
        (x0, y0), (x1, y1) = self._press, self.p.iren.get_event_position()
        self._press = None
        if abs(x1 - x0) > CLICK_TOLERANCE_PX or abs(y1 - y0) > CLICK_TOLERANCE_PX:
            return                          # it was a rotate/drag, not a click
        vi = self.p.iren.interactor
        self.click(x1, y1, additive=bool(vi.GetShiftKey() or vi.GetControlKey()))

    def click(self, x, y, additive=False):
        """What a click at display (x, y) does, depending on the measure mode."""
        name, cell, pos = self.pick_full(x, y)
        m = self.measure
        if m.mode in ("distance", "point"):
            m.add_point(pos, name, cell)
            return
        if m.mode == "angle":                        # v2.9
            m.add_face(pos, name, cell)
            return
        if m.mode == "area" and m.pick_faces and name is None and self.selected_faces:
            self.clear_face_selection()              # NEW (v2.5.4): click outside -> deselect
            m._changed()
            return
        if m.mode == "area" and m.pick_faces and name and cell is not None \
                and "face_id" in self.model.parts[name].cell_data:
            self.toggle_face(name, int(self.model.parts[name].cell_data["face_id"][cell]),
                             additive)
            m._changed()
            return
        if additive and name:
            self.toggle_part(name)
        else:
            self.select(name)
        if self.on_pick:
            self.on_pick(list(self.selected_parts))

    def pick(self, x, y):
        """Part name under the display position (x, y), or None."""
        return self.pick_full(x, y)[0]

    def pick_full(self, x, y):
        """(part name, cell id in that part or None, 3D point) under (x, y)."""
        hit = self._hit(self._hw_picker, self._hw_picker.Pick(x, y, 0, self.p.renderer))
        if hit[0] is not None:
            return hit
        # Something else was in front (e.g. the section handle): try a ray pick
        # against parts and cut faces only, ignoring hidden parts.
        self._picker.InitializePickList()
        self._picker.AddPickList(self._surf)
        for a in self.section.cap_actors():
            self._picker.AddPickList(a)
        self._picker.PickFromListOn()
        # Edges only (v2.8.4): the faces aren't drawn, but clicking them still selects.
        hidden = not self._surf.GetVisibility() or \
            self._surf.GetProperty().GetRepresentation() != 2
        if hidden:
            self._surf.VisibilityOn()
            self._surf.GetProperty().SetRepresentationToSurface()
        try:
            return self._hit(self._picker, self._picker.Pick(x, y, 0, self.p.renderer))
        finally:
            if hidden:
                self._apply_lines()

    def _hit(self, picker, ok):
        if not ok:
            return None, None, None
        actor, pos = picker.GetActor(), np.array(picker.GetPickPosition())
        if actor is self._surf:
            i = picker.GetFlatBlockIndex() - 1
            if 0 <= i < len(self.names) and self.visible[self.names[i]]:
                return self.names[i], int(picker.GetCellId()), pos
            return None, None, None
        name = self.section.cap_owner(actor, picker.GetCellId())
        return (name, None, pos) if name else (None, None, None)

    def _refresh_highlights(self):
        """Blue outline (silhouette + sharp edges) on every selected, visible part."""
        want = {n for n in self.selected_parts if self.visible.get(n)}
        for n in list(self._highlights):
            if n not in want:
                self.p.remove_actor(self._highlights.pop(n), render=False)
        for n in want - set(self._highlights):
            a = self.p.add_silhouette(self.model.parts[n], color=self.accent, line_width=3.5,
                                      feature_angle=FEATURE_ANGLE)
            a.SetPickable(False)
            self.section.clip(a)
            self._highlights[n] = a

    def _refresh_face_overlay(self):
        for a in self._face_actors:
            self.p.remove_actor(a, render=False)
        self._face_actors = []
        pieces = []
        for n, ids in self.selected_faces.items():
            poly = self.model.parts.get(n)
            if ids and poly is not None and self.visible.get(n):
                mask = np.isin(poly.cell_data["face_id"], list(ids))
                pieces.append(poly.extract_cells(np.flatnonzero(mask)))
        if not pieces:
            return
        mesh = pv.merge(pieces) if len(pieces) > 1 else pieces[0]
        fill = self.p.add_mesh(mesh, color=self.accent, opacity=0.85, pickable=False,
                               reset_camera=False)
        # Drawn just in front of the part so it doesn't flicker.
        fill.GetMapper().SetRelativeCoincidentTopologyPolygonOffsetParameters(-2, -2)
        self._face_actors.append(fill)
        rim = mesh.extract_feature_edges(boundary_edges=True, feature_edges=False,
                                         manifold_edges=False, non_manifold_edges=False)
        if rim.n_cells:
            self._face_actors.append(self.p.add_mesh(
                rim, color=self.accent, line_width=3.5, lighting=False, pickable=False,
                reset_camera=False))
        for a in self._face_actors:
            self.section.clip(a)

    # ---- screenshots with chosen size + background --------------------
    def screenshot(self, path, scale=2, background="current"):
        """Save a PNG at `scale`× the view size. background: "current" (exactly
        as on screen) | "transparent" (PNG with alpha).

        The image is rendered in a separate off-screen window at the full target
        size, with text and line widths scaled by the same factor, so it looks
        exactly like the view, only sharper. (VTK's built-in tiled zoom drew the
        axis labels far too big / the grid labels far too small.)"""
        k = max(1, int(scale))
        # Whether grid/axes are drawn light-on-dark. (v2.5.5: light / dark / custom
        # colour backgrounds removed — "current" follows Appearance.)
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
            off.add_axes(line_width=3 * k, color=t["grid"], viewport=self._axes_viewport())
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
        actors = [self._surf, self._edges, *self._highlights.values(), *self._face_actors,
                  *sec.cap_actors(), sec._outline, sec._plate, sec._plate_edge,
                  self._bbox_actor]
        return [a for a in actors if a is not None and a.GetVisibility()]

    # ---- smooth rotation: edges off while the view moves --------------------------
    def _setup_interaction_lod(self):
        style = self.p.iren.interactor.GetInteractorStyle()
        if style is not None:
            style.AddObserver("StartInteractionEvent", lambda *_: self._set_moving(True))
            style.AddObserver("EndInteractionEvent", lambda *_: self._set_moving(False))
        # NEW (v2.5.4): the scroll wheel / trackpad zooms in single steps (each one a
        # complete start-zoom-end), so edges would flash back between steps. Treat a
        # burst of zoom steps as one movement that ends 0.3 s after the last step.
        self._zooming = False
        self._zoom_timer = QTimer()
        self._zoom_timer.setSingleShot(True)
        self._zoom_timer.setInterval(300)
        self._zoom_timer.timeout.connect(self._zoom_ended)
        iren = self.p.iren.interactor
        for ev in ("MouseWheelForwardEvent", "MouseWheelBackwardEvent", "MouseWheelLeftEvent",
                   "MouseWheelRightEvent", "StartPinchEvent", "PinchEvent", "EndPinchEvent"):
            iren.AddObserver(ev, self._zoom_step, 10.0)    # before the style draws the frame

    def _zoom_step(self, *_):
        if not self.hide_edges_moving:
            return
        self._zooming = True
        self._set_moving(True)
        self._zoom_timer.start()                     # restart: wait for the last step

    def _zoom_ended(self):
        self._zooming = False
        self._set_moving(False)

    def _set_moving(self, moving):
        # any model size, switchable in Appearance (v2.5.3: was > 1.5 M triangles only)
        if moving == self._moving or (moving and not self.hide_edges_moving):
            return
        if not moving and self._zooming:
            return                                   # still zooming: keep edges off
        self._moving = moving
        # Lines are the costliest thing to draw on macOS: drop them while moving
        # (v2.8.4: except feature edges in "Edges only", the only thing left to see).
        self._apply_lines()
        self.section.set_moving(moving)            # v2.7: cut mesh edges too
        if not moving:
            self.p.render()

    # ---- mesh quality (STEP) -------------------------------------------------
    @property
    def can_retessellate(self):
        return self.model.retessellate is not None

    def replace_parts(self, parts, level):
        """Swap in a new tessellation, keeping colours, visibility, selection, section."""
        cam = self.p.camera_position
        for a in (self._surf, self._edges):
            if a is not None:
                self.p.remove_actor(a, render=False)
        self._surf = self._surf_map = self._edges = self._edges_map = None
        parts = {self._alias.get(k, k): v for k, v in parts.items()}   # keep renames
        self.model.parts = parts
        self.model.quality = level
        self.names = sorted(parts, key=str.lower)
        for n in self.names:
            self.colors.setdefault(n, PART_COLORS[len(self.colors) % len(PART_COLORS)])
            self.visible.setdefault(n, True)
        self.selected_parts = [n for n in self.selected_parts if n in parts]
        self.selected_faces = {}                     # face ids change with the mesh
        for a in self._highlights.values():
            self.p.remove_actor(a, render=False)
        self._highlights = {}
        self._build_surfaces()
        self.set_feature_edges(self.state["feature_edges"], render=False)
        self.section.rebuild()
        self._refresh_face_overlay()
        self.set_selection(self.selected_parts, render=False)
        self.measure._changed()
        self.p.camera_position = cam
        self.p.render()

    # ---- NEW (v2.8.3): rename a part (any file type; Export writes the new names) ----
    @property
    def renamed(self):
        return any(k != v for k, v in self._alias.items())

    @property
    def has_changes(self):
        """Edits or renames that only live in memory until exported."""
        return self.model.edited or self.renamed

    def rename_part(self, old, new):
        """True when renamed. Same place in the composite actor, so nothing is rebuilt."""
        new = new.strip()
        if not new or new == old or old not in self.model.parts or new in self.model.parts:
            return False

        def rekey(d):
            if d and old in d:
                items = [(new if k == old else k, v) for k, v in d.items()]
                d.clear()
                d.update(items)
        for d in (self.model.parts, self.colors, self.visible, self.selected_faces,
                  self._highlights, self._flipped, self._orig_points):
            rekey(d)
        self.names[self.names.index(old)] = new       # same block index
        self.selected_parts = [new if n == old else n for n in self.selected_parts]
        orig = next((k for k, v in self._alias.items() if v == old), old)
        self._alias[orig] = new                       # re-meshed STEP parts keep it
        self.measure._changed()
        return True

    # ---- Edit section: rotate / mirror (v2.8), move + undo + original (v2.8.1) -------
    def apply_edit(self, r, t=(0.0, 0.0, 0.0), label=""):
        """Rotate / mirror (R, 3×3) then move (t) every part and the volume
        cells. Returns False for exact CAD (STEP, IGES, BREP), which can't be edited."""
        if not self.model.editable:
            return False
        state = (self.model.transform, self.model.offset)
        self._edit_history.append((state, label))
        self._set_edit_state(*xf.compose((r, t), state))
        return True

    def undo_edit(self):
        """Back one step (exact: everything is recomputed from the file's points)."""
        if self._edit_history:
            (r, t), _ = self._edit_history.pop()
            self._set_edit_state(r, t)

    def reset_edits(self):
        if self.model.edited:
            self._edit_history.clear()
            self._set_edit_state(xf.identity(), np.zeros(3))

    @property
    def edit_labels(self):
        """v2.8.4: every change so far, oldest first (the Edit section lists them)."""
        return [label for _, label in self._edit_history]

    def _set_edit_state(self, r, t):
        if self._orig_points is None:               # first edit: keep the file's points
            self._orig_points = {n: np.array(p.points) for n, p in self.model.parts.items()}
        old = (self.model.transform, self.model.offset)
        for n, poly in self.model.parts.items():
            self._flipped[n] = xf.set_surface(poly, self._orig_points[n], r, t,
                                              self._flipped.get(n, False))
        self.model.transform, self.model.offset = np.asarray(r, dtype=float), np.asarray(t, float)
        self.section.follow_edit(xf.delta(old, (r, t)))   # plane + volume cells follow
        self.measure.forget_points()                # picked points were in the old place
        self.quality.after_edit()                   # v2.9: bad cells move along
        self.replace_parts(self.model.parts, self.model.quality)   # keeps the camera
        self.refresh_grid(render=False)             # new bounds
        if self._bbox_actor is not None:
            self.p.remove_actor(self._bbox_actor, render=False)
            self._bbox_actor = None
            self.set_bbox(self.state["bbox"], render=False)
        if self.state.get("origin"):
            self._build_origin()
        self._sync_original()
        self.p.render()

    def set_show_original(self, on, render=True):
        """Grey feature edges of the file as it was opened, to compare with the edits."""
        self.state["original"] = bool(on)
        self._sync_original()
        if render:
            self.p.render()

    def _sync_original(self):
        want = self.state.get("original") and self.model.edited
        if want and self._original_actor is None:
            app = vtkAppendPolyData()
            for n, poly in self.model.parts.items():
                pts = self._orig_points[n] if self._orig_points else poly.points
                src = pv.PolyData(np.asarray(pts), faces=poly.faces)
                app.AddInputData(src.extract_feature_edges(
                    feature_angle=FEATURE_ANGLE, boundary_edges=True, feature_edges=True,
                    manifold_edges=False, non_manifold_edges=False))
            app.Update()
            self._original_actor = self.p.add_mesh(
                pv.wrap(app.GetOutput()), color=THEMES[self._dark]["grid"], opacity=0.7,
                line_width=1.5, lighting=False, pickable=False, reset_camera=False)
        if self._original_actor is not None:
            self._original_actor.SetVisibility(bool(want))

    # ---- display options ----------------------------------------------
    def set_parallel(self, on, render=True):
        self.state["parallel"] = bool(on)
        if on:
            self.p.enable_parallel_projection()
        else:
            self.p.disable_parallel_projection()
        if render:
            self.p.render()

    def set_shading(self, on, render=True):
        """NEW (v2.8.2): lights on (shaded, 3D look) or off (flat part colours, no
        light or shadow) for the parts and the filled cut faces."""
        self.state["shading"] = bool(on)
        self._surf.GetProperty().SetLighting(bool(on))
        self.section.sync_shading()
        if render:
            self.p.render()

    def _apply_lines(self):
        """Faces, mesh edges and feature edges from the toolbar toggles + the moving
        state. Faces hidden (v2.8.4): mesh edges become a wireframe (still hidden while
        moving); feature edges stay on while moving."""
        if self._surf is None:
            return
        eo, mesh, moving = not self.state["faces"], self.state["mesh_edges"], self._moving
        prop = self._surf.GetProperty()
        if eo:
            prop.SetRepresentationToWireframe()
            prop.SetEdgeVisibility(False)
            self._surf.SetVisibility(mesh and not moving)
        else:
            prop.SetRepresentationToSurface()
            self._surf.SetVisibility(True)
            prop.SetEdgeVisibility(mesh and not moving)
        if self._edges is not None:
            self._edges.SetVisibility(self.state["feature_edges"] and (eo or not moving))
        quality = getattr(self, "quality", None)
        if quality is not None and quality.hides_surface:   # coloured copy shown instead
            self._surf.SetVisibility(False)
        yv = getattr(self, "yplus_view", None)              # v2.11.4: y+ colours follow too
        if yv is not None:
            yv.apply_lines()

    def set_ghost(self, on, render=True):
        """NEW (v2.9): faces see-through, so the bad cells inside show."""
        self._ghost = bool(on)
        self._surf.GetProperty().SetOpacity(GHOST_OPACITY if on else 1.0)
        if render:
            self.p.render()

    def set_faces(self, on, render=True):
        """Show or hide the faces, keeping the edges (v2.8.4 "Edges only", v2.8.6 Faces)."""
        self.state["faces"] = bool(on)
        self._apply_lines()
        if render:
            self.p.render()

    def set_mesh_edges(self, on, render=True):
        self.state["mesh_edges"] = bool(on)
        self._apply_lines()
        self.section.sync_cut_edges()              # v2.7.2: the cut mesh follows this switch
        if render:
            self.p.render()

    def set_feature_edges(self, on, render=True):
        self.state["feature_edges"] = bool(on)
        if on and self._edges is None:
            self._build_edges()
        self._apply_lines()
        if render:
            self.p.render()

    def _build_edges(self):
        blocks = pv.MultiBlock()
        for n in self.names:
            blocks[n] = self.model.parts[n].extract_feature_edges(
                feature_angle=FEATURE_ANGLE, boundary_edges=True, feature_edges=True,
                manifold_edges=False, non_manifold_edges=False)
        self._edges, self._edges_map = self.p.add_composite(
            blocks, color=THEMES[self._dark]["edge"], line_width=self.edge_width, lighting=False,
            pickable=False, reset_camera=False)
        self._edges_map.SetStatic(True)
        for n in self.names:
            self._edges_map.block_attr[self._block(n)].visible = self.visible[n]
        self.section.clip(self._edges)

    # ---- NEW (v2.6): origin marker ---------------------------------------------------
    def set_origin(self, on, render=True):
        """A dot at (0, 0, 0) with short X / Y / Z arrows (red / green / blue),
        drawn on top of the model so it shows even inside a part."""
        self.state["origin"] = bool(on)
        self._build_origin()
        if render:
            self.p.render()

    def origin_actors(self):
        return list(self._origin_actors)

    def _build_origin(self):
        layer = self.measure._layer()             # the overlay the measure markers use
        for a in self._origin_actors:
            layer.RemoveActor(a)
        self._origin_actors = []
        if not self.state.get("origin"):
            return
        length = 0.06 * self._diag()
        for axis, color in zip(np.eye(3), AXIS_COLORS):
            self._origin_actors.append(_overlay_actor(
                pv.Line((0.0, 0.0, 0.0), axis * length), color, line_width=2.5))
        dot = _overlay_actor(pv.PolyData(np.zeros((1, 3))),
                             "#f2f2f7" if self._dark else "#1c1c1e", point_size=10)
        self._origin_actors.append(dot)
        for a in self._origin_actors:
            layer.AddActor(a)

    def set_bbox(self, on, render=True):
        self.state["bbox"] = bool(on)
        if on and self._bbox_actor is None:
            self._bbox_actor = self.p.add_bounding_box(color=THEMES[self._dark]["grid"],
                                                       line_width=1, reset_camera=False)
        if self._bbox_actor is not None:
            self._bbox_actor.SetVisibility(bool(on))
        if render:
            self.p.render()

    # ---- camera --------------------------------------------------------
    def view(self, which):
        """NEW (v2.6): pressing X, Y or Z again without moving the camera in
        between looks from the opposite side (X -> -X -> X …). Iso never flips."""
        last = self._last_view
        flip = (which != "iso" and last is not None and last[0] == which
                and np.allclose(self._camera_state(), last[2], atol=1e-6 * self._diag()))
        negative = (not last[1]) if flip else False
        {"iso": self.p.view_isometric, "x": self.p.view_yz, "y": self.p.view_xz,
         "z": self.p.view_xy}[which](negative=negative, render=False)
        self.fit()
        self._last_view = (which, negative, self._camera_state())

    def _camera_state(self):
        c = self.p.camera
        return np.concatenate([c.position, c.focal_point, c.up, [c.parallel_scale]])

    def _diag(self):
        b = np.asarray(self.model_bounds(), dtype=float).reshape(3, 2)
        return float(np.linalg.norm(b[:, 1] - b[:, 0])) or 1.0

    def fit(self):
        # Model bounds only (not the section handle or the grid).
        self.p.reset_camera(bounds=self.model_bounds())
        self.p.render()

    # ---- theme ---------------------------------------------------------
    @property
    def edge_color(self):
        return THEMES[self._dark]["edge"]

    def theme_colors(self):
        """Colours for the background actually shown (light or dark set)."""
        return THEMES[self._dark]

    # ---- Appearance: axis labels, edge lines, grid lines ----------------------------
    def set_axis_font(self, size, rebuild=True):
        size = int(size)                              # points
        if size != self.axis_font:
            self.axis_font = size
            if rebuild:
                self.set_theme(self._ui_dark)         # rebuilds the grid + axes

    def set_edge_options(self, width=None, hide_while_moving=None, render=True):
        """NEW (v2.5.3): feature edge thickness ("thin" / "medium" / "thick" or px)
        and whether lines are hidden while the view moves."""
        if hide_while_moving is not None:
            self.hide_edges_moving = bool(hide_while_moving)
        if width is not None:
            self.edge_width = float(EDGE_WIDTHS.get(width, width))
            if self._edges is not None:
                self._edges.GetProperty().SetLineWidth(self.edge_width)
            if render:
                self.p.render()

    def set_axes_mode(self, mode, rebuild=True, render=True):
        """NEW (v2.7.2), one control instead of three (Display ▸ Grid + Appearance
        ▸ Grid lines / Axis lines):
            "off"   nothing
            "axes"  axis frame, ticks, numbers and titles
            "grid"  grid lines on the walls behind the model only
            "both"  axes + grid lines (default)"""
        mode = mode if mode in AXES_MODES else "both"
        lines, axes = mode in ("grid", "both"), mode in ("axes", "both")
        changed = (lines, axes) != (self.grid_lines, self.axis_lines)
        self.grid_lines, self.axis_lines = lines, axes
        self.state["grid"] = mode != "off"
        if changed and rebuild:
            self.refresh_grid(render=False)
        elif self._grid_actor is not None:
            self._grid_actor.SetVisibility(self.state["grid"])
        if render:
            self.p.render()

    # ---- the grid / axes box -----------------------------------------------------------
    def refresh_grid(self, render=True):
        """Rebuild the grid (it can't be recoloured or relabelled in place).
        Called on theme / Appearance changes and when the display unit changes."""
        self.p.remove_bounds_axes()
        self._grid_actor = self._add_grid(self.p, THEMES[self._dark]["grid"])
        self._grid_actor.SetVisibility(self.state["grid"])
        if render:
            self.p.render()

    def _add_grid(self, plotter, color, k=1):
        """Grid + axes on `plotter` (the view, or an off-screen screenshot at k×).
        Fixed to the model's bounds, so the section handle can't stretch it.
        NEW (v2.5.6): numbers in the unit chosen in the toolbar and titles like
        "X Axis (mm)"; with Axis lines off, numbers and titles go too."""
        b = np.asarray(self.model_bounds(), dtype=float)
        s, unit = self.measure.unit_scale()
        kw = dict(color=color, font_size=self.axis_font * k, grid=self._grid_mode(),
                  location="outer", ticks="both", bounds=list(b))
        if not self.axis_lines:
            kw.update(xtitle=" ", ytitle=" ", ztitle=" ")
            # (not show_*labels=False: PyVista then drops the ticks the grid lines use)
        else:
            suffix = f" ({unit})" if unit else ""
            kw.update(xtitle=f"X Axis{suffix}", ytitle=f"Y Axis{suffix}", ztitle=f"Z Axis{suffix}")
            if s != 1.0:                                  # converted: label the real values
                span = np.ptp(b.reshape(3, 2), axis=1).max() * s
                kw.update(axes_ranges=list(b * s), fmt=_label_format(span))
        g = plotter.show_grid(**kw)
        if not self.axis_lines:                   # numbers, frame lines and tick marks
            for i, ax in enumerate("XYZ"):
                g.GetLabelTextProperty(i).SetOpacity(0.0)
                getattr(g, f"Get{ax}AxesLinesProperty")().SetOpacity(0.0)
                getattr(g, f"Set{ax}AxisTickVisibility")(False)
                getattr(g, f"Set{ax}AxisMinorTickVisibility")(False)
        return g

    def _grid_mode(self):
        return "back" if self.grid_lines else False

    def _axes_viewport(self):
        """XYZ corner widget grows a little with the label size."""
        side = min(0.16 * (self.axis_font / 10) ** 0.5, 0.26)     # 10 pt = original 0.16
        return (1.0 - side * 0.875, 0.0, 1.0, side)

    # ---- 3D background chosen in Appearance -----------------------------------
    def set_background(self, mode="default", value=None, render=True):
        """mode: "default" (theme gradient) | "color" ("#RRGGBB") | "image" (path)."""
        if mode == "image" and not value:
            mode = "default"
        self.bg_mode = (mode, value)
        self.set_theme(self._ui_dark, render=render)

    def set_theme(self, dark, render=True, accent=None):
        self._ui_dark = bool(dark)                    # the app's light / dark mode
        mode, value = self.bg_mode
        img = self._background_image(value) if mode == "image" else None
        # Grid, axes and edges follow the background actually shown.
        if mode == "color":
            self._dark = _is_dark_color(value)
        elif img is not None:
            self._dark = is_dark_image(img)
        else:
            self._dark = self._ui_dark
        if accent and accent != self.accent:
            self.accent = accent
            for a in self._highlights.values():
                a.GetProperty().SetColor(pv.Color(accent).float_rgb)
            self.section.set_accent(accent)
        t = THEMES[self._dark]
        if mode == "color":
            self.p.set_background(value)
        else:
            self.p.set_background(t["bg"], top=t["bg_top"])
        self._apply_background_image(img)
        if self._edges is not None:
            self._edges.GetProperty().SetColor(pv.Color(t["edge"]).float_rgb)
        self.refresh_grid(render=False)
        self.p.hide_axes()
        self.p.add_axes(line_width=3, color=t["grid"], viewport=self._axes_viewport())
        if self._bbox_actor is not None:
            self._bbox_actor.GetProperty().SetColor(pv.Color(t["grid"]).float_rgb)
        if self.state.get("origin"):
            self._build_origin()                   # dot colour follows the background
        self.section.restyle()                     # v2.7: cut mesh + outline colours
        if self._original_actor is not None:       # v2.8.1: grey "original" edges
            self._original_actor.GetProperty().SetColor(pv.Color(t["grid"]).float_rgb)
        if render:
            self.p.render()

    def _background_image(self, path):
        """Pixels of the chosen picture (cached); None if it can't be read."""
        cache = getattr(self, "_bg_cache", (None, None))
        if cache[0] != path:
            try:
                cache = (path, load_image(path))
            except Exception as exc:                  # unreadable: keep the gradient
                print(f"background image failed: {exc}")
                cache = (path, None)
            self._bg_cache = cache
        return cache[1]

    def _apply_background_image(self, arr):
        old = getattr(self, "_bg_image", None)
        if old is not None and old.arr is arr:
            return
        if old is not None:
            old.detach()
        self._bg_image = ImageBackground(self.p.renderer, arr) if arr is not None else None

    # ---- internals -----------------------------------------------------
    def model_bounds(self):
        b = np.array([p.bounds for p in self.model.parts.values()])
        return [b[:, 0].min(), b[:, 1].max(), b[:, 2].min(), b[:, 3].max(),
                b[:, 4].min(), b[:, 5].max()]

    def clippable_actors(self):
        """Everything the section plane should cut."""
        return [self._surf, self._edges, *self._face_actors, *self._highlights.values(),
                *self.quality.actors(), *self.yplus_view.actors()]
