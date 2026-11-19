"""OpenFOAM cases, read with VTK's vtkOpenFOAMReader (ASCII or binary, gzipped or not).

What can be opened: a case folder (with constant/polyMesh), a constant/ or polyMesh/
folder, a .foam file in a case folder, or a decomposed case (processor*/constant/polyMesh).
The reader is pointed at a temporary case that links to the polyMesh folder(s) and to the
time folders that hold fields, with an empty .foam file: nothing is written into the
user's case. A `FoamCase` stays open with the model (`Model.case`): its readers are kept,
so the cells and other time steps read fast. The time steps — read field by field, kept
as float32 (core/mesh/openfoam_cache.py), read ahead — are core/mesh/openfoam_steps.py
(`step_arrays`, `volume_arrays`, `prefetch`, `known_ranges`, `varies`).

    3D  {patch: its faces}                    + volume(): the cells (internalMesh)
    2D  {"internalMesh": its cells, flat in XY} + {patch: its edges, as lines}

Time steps: the numbered folders with fields (`Model.times`, `time_labels`), the latest
shown (`time_index`). Fields: the volume scalars and vectors of that step, on the patches
(the faces' own values, and at the nodes) and on the cells; a vector V becomes Vx, Vy, Vz
and mag(V) (U: Ux, Uy, Uz, its magnitude is Speed); their units from the files'
dimensions (`Model.field_units`).

A case is 2D when it is one cell thick (OpenFOAM's usual 2D setup): it has `empty`
patches, and every boundary point lies on one of two parallel planes. The cells are the
empty faces on one plane (with their cells' values), the other patches the edges they
leave on that plane; both are turned so the plane is XY (z = 0).

read_openfoam returns (parts, {"dim", "units": "m", "times", "time_labels", "time_index",
"field_units", "case", "volume"}).
"""
from __future__ import annotations

import atexit
import os
import re
import tempfile
import threading
import weakref
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pyvista as pv

from meshviewer.core.field_kinds import SPEED
from meshviewer.core.mesh.openfoam_2d import OWNER, ZONE, flat_arrays, two_d as _two_d
from meshviewer.core.mesh.openfoam_cache import StepCache
from meshviewer.core.mesh.openfoam_steps import AXES, SYMM, TENSOR9, VELOCITY, Steps
from meshviewer.core.mesh.openfoam_files import (cells_in_note, fields_in, patch_values,
                                                  read_boundary, read_labels, time_folders)

REQUIRED = ("points", "faces", "owner", "neighbour", "boundary")
SKIPPED = {"processor", "processorCyclic"}          # boundaries between processors
VTK_SYMM = ("xx", "yy", "zz", "xy", "yz", "xz")    # the order VTK gives them in


@dataclass
class _Case:
    root: Path                                      # what the user opened (for messages)
    meshes: list = field(default_factory=list)      # [(link name, polyMesh, case folder)]


def _has(folder, name):
    return (folder / name).is_file() or (folder / f"{name}.gz").is_file()


def _check(poly, shown):
    missing = [n for n in REQUIRED if not _has(poly, n)]
    if missing:
        raise ValueError(f"The OpenFOAM mesh in “{shown}” is incomplete: "
                         f"{', '.join(missing)} {'is' if len(missing) == 1 else 'are'} missing.")


def _locate(path) -> _Case:
    """Where the polyMesh folder(s) and the time folders are, from whatever was picked."""
    path = Path(path)
    if path.is_file() and path.suffix.lower() == ".foam":
        path = path.parent
    if not path.is_dir():
        raise ValueError(f"“{path.name}” is not a folder: choose an OpenFOAM case folder.")
    if path.name == "polyMesh":
        poly = path
    elif (path / "polyMesh").is_dir() and path.name == "constant":
        poly = path / "polyMesh"
    elif (path / "constant" / "polyMesh").is_dir():
        poly = path / "constant" / "polyMesh"
    else:
        procs = sorted((p for p in path.glob("processor*")
                        if (p / "constant" / "polyMesh").is_dir()),
                       key=lambda p: int(re.sub(r"\D", "", p.name) or 0))
        if not procs:
            raise ValueError(f"“{path.name}” is not an OpenFOAM case: it has no "
                             "constant/polyMesh folder.")
        case = _Case(path)
        for p in procs:
            _check(p / "constant" / "polyMesh", f"{p.name}/constant/polyMesh")
            case.meshes.append((p.name, p / "constant" / "polyMesh", p))
        return case
    _check(poly, poly.relative_to(path.parent) if poly != path else path.name)
    folder = poly.parent.parent if poly.parent.name == "constant" else None
    return _Case(path, [("case", poly, folder)])


