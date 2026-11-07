"""File extension -> reader. The only place that knows which formats exist.

To add a format: write a reader in mesh/ or cad/ that returns
{name: pv.PolyData}, then add one line to FORMATS.
"""
from __future__ import annotations

import functools
import importlib
from pathlib import Path

from .model import Model

# (extensions, kind, label, module, function)
# Longer extensions first so ".lb8.ugrid" wins over ".ugrid".
FORMATS = [
    # ---- meshes ----------------------------------------------------------
    ((".cgns",),                                     "mesh", "CGNS",  "mesh.cgns", "read_cgns"),
    ((".lb8.ugrid", ".b8.ugrid", ".lb4.ugrid",
      ".b4.ugrid", ".ugrid"),                        "mesh", "UGRID", "mesh.ugrid", "read_ugrid"),
    # NEW (v2.15): results on the boundaries (FUN3D _tec_boundary.dat, Tecplot ASCII)
    ((".dat",),                                      "mesh", "Tecplot", "mesh.tecplot", "read_tecplot"),
    # ---- CAD: exact geometry (OpenCASCADE, adjustable mesh quality) ------
    ((".step", ".stp"),                              "cad",  "STEP",  "cad.step",  "read_step"),
    ((".iges", ".igs"),                              "cad",  "IGES",  "cad.iges",  "read_iges"),
    ((".brep", ".brp"),                              "cad",  "BREP",  "cad.brep",  "read_brep"),
    # ---- CAD: already triangulated exports --------------------------------
    ((".stl",),                                      "cad",  "STL",   "cad.stl",   "read_stl"),
    ((".obj",),                                      "cad",  "OBJ",   "cad.tessellated", "read_tessellated"),
    ((".ply",),                                      "cad",  "PLY",   "cad.tessellated", "read_tessellated"),
    ((".gltf", ".glb"),                              "cad",  "glTF",  "cad.tessellated", "read_tessellated"),
    ((".wrl", ".vrml"),                              "cad",  "VRML",  "cad.tessellated", "read_tessellated"),
]


def supported_extensions() -> list[str]:
    return [ext for exts, *_ in FORMATS for ext in exts]


def detect(path: Path):
    name = path.name.lower()
    for exts, kind, label, module, func in FORMATS:
        if any(name.endswith(e) for e in exts):
            return kind, label, module, func
    raise ValueError(
        f"Unrecognized file type: {path.name}\n"
        f"Supported: {', '.join(supported_extensions())}"
    )


def load(path: Path, debug: bool = True, quality: int | None = None) -> Model:
    kind, label, module, func = detect(path)
    # Readers are imported only when needed, so a missing optional package
    # (cadquery-ocp for STEP, h5py for CGNS) never blocks the other formats.
    mod = importlib.import_module(f"{__package__}.{module}")
    print(f"  format: {label} ({kind})")

    # Formats that can be re-tessellated (STEP) keep their source in memory.
    if hasattr(mod, "open_refinable"):
        src = mod.open_refinable(path, debug=debug)
        q = mod.DEFAULT_QUALITY if quality is None else quality
        return Model(kind=kind, fmt=label, parts=src.tessellate(q),
                     retessellate=src.tessellate, quality_levels=list(src.levels), quality=q,
                     source=src, units="mm" if label in ("STEP", "IGES") else "")

    model = Model(kind=kind, fmt=label, parts=getattr(mod, func)(path, debug=debug))
    if hasattr(mod, "read_volume"):                 # NEW (v2.7): CGNS / UGRID volume cells
        model.volume = functools.partial(mod.read_volume, path, debug=debug)
    return model
