"""Tiny headless test harness (no pytest needed): check(), open_file(), run().

    python tests/test_sidebar.py        one test file, in its own app
    python tests/run_all.py             all of them in one app (under xvfb-run on Linux
                                        without a display); --isolated: one process each

Shared by every file in run_all.py: the app, its imports and VTK's first window. Each
file still starts clean: its own scratch settings file, the app's settings as at
launch, no window left open (`fresh_start`).
"""
from __future__ import annotations

import copy
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

RESULTS = []


def check(ok, msg):
    RESULTS.append((bool(ok), msg))
    print(("PASS " if ok else "FAIL ") + msg, flush=True)


def wait(app, cond, timeout=60):
    t = time.time()
    while not cond():
        app.processEvents()
        if time.time() - t > timeout:
            raise TimeoutError("waited too long")
        time.sleep(0.005)


def open_file(app, path, size=(1400, 900)):
    w = app.open_path(Path(path))
    wait(app, lambda: w.scene is not None)
    w.resize(*size)
    w.show()
    for _ in range(5):
        app.processEvents()
    return w


class ContourTool:
    """The Contours tool and its active contour's fold-out as one object: the checks
    written for the single Results tool read on (field, units, range…)."""

    def __init__(self, panel):
        self.__dict__["panel"] = panel

    @property
    def ed(self):
        return self.panel.editors[self.panel.active][1]

    @property
    def log(self):
        return self.ed.c["log"]

    @property
    def shown(self):
        return self.ed.c["show"]

    def _update(self):
        self.ed.commit()
        self.panel._changed()

    def __getattr__(self, k):
        ed = self.ed
        return getattr(ed, k) if hasattr(ed, k) else getattr(self.panel, k)


SHARED = {}                  # run_all.py: {"app": the app every test file uses}


def _scratch_settings():
    """Settings in a new scratch file: what the app remembers for you is untouched."""
    os.environ["MESHVIEWER_SETTINGS"] = os.path.join(tempfile.mkdtemp(), "settings.ini")


def _uncaught(kind, exc, tb):
    """An error raised inside the app (a Qt slot, a timer) — printed and left running by
    Qt — fails the test instead of passing unseen."""
    import traceback
    traceback.print_exception(kind, exc, tb)
    check(False, f"no error inside the app ({kind.__name__}: {exc})")


def make_app():
    sys.excepthook = _uncaught
    _scratch_settings()
    from PySide6.QtCore import QEvent
    from meshviewer.gui.app import MeshViewerApp

    class TestApp(MeshViewerApp):
        def event(self, e):
            # macOS hands the script's own path to the app as a file to open (a window
            # and an error sheet nobody asked for): the tests open theirs with open_file()
            return True if e.type() == QEvent.FileOpen else super().event(e)

    app = TestApp(["test"])
    app.setQuitOnLastWindowClosed(False)
    app._launch_state = copy.deepcopy((app.appearance, app.prefs, app._last_dir))
    return app


def close_all(app):
    """Every window and dialog closed (edits or not), their widgets deleted."""
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication, QMenuBar
    from meshviewer.gui.window import ViewerWindow
    # sheets and dialogs first, hidden (not rejected: that would act on their window)
    for top in QApplication.topLevelWidgets():
        if (top.isWindow() and top.isVisible() and not isinstance(top, (QMenuBar, ViewerWindow))):
            top.hide()
    for w in list(app.windows):
        w._close_ok = True
        w.close()
        if w in app.windows:                      # something kept it open
            w.plotter.close()
            app.forget(w)
        w.deleteLater()
    app._settings = app._about = None
    for _ in range(3):
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.DeferredDelete)


def fresh_start(app):
    """Before the next test file in a shared app: no window, a new scratch settings
    file, the app's settings as at launch."""
    close_all(app)
    _scratch_settings()
    appearance, prefs, last_dir = copy.deepcopy(app._launch_state)
    theme = app.appearance.get("theme")
    app.appearance.clear()
    app.appearance.update(appearance)
    app.prefs.clear()
    app.prefs.update(prefs)
    app._last_dir = last_dir
    if theme != appearance["theme"]:
        from meshviewer.gui.style import stylesheet
        app._apply_theme()
        app.setStyleSheet(stylesheet())
    RESULTS.clear()


def _run_one(app, test):
    from fixtures import files
    try:
        test(app, files())
    except Exception:
        import traceback
        traceback.print_exc()
        RESULTS.append((False, "exception"))
    bad = [m for ok, m in RESULTS if not ok]
    print(f"{len(RESULTS) - len(bad)} passed, {len(bad)} failed", flush=True)
    return bad


def run(test):
    app = SHARED.get("app")
    if app is not None:                           # run_all.py: the shared app
        _run_one(app, test)
        close_all(app)
        return
    bad = _run_one(make_app(), test)
    sys.exit(1 if bad else 0)