class FoamCase(Steps):
    """An open case: the temporary case of links and one reader per polyMesh folder."""

    def __init__(self, path):
        self.case = _locate(path)
        self.labels = time_folders(self.case.meshes[0][2])   # with fields, earliest first
        self.times = [float(t) for t in self.labels]
        self.time_index = len(self.labels) - 1 if self.labels else None   # the latest
        self._tmp = tempfile.TemporaryDirectory(prefix="meshviewer-foam-")
        ref = weakref.ref(self)              # quitting: reading ahead stops before the
        atexit.register(lambda: (c := ref()) is not None and c._quit())   # links go
        self.foams = []
        for name, poly, src in self.case.meshes:
            root = Path(self._tmp.name) / name
            (root / "constant").mkdir(parents=True)
            os.symlink(poly.resolve(), root / "constant" / "polyMesh")
            for t in self.labels:
                if src is not None and (src / t).is_dir():
                    os.symlink((src / t).resolve(), root / t)
            (root / "case.foam").write_text("")
            self.foams.append(root / "case.foam")
        self.boundaries = [read_boundary(poly) for _, poly, _ in self.case.meshes]
        self._readers = [None] * len(self.foams)
        self._lock = threading.RLock()                # one read at a time (UI and jobs)
        self.cache = StepCache()                      # (what, step, field) -> arrays
        self._steps_init()                            # its steps' fields (openfoam_steps)
        self._owners = {}                             # mesh -> its owner list (2D)
        self._flat = None                             # 2D: the reader's arrays -> the parts
        self.dim = None                               # 2 or 3, once the parts are read
        self._carry = None                            # the polyhedra split (volume)

    @property
    def label(self):
        """The time folder shown ("1", "0.5"), or None (the mesh only)."""
        return None if self.time_index is None else self.labels[self.time_index]

    def fields(self):
        """{field: ("scalar" | "vector", unit)} of the time shown."""
        src = self.case.meshes[0][2]
        return fields_in(src / self.label) if self.label is not None else {}

    def field_units(self):
        """{array name: the file's unit} as the parts carry them (vectors split)."""
        out = {}
        for name, (kind, unit) in self.fields().items():
            if kind in ("scalar", "surface"):
                out[name] = unit
            elif kind == "vector":
                out.update({f"{name}{c}": unit for c in AXES})
                out[SPEED if name == VELOCITY else f"mag({name})"] = unit
            else:
                out.update({f"{name}{c}": unit for c in (SYMM if kind == "symmTensor"
                                                          else TENSOR9)})
        return out

    def z_fields(self):
        """The out-of-plane components (2D cases): the vectors' z, the tensors' xz…zz."""
        out = []
        for n, (kind, _u) in self.fields().items():
            if kind == "vector":
                out.append(f"{n}z")
            elif kind in ("symmTensor", "tensor"):
                out += [f"{n}{c}" for c in (SYMM if kind == "symmTensor" else TENSOR9)
                        if "z" in c]
        return out

    # ---- reading --------------------------------------------------------------------------
    def _reader(self, i):
        r = self._readers[i]
        if r is None:
            from vtkmodules.vtkIOGeometry import vtkOpenFOAMReader   # (not `import vtk`:
            r = vtkOpenFOAMReader()                                  # every module, 1.4 s)
            r.SetFileName(str(self.foams[i]))
            r.SetCreateCellToPoint(1)                  # the fields at the nodes too
            r.SetReadZones(0)
            r.SetSkipZeroTime(0)
            r.UpdateInformation()
            self._readers[i] = r
        return r

    def _step(self, step):
        return self.time_index if step is None else step

    def _read(self, i, want, step=None, only=None):
        """{block: a copy} of mesh i at time step `step` (None: the one shown), with the
        patches `want(name)` accepts on ("internalMesh" is one of them); only: just these
        fields (None: all)."""
        step = self._step(step)
        with self._lock:
            r = self._reader(i)
            for k in range(r.GetNumberOfPatchArrays()):
                name = r.GetPatchArrayName(k)
                r.SetPatchArrayStatus(name, int(want(name.removeprefix("patch/")) and
                                                not name.startswith(("group/", "lagrangian/"))))
            if step is None:
                r.DisableAllCellArrays()
            else:
                r.EnableAllCellArrays()
                if only is not None:
                    for k in range(r.GetNumberOfCellArrays()):
                        name = r.GetCellArrayName(k)
                        r.SetCellArrayStatus(name, int(name in only))
                r.UpdateTimeStep(self.times[step])
            r.DisableAllPointArrays()
            r.DisableAllLagrangianArrays()
            r.Update()
            return _leaves(r.GetOutput())

    def _n_cells(self, i, owner):
        n = cells_in_note(self.case.meshes[i][1])
        if n is None:
            owner = self._owner(i) if owner is None else owner
            n = int(owner.max()) + 1 if len(owner) else 0
        return n

    def patches(self, step=None, only=None, cells=False):
        """({patch: surface with its fields}, {patch: type}, the cells or None) of every
        patch with faces, in the file's order. Empty patches' faces carry their cell
        (OWNER). cells: the cells too, in the same read (2D: the fields read once)."""
        types, per, grids, offset = {}, {}, [], 0
        for i, (_name, poly, _src) in enumerate(self.case.meshes):
            bnd = {n: b for n, b in self.boundaries[i].items()
                   if b["nFaces"] and b["type"] not in SKIPPED}
            for n, b in bnd.items():
                types.setdefault(n, b["type"])
            owner = None
            faces = self._face_fields(i, bnd, step, only)
            want = (lambda n: n in bnd or n == ZONE) if cells else (lambda n: n in bnd)
            for n, ds in self._read(i, want, step, only).items():
                if n == ZONE and cells:
                    grids.append(ds)
                    continue
                if n not in bnd or not ds.n_cells:
                    continue
                if bnd[n]["type"] == "empty":           # 2D: the cell behind each face
                    owner = self._owner(i) if owner is None else owner
                    s = bnd[n]["startFace"]
                    ds.cell_data[OWNER] = owner[s:s + ds.n_cells] + offset
                for f, vals in faces.items():          # phi: each face's own value
                    if n in vals and len(vals[n]) == ds.n_cells:
                        ds.cell_data[f] = vals[n]
                per.setdefault(n, []).append(ds)
            if len(self.case.meshes) > 1:
                offset += self._n_cells(i, owner)
        grid = _merge(grids) if grids else None
        grid = _split_vectors(grid) if grid is not None and grid.n_cells else None
        return {n: _split_vectors(_merge(per[n])) for n in types if n in per}, types, grid

    def _face_fields(self, i, bnd, step, only=None):
        """{field: {patch: values}} of the face fields (phi) of mesh i at a time step,
        read from the files (VTK doesn't)."""
        step = self._step(step)
        src = self.case.meshes[i][2]
        if step is None or src is None:
            return {}
        folder = src / self.labels[step]
        names = [(n, b["nFaces"]) for n, b in bnd.items()]
        return {f: patch_values(folder / f, names)
                for f, (kind, _u) in self.fields_at(step).items()
                if kind == "surface" and (only is None or f in only)}

    def _owner(self, i):
        """Mesh i's owner list (which cell owns each face), read once."""
        if i not in self._owners:
            self._owners[i] = read_labels(self.case.meshes[i][1] / "owner")
        return self._owners[i]

    def _quit(self):
        self.cache.stop()
        self.cache.wait(5)

    def cells(self, step=None, only=None):
        """The cells (internalMesh) with their fields, as the reader gives them."""
        grids = []
        for i in range(len(self.foams)):
            grids += [g for n, g in self._read(i, lambda n: n == ZONE, step, only).items()
                      if n == ZONE]
        grid = _merge(grids) if grids else None
        return _split_vectors(grid) if grid is not None and grid.n_cells else None

    def volume(self, debug=True):
        """The cells for Section and Cell Quality (polyhedra split), or None."""
        from meshviewer.core.mesh.volume import describe, split_polyhedra
        grid = self.cells()
        if grid is None:
            return None
        grid, split, self._carry = split_polyhedra(grid)
        if debug:
            print(f"  volume: {describe(grid)}"
                  + (f" · {split:,} polyhedra split into pyramids and tetra" if split else ""))
        return grid

    def parts(self, step=None, only=None):
        """(parts, dim) at time step `step` (None: the one shown); only: just these fields.
        Once a case is known to be 2D, its cells are read with the patches (one read)."""
        step = self._step(step)
        both = self.dim == 2 and step is not None
        patches, types, grid = self.patches(step, only, cells=both)
        if not patches:
            raise ValueError(f"No boundary faces found in “{self.case.root.name}”.")
        cells = (lambda: grid) if both else \
            (lambda: self.cells(step, only)) if step is not None else None
        flat, fmap = _two_d(patches, types, cells)
        for p in patches.values():
            p.cell_data.pop(OWNER, None)
        self.dim = 2 if flat is not None else 3
        if fmap is not None:
            self._flat = fmap                          # (the same for every step)
        return (flat, 2) if flat is not None else (patches, 3)

    def part_arrays(self, step, only):
        """{part: ({point arrays}, {cell arrays})} of a step's fields `only`: a 2D case
        through its map (no flat parts built again), else from the parts read."""
        if self._flat is not None and step is not None:
            patches, _types, grid = self.patches(step, only, cells=True)
            return flat_arrays(self._flat, patches, grid)
        parts, _dim = self.parts(step, only)
        return {n: ({k: np.asarray(p.point_data[k]) for k in p.point_data.keys()},
                    {k: np.asarray(p.cell_data[k]) for k in p.cell_data.keys()})
                for n, p in parts.items()}


