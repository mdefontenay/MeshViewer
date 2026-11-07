"""NEW (v2.10): "Show flow vectors" — small arrows in the 3D view pointing the way
the flow goes: a 5 × 5 grid just upstream of the chosen boundary and one just
downstream of it. No Qt widgets."""
from __future__ import annotations

import numpy as np
import pyvista as pv

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


# ---- NEW (v2.11.3): "Colour by y+" — the boundary painted by its y+ at each wall node -------
# y+ / target: 0 blue (finer than needed) · 1 green (on target) · 2 orange · ≥ 3 red
YPLUS_STOPS = ((0.0, "#0a84ff"), (1.0, "#30b350"), (2.0, "#ff9f0a"), (3.0, "#ff453a"))
NAN_COLOR = "#8e8e93"                 # nodes without a measured first cell


def yplus_rgb(ratio):
    """Colour (n, 3) uint8 for y+ / target values (NaN -> grey)."""
    r = np.asarray(ratio, dtype=float)
    xs = [s for s, _ in YPLUS_STOPS]
    cols = np.array([[int(c[i:i + 2], 16) for i in (1, 3, 5)] for _, c in YPLUS_STOPS], float)
    rc = np.clip(np.nan_to_num(r, nan=0.0), xs[0], xs[-1])
    out = np.stack([np.interp(rc, xs, cols[:, k]) for k in range(3)], axis=1)
    out[~np.isfinite(r)] = [int(NAN_COLOR[i:i + 2], 16) for i in (1, 3, 5)]
    return out.astype(np.uint8)


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
        if len(ratio) != part.n_points:
            self.p.render()
            return
        surf = pv.PolyData(np.asarray(part.points), faces=part.faces)
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
        """v2.11.4: like the model — mesh edges hidden while the view moves; with the
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


# ---- NEW (v2.12): CFD mode (CAD) — the walls that get inflation layers -----------------
WALL_COLOR = "#00b5ad"


class WallView:
    """The chosen walls tinted in the 3D view (CFD mode)."""

    def __init__(self, scene):
        self.scene = scene
        self.p = scene.p
        self._actors = []

    def show(self, mesh):
        """mesh: the wall surface (PolyData) or None to hide."""
        self.hide(render=False)
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
