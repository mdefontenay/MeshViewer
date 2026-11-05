"""One document window: toolbar + side panel + 3D view."""
from __future__ import annotations

import traceback
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QSettings, Qt, QThreadPool, QTimer, Signal
from PySide6.QtGui import QAction, QActionGroup, QCursor, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QLabel, QMainWindow, QMessageBox, QScrollArea, QSplitter, QStackedWidget,
    QSizePolicy, QToolBar, QWidget,
)
from pyvistaqt import QtInteractor

from ..formats import load, supported_extensions
from ..model import MissingDependency
from .icons import icon
from .scene import Scene
from .sidebar import Sidebar
from .style import accent, is_dark
from .appearance_dialog import AppearanceDialog
from .screenshot_dialog import ScreenshotDialog
from .widgets import Capsule

FILE_FILTER = "Meshes and CAD (" + " ".join(f"*{e}" for e in supported_extensions()) + ")"


# ---------------------------------------------------------------------------
# Background loading, so the window stays responsive on big files
# ---------------------------------------------------------------------------

class _JobSignals(QObject):
    done = Signal(object)          # result
    failed = Signal(object)        # Exception


class _Job(QRunnable):
    """Runs fn() on a worker thread; result/exception come back as signals."""

    def __init__(self, fn):
        super().__init__()
        self.fn = fn
        self.signals = _JobSignals()

    def run(self):
        try:
            self.signals.done.emit(self.fn())
        except Exception as exc:       # reported in the window
            traceback.print_exc()
            self.signals.failed.emit(exc)


def _settings():
    return QSettings("local", "Mesh Viewer")