def read_openfoam(path, debug=True):
    case = FoamCase(path)
    parts, dim = case.parts()
    if debug:
        procs = f" · {len(case.case.meshes)} processors" if len(case.case.meshes) > 1 else ""
        steps = (f" · {len(case.times)} time steps, showing {case.label}"
                 if case.times else " · mesh only")
        print(f"  OpenFOAM {dim}D mesh · {len(parts)} parts{procs}{steps}")
    extra = {"dim": dim, "units": "m", "times": list(case.times),
             "time_labels": list(case.labels), "time_index": case.time_index,
             "field_units": case.field_units(), "z_fields": case.z_fields(), "case": case}
    if dim == 3:
        extra["volume"] = lambda: case.volume(debug=debug)
    return parts, extra


def read_volume(path, debug=True):
    """The cells (internalMesh) as a pv.UnstructuredGrid, at the latest time."""
    return FoamCase(path).volume(debug=debug)


def cell_count(path):
    """Volume cells, from the owner files' notes ("nCells:…"); None when they don't say."""
    total = 0
    for _name, poly, _src in _locate(path).meshes:
        n = cells_in_note(poly)
        if n is None:
            return None
        total += n
    return total


# ---- the reader's output ---------------------------------------------------------------------
def _leaves(data):
    """{block name: a copy of the dataset} of a reader's output."""
    from vtkmodules.vtkCommonDataModel import vtkCompositeDataSet
    out = {}
    it = data.NewIterator()
    it.InitTraversal()
    while not it.IsDoneWithTraversal():
        obj = it.GetCurrentDataObject()
        name = it.GetCurrentMetaData().Get(vtkCompositeDataSet.NAME())
        copy = pv.PolyData() if obj.IsA("vtkPolyData") else pv.UnstructuredGrid()
        copy.deep_copy(obj)                           # no views into the reader's arrays
        copy.field_data.clear()
        out[name] = copy
        it.GoToNextItem()
    return out


