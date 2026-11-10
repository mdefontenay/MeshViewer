"""How long things take, in milliseconds — to compare before and after a change.

    python tools/bench.py path/to/model.step

Opens the file in the app and times what one does with it: drawing a frame, selecting,
hiding, isolating, the parts list, the section plane, a unit change. "frame" is what one
frame of a turn costs (1000 / frame = frames per second).
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from meshviewer.gui.app import MeshViewerApp          # noqa: E402


def main(path):
    app = MeshViewerApp(["bench"])
    app.setQuitOnLastWindowClosed(False)
    results = {}

    def pump(n=5):
        for _ in range(n):
            app.processEvents()

    def timed(name, action, repeat=1):
        t = time.perf_counter()
        for _ in range(repeat):
            action()
            pump()                                    # the frame it asked for, on screen
        results[name] = (time.perf_counter() - t) / repeat * 1000

    t = time.perf_counter()
    w = app.open_path(Path(path))
    while w.scene is None and time.perf_counter() - t < 600:
        app.processEvents()
        time.sleep(0.01)
    w.show()
    pump()
    sheet = getattr(w, "_unit_dialog", None)          # "which unit is this file in?"
    if sheet is not None:
        sheet._ok()
        pump()
    results["open"] = (time.perf_counter() - t) * 1000
    sc, sb = w.scene, w.sidebar
    names = list(sc.names)

    def turn():
        sc.p.camera.Azimuth(3)
        sc.p.iren.interactor.Render()                 # as a mouse drag does

    timed("frame", turn, 30)
    sc.select(names[0])
    timed("frame, 1 part selected", turn, 30)
    sc.select(None)
    timed("select 1 part", lambda: sc.select(names[0]))
    timed("select every part", lambda: sc.set_selection(names, notify=True))
    timed("deselect", lambda: sc.set_selection([], notify=True))
    timed("hide every part", lambda: sb._visibility_changed(names, False))
    timed("show every part", lambda: sb._visibility_changed(names, True))
    timed("isolate 1 part", lambda: sc.isolate(names[0]))
    sb._visibility_changed(names, True)
    timed("fill the parts list", sb.refresh_parts)
    if sc.model.dim == 3:
        sp = sb.section_panel
        timed("section on", lambda: sp.enable.setChecked(True))
        timed("section moved", lambda: sp.slider.setValue(sp.slider.value() + 40), 5)
        sp.enable.setChecked(False)
        pump()
    timed("another unit", lambda: w._unit_chosen(w.a_units[0]))
    n_cells = sum(p.n_cells for p in sc.model.parts.values())
    print(f"\n{Path(path).name}: {len(names)} parts, {n_cells:,} faces")
    for name, ms in results.items():
        print(f"  {name:26s} {ms:9.1f} ms")
    w.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
