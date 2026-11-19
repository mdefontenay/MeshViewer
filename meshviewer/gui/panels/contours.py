"""The Contours tool — the boundaries colored by a solution field (files that carry
one: a solver's Tecplot boundary output, .dat). Laid out as Plots:

    Contours
      [ New Contour ]
      ▾ Contour 1        its field, unit, range, color scale, color bar (contour_editor.py)
      ▸ Contour 2

Every contour has its tab under the view (gui/window_pages.py): choosing one shows the
model colored by it, with its own camera and Show ▾ toggles, and opens its fold-out here
(the others fold). Contours are drawn only in their tabs, always (`tab`): the 3D View
tab shows the model alone. Editing a contour shows its tab. A results file starts with
one, Contour 1. A contour's auto range: the boundaries shown in its own tab (each tab
shows and hides parts on its own, gui/window_pages.py).

Custom… (in both unit menus): a unit typed for this file only (kept with the file's units in
scene.results_settings, never in core/units or the app's settings); nothing converts it:
the values are shown as written, labeled with it.

Units: a field Mesh Viewer knows (core/field_kinds: pressure, Mach, stress…) offers its
quantity's units, or none (Mach, y+, cp); a field it doesn't know, every unit by
quantity; a position, lengths (the file's unit, shown in the toolbar's until another is
picked). Solvers often write non-dimensional numbers: "As written" uses them as they are.
A field's units are the same in every contour, and in Plots.

Gradient (F15): |∇f| along the surface, per unit length — large at shocks, leading
edges, separation lines.

The range is the visible boundaries' min to max unless typed, and follows when
boundaries are shown or hidden. The color bar is drawn over the 3D view
(render/colorbar.py; it can be dragged); in bands, the boundaries get the same bands.
Remembered per file (scene.results_settings: on, active, units, contours); a new contour
starts with the color bar's settings last chosen ("results/color_bar").

Time steps (OpenFOAM): another step shown (scene.time_listeners) draws again. A contour
whose ▸ Animation is on with Timeline keeps its auto Min / Max over every step: the steps'
ranges are read once in the background ("Reading time steps…"), kept by the case, and
the visible boundaries' are taken from them (`_timeline`).
"""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

from meshviewer.core.field_kinds import field_kind
from meshviewer.core.fields import (COLORMAPS, DEFAULT_MAP, SPEED, field_values,
                                    dead_fields, gradient_magnitude, planar, solution_fields,
                                    speed_values, ticks)
from meshviewer.core.plots import AXES, COORD
from meshviewer.core.units import (CUSTOM, NO_UNIT, QUANTITIES, convert_field, field_scale,
                                   is_custom, nice_num, unit_quantity)
from meshviewer.gui.forms import note
from meshviewer.gui.panels.contour_editor import (  # noqa: F401  (field_label, grouped: Plots)
    BAR_DEFAULTS, ContourEditor, clean_contour, field_label, grouped, new_contour,
    save_bar_defaults,
)
from meshviewer.gui.sheets import ask_text
from meshviewer.gui.widgets import CollapsibleSection

GRAD = "__grad__"                    # point array: |∇ field| (kept on the parts)
POS = "__pos_"                       # point array: the X / Y / Z of each node ("__pos_x")


