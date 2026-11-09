"""OpenCASCADE core shared by the exact-geometry CAD readers (STEP, IGES, BREP).

Needs: pip install cadquery-ocp

A CadFile holds the B-rep shapes in memory and turns them into
{part_name: pv.PolyData} at any of the QUALITY_LEVELS (the side panel's
"Mesh quality" slider), one triangulated surface per solid. Part names and
assembly placements come from the file's assembly tree when it has one
(STEP, IGES); repeated instances keep their own names and positions.
The triangulation is for display only: curved faces become facets.
"""
from __future__ import annotations

import re

import numpy as np
import pyvista as pv

from meshviewer.core.model import MissingDependency

try:
    from OCP.BRep import BRep_Tool
    from OCP.BRepBndLib import BRepBndLib
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    from OCP.BRepMesh import BRepMesh_IncrementalMesh
    from OCP.BRepTools import BRepTools
    from OCP.Bnd import Bnd_Box
    from OCP.BRep import BRep_Builder
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.TopoDS import TopoDS_Iterator, TopoDS_Shape
    from OCP.TCollection import TCollection_ExtendedString
    from OCP.TDataStd import TDataStd_Name
    from OCP.TDF import TDF_Label
    from OCP.TDocStd import TDocStd_Document
    from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED, TopAbs_SOLID
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopLoc import TopLoc_Location
    from OCP.TopoDS import TopoDS
    from OCP.XCAFDoc import XCAFDoc_DocumentTool, XCAFDoc_ShapeTool
except ImportError as exc:  # only needed for STEP / IGES / BREP files
    raise MissingDependency("cadquery-ocp", "STEP, IGES and BREP files") from exc

try:                                    # cadquery-ocp 7.x
    from OCP.TDF import TDF_LabelSequence
except ImportError:                     # cadquery-ocp 8.x moved it
    from OCP.collections import Sequence_TDF_Label as TDF_LabelSequence

_as_face = getattr(TopoDS, "Face_s", None) or TopoDS.Face   # 7.x: Face_s, 8.x: Face
_as_edge = getattr(TopoDS, "Edge_s", None) or TopoDS.Edge


# ---- Tessellation settings ------------------------------------------------
# (label, max chord error as a fraction of model size, max angle between facets in rad)
QUALITY_LEVELS = [
    ("Very coarse", 5e-3, 0.80),
    ("Coarse",      2e-3, 0.50),
    ("Medium",      1e-3, 0.35),     # ~18 facets per full circle
    ("Fine",        3e-4, 0.20),
    ("Very fine",   1e-4, 0.10),     # ~63 facets per full circle
]
DEFAULT_QUALITY = 2


# ---------------------------------------------------------------------------
# Assembly tree -> list of (name, located shape)
# ---------------------------------------------------------------------------

_GENERIC_TOPO = re.compile(r"^(face|shell|solid|compound|compsolid|wire|edge|vertex|shape)"
                           r"[\s_]*\d*$", re.I)


def _children_with_faces(shape):
    """Direct sub-shapes that contain faces (bodies inside a compound)."""
    out, it = [], TopoDS_Iterator(shape)
    while it.More():
        if TopExp_Explorer(it.Value(), TopAbs_FACE).More():
            out.append(it.Value())
        it.Next()
    return out


def _label_name(label) -> str:
    attr = TDataStd_Name()
    if label.FindAttribute(TDataStd_Name.GetID_s(), attr):
        name = attr.Get().ToExtString().strip()
        # Files written without names carry the translator's name — not useful.
        # ...and IGES often names entities after their type ("FACE", "SHELL").
        if name and not re.search(r"STEP translator|^\d+(\.\d+)*$|^=>\[", name) \
                and not _GENERIC_TOPO.match(name):
            return name
    return ""


