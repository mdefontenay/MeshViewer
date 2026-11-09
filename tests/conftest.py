"""Tiny headless test harness (no pytest needed): check(), open_file(), run().

    python tests/test_sidebar.py        one test file
    python tests/run_all.py             all of them (under xvfb-run on Linux without a display)
"""
from __future__ import annotations

import sys
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
        time.sleep(0.02)


def open_file(app, path, size=(1400, 900)):
    w = app.open_path(Path(path))
    wait(app, lambda: w.scene is not None)
    w.resize(*size)
    w.show()
    for _ in range(5):
        app.processEvents()
    return w


def run(test):
    from PySide6.QtCore import QSettings
    QSettings("local", "Mesh Viewer").remove("views")           # fresh per-file memory
    from fixtures import files
    from meshviewer.gui.app import MeshViewerApp
    app = MeshViewerApp(["test"])
    app.setQuitOnLastWindowClosed(False)
    try:
        test(app, files())
    except Exception:
        import traceback
        traceback.print_exc()
        RESULTS.append((False, "exception"))
    bad = [m for ok, m in RESULTS if not ok]
    print(f"{len(RESULTS) - len(bad)} passed, {len(bad)} failed", flush=True)
    sys.exit(1 if bad else 0)
