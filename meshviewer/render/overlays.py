"""3D overlays drawn over the model (no Qt widgets):

    FlowView     "Show flow vectors": 5 × 5 arrows up- and downstream of a boundary
    YplusView    CFD ▸ Colour by y+ (per wall node, relative to the target)
    WallView     Inflation Layers: the walls tinted
    ResultsView  Results: a solution field on the visible boundaries (or its gradient)
    CutLineView  Plots: where the plane of a section plot cuts the boundaries

Colour maths (ramps, scales) lives in core/fields.py.
"""
from __future__ import annotations

import numpy as np
import pyvista as pv
from meshviewer.core.fields import field_values, lighter_rgb, ramp_rgb, yplus_rgb
from meshviewer.core.polys import bare

ARROW_COLOR = "#0a84ff"
N = 5                               # arrows per side of each grid


class FlowView:
    def __init__(self, scene):
        self.scene = scene
        self.p = scene.p
        self._actor = None

    def show(self, direction, bounds):
        """direction: XYZ (any length); bounds: box to put the arrows around.
        None for either hides them."""
        self.hide(render=False)
        d = None if direction is None else np.asarray(direction, dtype=float)
        if d is None or bounds is None or not np.linalg.norm(d):
            self.p.render()
            return
        d = d / np.linalg.norm(d)
        b = np.asarray(bounds, dtype=float).reshape(3, 2)
        centre, half = b.mean(axis=1), (b[:, 1] - b[:, 0]) / 2
        size = float(np.linalg.norm(half)) or 1.0
        u = np.cross(d, [1.0, 0, 0] if abs(d[0]) < 0.9 else [0, 1.0, 0])
        u /= np.linalg.norm(u)
        v = np.cross(d, u)
        reach = float(np.abs(half) @ np.abs(d))            # half-depth of the box along d
        span = max(float(np.abs(half) @ np.abs(u)), float(np.abs(half) @ np.abs(v)), size * 0.2)
        length = size * 0.16
        s = np.linspace(-span, span, N)
        gu, gv = np.meshgrid(s, s)
        plane = gu.ravel()[:, None] * u + gv.ravel()[:, None] * v
        pts = np.vstack([centre - d * (reach + 1.6 * length) + plane,      # upstream
                         centre + d * (reach + 0.4 * length) + plane])     # downstream
        cloud = pv.PolyData(pts)
        cloud["v"] = np.tile(d, (len(pts), 1))
        arrows = cloud.glyph(orient="v", scale=False, factor=length,
                             geom=pv.Arrow(tip_length=0.35, tip_radius=0.12, shaft_radius=0.04))
        self._actor = self.p.add_mesh(arrows, color=ARROW_COLOR, pickable=False,
                                      reset_camera=False, lighting=True)
        self.p.render()

    def hide(self, render=True):
        if self._actor is not None:
            self.p.remove_actor(self._actor, render=False)
            self._actor = None
        if render:
            self.p.render()

    @property
    def shown(self):
        return self._actor is not None


# --- "Colour by y+" — the boundary painted by its y+ at each wall node -------
# y+ / target: 0 blue (finer than needed) · 1 green (on target) · 2 orange · ≥ 3 red


