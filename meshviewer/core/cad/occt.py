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

from meshviewer.core.model import CAD_QUALITY_NAMES, MissingDependency

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
QUALITY_LEVELS = [(name, lin, ang) for name, (lin, ang) in zip(CAD_QUALITY_NAMES, (
    (5e-3, 0.80),
    (2e-3, 0.50),
    (1e-3, 0.35),     # Medium: ~18 facets per full circle
    (3e-4, 0.20),
    (1e-4, 0.10),     # Very fine: ~63 facets per full circle
))]
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
            p, idx = _nodes_and_triangles(tri)
            n_nodes = len(p)
            if not loc.IsIdentity():
                m = _matrix(loc)
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



class _PerShape:
    """One value per distinct shape. The instances of a shape (a bolt used 40 times: the
    same geometry in other places) are "partners" and share the value."""

    def __init__(self):
        self._found = {}                              # hash -> [(shape, value)]

    @staticmethod
    def _key(shape):
        return hash(shape.Located(TopLoc_Location()))     # the place left out

    def get(self, shape):
        for other, value in self._found.get(self._key(shape), ()):
            if other.IsPartner(shape):
                return value
        return None

    def put(self, shape, value):
        self._found.setdefault(self._key(shape), []).append((shape, value))
        return value


def _matrix(loc):
    """A location as a 3×4 array: x -> m[:, :3] @ x + m[:, 3]."""
    t = loc.Transformation()
    return np.array([[t.Value(r, c) for c in range(1, 5)] for r in range(1, 4)])


def _instance_poly(shape, free_only, done):
    """_faces_to_poly of one shape, triangles gathered once for all its instances
    (`done`: a _PerShape) and moved to this instance's place."""
    hit = done.get(shape)
    if hit is None:
        poly, faces = _faces_to_poly([shape.Located(TopLoc_Location())], free_only)
        hit = done.put(shape, [poly, faces, False])
    poly, faces, used = hit
    loc = shape.Location()
    if poly is None:
        return None, []
    if loc.IsIdentity() and not used:
        hit[2] = True                                 # the only copy so far: no need for another
        return poly, faces
    out = poly.copy()
    if not loc.IsIdentity():
        m = _matrix(loc)
        out.points = np.asarray(poly.points) @ m[:, :3].T + m[:, 3]
    return out, [f.Moved(loc) for f in faces]


def _nodes_and_triangles(tri):
    """A meshed face as OpenCASCADE made it: nodes (n, 3) in the face's own frame and
    triangles (m, 3), counted from 0."""
    p = np.array([tri.Node(i).Coord() for i in range(1, tri.NbNodes() + 1)], dtype=np.float64)
    idx = np.array([tri.Triangle(i).Get() for i in range(1, tri.NbTriangles() + 1)],
                   dtype=np.int64) - 1
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

def _occt_mesh(shape, deflection, angle):
    """OpenCASCADE's own mesh of a shape, on every core, with its faster triangulator
    (Delabella) where this OCCT has it."""
    try:
        from OCP.IMeshTools import IMeshTools_MeshAlgoType, IMeshTools_Parameters
        par = IMeshTools_Parameters()
        par.Deflection, par.Angle, par.InParallel = float(deflection), float(angle), True
        par.MeshAlgo = IMeshTools_MeshAlgoType.IMeshTools_MeshAlgoType_Delabella
        BRepMesh_IncrementalMesh(shape, par)
    except (ImportError, AttributeError, TypeError):
        BRepMesh_IncrementalMesh(shape, deflection, False, angle, True)


class CadFile:
    """B-rep shapes read once, tessellated at any quality level."""

    levels = [q[0] for q in QUALITY_LEVELS]

    def __init__(self, path, leaves, keepalive=None, debug=True):
        self.path = path
        self.leaves = leaves
        self._keepalive = keepalive         # e.g. the XCAF document owning the shapes
        self.debug = debug
        self._areas = _PerShape()           # exact area of each face, as asked
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
        meshed = _PerShape()
        for _, s in self.leaves:
            if meshed.get(s) is None:
                BRepTools.Clean_s(s)        # drop the previous triangulation
                _occt_mesh(s, self.diag * lin, ang)
                meshed.put(s, True)

        parts, loose = {}, []
        whole, free = _PerShape(), _PerShape()         # triangles of each distinct shape
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
                    self._add(parts, f"{leaf_name} {k}", _instance_poly(body, False, whole))
                continue
            for name, shapes, free_only in _split_solids(leaf_name, shape):
                self._add(parts, name,
                          _instance_poly(shapes[0], free_only, free if free_only else whole),
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
        return sum(self._face_area(faces[i]) for i in ids if 0 <= i < len(faces))

    def _face_area(self, face):
        """Computed once per distinct face: it never changes, and lists ask again and again."""
        a = self._areas.get(face)
        return self._areas.put(face, _props(face, "area")) if a is None else a

    # --- exact cut by a plane (Inflation Layers ▸ Section) --------------------
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
