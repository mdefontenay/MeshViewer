"""What every reader hands to the UI.

Each reader (mesh/ or cad/) returns {name: pv.PolyData}. formats.load() wraps
that into a Model so the window code never needs to know the file type.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np
import pyvista as pv


@dataclass
class Model:
    kind: str                       # "mesh" or "cad"
    fmt: str                        # "CGNS", "UGRID", "STEP", "STL"
    parts: dict[str, pv.PolyData] = field(default_factory=dict)
    # Only for formats whose display mesh can be regenerated (STEP):
    retessellate: Optional[Callable[[int], dict]] = None   # level -> new parts
    quality_levels: list[str] = field(default_factory=list)
    quality: int = 0
    # Exact CAD geometry (STEP/IGES/BREP) for exact area / volume, else None.
    source: Optional[object] = None
    units: str = ""                 # "mm" when the reader converts to millimetres
    dim: int = 3                    # 2: a 2D mesh or a drawing (flat, z = 0)
    file_units: str = ""            # the unit the file itself states ("" = none); set below
    # Meshes only: reads the 3D cells on demand (-> pv.UnstructuredGrid
    # or None) for the section's "Show cut mesh". None = format without volume cells.
    volume: Optional[Callable[[], object]] = None
    # What the file says about each part (STEP / IGES: core/cad/occt.CadFile.part_info):
    # name -> {"path": assemblies above it, "color": "#rrggbb" or None, "material"}
    part_info: dict = field(default_factory=dict)
    # Volume cells in the file (CGNS, UGRID: from their headers), or None
    n_cells: Optional[int] = None
    # Time steps with fields (OpenFOAM: its time folders, earliest first; [] = one or none),
    # their folder names, and the one shown (an index, the latest at first)
    times: list = field(default_factory=list)
    time_labels: list = field(default_factory=list)
    time_index: Optional[int] = None
    # The unit each solution field is in, as the file says ({"p": "m²/s²"}); Contours'
    # Unit in file starts there
    field_units: dict = field(default_factory=dict)
    # The z components of the file's vectors ("Uz", "UMeanz"): left out on a 2D file
    z_fields: list = field(default_factory=list)
    # An open case kept for reading its cells and other time steps (OpenFOAM: FoamCase)
    case: Optional[object] = None
    # Edit section: rotations / mirrors (3×3 integers) and move applied so
    # far — new point = transform @ original + offset. Parts are moved in memory;
    # Export saves the result.
    transform: np.ndarray = field(default_factory=lambda: np.eye(3))
    offset: np.ndarray = field(default_factory=lambda: np.zeros(3))

    @property
    def editable(self) -> bool:
        """Edit works on triangle / polygon data: meshes and STL, OBJ, PLY,
        glTF, VRML. Exact CAD (STEP, IGES, BREP) keeps its geometry in
        OpenCASCADE, so it can't be rotated / mirrored here."""
        return self.source is None

    @property
    def edited(self) -> bool:
        return not np.array_equal(self.transform, np.eye(3)) or bool(np.any(self.offset))

    @property
    def is_cad(self) -> bool:
        return self.kind == "cad"

    @property
    def file_type(self) -> str:
        """What the sidebar sections check: "cad", "mesh" (3D), "mesh2d" or "drawing"."""
        if self.dim == 2:
            return "drawing" if self.is_cad else "mesh2d"
        return "cad" if self.is_cad else "mesh"

    def __post_init__(self):
        self.file_units = self.file_units or self.units   # before the user picks one

    @property
    def kind_title(self) -> str:    # used in the window title
        return {"drawing": "Drawing", "mesh2d": "2D mesh"}.get(self.file_type,
                                                              "CAD" if self.is_cad else "Mesh")

    @property
    def cell_word(self) -> str:     # what the summary counts
        return "segments" if self.file_type == "drawing" else "faces"

    @property
    def group_title(self) -> str:   # header of the toggle list
        if self.file_type == "drawing":
            return "Layers"
        if self.file_type == "mesh2d":
            return "Faces & Boundaries"
        return "Parts" if self.is_cad else "Boundaries"

    @property
    def item_words(self) -> tuple[str, str]:   # "1 boundary selected", "3 boundaries…"
        return {"drawing": ("layer", "layers"), "mesh": ("boundary", "boundaries")}.get(
            self.file_type, ("part", "parts"))


# Mesh quality of exact CAD (STEP, IGES, BREP), coarsest first: the names of
# core/cad/occt.QUALITY_LEVELS (kept here so Settings can list them without OpenCASCADE)
CAD_QUALITY_NAMES = ("Very coarse", "Coarse", "Medium", "Fine", "Very fine")


class MissingDependency(RuntimeError):
    """Raised when an optional Python package for one format isn't installed."""

    def __init__(self, package: str, purpose: str):
        self.package = package
        self.purpose = purpose
        super().__init__(f"Opening {purpose} needs the '{package}' Python package.")
