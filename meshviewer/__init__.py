"""Mesh Viewer internals. See README.md for the layout."""

__version__ = "2.5b4"       # single source: setup.py (app bundle) and About read it
#                             a beta: "2.5b1" (shown "2.5 beta 1"); a release: "2.5", "2.5.1"


def version_label(version=None):
    """"2.5b1" -> "2.5 beta 1"; a release stays as it is."""
    import re
    v = version or __version__
    m = re.fullmatch(r"([\d.]+)b(\d+)", v)
    return f"{m[1]} beta {m[2]}" if m else v


