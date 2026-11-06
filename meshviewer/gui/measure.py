"""Measurements: point-to-point distance, surface area, enclosed volume. No Qt.

Distance  — click two points on the model (or on a section cut face).
            Gives ΔX, ΔY, ΔZ and the straight-line (minimum) distance.
Area      — of the selected parts / boundaries, or of selected CAD faces.
Volume    — when the selection encloses a volume (one closed solid, or several
            surfaces that together close up, e.g. wing skins + tip + root).

For STEP / IGES / BREP, area and volume come from the exact CAD geometry when
possible; otherwise they are computed from the triangles (precision then
depends on the mesh quality) and labelled "from mesh".

Markers are drawn in an overlay layer so they stay visible through the model.
"""
from __future__ import annotations

import numpy as np
import pyvista as pv
from vtkmodules.vtkFiltersCore import vtkMassProperties
from vtkmodules.vtkFiltersGeometry import vtkDataSetSurfaceFilter
from vtkmodules.vtkFiltersModeling import vtkSelectEnclosedPoints
from vtkmodules.vtkRenderingCore import (
    vtkActor, vtkBillboardTextActor3D, vtkPolyDataMapper, vtkRenderer,
)

AXIS_COLORS = ("#ff453a", "#32d74b", "#0a84ff")      # ΔX red, ΔY green, ΔZ blue

# Display units: metres per unit. None = show the file's numbers without a unit.
UNITS = {"mm": 1e-3, "cm": 1e-2, "m": 1.0, "in": 0.0254, "ft": 0.3048}
LINE_GRAY = "#8e8e93"                                 # the distance line itself
POINT_GRAY = "#d1d1d6"
POINT_PX = 13                     # picked-point dots, screen pixels (same size at any zoom)


def _inside(point, closed_surface):
    """Is `point` inside the closed surface? (VTK, no PyVista version issues)"""
    sel = vtkSelectEnclosedPoints()
    sel.SetInputData(pv.PolyData(np.asarray([point])))
    sel.SetSurfaceData(closed_surface)
    sel.CheckSurfaceOff()
    sel.Update()
    return bool(sel.IsInside(0))


def _surface(ds):
    if isinstance(ds, pv.PolyData):
        return ds
    f = vtkDataSetSurfaceFilter()
    f.SetInputData(ds)
    f.Update()
    return pv.wrap(f.GetOutput())


def fmt(v, units=""):
    """At least 5 significant digits (0.026907 m, 60.022 mm, 1,935.221 mm²)."""
    if v is None:
        return "—"
    a = abs(v)
    if a == 0:
        s = "0"
    elif a >= 1e7 or a < 1e-4:
        s = f"{v:.5g}"
    else:
        dec = int(min(8, max(3, 4 - np.floor(np.log10(a)))))
        s = f"{v:,.{dec}f}".rstrip("0").rstrip(".")
    return f"{s} {units}".strip()


