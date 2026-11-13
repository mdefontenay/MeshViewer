"""Scene ▸ what a click selects (the toolbar's Select ▾): the part, or a mesh node,
mesh edge or mesh triangle (meshes only), or a feature node, feature edge or feature
face (`core/features.py`). Picked elements are drawn in the accent color. No Qt."""
from __future__ import annotations

import numpy as np
import pyvista as pv

from meshviewer.core.features import cut_at_junctions, Features, place_tolerance
from meshviewer.core.units import fmt
from meshviewer.render.style import FEATURE_ANGLE

# key, title (menus), one, many (the selection line)
KINDS = (
    ("part", "Part", None, None),
    ("mesh_node", "Mesh Node", "mesh node", "mesh nodes"),
    ("mesh_edge", "Mesh Edge", "mesh edge", "mesh edges"),
    ("mesh_cell", "Mesh Triangle", "mesh triangle", "mesh triangles"),
    ("feature_node", "Feature Node", "feature node", "feature nodes"),
    ("feature_edge", "Feature Edge", "feature edge", "feature edges"),
    ("feature_face", "Feature Face", "feature face", "feature faces"),
)
MESH_KINDS = ("mesh_node", "mesh_edge", "mesh_cell")
WORDS = {k: (one, many) for k, _, one, many in KINDS}
NODE_PX = 12          # picked nodes, screen pixels
LINE_PX = 5.0         # picked edges


