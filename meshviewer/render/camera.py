"""Scene ▸ the camera: X / Y / Z / iso views, fit, parallel or perspective; 2D files
locked to the view from +Z; zoom to the cursor (`zoom_at`, driven by gui/viewport.py);
lines hidden while the view moves (smooth turning and zooming). `camera_gesture` =
(kind, serial) of what moves the camera now, for Undo (gui/undo.py): a new serial at each
drag, zoom burst or view button; kinds: rotate, pan, spin, zoom, view."""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import QTimer

from meshviewer.render.appearance import _size_labels

DRAG_KINDS = {1: "rotate", 2: "pan", 3: "spin", 4: "zoom", 5: "zoom"}   # VTKIS_* states
FAR_BACK = 40          # parallel view: the camera's distance, in model radii
ZOOM_RANGE = (1e-5, 1e3)   # zoom_at: the view's size (or distance) in model diagonals


class Camera:
    camera_gesture = ("move", 0)

    def new_gesture(self, kind):
        """What moves the camera from now on (Undo: a gesture is never cut in two)."""
        self.camera_gesture = (kind, self.camera_gesture[1] + 1)

    def view(self, which):
        """pressing X, Y or Z again without moving the camera in
        between looks from the opposite side (X -> -X -> X …). Iso never flips."""
        self.new_gesture("view")
        if self.model.dim == 2:                         # 2D: always from +Z
            self.p.view_xy(render=False)
            self.snap_to_z()
            self.fit()
            self._last_view = None
            return
        last = self._last_view
        flip = (which != "iso" and last is not None and last[0] == which
                and np.allclose(self._camera_state(), last[2], atol=1e-6 * self._diag()))
        negative = (not last[1]) if flip else False
        {"iso": self.p.view_isometric, "x": self.p.view_yz, "y": self.p.view_xz,
         "z": self.p.view_xy}[which](negative=negative, render=False)
        self.fit()
        self._last_view = (which, negative, self._camera_state())

    def _camera_state(self):
        c = self.p.camera
        return np.concatenate([c.position, c.focal_point, c.up, [c.parallel_scale]])

    def _diag(self):
        b = np.asarray(self.model_bounds(), dtype=float).reshape(3, 2)
        return float(np.linalg.norm(b[:, 1] - b[:, 0])) or 1.0

    def fit(self):
        # Model bounds only (not the section handle or the grid).
        self.new_gesture("view")
        self.p.reset_camera(bounds=self.model_bounds())
        self._place_camera()
        self.p.render()

    def rotate_left(self):
        """View ▸ Rotate Camera 90° Left: the picture turns a quarter turn to the left
        (counterclockwise) about the line of sight."""
        if self.model.dim == 2:
            return                                      # 2D: +Y stays up
        self.new_gesture("view")
        self.p.camera.Roll(90)
        self.p.renderer.ResetCameraClippingRange()
        self.p.render()

    # ---- parallel view: the camera far behind the model ------------------------------
    def _watch_camera(self):
        self.p.renderer.AddObserver("StartEvent", self._place_camera)    # before each frame
        self.on_camera = None            # UI hook (undo): (before, after) once it moved
        self._cam_base = None            # where it stood at the last frame (None: not yet)
        self.p.renderer.AddObserver("StartEvent", self._note_camera, -1.0)   # after placing

    # ---- the camera as a state (Edit ▸ Undo) ---------------------------------------
    def camera_snapshot(self):
        c = self.p.camera
        return (tuple(c.GetPosition()), tuple(c.GetFocalPoint()), tuple(c.GetViewUp()),
                float(c.GetParallelScale()), bool(c.GetParallelProjection()),
                float(c.GetViewAngle()))

    def same_camera(self, a, b):
        """The same picture: in parallel view, wherever the camera stands along its line
        of sight (`_place_camera` moves it there)."""
        if a is None or b is None or a[4] != b[4]:
            return a is b
        tol = 1e-9 * self._diag()
        pa, fa, ua, sa, par, va = (np.asarray(v, dtype=float) for v in a)
        pb, fb, ub, sb, _, vb = (np.asarray(v, dtype=float) for v in b)
        if not (np.allclose(fa, fb, atol=tol) and np.allclose(ua, ub, atol=1e-9)):
            return False
        if a[4]:
            da, db = fa - pa, fb - pb
            da /= np.linalg.norm(da) or 1.0
            db /= np.linalg.norm(db) or 1.0
            return bool(np.allclose(da, db, atol=1e-9) and abs(sa - sb) <= 1e-9 * max(sa, sb))
        return bool(np.allclose(pa, pb, atol=tol) and abs(va - vb) < 1e-9)

    def set_camera_snapshot(self, snap):
        pos, focal, up, scale, parallel, angle = snap
        if parallel != self.state.get("parallel"):
            self.state["parallel"] = bool(parallel)
        cam = self.p.camera
        cam.SetParallelProjection(bool(parallel))
        cam.SetPosition(*pos)
        cam.SetFocalPoint(*focal)
        cam.SetViewUp(*up)
        cam.SetParallelScale(scale)
        cam.SetViewAngle(angle)
        self.p.renderer.ResetCameraClippingRange()
        self._cam_base = None                          # where it is now: no new change
        self._place_camera()
        self.p.render()

    def _note_camera(self, *_):
        """Before each frame: the camera moved since the last one -> on_camera."""
        if self.on_camera is None:
            return
        now = self.camera_snapshot()
        before = self._cam_base
        if before is None or self.same_camera(before, now):
            self._cam_base = now
            return
        self._cam_base = now
        self.on_camera(before, now)

    def _place_camera(self, *_):
        """A parallel picture is the same wherever the camera stands along its line of
        sight, but two things in VTK are not. What is behind the camera is cut away:
        after zooming in and turning, the camera ended up inside the model and holes
        opened. And the grid's numbers are sized by their distance to the camera: the
        nearest axis got the smallest numbers. So, in parallel view, the camera is kept
        FAR_BACK model radii from the model's centre, and the numbers are sized for it."""
        cam = self.p.camera
        grid = self._grid_actor
        if not cam.GetParallelProjection():
            if grid is not None and grid.GetScreenSize() != self._label_made[0]:
                _size_labels(grid, self._label_made, 1.0)
            return
        b = np.asarray(self.model_bounds(), dtype=float).reshape(3, 2)
        centre, radius = b.mean(1), 0.5 * float(np.linalg.norm(b[:, 1] - b[:, 0])) or 1.0
        focal = np.asarray(cam.GetFocalPoint(), dtype=float)
        look = np.asarray(cam.GetDirectionOfProjection(), dtype=float)
        back = max(FAR_BACK * radius - float((centre - focal) @ look), radius)
        if abs(back - cam.GetDistance()) > 1e-6 * back:
            cam.SetPosition(*(focal - back * look))
            self.p.renderer.ResetCameraClippingRange()
        if grid is not None:
            factor = self.label_factor()
            if abs(grid.GetScreenSize() - self._label_made[0] * factor) > 1e-3 * grid.GetScreenSize():
                _size_labels(grid, self._label_made, factor)

    def label_factor(self):
        """What the grid's label size is multiplied by in parallel view, so the numbers
        keep the size they have in perspective whatever the zoom (1 in perspective)."""
        cam = self.p.camera
        if not cam.GetParallelProjection():
            return 1.0
        b = np.asarray(self.model_bounds(), dtype=float).reshape(3, 2)
        radius = 0.5 * float(np.linalg.norm(b[:, 1] - b[:, 0])) or 1.0
        half = np.tan(np.radians(cam.GetViewAngle()) / 2)
        return float(cam.GetParallelScale() / (half * FAR_BACK * radius))

    def set_parallel(self, on, render=True):
        on = on or self.model.dim == 2                 # 2D: always parallel
        self.state["parallel"] = bool(on)
        cam = self.p.camera
        if on:
            self.p.enable_parallel_projection()
        else:                                # stand where perspective shows the same size
            half = np.tan(np.radians(cam.GetViewAngle()) / 2)
            focal = np.asarray(cam.GetFocalPoint(), dtype=float)
            look = np.asarray(cam.GetDirectionOfProjection(), dtype=float)
            if cam.GetParallelProjection():
                cam.SetPosition(*(focal - cam.GetParallelScale() / half * look))
            self.p.disable_parallel_projection()
            self.p.renderer.ResetCameraClippingRange()
        self._place_camera()
        if render:
            self.p.render()

    # ---- 2D files: always seen from above (+Z), never turned -----------------------
    def snap_to_z(self, render=False):
        """Look straight down -Z with +Y up, keeping the place and the zoom."""
        c = self.p.camera
        f = np.asarray(c.focal_point, dtype=float)
        d = float(np.linalg.norm(np.asarray(c.position, dtype=float) - f)) or self._diag()
        c.position = tuple(f + (0.0, 0.0, d))
        c.up = (0.0, 1.0, 0.0)
        self.p.renderer.ResetCameraClippingRange()
        if render:
            self.p.render()

    def _lock_to_z(self):
        """Left / middle drag pan, right drag and the wheel zoom; nothing rotates
        (the trackpad's two-finger rotate is ignored too)."""
        self.p.enable_custom_trackball_style(
            left="pan", shift_left="pan", control_left="pan", middle="pan",
            shift_middle="pan", control_middle="pan", right="dolly", shift_right="dolly",
            control_right="dolly")
        style = self.p.iren.interactor.GetInteractorStyle()
        if style is not None:                             # whatever moved it: square again
            style.AddObserver("EndInteractionEvent", lambda *_: self.snap_to_z(render=True))
        iren = self.p.iren.interactor
        for ev in ("StartRotateEvent", "RotateEvent", "EndRotateEvent"):
            held = {}

            def block(*_, h=held):
                h["cmd"].SetAbortFlag(1)                  # the style never sees it
            held["cmd"] = iren.GetCommand(iren.AddObserver(ev, block, 100.0))

    # ---- zoom to the cursor (wheel, trackpad scroll and pinch: gui/viewport.py) --------
    def _world_at(self, x, y, z):
        """The world point at display (x, y) (VTK's pixels, from the bottom left) and
        depth z (0 near … 1 far)."""
        ren = self.p.renderer
        ren.SetDisplayPoint(float(x), float(y), float(z))
        ren.DisplayToWorld()
        w = np.asarray(ren.GetWorldPoint(), dtype=float)
        return w[:3] / (w[3] if w[3] else 1.0)

    def zoom_at(self, factor, x, y, render=True):
        """Zoom by `factor` (> 1: closer) keeping what is under display point (x, y)
        where it is on screen. Parallel: the scale changes and the view slides so that
        point stays put (on a 2D file the slide is in the XY plane: still seen from +Z).
        Perspective: the camera moves along the line through the cursor, `factor` times
        closer to its point on the focal plane, and the focal plane comes with it (as
        VTK's own dolly, aimed at the cursor). `_place_camera` still puts a parallel
        camera FAR_BACK before the frame is drawn. (The depth buffer would give the model
        under the cursor, but the Qt view's buffer can't be read reliably.)"""
        if not (factor > 0 and np.isfinite(factor)) or abs(factor - 1.0) < 1e-9:
            return
        cam, ren = self.p.camera, self.p.renderer
        diag = self._diag()
        pos = np.asarray(cam.GetPosition(), dtype=float)
        focal = np.asarray(cam.GetFocalPoint(), dtype=float)
        ren.SetWorldPoint(*focal, 1.0)
        ren.WorldToDisplay()
        zf = ren.GetDisplayPoint()[2]                      # the focal plane's depth
        if cam.GetParallelProjection():
            before = self._world_at(x, y, zf)
            scale = float(np.clip(cam.GetParallelScale() / factor,
                                  diag * ZOOM_RANGE[0], diag * ZOOM_RANGE[1]))
            cam.SetParallelScale(scale)
            shift = before - self._world_at(x, y, zf)
            cam.SetFocalPoint(*(focal + shift))
            cam.SetPosition(*(pos + shift))
        else:
            look = focal - pos
            d_focal = float(np.linalg.norm(look)) or diag
            look /= d_focal
            target = self._world_at(x, y, zf)              # on the focal plane
            d = float((target - pos) @ look) or d_focal    # its depth ahead
            new_d = float(np.clip(d / factor, diag * ZOOM_RANGE[0], diag * ZOOM_RANGE[1]))
            new_pos = target - (target - pos) * (new_d / d)
            cam.SetPosition(*new_pos)
            cam.SetFocalPoint(*(new_pos + look * new_d))   # focal plane at the target's
        ren.ResetCameraClippingRange()
        if render:
            self.p.render()

    def wheel_zoom(self, factor, x, y):
        """A zoom from the viewport (wheel, trackpad, pinch): edges off while zooming."""
        self._zoom_step()
        self.zoom_at(factor, x, y)

    # ---- smooth rotation: edges off while the view moves --------------------------
    def _setup_interaction_lod(self):
        style = self.p.iren.interactor.GetInteractorStyle()
        if style is not None:
            style.AddObserver("StartInteractionEvent", lambda *_: self._drag_started(style))
            style.AddObserver("EndInteractionEvent", lambda *_: self._set_moving(False))
        # the scroll wheel / trackpad zooms in many small steps, so edges would flash back
        # between steps. Treat a burst of zoom steps (wheel_zoom, or VTK's own wheel when
        # the plain view is used) as one movement that ends 0.3 s after the last step.
        self._zooming = False
        self._zoom_timer = QTimer()
        self._zoom_timer.setSingleShot(True)
        self._zoom_timer.setInterval(300)
        self._zoom_timer.timeout.connect(self._zoom_ended)
        iren = self.p.iren.interactor
        for ev in ("MouseWheelForwardEvent", "MouseWheelBackwardEvent", "MouseWheelLeftEvent",
                   "MouseWheelRightEvent", "StartPinchEvent", "PinchEvent", "EndPinchEvent"):
            iren.AddObserver(ev, self._zoom_step, 10.0)    # before the style draws the frame
        self.p.zoom_handler = self.wheel_zoom    # gui/viewport.py: smooth zoom to the cursor

    def _drag_started(self, style):
        self.new_gesture(DRAG_KINDS.get(style.GetState(), "move"))
        self._set_moving(True)

    def _zoom_step(self, *_):
        if self.camera_gesture[0] != "zoom" or not self._zoom_timer.isActive():
            self.new_gesture("zoom")                 # a new burst of zoom steps
        self._zoom_timer.start()                     # restart: wait for the last step
        if self.hide_edges_moving:
            self._zooming = True
            self._set_moving(True)

    def _zoom_ended(self):
        self._zooming = False
        self._set_moving(False)

    def _set_moving(self, moving):
        # any model size; switchable in Appearance
        if moving == self._moving or (moving and not self.hide_edges_moving):
            return
        if not moving and self._zooming:
            return                                   # still zooming: keep edges off
        self._moving = moving
        # Lines are the costliest thing to draw on macOS: drop them while moving
        # (except feature edges in "Edges only", the only thing left to see).
        self._apply_lines()
        self._sync_outline()
        self.section.set_moving(moving)            # cut mesh edges too
        if not moving:
            self.p.render()
