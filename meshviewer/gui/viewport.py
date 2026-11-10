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

make_view() gives this widget — or PyVistaQt's own, untouched, when the environment
variable MESHVIEWER_PLAIN_VIEW is set (to compare, should a picture ever look stale).
"""
from __future__ import annotations

import os

from PySide6.QtCore import QThread, QTimer
from pyvistaqt import QtInteractor


class Viewport(QtInteractor):
    def __init__(self, parent=None):
        self._fresh = False                         # VTK's last frame is not on screen yet
        super().__init__(parent, auto_update=False)
        self._due = QTimer(self)
        self._due.setSingleShot(True)
        self._due.setInterval(0)                    # as soon as the event is handled
        self._due.timeout.connect(self.render_now)

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