def _merge(pieces):
    """One dataset from the same patch (or the cells) of each processor."""
    pieces = [p for p in pieces if p.n_cells]
    if len(pieces) == 1:
        return pieces[0]
    if isinstance(pieces[0], pv.PolyData):
        return pieces[0].append_polydata(*pieces[1:]).clean()
    return pv.merge(pieces, merge_points=True)


def _split_vectors(ds):
    """Each vector V -> Vx, Vy, Vz and mag(V) (U: no mag, Speed is its own); each tensor
    R -> Rxx, Rxy, Rxz, Ryy, Ryz, Rzz (symmetric; VTK gives xx yy zz xy yz xz) or its 9."""
    for data in (ds.point_data, ds.cell_data):
        for k in list(data.keys()):
            a = np.asarray(data[k])
            if k.startswith("__") or a.ndim != 2 or a.shape[1] not in (3, 6, 9):
                continue
            a = np.array(a, dtype=np.float64)
            names = {3: AXES, 6: VTK_SYMM, 9: TENSOR9}[a.shape[1]]
            for i, c in enumerate(names):
                data[f"{k}{c}"] = a[:, i].copy()
            if a.shape[1] == 3 and k != VELOCITY:
                data[f"mag({k})"] = np.linalg.norm(a, axis=1)
            del data[k]
    return ds
