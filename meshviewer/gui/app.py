"""Application: one process, one window per file.

macOS sends double-clicked / dropped-on-Dock files to the running app as
FileOpen events, so a second file opens instantly in a new window instead of
starting Python + VTK again. The app keeps running with no windows (like any
Mac app); ⌘Q quits.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QEvent, QPoint, QSettings, Qt, QTimer
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import QApplication, QFileDialog, QMenuBar

from .about_dialog import AboutDialog
from .scene import AXIS_FONT_DEFAULT
from .style import stylesheet
from .window import FILE_FILTER, ViewerWindow

ICON = Path(__file__).resolve().parents[2] / "resources" / "mesh_icon.icns"


def _axis_font(v) -> int:
    """Points; also reads the old Small / Medium / Large setting (v2.11–2.13)."""
    v = {"small": 16, "medium": 20, "large": 24}.get(str(v), v)
    try:
        return max(10, min(28, int(v)))
    except (TypeError, ValueError):
        return AXIS_FONT_DEFAULT


class MeshViewerApp(QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        self.setApplicationName("Mesh Viewer")
        self.setApplicationDisplayName("Mesh Viewer")
        self.setOrganizationName("local")
        if ICON.exists():                       # only matters when run from source
            self.setWindowIcon(QIcon(str(ICON)))
        # appearance (theme + 3D background), remembered between launches
        st = QSettings("local", "Mesh Viewer")
        self.appearance = {
            "theme": st.value("appearance/theme", "system"),
            "bg": st.value("appearance/bg", "default"),
            "bg_color": st.value("appearance/bg_color", "#2B2B2E"),
            "bg_image": st.value("appearance/bg_image", ""),
            "density": st.value("appearance/density", "compact"),     # parts list rows
            "axis_font": _axis_font(st.value("appearance/axis_font", AXIS_FONT_DEFAULT)),
            # NEW (v2.14): edge lines
            "edge_width": st.value("appearance/edge_width", "thin"),
            "hide_edges_moving": st.value("appearance/hide_edges_moving", True, type=bool),
            "grid_lines": st.value("appearance/grid_lines", True, type=bool),   # NEW (v2.15)
            "axis_lines": st.value("appearance/axis_lines", True, type=bool),   # NEW (v2.16)
        }
        self._apply_theme()
        self.setStyleSheet(stylesheet())
        self.styleHints().colorSchemeChanged.connect(lambda *_: self.setStyleSheet(stylesheet()))
        self.setQuitOnLastWindowClosed(sys.platform != "darwin")
        self.windows: list[ViewerWindow] = []
        self._last_dir = str(Path.home())
        # Clicking the Dock icon with no window open -> show an empty window.
        self.applicationStateChanged.connect(self._state_changed)
        # macOS: menu bar used when no window is open, so ⌘O still works.
        if sys.platform == "darwin":
            self._global_menu = QMenuBar(None)
            m = self._global_menu.addMenu("File")
            a = m.addAction("Open…")
            a.setShortcut(QKeySequence.Open)
            a.triggered.connect(self.open_dialog)
            m.addAction(self.about_action(m))                  # NEW (v2.15)

    # ---- NEW (v2.15): About Mesh Viewer ---------------------------------------------
    def about_action(self, parent):
        """'About Mesh Viewer' — macOS moves it to the app menu (left of File)."""
        a = QAction("About Mesh Viewer", parent)
        a.setMenuRole(QAction.AboutRole)
        a.triggered.connect(self.show_about)
        return a

    def show_about(self):
        if getattr(self, "_about", None) is None:
            self._about = AboutDialog()
        self._about.show()
        self._about.raise_()
        self._about.activateWindow()

    # ---- appearance ---------------------------------------------------
    def set_appearance(self, **changes):
        self.appearance.update(changes)
        st = QSettings("local", "Mesh Viewer")
        for k, v in changes.items():
            st.setValue(f"appearance/{k}", v)
        if "theme" in changes:
            self._apply_theme()
            self.setStyleSheet(stylesheet())
        for w in self.windows:
            w.apply_appearance()

    def _apply_theme(self):
        """System / Light / Dark for the whole app (Qt 6.8+ can force it)."""
        scheme = {"light": Qt.ColorScheme.Light, "dark": Qt.ColorScheme.Dark}.get(
            self.appearance["theme"], Qt.ColorScheme.Unknown)
        try:
            self.styleHints().setColorScheme(scheme)
        except AttributeError:                       # older Qt: follows the system only
            pass

    def background(self):
        a = self.appearance
        if a["bg"] == "color":
            return "color", a["bg_color"]
        if a["bg"] == "image" and a["bg_image"] and Path(a["bg_image"]).exists():
            return "image", a["bg_image"]
        return "default", None

    # ---- macOS file-open events ----------------------------------------
    def event(self, e):
        if e.type() == QEvent.FileOpen:
            self.open_path(Path(e.file()))
            return True
        return super().event(e)

    def _state_changed(self, state):
        if state == Qt.ApplicationActive:
            QTimer.singleShot(400, self.ensure_window)

    # ---- windows -----------------------------------------------------------
    def ensure_window(self):
        if not any(w.isVisible() for w in self.windows):
            self.new_window()

    def new_window(self) -> ViewerWindow:
        w = ViewerWindow(self)
        if self.windows:                          # cascade like Finder / Preview
            w.move(self.windows[-1].pos() + QPoint(26, 26))
        self.windows.append(w)
        w.show()
        w.raise_()
        w.activateWindow()
        return w

    def forget(self, w):
        if w in self.windows:
            self.windows.remove(w)

    def open_path(self, path: Path, prefer: ViewerWindow | None = None):
        path = Path(path).expanduser()
        # Already open? Just bring it forward.
        for w in self.windows:
            if w.path and w.path.resolve() == path.resolve():
                w.raise_()
                w.activateWindow()
                return w
        # Reuse an empty window if there is one, otherwise open a new one.
        target = prefer if (prefer and prefer.is_empty) else next(
            (w for w in self.windows if w.is_empty and w.isVisible()), None)
        target = target or self.new_window()
        self._last_dir = str(path.parent)
        target.load(path)
        target.raise_()
        target.activateWindow()
        return target

    def open_dialog(self):
        files, _ = QFileDialog.getOpenFileNames(None, "Open", self._last_dir, FILE_FILTER)
        for f in files:
            self.open_path(Path(f))


def run(argv=None):
    argv = sys.argv if argv is None else argv
    app = MeshViewerApp(argv)
    for arg in argv[1:]:
        if not arg.startswith("-psn"):            # old Finder process-serial arg
            app.open_path(Path(arg))
    # Files double-clicked in Finder arrive as FileOpen events just after
    # start-up; only show an empty window if none did.
    QTimer.singleShot(500, app.ensure_window)
    return app.exec()