class YplusView:
    def __init__(self, scene):
        self.scene = scene
        self.p = scene.p
        self._actor = None

    def show(self, name, ratio):
        """name: boundary; ratio: y+ / target at each of its points (NaN allowed).
        None for either hides the colours."""
        self.hide(render=False)
        sc = self.scene
        if name is None or ratio is None or name not in sc.model.parts:
            self.p.render()
            return
        part = sc.model.parts[name]
        self.show_surface(part, ratio)

    def show_surface(self, part, ratio):
        """The colours on one surface, ratio at each of its points."""
        self.hide(render=False)
        sc = self.scene
        if part is None or ratio is None or len(ratio) != part.n_points:
            self.p.render()
            return
        surf = bare(part)
        surf.point_data["YplusRGB"] = yplus_rgb(ratio)
        self._actor = self.p.add_mesh(
            surf, scalars="YplusRGB", rgb=True, edge_color="#202020", pickable=False, reset_camera=False, lighting=True)
        m = self._actor.GetMapper()                 # drawn just in front of the part
        m.SetResolveCoincidentTopologyToPolygonOffset()
        m.SetRelativeCoincidentTopologyPolygonOffsetParameters(-2, -2)
        sc.section.clip(self._actor)
        self.apply_lines()
        self.p.render()

    def apply_lines(self):
        """like the model — mesh edges hidden while the view moves; with the
        faces off, a coloured wireframe (hidden while moving)."""
        if self._actor is None:
            return
        sc = self.scene
        eo, mesh, moving = (not sc.state["faces"], sc.state["mesh_edges"],
                            getattr(sc, "_moving", False))
        prop = self._actor.GetProperty()
        if eo:
            prop.SetRepresentationToWireframe()
            prop.SetEdgeVisibility(False)
            self._actor.SetVisibility(mesh and not moving)
        else:
            prop.SetRepresentationToSurface()
            prop.SetEdgeVisibility(mesh and not moving)
            self._actor.SetVisibility(True)

    def hide(self, render=True):
        if self._actor is not None:
            self.p.remove_actor(self._actor, render=False)
            self._actor = None
        if render:
            self.p.render()

    @property
    def shown(self):
        return self._actor is not None

    def actors(self):
        return [self._actor] if self._actor is not None else []


# --- Inflation Layers (CAD) — the walls that get the layers ---------------
WALL_COLOR = "#00b5ad"


def offset_field(mesh, thickness):
    """(surface, displacement per point) moving the walls out by `thickness` (model
    units; < 0: the other side). Points at the same place are merged first (no cracks
    between CAD faces). Each point goes along its angle-weighted normal, far enough that
    the faces at it move out by the thickness (a box grows by exactly that), at most
    twice the thickness (a thin trailing edge: no spikes)."""
    surf = mesh.extract_surface().triangulate().clean(tolerance=1e-9, absolute=False)
    pts = np.asarray(surf.points, dtype=float)
    tri = np.asarray(surf.faces).reshape(-1, 4)[:, 1:]
    p0, p1, p2 = pts[tri[:, 0]], pts[tri[:, 1]], pts[tri[:, 2]]
    cn = np.cross(p1 - p0, p2 - p0)
    area = np.linalg.norm(cn, axis=1)
    ok = area > 0
    tri, cn = tri[ok], cn[ok] / area[ok][:, None]
    pn = np.zeros_like(pts)
    for k in range(3):                          # the angle of each triangle at the point
        a = pts[tri[:, k]]
        u = pts[tri[:, (k + 1) % 3]] - a
        v = pts[tri[:, (k + 2) % 3]] - a
        cos = np.einsum("ij,ij->i", u, v) / np.maximum(
            np.linalg.norm(u, axis=1) * np.linalg.norm(v, axis=1), 1e-300)
        np.add.at(pn, tri[:, k], cn * np.arccos(np.clip(cos, -1, 1))[:, None])
    pn /= np.maximum(np.linalg.norm(pn, axis=1), 1e-300)[:, None]
    lean = np.ones(len(pts))
    for k in range(3):
        np.minimum.at(lean, tri[:, k], np.einsum("ij,ij->i", pn[tri[:, k]], cn))
    d = pn * (float(thickness) / np.clip(lean, 0.5, 1.0))[:, None]
    return surf, d


def thickness_shell(mesh, thickness):
    """The walls moved out along their normals by `thickness`: a quick picture of how
    thick the inflation layers are (`offset_field`)."""
    surf, d = offset_field(mesh, thickness)
    shell = surf.copy()
    shell.points = np.asarray(surf.points) + d
    return shell


