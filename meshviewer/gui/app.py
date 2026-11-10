"""Application: one process, one window per file.

macOS sends double-clicked / dropped-on-Dock files to the running app as
FileOpen events, so a second file opens instantly in a new window instead of
starting Python + VTK again. The app keeps running with no windows (like any
Mac app); ⌘Q quits.
"""
from __future__ import annotations

from pathlib import Path
import sys

from PySide6.QtCore import QEvent, QPoint, Qt, QTimer
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWidgets import QApplication, QFileDialog, QMenuBar
import shiboken6

from meshviewer.gui.dialogs.about import AboutDialog
from meshviewer.gui.macos import join_active_space
from meshviewer.gui.store import settings
from meshviewer.gui.style import stylesheet
from meshviewer.gui.welcome import add_sample_menu
from meshviewer.gui.window import FILE_FILTER, ViewerWindow
from meshviewer.render.style import AXIS_FONT_DEFAULT

ICON = Path(__file__).resolve().parents[2] / "resources" / "mesh_icon.icns"


def _axis_font(v) -> int:
    """Points; also reads the old Small / Medium / Large setting (v2.1.11–2.3.10)."""
    v = {"small": 16, "medium": 20, "large": 24}.get(str(v), v)
    try:
        return max(10, min(28, int(v)))
    except (TypeError, ValueError):
        return AXIS_FONT_DEFAULT


def _pref_quality(v):
    """Settings ▸ CAD mesh quality: "last" or a level number."""
    try:
        return int(v)
    except (TypeError, ValueError):
        return "last"


def _old_axes_setting(st) -> str:
    """Display ▸ Axes from the two switches older versions saved."""
    grid = st.value("appearance/grid_lines", True, type=bool)
    axes = st.value("appearance/axis_lines", True, type=bool)
    return {(True, True): "both", (True, False): "grid", (False, True): "axes"}.get(
        (grid, axes), "axes")


