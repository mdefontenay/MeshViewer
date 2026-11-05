"""STEP reader (.step / .stp) — exact CAD geometry via OpenCASCADE.

CAD format. Part names + placements from the STEP assembly tree; mesh quality
adjustable from the side panel. Shared logic lives in occt.py.
"""
from __future__ import annotations

from ..model import MissingDependency
from .occt import DEFAULT_QUALITY, CadFile, read_xcaf

try:
    from OCP.STEPCAFControl import STEPCAFControl_Reader
except ImportError as exc:
    raise MissingDependency("cadquery-ocp", "STEP files") from exc


def open_refinable(path, debug=True):
    leaves, doc = read_xcaf(path, STEPCAFControl_Reader, "STEP")
    return CadFile(path, leaves, keepalive=doc, debug=debug)


def read_step(path, debug=True, quality=DEFAULT_QUALITY):
    return open_refinable(path, debug).tessellate(quality)
