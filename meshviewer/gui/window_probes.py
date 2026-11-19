"""Probes in the window (cases with several time steps): a tab per probe under the view,
its field over time (gui/pages/probe.py), with the step shown as a line.

The probe's tab counts as animated (gui/window_animation.py): the playback bar shows
under it, playing or scrubbing moves the line; a click or a drag on the plot goes to that
step (`_probe_time_picked`) — the contours' tabs follow, as from the bar. One step (.dat,
.msh): no tab, the values are in the probe's card.
"""
from __future__ import annotations

import numpy as np

from meshviewer.gui.pages.probe import ProbePage
from meshviewer.gui.panels.contour_editor import field_label


class Probes:
    def _build_probes(self):
        self.probe_page = ProbePage()                 # Probe: the tab of a probe
        self.stack.addWidget(self.probe_page)
        self._probe_acts = {}                         # probe id -> its tab
        pp = self.sidebar.probes_panel
        pp.added.connect(self._probe_added)
        pp.removed.connect(self._probe_removed)
        pp.renamed.connect(lambda _i: self._rebuild_view_bar())
        pp.show_probe.connect(lambda i: self._show_page(f"probe:{i}"))
        pp.changed.connect(self._probe_changed)
        pp.select_kind.connect(self.set_select_kind)
        self.probe_page.plot.time_picked.connect(self._probe_time_picked)

    def _bind_probes(self):
        self.scene.time_listeners.append(self._probe_playhead)

    def _probe_tabs(self):
        """The probes with a tab: all of them on a case with several time steps."""
        sc = self.scene
        return list(getattr(sc, "probes", None) or []) if sc is not None and \
            sc.time_count > 1 else []

    def _probe_added(self, ident):
        self._rebuild_view_bar()
        if ident in self._probe_acts:
            self._show_page(f"probe:{ident}")

    def _probe_removed(self, ident):
        was = self._page == f"probe:{ident}"
        self._rebuild_view_bar()
        if was:
            self._show_page("model")

    def _probe_changed(self, ident):
        if self._page == f"probe:{ident}":
            self._refresh_probe(ident)

    def _show_probe(self, ident):
        """Its tab chosen: the plot of its field over time."""
        self._probe_acts[ident].setChecked(True)
        self._refresh_probe(ident)
        self.stack.setCurrentWidget(self.probe_page)

    def _refresh_probe(self, ident):
        pp, rp = self.sidebar.probes_panel, self.sidebar.contours_panel
        p = pp.probe(ident)
        if p is None:
            return
        f = p.get("field")
        unit = rp.unit_label(f) if f else ""
        y_title = (field_label(f) if f else "") + (f" ({unit})" if unit else "")
        m = self.scene.model
        self.probe_page.show_probe(p, m.times, pp.series.get(ident), pp.describe(p),
                                   y_title, lambda v, f=f: rp.shown_values(f, v))
        self._probe_playhead()

    def _probe_playhead(self):
        m = self.scene.model if self.scene is not None else None
        if m is not None and m.time_index is not None and m.times:
            self.probe_page.set_playhead(m.times[m.time_index])

    def _probe_time_picked(self, t):
        """A click / drag on a probe's plot: the step nearest that time."""
        m = self.scene.model if self.scene is not None else None
        if m is None or len(m.times) < 2:
            return
        self.scene.set_time_index(int(np.argmin(np.abs(np.asarray(m.times) - t))))

    def _shown_page(self):
        """The plot page shown (a plot's or a probe's tab), or None (a 3D page)."""
        if self._page.startswith("plot:"):
            return self.plot_page
        if self._page.startswith("probe:"):
            return self.probe_page
        return None