def _collect_leaves(label, loc, inst_name, out):
    if XCAFDoc_ShapeTool.IsAssembly_s(label):
        comps = TDF_LabelSequence()
        XCAFDoc_ShapeTool.GetComponents_s(label, comps, False)
        for i in range(1, comps.Length() + 1):
            comp = comps.Value(i)
            ref = TDF_Label()
            XCAFDoc_ShapeTool.GetReferredShape_s(comp, ref)
            comp_loc = loc.Multiplied(XCAFDoc_ShapeTool.GetLocation_s(comp))
            _collect_leaves(ref, comp_loc, _label_name(comp) or _label_name(ref), out)
    else:
        shape = XCAFDoc_ShapeTool.GetShape_s(label)
        if not shape.IsNull():
            out.append((inst_name or _label_name(label), shape.Moved(loc)))


def _split_solids(name, shape):
    """One entry per solid; faces outside any solid become '<name> surfaces'."""
    solids = []
    exp = TopExp_Explorer(shape, TopAbs_SOLID)
    while exp.More():
        solids.append(exp.Current())
        exp.Next()
    has_free_faces = TopExp_Explorer(shape, TopAbs_FACE, TopAbs_SOLID).More()

    out = []
    for k, s in enumerate(solids, 1):
        out.append((name if len(solids) == 1 else f"{name}.{k}", [s], False))
    if has_free_faces:
        out.append((f"{name} surfaces" if solids else name, [shape], True))
    return out


# ---------------------------------------------------------------------------
# Tessellation -> PolyData
# ---------------------------------------------------------------------------

def _faces_to_poly(shapes, outside_solids_only):
    """(PolyData, [faces]). Each triangle carries cell data "face_id" = index of
    the CAD face it came from, so a click can be mapped back to the exact face."""
    pts_chunks, tri_chunks, id_chunks, faces_used, offset = [], [], [], [], 0
    for shape in shapes:
        exp = (TopExp_Explorer(shape, TopAbs_FACE, TopAbs_SOLID) if outside_solids_only
               else TopExp_Explorer(shape, TopAbs_FACE))
        while exp.More():
            face = _as_face(exp.Current())
            exp.Next()
            loc = TopLoc_Location()
            tri = BRep_Tool.Triangulation_s(face, loc)
            if tri is None or tri.NbTriangles() == 0:
                continue
            p, idx = _refined(face, tri)                  # no fans of thin slivers
            n_nodes = len(p)
            if not loc.IsIdentity():
                t = loc.Transformation()
                m = np.array([[t.Value(r, c) for c in range(1, 5)] for r in range(1, 4)])
                p = p @ m[:, :3].T + m[:, 3]
            if face.Orientation() == TopAbs_REVERSED:
                idx = idx[:, [0, 2, 1]]
            pts_chunks.append(p)
            tri_chunks.append(idx + offset)
            id_chunks.append(np.full(len(idx), len(faces_used), dtype=np.int32))
            faces_used.append(face)
            offset += n_nodes
    if not tri_chunks:
        return None, []
    tris = np.vstack(tri_chunks)
    cells = np.hstack([np.full((len(tris), 1), 3, dtype=np.int64), tris]).ravel()
    poly = pv.PolyData(np.vstack(pts_chunks), faces=cells)
    poly.cell_data["face_id"] = np.concatenate(id_chunks)
    return poly.clean(), faces_used


_REFINED = {}       # face (shared by repeated instances) -> its nodes and triangles
REFINE_BUDGET = 3.0     # seconds per meshing spent redoing faces; the rest keep OCCT's
_budget = [0.0]         # time.monotonic() when the current meshing's budget runs out


def _refined(face, tri):
    """Nodes (in the face's own frame) and triangles of a meshed face, through
    remesh.refine (no fans of thin slivers). Computed once per face and triangulation,
    so repeated instances of a part cost nothing more."""
    p = np.array([tri.Node(i).Coord() for i in range(1, tri.NbNodes() + 1)], dtype=np.float64)
    idx = np.array([tri.Triangle(i).Get() for i in range(1, tri.NbTriangles() + 1)],
                   dtype=np.int64) - 1
    key = (hash(face.TShape()), hash(p.tobytes()), hash(idx.tobytes()))
    hit = _REFINED.get(key)
    if hit is not None:
        return hit
    import time
    from meshviewer.core.cad.remesh import has_fans, refine
    if tri.HasUVNodes() and time.monotonic() < _budget[0] and has_fans(p, idx):
        uv = np.array([tri.UVNode(i).Coord() for i in range(1, tri.NbNodes() + 1)])
        surf = BRep_Tool.Surface_s(face, TopLoc_Location())        # in the face's own frame

        def evaluate(q):
            return np.array([surf.Value(float(u), float(v)).Coord() for u, v in q])
        try:
            better = refine(p, uv, idx, evaluate)
        except Exception:                                # noqa: BLE001 keep OCCT's triangles
            better = None
        if better is not None:
            p, idx = better
    if len(_REFINED) > 20000:
        _REFINED.clear()
    _REFINED[key] = (p, idx)
    return p, idx


