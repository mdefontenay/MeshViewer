"""The tools of the inspector (the panel right of the 3D view), in three tabs:

    View      Mesh Quality, Section, Edit         how the model is shown and changed
    Measure   Info, Measure, Plots                numbers about it
    Analyze   CFD, Cell Quality, Results          CFD checks and solver results

(On screen they are "tools"; in the code a tool's fold-out box is a "section".)
Every tool is in its tab for every file. When one doesn't apply to the open file, it
says so in gray instead of its controls (`unavailable` returns the reason). The tab
shown and the tools open are remembered per file; a file opened for the first time
gets DEFAULT_TAB for its type (Model.file_type), a results file the Analyze tab.

To add a tool: write its panel in gui/panels/, add a SectionSpec here (with its tab),
and build it in Sidebar._build_sections (keyed by the same name).
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
    tab: str = "view"               # the inspector tab it is in (TABS)


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
        return "Not for 2D files yet: a section plot cuts 3D boundaries."


def _needs_fields(scene):
    if not solution_fields(scene.model.parts):
        return ("This file has no solution fields. Open a results file, such as the "
                "Tecplot .dat FUN3D writes (project_tec_boundary.dat).")


SECTIONS = (
    SectionSpec("info", "Info", "info", "What's in the file: size, faces, points",
                tab="measure"),
    SectionSpec("quality", "Mesh Quality", "mesh_quality",
                "How finely curved CAD faces are triangulated", _needs_exact_cad),
    SectionSpec("section", "Section", "section", "Cut the model with a plane", _needs_3d),
    SectionSpec("edit", "Edit", "edit", "Rotate, mirror or move the model", _needs_editable),
    SectionSpec("measure", "Measure", "measure", "Distances, points, angles, areas, volumes",
                tab="measure"),
    SectionSpec("cfd", "CFD", "cfd",
                "y+ estimate (meshes) · Inflation Layers (CAD)", _needs_3d_cfd,
                tab="analyze"),
    SectionSpec("cells", "Cell Quality", "cell_quality",
                "Skewness, aspect ratio, Jacobian and volume of the cells", _needs_mesh,
                tab="analyze"),
    SectionSpec("results", "Results", "results", "Color the boundaries by a solution field",
                _needs_fields, tab="analyze"),
    SectionSpec("plots", "Plots", "plots",
                "Plots under the 3D view: sections (cp along x/c…)",
                _needs_3d_plots, tab="measure"),
)
BY_KEY = {s.key: s for s in SECTIONS}

TABS = (("view", "View"), ("measure", "Measure"), ("analyze", "Analyze"))
IN_TAB = {key: [spec.key for spec in SECTIONS if spec.tab == key] for key, _ in TABS}

# the tab a file opens on the first time
DEFAULT_TAB = {"cad": "view", "mesh": "view", "mesh2d": "view", "drawing": "measure"}


def default_tab(scene):
    if solution_fields(scene.model.parts):          # a results file opens on its results
        return "analyze"
    return DEFAULT_TAB.get(scene.model.file_type, "view")


def default_open(scene):
    """The tools open the first time: Results for a results file, Measure for a drawing."""
    if solution_fields(scene.model.parts):
        return ["results"]
    return ["measure"] if scene.model.file_type == "drawing" else []
