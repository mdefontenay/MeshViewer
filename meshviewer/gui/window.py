"""One document window: toolbar + side panel + 3D view."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QCursor, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
    QScrollArea, QSizePolicy, QSplitter, QStackedWidget, QToolBar, QVBoxLayout, QWidget,
)
from pyvistaqt import QtInteractor

from meshviewer.core.cfd_export import FORMATS as CFD_FORMATS, SUFFIX as CFD_SUFFIX
from meshviewer.core.cfd_export import export as write_cfd
from meshviewer.core.export import FORMATS as EXPORT_FORMATS
from meshviewer.core.export import available as available_formats
from meshviewer.core.export import export as write_export
from meshviewer.core.formats import load, supported_extensions
from meshviewer.core.model import MissingDependency
from meshviewer.gui import memory
from meshviewer.gui.icons import icon
from meshviewer.gui.jobs import run_job
from meshviewer.render.scene import Scene
from meshviewer.gui.dialogs.units import FileUnitDialog, default_unit
from meshviewer.gui.sections import SECTIONS
from meshviewer.gui.sidebar import Sidebar
from meshviewer.gui.style import accent, is_dark
from meshviewer.gui.dialogs.appearance import AppearanceDialog
from meshviewer.gui.dialogs.export import ExportDialog
from meshviewer.gui.pages.inflation import InflationView
from meshviewer.gui.pages.plots import PlotPage
from meshviewer.core.plots import KINDS
from meshviewer.gui.dialogs.screenshot import ScreenshotDialog
from meshviewer.gui.widgets import Capsule, Menu

FILE_FILTER = "Meshes and CAD (" + " ".join(f"*{e}" for e in supported_extensions()) + ")"


def _settings():
    return QSettings("local", "Mesh Viewer")


# ---------------------------------------------------------------------------
# Window
# ---------------------------------------------------------------------------

class _TabScroll(QScrollArea):
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
        capsule.adjustSize()
        self.setWidget(capsule)
        self.setFixedHeight(capsule.sizeHint().height() + 10)   # + the thin scrollbar

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


class ViewerWindow(QMainWindow):
    def __init__(self, app_controller):
        super().__init__()
        self.ctl = app_controller
        self.path: Path | None = None
        self.scene: Scene | None = None
        self._job = None

        self.setUnifiedTitleAndToolBarOnMac(True)
        self.setAcceptDrops(True)
        self.resize(1400, 900)
        self.setWindowTitle("Mesh Viewer")

        # ---- 3D view (placeholder until a file is loaded) ---------------
        self.plotter = QtInteractor(self, auto_update=False)
        # 4× MSAA: smooth edges at much lower cost than 8× on Retina screens.
        self.plotter.enable_anti_aliasing("msaa", multi_samples=4)
        self.empty = QLabel("Drop a mesh or CAD file here\nor choose File ▸ Open…  (⌘O)")
        self.empty.setObjectName("EmptyState")
        self.empty.setAlignment(Qt.AlignCenter)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.empty)
        self.stack.addWidget(self.plotter)
        # CFD mode (CAD) — the Inflation page, and a bar under the view
        # with a pill to switch between the 3D model and that page.
        self.inflation_view = InflationView()
        self.stack.addWidget(self.inflation_view)
        self.plot_page = PlotPage()                    # Plots: the tab of a measurement
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
        self._plot_acts = {}                       # measurement id -> its tab (QAction)
        self._cfd_on = False
        self._page = "model"
        self._active_plot = None                   # whose cut is drawn in 3D
        self.a_page_model = QAction("3D model", self)
        self.a_page_model.setToolTip("3D Model")
        self.a_page_cfd = QAction("Inflation layers", self)
        self.a_page_cfd.setToolTip("Inflation Layers")
        for a in (self.a_page_model, self.a_page_cfd):
            a.setCheckable(True)
            group.addAction(a)
        self.a_page_model.setChecked(True)
        self.a_page_model.triggered.connect(lambda: self._show_page("model"))
        self.a_page_cfd.triggered.connect(lambda: self._show_page("cfd"))
        self._pages_scroll = _TabScroll()              # many plots: scroll sideways
        vb.addWidget(self._pages_scroll, 1)
        va.addWidget(self.view_bar)
        self.view_bar.setVisible(False)

        self.sidebar = Sidebar()
        self.sidebar.quality_requested.connect(self._retessellate)
        self.sidebar.renamed.connect(self._edited_changed)
        self.sidebar.info_panel.file_unit_changed.connect(self._set_file_unit)   # Info ▸ File unit
        self.sidebar.inflation_panel.mode_toggled.connect(self._cfd_mode)
        pp = self.sidebar.plots_panel                                      # Plots
        pp.added.connect(self._plot_added)
        pp.removed.connect(self._plot_removed)
        pp.renamed.connect(lambda i: self._rebuild_view_bar())
        pp.changed.connect(self._plot_changed)
        pp.show_plot.connect(lambda i: self._show_page(f"plot:{i}"))
        pp.cuts_changed.connect(self._show_cuts)               # an eye clicked
        rp = self.sidebar.results_panel
        pp.value_unit = lambda f: (lambda v: rp.shown_values(f, v), rp.unit_label(f))
        self.sidebar.section_actions["plots"].toggled.connect(lambda _on: self._show_cuts())
        self.sidebar.results_panel.units_changed.connect(     # a field's unit: the plots too
            lambda: self._active_plot is not None and self._refresh_plot(self._active_plot))
        self.sidebar.inflation_panel.changed.connect(self.inflation_view.set_result)
        self.sidebar.inflation_panel.wants_model.connect(self._show_model_page)
        self.inflation_view.section.set_panel(self.sidebar.inflation_panel)
        ep = self.sidebar.edit_panel                                       # Edit section
        ep.edit_requested.connect(self._apply_edit)
        ep.undo_requested.connect(lambda: self._edit_step(lambda s: s.undo_edit()))
        ep.reset_requested.connect(lambda: self._edit_step(lambda s: s.reset_edits()))
        ep.original_toggled.connect(lambda on: self.scene and self.scene.set_show_original(on))
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.sidebar)          # icon bar + sections + parts
        self.splitter.addWidget(self.view_area)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([414, 986])            # icon bar 44 + sections 370 (CFD on its card)
        self.splitter.setHandleWidth(1)
        self.splitter.setChildrenCollapsible(True)
        self.setCentralWidget(self.splitter)

        self._build_actions()
        self._build_toolbar()
        self._build_menus()
        self._set_loaded(False)
        self._sync_show()

        QApplication.styleHints().colorSchemeChanged.connect(self._theme_changed)

    # ---- actions / toolbar / menus ----------------------------------
    def _act(self, text, slot, shortcut=None, checkable=False):
        a = QAction(text, self)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        a.setCheckable(checkable)
        a.triggered.connect(slot)
        return a

    def _build_actions(self):
        self.a_open = self._act("Open…", self.ctl.open_dialog, QKeySequence.Open)
        self.a_close = self._act("Close Window", self.close, QKeySequence.Close)
        self.a_shot = self._act("Save Screenshot…", self.save_screenshot, "Ctrl+Shift+S")
        self.a_appearance = self._act("Appearance…", self.show_appearance, "Ctrl+,")
        self.a_sidebar = self._act("Sidebar", self.toggle_sidebar, "Ctrl+Alt+S", checkable=True)
        self.a_sidebar.setChecked(True)
        self.a_section = self._act("Section", self._toggle_section, "Ctrl+Alt+X", checkable=True)
        self.a_measure = self._act("Measure", self._toggle_measure, "Ctrl+Shift+M", checkable=True)
        self.a_deselect = self._act("Deselect", self._deselect, "Esc")
        # display units for measurements (lengths, areas, volumes)
        self.unit_group = QActionGroup(self)
        self.unit_group.setExclusive(True)
        self.a_units = []
        for key, text, tip in (("mm", "mm", "Millimetres"), ("cm", "cm", "Centimetres"),
                               ("m", "m", "Metres"), ("in", "in", "Inches"), ("ft", "ft", "Feet")):
            a = QAction(text, self)
            a.setCheckable(True)
            a.setData(key)
            a.setToolTip(tip)
            self.unit_group.addAction(a)
            self.a_units.append(a)
        self.unit_group.triggered.connect(self._unit_chosen)
        # where the old "no unit" button was: what unit are the file's numbers in?
        self.a_file_unit = self._act("File Unit…", self._edit_file_unit)
        self.a_file_unit.setIcon(icon("edit_unit"))
        self.a_fit = self._act("Fit", lambda: self.scene and self.scene.fit(), "Ctrl+0")
        # parallel projection is a toolbar toggle next to the views
        self.a_parallel = self._act("Perspective",          # on: perspective, off: parallel
                                    lambda on: self.scene and self.scene.set_parallel(not on),
                                    "Ctrl+5", checkable=True)
        # what is shown, as toolbar toggles (was the sidebar's Display
        # section). Edges: one pill; axes, grid, bounding box, origin: another.
        self.a_show = {}
        for key, text in (("mesh_edges", "Mesh Edges"), ("feature_edges", "Feature Edges"),
                          ("faces", "Faces"), ("axes", "Axes"), ("grid", "Grid"),
                          ("bbox", "Bounding Box"), ("origin", "Origin")):
            a = self._act(text, lambda on, k=key: self._show_toggled(k, on), checkable=True)
            a.setIcon(icon(key))
            self.a_show[key] = a
        # Export. (Edit lives in the sidebar.)
        self.a_export = self._act("Export…", self.export_model, "Ctrl+Shift+E")
        self.a_views = [
            self._act("Iso", lambda: self.scene and self.scene.view("iso"), "Ctrl+1"),
            self._act("X", lambda: self.scene and self.scene.view("x"), "Ctrl+2"),
            self._act("Y", lambda: self.scene and self.scene.view("y"), "Ctrl+3"),
            self._act("Z", lambda: self.scene and self.scene.view("z"), "Ctrl+4"),
        ]
        # Icons (drawn, follow light/dark). X / Y / Z stay as letters.
        for a, name in ((self.a_sidebar, "sidebar"), (self.a_fit, "fit"),
                        (self.a_views[0], "iso"), (self.a_section, "section"),
                        (self.a_shot, "camera"), (self.a_measure, "ruler"),
                        (self.a_appearance, "appearance"), (self.a_parallel, "parallel"),
                        (self.a_export, "export")):
            a.setIcon(icon(name))
        # hover: the name and the shortcut, nothing more
        names = {self.a_views[0]: "Isometric", self.a_shot: "Screenshot",
                 self.a_appearance: "Appearance", self.a_export: "Export",
                 self.a_fit: "Fit View"}
        for a in (self.a_sidebar, self.a_fit, *self.a_views, self.a_section, self.a_shot,
                  self.a_measure, self.a_appearance, self.a_parallel, self.a_export,
                  self.a_file_unit, *self.a_show.values()):
            name = names.get(a, a.text().rstrip("…"))
            keys = a.shortcut().toString(QKeySequence.NativeText)
            a.setToolTip(f"{name}  ({keys})" if keys else name)

    def _build_toolbar(self):
        tb = QToolBar("Toolbar")
        tb.setMovable(False)
        tb.setFloatable(False)
        tb.toggleViewAction().setVisible(False)
        # Groups of related buttons, each in one capsule (macOS 27 toolbar style).
        tb.addWidget(Capsule([self.a_sidebar]))
        s = self.a_show                                # what is shown
        self.view_capsule = Capsule([self.a_fit, *self.a_views, self.a_parallel])
        self.edges_capsule = Capsule([s["mesh_edges"], s["feature_edges"], s["faces"]])
        self.marks_capsule = Capsule([s["axes"], s["grid"], s["bbox"], s["origin"]])
        self._tb_slot = {c: tb.addWidget(c) for c in (self.view_capsule, self.edges_capsule,
                                                      self.marks_capsule)}
        tb.addWidget(Capsule([self.a_file_unit, *self.a_units]))   # file unit · shown unit
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(spacer)
        # Screenshot, top right. (Section and Measure live in the sidebar.)
        tb.addWidget(Capsule([self.a_export]))
        tb.addWidget(Capsule([self.a_appearance, self.a_shot]))
        self.addToolBar(tb)

    def _build_menus(self):
        m = self.menuBar().addMenu("File")
        m.addAction(self.ctl.about_action(m))     # shown in the app menu on macOS
        m.addAction(self.a_open)
        self.ctl.add_recent_menu(m)                       # Open Recent
        m.addSeparator()
        m.addAction(self.a_export)
        m.addAction(self.a_shot)
        m.addSeparator()
        m.addAction(self.a_close)
        v = self.menuBar().addMenu("View")
        v.addAction(self.a_sidebar)
        sections = v.addMenu("Sidebar Sections")          # same toggles as the icon bar
        for spec in SECTIONS:
            sections.addAction(self.sidebar.section_actions[spec.key])
        v.addAction(self.a_section)
        v.addAction(self.a_measure)
        v.addSeparator()
        show = v.addMenu("Show")                      # the toolbar toggles
        for k, a in self.a_show.items():
            if k == "axes":
                show.addSeparator()
            show.addAction(a)
        v.addSeparator()
        v.addAction(self.a_parallel)
        v.addAction(self.a_appearance)
        v.addAction(self.a_deselect)
        v.addSeparator()
        v.addAction(self.a_fit)
        for a in self.a_views:
            v.addAction(a)

    def _set_loaded(self, loaded):
        for a in [self.a_shot, self.a_fit, self.a_section, self.a_measure, *self.a_views,
                  *self.a_units, self.a_file_unit, *self.a_show.values()]:
            a.setEnabled(loaded)
        if loaded and self.scene is not None:
            self._fit_toolbar(self.scene.model)
        self.stack.setCurrentWidget(self.plotter if loaded else self.empty)

    def _fit_toolbar(self, model):
        """Only the buttons that mean something for this file: 2D files are always seen
        from above (no views, no perspective); drawings are lines only (no edges or
        faces toggles, no bounding box or origin)."""
        flat, drawing = model.dim == 2, model.file_type == "drawing"
        hide = set()
        if flat:
            hide |= {*self.a_views, self.a_parallel}
        if drawing:
            hide |= {self.a_show[k] for k in ("mesh_edges", "feature_edges", "faces",
                                               "bbox", "origin")}
        for a in (*self.a_views, self.a_parallel, *self.a_show.values()):
            a.setVisible(a not in hide)              # menus and shortcuts too
        for cap in (self.view_capsule, self.edges_capsule, self.marks_capsule):
            cap.show_only([b.defaultAction() for b in cap.buttons
                           if b.defaultAction() not in hide])
            self._tb_slot[cap].setVisible(cap.has_shown)   # a toolbar widget hides by its action

    # ---- loading --------------------------------------------------------
    @property
    def is_empty(self):
        return self.path is None

    def load(self, path: Path):
        self.path = Path(path)
        self.setWindowFilePath(str(self.path))      # native title + proxy icon
        self.setWindowTitle(f"{self.path.name}[*]")      # [*]: "edited" marker
        self.empty.setText(f"Opening {self.path.name}…")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        path = self.path
        # STEP opens at the mesh quality you used last time.
        saved = _settings().value("step_quality")        # None the first time
        quality = int(saved) if saved is not None else None

        def job():
            print(f"Reading {path} …")
            return load(path, quality=quality)
        self._job = run_job(job, self._loaded, self._failed)

    def _loaded(self, model):
        QApplication.restoreOverrideCursor()
        if not model.parts:
            return self._failed(RuntimeError(f"No {model.group_title.lower()} found in this file."))
        self.scene = Scene(self.plotter, model, dark=is_dark(), accent=accent())
        saved = memory.load(self.path)                   # as you left it
        memory.restore(self.scene, saved)
        self.sidebar.bind(self.scene)
        self.sidebar.plots_panel.file_stem = self.path.stem
        self._rebuild_view_bar()                         # a tab per measurement
        self.a_parallel.blockSignals(True)                  # show the scene's projection
        self.a_parallel.setChecked(not self.scene.state["parallel"])
        self.a_parallel.blockSignals(False)
        self._sync_show()
        # Menu opened just after VTK finishes handling the click (not inside it).
        self.scene.on_context = lambda names, clicked: QTimer.singleShot(
            0, lambda p=QCursor.pos(): self.sidebar.part_menu(names, clicked, p))
        self._sync_units()
        if not (saved or {}).get("file_unit"):
            self._ask_file_unit()                      # first time: what unit is it in?
        self.apply_appearance()
        # View ▸ Measure and the sidebar's Measure section stay in sync.
        self.sidebar.measure_section.toggled.connect(self._measure_section_toggled)
        # Toolbar "Section" button and the sidebar switch stay in sync.
        self.sidebar.section_panel.enable.toggled.connect(self._section_switched)
        self._section_switched(self.scene.section.enabled)
        self._set_loaded(True)
        ip = self.sidebar.inflation_panel                  # CFD mode as left
        page = getattr(self.scene, "inflation_page", None) or {}
        self.inflation_view.set_state(page)                # tab, flip side, zoom
        self.inflation_view.set_result(ip.result)
        self._cfd_mode(model.is_cad and ip.enabled, open_page=False)
        if model.is_cad and ip.enabled and page.get("page") == "cfd":
            self.a_page_cfd.setChecked(True)
            self._show_page("cfd")
        elif str(page.get("page", "")).startswith("plot:"):   # a measurement's tab
            self._show_page(page["page"])
        memory.restore_camera(self.scene, saved)
        self.ctl.add_recent(self.path)                   # File ▸ Open Recent
        self.plotter.render()

    def _failed(self, exc):
        QApplication.restoreOverrideCursor()
        name = self.path.name if self.path else "file"
        if isinstance(exc, MissingDependency):
            detail = (f"{exc}\n\nInstall it into the app's Python environment, e.g.:\n"
                      f"   .venv/bin/pip install {exc.package}\n"
                      f"(then rebuild with build_app.sh)")
        else:
            detail = str(exc) or exc.__class__.__name__
        box = QMessageBox(QMessageBox.Critical, "Mesh Viewer", f"Couldn't open “{name}”.",
                          QMessageBox.Ok, self)
        box.setInformativeText(detail)
        box.setWindowModality(Qt.WindowModal)   # a sheet on macOS
        box.open()
        self.path = None if self.scene is None else self.path
        self.empty.setText("Drop a mesh or CAD file here\nor choose File ▸ Open…  (⌘O)")

    # ---- mesh quality (STEP) ----------------------------------------
    def _retessellate(self, level):
        if not (self.scene and self.scene.can_retessellate):
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        fn = self.scene.model.retessellate
        self._pending_level = level
        self._job = run_job(lambda: fn(level), self._retessellated, self._retessellate_failed)

    def _retessellated(self, parts):
        level = self._pending_level
        QApplication.restoreOverrideCursor()
        self.scene.replace_parts(parts, level)
        self.sidebar.refresh_parts()
        self.sidebar.info_panel.model_changed()
        _settings().setValue("step_quality", level)

    def _retessellate_failed(self, exc):
        QApplication.restoreOverrideCursor()
        self.sidebar.quality_failed()
        QMessageBox.warning(self, "Mesh Viewer", f"Re-meshing failed:\n{exc}")

    # ---- misc -----------------------------------------------------------
    # ---- appearance --------------------------------------------------
    def show_appearance(self):
        self._appearance_dialog = AppearanceDialog(self, self.ctl)
        self._appearance_dialog.open()

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

    # --- CFD mode (CAD files) ---------------------------------------------
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

    # --- Plots: one tab per measurement under the 3D view -------------------------
    def _rebuild_view_bar(self):
        """The pill under the view: 3D model · Inflation layers (CFD mode) · each plot.
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
        acts = [self.a_page_model] + ([self.a_page_cfd] if self._cfd_on else []) + \
            [self._plot_acts[m["id"]] for m in ms]
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

    def _plot_changed(self, ident):
        self._active_plot = ident
        if self._page == f"plot:{ident}":
            self._refresh_plot(ident)
        else:
            self._show_cuts()

    def _show_cuts(self):
        """The cuts whose eye is open, drawn in 3D while Plots is in the sidebar."""
        if self.scene is None:
            return
        pp = self.sidebar.plots_panel
        on = self.sidebar.section_actions["plots"].isChecked()
        lines = [pp.results[m["id"]]["lines"] for m in self.scene.plots
                 if on and m.get("show", True) and pp.results.get(m["id"])
                 and pp.results[m["id"]].get("lines") is not None]
        self.scene.plot_cut.show(lines, self.scene.accent)

    def _refresh_plot(self, ident):
        pp = self.sidebar.plots_panel
        m, r = pp.measurement(ident), pp.results.get(ident)
        if m is None or r is None:
            return
        s, unit = self.scene.measure.unit_scale()
        rp = self.sidebar.results_panel                # a field in its unit (Results)
        self.plot_page.show(m, r, self.scene.colors, s, unit,
                            value_unit=(lambda v, f=r["value"]: rp.shown_values(f, v),
                                        rp.unit_label(r["value"])))
        self._show_cuts()

    def _sync_units(self):
        """Select the shown unit (the file's own unless another was picked)."""
        unit = self.scene.measure.display_unit or self.scene.model.units
        for a in self.a_units:
            a.setChecked(a.data() == unit)

    def _ask_file_unit(self):
        """First time this file is opened: which unit are its numbers in?"""
        m = self.scene.model
        unit = default_unit(m)
        self._set_file_unit(unit)                      # works meanwhile; the answer replaces it
        self._open_unit_sheet(unit)

    def _edit_file_unit(self):
        """Toolbar ✎: change the file's unit (the same sheet as on the first open)."""
        if self.scene is not None:
            self._open_unit_sheet(self.scene.model.units or default_unit(self.scene.model))

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
            self.sidebar.show_selection([])

    def toggle_sidebar(self, on):
        self.sidebar.setVisible(on)

    def save_screenshot(self):
        """choose resolution + background first (a sheet), then where to save."""
        if not self.scene:
            return
        w, h = self.plotter.window_size
        self._shot_dialog = ScreenshotDialog(self, w, h)
        self._shot_dialog.accepted.connect(                  # after the sheet has gone
            lambda: QTimer.singleShot(300, self._save_screenshot_to_file))
        self._shot_dialog.open()

    def _save_screenshot_to_file(self):
        d = self._shot_dialog
        default = str(self.path.with_suffix(".png")) if self.path else "screenshot.png"
        fn, _ = QFileDialog.getSaveFileName(self, "Save Screenshot", default, "PNG image (*.png)")
        if fn:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                self.scene.screenshot(fn, scale=d.scale, background=d.background)
            finally:
                QApplication.restoreOverrideCursor()

    # ---- Edit section --------
    def _apply_edit(self, r, t, label):
        if self.scene and self.scene.apply_edit(r, t, label):
            self._edited_changed()

    def _edit_step(self, fn):
        if self.scene:
            fn(self.scene)
            self._edited_changed()

    def _edited_changed(self):
        # only edits count as unsaved — names, colours, the view are remembered
        edited = bool(self.scene and self.scene.model.edited)
        self.setWindowModified(edited)                  # dot in the close button (macOS)
        self.sidebar.edit_panel.refresh()
        self.sidebar.info_panel.model_changed()        # new bounds
        self.sidebar.cfd_panel.model_changed()         # flow vectors, length
        self.sidebar.inflation_panel.model_changed()   # walls, arrows, auto length
        self.sidebar.results_panel.model_changed()     # results follow the edits
        self.sidebar.plots_panel.model_changed()       # cuts of the moved model

    def _unit_chosen(self, a):
        if self.scene:
            self.scene.measure.set_display_unit(a.data())
            self.sidebar.info_panel.refresh()           # Info in the new unit
            self.sidebar.cfd_panel.model_changed()      # mesh length in metres
            self.sidebar.inflation_panel.model_changed()   # auto length in metres
            self.sidebar.plots_panel.model_changed()       # plots in the new unit

    # --- Export ----------------------------------------------------------
    def export_model(self):
        if not self.scene:
            return
        sc = self.scene
        keys = available_formats(sc.model.kind, exact_cad=not sc.model.editable)
        ip = self.sidebar.inflation_panel
        cfd = ({"on": ip.enabled and bool((ip.result or {}).get("ok"))}   # CAD files
               if sc.model.is_cad else None)
        self._export_dialog = ExportDialog(
            self, keys, has_hidden=not all(sc.visible.values()),
            has_volume=sc.section.has_volume, edited=sc.model.edited,
            renamed=sc.renamed, cfd=cfd)
        # Ask where to save once the sheet has gone: opened while it is still closing,
        # macOS shows the save panel as a separate window (on another desktop in full
        # screen) instead of attached to this one.
        self._export_dialog.accepted.connect(lambda: QTimer.singleShot(300, self._export_to_file))
        self._export_dialog.open()

    def _export_to_file(self):
        sc, d = self.scene, self._export_dialog
        if d.what == "cfd":                              # CFD settings
            return self._export_cfd(d.cfd_fmt)
        fmt = d.fmt
        label, ext = EXPORT_FORMATS[fmt]
        base = self.path.name.split(".")[0] + ("_edited" if sc.has_changes else "")
        # one-dot pattern: macOS file types can't be ".lb8.ugrid" (the panel then
        # falls back to a detached window); the full suffix is put back below
        pattern = "*." + ext.rsplit(".", 1)[-1]
        fn, _ = QFileDialog.getSaveFileName(self, "Export", str(self.path.with_name(base + ext)),
                                            f"{label} ({pattern})")
        if not fn:
            return
        if not fn.lower().endswith(ext):
            fn = fn[: -len(".ugrid")] + ext if fn.lower().endswith(".ugrid") else fn + ext
        names = [n for n in sc.names if sc.visible[n] or not d.visible_only.isChecked()]
        parts = {n: sc.model.parts[n] for n in names}
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            volume = sc.section.volume_grid() if fmt in ("vtu", "ugrid") else None
            write_export(fmt, fn, parts, volume=volume,
                         colors={n: sc.colors[n] for n in names})   # OBJ / PLY
        except Exception as exc:                        # shown, not a crash
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "Export", f"Could not export:\n{exc}")
            return
        QApplication.restoreOverrideCursor()
        if sys.platform == "darwin":                    # show the new file in Finder
            subprocess.run(["open", "-R", fn], check=False)

    def _export_cfd(self, kind):
        """the inflation layers for a mesher, or a CSV of everything."""
        label, ext = CFD_FORMATS[kind]
        base = self.path.name.split(".")[0] + CFD_SUFFIX[kind]
        fn, _ = QFileDialog.getSaveFileName(self, "Export CFD settings",
                                            str(self.path.with_name(base + ext)),
                                            f"{label.split(' — ')[0]} (*{ext})")
        if not fn:
            return
        if not fn.lower().endswith(ext):
            fn += ext
        try:
            write_cfd(kind, fn, self.sidebar.inflation_panel.export_info(self.path.name))
        except Exception as exc:                        # shown, not a crash
            QMessageBox.warning(self, "Export", f"Could not export:\n{exc}")
            return
        if sys.platform == "darwin":
            subprocess.run(["open", "-R", fn], check=False)

    def _toggle_measure(self, on):
        if self.scene:
            if on and not self.a_sidebar.isChecked():
                self.a_sidebar.trigger()                 # results live in the sidebar
            self.sidebar.set_measuring(on)

    def _measure_section_toggled(self, on):
        self.a_measure.blockSignals(True)
        self.a_measure.setChecked(on)
        self.a_measure.blockSignals(False)

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

    def closeEvent(self, e):
        # rotations / mirrors only live in memory until exported
        if self.scene is not None and self.scene.model.edited:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Warning)
            box.setText(f"Close {self.path.name} without exporting your edits?")
            box.setInformativeText("Moves, rotations and mirrors are only kept if you export "
                                   "the file. (Names, colours and the view are remembered.)")
            box.setStandardButtons(QMessageBox.Discard | QMessageBox.Cancel)
            box.setDefaultButton(QMessageBox.Cancel)
            if box.exec() != QMessageBox.Discard:
                e.ignore()
                return
        self.remember_view()
        self.plotter.close()
        self.ctl.forget(self)
        super().closeEvent(e)

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
