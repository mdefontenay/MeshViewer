"""BREP reader (.brep / .brp) — OpenCASCADE's native exact-geometry format.

CAD format (FreeCAD, gmsh, CadQuery and Salome can save it). No part names:
one part per solid. Shared logic lives in occt.py.
"""
from __future__ import annotations

from .occt import DEFAULT_QUALITY, CadFile, read_brep_shape


def open_refinable(path, debug=True):
    return CadFile(path, read_brep_shape(path), debug=debug)


def read_brep(path, debug=True, quality=DEFAULT_QUALITY):
    return open_refinable(path, debug).tessellate(quality)