def _folded(surf, d):
    """Share of the area whose triangles turn over when the points move by d."""
    tri = np.asarray(surf.faces).reshape(-1, 4)[:, 1:]
    p = np.asarray(surf.points, dtype=float)
    q = p + d
    n0 = np.cross(p[tri[:, 1]] - p[tri[:, 0]], p[tri[:, 2]] - p[tri[:, 0]])
    n1 = np.cross(q[tri[:, 1]] - q[tri[:, 0]], q[tri[:, 2]] - q[tri[:, 0]])
    a = np.linalg.norm(n0, axis=1)
    bad = np.einsum("ij,ij->i", n0, n1) <= 0
    return float(a[bad].sum() / max(a.sum(), 1e-300))


def auto_side(mesh, thickness):
    """+1 (along the normals) or −1: the side where the layers fold over themselves
    least — the fluid side of a wing's skin, not into its thin trailing edge."""
    surf, d = offset_field(mesh, abs(float(thickness)))
    return 1 if _folded(surf, d) <= _folded(surf, -d) else -1


def offset_lines(lines, surf, d):
    """Feature lines moved with the surface they lie on (each point as the nearest
    point of `surf`)."""
    from vtkmodules.vtkCommonDataModel import vtkStaticPointLocator
    loc = vtkStaticPointLocator()
    loc.SetDataSet(surf)
    loc.BuildLocator()
    pts = np.asarray(lines.points, dtype=float)
    idx = np.fromiter((loc.FindClosestPoint(x) for x in pts), dtype=np.int64, count=len(pts))
    out = lines.copy()
    out.points = pts + d[idx]
    return out


class WallView:
    """The chosen walls tinted in the 3D view (Inflation Layers), and, when asked, the
    layers' total thickness over them as a see-through shell."""

    def __init__(self, scene):
        self.scene = scene
        self.p = scene.p
        self._actors = []

    def show(self, mesh, thickness=None, over=None, lines=None):
        """mesh: the wall surface (PolyData) to tint, or None; thickness: the layers'
        total (model units, < 0: against the normals) to draw over `over` (default:
        mesh), or None; lines: the walls' feature edges, drawn moved with it."""
        self.hide(render=False)
        over = over if over is not None else mesh
        if thickness and over is not None and over.n_cells:
            try:
                surf, d = offset_field(over, thickness)
                shell = surf.copy()
                shell.points = np.asarray(surf.points) + d
                a = self.p.add_mesh(shell, color=WALL_COLOR, opacity=0.3, pickable=False,
                                    reset_camera=False, smooth_shading=True)
                self._actors.append(a)
                if lines is not None and lines.n_points:
                    a = self.p.add_mesh(offset_lines(lines, surf, d), color=WALL_COLOR,
                                        line_width=1.5, lighting=False, pickable=False,
                                        reset_camera=False)
                    self._actors.append(a)
            except Exception as exc:                        # noqa: BLE001
                print(f"inflation thickness: {exc}")
        if mesh is None or not mesh.n_cells:
            self.p.render()
            return
        fill = self.p.add_mesh(mesh, color=WALL_COLOR, opacity=0.6, pickable=False,
                               reset_camera=False, lighting=False)    # same tint any side
        m = fill.GetMapper()                         # just in front of the part
        m.SetResolveCoincidentTopologyToPolygonOffset()
        m.SetRelativeCoincidentTopologyPolygonOffsetParameters(-2, -2)
        self._actors.append(fill)
        rim = mesh.extract_feature_edges(boundary_edges=True, feature_edges=False,
                                         manifold_edges=False, non_manifold_edges=False)
        if rim.n_cells:
            self._actors.append(self.p.add_mesh(rim, color=WALL_COLOR, line_width=3,
                                                lighting=False, pickable=False,
                                                reset_camera=False))
        for a in self._actors:
            self.scene.section.clip(a)
        self.p.render()

    def hide(self, render=True):
        for a in self._actors:
            self.p.remove_actor(a, render=False)
        self._actors = []
        if render:
            self.p.render()

    @property
    def shown(self):
        return bool(self._actors)

    def actors(self):
        return list(self._actors)