class ContoursPanel(QWidget):
    units_changed = Signal()                      # a field's units: the plots follow
    added = Signal(int)
    removed = Signal(int)
    renamed = Signal(int)
    show_contour = Signal(int)                    # open its tab
    animation_changed = Signal()                  # a contour's ▸ Animation switched / set
    fields_changed = Signal()                     # the fields offered (every step read)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = None
        self.fields = []
        self.contours = []                        # their dicts (the scene's, remembered)
        self.editors = {}                         # id -> (CollapsibleSection, editor)
        self.active = None                        # the contour last shown or edited
        self.tab = None                           # the contour whose tab shows (drawn)
        self.range = None                         # its (lo, hi), in the unit shown
        self._units = {}                          # field -> [file unit, shown unit]
        self._steps_job = None                    # reading the steps that tell fields apart
        self._steps_failed = False
        self._field_job = None                    # (field, stop flag, job): Timeline's read
        self._names = []
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.new = QPushButton("New Contour")
        self.new.setObjectName("ApplyButton")
        self.new.setCursor(Qt.PointingHandCursor)
        self.new.setToolTip("New Contour")
        self.new.clicked.connect(lambda: self.add())
        lay.addWidget(self.new)
        self.stats = note()                       # no fields in this file
        self.stats.setVisible(False)
        lay.addWidget(self.stats)
        self.list = QVBoxLayout()
        self.list.setSpacing(6)
        lay.addLayout(self.list)

    # ---- binding ---------------------------------------------------------------------------
    def fields_of(self, model):
        """The file's fields, then the position of each node: X, Y, Z. Not on a 2D file:
        the out-of-plane z components, Z. Never: a field that doesn't vary over the faces
        a contour colors, at any time step (once they are read: `dead_fields`) — on a 2D
        case, one only on the boundary lines (phi) or flat over the cells."""
        fields = planar(self._names, model)
        steps = None
        if model.case is not None and len(model.times) > 1:
            sampled = model.case.range_steps()
            if model.case.ranges_read(sampled):
                steps = [model.case.known_ranges(i) for i in sampled]
        dead = dead_fields(model.parts, fields, steps)
        fields = [f for f in fields if f not in dead]
        axes = AXES if model.dim != 2 else [a for a in AXES if a != "z"]
        return fields + [COORD + a for a in axes] if fields else fields

    def bind(self, scene):
        if self.scene is not None:
            self.scene.results.clear()
            self.scene.colorbar.hide()
            self.scene.colorbar.on_moved = None
            if self.model_changed in self.scene.visibility_listeners:
                self.scene.visibility_listeners.remove(self.model_changed)
            if self.time_changed in self.scene.time_listeners:
                self.scene.time_listeners.remove(self.time_changed)
        for sec, _ed in list(self.editors.values()):
            self._drop(sec)
        self.editors = {}
        self.scene = None                          # no saving while setting up
        self._names = solution_fields(scene.model.parts)   # every field (the step opened)
        self.fields = self.fields_of(scene.model)
        st = getattr(scene, "results_settings", None) or {}
        if "contours" not in st and st.get("field") is not None:   # one, before 2.5.1
            st = {"on": st.get("on"), "units": st.get("units"), "active": 1,
                  "contours": [dict(st, id=1, name="Contour 1")]}
        self._units = {k: list(v) for k, v in (st.get("units") or {}).items()
                       if isinstance(v, (list, tuple)) and len(v) == 2}
        self.contours = [c for c in (clean_contour(c, i + 1) for i, c in
                                     enumerate(st.get("contours") or [])) if c is not None]
        if not self.contours and self.fields:      # a results file: one to start with
            self.contours = [new_contour(1, "Contour 1", self._default_field(scene.model.dim))]
        ids = [c["id"] for c in self.contours]
        self.active = st.get("active") if st.get("active") in ids else (ids[0] if ids else None)
        self.tab = None                            # the window opens the tab remembered
        self.scene = scene
        scene.visibility_listeners.append(self.model_changed)   # auto range: shown boundaries
        scene.time_listeners.append(self.time_changed)         # another time step
        scene.field_users.append(lambda: [c["field"] for c in self.contours
                                          if c["field"] and not c["field"].startswith(COORD)])
        self._steps_job, self._steps_failed = None, False
        if self.time_count() > 1 and self.fields:                # which fields vary: read
            self._all_ranges()                                   # every step (background)
        scene.colorbar.on_moved = self._bar_moved
        for c in self.contours:
            self._editor(c, expanded=False)
        self.stats.setText("" if self.fields else "No solution fields in this file.")
        self.stats.setVisible(not self.fields)
        self.new.setEnabled(bool(self.fields))
        self._place_bar()
        self._changed(save=False)

    def _default_field(self, dim=3):
        """Contour 1's field: y+ on boundaries (else cp, p, speed); a 2D flow: p, speed."""
        keys = {(field_kind(f).key if field_kind(f) else f): f for f in self.fields}
        for k in (("p", SPEED) if dim == 2 else ("yplus", "cp", "p", SPEED)):
            if k in keys:
                return keys[k]
        return self.fields[0] if self.fields else None

    def settings(self):
        return {"active": self.active,
                "units": {k: list(v) for k, v in self._units.items()},
                "contours": [dict(c, bar=dict(c["bar"])) for c in self.contours]}
    # (each contour's "view": its tab's camera and Show ▾ toggles, kept by the window)

    def contour(self, ident):
        return next((c for c in self.contours if c["id"] == ident), None)

    @property
    def current(self):
        """The active contour's dict (None: none)."""
        return self.contour(self.active)

    # ---- add / rename / remove ----------------------------------------------------------------
    def _next_name(self):
        used = {c["name"] for c in self.contours}
        k = 1
        while f"Contour {k}" in used:
            k += 1
        return f"Contour {k}"

    def add(self, field=None, name=None):
        """A new contour (the active one's field, or the default), opened: its tab and
        its fold-out."""
        if self.scene is None or not self.fields:
            return None
        ident = max((c["id"] for c in self.contours), default=0) + 1
        cur = self.current
        c = new_contour(ident, name or self._next_name(),
                        field or (cur["field"] if cur else self._default_field()))
        self.contours.append(c)
        self._editor(c, expanded=False)
        self.active = ident
        self._changed()
        self.added.emit(ident)
        return ident

    def rename(self, ident, name=None):
        c = self.contour(ident)
        if c is None:
            return
        if name is None:
            if self.scene:
                self.scene.end_stuck_drag()
            ask_text(self.window(), "Rename Contour", "Name", c["name"],
                     lambda text: self.rename(ident, text))
            return
        name = name.strip()
        if name:
            c["name"] = name
            self.editors[ident][0].set_title(name)
            self._save()
            self.renamed.emit(ident)

    def remove(self, ident):
        c = self.contour(ident)
        if c is None:
            return
        self.contours.remove(c)
        sec, _ = self.editors.pop(ident)
        self._drop(sec)
        if self.active == ident:
            self.active = self.contours[0]["id"] if self.contours else None
        if self.tab == ident:
            self.tab = None
        self._changed()
        self.removed.emit(ident)

    def _drop(self, sec):
        self.list.removeWidget(sec)
        sec.hide()
        sec.setParent(None)
        sec.deleteLater()

    def _editor(self, c, expanded):
        ed = ContourEditor(self, c)
        sec = CollapsibleSection(c["name"], ed, f"contour{c['id']}", remember=False,
                                 start_open=expanded, sub=True)
        sec.header.setToolTip("Click to show or hide its settings (opening one shows it)")
        sec.toggled.connect(lambda on, i=c["id"]: on and self._unfolded(i))
        self.list.addWidget(sec)
        self.editors[c["id"]] = (sec, ed)

    def _unfolded(self, ident):
        """A contour's fold-out opened: its numbers (not kept up while folded), its tab."""
        c = self.contour(ident)
        if c is not None and self.scene is not None:
            self.editors[ident][1].show_info(self.info(c))
        self.show_contour.emit(ident)

    def expand_only(self, ident):
        """Its fold-out open, the others folded -> its section (None: no such contour)."""
        for i, (sec, _ed) in self.editors.items():
            if (i == ident) != sec.expanded:
                sec.set_expanded(i == ident)
        return self.editors[ident][0] if ident in self.editors else None

    # ---- which contour is drawn ----------------------------------------------------------
    def set_tab(self, ident):
        """The tab shown under the view: a contour's (drawn) or None (the 3D View, a
        plot…: nothing drawn)."""
        if ident is not None and self.contour(ident) is None:
            ident = None
        self.tab = ident
        if ident is not None:
            self.active = ident
            self._place_bar()
        self._changed()

    def contour_changed(self, ident):
        """An editor changed its contour: its tab shown (and so it is drawn)."""
        self.active = ident
        if ident != self.tab:
            self.show_contour.emit(ident)              # the window opens its tab
            if self.tab != ident:                      # (no window: drawn anyway)
                self.tab = ident
                self._place_bar()
        self._changed()

    def bar_changed(self, ident):
        """A color bar setting: kept as the start of a new contour's, and drawn (its
        place too: Reset Color Bar)."""
        c = self.contour(ident)
        if c is not None:
            save_bar_defaults(c["bar"])
            if ident == self.tab and self.scene is not None:
                self.scene.colorbar.set_offset(c["bar"]["pos"])
        self.contour_changed(ident)

    def _bar_moved(self):
        """The bar dragged: its place, the shown contour's."""
        c = self.contour(self.tab)
        if c is not None and self.scene is not None:
            c["bar"]["pos"] = [round(float(v), 1) for v in self.scene.colorbar.offset]
            save_bar_defaults(c["bar"])
            self._save()

    def _place_bar(self):
        c = self.current
        if c is not None and self.scene is not None:
            self.scene.colorbar.set_offset(c["bar"]["pos"])

    # ---- units ---------------------------------------------------------------------------
    def unit_of(self, field):
        """(quantity, file unit, shown unit) of a field; quantity None = no unit.
        Its quantity: from its name (p, ρ, u, T…), else from the unit picked for it in
        the file; a position: a length, in the file's unit, shown in the one picked (or
        the toolbar's until one is)."""
        model = self.scene.model if self.scene is not None else None
        said = (model.field_units if model is not None else {}).get(field, NO_UNIT)
        fu, su = self._units.get(field, [said, NO_UNIT])   # the file's own unit at first
        if field and field.startswith(COORD):
            fu = model.units if model is not None and model.units in QUANTITIES["length"] \
                else NO_UNIT
            if su not in QUANTITIES["length"]:
                du = self.scene.measure.display_unit if self.scene is not None else None
                su = du if du in QUANTITIES["length"] else fu
            return ("length", fu, su) if fu else (None, NO_UNIT, NO_UNIT)
        kind = field_kind(field)
        if kind is not None and kind.quantity is None:
            return None, NO_UNIT, NO_UNIT                  # Mach, y+…: no unit
        if is_custom(fu):                                  # typed for this file (Custom…):
            return CUSTOM, fu, (su if is_custom(su) else fu)   # nothing converts it
        q = kind.quantity if kind is not None else unit_quantity(fu)   # known: no choice
        if q is not None and fu and fu not in QUANTITIES[q] and unit_quantity(fu):
            q = unit_quantity(fu)          # as the file says: kinematic p in m²/s²
        if q is None:
            return None, NO_UNIT, NO_UNIT
        table = QUANTITIES[q]
        su = su if su in table or is_custom(su) else (fu if fu in table else next(iter(table)))
        return q, (fu if fu in table else NO_UNIT), su

    def shown_values(self, field, vals):
        """Field values in the unit shown (unchanged when the file's has none, or a unit
        typed for the file is involved: only its name is shown)."""
        q, fu, su = self.unit_of(field)
        return vals if q is None or not fu or is_custom(fu) or is_custom(su) else \
            convert_field(vals, q, fu, su)

    def unit_label(self, field):
        q, fu, su = self.unit_of(field)
        return su if q is not None and fu else ""

    def set_units(self, field, fu, su):
        """Unit in file / Shown in picked for a field: every contour of it follows (a typed
        Min / Max converted, in the same quantity), and the plots."""
        old = self.unit_of(field)
        if field.startswith(COORD):
            fu = NO_UNIT                                # (the file's own, not stored)
        elif unit_quantity(fu) != unit_quantity(old[1]) and field_kind(field) is None:
            su = fu                                     # another quantity: shown as written
        self._units[field] = [fu, su]
        new = self.unit_of(field)
        for c in self.contours:
            if c["field"] != field:
                continue
            if new != old:
                for k in ("lo", "hi"):
                    v = c[k]
                    if v is not None and old[1] and new[1] and old[0] == new[0]:
                        c[k] = float(convert_field(convert_field(v, old[0], old[2], old[1]),
                                                   new[0], new[1], new[2]))
                    elif v is not None:
                        c[k] = None
            self.editors[c["id"]][1].sync()
        self._changed()
        self.units_changed.emit()

    def model_changed(self):
        self._changed(save=False)

    # ---- time steps ----------------------------------------------------------------------
    def time_count(self):
        return self.scene.time_count if self.scene is not None else 0

    def time_text(self):
        """"t = 0.5 · Step 2 / 3" (the step shown), or "—"."""
        m = self.scene.model if self.scene is not None else None
        if m is None or self.time_count() < 2 or m.time_index is None:
            return "—"
        i = m.time_index
        return f"t = {m.time_labels[i]} · Step {i + 1} / {len(m.times)}"

    def time_changed(self):
        """Another time step shown: the step in each ▸ Animation, the numbers, the active
        contour drawn."""
        text = self.time_text()
        for _sec, ed in self.editors.values():
            ed.anim.step_label.setText(text)
        self._changed(save=False)

    def animation_changed_for(self, ident):
        """A contour's ▸ Animation switched or its range picked."""
        self._save()
        self.animation_changed.emit()
        self._changed(save=False)

    def _timeline(self, field, c):
        """(min, max, min above zero) of a field over every time step, on contour c's
        visible boundaries — or None: not Timeline, or the steps are still being read."""
        a = c.get("anim") or {}
        if not a.get("on") or a.get("range") != "timeline" or self.time_count() < 2:
            return None
        if self._all_ranges() is None:
            return None
        case, n = self.scene.model.case, self.time_count()
        if not case.ranges_read(range(n), [field]):        # its every step: read (once)
            self._read_field(field)
        steps = [r for r in (case.known_ranges(i) for i in range(n)) if r is not None]
        shown = self._shown(c)
        lo = hi = pos = None
        for per_part in steps:
            for name, per in per_part.items():
                if name not in shown or field not in per:
                    continue
                a0, a1, ap, _mark = per[field]
                lo = a0 if lo is None else min(lo, a0)
                hi = a1 if hi is None else max(hi, a1)
                if ap is not None:
                    pos = ap if pos is None else min(pos, ap)
        return None if lo is None else (lo, hi, pos)

    def _all_ranges(self):
        """The ranges of the steps that tell the fields apart (every step of a short case,
        a few spread over a long one: `FoamCase.range_steps`), every field; else they are
        read in the background (once) and None for now."""
        case = self.scene.model.case
        steps = case.range_steps()
        if case.ranges_read(steps):
            return [case.known_ranges(i) for i in steps]
        if self._steps_job is None and not self._steps_failed:
            from meshviewer.gui.jobs import run_job
            self._steps_job = run_job(lambda: case.read_ranges(steps),
                                      self._steps_read, self._steps_not_read,
                                      busy=(self.window(), "Reading time steps…"))
        return None

    def _read_field(self, field):
        """Timeline: one field at every step, in the background (the one asked last; an
        older read stops) — the range then covers them all."""
        import threading
        from meshviewer.gui.jobs import run_job
        if self._field_job is not None:
            if self._field_job[0] == field:
                return
            self._field_job[1].set()
        stop = threading.Event()
        case, n = self.scene.model.case, self.time_count()
        job = run_job(lambda: case.read_ranges(range(n), [field], stop.is_set),
                      lambda _ok, f=field: self._field_read(f),
                      lambda exc, f=field: self._field_read(f),
                      busy=(self.window(), "Reading time steps…"))
        self._field_job = (field, stop, job)

    def _field_read(self, field):
        if self._field_job is not None and self._field_job[0] == field:
            self._field_job = None
            self._changed(save=False)

    def field_varies(self, field):
        """Does `field` change over the time steps? None: not known yet (being read)."""
        if self.time_count() < 2 or field is None:
            return False
        if field.startswith(COORD):
            return False
        if self._all_ranges() is None:
            return None
        return self.scene.model.case.varies(field)

    def _steps_read(self, _ok):
        """The sampled steps read: the fields offered (dead ones out), ▸ Animation's."""
        self._steps_job = None
        fields = self.fields_of(self.scene.model)
        if fields != self.fields:
            self.fields = fields
            for _sec, ed in self.editors.values():
                ed.sync()
            self.fields_changed.emit()
        for _sec, ed in self.editors.values():
            ed.anim.sync()
        self._changed(save=False)

    def _steps_not_read(self, exc):
        self._steps_job, self._steps_failed = None, True
        print(f"time steps could not be read: {exc}")

    def length_unit_changed(self):
        """The toolbar's unit or the file's changed: a position that follows the toolbar
        (no unit picked for it here), or any position when the file's unit changed, had
        its typed Min / Max in the old one, so they go back to auto."""
        for c in self.contours:
            if c["field"] and c["field"].startswith(COORD):
                c["lo"] = c["hi"] = None
                self.editors[c["id"]][1].sync()
        self._changed()

    # ---- values ----------------------------------------------------------------------------
    def _shown(self, c=None):
        """The boundaries contour `c` counts: those shown in its tab (the scene's when its
        tab is the one shown, or it has none of its own yet)."""
        sc = self.scene
        hidden = ((c or {}).get("view") or {}).get("hidden")
        if c is None or c["id"] == self.tab or hidden is None:
            return {n for n in sc.names if sc.visible.get(n)}
        return set(sc.names) - set(hidden)

    def _values(self, field, visible_only=True, c=None):
        """All values of a field on the (visible) boundaries (contour c's)."""
        sc = self.scene
        out = []
        shown = self._shown(c)
        for n in sc.names:
            if visible_only and n not in shown:
                continue
            part = sc.model.parts[n]
            if field == SPEED:
                s, _ = speed_values(part)
                if s is not None:
                    out.append(s)
                continue
            vals, _ = field_values(part, field)
            if vals is not None:
                out.append(vals)
        return np.concatenate(out) if out else np.zeros(0)

    def _ensure_gradient(self, field):
        """|∇ field| stored on the parts (point array GRAD + field) the first time."""
        key = GRAD + field
        for part in self.scene.model.parts.values():
            if key in part.point_data or not part.GetNumberOfPolys():
                continue
            vals, where = field_values(part, field)
            if vals is None:
                continue
            if where == "cell":                       # to the nodes first
                tmp = part.cell_data_to_point_data()
                vals = np.asarray(tmp.point_data[field], dtype=float)
            part.point_data[key] = gradient_magnitude(part, vals)
        return key

    def _ensure_position(self, field):
        """X / Y / Z of every node as a point array (read again each time: the Edit tool
        moves the parts); returns its name."""
        i = AXES.index(field[len(COORD):])
        key = POS + AXES[i]
        for part in self.scene.model.parts.values():
            if part.n_points:
                part.point_data[key] = np.asarray(part.points[:, i], dtype=float)
        return key

    def _ensure_speed(self):
        """|u, v, w| stored on the parts the first time it is asked for."""
        for part in self.scene.model.parts.values():
            if SPEED not in part.point_data:
                s, where = speed_values(part)
                if s is not None and where == "point":
                    part.point_data[SPEED] = s

    def info(self, c):
        """What contour `c` shows: {array, unit, back, lo, hi, a_lo, a_hi, stops, log,
        marks, edges, title} — or {why, unit}: why nothing shows."""
        base = c["field"]
        if base is None:
            return {"why": "No solution fields in this file.", "unit": ""}
        f = base
        if not base.startswith(COORD):
            self.scene.ensure_fields([base])           # (a step read for other fields)
        if f == SPEED:
            self._ensure_speed()
        q, fu, su = self.unit_of(base)
        unit = su if q is not None and fu else ""
        position = f.startswith(COORD)
        if position:                                  # a length, as the other fields
            f = self._ensure_position(f)
        gradient = c["show"] == "gradient"
        if position and gradient:                     # |∇x| along a surface: no unit
            f = self._ensure_gradient(f)
            unit = ""
            conv = back = lambda v: v                             # noqa: E731
        elif gradient:
            f = self._ensure_gradient(f)
            k = field_scale(q, fu, su) if unit else 1.0
            conv, back = (lambda v: v * k), (lambda v: v / k)    # noqa: E731
            per = self.scene.model.units or "length"
            unit = f"{unit}/{per}" if unit else f"/{per}"
        elif unit:
            conv = lambda v: convert_field(v, q, fu, su)          # noqa: E731
            back = lambda v: convert_field(v, q, su, fu)          # noqa: E731
        else:
            conv = back = lambda v: v                             # noqa: E731
        vals = self._values(f, c=c)
        vals = conv(vals[np.isfinite(vals)])
        if not len(vals):
            return {"why": "No visible boundary has this field.", "unit": unit}
        log = c["log"]
        if log:                                       # only what a log scale can show
            vals = vals[vals > 0]
            if not len(vals):
                return {"why": "No value above zero here: a log scale can't show it.",
                        "unit": unit}
        a_lo, a_hi = float(vals.min()), float(vals.max())
        span = None if gradient or position else self._timeline(base, c)
        if span is not None and (span[2] if log else span[0]) is not None:
            a_lo, a_hi = float(conv(span[2] if log else span[0])), float(conv(span[1]))
        lo = c["lo"] if c["lo"] is not None else a_lo
        hi = c["hi"] if c["hi"] is not None else a_hi
        if log and lo <= 0:                           # (typed): the smallest above zero
            lo = a_lo
        if hi <= lo:
            hi = lo * 10 if log else lo + (abs(lo) or 1.0) * 1e-6
        b = c["bar"]
        marks = ticks(lo, hi, b["ticks"], log, b["tick_log"])
        name = field_label(base)
        if gradient:
            name = f"|∇ {name}|"
        return {"array": f, "unit": unit, "back": back, "lo": lo, "hi": hi,
                "a_lo": a_lo, "a_hi": a_hi, "a_lo_text": nice_num(a_lo),
                "a_hi_text": nice_num(a_hi), "lo_positive": lo > 0,
                "stops": COLORMAPS.get(c["cmap"], COLORMAPS[DEFAULT_MAP]), "log": log,
                "marks": marks, "edges": None if b["smooth"] else [p for p, _ in marks],
                "title": f"{name} ({unit})" if unit else name}

    # ---- drawing -------------------------------------------------------------------------------
    def _save(self):
        if self.scene is not None:
            self.scene.results_settings = self.settings()

    def _changed(self, save=True):
        """Every editor's numbers (auto ranges follow the shown boundaries), and the active
        contour drawn — or nothing, colors off."""
        sc = self.scene
        if sc is None:
            return
        if save:
            self._save()
        drawn = None
        for c in self.contours:                        # (a folded one: when it unfolds)
            sec, ed = self.editors[c["id"]]
            if c["id"] == self.active or sec.expanded:
                inf = self.info(c)
                ed.show_info(inf)
                if c["id"] == self.active:
                    drawn = inf
        self.range = None if drawn is None or "why" in drawn else (drawn["lo"], drawn["hi"])
        if self.range is None or self.tab is None or self.tab != self.active:
            sc.results.clear()
            sc.colorbar.hide()
            return
        d, c = drawn, self.current                     # the colors work in the file's numbers
        sc.results.show_field(d["array"], d["back"](d["lo"]), d["back"](d["hi"]), d["stops"],
                              d["log"], d["edges"])
        b = c["bar"]
        if b["on"] and sc.results.shown:
            sc.colorbar.show(d["stops"], d["lo"], d["hi"], d["marks"],
                             title=d["title"] if b["title"] else "", smooth=b["smooth"],
                             height=b["height"], width=b["width"], text=b["text"])
        else:
            sc.colorbar.hide()
