"""One document window: toolbar, then the parts list | the 3D view | the inspector."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QCursor
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QMainWindow, QMessageBox, QSplitter, QStackedWidget,
    QVBoxLayout, QWidget,
)

from meshviewer.core.formats import load, supported_extensions
from meshviewer.core.model import MissingDependency
from meshviewer.gui import memory
from meshviewer.gui.access import name_controls
from meshviewer.gui.dialogs.units import default_unit, FileUnitDialog
from meshviewer.gui.feedback import show_error
from meshviewer.gui.jobs import run_job
from meshviewer.gui.pages.inflation import InflationView
from meshviewer.gui.pages.plots import PlotPage
from meshviewer.gui.sidebar import Sidebar
from meshviewer.gui.store import settings
from meshviewer.gui.style import accent, is_dark
from meshviewer.gui.undo import Changes
from meshviewer.gui.viewport import make_view
from meshviewer.gui.welcome import Welcome
from meshviewer.gui.window_bars import Bars
from meshviewer.gui.window_export import Exports
from meshviewer.gui.window_pages import Pages, TabScroll
from meshviewer.render.scene import Scene

FILE_FILTER = "Meshes and CAD (" + " ".join(f"*{e}" for e in supported_extensions()) + ")"


def _settings():
    return settings()


# ---------------------------------------------------------------------------
# Window
# ---------------------------------------------------------------------------

class ViewerWindow(Bars, Pages, Exports, QMainWindow):
    def __init__(self, app_controller):
        super().__init__()
        self.ctl = app_controller
        self.path: Path | None = None
        self.scene: Scene | None = None
        self._job = None

        self._close_ok = False                         # the "close without exporting?" answer
        self.setUnifiedTitleAndToolBarOnMac(True)
        self.setAcceptDrops(True)
        self.resize(1400, 900)
        self.setWindowTitle("Mesh Viewer")

        # ---- 3D view (placeholder until a file is loaded) ---------------
        self.plotter = make_view(self)
        # 4× MSAA: smooth edges at much lower cost than 8× on Retina screens.
        self.plotter.enable_anti_aliasing("msaa", multi_samples=4)
        self.welcome = Welcome(self.ctl.recent_files)     # an empty window: the way in
        self.welcome.open_dialog.connect(self.ctl.open_dialog)
        self.welcome.open_file.connect(lambda f: self.ctl.open_path(Path(f), prefer=self))
        self.empty = self.welcome
        self.stack = QStackedWidget()
        self.stack.addWidget(self.welcome)
        self.stack.addWidget(self.plotter)
        # Inflation Layers (CAD) — its page, and a bar under the view
        # with a pill to switch between the 3D model and that page.
        self.inflation_view = InflationView()
        self.stack.addWidget(self.inflation_view)
        self.plot_page = PlotPage()                    # Plots: the tab of a plot
        self.stack.addWidget(self.plot_page)
        self.view_area = QWidget()
        va = QVBoxLayout(self.view_area)
        va.setContentsMargins(0, 0, 0, 0)
        va.setSpacing(0)
        va.addWidget(self.stack, 1)
        self.view_bar = QWidget()
        self.view_bar.setObjectName("ViewBar")
        self.view_bar.setAttribute(Qt.WA_StyledBackground, True)
        vb = QHBoxLayout(self.view_bar)
        vb.setContentsMargins(10, 6, 10, 6)
        self._view_lay = vb
        group = QActionGroup(self)
        group.setExclusive(True)
        self._page_group = group
        self._pages_cap = None                     # the pill: 3D model · Inflation · plots
        self._plot_acts = {}                       # plot id -> its tab (QAction)
        self._cfd_on = False
        self._page = "model"
        self._active_plot = None                   # whose cut is drawn in 3D
        self.a_page_model = QAction("3D Model", self)
        self.a_page_model.setToolTip("3D Model")
        self.a_page_cfd = QAction("Inflation Layers", self)
        self.a_page_cfd.setToolTip("Inflation Layers")
        for a in (self.a_page_model, self.a_page_cfd):
            a.setCheckable(True)
            group.addAction(a)
        self.a_page_model.setChecked(True)
        self.a_page_model.triggered.connect(lambda: self._show_page("model"))
        self.a_page_cfd.triggered.connect(lambda: self._show_page("cfd"))
        self._pages_scroll = TabScroll()              # many plots: scroll sideways
        vb.addWidget(self._pages_scroll, 1)
        va.addWidget(self.view_bar)
        self.view_bar.setVisible(False)

        self.sidebar = Sidebar()
        self.changes = Changes(self)                  # Edit ▸ Undo / Redo
        self.sidebar.changes = self.changes
        self.sidebar.quality_requested.connect(self._retessellate)
        self.sidebar.renamed.connect(self._edited_changed)
        self.sidebar.info_panel.file_unit_changed.connect(self._set_file_unit)   # Info ▸ File unit
        self.sidebar.inflation_panel.mode_toggled.connect(self._cfd_mode)
        pp = self.sidebar.plots_panel                                      # Plots
        pp.added.connect(self._plot_added)
        pp.removed.connect(self._plot_removed)
        pp.renamed.connect(self._plot_renamed)
        pp.changed.connect(self._plot_changed)
        pp.show_plot.connect(lambda i: self._show_page(f"plot:{i}"))
        pp.cuts_changed.connect(self._show_cuts)               # an eye clicked
        rp = self.sidebar.results_panel
        pp.value_unit = lambda f: (lambda v: rp.shown_values(f, v), rp.unit_label(f))
        self.sidebar.activity_changed.connect(self._activity_changed)   # a tab, a tool
        self.sidebar.results_panel.units_changed.connect(     # a field's unit: the plots too
            lambda: self._active_plot is not None and self._refresh_plot(self._active_plot))
        self.sidebar.inflation_panel.changed.connect(self.inflation_view.set_result)
        self.sidebar.inflation_panel.wants_model.connect(self._show_model_page)
        self.inflation_view.section.set_panel(self.sidebar.inflation_panel)
        ep = self.sidebar.edit_panel                                       # Edit section
        ep.edit_requested.connect(lambda r, t, label: self.scene and self.changes.edit(r, t, label))
        ep.undo_requested.connect(lambda: self.scene and self.changes.undo_last_edit())
        ep.reset_requested.connect(lambda: self.scene and self.changes.reset_edits())
        ep.original_toggled.connect(lambda on: self.scene and self.scene.set_show_original(on))
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.sidebar)          # the parts list
        self.splitter.addWidget(self.view_area)
        self.splitter.addWidget(self.sidebar.inspector)   # the tools, in tabs
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 0)
        self.splitter.setSizes([250, 766, 384])           # the tools as wide as their cards
        self.splitter.setHandleWidth(1)
        self.splitter.setChildrenCollapsible(False)
        self.setCentralWidget(self.splitter)

        self.select_kind = "part"                         # Select ▾ (kept from file to file)
        self._build_actions()
        self._build_toolbar()
        self._build_menus()
        self._set_loaded(False)
        name_controls(self)                            # VoiceOver: names of icon buttons
        self._sync_show()

        QApplication.styleHints().colorSchemeChanged.connect(self._theme_changed)

    # ---- actions / toolbar / menus ----------------------------------
    # ---- loading --------------------------------------------------------
    @property
    def is_empty(self):
        return self.path is None

    def load(self, path: Path):
        self.path = Path(path)
        self.setWindowFilePath(str(self.path))      # ⌘-click the title: the file's folders
        self._set_title(False)
        self.welcome.opening(self.path.name)
        path = self.path
        # STEP opens at Settings ▸ CAD meshing control, or at the one used last time
        pref = self.ctl.prefs["cad_quality"]
        saved = _settings().value("step_quality") if pref == "last" else pref
        quality = int(saved) if saved is not None else None

        def job():
            print(f"Reading {path} …")
            return load(path, quality=quality)
        self._job = run_job(job, self._loaded, self._failed,
                            busy=(self, f"Opening {self.path.name}…"))

    def _loaded(self, model):
        if not model.parts:
            return self._failed(RuntimeError(f"No {model.group_title.lower()} found in this file."))
        self.scene = Scene(self.plotter, model, dark=is_dark(), accent=accent())
        saved = memory.load(self.path)                   # as you left it
        memory.restore(self.scene, saved)
        self.sidebar.bind(self.scene)
        self.sidebar.plots_panel.file_stem = self.path.stem
        self._rebuild_view_bar()                         # a tab per plot
        self.a_parallel.blockSignals(True)                  # show the scene's projection
        self.a_parallel.setChecked(not self.scene.state["parallel"])
        self.a_parallel.blockSignals(False)
        self._sync_show()
        # Menu opened just after VTK finishes handling the click (not inside it).
        self.scene.on_context = lambda names, clicked: QTimer.singleShot(
            0, lambda p=QCursor.pos(): self.sidebar.part_menu(names, clicked, p))
        self._sync_units()
        if not saved and self.ctl.prefs["shown_unit"] != "file":    # Settings ▸ Units
            self.scene.measure.display_unit = self.ctl.prefs["shown_unit"]
        if not (saved or {}).get("file_unit"):
            self._ask_file_unit()                      # first time: what unit is it in?
        self.apply_appearance()
        # View ▸ Section and the tool's switch stay in sync.
        if not getattr(self, "_section_synced", False):
            self.sidebar.section_panel.enable.toggled.connect(self._section_switched)
            self._section_synced = True
        self._section_switched(self.scene.section.enabled)
        self._set_loaded(True)
        self.set_select_kind(self.select_kind)             # a mesh kind: Part on CAD
        ip = self.sidebar.inflation_panel                  # Inflation Layers as left
        page = getattr(self.scene, "inflation_page", None) or {}
        self.inflation_view.set_state(page)                # tab, flip side, zoom
        self.inflation_view.set_result(ip.result)
        self._cfd_mode(model.is_cad and ip.enabled, open_page=False)
        if model.is_cad and ip.enabled and page.get("page") == "cfd":
            self.a_page_cfd.setChecked(True)
            self._show_page("cfd")
        elif str(page.get("page", "")).startswith("plot:"):   # a plot's tab
            self._show_page(page["page"])
        memory.restore_camera(self.scene, saved)
        name_controls(self)                            # (the tools' controls are built now)
        self.ctl.add_recent(self.path)                   # File ▸ Open Recent
        self.plotter.render()

    def _failed(self, exc):
        name = self.path.name if self.path else "file"
        if isinstance(exc, MissingDependency):
            detail = str(exc)
            step = (f"Install it into the app's Python environment:\n"
                    f"   .venv/bin/pip install {exc.package}\n(then rebuild with build_app.sh)")
        else:
            detail = str(exc) or exc.__class__.__name__
            step = ("Check that the file is complete (not still being copied or written) and "
                    "that File ▸ Open lists its type. A STEP or IGES file may open after "
                    "re-saving it from your CAD program.")
        show_error(self, f"“{name}” couldn't be opened.", detail, step, name)
        self.path = None if self.scene is None else self.path
        if self.scene is None:
            self.welcome.idle()

    # ---- mesh quality (STEP) ----------------------------------------
    def _retessellate(self, level):
        if not (self.scene and self.scene.can_retessellate):
            return
        fn = self.scene.model.retessellate
        self._pending_level = level
        name = self.scene.model.quality_levels[level]
        self._job = run_job(lambda: fn(level), self._retessellated, self._retessellate_failed,
                            busy=(self, f"Meshing at {name}…"))

    def _retessellated(self, parts):
        level = self._pending_level
        self.scene.replace_parts(parts, level)
        self.sidebar.refresh_parts()
        self.sidebar.info_panel.model_changed()
        _settings().setValue("step_quality", level)

    def _retessellate_failed(self, exc):
        self.sidebar.quality_failed()
        show_error(self, "The model couldn't be meshed at this quality.", str(exc),
                   "It stays at the quality it had. Try another level in Meshing Control.",
                   self.path.name if self.path else "", warning=True)

    # ---- misc -----------------------------------------------------------
    # ---- appearance --------------------------------------------------
    def apply_appearance(self):
        self.sidebar.list.set_density(self.ctl.appearance["density"])
        self._sync_show()
        if self.scene:
            a = self.ctl.appearance
            self.scene.set_axis_font(a["axis_font"], rebuild=False)
            self.scene.set_edge_options(a["edge_width"], a["hide_edges_moving"], render=False)
            self.scene.set_shading(a["shading"], render=False)
            self.scene.set_axes_mode(a["axes"], rebuild=False, render=False)
            self.scene.set_background(*self.ctl.background())        # rebuilds grid + axes

    # --- toolbar toggles for what is shown -----------------------------
    SCENE_TOGGLES = {"mesh_edges": "set_mesh_edges", "feature_edges": "set_feature_edges",
                     "faces": "set_faces", "bbox": "set_bbox", "origin": "set_origin"}

    def _show_toggled(self, key, on):
        if key in ("axes", "grid"):
            # Axes and Grid together are the saved app-wide axes mode
            ax, gr = self.a_show["axes"].isChecked(), self.a_show["grid"].isChecked()
            mode = {(True, True): "both", (True, False): "axes",
                    (False, True): "grid", (False, False): "off"}[(ax, gr)]
            self.ctl.set_appearance(axes=mode)
            return
        if not self.scene:
            return
        getattr(self.scene, self.SCENE_TOGGLES[key])(on)
        # Faces hidden with no edges switched on would show nothing: feature edges on.
        st = self.scene.state
        if key == "faces" and not on and not st["feature_edges"] and not st["mesh_edges"]:
            self.a_show["feature_edges"].setChecked(True)
            self.scene.set_feature_edges(True)

    def _sync_show(self):
        """Toolbar toggles = the scene's state + the saved axes mode (no signals)."""
        mode = self.ctl.appearance["axes"]
        want = {"axes": mode in ("axes", "both"), "grid": mode in ("grid", "both")}
        if self.scene:
            want.update({k: bool(self.scene.state.get(k)) for k in self.SCENE_TOGGLES})
        for k, on in want.items():
            a = self.a_show[k]
            a.blockSignals(True)
            a.setChecked(on)
            a.blockSignals(False)

    # --- Inflation Layers (CAD files) -------------------------------------
    # --- Plots: one tab per plot under the 3D view --------------------------------
    def _sync_units(self):
        """Select the shown unit (the file's own unless another was picked)."""
        unit = self.scene.measure.display_unit or self.scene.model.units
        for a in self.a_units:
            a.setChecked(a.data() == unit)
        self.a_units_menu.setText(unit or "Units")      # the toolbar's pull-down

    def _ask_file_unit(self):
        """First time this file is opened: which unit are its numbers in?"""
        m = self.scene.model
        unit = default_unit(m, self.ctl.prefs)
        self._set_file_unit(unit)                      # works meanwhile; the answer replaces it
        if self.ctl.prefs["ask_unit"]:                 # Settings ▸ Units
            self._open_unit_sheet(unit)

    def _edit_file_unit(self):
        """Toolbar ✎: change the file's unit (the same sheet as on the first open)."""
        if self.scene is not None:
            self._open_unit_sheet(self.scene.model.units
                                  or default_unit(self.scene.model, self.ctl.prefs))

    def _open_unit_sheet(self, unit):
        self._unit_dialog = FileUnitDialog(self, self.path.name, unit,
                                           self.scene.model.file_units)
        self._unit_dialog.chosen.connect(self._set_file_unit)
        self._unit_dialog.open()

    def _set_file_unit(self, unit):
        sc = self.scene
        if sc is None or not unit:
            return
        sc.model.units = unit
        sc.measure.set_display_unit(sc.measure.display_unit)    # None: follows the file
        self._sync_units()
        self.sidebar.info_panel.refresh()
        self.sidebar.edit_panel.refresh()
        self.sidebar.cfd_panel.model_changed()         # lengths in metres
        self.sidebar.inflation_panel.model_changed()
        self.sidebar.results_panel.length_unit_changed()   # positions X / Y / Z
        self.sidebar.plots_panel.model_changed()       # positions in the new unit

    def _toggle_section(self, on):
        self.sidebar.section_panel.enable.setChecked(on)

    def _section_switched(self, on):
        self.a_section.blockSignals(True)
        self.a_section.setChecked(on)
        self.a_section.blockSignals(False)

    def _deselect(self):
        if self.scene:
            if self.scene.measure.mode != "off":
                self.scene.measure.clear()
            self.scene.select(None)
            self.scene.elements.clear()
            self.sidebar.show_selection([])

    def toggle_sidebar(self, on):
        self.sidebar.setVisible(on)

    def toggle_inspector(self, on):
        self.sidebar.set_inspector_visible(on)

    def show_tools(self, tab):
        """View ▸ View / Measure / Analyze Tools (⌥⌘1–3): the inspector, on that tab."""
        if self.scene is None:
            return
        if self.sidebar.inspector.isHidden():
            self.sidebar.set_inspector_visible(True)
        self.sidebar.show_tab(tab)

    # ---- Edit section --------
    def _set_title(self, edited):
        """The file's name, "— Edited" while moves / rotations wait to be exported (as
        macOS documents do), and the dot in the close button."""
        if self.path is not None:
            self.setWindowTitle(f"{self.path.name}{' — Edited' if edited else ''}[*]")
        self.setWindowModified(edited)

    def _edited_changed(self):
        # only edits count as unsaved — names, colours, the view are remembered
        edited = bool(self.scene and self.scene.model.edited)
        self._set_title(edited)
        self.sidebar.edit_panel.refresh()
        self.sidebar.info_panel.model_changed()        # new bounds
        self.sidebar.cfd_panel.model_changed()         # flow vectors, length
        self.sidebar.inflation_panel.model_changed()   # walls, arrows, auto length
        self.sidebar.results_panel.model_changed()     # results follow the edits
        self.sidebar.plots_panel.model_changed()       # cuts of the moved model

    def _unit_chosen(self, a):
        if self.scene:
            self.scene.measure.set_display_unit(a.data())
            self._sync_units()
            self.sidebar.info_panel.refresh()           # Info in the new unit
            self.sidebar._show_info(self.scene.selected_parts)   # a picked length / area
            self.sidebar.cfd_panel.model_changed()      # mesh length in metres
            self.sidebar.inflation_panel.model_changed()   # auto length in metres
            self.sidebar.results_panel.length_unit_changed()   # positions X / Y / Z
            self.sidebar.plots_panel.model_changed()       # plots in the new unit

    # --- Export ----------------------------------------------------------
    def _toggle_measure(self, on):
        if self.scene:
            self.sidebar.set_measuring(on)           # the Measure tab (shows the inspector)
        self._activity_changed()

    def _activity_changed(self):
        """The inspector shown or hidden, a tab, a tool opened: View ▸ Measure and
        View ▸ Inspector say what is on; Plots draw their cuts while their tab shows."""
        loaded = self.scene is not None
        shown = self.a_inspector.isEnabled()          # (an empty window hides it: not a choice)
        for a, on in ((self.a_measure, loaded and self.sidebar.is_active("measure")),
                      (self.a_inspector, (not self.sidebar.inspector.isHidden()) if shown
                       else self.a_inspector.isChecked())):
            if a.isChecked() != on:
                a.blockSignals(True)
                a.setChecked(on)
                a.blockSignals(False)
        if loaded:
            self._show_cuts()

    def _theme_changed(self, *_):
        if self.scene:
            self.scene.set_theme(is_dark(), accent=accent())

    # drag & drop
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()

    def dropEvent(self, e):
        for url in e.mimeData().urls():
            if url.isLocalFile():
                self.ctl.open_path(Path(url.toLocalFile()), prefer=self)

    # ---- File ▸ Revert to Original… ---------------------------------------------------
    def revert_to_original(self):
        """Forget everything about this file and open it as the first time (after asking)."""
        if self.scene is None or self.path is None:
            return
        box = QMessageBox(self)
        box.setWindowModality(Qt.WindowModal)           # a sheet on macOS
        box.setIcon(QMessageBox.Warning)
        box.setText(f"Revert “{self.path.name}” to how it opened the first time?")
        box.setInformativeText(
            "Your edits, colors, names, hidden parts, the view, the tools and their "
            "settings, and the plots of this file are forgotten. You can't undo this.")
        revert = box.addButton("Revert", QMessageBox.DestructiveRole)
        box.addButton(QMessageBox.Cancel)
        box.setDefaultButton(QMessageBox.Cancel)
        self._revert_box = box
        box.finished.connect(lambda _: box.clickedButton() is revert and self._revert())
        box.open()

    def _revert(self):
        path, geometry, full = self.path, self.saveGeometry(), self.isFullScreen()
        memory.forget(path)
        new = self.ctl.new_window()                     # the same place, a fresh start
        new.restoreGeometry(geometry)
        if full:
            new.showFullScreen()
        self._reverting = True                          # no question, nothing remembered
        self.close()
        new.load(path)

    def closeEvent(self, e):
        if getattr(self, "_reverting", False):
            self.plotter.close()
            self.ctl.forget(self)
            return super().closeEvent(e)
        # rotations / mirrors only live in memory until exported: ask in a sheet first
        if self.scene is not None and self.scene.model.edited and not self._close_ok:
            e.ignore()
            box = QMessageBox(self)
            box.setWindowModality(Qt.WindowModal)
            box.setIcon(QMessageBox.Warning)
            box.setText(f"Close “{self.path.name}” without exporting your edits?")
            box.setInformativeText("Moves, rotations and mirrors are only kept if you export "
                                   "the file. (Names, colors and the view are remembered.)")
            close = box.addButton("Close", QMessageBox.DestructiveRole)
            box.addButton(QMessageBox.Cancel)
            box.setDefaultButton(QMessageBox.Cancel)
            self._close_box = box
            box.finished.connect(lambda _: box.clickedButton() is close and self._close_anyway())
            box.open()
            return
        self.remember_view()
        self.plotter.close()
        self.ctl.forget(self)
        super().closeEvent(e)

    def _close_anyway(self):
        self._close_ok = True
        self.close()

    def remember_view(self):
        """camera, colours, hidden parts, section… for the next time."""
        if self.scene is not None and self.path is not None:
            try:                                        # the Inflation page too
                self.scene.inflation_page = {
                    **self.inflation_view.get_state(),
                    "page": self._page}
            except Exception:                           # noqa: BLE001
                pass
            try:
                memory.save(self.path, memory.capture(self.scene))
            except Exception as exc:                    # never block closing
                print(f"could not remember the view: {exc}")
