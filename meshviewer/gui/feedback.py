"""What the window shows while it works or when something goes wrong.

    Spinner           a small turning ring in the toolbar while background work runs
                      (opening a file, another mesh quality, y+, cell quality); its hover
                      text says what is being done
    show_error(...)   a sheet that says what failed and what to do next, with
                      Report a Problem… (gui/report.py)
"""
from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QPainter, QPalette, QPen
from PySide6.QtWidgets import QMessageBox, QWidget


class Spinner(QWidget):
    """Hidden when idle. begin(text) / end(): nested jobs keep it turning."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(QSize(18, 18))
        self._angle = 0
        self._jobs = []
        self._timer = QTimer(self)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._turn)
        self.setAccessibleName("Working")
        self.slot = None              # its QToolBar action: a toolbar widget hides through it
        self._show(False)

    @property
    def busy(self):
        return bool(self._jobs)

    def begin(self, text):
        self._jobs.append(text)
        self.setToolTip("\n".join(self._jobs))
        self.setAccessibleDescription(text)
        self._show(True)
        self._timer.start()

    def end(self, *_):
        if self._jobs:
            self._jobs.pop(0)
        self.setToolTip("\n".join(self._jobs))
        if not self._jobs:
            self._timer.stop()
            self._show(False)

    def _show(self, on):
        (self.slot or self).setVisible(on)

    def _turn(self):
        self._angle = (self._angle + 30) % 360
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = self.palette().color(QPalette.WindowText)
        r = QRectF(3, 3, 12, 12)
        c.setAlphaF(0.18)
        p.setPen(QPen(c, 2))
        p.drawEllipse(r)
        c.setAlphaF(0.75)
        p.setPen(QPen(c, 2, Qt.SolidLine, Qt.RoundCap))
        p.drawArc(r, -self._angle * 16, 100 * 16)
        p.end()


def show_error(window, text, detail, next_step="", file_name="", warning=False):
    """A sheet on `window`: what failed (text), why (detail), what to do (next_step)."""
    from meshviewer.gui.report import report_problem
    box = QMessageBox(window)
    box.setWindowModality(Qt.WindowModal)              # a sheet on macOS
    box.setIcon(QMessageBox.Warning if warning else QMessageBox.Critical)
    box.setText(text)
    box.setInformativeText("\n\n".join(t for t in (detail, next_step) if t))
    report = box.addButton("Report a Problem…", QMessageBox.HelpRole)
    box.addButton(QMessageBox.Ok)
    box.setDefaultButton(QMessageBox.Ok)
    box.finished.connect(lambda _: box.clickedButton() is report
                         and report_problem(f"{text}\n{detail}", file_name))
    window._error_box = box                            # kept alive while it shows
    box.open()
    return box