class Elements:
    def __init__(self, scene):
        self.scene = scene
        self.kind = "part"
        self.items: list[tuple[str, object]] = []    # (part, id): what the kind picks
        self.on_changed = None                       # UI hook: something picked / cleared
        self._features = {}                          # part -> (surface, Features)
        self._actors = []

    # ---- the kind ----------------------------------------------------------------
    def kinds(self):
        """The kinds this file offers: mesh elements only for meshes."""
        m = self.scene.model
        if m.file_type == "drawing":
            return ("part",)
        return tuple(k for k, *_ in KINDS if m.kind == "mesh" or k not in MESH_KINDS)

    def set_kind(self, kind):
        kind = kind if kind in self.kinds() else "part"
        if kind == self.kind:
            return
        self.kind = kind
        self.clear()

    def features(self, name):
        """The part's feature faces, edges and nodes, made when first needed. A mesh's
        parts (boundaries) are done together: one's feature edges cut another's."""
        parts = self.scene.model.parts
        poly = parts[name]
        got = self._features.get(name)
        if got is not None and got[0] is poly:
            return got[1]
        if self.scene.model.kind != "mesh":            # CAD: each part on its own
            got = (poly, Features(poly, FEATURE_ANGLE))
            self._features[name] = got
            return got[1]
        tol = place_tolerance(self.scene.model_bounds())
        self._features = {n: (p, Features(p, FEATURE_ANGLE, tol)) for n, p in parts.items()}
        cut_at_junctions([f for _, f in self._features.values()])
        return self._features[name][1]

    def feature_lines(self, name, hidden=None):
        """The part's feature edges as lines (Show ▸ Feature Edges): a mesh's sharp and
        smooth edges, a CAD part's face borders. `hidden`: CAD face ids hidden (Hide
        Face): a border with only hidden faces beside it goes too."""
        f = self.features(name)
        seg = f.seg
        if hidden and f.face_ids is not None and len(seg):
            gone = np.isin(f.face_ids, list(hidden))
            side = f.seg_faces
            shown = ((side >= 0) & ~gone[np.maximum(side, 0)]).any(axis=1)
            seg = seg[shown]
        if not len(seg):
            return pv.PolyData()
        pts = np.asarray(self.scene.model.parts[name].points, dtype=float)[seg.reshape(-1)]
        n = len(seg)
        lines = np.column_stack([np.full(n, 2), np.arange(0, 2 * n, 2),
                                 np.arange(1, 2 * n, 2)]).reshape(-1)
        return pv.PolyData(pts, lines=lines)

    # ---- a click -----------------------------------------------------------------
    def click(self, name, cell, pos, additive=False):
        """Pick what the kind wants under the click (None: nothing, clears)."""
        item = self._item_at(name, cell, pos) if name is not None else None
        if item is None:
            if not additive:
                self.items = []
        elif additive:
            self.items.remove(item) if item in self.items else self.items.append(item)
        else:
            self.items = [item]
        self.refresh()

    def _item_at(self, name, cell, pos):
        if cell is None or cell < 0 or pos is None:
            return None                          # a cut face: no element of a part
        poly = self.scene.model.parts[name]
        pts = np.asarray(poly.points, dtype=float)
        pos = np.asarray(pos, dtype=float)
        k = self.kind
        if k in ("mesh_node", "mesh_edge", "mesh_cell"):
            ids = np.array(poly.get_cell(cell).point_ids, dtype=np.int64)
            if k == "mesh_cell":
                return name, int(cell)
            if k == "mesh_node":
                return name, int(ids[np.argmin(np.linalg.norm(pts[ids] - pos, axis=1))])
            a, b = ids, np.roll(ids, -1)
            if len(ids) == 2:                     # a line: its one edge
                a, b = ids[:1], ids[1:]
            p0, d = pts[a], pts[b] - pts[a]
            dd = np.einsum("ij,ij->i", d, d)
            t = np.clip(np.einsum("ij,ij->i", pos - p0, d) / np.where(dd > 0, dd, 1), 0, 1)
            i = int(np.argmin(np.linalg.norm(p0 + t[:, None] * d - pos, axis=1)))
            return name, tuple(sorted((int(a[i]), int(b[i]))))
        f = self.features(name)
        face = f.face_of(cell)
        if k == "feature_face":
            return (name, face) if face >= 0 else None
        if k == "feature_edge":
            c = f.nearest_curve(pts, pos, face)
            return None if c is None else (name, c)
        if k == "feature_node":
            n = f.nearest_node(pts, pos, face)
            return None if n is None else (name, n)
        return None

    def clear(self, render=True):
        had = bool(self.items) or bool(self._actors)
        self.items = []
        self.refresh(render=render, notify=had)

    def parts_changed(self):
        """New meshes (Meshing Control) or moved points (Edit): ids may differ."""
        parts = self.scene.model.parts
        keep = {n for n, (poly, _) in self._features.items() if parts.get(n) is poly}
        if self.scene.model.kind == "mesh" and len(keep) < len(self._features):
            keep = set()                                 # a mesh's parts go together
        self._features = {n: v for n, v in self._features.items() if n in keep}
        if self.kind.startswith("feature"):
            self.items = [it for it in self.items if it[0] in keep]
        else:
            self.items = [it for it in self.items if it[0] in parts]
        self.refresh(notify=False)

    # ---- what is shown -------------------------------------------------------------
    def refresh(self, render=True, notify=True):
        sc = self.scene
        for a in self._actors:
            sc.p.remove_actor(a, render=False)
        self._actors = []
        nodes, lines, faces = [], [], []
        for name, key in self.items:
            poly = sc.model.parts.get(name)
            if poly is None or not sc.visible.get(name):
                continue
            pts = np.asarray(poly.points, dtype=float)
            if self.kind in ("mesh_node", "feature_node"):
                nodes.append(pts[[key]])
            elif self.kind == "mesh_edge":
                lines.append(pts[list(key)][None])
            elif self.kind == "feature_edge":
                lines.append(pts[self.features(name).curve_segments(key)])
            elif self.kind == "mesh_cell":
                faces.append(poly.extract_cells([key]))
            elif self.kind == "feature_face":
                faces.append(poly.extract_cells(self.features(name).face_cells(key)))
        if faces:
            mesh = pv.merge(faces) if len(faces) > 1 else faces[0]
            fill = sc.p.add_mesh(mesh, color=sc.accent, opacity=0.85, pickable=False,
                                 reset_camera=False, render=False)
            fill.GetMapper().SetRelativeCoincidentTopologyPolygonOffsetParameters(-2, -2)
            self._actors.append(fill)
            rim = mesh.extract_feature_edges(boundary_edges=True, feature_edges=False,
                                             manifold_edges=False, non_manifold_edges=False)
            if rim.n_cells:
                self._add_lines(rim)
        if lines:
            s = np.concatenate(lines)                 # (k, 2, 3)
            n = len(s)
            cells = np.column_stack([np.full(n, 2), np.arange(0, 2 * n, 2),
                                     np.arange(1, 2 * n, 2)]).reshape(-1)
            self._add_lines(pv.PolyData(s.reshape(-1, 3), lines=cells))
        if nodes:
            dots = sc.p.add_mesh(pv.PolyData(np.concatenate(nodes)), color=sc.accent,
                                 point_size=NODE_PX, render_points_as_spheres=True,
                                 lighting=False, pickable=False, reset_camera=False,
                                 render=False)
            m = dots.GetMapper()
            m.SetResolveCoincidentTopologyToPolygonOffset()
            m.SetRelativeCoincidentTopologyPointOffsetParameter(-8)
            self._actors.append(dots)
        for a in self._actors:
            sc.section.clip(a)
        if notify and self.on_changed:
            self.on_changed()
        if render:
            sc.p.render()

    def _add_lines(self, poly):
        sc = self.scene
        a = sc.p.add_mesh(poly, color=sc.accent, line_width=LINE_PX, lighting=False,
                          pickable=False, reset_camera=False, render=False)
        m = a.GetMapper()
        m.SetResolveCoincidentTopologyToPolygonOffset()
        m.SetRelativeCoincidentTopologyLineOffsetParameters(-6, -6)
        self._actors.append(a)

    def actors(self):
        return list(self._actors)

    # ---- the selection line in the parts list ------------------------------------------
    def describe(self):
        """("2 feature faces selected", "Wing · 12.5 mm²") or None when nothing is picked."""
        parts = self.scene.model.parts
        self.items = [it for it in self.items if it[0] in parts]     # (renamed parts)
        if self.kind == "part" or not self.items:
            return None
        one, many = WORDS[self.kind]
        count = f"{len(self.items)} {one if len(self.items) == 1 else many} selected"
        s, unit = self.scene.measure.unit_scale()
        u = f" {unit}" if unit else ""
        names = list(dict.fromkeys(n for n, _ in self.items))
        where = names[0] if len(names) == 1 else f"{len(names)} parts"
        if self.kind in ("mesh_node", "feature_node"):
            if len(self.items) > 1:
                return count, where
            n, i = self.items[0]
            x, y, z = np.asarray(parts[n].points[i], dtype=float) * s
            return count, f"{where} · node {i:,}\nX {fmt(x)} · Y {fmt(y)} · Z {fmt(z)}{u}"
        if self.kind in ("mesh_edge", "feature_edge"):
            total = 0.0
            for n, key in self.items:
                pts = np.asarray(parts[n].points, dtype=float)
                seg = np.array([key]) if self.kind == "mesh_edge" else \
                    self.features(n).curve_segments(key)
                total += float(np.linalg.norm(pts[seg[:, 1]] - pts[seg[:, 0]], axis=1).sum())
            return count, f"{where}\nlength {fmt(total * s)}{u}"
        total = 0.0
        for n, key in self.items:
            ids = [key] if self.kind == "mesh_cell" else self.features(n).face_cells(key)
            sizes = parts[n].extract_cells(ids).compute_cell_sizes(length=False, volume=False)
            total += float(np.sum(sizes.cell_data["Area"]))
        sq = f" {unit}²" if unit else ""
        return count, f"{where}\narea {fmt(total * s * s)}{sq}"
