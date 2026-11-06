"""What every reader hands to the UI.

Each reader (mesh/ or cad/) returns {name: pv.PolyData}. formats.load() wraps
that into a Model so the window code never needs to know the file type.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

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
    # NEW (v2.19), meshes only: reads the 3D cells on demand (-> pv.UnstructuredGrid
    # or None) for the section's "Show cut mesh". None = format without volume cells.
    volume: Optional[Callable[[], object]] = None

    @property
    def is_cad(self) -> bool:
        return self.kind == "cad"

    @property
    def kind_title(self) -> str:    # used in the window title
        return "CAD" if self.is_cad else "Mesh"

    @property
    def group_title(self) -> str:   # header of the toggle list
        return "Parts" if self.is_cad else "Boundaries"


class MissingDependency(RuntimeError):
    """Raised when an optional Python package for one format isn't installed."""

    def __init__(self, package: str, purpose: str):
        self.package = package
        self.purpose = purpose
        super().__init__(f"Opening {purpose} needs the '{package}' Python package.")
