"""IGES reader (.iges / .igs) — exact CAD geometry via OpenCASCADE.

CAD format. IGES often stores bare surfaces rather than solids: unnamed
surfaces are grouped into one "Surfaces" part. Shared logic lives in occt.py.
"""
from __future__ import annotations

from meshviewer.core.model import MissingDependency
from meshviewer.core.cad.occt import DEFAULT_QUALITY, CadFile, read_xcaf

try:
    from OCP.IGESCAFControl import IGESCAFControl_Reader
except ImportError as exc:
    raise MissingDependency("cadquery-ocp", "IGES files") from exc


def open_refinable(path, debug=True):
    leaves, doc = read_xcaf(path, IGESCAFControl_Reader, "IGES")
    return CadFile(path, leaves, keepalive=doc, debug=debug)


def read_iges(path, debug=True, quality=DEFAULT_QUALITY):
    return open_refinable(path, debug).tessellate(quality)
