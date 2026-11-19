"""The Probe tool (Analyze tab): New Probe, then a card per probe (gui/panels/
probe_editor.py) — what a point, a line or an area of the model holds.

A probe's target comes from Select ▾ (Use Current Selection, or Follow Select ▾: each
pick moves it) or, for a point, from typed X / Y / Z; it is found in the mesh once
(core/probe.py `sampler`: the cells and nodes, with their weights) — again only when
the target, the model (Edit) or the cells read change. Then:

    several time steps (OpenFOAM)   its field at every step, read in the background
                                    from the arrays the case keeps (`_read_series`):
                                    a tab under the view plots it over time, with the
                                    step shown as a line (gui/window_probes.py)
    one step (.dat, .msh…)          every field at that place, in the card

Values are shown in Contours' units (`units`: the ContoursPanel, set by the window);
markers in 3D by render/probes.py (`scene.probe_marks`). Remembered per file
(`scene.probes`: id, name, show, target, field).
"""
from __future__ import annotations

import json

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QApplication, QPushButton, QVBoxLayout, QWidget

from meshviewer.core import probe as P
from meshviewer.core.fields import planar, solution_fields
from meshviewer.core.plots import COORD
from meshviewer.gui.forms import note
from meshviewer.gui.jobs import run_job
from meshviewer.gui.panels.contour_editor import field_label
from meshviewer.gui.panels.probe_editor import ProbeEditor, values_text
from meshviewer.gui.sheets import ask_save, ask_text, save_folder
from meshviewer.gui.widgets import CollapsibleSection, IconToggle
from meshviewer.render.elements import VOLUME


