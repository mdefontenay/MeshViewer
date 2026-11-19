"""The 3D view draws each frame once, and what is on screen is the latest frame."""
import sys

import numpy as np
from conftest import check, open_file, run


def _float_on_top(w):
    """macOS: the window above every other one, so a screen grab sees it (a test run from
    a terminal or an agent is not the app in front, and other windows may cover it)."""
    if sys.platform != "darwin":
        return
    import objc
    win = objc.objc_object(c_void_p=int(w.winId())).window()
    win.setLevel_(3)                                       # NSFloatingWindowLevel
    win.orderFrontRegardless()


def test(app, files):
    w = open_file(app, files["step"])
    _float_on_top(w)
    sc, sb, view = w.scene, w.sidebar, w.plotter
    pump = lambda: [app.processEvents() for _ in range(5)]            # noqa: E731
    pump()
    drawn = []
    view.ren_win.AddObserver("StartEvent", lambda *_: drawn.append(1))

    def frames(action):
        drawn.clear()
        action()
        pump()
        return len(drawn)

    def screen():                                    # the pixels of the view, as shown
        img = app.primaryScreen().grabWindow(view.winId()).toImage()
        a = np.frombuffer(img.constBits(), np.uint8).reshape(img.height(), img.bytesPerLine())
        return a[:, :img.width() * 4].reshape(img.height(), img.width(), 4)[..., :3].astype(int)

    def differ(a, b):
        return int((np.abs(a - b).max(axis=2) > 24).sum())

    names = list(sc.names)
    full = screen()
    n = frames(lambda: sb._visibility_changed(names, False))
    empty = screen()
    check(n == 1, f"hide every part: drawn once ({n})")
    check(differ(full, empty) > 2000, "…and the screen shows it (parts gone)")
    n = frames(lambda: sb._visibility_changed(names, True))
    check(n == 1 and differ(full, screen()) < 50, f"show them again: drawn once ({n}), same picture")
    n = frames(lambda: sc.set_selection(names, notify=True))
    check(n == 1, f"select every part: drawn once ({n})")
    sel = screen()
    check(differ(full, sel) > 200, "…and the outline is on screen")
    sc.set_selection([])
    pump()

    def turn():                                      # as a mouse drag does: VTK draws itself
        sc.p.camera.Azimuth(35)
        sc.p.iren.interactor.Render()
    n = frames(turn)
    check(n == 1, f"turning the model: one draw per frame ({n})")
    check(differ(full, screen()) > 500, "…and the turned model is on screen")
    turned = screen()
    n = frames(view.update)                          # the window asks for a repaint
    check(n == 1 and differ(turned, screen()) < 50, f"a repaint draws again ({n}), same picture")
    # parallel view, zoomed in on a corner and turned: nothing of the model behind the camera
    cam = sc.p.camera
    b = np.array(sc.model_bounds()).reshape(3, 2)
    centre, radius = b.mean(1), 0.5 * np.linalg.norm(b[:, 1] - b[:, 0])
    cam.SetFocalPoint(*b[:, 1])
    cam.SetPosition(*(b[:, 1] + 0.1 * radius * np.ones(3) / 3 ** 0.5))    # inside the model's box
    cam.SetParallelScale(cam.GetParallelScale() / 20)
    turn()
    pump()
    depth = (centre - np.array(cam.GetPosition())) @ np.array(cam.GetDirectionOfProjection())
    check(cam.GetParallelProjection() and depth - radius > 0
          and cam.GetClippingRange()[0] < depth - radius,
          "zoomed in and turned: the whole model stays in front of the camera (no hole)")
    made, grid = sc._label_made[0], sc._grid_actor
    check(abs(grid.GetScreenSize() - made * sc.label_factor()) < 1e-3 * grid.GetScreenSize()
          and sc.label_factor() < 0.2, "grid numbers sized for the zoom, the same on every axis")
    zoom_checks(app, w, pump, drawn)
    w.resize(1200, 800)
    pump()
    check(screen().shape[1] > 100 and differ(screen(), screen()) == 0, "after a resize: drawn at the new size")
    w.close()
    tab_checks(app, files, screen_of=lambda view: screen_fn(app, view), differ=differ)
    step_checks(app, screen_of=lambda view: screen_fn(app, view), differ=differ)