# --- Results — the boundaries painted by a solution field -----------------------
# Colour scales (dataviz reference palette): one hue, light -> dark, for magnitudes; blue ->
# grey -> red around zero for fields that change sign (cp, u, v, w…).


class ResultsView(YplusView):
    """The visible boundaries that carry `field`, coloured on lo..hi (drawn just in
    front of the model, cut by the section plane, edges like the model's)."""

    def __init__(self, scene):
        super().__init__(scene)
        self.spec = None                      # (field, lo, hi, stops, log) while shown

    def show_field(self, field, lo, hi, stops, log=False):
        self.hide(render=False)
        sc = self.scene
        self.spec = (field, lo, hi, stops, log)
        polys, self._pieces = [], []          # (part name, "point" | "cell", RGB)
        for n in sc.names:
            part = sc.model.parts.get(n)
            if part is None or not sc.visible.get(n):
                continue
            vals, where = field_values(part, field)
            if vals is None:
                continue
            surf = bare(part)
            rgb = ramp_rgb(vals, lo, hi, stops, log)
            (surf.point_data if where == "point" else surf.cell_data)["ResultRGB"] = rgb
            polys.append(surf)
            self._pieces.append((n, where, rgb))
        if not polys:
            self.p.render()
            return
        # merge_points=False keeps every piece's points in order (see show_selection)
        surf = polys[0] if len(polys) == 1 else pv.merge(polys, merge_points=False)
        self._surf = surf
        self.show_selection(render=False)
        self._actor = self.p.add_mesh(surf, scalars="ResultRGB", rgb=True, edge_color="#202020",
                                      pickable=False, reset_camera=False, lighting=True,
                                      smooth_shading=True, ambient=0.25, diffuse=0.8)
        m = self._actor.GetMapper()
        m.Update()                             # (the copy exists once the mapper has run)
        self._surf = pv.wrap(m.GetInput())     # what is drawn (smooth shading copies it)
        m.SetResolveCoincidentTopologyToPolygonOffset()
        m.SetRelativeCoincidentTopologyPolygonOffsetParameters(-2, -2)
        sc.section.clip(self._actor)
        self.apply_lines()
        self.p.render()

    def show_selection(self, render=True):
        """Selected parts lighter, as on the model (the colours hide the model's tint)."""
        if self.spec is None or getattr(self, "_surf", None) is None:
            return
        sel = set(self.scene.selected_parts)
        where = {w for _, w, _ in self._pieces}
        if len(where) > 1:                     # mixed point / cell fields: leave as is
            return
        rgb = np.concatenate([lighter_rgb(c) if n in sel else c for n, _, c in self._pieces])
        data = self._surf.point_data if where == {"point"} else self._surf.cell_data
        data["ResultRGB"] = rgb
        self._surf.Modified()
        if render:
            self.p.render()

    def refresh(self):
        """Visibility or the model changed: draw again with the same field."""
        if self.spec is not None:
            self.show_field(*self.spec)

    def clear(self):
        self.spec = None
        self.hide()


class CutLineView:
    """The cuts of the section plots whose eye is open, drawn over the model."""

    def __init__(self, scene):
        self.scene = scene
        self.p = scene.p
        self._actor = None

    def show(self, lines, color):
        """lines: PolyData of line segments, a list of them, or None (hide)."""
        if self._actor is not None:
            self.p.remove_actor(self._actor, render=False)
            self._actor = None
        if isinstance(lines, (list, tuple)):
            lines = [x for x in lines if x is not None and x.n_cells]
            lines = None if not lines else lines[0] if len(lines) == 1 else pv.merge(lines)
        if lines is not None and lines.n_cells:
            self._actor = self.p.add_mesh(lines, color=color, line_width=3.5, lighting=False,
                                          pickable=False, reset_camera=False,
                                          render_lines_as_tubes=False)
            m = self._actor.GetMapper()
            m.SetResolveCoincidentTopologyToPolygonOffset()
            m.SetRelativeCoincidentTopologyLineOffsetParameters(-8, -8)
        self.p.render()

    def hide(self):
        self.show(None, None)
