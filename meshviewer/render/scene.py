"""The 3D scene: what is drawn and how. No Qt widgets in here.

Takes a Model (from any reader) and a PyVista plotter, and exposes simple methods the
side panel calls. This file: the parts (their actors, colour, visibility), the
selection and its outline, and the Display toggles (faces, mesh edges, feature edges).
The rest of the Scene is in its neighbours, one subject each:

    picking.py      clicks: the part / face / point under the mouse, right-click menu
    camera.py       views, fit, 2D lock, lines hidden while the view moves
    editing.py      new mesh quality, rename, rotate / mirror / move + undo
    appearance.py   theme, background, grid and axes, origin, bounding box
    screenshot.py   Save Screenshot
    style.py        colours and sizes

Speed:
  - all parts are drawn by ONE composite actor (one block per part, per-block colour
    and visibility), all feature edges by another and the selection's outline by a
    third, instead of actors per part: several times faster with hundreds of parts;
  - edge lines (and the outline of a heavy selection) are hidden while the view moves;
  - p.render() only says a frame is due (gui/viewport.py draws once per event), so
    methods here render freely.
"""
from __future__ import annotations

import numpy as np
import pyvista as pv
from vtkmodules.vtkFiltersCore import vtkAppendPolyData
from vtkmodules.vtkFiltersHybrid import vtkPolyDataSilhouette
from vtkmodules.vtkRenderingCore import vtkActor, vtkMapper, vtkPolyDataMapper

from meshviewer.core.model import Model
from meshviewer.core.polys import bare, one_thread, SMALL_PART
from meshviewer.render.appearance import Appearance
from meshviewer.render.camera import Camera
from meshviewer.render.colorbar import ColorBar
from meshviewer.render.editing import Editing
from meshviewer.render.elements import Elements
from meshviewer.render.measure import Measure
from meshviewer.render.overlays import CutLineView, FlowView, ResultsView, WallView, YplusView
from meshviewer.render.layers import Overlays
from meshviewer.render.picking import Picking
from meshviewer.render.probes import ProbeMarks
from meshviewer.render.quality_overlay import GHOST_OPACITY, QualityView
from meshviewer.render.screenshot import Screenshots
from meshviewer.render.section import Section
from meshviewer.render.timesteps import TimeSteps
from meshviewer.render.style import (
    AXIS_FONT_DEFAULT, EDGE_WIDTHS, FEATURE_ANGLE, HEAVY_OUTLINE, lighter, PART_COLORS, rgb,
    SELECT_COLOR, THEMES,
)


