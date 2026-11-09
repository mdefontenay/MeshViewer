"""Already-triangulated CAD exports: OBJ, PLY, glTF/GLB, VRML (via VTK).

CAD format, no extra packages. These files store triangles, not exact
geometry, so there is no "Mesh quality" slider for them. Parts:
  * OBJ   — one part per group ('g' name), else per material
  * glTF  — one part per mesh node (node / mesh names when the file has them)
  * VRML  — one part per shape
  * PLY   — a single part
Note: glTF is Y-up by definition, so models exported from Z-up CAD tools
usually come in rotated.
"""
from __future__ import annotations

import re

import numpy as np
import pyvista as pv
from vtkmodules.vtkFiltersGeometry import vtkDataSetSurfaceFilter

_GENERIC = re.compile(r"^(None|Block-\d+|Node_\d+|Mesh_\d+|Primitive_\d+|\d+)?$")


def _surface(ds):
    if not isinstance(ds, pv.PolyData):
        f = vtkDataSetSurfaceFilter()
        f.SetInputData(ds)
        f.Update()
        ds = pv.wrap(f.GetOutput())
    return ds.clean() if ds.n_cells else None


def _unique(name, taken):
    k, base = 2, name
    while name in taken:
        name = f"{base} ({k})"
        k += 1
    return name


# ---- OBJ ------------------------------------------------------------------
def _obj_group_names(path):
    names = []
    with open(path, "r", errors="replace") as f:
        for line in f:
            if line.startswith("g ") or line.rstrip() == "g":
                names.append(line[1:].strip() or f"Group {len(names) + 1}")
    return names


def _split_obj(path, poly):
    cd, fd = poly.cell_data, poly.field_data
    groups = np.asarray(cd["GroupIds"]).astype(int) if "GroupIds" in cd else None
    if groups is not None and len(np.unique(groups)) > 1:
        names = _obj_group_names(path)
        ids, label = groups, lambda g: names[g] if g < len(names) else f"Group {g + 1}"
    elif "MaterialIds" in cd and len(np.unique(cd["MaterialIds"])) > 1:
        mats = list(fd["MaterialNames"]) if "MaterialNames" in fd else []
        ids = np.asarray(cd["MaterialIds"]).astype(int)
        label = lambda m: str(mats[m]) if m < len(mats) else f"Material {m}"   # noqa: E731
    else:
        return {path.stem: poly.clean()}
    parts = {}
    for g in np.unique(ids):
        sub = _surface(poly.extract_cells(np.flatnonzero(ids == g)))
        if sub is not None:
            parts[_unique(label(int(g)), parts)] = sub
    return parts


# ---- multi-block (glTF, VRML) -----------------------------------------------
def _walk(block, path, out):
    for i in range(block.n_blocks):
        child, name = block[i], block.get_block_name(i) or ""
        if isinstance(child, pv.MultiBlock):
            _walk(child, path + [name], out)
        elif child is not None and child.n_cells:
            out.append((path + [name], child))


def _best_name(path_names, fallback):
    for n in reversed(path_names):           # deepest meaningful name wins
        if not _GENERIC.match(str(n)):
            return str(n)
    return fallback


def read_tessellated(path, debug=True):
    data = pv.read(str(path))
    if isinstance(data, pv.MultiBlock):
        leaves = []
        _walk(data, [], leaves)
        parts = {}
        for i, (names, ds) in enumerate(leaves, 1):
            poly = _surface(ds)
            if poly is not None:
                fallback = path.stem if len(leaves) == 1 else f"Part {i}"
                parts[_unique(_best_name(names, fallback), parts)] = poly
    elif path.suffix.lower() == ".obj":
        parts = _split_obj(path, data)
    else:
        poly = _surface(data)
        parts = {path.stem: poly} if poly is not None else {}
    if debug:
        print(f"  {len(parts)} part(s), {sum(p.n_cells for p in parts.values()):,} faces")
    return parts
