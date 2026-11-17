"""The window's pages: the 3D model, the Inflation Layers page (CAD files), a tab per
contour (the 3D view colored by it) and a page per plot, with the tab bar under the view
that switches between them. Opening a contour's or a plot's tab opens its fold-out in
the right sidebar and folds the others (`Sidebar.reveal`); View ▸ Fit (⌘0) fits the
plot shown, or the 3D view (`fit_view`).

The 3D View tab shows the model alone; a contour is drawn only in its own tab. Each of
those tabs has its own view (`_view_state`): the camera and the Show ▾ toggles. Leaving
one keeps its view, opening one puts its back (`_switch_view`); a contour's tab opened
the first time starts as the view it was opened from. The 3D View's axes, grid and axis
indicator are the app's (Settings, every window); a contour's tab has its own. The file
remembers the 3D View's view as before, and each contour's in its settings ("view").

Every tab — the 3D View, each contour, each plot — also shows and hides parts on its own
(`_switch_parts`): hiding a boundary in a plot's tab leaves it in the 3D View. The parts
list shows the tab's; its order and filter are the same in all. Kept as a list of hidden
parts: the 3D View's `_model_hidden` (the file's "hidden"), a contour's `view["hidden"]`,
a plot's `hidden` (it is cut with its own, `PlotsPanel._visible`)."""
from __future__ import annotations

import shiboken6
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QFrame, QScrollArea, QSizePolicy

from meshviewer.core.plots import KINDS
from meshviewer.gui.widgets import Capsule, Menu


BAR_ROOM = 6           # under the pill, for the scrollbar; the bar's margins even it out


class TabScroll(QScrollArea):
    """The tabs under the view (3D model · Inflation layers · plots), scrolling sideways
    when they don't fit: thin bar, the wheel / trackpad scrolls them, the chosen tab is
    kept in view."""

    def __init__(self):
        super().__init__()
        self.setObjectName("TabScroll")
        self.setFrameShape(QFrame.NoFrame)
        self.setWidgetResizable(False)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set_tabs(self, capsule):
        old = self.takeWidget()
        if old is not None:
            old.hide()
            old.deleteLater()
        self.setWidget(capsule)
        # setWidget fills the pill's whole rect (a square behind its rounded corners)
        capsule.setAutoFillBackground(False)
        # sized after the stylesheet's font is applied: sized before, the pill came out
        # wider than its buttons (more room after the last tab than before the first)
        capsule.ensurePolished()
        for b in getattr(capsule, "buttons", []):
            b.ensurePolished()
        capsule.adjustSize()
        # + the thin scrollbar's room (6 px): as much as the bar has above the pill
        self.setFixedHeight(capsule.sizeHint().height() + BAR_ROOM)
        QTimer.singleShot(0, lambda: capsule.adjustSize() if shiboken6.isValid(capsule) else None)

    def show_current(self):
        cap = self.widget()
        if cap is None:
            return
        for b in getattr(cap, "buttons", []):
            if b.defaultAction() is not None and b.defaultAction().isChecked():
                self.ensureWidgetVisible(b, 24, 0)

    def wheelEvent(self, e):
        d = e.angleDelta()
        step = d.x() or d.y()                          # up / down scrolls sideways too
        bar = self.horizontalScrollBar()
        bar.setValue(bar.value() - step)
        e.accept()


VIEW_KEYS = ("mesh_edges", "feature_edges", "faces", "bbox", "origin", "axes", "grid",
             "axis_indicator")                     # Show ▾: each 3D tab its own