class Measure:
    def __init__(self, scene):
        self.scene = scene
        self.p = scene.p
        self.mode = "off"            # "off" | "distance" | "area"
        self.pick_faces = False      # area mode on CAD: pick single CAD faces
        self.snap = False            # distance: snap to the nearest mesh vertex
        self.points = []             # up to 2 picked 3D points
        self.display_unit = scene.model.units or None   # unit chosen in the toolbar
        self.on_changed = None       # UI hook: called with self.result()
        self._overlay = None
        self._marker_actors = []

    # ---- mode ------------------------------------------------------------
    def set_mode(self, mode):
        self.mode = mode
        self.points = []
        if mode != "area":
            self.scene.clear_face_selection(render=False)
        self._draw()
        self._changed()

    def set_pick_faces(self, on):
        self.pick_faces = bool(on)
        self.scene.clear_face_selection(render=False)
        self.scene.set_selection([], notify=True)   # parts and faces aren't mixed
        self._changed()

    def forget_points(self):
        """NEW (v2.23): drop picked distance points (the model moved), keep the selection."""
        if self.points:
            self.points = []
            self._draw()
            self._changed()

    def clear(self):
        self.points = []
        self.scene.clear_face_selection(render=False)
        self.scene.set_selection([], notify=True)
        self._draw()
        self._changed()

    # ---- distance --------------------------------------------------------
    def add_point(self, pos, name=None, cell_id=None):
        if pos is None:
            return
        pos = np.asarray(pos, dtype=float)
        if self.snap and name is not None and cell_id is not None and cell_id >= 0:
            poly = self.scene.model.parts[name]
            ids = poly.get_cell(cell_id).point_ids
            pts = poly.points[ids]
            pos = pts[np.argmin(np.linalg.norm(pts - pos, axis=1))]
        if len(self.points) >= 2:
            self.points = []
        self.points.append(pos)
        self._draw()
        self._changed()

    # ---- units -----------------------------------------------------------------
    def set_display_unit(self, unit):
        self.display_unit = unit if unit in UNITS else None
        self.scene.refresh_grid(render=False)       # NEW (v2.17): axis numbers + "(unit)"
        self._draw()
        self._changed()

    def unit_scale(self):
        """(factor from file numbers to displayed numbers, unit label).
        File with units (STEP/IGES = mm): converted. File without units: the
        chosen unit is just a label (the file is taken to be in that unit)."""
        du, mu = self.display_unit, self.scene.model.units
        if du is None:
            return 1.0, ""
        return (UNITS[mu] / UNITS[du] if mu in UNITS else 1.0), du

    # ---- results -----------------------------------------------------------
    def result(self):
        s, units = self.unit_scale()
        base = {"units": units, "file_units": self.scene.model.units,
                "unit_assumed": bool(units) and not self.scene.model.units}
        if self.mode == "distance":
            r = {"mode": "distance", **base, "points": [(p * s).tolist() for p in self.points]}
            if len(self.points) == 2:
                d = self.points[1] - self.points[0]
                d[np.abs(d) < self.scene.section.diag * 1e-9] = 0.0     # no "4.6e-17"
                d = d * s
                r.update(dx=float(d[0]), dy=float(d[1]), dz=float(d[2]),
                         distance=float(np.linalg.norm(d)))
            return r
        if self.mode == "area":
            r = {"mode": "area", **base, **self._area_volume()}
            if r.get("area") is not None:
                r["area"] *= s ** 2
            if r.get("volume") is not None:
                r["volume"] *= s ** 3
            return r
        return {"mode": "off", **base}

    def _area_volume(self):
        sc, src = self.scene, self.scene.model.source
        faces = {n: ids for n, ids in sc.selected_faces.items() if ids}
        if self.pick_faces and faces:
            items = [(n, sorted(ids)) for n, ids in faces.items()]
        else:
            items = [(n, None) for n in sc.selected_parts]
        if not items:
            return {"count": 0}
        what = "faces" if (self.pick_faces and faces) else self.scene.model.group_title.lower()
        count = sum(len(ids) for _, ids in items) if what == "faces" else len(items)

        # Area: exact for CAD, else sum of triangle areas.
        if src is not None:
            area, exact = sum(src.exact_area(n, ids) for n, ids in items), True
        else:
            area, exact = sum(self._piece(n, ids).area for n, ids in items), False

        # Volume: exact if whole closed CAD solids are selected...
        volume, vol_exact, closed = None, False, False
        whole = [n for n, ids in items if ids is None or
                 (src is not None and len(ids) == len(src.part_faces.get(n, [])))]
        if src is not None and len(whole) == len(items) and \
                all(src.exact_volume(n) is not None for n in whole):
            volume, vol_exact, closed = sum(src.exact_volume(n) for n in whole), True, True
        else:                         # ...else from the triangles, if they close up
            volume = self._mesh_volume(items)
            closed = volume is not None
        return {"count": count, "what": what, "n_parts": len(items),
                "area": area, "area_exact": exact,
                "volume": volume, "volume_exact": vol_exact, "closed": closed}

    def _piece(self, name, face_ids):
        poly = self.scene.model.parts[name]
        if face_ids is None:
            return poly
        mask = np.isin(poly.cell_data["face_id"], face_ids)
        return _surface(poly.extract_cells(np.flatnonzero(mask)))

    def _mesh_volume(self, items):
        pieces = [self._piece(n, ids) for n, ids in items]
        surf = _surface(pv.merge(pieces)) if len(pieces) > 1 else pieces[0]
        surf = surf.triangulate().clean()
        if surf.n_cells == 0 or surf.n_open_edges > 0:
            return None                              # has holes: no enclosed volume
        shells = []
        for body in surf.split_bodies():             # one closed shell at a time
            if body is None or body.n_cells == 0:
                continue
            shell = _surface(body).compute_normals(
                auto_orient_normals=True, consistent_normals=True, cell_normals=False)
            mp = vtkMassProperties()
            mp.SetInputData(shell)
            mp.Update()
            shells.append((abs(mp.GetVolume()), shell))
        # Nested shells (e.g. a far-field box around a wing): a shell inside
        # another is a hole, so it is subtracted — gives the fluid volume.
        shells.sort(key=lambda t: -t[0])
        total = 0.0
        for i, (vol, shell) in enumerate(shells):
            probe = shell.points[0]
            depth = sum(_inside(probe, outer) for _, outer in shells[:i])
            total += vol if depth % 2 == 0 else -vol
        return total

    # ---- screenshots: show the same markers in an off-screen window -----------
    def add_to(self, ren_win, camera, k, clone=lambda a: a):
        actors = [*self._marker_actors, *self.scene.origin_actors()]   # v2.18: + origin
        if not actors:
            return
        ren_win.SetNumberOfLayers(3)
        self._shot_layer, self._shot_text = vtkRenderer(), vtkRenderer()
        for lay, n in ((self._shot_layer, 1), (self._shot_text, 2)):
            lay.SetLayer(n)
            lay.SetActiveCamera(camera)
        self._shot_saved = []
        for a in actors:
            if isinstance(a, vtkBillboardTextActor3D):
                tp = a.GetTextProperty()
                self._shot_saved.append((tp, "font", tp.GetFontSize()))
                tp.SetFontSize(tp.GetFontSize() * k)
                t2 = vtkBillboardTextActor3D()            # text: a fresh copy
                t2.SetInput(a.GetInput())
                t2.SetPosition(a.GetPosition())
                t2.SetTextProperty(tp)
                self._shot_text.AddActor(t2)
            else:
                prop = a.GetProperty()
                self._shot_saved.append((prop, "line", prop.GetLineWidth()))
                self._shot_saved.append((prop, "point", prop.GetPointSize()))
                prop.SetLineWidth(prop.GetLineWidth() * k)
                prop.SetPointSize(prop.GetPointSize() * k)
                self._shot_layer.AddActor(clone(a))
        ren_win.AddRenderer(self._shot_layer)
        ren_win.AddRenderer(self._shot_text)

    def remove_from(self, ren_win):
        layer = getattr(self, "_shot_layer", None)
        if layer is None:
            return
        setter = {"font": "SetFontSize", "line": "SetLineWidth", "point": "SetPointSize"}
        for obj, kind, v in self._shot_saved:
            getattr(obj, setter[kind])(v)
        for lay in (layer, self._shot_text):
            lay.RemoveAllViewProps()
            ren_win.RemoveRenderer(lay)
        self._shot_layer = self._shot_text = None

    def _changed(self):
        if self.on_changed:
            self.on_changed(self.result())

    # ---- markers (overlay layer, always visible) -------------------------------
    def _layer(self, text=False):
        """Overlay renderers on top of the model: layer 1 = markers, 2 = labels."""
        if self._overlay is None:
            rw = self.p.ren_win
            rw.SetNumberOfLayers(max(3, rw.GetNumberOfLayers()))
            self._overlay, self._text_overlay = vtkRenderer(), vtkRenderer()
            for lay, n in ((self._overlay, 1), (self._text_overlay, 2)):
                lay.SetLayer(n)
                lay.InteractiveOff()
                lay.SetActiveCamera(self.p.renderer.GetActiveCamera())
                rw.AddRenderer(lay)
        return self._text_overlay if text else self._overlay

    def _add(self, poly, color, line_width=2.0, lit=True):
        m = vtkPolyDataMapper()
        m.SetInputData(poly)
        m.ScalarVisibilityOff()        # pv.Line carries a scalar array that tinted lines red→blue
        a = vtkActor()
        a.SetMapper(m)
        a.GetProperty().SetColor(pv.Color(color).float_rgb)
        a.GetProperty().SetLineWidth(line_width)
        a.GetProperty().SetLighting(lit)
        a.PickableOff()
        self._layer().AddActor(a)
        self._marker_actors.append(a)
        return a

    def _draw(self):
        if self._marker_actors:
            for a in self._marker_actors:
                self._layer().RemoveActor(a)
                self._layer(text=True).RemoveActor(a)
        self._marker_actors = []
        if self.mode == "distance" and self.points:
            if len(self.points) == 2:
                a, b = self.points
                self._add(pv.Line(a, b), LINE_GRAY, 3.0, lit=False)
                corner1, corner2 = np.array([b[0], a[1], a[2]]), np.array([b[0], b[1], a[2]])
                for (p0, p1), c in zip(((a, corner1), (corner1, corner2), (corner2, b)),
                                       AXIS_COLORS):
                    if np.linalg.norm(p1 - p0) > 1e-12:
                        self._add(pv.Line(p0, p1), c, 2.5, lit=False)   # v2.16: was 1.5
            # NEW (v2.16): picked points are screen-size dots (fixed pixels), not
            # spheres in model units that grew huge when zooming in. Drawn last = on top.
            dots = self._add(pv.PolyData(np.array(self.points, dtype=float)), POINT_GRAY)
            dots.GetProperty().SetRepresentationToPoints()
            dots.GetProperty().SetPointSize(POINT_PX)
            dots.GetProperty().SetRenderPointsAsSpheres(True)
            if len(self.points) == 2:
                a, b = self.points
                label = vtkBillboardTextActor3D()
                s, unit = self.unit_scale()
                label.SetInput(" " + fmt(float(np.linalg.norm(b - a)) * s, unit) + " ")
                label.SetPosition(*((a + b) / 2))
                tp = label.GetTextProperty()
                tp.SetFontSize(15)
                tp.SetBold(True)
                tp.SetColor(1, 1, 1)
                tp.SetBackgroundColor(pv.Color("#3a3a3c").float_rgb)
                tp.SetBackgroundOpacity(0.9)
                tp.SetFrame(False)
                label.PickableOff()
                self._layer(text=True).AddActor(label)
                self._marker_actors.append(label)
        self.p.render()