def step_checks(app, screen_of, differ):
    """Another time step (the playback bar): drawn once, new colors, the camera as it was."""
    import shutil
    import tempfile
    from pathlib import Path
    from fixtures import foam_case
    tmp = Path(tempfile.mkdtemp(prefix="foam-view-"))
    try:
        w = open_file(app, foam_case(tmp / "steps", n=(6, 4, 4), times=("0.5", "1")))
        _float_on_top(w)
        sc, view, panel = w.scene, w.plotter, w.sidebar.contours_panel
        pump = lambda: [app.processEvents() for _ in range(5)]        # noqa: E731
        w._show_page("contour:1")
        ed = panel.editors[panel.active][1]
        ed.field.setCurrentIndex(ed.field.findData("p"))
        ed.anim.on.setChecked(True)
        ed.anim.range_acts["timeline"].trigger()
        from conftest import wait
        wait(app, lambda: panel._steps_job is None, 30)
        pump()
        drawn = []
        view.ren_win.AddObserver("StartEvent", lambda *_: drawn.append(1))
        before, cam = screen_of(view), [tuple(v) for v in sc.p.camera_position]
        drawn.clear()
        w.anim_bar.step(-1)
        pump()
        check(len(drawn) == 1 and sc.model.time_index == 0
              and [tuple(v) for v in sc.p.camera_position] == cam,
              f"Step Backward: drawn once, the camera as it was ({len(drawn)})")
        check(differ(before, screen_of(view)) > 300, "…and the new step's colors are on screen")
        w.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def screen_fn(app, view):
    img = app.primaryScreen().grabWindow(view.winId()).toImage()
    a = np.frombuffer(img.constBits(), np.uint8).reshape(img.height(), img.bytesPerLine())
    return a[:, :img.width() * 4].reshape(img.height(), img.width(), 4)[..., :3].astype(int)


def tab_checks(app, files, screen_of, differ):
    """3D View and a contour's tab: one frame each way, the colors only in the contour's."""
    w = open_file(app, files["tecplot"])
    _float_on_top(w)
    sc, view = w.scene, w.plotter
    pump = lambda: [app.processEvents() for _ in range(5)]            # noqa: E731
    pump()
    drawn = []
    view.ren_win.AddObserver("StartEvent", lambda *_: drawn.append(1))
    plain = screen_of(view)
    drawn.clear()
    w._show_page("contour:1")
    pump()
    colored = screen_of(view)
    check(len(drawn) == 1 and sc.results.shown and sc.colorbar.shown,
          f"Contour 1's tab: drawn once, with its colors and bar ({len(drawn)})")
    check(differ(plain, colored) > 500, "…and the screen shows them")
    drawn.clear()
    w._show_page("model")
    pump()
    check(len(drawn) == 1 and not sc.results.shown and not sc.colorbar.shown
          and differ(plain, screen_of(view)) < 50,
          f"3D View again: drawn once, the model alone as before ({len(drawn)})")
    w.close()



