"""The 3D view widget: PyVista's Qt view, drawing each frame once.

Two things made the stock widget draw more than needed:

  - Every part of the app says "draw again" (plotter.render()) after it changes
    something, and one click often changes several things: hiding 300 parts, another
    unit, a selection with its outlines. Drawing each time made such a click cost from
    2 to 300 frames. Here render() only notes that a frame is due; it is drawn once,
    when the click's work is done.
  - After VTK has drawn a frame, the widget is asked to show it — and PyVistaQt drew
    the whole scene a second time to do so, also on every frame of a turn or a zoom.
    Here a frame that was just drawn is only copied to the screen.

    view.render()        a frame is due
    view.render_now()    draw right away
    view.flush()         draw right away if a frame is due

Zooming (as in a CAD app on the Mac): the wheel, a trackpad's two-finger scroll and its
pinch zoom smoothly, toward the point under the cursor (the camera's `zoom_at`, through
`zoom_handler`, set by the scene), not in VTK's fixed steps toward the middle:

    trackpad scroll      continuous: exp(pixels × TRACKPAD_ZOOM) per event (and its glide)
    pinch                exp(the gesture's magnification) per event
    mouse wheel          each notch NOTCH_ZOOM, eased in over a few frames (GLIDE_MS ticks)

Each step asks for a frame (`render`): still one frame per event or tick.

Dragging an overlay (Contours ▸ the color bar): `overlay`, set by the scene, answers
`hit(x, y)`; a left press on it moves it (`drag(dx, dy)`, `drag_done()`) instead of the
camera, and the pointer is an open hand over it.

make_view() gives this widget — or PyVistaQt's own, untouched, when the environment
variable MESHVIEWER_PLAIN_VIEW is set (to compare, should a picture ever look stale).
"""
from __future__ import annotations

import math
import os

from PySide6.QtCore import QEvent, Qt, QThread, QTimer
from PySide6.QtGui import QCursor
from pyvistaqt import QtInteractor

TRACKPAD_ZOOM = 0.004          # per pixel of trackpad scroll: 100 px -> × 1.5
NOTCH_ZOOM = math.log(1.2)     # one wheel notch (120 / 8 degrees): × 1.2
GLIDE_MS = 15                  # a wheel notch is eased in at this tick…
GLIDE = 0.35                   # …taking this share of what is left each tick


class Viewport(QtInteractor):
    def __init__(self, parent=None):
        self._fresh = False                         # VTK's last frame is not on screen yet
        super().__init__(parent, auto_update=False)
        self._due = QTimer(self)
        self._due.setSingleShot(True)
        self._due.setInterval(0)                    # as soon as the event is handled
        self._due.timeout.connect(self.render_now)
        self.zoom_handler = None                    # (factor, x, y): the scene's zoom
        self.overlay = None                         # what can be dragged (the color bar)
        self._dragging = None                       # its last display point while dragged
        self._hand = False                          # the open hand shown over it
        self._glide_left = 0.0                      # log of the wheel zoom still to come
        self._glide_at = (0.0, 0.0)
        self._glide = QTimer(self)
        self._glide.setInterval(GLIDE_MS)
        self._glide.timeout.connect(self._glide_tick)

    # ---- zooming: wheel, trackpad, pinch ---------------------------------------------------
    def _display_point(self, pos):
        """A Qt position (points, from the top left) -> VTK display pixels."""
        r = self.devicePixelRatioF()
        return pos.x() * r, (self.height() - pos.y() - 1) * r

    def wheelEvent(self, ev):
        if getattr(self, "zoom_handler", None) is None:
            return super().wheelEvent(ev)
        ev.accept()
        pixels, angle = ev.pixelDelta().y(), ev.angleDelta().y()
        x, y = self._display_point(ev.position())
        trackpad = not ev.pixelDelta().isNull() or ev.phase() != Qt.ScrollPhase.NoScrollPhase
        if trackpad:                                # continuous, as the fingers move
            dy = pixels if pixels else angle / 8
            if dy:
                self.zoom_handler(math.exp(dy * TRACKPAD_ZOOM), x, y)
        elif angle:                                 # a wheel notch: eased in
            self._glide_left += angle / 120 * NOTCH_ZOOM
            self._glide_at = (x, y)
            if not self._glide.isActive():
                self._glide_tick()
                self._glide.start()

    def _glide_tick(self):
        left = self._glide_left
        step = left if abs(left) < 2e-3 else left * GLIDE
        self._glide_left = left - step
        if step and self.zoom_handler is not None:
            self.zoom_handler(math.exp(step), *self._glide_at)
        if not self._glide_left:
            self._glide.stop()

    def event(self, ev):
        if (ev.type() == QEvent.Type.NativeGesture
                and getattr(self, "zoom_handler", None) is not None
                and ev.gestureType() == Qt.NativeGestureType.ZoomNativeGesture):
            ev.accept()                             # pinch: its magnification, continuous
            self.zoom_handler(math.exp(ev.value()), *self._display_point(ev.position()))
            return True
        return super().event(ev)

    # ---- dragging an overlay (the color bar) ----------------------------------------------
    def _on_overlay(self, ev):
        ov = getattr(self, "overlay", None)
        return ov is not None and ov.hit(*self._display_point(ev.position()))

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton and self._on_overlay(ev):
            ev.accept()
            self._dragging = self._display_point(ev.position())
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
            return
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        if self._dragging is not None:
            ev.accept()
            x, y = self._display_point(ev.position())
            self.overlay.drag(x - self._dragging[0], y - self._dragging[1])
            self._dragging = (x, y)
            return
        if not ev.buttons():                        # the hand over the bar
            over = self._on_overlay(ev)
            if over != self._hand:
                self._hand = over
                if over:
                    self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
                else:
                    self.unsetCursor()
        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        if self._dragging is not None and ev.button() == Qt.MouseButton.LeftButton:
            ev.accept()
            self._dragging = None
            self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
            self.overlay.drag_done()
            return
        super().mouseReleaseEvent(ev)

    # ---- one frame per event -----------------------------------------------------------
    def render(self):
        due = getattr(self, "_due", None)
        if due is None or QThread.currentThread() is not self.thread():
            return super().render()                 # being built / asked by a worker
        if not due.isActive():
            due.start()
        return None

    def render_now(self):
        self._due.stop()
        return super().render()

    def flush(self):
        if self._due.isActive():
            self.render_now()

    # ---- a drawn frame is shown, not drawn again -----------------------------------------
    # (PyVistaQt's names: _cb_frame is called when VTK finishes a frame, paintGL draws
    # the scene unless _in_paint says a draw is already running, then copies it over.)
    def _cb_frame(self, obj, evt):
        super()._cb_frame(obj, evt)                 # asks for a paint
        rw = self._RenderWindow
        self._fresh = rw is not None and not (rw.GetDoubleBuffer() and not rw.GetSwapBuffers())

    def update(self, *args):
        self._fresh = False                         # asked by someone else: draw
        super().update(*args)

    def resizeGL(self, w, h):
        self._fresh = False                         # another size: draw again
        super().resizeGL(w, h)

    def paintGL(self):
        show_only = self._fresh and not self._in_paint
        if show_only:
            self._in_paint = True                   # skips the draw, keeps the copy
        elif getattr(self, "_due", None) is not None:
            self._due.stop()                        # this paint draws the frame that was due
        try:
            super().paintGL()
        finally:
            if show_only:
                self._in_paint = False
            self._fresh = False


def make_view(parent=None):
    if os.environ.get("MESHVIEWER_PLAIN_VIEW"):
        return QtInteractor(parent, auto_update=False)
    return Viewport(parent)
