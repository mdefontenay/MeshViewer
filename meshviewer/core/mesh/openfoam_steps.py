"""The time steps of an OpenFOAM case (core/mesh/openfoam.py `FoamCase`): what each step
holds, read field by field and kept. No Qt.

    step_arrays(step, names)    {part: ({point arrays}, {cell arrays})} of the fields
                                `names` need (array names: "p", "Ux", SPEED…; None: all)
    volume_arrays(step, names)  the same on the cells (Section, probes)
    prefetch(step, names)       the steps after `step`, read ahead in the background
    read_ranges(steps, names)   (a job) those steps read, so their ranges are known
    known_ranges(step)          {part: {array: (min, max, min above zero, fingerprint)}}
                                of what is read of that step so far
    range_steps()               the steps that say which fields vary or are flat: every
                                one on a short case, SAMPLED spread evenly on a long one
    varies(field)               does it change from step to step (on those)?

Only the file fields an array comes from are read: U for Ux, Uy, Uz and Speed. A long
case (601 steps of an LES) then plays reading one field a step, not all of them, and its
field list is settled from a few steps. Everything read stays in the cache (float32).
"""
from __future__ import annotations

import numpy as np

from meshviewer.core.field_kinds import SPEED

SAMPLED = 24                       # steps read to tell the fields apart (a long case)
AXES = "xyz"
SYMM = ("xx", "xy", "xz", "yy", "yz", "zz")
TENSOR9 = ("xx", "xy", "xz", "yx", "yy", "yz", "zx", "zy", "zz")
VELOCITY = "U"


def derived(field, kind):
    """The arrays a file field becomes on the parts (U: Ux, Uy, Uz; R: Rxx…)."""
    if kind in ("scalar", "surface"):
        return {field}
    if kind == "vector":
        return {f"{field}{c}" for c in AXES} | {f"mag({field})"}
    return {f"{field}{c}" for c in (SYMM if kind == "symmTensor" else TENSOR9)}


