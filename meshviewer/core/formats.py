"""File extension -> reader. The only place that knows which formats exist.

To add a format: write a reader in mesh/ or cad/ that returns
{name: pv.PolyData}, then add one line to FORMATS. A folder is an OpenFOAM case.
"""
from __future__ import annotations

import functools
import importlib
from pathlib import Path

from meshviewer.core.model import Model

# (extensions, kind, label, module, function)
# Longer extensions first so ".lb8.ugrid" wins over ".ugrid".
FORMATS = [
    # ---- meshes ----------------------------------------------------------
    ((".cgns",),                                     "mesh", "CGNS",  "mesh.cgns", "read_cgns"),
    ((".lb8.ugrid", ".b8.ugrid", ".lb4.ugrid",
      ".b4.ugrid", ".ugrid"),                        "mesh", "UGRID", "mesh.ugrid", "read_ugrid"),
    ((".msh",),                                      "mesh", "MSH",   "mesh.msh",  "read_msh"),
    # a case folder (or its polyMesh folder, or a .foam file in it)
    ((".foam",),                                     "mesh", "OpenFOAM", "mesh.openfoam", "read_openfoam"),
    # results on the boundaries (FUN3D _tec_boundary.dat, Tecplot ASCII)
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
    # ---- 2D drawings ---------------------------------------------------------
    ((".dxf",),                                      "cad",  "DXF",   "cad.dxf",   "read_dxf"),
]


def supported_extensions() -> list[str]:
    return [ext for exts, *_ in FORMATS for ext in exts]


def detect(path: Path):
    name = ".foam" if path.is_dir() else path.name.lower()
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
                     source=src, units="mm" if label in ("STEP", "IGES") else "",
                     part_info=src.part_info)             # (the same dict, kept up to date)

    out = getattr(mod, func)(path, debug=debug)
    parts, extra = out if isinstance(out, tuple) else (out, {})   # (parts, {"dim", "units"})
    model = Model(kind=kind, fmt=label, parts=parts, dim=int(extra.get("dim", 3)),
                  units=extra.get("units", ""))
    for key in ("times", "time_labels", "time_index", "field_units", "z_fields", "case"):
        if key in extra:
            setattr(model, key, extra[key])
    if label == "MSH":                                # Gmsh or Fluent, said by the file
        from meshviewer.core.mesh.msh import _kind
        model.fmt = "Gmsh" if _kind(path) == "gmsh" else "Fluent"
    if hasattr(mod, "read_volume") and model.dim == 3:    # CGNS, UGRID, .msh, OpenFOAM cells
        model.volume = extra.get("volume") or functools.partial(mod.read_volume, path,
                                                                debug=debug)
    if hasattr(mod, "cell_count") and model.dim == 3:     # from the header: quick
        try:
            model.n_cells = mod.cell_count(path) or None
        except Exception:                                 # noqa: BLE001
            model.n_cells = None
    return model
