"""How fast a contour plays through time steps, in milliseconds — to compare before and
after a change.

    python tools/bench_timeline.py [folder]     (the cases are made there once and kept;
                                                 default: a temporary folder)

Makes two OpenFOAM cases with tests/fixtures.foam_case (3D 40 × 24 × 20 cells and 2D
200 × 100 cells, 8 time steps, about 25 fields each), opens each in the app (with a
scratch settings file: what the app remembers is untouched) and times: opening, reading
every step's ranges, one step the first time (from disk) and again (from memory) — the
contour alone, then with Section's cut cells, a plot, a second contour and three
probes (a point, an area, a line through the cells). "fps" is
1000 / the step's time, the frame drawn included.
"""
import os
import sys

import numpy as np
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
os.environ["MESHVIEWER_SETTINGS"] = os.path.join(tempfile.mkdtemp(), "settings.ini")

from PySide6.QtCore import QEvent                     # noqa: E402
from fixtures import foam_case                         # noqa: E402
from meshviewer.gui.app import MeshViewerApp          # noqa: E402


class BenchApp(MeshViewerApp):
    def event(self, e):                                # (macOS sends the folder argument
        if e.type() == QEvent.FileOpen:                #  as a file to open: not here)
            return True
        return super().event(e)

TIMES = tuple(str(t) for t in (0, 0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 1))
CASES = {"3D 40×24×20": dict(n=(40, 24, 20)),
         "2D 200×100": dict(n=(200, 100, 1), size=(2.0, 1.0, 0.01), two_d=True)}


def make(folder):
    out = {}
    for name, kw in CASES.items():
        case = Path(folder) / name.split()[0]
        if not (case / TIMES[-1]).is_dir():
            print(f"making {name}…", flush=True)
            foam_case(case, times=TIMES, **kw)
        out[name] = case
    return out


def main(folder):
    cases = make(folder)
    app = BenchApp(["bench"])
    app.setQuitOnLastWindowClosed(False)

    def pump(n=3):
        for _ in range(n):
            app.processEvents()

    def wait(cond, limit=600):
        t = time.perf_counter()
        while not cond() and time.perf_counter() - t < limit:
            app.processEvents()
            time.sleep(0.002)

    report = []
    for name, case in cases.items():
        res = {}
        t = time.perf_counter()
        w = app.open_path(case)
        wait(lambda: w.scene is not None)
        w.resize(1400, 900)
        w.show()
        pump()
        sheet = getattr(w, "_unit_dialog", None)
        if sheet is not None:
            sheet._ok()
        res["open"] = (time.perf_counter() - t) * 1000
        sc, sb, panel = w.scene, w.sidebar, w.sidebar.contours_panel
        view, case_ = w.plotter, sc.model.case
        t = time.perf_counter()
        wait(lambda: panel._steps_job is None)
        res["read every step (background)"] = (time.perf_counter() - t) * 1000
        w._show_page("contour:1")
        ed = panel.editors[panel.active][1]
        ed.field.setCurrentIndex(ed.field.findData("p"))
        ed.anim.on.setChecked(True)
        pump()
        case_.cache.stop()
        case_.cache.wait()
        bar = w.anim_bar
        n = bar.count

        def step(i):
            bar.set_index(i)
            pump(1)
            view.flush()                       # the frame drawn

        def per_step(rounds=2):
            t = time.perf_counter()
            k = 0
            for _ in range(rounds):
                for i in range(n):
                    step(i)
                    k += 1
            return (time.perf_counter() - t) / k * 1000

        def first_read():
            case_.cache.stop()
            case_.cache.wait()
            case_.cache._items.clear()
            case_.cache.nbytes = 0
            case_._fields_at.clear()
            t = time.perf_counter()
            for i in range(n):
                step(i)
                case_.cache.stop()                # (no reading ahead: the disk each time)
            return (time.perf_counter() - t) / n * 1000

        res["step, first time (disk)"] = first_read()
        res["step, contour"] = per_step()
        if sc.model.dim == 3:
            sp = sb.section_panel
            sp.enable.setChecked(True)
            sp.fill.setChecked(True)
            sc.section.set_plane(origin=sc.section.center, normal=(1, 0, 0))
            wait(lambda: sc.section._volume is not None)
            pump()
            res["step, + section cut cells"] = per_step()
        sb.show_tab("analyze")                         # a plot (2D: a line across the zone)
        sb.plots_panel.add("section", "Cut")
        pump()
        w._show_page("contour:1")
        pump()
        res["step, + a plot"] = per_step()
        panel.add(field="k")
        pump()
        w._show_page("contour:1")
        pump()
        res["step, + a 2nd contour"] = per_step()
        pp = sb.probes_panel                           # three probes: a point, an area, a line
        lo, hi = (np.asarray(b) for b in np.array(sc.model_bounds()).reshape(3, 2).T)
        t = time.perf_counter()
        pp.add(target={"kind": "point", "how": "xyz", "xyz": list((lo + hi) / 2)})
        pp.add(target={"kind": "area", "how": "parts", "parts": [sc.names[0]]})
        pp.add(target={"kind": "line", "how": "through",
                       "points": [list(lo + 0.1 * (hi - lo)), list(hi - 0.1 * (hi - lo))]})
        wait(lambda: not pp.busy)
        res["3 probes made, every step read"] = (time.perf_counter() - t) * 1000
        w._show_page("contour:1")
        pump()
        res["step, + 3 probes"] = per_step()
        cells = sum(p.n_cells for p in sc.model.parts.values())
        report.append((name, cells, n, res, case_.cache.nbytes))
        w.close()
        pump()
    for name, cells, n, res, nbytes in report:
        print(f"\n{name}: {cells:,} faces shown, {n} steps, cache {nbytes / 2**20:.1f} MB")
        for k, ms in res.items():
            fps = f"  ({1000 / ms:5.1f} fps)" if k.startswith("step") else ""
            print(f"  {k:32s} {ms:9.1f} ms{fps}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix="bench-timeline-"))