class MeshViewerApp(QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        self.setApplicationName("Mesh Viewer")
        self.setApplicationDisplayName("Mesh Viewer")
        self.setOrganizationName("local")
        if ICON.exists():                       # only matters when run from source
            self.setWindowIcon(QIcon(str(ICON)))
        # appearance (theme + 3D background), remembered between launches
        st = settings()
        self.appearance = {
            "theme": st.value("appearance/theme", "system"),
            "bg": st.value("appearance/bg", "default"),
            "bg_color": st.value("appearance/bg_color", "#2B2B2E"),
            "bg_image": st.value("appearance/bg_image", ""),
            "density": st.value("appearance/density", "compact"),     # parts list rows
            "axis_font": _axis_font(st.value("appearance/axis_font", AXIS_FONT_DEFAULT)),
            # edge lines
            "edge_width": st.value("appearance/edge_width", "thin"),
            "hide_edges_moving": st.value("appearance/hide_edges_moving", True, type=bool),
            # light and shadow on the model
            "shading": st.value("appearance/shading", True, type=bool),
            # Display ▸ Axes (off / axes / grid / both) replaces the Grid switch
            # and Appearance's Grid lines / Axis lines switches
            "axes": st.value("appearance/axes", _old_axes_setting(st)),
        }
        # Settings ▸ General / Units
        self.prefs = {
            "cad_quality": _pref_quality(st.value("prefs/cad_quality", "last")),
            "shown_unit": st.value("prefs/shown_unit", "file"),   # "file": the file's own
            "unit_mesh": st.value("prefs/unit_mesh", "m"),         # files that don't say
            "unit_cad": st.value("prefs/unit_cad", "mm"),
            "ask_unit": st.value("prefs/ask_unit", True, type=bool),
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
            self.add_recent_menu(m)
            add_sample_menu(m, self.open_path)
            for a in self.app_menu_actions():          # the app menu: only here, so once
                m.addAction(a)
        self.aboutToQuit.connect(self._remember_all)

    # --- File ▸ Open Recent ---------------------------------------------
    RECENT_MAX = 12

    def recent_files(self):
        st = settings()
        files = st.value("recent", []) or []
        files = [files] if isinstance(files, str) else list(files)
        return [f for f in files if Path(f).exists()]

    def add_recent(self, path):
        p = str(Path(path).resolve())
        files = [p] + [f for f in self.recent_files() if f != p]
        settings().setValue("recent", files[: self.RECENT_MAX])

    def add_recent_menu(self, menu):
        sub = menu.addMenu("Open Recent")
        sub.aboutToShow.connect(lambda: self._fill_recent(sub))
        self._fill_recent(sub)                             # so it isn't empty before
        return sub

    def _fill_recent(self, sub):
        sub.clear()
        files = self.recent_files()
        names = [Path(f).name for f in files]
        for f, name in zip(files, names):
            text = name if names.count(name) == 1 else f"{name} — {Path(f).parent.name}"
            a = sub.addAction(text)
            a.setToolTip(f)
            a.triggered.connect(lambda _=False, f=f: self.open_path(Path(f)))
        if files:
            sub.addSeparator()
        clear = sub.addAction("Clear Menu")
        clear.setEnabled(bool(files))
        clear.triggered.connect(lambda: settings().setValue("recent", []))

    def _remember_all(self):
        for w in list(self.windows):
            w.remember_view()

    # --- the app menu: About, Check for Updates…, Settings… -----------------
    def app_menu_actions(self):
        """Made once for the whole app. On macOS they live in the app menu (left of File),
        which every window shares: they are added to the no-window menu bar only — added
        to each window's menu bar too, macOS showed them once per menu bar."""
        if getattr(self, "_app_actions", None) is None:
            about = QAction("About Mesh Viewer", self)
            about.setMenuRole(QAction.AboutRole)
            about.triggered.connect(self.show_about)
            updates = QAction("Check for Updates…", self)
            updates.setMenuRole(QAction.ApplicationSpecificRole)
            updates.triggered.connect(lambda: (self.show_about(), self._about.check_updates()))
            settings = QAction("Settings…", self)          # (PreferencesRole would rename it
            settings.setMenuRole(QAction.ApplicationSpecificRole)   # "Preferences…")
            settings.setShortcut(QKeySequence("Ctrl+,"))
            settings.triggered.connect(self.show_settings)
            self._app_actions = [about, updates, settings]
        return self._app_actions

    def _front(self):
        """The file window in front (None with no window open)."""
        win = self.activeWindow()
        while win is not None and not isinstance(win, ViewerWindow):
            win = win.parentWidget()
        return win or next((w for w in reversed(self.windows) if w.isVisible()), None)

    def _present(self, w):
        """Show one of the app's own windows where you are, also over a full-screen
        window. A window of its own went to the desktop Space, so macOS slid the full
        screen away: it belongs to the front window now (as a dialog of it), and macOS
        is asked to keep it on the active Space."""
        front = self._front()
        if front is not None and w.parentWidget() is not front:
            geometry = w.geometry() if w.isVisible() else None
            w.setParent(front, Qt.Dialog)              # (setParent hides it)
            if geometry is not None:
                w.setGeometry(geometry)
        join_active_space(w)                           # before it shows…
        w.show()
        w.raise_()
        w.activateWindow()
        QTimer.singleShot(0, lambda: join_active_space(w))   # …and after (Qt may reset it)

    def _alive(self, name):
        """The window kept in self.<name>, unless it went with its front window."""
        w = getattr(self, name, None)
        return w if w is not None and shiboken6.isValid(w) else None

    def show_about(self):
        if self._alive("_about") is None:
            self._about = AboutDialog()
        self._present(self._about)

    # ---- Settings (⌘,) -------------------------------------------------
    def show_settings(self):
        if self._alive("_settings") is None:
            from meshviewer.gui.dialogs.settings import SettingsWindow
            self._settings = SettingsWindow(self)
        self._present(self._settings)

    def set_pref(self, **changes):
        self.prefs.update(changes)
        st = settings()
        for k, v in changes.items():
            st.setValue(f"prefs/{k}", v)

    def bring_all_to_front(self):
        for w in self.windows:
            if w.isVisible():
                w.raise_()
        active = self.activeWindow()
        if active is not None:
            active.raise_()

    # ---- appearance ---------------------------------------------------
    def set_appearance(self, **changes):
        self.appearance.update(changes)
        st = settings()
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