class Steps:
    """Mixed into FoamCase: needs labels, times, cache, fields_at's folder, parts(),
    cells() and the polyhedra split (_carry)."""

    def _steps_init(self):
        self._ranges = {}                  # step -> {part: {array: range}} (what is read)
        self._sources_read = {}            # step -> {file fields read}
        self._fields_at = {}               # step -> fields_in(its folder)

    def fields_at(self, step):
        """fields_in(the step's folder), read once."""
        from meshviewer.core.mesh.openfoam_files import fields_in
        if step not in self._fields_at:
            src = self.case.meshes[0][2]
            self._fields_at[step] = fields_in(src / self.labels[step]) if src else {}
        return self._fields_at[step]

    def sources_for(self, step, names=None):
        """The file fields of a step that the arrays `names` come from (None: all)."""
        fields = self.fields_at(step)
        if names is None:
            return list(fields)
        names = set(names)
        return [f for f, (kind, _u) in fields.items()
                if derived(f, kind) & names or f in names
                or (SPEED in names and f == VELOCITY)]

    # ---- the parts ---------------------------------------------------------------------------
    def step_arrays(self, step, names=None):
        """{part: ({point arrays}, {cell arrays})} of a step's fields that `names` need:
        each from the cache, the others read (only those) and kept."""
        fields = self.fields_at(step)
        sources = self.sources_for(step, names)
        have = {f: self.cache.get(("field", step, f)) for f in sources}
        missing = [f for f, v in have.items() if v is None]
        if missing:
            parts = self.part_arrays(step, missing)
            for f in missing:
                keep = derived(f, fields[f][0])
                have[f] = self.cache.put(("field", step, f), {
                    n: ({k: a for k, a in point.items() if k in keep},
                        {k: a for k, a in cell.items() if k in keep})
                    for n, (point, cell) in parts.items()})
                self._note_ranges(step, f, have[f])
        out = {}
        for entry in have.values():
            for n, (point, cell) in entry.items():
                op, oc = out.setdefault(n, ({}, {}))
                op.update(point)
                oc.update(cell)
        return out

    def _note_ranges(self, step, field, entry):
        """A field read at a step: its arrays' ranges (Speed with U) kept for good."""
        per = self._ranges.setdefault(step, {})
        for n, (point, cell) in entry.items():
            per.setdefault(n, {}).update(_ranges_of(point, cell, field == VELOCITY))
        self._sources_read.setdefault(step, set()).add(field)

    # ---- the cells ---------------------------------------------------------------------------
    def volume_arrays(self, step, names=None):
        """({point arrays}, {cell arrays}) on the cells at a step, of the fields `names`
        need, as on the grid `volume()` gave (polyhedra split the same way); kept."""
        fields = self.fields_at(step)
        sources = [f for f in self.sources_for(step, names) if fields[f][0] != "surface"]
        have = {f: self.cache.get(("cells", step, f)) for f in sources}
        missing = [f for f, v in have.items() if v is None]
        if missing:
            grid = self.cells(step, only=missing)
            if grid is not None:
                if self._carry is None:
                    from meshviewer.core.mesh.volume import split_polyhedra
                    _g, _n, self._carry = split_polyhedra(grid)
                point, cell = self._carry(grid)
                for f in missing:
                    keep = derived(f, fields[f][0])
                    have[f] = self.cache.put(("cells", step, f),
                                             ({k: a for k, a in point.items() if k in keep},
                                              {k: a for k, a in cell.items() if k in keep}))
        point, cell = {}, {}
        for entry in have.values():
            if entry is not None:
                point.update(entry[0])
                cell.update(entry[1])
        return point, cell

    # ---- reading ahead -------------------------------------------------------------------------
    def has_step(self, step, names=None, cells=False):
        """Is all of it in the cache (the cells' too, with cells)?"""
        sources = self.sources_for(step, names)
        return all(("field", step, f) in self.cache for f in sources) and \
            (not cells or all(("cells", step, f) in self.cache for f in sources
                              if self.fields_at(step)[f][0] != "surface"))

    def prefetch(self, step, names=None):
        """Read the steps after `step` ahead (then from the first), in the background —
        what `names` need, and the cells' when they are read; nothing left: no thread."""
        n = len(self.times)
        cells = self._carry is not None
        order = [s for s in ((step + k) % n for k in range(1, n))
                 if not self.has_step(s, names, cells)]
        if not order:
            return

        def load(s):
            self.step_arrays(s, names)
            if cells:
                self.volume_arrays(s, names)
        self.cache.prefetch(order, load)

    # ---- ranges ---------------------------------------------------------------------------------
    def range_steps(self):
        """The steps that tell the fields apart: all of a short case, SAMPLED spread evenly
        (the first and the last among them) on a long one."""
        n = len(self.times)
        if n <= SAMPLED:
            return list(range(n))
        return sorted({int(round(k)) for k in np.linspace(0, n - 1, SAMPLED)})

    def read_ranges(self, steps, names=None, stop=None):
        """Read those steps (what `names` need) so their ranges are known; stop() -> True
        ends it early (a newer job). Returns whether it went through."""
        for s in steps:
            if stop is not None and stop():
                return False
            self.step_arrays(s, names)
        return True

    def ranges_read(self, steps, names=None):
        """Are the ranges of those steps known (for what `names` need)?"""
        return all(set(self.sources_for(s, names)) <= self._sources_read.get(s, set())
                   for s in steps)

    def known_ranges(self, step):
        """What is known of a step's ranges ({part: {array: range}}), or None."""
        return self._ranges.get(step)

    def varies(self, field):
        """Does a field change from step to step (on `range_steps`)? None: not read yet;
        False: the same everywhere (or in one step only)."""
        steps = self.range_steps()
        if not self.ranges_read(steps, [field]):
            return None
        prints = {tuple(sorted((n, per[field][3]) for n, per in self._ranges[s].items()
                               if field in per)) for s in steps if s in self._ranges}
        prints.discard(())
        return len(prints) > 1


def _ranges_of(point, cell, speed=False):
    """{array: (min, max, min above zero, fingerprint)}: of the node values when there are
    (as Contours draws them), else the cells'; speed: SPEED from Ux, Uy, Uz too. The
    fingerprint tells two steps' values apart (`varies`)."""
    import hashlib
    out = {}
    arrays = dict(cell)
    arrays.update(point)
    if speed:
        names = ("Ux", "Uy", "Uz")
        data = point if all(k in point for k in names) else cell
        if all(k in data for k in names):
            arrays[SPEED] = np.sqrt(sum(np.asarray(data[k], dtype=float) ** 2 for k in names))
    for k, a in arrays.items():
        a = np.asarray(a, dtype=float)
        if a.ndim != 1 or not len(a) or (k.startswith("__") and k != SPEED):
            continue
        a = a[np.isfinite(a)]
        if len(a):
            pos = a[a > 0]
            mark = hashlib.blake2b(np.ascontiguousarray(a).tobytes(), digest_size=8).hexdigest()
            out[k] = (float(a.min()), float(a.max()), float(pos.min()) if len(pos) else None,
                      mark)
    return out
