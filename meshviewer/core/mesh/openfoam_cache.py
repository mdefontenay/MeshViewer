"""Time steps' fields kept in memory (OpenFOAM), and read ahead.

    cache = StepCache()
    cache.put(key, value)      value: {part: ({point arrays}, {cell arrays})} or
                               ({point arrays}, {cell arrays}); kept as float32
    cache.get(key)             or None
    cache.prefetch(steps, load)    load(step) for each, in a background thread (a new
                               call cancels the last)

Everything read stays while the case is open (no budget, nothing evicted): float32
halves what float64 would take. Keys are (what, step, field): ("field", 3, "U") is U's
arrays (Ux, Uy, Uz) on every part at step 3; ("cells", 3, None) the cells' fields.
No Qt in here.
"""
from __future__ import annotations

import threading

import numpy as np


def _compact(arrays):
    return {k: (np.array(a, dtype=np.float32) if np.issubdtype(np.asarray(a).dtype, np.floating)
                else np.array(a)) for k, a in arrays.items()}


def _size(value):
    pairs = value.values() if isinstance(value, dict) else [value]
    return sum(a.nbytes for pair in pairs for arrays in pair for a in arrays.values())


class StepCache:
    def __init__(self):
        self._items = {}                          # key -> value
        self.nbytes = 0
        self._lock = threading.RLock()
        self._stop = None                         # the read-ahead's cancel flag
        self._thread = None

    def __contains__(self, key):
        return key in self._items

    def get(self, key):
        return self._items.get(key)

    def put(self, key, value):
        """Keep `value` (its arrays as float32); returns what is kept."""
        if isinstance(value, dict):
            value = {n: (_compact(p), _compact(c)) for n, (p, c) in value.items()}
        else:
            value = (_compact(value[0]), _compact(value[1]))
        with self._lock:
            old = self._items.get(key)
            if old is not None:
                self.nbytes -= _size(old)
            self._items[key] = value
            self.nbytes += _size(value)
        return value

    # ---- reading ahead ----------------------------------------------------------------------
    def prefetch(self, steps, load):
        """load(step) for each step, in turn, in a background thread — stopped by the next
        call (or `stop`)."""
        self.stop()
        flag = threading.Event()
        self._stop = flag

        def run():
            for s in steps:
                if flag.is_set():
                    return
                try:
                    load(s)
                except Exception as exc:              # noqa: BLE001  (shown when asked)
                    print(f"time step {s} could not be read ahead: {exc}")
                    return
        self._thread = threading.Thread(target=run, name="timeline-prefetch", daemon=True)
        self._thread.start()

    def stop(self):
        if self._stop is not None:
            self._stop.set()

    def wait(self, timeout=None):
        """(Tests) until the read-ahead is done."""
        if self._thread is not None:
            self._thread.join(timeout)