class ProbesPanel(QWidget):
    added = Signal(int)
    removed = Signal(int)
    renamed = Signal(int)
    show_probe = Signal(int)              # open its plot's tab
    changed = Signal(int)                 # its values over time are new: its tab redraws
    select_kind = Signal(str)             # Select ▾ to this kind (window.set_select_kind)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = None
        self.units = None                 # the ContoursPanel (units, fields): window.py
        self.editors = {}                 # id -> (CollapsibleSection, editor)
        self.samplers = {}                # id -> (key, core.probe.Sampler)
        self.series = {}                  # id -> {"field", "mean", "min", "max"}
        self.following = None            # the probe Follow Select ▾ moves
        self.picking = None               # (id, Select ▾ kind before): Select Vertex Point
        self._jobs = {}                   # id -> (token, job): its latest read
        self._cells_job = None            # reading the cells (for every probe needing them)
        self._locators = {}               # VTK locators, per dataset (for the file)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.new = QPushButton("New Probe")
        self.new.setObjectName("ApplyButton")
        self.new.setCursor(Qt.PointingHandCursor)
        self.new.setToolTip("New Probe")
        self.new.clicked.connect(lambda: self.add())
        lay.addWidget(self.new)
        self.hint = note("Pick a point, an edge or a face in the 3D view (Select ▾), then "
                         "New Probe — or type a point in its card.")
        lay.addWidget(self.hint)
        self.list = QVBoxLayout()
        self.list.setSpacing(6)
        lay.addLayout(self.list)

    # ---- binding ---------------------------------------------------------------------------
    def bind(self, scene):
        for sec, _ed in list(self.editors.values()):
            self._drop(sec)
        for ident in list(self._jobs):
            self._stop(ident)
        if self.scene is not None and self._time_changed in self.scene.time_listeners:
            self.scene.time_listeners.remove(self._time_changed)
        self.editors, self.samplers, self.series, self._jobs = {}, {}, {}, {}
        self._cells_job = None
        self.following, self.picking, self._locators = None, None, {}
        self.scene = scene
        scene.time_listeners.append(self._time_changed)
        scene.field_users.append(lambda: [p.get("field") for p in scene.probes
                                          if p.get("field")] if self.time_count() > 1 else [])
        scene.probes = [p for p in (getattr(scene, "probes", None) or [])
                        if isinstance(p, dict) and "id" in p]
        for p in scene.probes:
            p.setdefault("name", f"Probe {p['id']}")
            p.setdefault("show", True)
            self._editor(p, expanded=False)
        for p in scene.probes:
            self._update(p["id"])
        self._markers()

    def probe(self, ident):
        return next((p for p in self.scene.probes if p["id"] == ident), None) \
            if self.scene is not None else None

    def time_count(self):
        return self.scene.time_count if self.scene is not None else 0

    def fields(self):
        """The fields Contours offers (none of the positions): 2D and dead ones out."""
        u = self.units
        if u is not None and u.scene is self.scene:
            fields = u.fields
        else:
            fields = planar(solution_fields(self.scene.model.parts), self.scene.model)
        return [f for f in fields if not f.startswith(COORD)]

    # ---- add / rename / remove -------------------------------------------------------------
    def add(self, target=None, name=None):
        """A new probe at `target` (None: what Select ▾ picked, if anything)."""
        if self.scene is None:
            return None
        ident = max((p["id"] for p in self.scene.probes), default=0) + 1
        fields = self.fields()
        drawn = self.units.current["field"] if self.units is not None and \
            self.units.current is not None else None
        p = {"id": ident, "name": name or self._next_name(), "show": True,
             "target": target if target is not None else self.target_from_selection(),
             "field": drawn if drawn in fields else (fields[0] if fields else None)}
        self.scene.probes.append(p)
        self._editor(p, expanded=True)
        self._update(ident)
        self.added.emit(ident)
        return ident

    def _next_name(self):
        used = {p["name"] for p in self.scene.probes}
        k = 1
        while f"Probe {k}" in used:
            k += 1
        return f"Probe {k}"

    def rename(self, ident, name=None):
        p = self.probe(ident)
        if p is None:
            return
        if name is None:
            ask_text(self.window(), "Rename Probe", "Name", p["name"],
                     lambda text: self.rename(ident, text))
            return
        if name.strip():
            p["name"] = name.strip()
            self.editors[ident][0].set_title(p["name"])
            self._markers()
            self.renamed.emit(ident)

    def remove(self, ident):
        p = self.probe(ident)
        if p is None:
            return
        self.scene.probes.remove(p)
        self._drop(self.editors.pop(ident)[0])
        self._stop(ident)
        for d in (self.samplers, self.series, self._jobs):
            d.pop(ident, None)
        if self.following == ident:
            self.following = None
        self._markers()
        self.removed.emit(ident)

    def _drop(self, sec):
        self.list.removeWidget(sec)
        sec.hide()
        sec.setParent(None)
        sec.deleteLater()

    def _editor(self, p, expanded):
        ed = ProbeEditor(self, p)
        ed.changed.connect(lambda i=p["id"]: self._update(i))
        eye = IconToggle(("eye", "eye_off"), "Show its marker in the 3D view",
                         checked=p.get("show", True), eye=True)
        eye.toggled.connect(lambda on, pp=p: (pp.__setitem__("show", bool(on)),
                                              self._markers()))
        sec = CollapsibleSection(p["name"], ed, f"probe{p['id']}", trailing=eye,
                                 remember=False, start_open=expanded, sub=True)
        sec.toggled.connect(lambda on, i=p["id"]: on and self._unfolded(i))
        self.list.addWidget(sec)
        self.editors[p["id"]] = (sec, ed)

    def _unfolded(self, ident):
        """Its card opened: its numbers (not kept up while folded), its tab."""
        self._readout(ident)
        if self.time_count() > 1:
            self.show_probe.emit(ident)

    def expand_only(self, ident):
        for i, (sec, _ed) in self.editors.items():
            if sec.expanded != (i == ident):
                sec.blockSignals(True)
                sec.set_expanded(i == ident)
                sec.blockSignals(False)
        if ident in self.editors:
            self._readout(ident)                       # (its numbers: not kept while folded)
        return self.editors[ident][0] if ident in self.editors else None

    # ---- Select ▾ ----------------------------------------------------------------------------
    def set_following(self, ident, on):
        self.following = ident if on else (None if self.following == ident else
                                           self.following)
        for i, (_sec, ed) in self.editors.items():
            if i != ident:
                ed.sync()                              # (one probe follows at a time)

    def pick_vertex(self, ident):
        """Select Vertex Point: the next vertex clicked in the 3D view becomes the probe's
        point (Select ▾ on Mesh Node until then, as it was after); again: cancelled."""
        if self.picking is not None:
            was = self.picking
            self._end_pick()
            if was[0] == ident:
                return
        sc = self.scene
        if sc is None or "mesh_node" not in sc.elements.kinds():
            return
        self.picking = (ident, sc.elements.kind)
        self.select_kind.emit("mesh_node")             # (a new kind: nothing picked)
        sc.elements.clear()
        self._sync_all()

    def vertex_picked(self):
        """Select ▾ picked (sidebar): True when it was for Select Vertex Point — the probe
        moved there, Select ▾ back as it was, Measure Selected not opened."""
        if self.picking is None:
            return False
        el = self.scene.elements
        if el.kind != "mesh_node":                    # Select ▾ changed by hand: cancelled
            self._end_pick()
            return False
        items = [(n, i) for n, i in el.items if n in self.scene.model.parts]
        if not items:
            return True
        ident = self.picking[0]
        p = self.probe(ident)
        self._end_pick()
        if p is not None:
            n, i = items[-1]
            p["target"] = {"kind": "point", "how": "nodes", "nodes": [[n, int(i)]]}
            self._update(ident)
        return True

    def _end_pick(self):
        ident, kind = self.picking
        self.picking = None
        self.scene.elements.clear(render=False)
        self.select_kind.emit(kind)
        self._sync_all()

    def _sync_all(self):
        for _sec, ed in self.editors.values():
            ed.sync()

    def selection_changed(self):
        """Something picked: the probe following Select ▾ moves there."""
        p = self.probe(self.following) if self.following is not None else None
        target = self.target_from_selection() if p is not None else None
        if target is not None:
            p["target"] = target
            self._update(p["id"])

    def target_from_selection(self):
        """The target of what Select ▾ picked: a node a point (two or more: a line
        through the cells between them), a volume cell a point, an edge a line, a face
        or a part an area — or None."""
        sc = self.scene
        el, parts = sc.elements, sc.model.parts
        kind, items = el.kind, [it for it in el.items]
        if kind == "part":
            names = [n for n in sc.selected_parts if n in parts]
            return {"kind": "area", "how": "parts", "parts": names} if names else None
        if not items:
            return None
        if kind in ("mesh_node", "feature_node"):
            nodes = [[n, int(i)] for n, i in items if n in parts]
            if len(nodes) == 1:
                return {"kind": "point", "how": "nodes", "nodes": nodes}
            pts = [[float(x) for x in parts[n].points[i]] for n, i in nodes]
            return {"kind": "line", "how": "through", "points": pts} if len(pts) > 1 else None
        if kind == "volume_cell":
            return {"kind": "point", "how": "cells",
                    "cells": [int(c) for n, c in items if n == VOLUME]}
        if kind in ("mesh_edge", "feature_edge"):
            edges = []
            for n, key in items:
                segs = np.asarray([key]).reshape(-1, 2) if kind == "mesh_edge" else \
                    el.features(n).curve_segments(key)
                edges += [[n, int(a), int(b)] for a, b in segs]
            return {"kind": "line", "how": "edges", "edges": edges} if edges else None
        if kind in ("mesh_cell", "feature_face"):
            by = {}
            for n, key in items:
                ids = [int(key)] if kind == "mesh_cell" else \
                    [int(c) for c in el.features(n).face_cells(key)]
                by.setdefault(n, []).extend(ids)
            return {"kind": "area", "how": "faces", "faces": [[n, ids] for n, ids in by.items()]}
        return None

    # ---- finding the cells, reading the values ---------------------------------------------
    def _needs_cells(self, p):
        t = p.get("target") or {}
        return t.get("how") in ("xyz", "cells", "through") and self.scene.model.dim == 3 \
            and self.scene.model.volume is not None

    def _volume(self):
        sec = self.scene.section
        return sec._volume_orig if sec._volume else None

    def _sampler(self, p):
        """The probe's Sampler, found again only when its target or the model changed."""
        m = self.scene.model
        vol = self._volume()
        key = (json.dumps(p.get("target"), sort_keys=True), id(vol),
               m.transform.tobytes(), m.offset.tobytes(),
               tuple((n, id(part)) for n, part in m.parts.items()))
        got = self.samplers.get(p["id"])
        if got is None or got[0] != key:
            s = P.sampler(p["target"], m.parts, vol, (m.transform, m.offset), self._locators) \
                if p.get("target") else P.Sampler(why="")
            got = self.samplers[p["id"]] = (key, s)
        return got[1]

    def _update(self, ident):
        """Its target or field changed: find it (the cells read first, in the background,
        when it needs them), its card and marker, its values."""
        p = self.probe(ident)
        if p is None:
            return
        sec = self.scene.section
        if self._needs_cells(p) and sec._volume is None:   # the cells first (once, for all)
            if self._cells_job is None:
                self._cells_job = run_job(sec.volume_grid, self._cells_read, self._cells_read,
                                          busy=(self.window(), "Reading volume cells…"))
            self.editors[ident][1].sync()
            return
        self._sampler(p)
        self.editors[ident][1].sync()
        self._markers()
        self._readout(ident)
        if self.time_count() > 1:
            self._read_series(ident)

    def _stop(self, ident):
        """Its read over the time steps, if one runs, stops at the next step."""
        job = self._jobs.get(ident)
        if job is not None and len(job) > 2:
            job[2].set()

    def _finished(self, ident, token):
        """A read is done: True when it is the probe's latest (an older one: dropped)."""
        if self._jobs.get(ident, (None,))[0] is not token:
            return False
        self._jobs.pop(ident)
        return True

    def _cells_read(self, _result=None):
        """The cells are read: the probes that waited for them are found now."""
        self._cells_job = None
        if self.scene is None:
            return
        for p in list(self.scene.probes):
            if self._needs_cells(p):
                self._update(p["id"])

    @property
    def busy(self):
        """(Tests) reading something."""
        return bool(self._jobs) or self._cells_job is not None

    def _live(self):
        """data(source) for the step shown: the parts' and the cells' arrays."""
        parts, vol = self.scene.model.parts, self._volume()
        empty = ({}, {})

        def data(src):
            ds = vol if src is P.VOLUME else parts.get(src)
            return (ds.point_data, ds.cell_data) if ds is not None else empty
        return data

    def rows(self, ident):
        """[(label, (mean, min, max) or None, unit)] the card shows: the field at the step
        shown (several steps), every field (one step); in Contours' units."""
        p = self.probe(ident)
        s = self._sampler(p)
        if not s.ok:
            return []
        if self.time_count() > 1:
            fields = [p["field"]] if p.get("field") else []
            self.scene.ensure_fields(fields)            # (a step read for other fields)
        else:
            fields = self.fields()
        data = self._live()
        out = []
        for f in fields:
            v = s.value(data, f)
            if v is not None and self.units is not None:
                v = tuple(float(self.units.shown_values(f, x)) for x in v)
            out.append((field_label(f) if self.time_count() < 2 else "At this step", v,
                        self.units.unit_label(f) if self.units is not None else ""))
        return out

    def _readout(self, ident):
        p = self.probe(ident)
        s = self._sampler(p)
        why = s.why if not s.ok else ""
        self.editors[ident][1].show_values(self.rows(ident) if s.ok else [], why)

    def _read_series(self, ident):
        """The field at every step, in the background (from the arrays the case keeps)."""
        p = self.probe(ident)
        s = self._sampler(p)
        field = p.get("field")
        if not s.ok or field is None:
            self.series.pop(ident, None)
            self.changed.emit(ident)
            return
        import threading
        case, n = self.scene.model.case, self.time_count()
        need_parts = any(src is not P.VOLUME for src in s.sources())
        need_cells = P.VOLUME in s.sources()
        stop = threading.Event()                       # a newer read stops this one

        def step_data(i):                              # only its field, step by step
            arr = case.step_arrays(i, [field]) if need_parts else {}
            cells = case.volume_arrays(i, [field]) if need_cells else ({}, {})
            return lambda src: cells if src is P.VOLUME else arr.get(src, ({}, {}))

        def work():
            return P.series(s, step_data, field, n, stop=stop.is_set)
        old = self._jobs.get(ident)
        if old is not None and len(old) > 2:
            old[2].set()
        token = object()
        self._jobs[ident] = (token, run_job(
            work, lambda out, i=ident, f=field, k=token: self._series_read(i, f, out, k),
            lambda exc, i=ident, k=token: self._series_failed(i, exc, k),
            busy=(self.window(), "Probing the time steps…")), stop)

    def _series_read(self, ident, field, out, token):
        p = self.probe(ident)
        if not self._finished(ident, token) or p is None or p.get("field") != field \
                or out is None:
            return
        self.series[ident] = {"field": field, "mean": out[0], "min": out[1], "max": out[2]}
        self.changed.emit(ident)

    def _series_failed(self, ident, exc, token):
        if self._finished(ident, token) and ident in self.editors:
            self.editors[ident][1].show_values([], f"The time steps could not be read: {exc}")

    def _time_changed(self):
        """Another step: the open cards' numbers (a folded one: when it opens)."""
        for ident, (sec, _ed) in self.editors.items():
            if sec.expanded:
                self._readout(ident)

    def refresh(self):
        """Contours' units changed: the numbers again."""
        for ident, (_sec, ed) in self.editors.items():
            ed.sync()
            self._readout(ident)
            self.changed.emit(ident)

    # ---- the card's words, the marker -------------------------------------------------------
    def describe(self, p):
        t = p.get("target") or {}
        kind, how = t.get("kind"), t.get("how")
        if not t:
            return "Nowhere yet: pick in the 3D view (Select ▾), then Use Current Selection."
        if how == "xyz":
            s = self.samplers.get(p["id"], (None, None))[1]
            where = ""
            if s is not None and s.ok:
                lk = s.lookups[0]
                where = (f" · volume cell {int(lk.cells[0]):,}" if lk.source is P.VOLUME
                         else f" · on {lk.source}") if len(lk.cells) else ""
            return "Point" + where
        if how == "nodes":
            n = t["nodes"]
            return f"Point · node {n[0][1]:,} of {n[0][0]}" if len(n) == 1 else \
                f"Point · {len(n)} nodes"
        if how == "cells":
            c = t["cells"]
            return f"Point · volume cell {c[0]:,}" if len(c) == 1 else \
                f"Point · {len(c)} volume cells"
        if how == "edges":
            parts = sorted({e[0] for e in t["edges"]})
            return f"Line · {len(t['edges']):,} edges of {', '.join(parts)}"
        if how == "through":
            return f"Line through the cells · {len(t['points'])} points"
        if how == "faces":
            n = sum(len(ids) for _p, ids in t["faces"])
            return f"Area · {n:,} faces of {', '.join(sorted(f[0] for f in t['faces']))}"
        if how == "parts":
            return "Area · " + ", ".join(t["parts"])
        return kind or ""

    def marker_point(self, ident):
        got = self.samplers.get(ident)
        at = got[1].marker.get("label_at") if got is not None else None
        return None if at is None else [float(x) for x in at]

    def _markers(self):
        if self.scene is None:
            return
        marks = []
        for p in self.scene.probes:
            got = self.samplers.get(p["id"])
            if p.get("show", True) and got is not None and got[1].marker:
                marks.append((p["name"], got[1].marker))
        self.scene.probe_marks.show(marks)

    # ---- copy / export -------------------------------------------------------------------
    def copy_values(self, ident):
        QApplication.clipboard().setText(values_text(self.rows(ident)))

    def export_csv(self, ident):
        p = self.probe(ident)
        if p is None:
            return
        stem = getattr(self.scene, "file_stem", None) or "probe"
        folder = save_folder(getattr(self.window(), "path", None))
        ask_save(self.window(), "Export CSV", folder / f"{stem} {p['name']}.csv",
                 "CSV (*.csv)", lambda fn, i=ident: self.write_csv(i, fn))

    def write_csv(self, ident, fn):
        """Several steps: time and the field (with min / max for a line or an area); one
        step: each field's value."""
        p = self.probe(ident)
        m = self.scene.model
        if self.time_count() > 1 and ident in self.series:
            r, f = self.series[ident], p["field"]
            conv = (lambda v: self.units.shown_values(f, v)) if self.units else (lambda v: v)
            unit = self.units.unit_label(f) if self.units else ""
            name = field_label(f) + (f" ({unit})" if unit else "")
            spread = (p.get("target") or {}).get("kind") in ("line", "area")
            head = ["time", name] + ([f"min {name}", f"max {name}"] if spread else [])
            rows = [(m.time_labels[i], float(conv(r["mean"][i]))) +
                    ((float(conv(r["min"][i])), float(conv(r["max"][i]))) if spread else ())
                    for i in range(len(m.times))]
        else:
            head = ["field", "value", "min", "max", "unit"]
            rows = [(label, *(v if v is not None else (np.nan,) * 3), unit)
                    for label, v, unit in self.rows(ident)]
        with open(fn, "w", encoding="utf-8") as fh:
            fh.write(P.csv_text(head, rows))
        return fn
