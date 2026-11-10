"""The sample files that come with the app (resources/samples/), for the welcome screen and
File ▸ Open Sample.

    SAMPLES                       [(title, what it shows, file name)]
    sample_path(file name)        where it is (the source folder, or inside the app)
    available()                   [(title, what it shows, path)] of the ones present
    is_sample(path)               a file of the app's own (read-only: save elsewhere)
"""
from __future__ import annotations

import os
from pathlib import Path

SAMPLES = (
    ("ONERA M6 Wing", "CGNS mesh: wing, symmetry plane, far field", "ONERA M6 wing.cgns"),
    ("Avionics Bay", "STEP assembly: flight computers, batteries", "avbay.step"),
)


def _folders():
    here = Path(__file__).resolve().parents[2] / "resources" / "samples"     # from source
    out = [here]
    if os.environ.get("RESOURCEPATH"):                                       # the app (py2app)
        out.insert(0, Path(os.environ["RESOURCEPATH"]) / "samples")
    return out


def sample_path(name):
    for folder in _folders():
        p = folder / name
        if p.exists():
            return p
    return None


def available():
    return [(title, what, p) for title, what, name in SAMPLES if (p := sample_path(name))]


def is_sample(path):
    try:
        p = Path(path).resolve()
    except (OSError, TypeError):
        return False
    return any(folder.resolve() in p.parents for folder in _folders() if folder.exists())
