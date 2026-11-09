"""The sidebar's sections: the one list of what the icon bar can show.

Every section is listed for every file. When one doesn't apply to the open file,
it says so in grey instead of its controls (`unavailable` returns the reason).
Which sections are on is remembered per file; a file opened for the first time
gets DEFAULTS for its type (Model.file_type).

To add a section: write its panel in gui/panels/, add a SectionSpec here, and
build it in Sidebar._build_sections (keyed by the same name).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from meshviewer.core.fields import solution_fields


@dataclass(frozen=True)
class SectionSpec:
    key: str
    title: str
    icon: str                       # gui/icons.py name
    tip: str                        # what it is for (docs; the hover shows the title only)
    unavailable: Callable[[object], Optional[str]] = lambda scene: None   # reason, or None
    analysis: bool = False          # also in the toolbar's Analysis Tools menu


def _needs_exact_cad(scene):
    if not scene.can_retessellate:
        return "Only for STEP, IGES and BREP files: this file is already made of triangles."


def _needs_editable(scene):
    if not scene.model.editable:
        return ("Not for STEP, IGES or BREP files yet: their exact geometry can't be moved "
                "here. Meshes and STL, OBJ, PLY, glTF and VRML files can.")


def _needs_mesh(scene):
    t = scene.model.file_type
    if t == "drawing":
        return "Not for drawings: a DXF has no cells to check."
    if t not in ("mesh", "mesh2d"):
        return "Only for meshes (CGNS, UGRID, .msh): CAD files have no cells to check."


def _needs_3d(scene):
    if scene.model.dim == 2:
        return "Not for 2D files: they are flat, there is nothing to cut."


def _needs_3d_cfd(scene):
    if scene.model.dim == 2:
        return ("Not for 2D files yet: the y+ estimate and the inflation layers need 3D walls "
                "(a 3D mesh or a CAD model).")


def _needs_3d_plots(scene):
    if scene.model.dim == 2:
        return "Not for 2D files yet: a cross section cuts 3D boundaries."


def _needs_fields(scene):
    if not solution_fields(scene.model.parts):
        return ("This file has no solution fields. Open a results file, such as the "
                "Tecplot .dat FUN3D writes (project_tec_boundary.dat).")


SECTIONS = (
    SectionSpec("info", "Info", "info", "What's in the file: size, faces, points"),
    SectionSpec("quality", "Mesh quality", "mesh_quality",
                "How finely curved CAD faces are triangulated", _needs_exact_cad),
    SectionSpec("section", "Section", "section", "Cut the model with a plane", _needs_3d),
    SectionSpec("edit", "Edit", "edit", "Rotate, mirror or move the model", _needs_editable),
    SectionSpec("measure", "Measure", "measure", "Distances, points, angles, areas, volumes"),
    SectionSpec("cfd", "CFD", "cfd",
                "y+ and inflation layers (meshes: y+ estimate · CAD: CFD mode)", _needs_3d_cfd,
                analysis=True),
    SectionSpec("cells", "Cell quality", "cell_quality",
                "Skewness, aspect ratio, Jacobian and volume of the cells", _needs_mesh,
                analysis=True),
    SectionSpec("results", "Results", "results", "Colour the boundaries by a solution field",
                _needs_fields, analysis=True),
    SectionSpec("plots", "Plots", "plots",
                "Measurements plotted under the 3D view: cross sections (cp along x/c…)",
                _needs_3d_plots, analysis=True),
)
BY_KEY = {s.key: s for s in SECTIONS}

# on the first time a file is opened
DEFAULTS = {"cad": ("quality", "section", "measure"),
            "mesh": ("section", "edit", "measure"),
            "mesh2d": ("edit", "measure", "cells"),
            "drawing": ("measure",)}


def default_sections(scene):
    on = list(DEFAULTS.get(scene.model.file_type, DEFAULTS["mesh"]))
    if solution_fields(scene.model.parts):          # a results file opens on its results
        on.append("results")
    return on
