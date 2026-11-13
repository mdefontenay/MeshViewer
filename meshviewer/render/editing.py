"""Scene ▸ the parts change: another mesh quality (CAD), a new name, the Edit
section's rotate / mirror / move with undo and the grey original."""
from __future__ import annotations

import numpy as np
import pyvista as pv
from vtkmodules.vtkFiltersCore import vtkAppendPolyData

from meshviewer.core import transform as xf
from meshviewer.core.polys import bare
from meshviewer.render.style import FEATURE_ANGLE, PART_COLORS, THEMES


class Editing:
    # ---- mesh quality (STEP) -------------------------------------------------
    @property
    def can_retessellate(self):
        return self.model.retessellate is not None

    def replace_parts(self, parts, level):
        """Swap in a new tessellation, keeping colours, visibility, selection, section."""
        cam = self.p.camera_position
        self._drop_part_actors()
        parts = {self._alias.get(k, k): v for k, v in parts.items()}   # keep renames
        self.model.parts = parts
        self.model.quality = level
        self._bounds = None
        self._set_names(sorted(parts, key=str.lower))
        for n in self.names:
            self.colors.setdefault(n, PART_COLORS[len(self.colors) % len(PART_COLORS)])
            self.visible.setdefault(n, True)
        self.selected_parts = [n for n in self.selected_parts if n in parts]
        self.selected_faces = {}                     # face ids change with the mesh
        self._build_surfaces()
        self.set_feature_edges(self.state["feature_edges"], render=False)
        self.section.rebuild()
        self._refresh_face_overlay()
        self.set_selection(self.selected_parts, render=False)
        self.measure._changed()
        self.elements.parts_changed()
        self.p.camera_position = cam
        self.p.render()

    # --- rename a part (any file type; Export writes the new names) ----
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
                  self._flipped, self._orig_points, self.hidden_faces, self._display):
            rekey(d)
        self._set_names(new if n == old else n for n in self.names)   # same block index
        self.selected_parts = [new if n == old else n for n in self.selected_parts]
        self._outlined = tuple(new if n == old else n for n in self._outlined)
        orig = next((k for k, v in self._alias.items() if v == old), old)
        self._alias[orig] = new                       # re-meshed STEP parts keep it
        self.measure._changed()
        return True

    # ---- Edit section: rotate / mirror, move + undo + original -------
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
        """every change so far, oldest first (the Edit section lists them)."""
        return [label for _, label in self._edit_history]

    def _set_edit_state(self, r, t):
        if self._orig_points is None:               # first edit: keep the file's points
            self._orig_points = {n: np.array(p.points) for n, p in self.model.parts.items()}
        old = (self.model.transform, self.model.offset)
        self._bounds = None
        for n, poly in self.model.parts.items():
            self._flipped[n] = xf.set_surface(poly, self._orig_points[n], r, t,
                                              self._flipped.get(n, False))
        self.model.transform, self.model.offset = np.asarray(r, dtype=float), np.asarray(t, float)
        self.section.follow_edit(xf.delta(old, (r, t)))   # plane + volume cells follow
        self.measure.forget_points()                # picked points were in the old place
        self.quality.after_edit()                   # bad cells move along
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
                src = bare(poly, pts)
                app.AddInputData(src.extract_feature_edges(
                    feature_angle=FEATURE_ANGLE, boundary_edges=True, feature_edges=True,
                    manifold_edges=False, non_manifold_edges=False))
            app.Update()
            self._original_actor = self.p.add_mesh(
                pv.wrap(app.GetOutput()), color=THEMES[self._dark]["grid"], opacity=0.7,
                line_width=1.5, lighting=False, pickable=False, reset_camera=False)
        if self._original_actor is not None:
            self._original_actor.SetVisibility(bool(want))