class Pages:
    def _cfd_mode(self, on, open_page=True):
        """Show the bar with the 3D model / Inflation layers pill (and the page)."""
        self._cfd_on = bool(on)
        self._rebuild_view_bar()
        if on and open_page:
            self.a_page_cfd.setChecked(True)
            self._show_page("cfd")
        elif not on and self._page == "cfd":
            self.a_page_model.setChecked(True)
            self._show_page("model")

    def _show_model_page(self):
        """picking walls happens in the 3D view."""
        self.a_page_model.setChecked(True)
        self._show_page("model")

    def _show_page(self, page):
        if self.scene is None:
            return
        reveal = None
        if page.startswith("plot:"):
            ident = int(page.split(":", 1)[1])
            if ident not in self._plot_acts:
                page = "model"
            else:
                self._switch_parts(page)                  # its own shown / hidden parts
                self._active_plot = ident
                self._plot_acts[ident].setChecked(True)
                self._refresh_plot(ident)
                self.stack.setCurrentWidget(self.plot_page)
                reveal = ("plots", ident)
        elif page.startswith("contour:"):
            ident = int(page.split(":", 1)[1])
            if ident not in self._contour_acts:
                page = "model"
            else:
                self._contour_acts[ident].setChecked(True)
                self._switch_parts(page)
                self._switch_view(page)                  # its camera, its Show ▾, drawn
                reveal = ("contours", ident)
        if page == "cfd" and not self._cfd_on:
            page = "model"
        if page in ("model", "cfd"):
            self._switch_parts("model")                   # the 3D View's parts
        self._page = page
        if page == "model":
            self.a_page_model.setChecked(True)
            self._switch_view("model")                   # the model alone
        elif page == "cfd":
            self.a_page_cfd.setChecked(True)
        if not page.startswith("plot:"):
            self.stack.setCurrentWidget(self.inflation_view if page == "cfd" else self.plotter)
        if page == "model" or page.startswith("contour:"):
            self.plotter.render()
        self._pages_scroll.show_current()
        if reveal is not None:                          # its fold-out, the others folded
            self.sidebar.reveal(*reveal)

    # ---- each tab's own shown / hidden parts ---------------------------------------------------
    def _hidden_now(self):
        sc = self.scene
        return sorted(n for n in sc.names if not sc.visible.get(n))

    def _parts_of(self, key):
        """The parts hidden in tab `key` ("model", "contour:<id>", "plot:<id>"), or None."""
        if key == "model":
            return self._model_hidden
        kind, ident = key.split(":", 1)
        if kind == "contour":
            c = self.sidebar.contours_panel.contour(int(ident))
            return ((c or {}).get("view") or {}).get("hidden")
        m = self.sidebar.plots_panel.plot(int(ident))
        return (m or {}).get("hidden")

    def _keep_parts(self, key, hidden):
        if key == "model":
            self._model_hidden = list(hidden)
            return
        kind, ident = key.split(":", 1)
        if kind == "contour":
            c = self.sidebar.contours_panel.contour(int(ident))
            if c is not None:
                c["view"] = {**(c.get("view") or {"camera": None, "show": {}}),
                             "hidden": list(hidden)}
        else:
            m = self.sidebar.plots_panel.plot(int(ident))
            if m is not None:
                m["hidden"] = list(hidden)

    def _switch_parts(self, key):
        """Tab `key` shown: the tab left keeps its hidden parts, this one's are put back
        (the first time: as they are)."""
        sc = self.scene
        old = getattr(self, "_vis_page", None)
        if sc is None or key == old:
            return
        if old is not None:
            self._keep_parts(old, self._hidden_now())
        self._vis_page = key
        pp = self.sidebar.plots_panel
        pp.tab = int(key.split(":", 1)[1]) if key.startswith("plot:") else None
        hidden = self._parts_of(key)
        if hidden is None:
            self._keep_parts(key, self._hidden_now())
            return
        want = set(hidden) & set(sc.names)
        if want != set(self._hidden_now()):
            shown = [n for n in sc.names if n not in want]
            if shown:
                sc.set_visible(shown, True, render=False)
            if want:
                sc.set_visible(sorted(want), False, render=False)
            self.sidebar.list.sync_checks(sc.visible)
            sc._after_visibility_change()             # contours, plots, picks follow

    # ---- each 3D tab's own view: camera and Show ▾ -------------------------------------------
    def _own_view(self):
        """Is a contour's tab the 3D page (its own axes, grid and axis indicator)?"""
        return bool(self._view_page and self._view_page.startswith("contour:"))

    def _view_state(self):
        cam = self.scene.camera_snapshot()
        return {"camera": [list(map(float, v)) for v in cam[:3]] + [float(cam[3]),
                                                                    bool(cam[4]),
                                                                    float(cam[5])],
                "show": {k: self.a_show[k].isChecked() for k in VIEW_KEYS}}

    def _tab_view(self, page):
        if page == "model":
            return self._model_view
        c = self.sidebar.contours_panel.contour(int(page.split(":", 1)[1]))
        return c.get("view") if c is not None else None

    def _store_view(self, page, st):
        if page == "model":
            self._model_view = st
            return
        c = self.sidebar.contours_panel.contour(int(page.split(":", 1)[1]))
        if c is not None:
            c["view"] = {**(c.get("view") or {}), **st}       # (its hidden parts stay)

    def _switch_view(self, page):
        """`page` ("model" or "contour:<id>") becomes the 3D page: the one left keeps its
        view, this one gets its own back (or keeps the current, the first time); a
        contour is drawn only in its tab."""
        if self.scene is None:
            return
        old = self._view_page
        cp = self.sidebar.contours_panel
        if page != old:
            if old is not None:
                self._store_view(old, self._view_state())
            self._view_page = page
            st = self._tab_view(page)
            if st is None:
                self._store_view(page, self._view_state())
            else:
                self._apply_view(st, own=page != "model")
        cp.set_tab(int(page.split(":", 1)[1]) if page.startswith("contour:") else None)

    def _apply_view(self, st, own):
        """Put a tab's view on the scene: its camera and Show ▾ toggles (own False: the
        axes, grid and axis indicator are the app's)."""
        sc = self.scene
        if sc is None or not st:
            return
        show = st.get("show") or {}
        for k, method in self.SCENE_TOGGLES.items():
            if k in show and bool(show[k]) != bool(sc.state.get(k)):
                getattr(sc, method)(bool(show[k]), render=False)
        a = self.ctl.appearance
        if own and "axes" in show and "grid" in show:
            mode = {(True, True): "both", (True, False): "axes", (False, True): "grid",
                    (False, False): "off"}[(bool(show["axes"]), bool(show["grid"]))]
            sc.set_axes_mode(mode, render=False)
            sc.set_axis_indicator(bool(show.get("axis_indicator", True)), render=False)
        else:
            sc.set_axes_mode(a[self._axes_key()], render=False)
            sc.set_axis_indicator(a["axis_indicator"], render=False)
        if st.get("camera"):
            sc.set_camera_snapshot(st["camera"])
            self.a_parallel.blockSignals(True)
            self.a_parallel.setChecked(not sc.state["parallel"])
            self.a_parallel.blockSignals(False)
        self._sync_show()
        sc.p.render()

    def fit_view(self):
        """View ▸ Fit (⌘0): the plot shown back to its whole data, else the 3D view."""
        if self.scene is None:
            return
        if self._page.startswith("plot:"):
            ed = self.sidebar.plots_panel.editors.get(int(self._page.split(":", 1)[1]))
            if ed is not None:
                ed[1].fit_view()
            return
        self.scene.fit()

    def _rebuild_view_bar(self):
        """The pill under the view: 3D model · Inflation Layers · each contour · each
        plot. Shown when there is more than the 3D model."""
        cs = list(self.sidebar.contours_panel.contours) if self.scene is not None else []
        for ident in [i for i in self._contour_acts if i not in {c["id"] for c in cs}]:
            a = self._contour_acts.pop(ident)
            self._page_group.removeAction(a)
            a.deleteLater()
        for c in cs:
            a = self._contour_acts.get(c["id"])
            if a is None:
                a = QAction(c["name"], self)
                a.setCheckable(True)
                self._page_group.addAction(a)
                a.triggered.connect(lambda _=False, i=c["id"]: self._show_page(f"contour:{i}"))
                self._contour_acts[c["id"]] = a
            a.setText(c["name"])
            a.setToolTip(c["name"])
        ms = list(self.scene.plots) if self.scene is not None else []
        for ident in [i for i in self._plot_acts if i not in {m["id"] for m in ms}]:
            a = self._plot_acts.pop(ident)
            self._page_group.removeAction(a)
            a.deleteLater()
        for m in ms:
            a = self._plot_acts.get(m["id"])
            if a is None:
                a = QAction(m["name"], self)
                a.setCheckable(True)
                self._page_group.addAction(a)
                a.triggered.connect(lambda _=False, i=m["id"]: self._show_page(f"plot:{i}"))
                self._plot_acts[m["id"]] = a
            a.setText(m["name"])
            a.setToolTip(f"{m['name']} ({KINDS[m['kind']]['title']})")
        acts = self.view_bar_actions()
        self._pages_cap = Capsule(acts, name="Segmented", dividers=False)   # same gaps
        self._pages_cap.layout().setSpacing(2)
        tab_of = {**{a: ("plot", i) for i, a in self._plot_acts.items()},
                  **{a: ("contour", i) for i, a in self._contour_acts.items()}}
        for b in self._pages_cap.buttons:              # right-click a plot's / contour's tab
            what = tab_of.get(b.defaultAction())
            if what is not None:
                b.setContextMenuPolicy(Qt.CustomContextMenu)
                b.customContextMenuRequested.connect(
                    lambda pos, btn=b, w=what: self._tab_menu(*w, btn.mapToGlobal(pos)))
        self._pages_scroll.set_tabs(self._pages_cap)   # the old pill is deleted
        self.view_bar.setVisible(len(acts) > 1)
        self._pages_scroll.show_current()

    def view_bar_actions(self):
        """The tabs under the view, in order: 3D Model, Inflation Layers, each contour,
        each plot."""
        ms = list(self.scene.plots) if self.scene is not None else []
        cs = list(self.sidebar.contours_panel.contours) if self.scene is not None else []
        return [self.a_page_model] + ([self.a_page_cfd] if self._cfd_on else []) + \
            [self._contour_acts[c["id"]] for c in cs if c["id"] in self._contour_acts] + \
            [self._plot_acts[m["id"]] for m in ms if m["id"] in self._plot_acts]

    def _tab_menu(self, kind, ident, pos):
        """Right-click on a plot's or a contour's tab: Open, Rename…, Delete."""
        panel = self.sidebar.plots_panel if kind == "plot" else self.sidebar.contours_panel
        menu = Menu(self)
        menu.addAction("Open", lambda: self._show_page(f"{kind}:{ident}"))
        menu.addAction("Rename…", lambda: panel.rename(ident))
        menu.addSeparator()
        menu.addAction("Delete", lambda: panel.remove(ident))
        menu.exec(pos)

    def _contour_added(self, ident):
        self._rebuild_view_bar()
        self._show_page(f"contour:{ident}")

    def _contour_removed(self, ident):
        """Its tab goes (the 3D view stays, with the contour now active)."""
        was = self._page == f"contour:{ident}"
        self._rebuild_view_bar()
        if was:
            self._show_page("model")

    def _plot_added(self, ident):
        self._rebuild_view_bar()
        self._show_page(f"plot:{ident}")

    def _plot_removed(self, ident):
        if self._active_plot == ident:
            self._active_plot = None
        self._show_cuts()
        was = self._page == f"plot:{ident}"
        self._rebuild_view_bar()
        if was:
            self._show_page("model")

    def _plot_renamed(self, ident):
        """Its tab, and the page's title when it is the one shown."""
        self._rebuild_view_bar()
        if self._page == f"plot:{ident}":
            self._refresh_plot(ident)

    def _plot_changed(self, ident):
        self._active_plot = ident
        if self._page == f"plot:{ident}":
            self._refresh_plot(ident)
        else:
            self._show_cuts()

    def _show_cuts(self):
        """The cuts whose eye is open, drawn in 3D while the Analyze tab (Plots) shows."""
        if self.scene is None:
            return
        pp = self.sidebar.plots_panel
        on = self.sidebar.tab_shown("plots")          # cuts while the Analyze tab shows
        lines = [pp.results[m["id"]]["lines"] for m in self.scene.plots
                 if on and m.get("show", True) and pp.results.get(m["id"])
                 and pp.results[m["id"]].get("lines") is not None]
        self.scene.plot_cut.show(lines, self.scene.accent)

    def _refresh_plot(self, ident):
        pp = self.sidebar.plots_panel
        m, r = pp.plot(ident), pp.results.get(ident)
        if m is None or r is None:
            return
        s, unit = self.scene.measure.unit_scale()
        rp = self.sidebar.contours_panel               # a field in its unit (Contours)
        self.plot_page.show(m, r, self.scene.colors, s, unit,
                            value_unit=(lambda v, f=r["value"]: rp.shown_values(f, v),
                                        rp.unit_label(r["value"])))
        if ident in pp.editors:                         # its Axes: the auto Min / Max
            pp.editors[ident][1].show_auto(self.plot_page.plot.drawn_ranges())
        self._show_cuts()
