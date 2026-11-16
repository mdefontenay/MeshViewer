"""The parts list's filter: a name, and limits on size and volume. No Qt.

    bolt                    names containing "bolt"
    size > 20               parts whose bounding-box diagonal is over 20
    volume < 1000           parts enclosing under 1000 (unit³)
    bracket size>=5 vol<50  all of these

Size and volume are in the toolbar's unit (cubed for volume). A part that encloses no
volume (an open surface) never passes a volume limit.
"""
from __future__ import annotations

import operator
import re

LIMIT = re.compile(r"\b(size|volume|vol)\s*(<=|>=|<|>|=)\s*([-+]?(?:\d+\.?\d*|\.\d+)(?:e[-+]?\d+)?)",
                   re.I)
OPS = {"<": operator.lt, "<=": operator.le, ">": operator.gt, ">=": operator.ge,
       "=": lambda a, b: abs(a - b) <= 1e-9 * max(abs(a), abs(b), 1e-300)}


def parse(text):
    """(name text, lowercase; [(\"size\" | \"volume\", op, limit)])."""
    limits = []
    for m in LIMIT.finditer(text or ""):
        prop = "size" if m.group(1).lower() == "size" else "volume"
        limits.append((prop, m.group(2), float(m.group(3))))
    name = LIMIT.sub(" ", text or "")
    return " ".join(name.split()).lower(), limits


def passes(values, limits):
    """values: {"size": float, "volume": float or None} -> all limits met?"""
    for prop, op, limit in limits:
        v = values.get(prop)
        if v is None or not OPS[op](v, limit):
            return False
    return True
