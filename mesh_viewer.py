#!/usr/bin/env python3
"""Mesh Viewer — entry point.

    MESH  CGNS (.cgns), UGRID (.lb8/.b8/.lb4/.b4.ugrid)   -> meshviewer/mesh/
    CAD   STEP, IGES, BREP, STL, OBJ, PLY, glTF, VRML    -> meshviewer/cad/
    UI    Qt window + side panel                         -> meshviewer/gui/

Run from source:   .venv/bin/python mesh_viewer.py [file ...]
Build the app:     ./build_app.sh          (installs in /Applications)
Build a .dmg:      ./make_dmg.sh
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def selftest() -> int:
    """NEW (v2.12): `Mesh Viewer --selftest` — checks a bundled app has everything
    (used by make_dmg.sh before packaging). Prints one line per check."""
    import importlib
    failed = 0
    # Standard modules backed by Homebrew libraries that the app actually uses
    # (py2app only bundles what's imported, so unused ones like sqlite3 aren't checked).
    for mod in ("lzma", "bz2", "zlib", "ssl", "hashlib", "decimal", "ctypes",
                "numpy", "h5py", "PySide6.QtWidgets", "pyvista", "pyvistaqt", "OCP.STEPControl",
                "meshviewer.gui.app", "meshviewer.cad.step", "meshviewer.mesh.cgns"):
        try:
            importlib.import_module(mod)
            print(f"ok    {mod}")
        except Exception as exc:                       # report every missing piece
            failed += 1
            print(f"FAIL  {mod}: {exc}")
    try:                                               # VTK can draw off screen
        import pyvista as pv
        p = pv.Plotter(off_screen=True, window_size=(64, 64))
        p.add_mesh(pv.Sphere())
        p.screenshot(None, return_img=True)
        p.close()
        print("ok    off-screen render")
    except Exception as exc:
        failed += 1
        print(f"FAIL  off-screen render: {exc}")
    try:                                               # Qt window system + 3D widget
        from PySide6.QtWidgets import QApplication
        from pyvistaqt import QtInteractor
        qapp = QApplication.instance() or QApplication(["Mesh Viewer"])
        view = QtInteractor(None)
        view.close()
        print(f"ok    Qt ({qapp.platformName()}) + 3D view")
    except Exception as exc:
        failed += 1
        print(f"FAIL  Qt window / 3D view: {exc}")
    print("SELFTEST OK" if not failed else f"SELFTEST FAILED ({failed})")
    return 1 if failed else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(selftest())
    from meshviewer.gui.app import run
    sys.exit(run())