def zoom_checks(app, w, pump, drawn):
    """The wheel, a trackpad scroll and a pinch zoom toward the cursor: the point under it
    stays put (parallel and perspective, and a 2D-like view from +Z), a wheel notch is
    eased in over a few frames — one draw each — edges come back 0.3 s after the last
    step, and a zoom is one Undo step."""
    import time
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtGui import QWheelEvent
    sc, view = w.scene, w.plotter
    cam, ren = sc.p.camera, sc.p.renderer
    st = w.changes.stack
    sc.set_parallel(True, render=False)
    sc.view("iso")
    pump()
    q = QPointF(view.width() * 0.3, view.height() * 0.4)
    x, y = view._display_point(q)
    diag = sc._diag()

    def under():                                 # the world point under the cursor
        ren.SetWorldPoint(*cam.GetFocalPoint(), 1.0)
        ren.WorldToDisplay()
        return sc._world_at(x, y, ren.GetDisplayPoint()[2])

    def wheel(pixels, angle, phase=Qt.ScrollPhase.NoScrollPhase):
        view.wheelEvent(QWheelEvent(q, q, QPoint(0, pixels), QPoint(0, angle), Qt.NoButton,
                                    Qt.NoModifier, phase, False))

    def settle(cond, timeout=3):
        t = time.time()
        while not cond() and time.time() - t < timeout:
            app.processEvents()
            time.sleep(0.005)
        pump()

    calls = []
    handler = view.zoom_handler
    view.zoom_handler = lambda f, *xy: (calls.append(f), handler(f, *xy))
    p0, s0, n0 = under(), cam.GetParallelScale(), st.count()
    drawn.clear()
    wheel(0, 120)                                # one notch forward: closer, × 1.2, eased in
    check(sc._moving or not sc.hide_edges_moving, "wheel: edges off while zooming")
    settle(lambda: not view._glide.isActive())
    ratio = s0 / cam.GetParallelScale()
    check(abs(ratio - 1.2) < 1e-6 and np.linalg.norm(under() - p0) < 1e-6 * diag,
          f"wheel notch: × {ratio:.4f}, the point under the cursor stays put")
    check(len(calls) > 3 and 0 < len(drawn) <= len(calls),
          f"…eased in over {len(calls)} steps, {len(drawn)} frames (one per step at most)")
    settle(lambda: not sc._zooming, timeout=1)
    check(not sc._moving, "edges back once the zoom has stopped")
    check(st.count() == n0 + 1, f"a wheel zoom: one Undo step ({st.count() - n0})")
    s1, p1 = cam.GetParallelScale(), under()
    wheel(50, 0, Qt.ScrollPhase.ScrollUpdate)    # trackpad: continuous, right away
    check(abs(s1 / cam.GetParallelScale() - np.exp(50 * 0.004)) < 1e-6
          and np.linalg.norm(under() - p1) < 1e-6 * diag,
          "trackpad scroll: zoomed at once by exp(pixels × k), toward the cursor")
    wheel(0, -240)                               # two notches back: farther
    settle(lambda: not view._glide.isActive())
    check(cam.GetParallelScale() > s1, "wheel backward: farther")
    view.zoom_handler = handler
    sc.set_parallel(False, render=False)         # perspective: toward the point too
    sc.view("iso")
    pump()
    sc.p.render_now() if hasattr(sc.p, "render_now") else None
    p2, d2 = under(), cam.GetDistance()
    sc.zoom_at(1.5, x, y)
    pump()
    look = np.asarray(cam.GetDirectionOfProjection())
    ren.SetWorldPoint(*p2, 1.0)
    ren.WorldToDisplay()
    px, py, _ = ren.GetDisplayPoint()
    check(abs(px - x) < 0.5 and abs(py - y) < 0.5 and cam.GetDistance() < d2
          and np.allclose(look, np.asarray(cam.GetDirectionOfProjection()), atol=1e-9),
          f"perspective: the point under the cursor stays put ({px - x:.2f}, {py - y:.2f} px), "
          "closer, not turned")
    sc.set_parallel(True, render=False)
    sc.view("z")                                 # seen from +Z (as a 2D file): stays so
    pump()
    sc.zoom_at(2.0, x, y)
    check(np.allclose(cam.GetDirectionOfProjection(), (0, 0, -1), atol=1e-9),
          "zoom from +Z: still looking down Z")
    sc.fit()
    pump()


if __name__ == "__main__":
    run(test)
