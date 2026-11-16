"""Scene ▸ what a click selects (the toolbar's Select ▾): the part, or a mesh node,
mesh edge or mesh triangle (meshes only), or a feature node, feature edge or feature
face (`core/features.py`). A 2D mesh picks mesh cells (its triangles and quads) and no
feature face (its face zones are its parts). A 3D mesh with volume cells (CGNS, UGRID,
.msh) also picks a Volume Cell: the cell under the click, on a boundary or on the
section's cut. Picked elements are drawn in the accent color; Measure Selected says
what they are (render/element_details.py). On 2D files Node and Edge pick the nearest
one on screen (`click_2d`), as Snap to edges does (`snap_2d`). No Qt."""
from __future__ import annotations

import numpy as np
import pyvista as pv

from meshviewer.core.features import cut_at_junctions, Features, place_tolerance
from meshviewer.core.units import fmt
from meshviewer.render.picking import nearest_on_screen
from meshviewer.render.style import FEATURE_ANGLE, NODE_SNAP_PX, PICK_PX

# key, title (menus), one, many (the selection line)
KINDS = (
    ("part", "Part", None, None),
    ("mesh_node", "Mesh Node", "mesh node", "mesh nodes"),
    ("mesh_edge", "Mesh Edge", "mesh edge", "mesh edges"),
    ("mesh_cell", "Mesh Triangle", "mesh triangle", "mesh triangles"),
    ("volume_cell", "Volume Cell", "volume cell", "volume cells"),
    ("feature_node", "Feature Node", "feature node", "feature nodes"),
    ("feature_edge", "Feature Edge", "feature edge", "feature edges"),
    ("feature_face", "Feature Face", "feature face", "feature faces"),
)
MESH_KINDS = ("mesh_node", "mesh_edge", "mesh_cell", "volume_cell")
VOLUME = ""                       # the part name of a volume cell's item: ("", cell id)
WORDS = {k: (one, many) for k, _, one, many in KINDS}
CELL_2D = ("Mesh Cell", "mesh cell", "mesh cells")     # mesh_cell on a 2D mesh
DRAWING = {"feature_edge": ("Edge", "edge", "edges"),   # a drawing's lines: corner to
           "feature_node": ("Node", "node", "nodes")}   # corner, and their ends


def kinds_for(model):
    """The kinds a file offers: Edge and Node on drawings (no parts list to pick a
    layer from); mesh elements only for meshes; no feature face on a 2D mesh."""
    if model.file_type == "drawing":
        return ("feature_edge", "feature_node")
    if model.file_type == "mesh2d":
        return tuple(k for k, *_ in KINDS if k not in ("feature_face", "volume_cell"))
    return tuple(k for k, *_ in KINDS if (model.kind == "mesh" or k not in MESH_KINDS)
                 and (k != "volume_cell" or model.volume is not None))


def title_for(kind, model):
    """The kind's name in the menus ("Mesh Cell" on a 2D mesh)."""
    if kind == "mesh_cell" and model is not None and model.file_type == "mesh2d":
        return CELL_2D[0]
    if model is not None and model.file_type == "drawing" and kind in DRAWING:
        return DRAWING[kind][0]
    return next(t for k, t, *_ in KINDS if k == kind)
NODE_PX = 12          # picked nodes, screen pixels
LINE_PX = 5.0         # picked edges
ON_SCREEN = ("mesh_node", "mesh_edge", "feature_node", "feature_edge")   # 2D: click_2d


def mesh_edges(poly):
    """(k, 2) point ids of a part's mesh edges (its cells' sides and its lines), each once."""
    from vtkmodules.util.numpy_support import vtk_to_numpy
    pairs = []
    for cells, closed in ((poly.GetPolys(), True), (poly.GetLines(), False)):
        if cells is None or cells.GetNumberOfCells() == 0:
            continue
        off = np.asarray(vtk_to_numpy(cells.GetOffsetsArray()), dtype=np.int64)
        conn = np.asarray(vtk_to_numpy(cells.GetConnectivityArray()), dtype=np.int64)
        cell_of = np.repeat(np.arange(len(off) - 1), np.diff(off))
        i = np.arange(len(conn))
        nxt = i + 1
        last = nxt == off[cell_of + 1]
        if closed:
            nxt = np.where(last, off[cell_of], nxt)
            keep = np.ones(len(i), dtype=bool)
        else:
            keep = ~last
        pairs.append(np.stack([conn[i[keep]], conn[nxt[keep]]], axis=1))
    if not pairs:
        return np.zeros((0, 2), dtype=np.int64)
    e = np.sort(np.concatenate(pairs), axis=1)
    e = e[e[:, 0] != e[:, 1]]
    return np.unique(e, axis=0)


