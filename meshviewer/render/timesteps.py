"""Time steps (OpenFOAM cases with several): another step's fields on the parts and the
cells already drawn — the geometry, camera, visibility and selection stay.

    scene.set_time_index(i)     step i's fields on the parts (and the read cells); then
                                scene.time_listeners are called (Contours, Plots, …)
    scene.ensure_fields(names)  those fields on the step shown, read if missing (a
                                contour's new field, Measure Selected's list…)
    scene.field_users           callables -> the fields each tool shows (None: all)
    scene.time_count            how many steps (0 or 1: nothing to animate)

A step change reads only the fields the tools show (`wanted_fields`: the contours',
plots', probes' fields; every field while Measure Selected lists a pick) — one field a
step on a long LES rather than a dozen. Each is read once and kept by the case
(core/mesh/openfoam_steps.py), and the steps after are read ahead.
"""
from __future__ import annotations

from meshviewer.core import transform as xf
from meshviewer.core.fields import replace_fields


class TimeSteps:
    @property
    def time_count(self):
        m = self.model
        return len(m.times) if m.case is not None else 0

    def wanted_fields(self):
        """The fields the tools show (array names), or None: all of them."""
        names = set()
        for cb in list(getattr(self, "field_users", [])):
            got = cb()
            if got is None:
                return None
            names |= {f for f in got if f}
        return sorted(names)

    def set_time_index(self, i):
        """Show time step i (clamped). Returns False when nothing changed."""
        m = self.model
        if self.time_count < 2:
            return False
        i = max(0, min(int(i), len(m.times) - 1))
        if i == m.time_index:
            return False
        names = self.wanted_fields()
        self._put_fields(i, names, drop=True)
        m.time_index = m.case.time_index = i             # (cells read later: this step)
        for cb in list(self.time_listeners):              # Contours draws again (the cut
            cb()                                           # cells too), Plots, …
        m.case.prefetch(i, names)                          # the next steps, in the background
        return True

    def ensure_fields(self, names=None):
        """Those fields (None: all) on the step shown — read when it lacks them (no step
        changed: no listeners called). True when something was added."""
        m = self.model
        if self.time_count < 2 or m.time_index is None:
            return False
        have = set()
        for part in m.parts.values():
            have |= set(part.point_data.keys()) | set(part.cell_data.keys())
        sources = m.case.sources_for(m.time_index, names)
        fields = m.case.fields_at(m.time_index)
        from meshviewer.core.mesh.openfoam_steps import derived
        if all(derived(f, fields[f][0]) & have for f in sources):
            return False
        self._put_fields(m.time_index, names, drop=False)
        return True

    def _put_fields(self, i, names, drop):
        m = self.model
        arrays = m.case.step_arrays(i, names)
        for name, part in m.parts.items():
            replace_fields(part, *arrays.get(name, ({}, {})), drop=drop)
        sec = self.section
        if sec._volume:                                 # the cells, once they are read
            replace_fields(sec._volume_orig, *m.case.volume_arrays(i, names), drop=drop)
            if sec._volume is not sec._volume_orig:     # moved by Edit: a moved copy again
                sec._volume = xf.grid_from(sec._volume_orig, m.transform, m.offset)
                sec._vol_cutter = None
