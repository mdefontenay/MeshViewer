"""Scene ▸ the camera: X / Y / Z / iso views, fit, parallel or perspective; 2D files
locked to the view from +Z; lines hidden while the view moves (smooth turning)."""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import QTimer

from meshviewer.render.appearance import _size_labels

FAR_BACK = 40          # parallel view: the camera's distance, in model radii


class Camera:
    def view(self, which):
        """pressing X, Y or Z again without moving the camera in
        between looks from the opposite side (X -> -X -> X …). Iso never flips."""
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
        self.p.reset_camera(bounds=self.model_bounds())
        self._place_camera()
        self.p.render()

    # ---- parallel view: the camera far behind the model ------------------------------
    def _watch_camera(self):
        self.p.renderer.AddObserver("StartEvent", self._place_camera)    # before each frame

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

    # ---- smooth rotation: edges off while the view moves --------------------------
    def _setup_interaction_lod(self):
        style = self.p.iren.interactor.GetInteractorStyle()
        if style is not None:
            style.AddObserver("StartInteractionEvent", lambda *_: self._set_moving(True))
            style.AddObserver("EndInteractionEvent", lambda *_: self._set_moving(False))
        # the scroll wheel / trackpad zooms in single steps (each one a
        # complete start-zoom-end), so edges would flash back between steps. Treat a
        # burst of zoom steps as one movement that ends 0.3 s after the last step.
        self._zooming = False
        self._zoom_timer = QTimer()
        self._zoom_timer.setSingleShot(True)
        self._zoom_timer.setInterval(300)
        self._zoom_timer.timeout.connect(self._zoom_ended)
        iren = self.p.iren.interactor
        for ev in ("MouseWheelForwardEvent", "MouseWheelBackwardEvent", "MouseWheelLeftEvent",
                   "MouseWheelRightEvent", "StartPinchEvent", "PinchEvent", "EndPinchEvent"):
            iren.AddObserver(ev, self._zoom_step, 10.0)    # before the style draws the frame

    def _zoom_step(self, *_):
        if not self.hide_edges_moving:
            return
        self._zooming = True
        self._set_moving(True)
        self._zoom_timer.start()                     # restart: wait for the last step

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
