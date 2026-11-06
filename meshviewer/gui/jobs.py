"""Background work (file reading, cell quality) so windows stay responsive.

    run_job(fn, on_done, on_failed=None)    # fn() runs on a worker thread

on_done / on_failed must be bound methods of a QObject (a window, a panel), not
lambdas: Qt then calls them on the main thread, where the UI may be touched.
"""
from __future__ import annotations

import traceback

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal


class _JobSignals(QObject):
    done = Signal(object)          # result
    failed = Signal(object)        # Exception


class Job(QRunnable):
    """Runs fn() on a worker thread; result / exception come back as signals
    (delivered on the main thread)."""

    def __init__(self, fn):
        super().__init__()
        self.fn = fn
        self.signals = _JobSignals()

    def run(self):
        try:
            self.signals.done.emit(self.fn())
        except Exception as exc:       # reported by the caller
            traceback.print_exc()
            self.signals.failed.emit(exc)


def run_job(fn, on_done, on_failed=None):
    """Start fn() in the background. Keep the returned job alive until it ends."""
    job = Job(fn)
    job.setAutoDelete(False)
    job.signals.done.connect(on_done)
    if on_failed is not None:
        job.signals.failed.connect(on_failed)
    QThreadPool.globalInstance().start(job)
    return job
