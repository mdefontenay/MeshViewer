"""The window's pages: the 3D model, the Inflation Layers page (CAD files) and one per
plot, with the tab bar under the view that switches between them."""
from __future__ import annotations

import shiboken6
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QFrame, QScrollArea, QSizePolicy

from meshviewer.core.plots import KINDS
from meshviewer.gui.widgets import Capsule, Menu


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
        self.setFixedHeight(capsule.sizeHint().height() + 10)   # + the thin scrollbar
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
        if page.startswith("plot:"):
            ident = int(page.split(":", 1)[1])
            if ident not in self._plot_acts:
                page = "model"
            else:
                self._active_plot = ident
                self._plot_acts[ident].setChecked(True)
                self._refresh_plot(ident)
                self.stack.setCurrentWidget(self.plot_page)
        if page == "cfd" and not self._cfd_on:
            page = "model"
        self._page = page
        if page == "model":
            self.a_page_model.setChecked(True)
        elif page == "cfd":
            self.a_page_cfd.setChecked(True)
        if not page.startswith("plot:"):
            self.stack.setCurrentWidget(self.inflation_view if page == "cfd" else self.plotter)
        if page == "model":
            self.plotter.render()
        self._pages_scroll.show_current()

    def _rebuild_view_bar(self):
        """The pill under the view: 3D model · Inflation Layers · each plot.
        Shown when there is more than the 3D model."""
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
        self._pages_cap = Capsule(acts, name="Segmented")
        plot_of = {a: i for i, a in self._plot_acts.items()}
        for b in self._pages_cap.buttons:              # right-click a plot's tab
            ident = plot_of.get(b.defaultAction())
            if ident is not None:
                b.setContextMenuPolicy(Qt.CustomContextMenu)
                b.customContextMenuRequested.connect(
                    lambda pos, btn=b, i=ident: self._tab_menu(i, btn.mapToGlobal(pos)))
        self._pages_scroll.set_tabs(self._pages_cap)   # the old pill is deleted
        self.view_bar.setVisible(len(acts) > 1)
        self._pages_scroll.show_current()

    def view_bar_actions(self):
        """The tabs under the view, in order: 3D Model, Inflation Layers, each plot."""
        ms = list(self.scene.plots) if self.scene is not None else []
        return [self.a_page_model] + ([self.a_page_cfd] if self._cfd_on else []) + \
            [self._plot_acts[m["id"]] for m in ms if m["id"] in self._plot_acts]

    def _tab_menu(self, ident, pos):
        """Right-click on a plot's tab: Open, Rename…, Delete."""
        pp = self.sidebar.plots_panel
        menu = Menu(self)
        menu.addAction("Open", lambda: self._show_page(f"plot:{ident}"))
        menu.addAction("Rename…", lambda: pp.rename(ident))
        menu.addSeparator()
        menu.addAction("Delete", lambda: pp.remove(ident))
        menu.exec(pos)

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
        rp = self.sidebar.results_panel                # a field in its unit (Results)
        self.plot_page.show(m, r, self.scene.colors, s, unit,
                            value_unit=(lambda v, f=r["value"]: rp.shown_values(f, v),
                                        rp.unit_label(r["value"])))
        self._show_cuts()