# ---------------------------------------------------------------------------
# Window
# ---------------------------------------------------------------------------

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

        self.sidebar = Sidebar()
        self.sidebar.quality_requested.connect(self._retessellate)
        self.splitter = QSplitter(Qt.Horizontal)
        # Scrolls only if the window is too short for everything.
        self.side_scroll = QScrollArea()
        self.side_scroll.setObjectName("SideScroll")
        self.side_scroll.setWidget(self.sidebar)
        self.side_scroll.setWidgetResizable(True)
        self.side_scroll.setFrameShape(QScrollArea.NoFrame)
        self.side_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.side_scroll.setMinimumWidth(self.sidebar.minimumWidth())
        self.splitter.addWidget(self.side_scroll)
        self.splitter.addWidget(self.stack)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([300, 1100])
        self.splitter.setHandleWidth(1)
        self.splitter.setChildrenCollapsible(True)
        self.setCentralWidget(self.splitter)

        self._build_actions()
        self._build_toolbar()
        self._build_menus()
        self._set_loaded(False)

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
        for key, text, tip in ((None, "", "No units — show the file's numbers as they are"),
                               ("mm", "mm", "Millimetres"), ("cm", "cm", "Centimetres"),
                               ("m", "m", "Metres"), ("in", "in", "Inches"), ("ft", "ft", "Feet")):
            a = QAction(text, self)
            a.setCheckable(True)
            a.setData(key)
            a.setToolTip(tip)
            if key is None:
                a.setIcon(icon("nounit"))
            self.unit_group.addAction(a)
            self.a_units.append(a)
        self.unit_group.triggered.connect(
            lambda a: self.scene and self.scene.measure.set_display_unit(a.data()))
        self.a_fit = self._act("Fit", lambda: self.scene and self.scene.fit(), "Ctrl+0")
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
                        (self.a_appearance, "appearance")):
            a.setIcon(icon(name))
        tips = {self.a_sidebar: "Show or hide the sidebar", self.a_fit: "Fit the model in view",
                self.a_views[0]: "Isometric view", self.a_views[1]: "Look along X",
                self.a_views[2]: "Look along Y", self.a_views[3]: "Look along Z",
                self.a_section: "Cross-section", self.a_shot: "Save a screenshot",
                self.a_measure: "Measure distances, areas and volumes",
                self.a_appearance: "Theme and 3D background"}
        for a, tip in tips.items():
            a.setToolTip(f"{tip}  ({a.shortcut().toString(QKeySequence.NativeText)})")

    def _build_toolbar(self):
        tb = QToolBar("Toolbar")
        tb.setMovable(False)
        tb.setFloatable(False)
        tb.toggleViewAction().setVisible(False)
        # Groups of related buttons, each in one capsule (macOS 27 toolbar style).
        tb.addWidget(Capsule([self.a_sidebar]))
        tb.addWidget(Capsule([self.a_fit, *self.a_views]))
        tb.addWidget(Capsule(self.a_units))            # measurement units
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(spacer)
        # Screenshot, top right. (Section and Measure live in the sidebar.)
        tb.addWidget(Capsule([self.a_appearance, self.a_shot]))
        self.addToolBar(tb)

    def _build_menus(self):
        m = self.menuBar().addMenu("File")
        m.addAction(self.ctl.about_action(m))     # NEW (v2.15): shown in the app menu on macOS
        m.addAction(self.a_open)
        m.addSeparator()
        m.addAction(self.a_shot)
        m.addSeparator()
        m.addAction(self.a_close)
        v = self.menuBar().addMenu("View")
        v.addAction(self.a_sidebar)
        v.addAction(self.a_section)
        v.addAction(self.a_measure)
        v.addSeparator()
        v.addAction(self.a_appearance)
        v.addAction(self.a_deselect)
        v.addSeparator()
        v.addAction(self.a_fit)
        for a in self.a_views:
            v.addAction(a)

    def _set_loaded(self, loaded):
        for a in [self.a_shot, self.a_fit, self.a_section, self.a_measure, *self.a_views,
                  *self.a_units]:
            a.setEnabled(loaded)
        self.stack.setCurrentWidget(self.plotter if loaded else self.empty)

    # ---- loading --------------------------------------------------------
    @property
    def is_empty(self):
        return self.path is None

    def load(self, path: Path):
        self.path = Path(path)
        self.setWindowFilePath(str(self.path))      # native title + proxy icon
        self.setWindowTitle(self.path.name)
        self.empty.setText(f"Opening {self.path.name}…")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        path = self.path
        # STEP opens at the mesh quality you used last time.
        saved = _settings().value("step_quality")        # None the first time
        quality = int(saved) if saved is not None else None

        def job():
            print(f"Reading {path} …")
            return load(path, quality=quality)
        self._job = _Job(job)
        self._job.signals.done.connect(self._loaded)
        self._job.signals.failed.connect(self._failed)
        QThreadPool.globalInstance().start(self._job)

    def _loaded(self, model):
        QApplication.restoreOverrideCursor()
        if not model.parts:
            return self._failed(RuntimeError(f"No {model.group_title.lower()} found in this file."))
        self.scene = Scene(self.plotter, model, dark=is_dark(), accent=accent())
        self.sidebar.bind(self.scene)
        # Menu opened just after VTK finishes handling the click (not inside it).
        self.scene.on_context = lambda names, clicked: QTimer.singleShot(
            0, lambda p=QCursor.pos(): self.sidebar.part_menu(names, clicked, p))
        self._sync_units()
        self.apply_appearance()
        # View ▸ Measure and the sidebar's Measure section stay in sync.
        self.sidebar.measure_section.toggled.connect(self._measure_section_toggled)
        # Toolbar "Section" button and the sidebar switch stay in sync.
        self.sidebar.section_panel.enable.toggled.connect(self._section_switched)
        self._set_loaded(True)
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
        self._job = _Job(lambda: fn(level))
        # Bound methods (not lambdas) so the result is handled on the UI thread.
        self._job.signals.done.connect(self._retessellated)
        self._job.signals.failed.connect(self._retessellate_failed)
        QThreadPool.globalInstance().start(self._job)

    def _retessellated(self, parts):
        level = self._pending_level
        QApplication.restoreOverrideCursor()
        self.scene.replace_parts(parts, level)
        self.sidebar.refresh_parts()
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
        if self.scene:
            a = self.ctl.appearance
            self.scene.set_axis_font(a["axis_font"], rebuild=False)
            self.scene.set_edge_options(a["edge_width"], a["hide_edges_moving"], render=False)
            self.scene.set_grid_lines(a["grid_lines"], rebuild=False)       # NEW (v2.15)
            self.scene.set_axis_lines(a["axis_lines"], rebuild=False)       # NEW (v2.16)
            self.scene.set_background(*self.ctl.background())        # rebuilds grid + axes

    def _sync_units(self):
        """Select the file's unit (mm for STEP/IGES), or 'no units' for files without."""
        unit = self.scene.measure.display_unit
        for a in self.a_units:
            a.setChecked(a.data() == unit)

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
        self.side_scroll.setVisible(on)

    def save_screenshot(self):
        """choose resolution + background first (a sheet), then where to save."""
        if not self.scene:
            return
        w, h = self.plotter.window_size
        self._shot_dialog = ScreenshotDialog(self, w, h)
        self._shot_dialog.accepted.connect(self._save_screenshot_to_file)
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
        self.plotter.close()
        self.ctl.forget(self)
        super().closeEvent(e)