def _props(shape, kind):
    """Exact surface area ('area') or volume ('volume') of a B-rep shape."""
    g = GProp_GProps()
    fn = {"area": "SurfaceProperties", "volume": "VolumeProperties"}[kind]
    (getattr(BRepGProp, fn + "_s", None) or getattr(BRepGProp, fn))(shape, g)
    return float(g.Mass())


def _unique(name, taken):
    if name not in taken:
        return name
    k = 2
    while f"{name} ({k})" in taken:
        k += 1
    return f"{name} ({k})"


# ---------------------------------------------------------------------------
# Reading: file -> list of (name, located shape)
# ---------------------------------------------------------------------------

def read_xcaf(path, reader_cls, label):
    """STEP / IGES with assembly names. Returns (leaves, doc); keep doc alive."""
    doc = TDocStd_Document(TCollection_ExtendedString("MDTV-XCAF"))
    reader = reader_cls()
    reader.SetNameMode(True)
    if reader.ReadFile(str(path)) != IFSelect_RetDone:
        raise RuntimeError(f"OpenCASCADE could not read this {label} file")
    reader.Transfer(doc)
    shape_tool = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    roots = TDF_LabelSequence()
    shape_tool.GetFreeShapes(roots)
    leaves = []
    for i in range(1, roots.Length() + 1):
        _collect_leaves(roots.Value(i), TopLoc_Location(), "", leaves)
    return leaves, doc


def read_brep_shape(path):
    """OpenCASCADE's native .brep: one shape, no names."""
    shape = TopoDS_Shape()
    if not BRepTools.Read_s(shape, str(path), BRep_Builder()) or shape.IsNull():
        raise RuntimeError("OpenCASCADE could not read this BREP file")
    return [("", shape)]


# ---------------------------------------------------------------------------
# Tessellation on demand
# ---------------------------------------------------------------------------