class Scene(Picking, Camera, Editing, Appearance, Screenshots, TimeSteps):
    def __init__(self, plotter: pv.BasePlotter, model: Model, dark: bool = False,
                 accent: str = SELECT_COLOR):
        self.p = plotter
        self.accent = accent        # selection outline + section plane colour
        self.model = model
        self._set_names(sorted(model.parts, key=str.lower))
        self._palette = {n: PART_COLORS[i % len(PART_COLORS)] for i, n in enumerate(self.names)}
        self.color_mode = "file"                     # the file's own colors (STEP) first
        self.default_colors = self._defaults()
        self.colors = dict(self.default_colors)
        self.visible = {n: True for n in self.names}
        self.selected_parts: list[str] = []          # multi-selection (parts)
        self.selected_faces: dict[str, set] = {}     # CAD faces (measure mode)
        self.on_pick = None          # UI hook: called with the selected part list after a click
        self.on_selection = None     # UI hook (undo): (before, after) when the parts picked change
        self.hidden_faces: dict[str, set] = {}       # right-click ▸ Hide Face
        self._display = {}                           # part -> block drawn (normals)
        self.face_pick = None        # Inflation Layers picks walls: (part, face id, additive)
        self.context_hit = None      # (part, face id) under the last right-click

        # Defaults: meshes show element edges, CAD shows sharp (feature) edges.
        self.state = dict(grid=True, parallel=True, mesh_edges=not model.is_cad,
                          feature_edges=model.is_cad and model.file_type != "drawing",
                          bbox=False, origin=False,          # bbox: drawings, below
                          original=False, shading=True, faces=True,
                          axis_indicator=True)              # the XYZ arrows in the corner
        self._dark = dark
        self._ui_dark = dark
        self.bg_mode = ("default", None)          # set by Appearance
        self._origin_actors = []                  # marker at (0, 0, 0)
        self._orig_points = None                  # file points, kept at the 1st edit
        self._flipped = {}                        # part -> faces flipped (mirrored)
        self._edit_history = []                   # [((R, t) before, label)]
        self._original_actor = None               # grey edges of the file as opened
        self._alias = {}                          # file's part name -> new name
        self.group_names = {}                     # file's assembly name -> its new name
        self._last_view = None                    # (view, flipped?, camera)
        self._bg_image = None                     # ImageBackground when a picture is shown
        self.axis_font = AXIS_FONT_DEFAULT        # set by Appearance
        self.edge_width = EDGE_WIDTHS["thin"]     # feature edge lines (Appearance)
        self.hide_edges_moving = model.dim != 2   # smooth rotation (Appearance); 2D: never
        self.grid_lines = True                    # grid lines on the walls behind the model
        self.axis_lines = True                    # axis frame, ticks, numbers and titles
        self._surf = self._surf_map = None      # composite actor/mapper: all parts
        self._edges = self._edges_map = None    # composite actor/mapper: feature edges
        self._lines2d = self._lines2d_map = None   # 2D meshes: boundary lines on top
        self._attrs = {}                        # "surf" / "edges" / "lines" -> block settings
        self._outline = None                    # outline actor of the selected parts
        self._outlined = ()                     # the parts it was made for
        self._outline_cells = 0
        self._bounds = None                     # model_bounds(), until the parts change
        self._face_actors = []                  # selected CAD faces (fill + rim)
        self._grid_actor = None
        self._label_made = (10.0, 20.0, (20.0,))  # the grid's label size and offsets as made
        self._bbox_actor = None
        self._moving = False
        self._ghost = False                       # see-through while bad cells show

        vtkMapper.SetResolveCoincidentTopologyToPolygonOffset()  # edges drawn over faces
        self._build_surfaces()
        if self.is_drawing:
            self.set_bbox(True, render=False)      # a drawing's frame: on by default
        self.section = Section(self)
        self.quality = QualityView(self)          # Cell quality overlays
        self.flow = FlowView(self)                # CFD ▸ Show flow vectors
        self.yplus_view = YplusView(self)         # CFD ▸ Colour by y+
        self.walls = WallView(self)               # Inflation Layers ▸ the walls
        self.results = ResultsView(self)          # Contours ▸ the active contour
        self.colorbar = ColorBar(self)            # Contours ▸ its color bar, over the view
        self.plot_cut = CutLineView(self)         # Plots ▸ the cuts shown
        self.plots = []                           # Plots: each plot's settings (memory)
        self.visibility_listeners = []            # called after parts are shown / hidden
        self.time_listeners = []                  # called after another time step is shown
        self.field_users = []                     # -> the fields each tool shows
        self.results_settings = None              # field, range (remembered)
        self.inspector_state = None               # {"tab", "open": tools} (None: first open)
        self.cfd_settings = None                  # CFD section (remembered per file)
        self.inflation_settings = None            # Inflation Layers (CAD), remembered too
        self.inflation_page = None                # Inflation page tab, zoom… (memory)
        self.overlays = Overlays(self)            # drawn over the model: marks, labels
        self.measure = Measure(self)
        self.probe_marks = ProbeMarks(self)       # Probe ▸ the markers shown
        self.elements = Elements(self)            # Select ▾: what a click picks
        self.set_theme(dark, render=False)
        self.set_parallel(self.state["parallel"])
        self.set_feature_edges(self.state["feature_edges"], render=False)
        self._setup_picking()
        if model.dim == 2:
            self._lock_to_z()
        self._setup_interaction_lod()
        self._watch_camera()
        self.view("z" if model.dim == 2 else "iso")     # 2D files: from above

    # ---- parts (one composite actor) -------------------------------------
    def _set_names(self, names):
        self.names = list(names)
        self._index = {n: i for i, n in enumerate(self.names)}   # place in the actors

    def _composite(self, key, datasets, **kw):
        """One actor drawing a dataset per part (in the order of self.names). Returns
        (actor, mapper); the parts' colour / visibility settings go to self._attrs[key]."""
        blocks = pv.MultiBlock()
        for n, d in zip(self.names, datasets):
            blocks.append(d, n)
        actor, mapper = self.p.add_composite(blocks, reset_camera=False, **kw)
        attr = mapper.block_attr                   # block 0 is the root
        self._attrs[key] = [attr[i + 1] for i in range(len(self.names))]
        return actor, mapper

    def _small_parts(self):
        """Mostly small parts (an assembly), not a few big ones?"""
        cells = sum(p.n_cells for p in self.model.parts.values())
        return cells < SMALL_PART * len(self.names)

    def _build_surfaces(self):
        self._display = {n: self._shown_part(n) for n in self.names}   # no hidden surfaces
        with one_thread(self._small_parts()):
            # smooth_shading: PyVista works out the normals, split at sharp corners
            self._surf, self._surf_map = self._composite(
                "surf", [self._display[n] for n in self.names], color="#bbbbbb",
                smooth_shading=True, feature_angle=FEATURE_ANGLE,
                show_edges=self.state["mesh_edges"], edge_color="#202020", pickable=True)
        self._surf_map.SetStatic(True)            # geometry never changes in place
        if self.model.file_type == "drawing":
            self._surf.GetProperty().SetLineWidth(2.0)   # a drawing is only lines
        self._build_lines2d()
        self._surf.GetProperty().SetLighting(self.state["shading"])
        self._surf.GetProperty().SetOpacity(GHOST_OPACITY if self._ghost else 1.0)
        self._apply_lines()                       # edges-only look survives rebuilds
        self._apply_blocks()

    def _build_lines2d(self):
        """2D meshes: the boundary lines again, thick and over the zones' mesh edges
        (they lie in the same plane, so the edges would hide them)."""
        if self._lines2d is not None:
            self.p.remove_actor(self._lines2d, render=False)
        self._lines2d = self._lines2d_map = None
        self._attrs.pop("lines", None)
        if self.model.file_type != "mesh2d":
            return
        shown = [self._display[n] for n in self.names]
        self._lines2d, self._lines2d_map = self._composite(
            "lines", [d if d.n_cells and not d.GetNumberOfPolys() else pv.PolyData()
                      for d in shown],
            color="#bbbbbb", line_width=3.0, lighting=False, pickable=False)
        self._lines2d_map.SetResolveCoincidentTopologyToPolygonOffset()
        self._lines2d_map.SetRelativeCoincidentTopologyLineOffsetParameters(-6, -6)

    # --- hide single CAD surfaces (right-click ▸ Hide Surface) ------------
    def _shown_part(self, name):
        """The part without its hidden surfaces; cell data "orig_id" = cell number in
        the full part (for picking)."""
        poly = self.model.parts[name]
        ids = self.hidden_faces.get(name)
        if not ids or "face_id" not in poly.cell_data:
            return poly
        drop = np.isin(poly.cell_data["face_id"], list(ids))
        if drop.all():
            return pv.PolyData()
        full = poly.copy(deep=False)
        full.cell_data["orig_id"] = np.arange(poly.n_cells)
        return full.remove_cells(np.flatnonzero(drop), inplace=False)

    def face_at(self, name, cell):
        """CAD face id of a cell of a part (None for files without CAD faces)."""
        poly = self.model.parts.get(name)
        if poly is None or cell is None or "face_id" not in poly.cell_data:
            return None
        return int(poly.cell_data["face_id"][cell])

    def hide_face(self, name, face_id):
        self.hidden_faces.setdefault(name, set()).add(int(face_id))
        self._rebuild_surfaces()

    def show_faces(self, names=None):
        """Hidden surfaces back (of these parts, or of all)."""
        for n in (list(self.hidden_faces) if names is None else names):
            self.hidden_faces.pop(n, None)
        self._rebuild_surfaces()

    @property
    def n_hidden_faces(self):
        return sum(len(v) for v in self.hidden_faces.values())

    def _rebuild_surfaces(self):
        cam = self.p.camera_position
        self._drop_part_actors()
        self._build_surfaces()
        self.set_feature_edges(self.state["feature_edges"], render=False)
        self.section.rebuild()
        self._refresh_face_overlay()
        self.set_selection(self.selected_parts, render=False)
        self.p.camera_position = cam
        self.p.render()

    def _drop_part_actors(self):
        """Before the parts' actors are built again (new mesh, surfaces hidden…)."""
        for a in (self._surf, self._edges, self._outline):
            if a is not None:
                self.p.remove_actor(a, render=False)
        self._surf = self._surf_map = self._edges = self._edges_map = self._outline = None
        self._outlined = ()
        self._attrs.pop("surf", None)
        self._attrs.pop("edges", None)

    def _apply_block(self, name, selected=None):
        """A part's colour and visibility, on every actor that draws it."""
        i, on = self._index[name], self.visible[name]
        if selected is None:
            selected = name in self.selected_parts
        if self.is_drawing:                            # one colour for every layer
            color = rgb(self.accent if selected else self.line_color)
        else:
            color = lighter(self.colors[name]) if selected else rgb(self.colors[name])
        attr = self._attrs["surf"][i]
        attr.visible, attr.color = on, color
        if "edges" in self._attrs:
            self._attrs["edges"][i].visible = on
        if "lines" in self._attrs:
            la = self._attrs["lines"][i]
            la.visible, la.color = on, color

    def _apply_blocks(self, names=None):
        chosen = set(self.selected_parts)
        for n in self.names if names is None else names:
            self._apply_block(n, n in chosen)

    def set_color(self, names, color, render=True):
        """new colour for parts (right-click ▸ Colour…)."""
        hex_color = pv.Color(color).hex_rgb
        names = [n for n in names if n in self.colors]
        for n in names:
            self.colors[n] = hex_color
        self._apply_blocks(names)
        self.section.recolor()                       # filled cut faces
        if render:
            self.p.render()

    def _defaults(self):
        """Each part's color unless you chose one: the file's ("file" mode, when it
        has one) or the palette's (keyed by the file's part names)."""
        info = (self.model.part_info or {}) if self.color_mode == "file" else {}
        return {n: (info.get(n) or {}).get("color") or self._palette[n] for n in self._palette}

    def set_color_mode(self, mode, render=True):
        """File Color / Randomized Color: parts still in their default color take the
        new mode's; colors you chose stay. Returns the (current) names recolored."""
        mode = mode if mode in ("file", "random") else "file"
        if mode == self.color_mode:
            return []
        old = self.default_colors
        self.color_mode = mode
        self.default_colors = self._defaults()
        changed = {}
        for n in self.names:
            o = self.original(n)
            if self.colors[n] == old.get(o) and old.get(o) != self.default_colors.get(o):
                changed.setdefault(self.default_colors[o], []).append(n)
        for c, names in changed.items():
            self.set_color(names, c, render=False)
        if render:
            self.p.render()
        return [n for ns in changed.values() for n in ns]

    def set_visible(self, names, on, render=True):
        """Show or hide a part, or a list of parts in one go."""
        names = [names] if isinstance(names, str) else list(names)
        for n in names:
            self.visible[n] = bool(on)
        self._apply_blocks(names)
        self._refresh_highlights()
        if render:
            self._after_visibility_change()

    def isolate(self, names):
        """Show only these part(s) (a name or a list) and zoom to them."""
        keep = {names} if isinstance(names, str) else set(names)
        self.visible = {n: n in keep for n in self.names}
        self._apply_blocks()
        self._refresh_highlights()
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

    # ---- what the file says about a part, its size and volume (the parts list) ------
    def original(self, name):
        """The file's name of a part (renamed parts: `_alias` maps it to the new one)."""
        return next((k for k, v in self._alias.items() if v == name), name)

    def part_meta(self, name):
        """{"path", "color", "material"} from the file (STEP / IGES), or {}."""
        return (self.model.part_info or {}).get(self.original(name)) or {}

    def part_size(self, name):
        """The part's size: its bounding box's diagonal (model units)."""
        b = np.asarray(self.model.parts[name].bounds, dtype=float).reshape(3, 2)
        return float(np.linalg.norm(b[:, 1] - b[:, 0]))

    def part_volume(self, name):
        """The volume the part encloses (model units³): exact for CAD solids, else from
        its triangles when they close up; None when it encloses none. Kept per part."""
        poly = self.model.parts[name]
        cache = self.__dict__.setdefault("_volumes", {})
        hit = cache.get(name)
        if hit is not None and hit[0] is poly:
            return hit[1]
        src, v = self.model.source, None
        if src is not None and hasattr(src, "exact_volume"):
            v = src.exact_volume(self.original(name))
        if v is None and poly.GetNumberOfPolys():
            try:
                v = self.measure._mesh_volume([(name, None)])
            except Exception:                                  # noqa: BLE001
                v = None
        v = abs(float(v)) if v is not None else None
        cache[name] = (poly, v)
        return v

    def _after_visibility_change(self):
        rv = getattr(self, "results", None)                 # only visible boundaries
        self.elements.refresh(render=False, notify=False)   # picks of hidden parts go
        cbs = list(getattr(self, "visibility_listeners", []))
        for cb in cbs:                                      # Contours (auto range), Plots
            cb()
        if not cbs and rv is not None:
            rv.refresh()
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
        was = list(self.selected_parts)
        old = set(was)
        self.selected_parts = [n for n in dict.fromkeys(names) if n in self.visible]
        if old != set(self.selected_parts) and getattr(self, "on_selection", None):
            self.on_selection(was, list(self.selected_parts))    # Edit ▸ Undo        self._apply_blocks(old ^ set(self.selected_parts))
        self._refresh_highlights()
        self.results.show_selection(render=False)       # tint shows over result colours
        if self.measure.picking == "area":             # (paused: the area stays)
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

    def _refresh_highlights(self):
        """The accent outline of the selected, visible parts: their silhouette and their
        feature edges — the same lines as Show ▸ Feature Edges (a mesh's sharp and smooth
        edges, a CAD part's face borders), not the triangles bending over the feature
        angle. One actor for all of them, rebuilt only when that set changes. VTK works
        the silhouette out again for every camera position."""
        want = tuple(n for n in self.selected_parts if self.visible.get(n))
        if want == self._outlined:
            return
        if self._outline is not None:
            self.p.remove_actor(self._outline, render=False)
        self._outline, self._outlined = None, want
        if not want:
            return
        parts, lines = vtkAppendPolyData(), vtkAppendPolyData()
        own = False                                   # the parts' own sharp edges
        for n in want:
            part = self.model.parts[n]
            parts.AddInputData(bare(part))
            if self._has_feature_lines(part):
                lines.AddInputData(self.elements.feature_lines(n, self.hidden_faces.get(n)))
            else:
                own = True
        edges = vtkPolyDataSilhouette()
        edges.SetInputConnection(parts.GetOutputPort())
        edges.SetCamera(self.p.renderer.GetActiveCamera())
        edges.SetEnableFeatureAngle(own)               # 2D zones, drawings: as before
        edges.SetFeatureAngle(FEATURE_ANGLE)
        lines.AddInputConnection(edges.GetOutputPort())
        m = vtkPolyDataMapper()
        m.SetInputConnection(lines.GetOutputPort())
        m.ScalarVisibilityOff()
        m.SetResolveCoincidentTopologyToPolygonOffset()       # over result / y+ colours too
        m.SetRelativeCoincidentTopologyLineOffsetParameters(-4, -4)
        a = vtkActor()
        a.SetMapper(m)
        a.PickableOff()
        prop = a.GetProperty()
        prop.SetColor(rgb(self.accent))
        prop.SetLineWidth(3.5)
        prop.SetLighting(False)
        self.p.add_actor(a, reset_camera=False, pickable=False, render=False)
        self.section.clip(a)
        self._outline = a
        self._outline_cells = sum(self.model.parts[n].n_cells for n in want)
        self._sync_outline()

    def _sync_outline(self):
        """A heavy selection's outline is too slow to redo on every frame of a move."""
        if self._outline is not None:
            self._outline.SetVisibility(
                not (self._moving and self._outline_cells > HEAVY_OUTLINE))

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

    @property
    def is_drawing(self):
        return self.model.file_type == "drawing"

    @property
    def line_color(self):
        """Drawings: every line white on a dark background, black on a light one."""
        return "#ffffff" if self._dark else "#000000"

    # ---- display options ----------------------------------------------

    def set_shading(self, on, render=True):
        """lights on (shaded, 3D look) or off (flat part colours, no
        light or shadow) for the parts and the filled cut faces."""
        self.state["shading"] = bool(on)
        self._surf.GetProperty().SetLighting(bool(on))
        self.section.sync_shading()
        if render:
            self.p.render()

    def _apply_lines(self):
        """Faces, mesh edges and feature edges from the toolbar toggles + the moving
        state. Faces hidden: mesh edges become a wireframe (still hidden while
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
        for yv in (getattr(self, "yplus_view", None), getattr(self, "results", None)):
            if yv is not None:                              # y+ colours follow too
                yv.apply_lines()

    def set_ghost(self, on, render=True):
        """faces see-through, so the bad cells inside show."""
        self._ghost = bool(on)
        self._surf.GetProperty().SetOpacity(GHOST_OPACITY if on else 1.0)
        if render:
            self.p.render()

    def set_faces(self, on, render=True):
        """Show or hide the faces, keeping the edges."""
        self.state["faces"] = bool(on)
        self._apply_lines()
        if render:
            self.p.render()

    def set_mesh_edges(self, on, render=True):
        on = on and not self.is_drawing             # drawings: lines only
        self.state["mesh_edges"] = bool(on)
        self._apply_lines()
        self.section.sync_cut_edges()              # the cut mesh follows this switch
        if render:
            self.p.render()

    def set_feature_edges(self, on, render=True):
        on = on and not self.is_drawing             # drawings: lines only
        self.state["feature_edges"] = bool(on)
        if on and self._edges is None:
            self._build_edges()
        self._apply_lines()
        if render:
            self.p.render()

    def _has_feature_lines(self, part):
        """Feature edges from `elements.feature_lines`: 3D meshes and CAD parts."""
        return self.model.file_type == "mesh" or (
            self.model.file_type == "cad" and "face_id" in part.cell_data)

    def _build_edges(self):
        flat = self.model.file_type == "mesh2d"
        edges = []
        for n in self.names:
            part = self._display[n]
            if flat and not part.GetNumberOfPolys():
                edges.append(pv.PolyData())          # 2D boundary lines: drawn already
                continue
            if self._has_feature_lines(part):
                # meshes: sharp and smooth edges; CAD: the borders of its faces (as in
                # the CAD program) — what Select picks
                edges.append(self.elements.feature_lines(n, self.hidden_faces.get(n)))
                continue
            # 2D zones: their outline, so boundaries that are hidden or have no name show
            with one_thread(part.n_cells < SMALL_PART):
                edges.append(part.extract_feature_edges(
                    feature_angle=FEATURE_ANGLE, boundary_edges=True, feature_edges=not flat,
                    manifold_edges=False, non_manifold_edges=False))
        self._edges, self._edges_map = self._composite(
            "edges", edges, color=THEMES[self._dark]["edge"],
            line_width=max(2.5, 2 * self.edge_width) if flat else self.edge_width,
            lighting=False, pickable=False)
        self._edges_map.SetStatic(True)
        if flat:                                     # over the mesh edges, under the boundaries
            self._edges_map.SetResolveCoincidentTopologyToPolygonOffset()
            self._edges_map.SetRelativeCoincidentTopologyLineOffsetParameters(-3, -3)
        for attr, n in zip(self._attrs["edges"], self.names):
            attr.visible = self.visible[n]
        self.section.clip(self._edges)

    # ---- internals -----------------------------------------------------
    def model_bounds(self):
        """[x0, x1, y0, y1, z0, z1] of every part, shown or not."""
        if self._bounds is None:
            b = np.array([p.bounds for p in self.model.parts.values()])
            self._bounds = (b[:, 0].min(), b[:, 1].max(), b[:, 2].min(), b[:, 3].max(),
                            b[:, 4].min(), b[:, 5].max())
        return list(self._bounds)

    def clippable_actors(self):
        """Everything the section plane should cut."""
        return [self._surf, self._edges, self._outline, *self._face_actors,
                *self.quality.actors(), *self.yplus_view.actors(),
                *self.walls.actors(), *self.results.actors(), *self.elements.actors()]