class Elements:
    def __init__(self, scene):
        self.scene = scene
        self.kind = "part"
        self.items: list[tuple[str, object]] = []    # (part, id): what the kind picks
        self.on_changed = None                       # UI hook: something picked / cleared
        self._features = {}                          # part -> (surface, Features)
        self._actors = []
        self._locator = None                         # (volume grid, its cell locator)
        self._edges = {}                             # part -> (surface, mesh_edges)
        self.show_diameter = False                   # Measure Selected: a circle's

    # ---- the kind ----------------------------------------------------------------
    def kinds(self):
        """The kinds this file offers (`kinds_for`)."""
        return kinds_for(self.scene.model)

    def set_kind(self, kind):
        kinds = self.kinds()
        kind = kind if kind in kinds else ("part" if "part" in kinds else kinds[0])
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
        self._take(self._item_at(name, cell, pos) if name is not None else None, additive)

    def _take(self, item, additive):
        if item is None:
            if not additive:
                self.items = []
        elif additive:
            self.items.remove(item) if item in self.items else self.items.append(item)
        else:
            self.items = [item]
        self.refresh()

    # ---- 2D: the nearest node or line on screen -----------------------------------------
    def on_screen(self):
        """Does a click on a 2D file pick the kind by distance on screen (Node, Edge)?"""
        return self.kind in ON_SCREEN

    def part_edges(self, name):
        poly = self.scene.model.parts[name]
        got = self._edges.get(name)
        if got is None or got[0] is not poly:
            got = (poly, mesh_edges(poly))
            self._edges[name] = got
        return got[1]

    def _targets(self, nodes_kind, edges_kind):
        """What a 2D click can reach, over the parts shown: node point ids and edge point
        id pairs, with the part and item of each."""
        sc = self.scene
        out = {"nodes": [], "segs": []}
        for name, poly in sc.model.parts.items():
            if not sc.visible.get(name) or not poly.n_points:
                continue
            pts = np.asarray(poly.points, dtype=float)
            if edges_kind == "mesh_edge" or nodes_kind == "mesh_node":
                e = self.part_edges(name)
                if edges_kind == "mesh_edge":
                    out["segs"].append((name, pts, e, e))
                if nodes_kind == "mesh_node":
                    ids = np.unique(e)
                    out["nodes"].append((name, pts, ids, ids))
            if edges_kind == "feature_edge" or nodes_kind == "feature_node":
                f = self.features(name)
                if edges_kind == "feature_edge" and len(f.seg):
                    out["segs"].append((name, pts, f.seg, f.curve))
                if nodes_kind == "feature_node" and len(f.nodes):
                    out["nodes"].append((name, pts, f.nodes, f.nodes))
        return out

    def _near_2d(self, x, y, nodes_kind=None, edges_kind=None, node_px=0.0):
        """(part, item, world point) of the nearest node / line to display (x, y) within
        PICK_PX, or None."""
        sc = self.scene
        got = self._targets(nodes_kind, edges_kind)
        node_rows = [(n, pts[ids], keys) for n, pts, ids, keys in got["nodes"]]
        seg_rows = [(n, pts[pairs], keys) for n, pts, pairs, keys in got["segs"]]
        nodes = np.concatenate([w for _, w, _ in node_rows]) if node_rows else None
        segs = np.concatenate([w for _, w, _ in seg_rows]) if seg_rows else None
        hit = nearest_on_screen(
            (x, y),
            None if nodes is None else sc.to_display(nodes),
            None if segs is None else sc.to_display(segs.reshape(-1, 3)).reshape(-1, 2, 2),
            sc.pixels(node_px), sc.pixels(PICK_PX))
        if hit is None:
            return None
        what, i, t = hit
        for name, world, keys in (node_rows if what == "node" else seg_rows):
            if i < len(world):
                p = world[i] if what == "node" else world[i, 0] + t * (world[i, 1] - world[i, 0])
                key = keys[i]
                key = int(key) if np.ndim(key) == 0 else tuple(int(v) for v in key)
                return name, key, np.array(p, dtype=float)
            i -= len(world)
        return None

    def click_2d(self, x, y, additive=False):
        """2D: Node / Edge picks the nearest one within PICK_PX on screen (the lines are
        too thin to hit). -> False when there is none (then a click inside a cell picks
        as in 3D: `click`)."""
        node = self.kind in ("mesh_node", "feature_node")
        hit = self._near_2d(x, y, nodes_kind=self.kind if node else None,
                            edges_kind=None if node else self.kind)
        if hit is None:
            return False
        self._take(hit[:2], additive)
        return True

    def snap_2d(self, x, y):
        """Snap to edges (2D): the nearest line's point within PICK_PX, or a node (a line's
        end, a corner; a 2D mesh's nodes) within NODE_SNAP_PX. -> a world point or None."""
        drawing = self.scene.model.file_type == "drawing"
        hit = self._near_2d(x, y, nodes_kind="feature_node" if drawing else "mesh_node",
                            edges_kind="mesh_edge", node_px=NODE_SNAP_PX)
        return None if hit is None else hit[2]

    def _item_at(self, name, cell, pos):
        if self.kind == "volume_cell":               # a boundary or the section's cut
            return self._volume_cell_at(pos)
        if cell is None or cell < 0 or pos is None:
            return None                          # a cut face: no element of a part
        poly = self.scene.model.parts[name]
        pts = np.asarray(poly.points, dtype=float)
        pos = np.asarray(pos, dtype=float)
        k = self.kind
        if k in ("mesh_node", "mesh_edge", "mesh_cell"):
            ids = np.array(poly.get_cell(cell).point_ids, dtype=np.int64)
            if k == "mesh_cell":
                if len(ids) < 3:                  # a 2D mesh's boundary line: the cell beside
                    return self._cell_beside(pos)
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

    def volume_grid(self):
        """The 3D cells (read the first time: the section's), or None."""
        return self.scene.section.volume_grid()

    def _volume_cell_at(self, pos):
        """The volume cell at a clicked point, a hair behind it as seen (the cell under
        a boundary face, or the one the section cuts there)."""
        if pos is None:
            return None
        grid = self.volume_grid()
        if grid is None or not grid.n_cells:
            return None
        if self._locator is None or self._locator[0] is not grid:
            from vtkmodules.vtkCommonDataModel import vtkStaticCellLocator
            loc = vtkStaticCellLocator()
            loc.SetDataSet(grid)
            loc.BuildLocator()
            self._locator = (grid, loc)
        loc = self._locator[1]
        look = np.asarray(self.scene.p.camera.GetDirectionOfProjection(), dtype=float)
        p = np.asarray(pos, dtype=float) + look * 1e-6 * self.scene._diag()
        cell = int(loc.FindCell(p))
        if cell < 0:
            from vtkmodules.vtkCommonCore import reference
            c, sub, d2, cid = [0.0, 0.0, 0.0], reference(0), reference(0.0), reference(0)
            loc.FindClosestPoint(p, c, cid, sub, d2)
            cell = int(cid)
        return (VOLUME, cell) if cell >= 0 else None

    def _cell_beside(self, pos):
        """The face cell nearest `pos` among the parts with faces (a click on a 2D
        mesh's boundary line, drawn over the cells' edges)."""
        best = None
        for n, poly in self.scene.model.parts.items():
            if not self.scene.visible.get(n) or not poly.n_cells or \
                    poly.GetPolys() is None or poly.GetPolys().GetNumberOfCells() == 0:
                continue
            c = int(poly.find_closest_cell(pos))
            if c < 0 or poly.get_cell(c).n_points < 3:
                continue
            d = float(np.linalg.norm(
                np.asarray(poly.get_cell(c).points, dtype=float).mean(axis=0) - pos))
            if best is None or d < best[0]:
                best = (d, n, c)
        return None if best is None else (best[1], best[2])

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
        self._edges = {n: v for n, v in self._edges.items() if parts.get(n) is v[0]}
        if self.kind.startswith("feature"):
            self.items = [it for it in self.items if it[0] in keep]
        elif self.kind == "volume_cell":                 # (moved cells: another grid)
            self.items, self._locator = [], None
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
        if self.kind == "volume_cell" and self.items:
            grid = self.volume_grid()
            if grid is not None:
                ids = [k for _, k in self.items if 0 <= k < grid.n_cells]
                if ids:
                    faces.append(grid.extract_cells(ids).extract_surface())
        circle = self.circle() if self.show_diameter else None
        if circle is not None:                           # Measure Selected ▸ Show Diameter
            c, u = circle["center"], circle["u"]
            r = circle["radius"]
            lines.append(np.array([[c - r * u, c + r * u]]))
            nodes.append(c[None])
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
        self.items = [it for it in self.items if it[0] in parts or it[0] == VOLUME]
        if self.kind == "part" or not self.items:
            return None
        if self.kind == "volume_cell":
            grid = self.volume_grid()
            n = len(self.items)
            count = f"{n} {'volume cell' if n == 1 else 'volume cells'} selected"
            if grid is None:
                return count, ""
            ids = [k for _, k in self.items if 0 <= k < grid.n_cells]
            sizes = grid.extract_cells(ids).compute_cell_sizes(length=False, area=False)
            s, unit = self.scene.measure.unit_scale()
            u3 = f" {unit}³" if unit else ""
            return count, f"volume {fmt(abs(float(np.sum(sizes.cell_data['Volume']))) * s ** 3)}{u3}"
        one, many = WORDS[self.kind]
        if self.kind == "mesh_cell" and self.scene.model.file_type == "mesh2d":
            one, many = CELL_2D[1:]
        if self.scene.model.file_type == "drawing" and self.kind in DRAWING:
            one, many = DRAWING[self.kind][1:]
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


    # ---- Measure Selected ----------------------------------------------------------------
    def circle(self):
        """The last picked edge when it is a circle or an arc: center, radius, normal and
        a direction in its plane (for the diameter), else None."""
        if not self.items or self.kind not in ("feature_edge",):
            return None
        from meshviewer.core.element_info import fit_circle, ordered_path
        name, key = self.items[-1]
        poly = self.scene.model.parts.get(name)
        if poly is None:
            return None
        path = ordered_path(self.features(name).curve_segments(key), poly.points)
        c = fit_circle(path)
        if c is None:
            return None
        u = path[0] - c["center"]
        u -= (u @ c["normal"]) * c["normal"]
        c["u"] = u / (np.linalg.norm(u) or 1.0)
        return c

    def set_show_diameter(self, on):
        self.show_diameter = bool(on)
        self.refresh(notify=False)
