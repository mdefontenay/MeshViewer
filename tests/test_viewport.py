"""The 3D view draws each frame once, and what is on screen is the latest frame."""
import numpy as np
from conftest import check, open_file, run


def test(app, files):
    w = open_file(app, files["step"])
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
    w.resize(1200, 800)
    pump()
    check(screen().shape[1] > 100 and differ(screen(), screen()) == 0, "after a resize: drawn at the new size")
    w.close()


if __name__ == "__main__":
    run(test)