class CadFile:
    """B-rep shapes read once, tessellated at any quality level."""

    levels = [q[0] for q in QUALITY_LEVELS]

    def __init__(self, path, leaves, keepalive=None, debug=True):
        self.path = path
        self.leaves = leaves
        self._keepalive = keepalive         # e.g. the XCAF document owning the shapes
        self.debug = debug
        box = Bnd_Box()
        for _, s in leaves:
            BRepBndLib.Add_s(s, box)
        if leaves and not box.IsVoid():
            lo, hi = box.CornerMin(), box.CornerMax()   # works on OCP 7.x and 8.x
            self.diag = float(np.linalg.norm([hi.X() - lo.X(), hi.Y() - lo.Y(),
                                              hi.Z() - lo.Z()])) or 1.0
        else:
            self.diag = 1.0
        if debug:
            print(f"  {len(leaves)} shape(s), size {self.diag:.4g}")

    def tessellate(self, level=DEFAULT_QUALITY):
        """{part_name: PolyData} at QUALITY_LEVELS[level]."""
        label, lin, ang = QUALITY_LEVELS[max(0, min(level, len(QUALITY_LEVELS) - 1))]
        # Each distinct part is meshed once; repeated instances share it.
        import time
        _budget[0] = time.monotonic() + REFINE_BUDGET   # redoing fan faces: at most this long
        for _, s in self.leaves:
            BRepTools.Clean_s(s)            # drop the previous triangulation
            BRepMesh_IncrementalMesh(s, self.diag * lin, False, ang, True)

        parts, loose = {}, []
        self.part_faces, self.part_solids = {}, {}     # for exact area / volume
        single = len(self.leaves) == 1
        for i, (leaf_name, shape) in enumerate(self.leaves, 1):
            has_solid = TopExp_Explorer(shape, TopAbs_SOLID).More()
            if not leaf_name and not has_solid and not single:
                loose.append(shape)          # unnamed bare surfaces (typical of IGES)
                continue
            # Unnamed parts: file name for a single-shape file, "Part N" otherwise.
            leaf_name = leaf_name or (self.path.stem if single else f"Part {i}")
            bodies = [] if has_solid else _children_with_faces(shape)
            if len(bodies) > 1:             # surface bodies grouped in a compound (IGES)
                for k, body in enumerate(bodies, 1):
                    self._add(parts, f"{leaf_name} {k}", _faces_to_poly([body], False))
                continue
            for name, shapes, free_only in _split_solids(leaf_name, shape):
                self._add(parts, name, _faces_to_poly(shapes, free_only),
                          solids=None if free_only else shapes)
        if loose:                           # ...grouped into one part, not hundreds
            self._add(parts, "Surfaces", _faces_to_poly(loose, False))
        if self.debug:
            n = sum(p.n_cells for p in parts.values())
            print(f"  quality {label}: {len(parts)} parts, {n:,} triangles")
        return parts

    def _add(self, parts, name, result, solids=None):
        poly, faces = result
        if poly is not None and poly.n_cells:
            name = _unique(name, parts)
            parts[name] = poly
            self.part_faces[name] = faces
            if solids:
                self.part_solids[name] = solids

    # ---- exact measurements (from the CAD geometry, not the triangles) ------
    def exact_area(self, name, face_ids=None):
        faces = self.part_faces.get(name, [])
        ids = range(len(faces)) if face_ids is None else face_ids
        return sum(_props(faces[i], "area") for i in ids if 0 <= i < len(faces))

    # --- exact cut by a plane (the Cross section of CFD mode) ----------------
    def section(self, name, face_ids, origin, normal, deflection):
        """The cut of a part's faces (all, or face_ids) by the plane, from the CAD curves
        themselves — not the triangles: a list of N×3 point arrays, one per cut edge,
        no further than `deflection` from the curve (and no more than ~3° per step).
        Empty when the plane misses, None when the cut fails."""
        from OCP.BRepAdaptor import BRepAdaptor_Curve
        from OCP.BRepAlgoAPI import BRepAlgoAPI_Section
        from OCP.GCPnts import GCPnts_TangentialDeflection
        from OCP.TopAbs import TopAbs_EDGE
        from OCP.TopoDS import TopoDS_Compound
        from OCP.gp import gp_Dir, gp_Pln, gp_Pnt
        faces = self.part_faces.get(name, [])
        ids = range(len(faces)) if face_ids is None else face_ids
        builder, comp = BRep_Builder(), TopoDS_Compound()
        builder.MakeCompound(comp)
        n = 0
        for i in ids:
            if 0 <= i < len(faces):
                builder.Add(comp, faces[i])
                n += 1
        if not n:
            return []
        try:
            pln = gp_Pln(gp_Pnt(*map(float, origin)), gp_Dir(*map(float, normal)))
            sec = BRepAlgoAPI_Section(comp, pln, False)
            sec.Approximation(True)
            sec.Build()
            if not sec.IsDone():
                return None
            out = []
            exp = TopExp_Explorer(sec.Shape(), TopAbs_EDGE)
            while exp.More():
                curve = BRepAdaptor_Curve(_as_edge(exp.Current()))
                exp.Next()
                d = GCPnts_TangentialDeflection(curve, 0.05, float(deflection), 2)
                pts = np.array([d.Value(k).Coord() for k in range(1, d.NbPoints() + 1)])
                if len(pts) >= 2:
                    out.append(pts)
            return out
        except Exception:                                  # noqa: BLE001
            return None

    def exact_volume(self, name):
        """Volume of a part that is a closed solid, else None."""
        solids = self.part_solids.get(name)
        return sum(_props(s, "volume") for s in solids) if solids else None
