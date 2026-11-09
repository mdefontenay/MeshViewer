"""`.msh` meshes: Gmsh (any version, text or binary, read with meshio) or Ansys Fluent
(text or binary sections). Which one is found from the file itself, and so is 2D / 3D.

    3D  {boundary: surface}            + read_volume(): the cells (tetra … hexa, Fluent
                                          polyhedra as tetra / pyramids / prisms / hexa)
    2D  {zone: its cells, flat}        + {boundary: its edges, as lines}

read_msh returns (parts, {"dim": 2 or 3}).
"""
from __future__ import annotations

import re

import numpy as np
import pyvista as pv

from meshviewer.core.model import MissingDependency


def _kind(path):
    head = open(path, "rb").read(4096).lstrip()
    if head.startswith(b"$MeshFormat") or head.startswith(b"$NOD"):
        return "gmsh"
    if head.startswith(b"("):
        return "fluent"
    raise ValueError("not a Gmsh or Fluent .msh file")


def read_msh(path, debug=True):
    parts, dim = (_gmsh(path, debug) if _kind(path) == "gmsh" else _fluent_parts(path, debug))
    if debug:
        print(f"  {dim}D mesh · {len(parts)} parts")
    return parts, {"dim": dim}


def read_volume(path, debug=True):
    """3D cells as a pv.UnstructuredGrid (None for 2D meshes)."""
    from meshviewer.core.mesh.volume import build_grid, describe
    if _kind(path) == "gmsh":
        pts, blocks = _gmsh_volume(path)
    else:
        pts, blocks = _fluent_volume(path, debug)
    grid = build_grid(pts, blocks) if blocks else None
    if debug and grid is not None:
        print(f"  volume: {describe(grid)}")
    return grid


# ---- Gmsh (meshio) ------------------------------------------------------------------------
VOLUME_TYPES = {"tetra": (10, 4), "tetra10": (10, 4), "pyramid": (14, 5), "pyramid13": (14, 5),
                "pyramid14": (14, 5), "wedge": (13, 6), "wedge15": (13, 6), "wedge18": (13, 6),
                "hexahedron": (12, 8), "hexahedron20": (12, 8), "hexahedron27": (12, 8)}
FACE_TYPES = {"triangle": 3, "triangle6": 3, "quad": 4, "quad8": 4, "quad9": 4}
LINE_TYPES = {"line": 2, "line3": 2}


def _meshio(path):
    try:
        import meshio
    except ImportError as exc:
        raise MissingDependency("meshio", "Gmsh .msh files") from exc
    return meshio.read(str(path), file_format="gmsh")


def _groups(m, kinds):
    """{name: (corner count, node ids (k, n))} of the cell blocks of the given types,
    split by physical group (named from field_data), else by geometrical entity."""
    names = {}
    for name, (tag, gdim) in getattr(m, "field_data", {}).items():
        names[(int(gdim), int(tag))] = name
    phys = m.cell_data.get("gmsh:physical")
    geo = m.cell_data.get("gmsh:geometrical")
    out = {}
    for b, block in enumerate(m.cells):
        if block.type not in kinds:
            continue
        n = kinds[block.type]
        data = np.asarray(block.data)[:, :n]
        dim = 1 if block.type in LINE_TYPES else 2
        tags = phys[b] if phys is not None else (geo[b] if geo is not None else None)
        if tags is None:
            out.setdefault("mesh", []).append(data)
            continue
        for t in np.unique(tags):
            name = names.get((dim, int(t))) or (f"Physical {t}" if phys is not None else f"Entity {t}")
            out.setdefault(name, []).append(data[tags == t])
    return {k: np.vstack(v) for k, v in out.items()}


def _gmsh(path, debug):
    m = _meshio(path)
    pts = np.asarray(m.points, dtype=float)
    if pts.shape[1] == 2:
        pts = np.column_stack([pts, np.zeros(len(pts))])
    dim3 = any(b.type in VOLUME_TYPES for b in m.cells)
    parts = {}
    if dim3:
        for name, faces in _groups(m, FACE_TYPES).items():
            parts[name] = _poly(pts, faces)
        if not parts:                                   # no surface elements: the hull
            grid = _gmsh_grid(pts, m)
            parts["boundary"] = grid.extract_surface().clean()
        return parts, 3
    for name, faces in _groups(m, FACE_TYPES).items():  # 2D: the zones, then the edges
        parts[name] = _poly(pts, faces)
    for name, lines in _groups(m, LINE_TYPES).items():
        parts[_unique(name, parts)] = _lines(pts, lines)
    return parts, 2


def _gmsh_blocks(m):
    blocks = {}
    for block in m.cells:
        if block.type in VOLUME_TYPES:
            ctype, n = VOLUME_TYPES[block.type]
            blocks.setdefault(pv.CellType(ctype), []).append(np.asarray(block.data)[:, :n])
    return blocks


def _gmsh_grid(pts, m):
    from meshviewer.core.mesh.volume import build_grid
    return build_grid(pts, _gmsh_blocks(m))


def _gmsh_volume(path):
    m = _meshio(path)
    pts = np.asarray(m.points, dtype=float)
    if pts.shape[1] == 2:
        return pts, {}
    return pts, _gmsh_blocks(m)


# ---- helpers -------------------------------------------------------------------------------
def _poly(pts, faces):
    """A surface from (k, n) node ids (or a list of node-id lists), only its own points."""
    if isinstance(faces, np.ndarray):
        cells = np.column_stack([np.full(len(faces), faces.shape[1]), faces]).ravel()
    else:
        cells = np.concatenate([[len(f), *f] for f in faces]).astype(np.int64)
    return pv.PolyData(pts, faces=cells).clean()


def _lines(pts, segs):
    cells = np.column_stack([np.full(len(segs), 2), segs]).ravel()
    return pv.PolyData(pts, lines=cells).clean()


def _unique(name, taken):
    k, out = 2, name
    while out in taken:
        out = f"{name} {k}"
        k += 1
    return out


# ---- Fluent ----------------------------------------------------------------------------------
BC_NAMES = {2: "interior", 3: "wall", 4: "pressure-inlet", 5: "pressure-outlet", 7: "symmetry",
            8: "periodic-shadow", 9: "pressure-far-field", 10: "velocity-inlet", 12: "periodic",
            14: "fan", 20: "mass-flow-inlet", 24: "interface", 31: "parent", 36: "outflow",
            37: "axis"}
INNER = {2, 31}                                          # interior / parent: not boundaries
_HEAD = re.compile(rb"\(\s*(\d+)[\s(]")


class _Fluent:
    """Sections of a Fluent mesh: nodes, faces (with their two cells) and zone names."""

    def __init__(self, path):
        self.data = open(path, "rb").read()
        self.dim = 3
        self.nodes = {}            # zone -> (first, coords (n, dim))
        self.faces = []            # (zone, bc type, first, nodes list | (k, n) array, c0, c1)
        self.names = {}            # zone -> name
        self._parse()

    def _hex(self, b):
        return [int(x, 16) for x in b.split()]

    def _parse(self):
        d, i = self.data, 0
        while True:
            m = _HEAD.search(d, i)
            if m is None:
                break
            idx, at = int(m.group(1)), m.start()
            if idx == 2:                                     # (2 ND)
                self.dim = self._dim(at)
                i = self._close(at)
                continue
            if idx in (39, 45):                              # zone name: (45 (id type name)())
                hs = d.find(b"(", m.end() - 1)
                header = d[hs + 1:d.find(b")", hs)].decode(errors="replace").split()
                if len(header) >= 3:
                    try:
                        self.names[int(header[0])] = header[2]
                    except ValueError:
                        self.names[int(header[0], 16)] = header[2]
                i = self._close(at)
                continue
            if idx in (10, 2010, 3010, 12, 2012, 3012, 13, 2013, 3013):
                hs = d.find(b"(", m.end() - 1)               # the header ( … )
                he = d.find(b")", hs)
                header = d[hs + 1:he]
                nxt = re.compile(rb"\s*\(").match(d, he + 1)  # a body follows?
                body = nxt.end() - 1 if nxt else None
                if idx in (10, 2010, 3010):
                    self._nodes(idx, header, d, body)
                elif idx in (13, 2013, 3013):
                    self._faces(idx, header, d, body)
                elif idx >= 2000 and body is not None:        # binary cell types: skip them
                    h = self._hex(header)
                    self._skip = self._after(body + 1 + 4 * (h[2] - h[1] + 1))
                i = self._close(at, binary=idx >= 2000)
                continue
            i = self._close(at)

    def _after(self, k):
        """Just after the two brackets that close a binary body and its section."""
        d = self.data
        return d.find(b")", d.find(b")", k) + 1) + 1

    def _dim(self, at):
        m = re.match(rb"\(\s*2\s+(\d+)\s*\)", self.data[at:at + 40])
        return int(m.group(1)) if m else 3

    def _close(self, at, binary=False):
        """Index just after the section that opens at `at` (balanced brackets; binary
        bodies are skipped by their length, set by _nodes / _faces)."""
        if binary and getattr(self, "_skip", None):
            i, self._skip = self._skip, None
            return i
        d, depth, i = self.data, 0, at
        n = len(d)
        while i < n:
            c = d[i]
            if c == 0x28:
                depth += 1
            elif c == 0x29:
                depth -= 1
                if depth == 0:
                    return i + 1
            elif c == 0x22:                                  # a string: skip it
                i = d.find(b'"', i + 1)
                if i < 0:
                    return n
            i += 1
        return n

    def _nodes(self, idx, header, d, body):
        h = self._hex(header)
        zone, first, last = h[0], h[1], h[2]
        nd = h[4] if len(h) > 4 else self.dim
        count = last - first + 1
        if zone == 0 or body is None or count <= 0:
            return
        if idx == 10:                                         # text
            end = d.find(b")", body + 1)
            arr = np.array(d[body + 1:end].split(), dtype=float).reshape(-1, nd)
        else:                                                 # binary: float / double
            size = 4 if idx == 2010 else 8
            dt = "<f4" if size == 4 else "<f8"
            arr = np.frombuffer(d, dtype=dt, count=count * nd, offset=body + 1).reshape(-1, nd)
            self._skip = self._after(body + 1 + count * nd * size)
        self.nodes[zone] = (first, arr.astype(float))

    def _faces(self, idx, header, d, body):
        h = self._hex(header)
        zone, first, last, bc = h[0], h[1], h[2], h[3]
        ftype = h[4] if len(h) > 4 else 0
        count = last - first + 1
        if zone == 0 or body is None or count <= 0:
            return
        if idx == 13:
            end = d.find(b")", body + 1)
            vals = np.array([int(x, 16) for x in d[body + 1:end].split()], dtype=np.int64)
        else:
            vals, end = self._binary_faces(d, body + 1, count, ftype)
            self._skip = self._after(end)
        if ftype == 0:                                        # mixed: count, nodes…, c0, c1
            faces, c0, c1, k = [], [], [], 0
            for _ in range(count):
                nn = int(vals[k])
                faces.append(vals[k + 1:k + 1 + nn])
                c0.append(vals[k + 1 + nn])
                c1.append(vals[k + 2 + nn])
                k += nn + 3
            c0, c1 = np.array(c0), np.array(c1)
        else:
            nn = {2: 2, 3: 3, 4: 4}.get(ftype, ftype)
            a = vals[:count * (nn + 2)].reshape(count, nn + 2)
            faces, c0, c1 = a[:, :nn], a[:, nn], a[:, nn + 1]
        self.faces.append((zone, bc, first, faces, c0, c1))

    def _binary_faces(self, d, at, count, ftype):
        if ftype != 0:
            nn = {2: 2, 3: 3, 4: 4}.get(ftype, ftype)
            n = count * (nn + 2)
            vals = np.frombuffer(d, dtype="<i4", count=n, offset=at).astype(np.int64)
            return vals, at + 4 * n
        out, k = [], at                                      # mixed: walk it
        for _ in range(count):
            nn = int(np.frombuffer(d, dtype="<i4", count=1, offset=k)[0])
            out.append(np.frombuffer(d, dtype="<i4", count=nn + 3, offset=k).astype(np.int64))
            k += 4 * (nn + 3)
        return np.concatenate(out), k

    # ---- views ----------------------------------------------------------------------------
    def points(self):
        if not self.nodes:
            raise ValueError("no nodes in this Fluent mesh")
        top = max(first + len(a) - 1 for first, a in self.nodes.values())
        pts = np.zeros((top, 3))
        for first, a in self.nodes.values():
            pts[first - 1:first - 1 + len(a), :a.shape[1]] = a
        return pts

    def zone_name(self, zone, bc):
        return self.names.get(zone) or f"{BC_NAMES.get(bc, 'zone')}-{zone}"


def _fluent_parts(path, debug):
    f = _Fluent(path)
    pts = f.points()
    parts = {}
    if f.dim == 3:
        for zone, bc, _first, faces, _c0, _c1 in f.faces:
            if bc in INNER:
                continue
            fl = [np.asarray(x) - 1 for x in faces] if isinstance(faces, list) else faces - 1
            parts[_unique(f.zone_name(zone, bc), parts)] = _poly(pts, fl)
        return parts, 3
    # 2D: cells are polygons, built from their edges (faces)
    for name, polys in _fluent_cells_2d(f).items():
        parts[_unique(name, parts)] = _poly(pts, polys)
    for zone, bc, _first, faces, _c0, _c1 in f.faces:
        if bc in INNER:
            continue
        segs = np.asarray([x[:2] for x in faces]) if isinstance(faces, list) else faces[:, :2]
        parts[_unique(f.zone_name(zone, bc), parts)] = _lines(pts, segs - 1)
    return parts, 2


def _all_faces(f):
    nodes, c0, c1 = [], [], []
    for _zone, _bc, _first, faces, a, b in f.faces:
        nodes += [np.asarray(x) - 1 for x in faces] if isinstance(faces, list) else list(faces - 1)
        c0.append(np.asarray(a))
        c1.append(np.asarray(b))
    return nodes, np.concatenate(c0), np.concatenate(c1)


def _fluent_cells_2d(f):
    """{"fluid": [polygon node lists]}: each cell's edges chained into a loop."""
    nodes, c0, c1 = _all_faces(f)
    edges = {}
    for e, a, b in zip(nodes, c0, c1):
        for c in (a, b):
            if c > 0:
                edges.setdefault(int(c), []).append((int(e[0]), int(e[1])))
    polys = []
    for c in sorted(edges):
        es = edges[c]
        nxt = {}
        for u, v in es:
            nxt.setdefault(u, []).append(v)
            nxt.setdefault(v, []).append(u)
        start = es[0][0]
        loop, prev, cur = [start], None, start
        for _ in range(len(es) - 1):
            options = [x for x in nxt[cur] if x != prev]
            if not options:
                break
            prev, cur = cur, options[0]
            loop.append(cur)
        if len(loop) >= 3:
            polys.append(loop)
    return {f.names.get(_cell_zone(f), "fluid"): polys} if polys else {}


def _cell_zone(f):
    named = [z for z in f.names if z not in {zone for zone, *_ in f.faces}]
    return named[0] if named else None


def _fluent_volume(path, debug):
    from meshviewer.core.mesh.polyhedra import standard_cells
    from meshviewer.core.mesh.volume import orient_each
    f = _Fluent(path)
    if f.dim != 3:
        return f.points(), {}
    pts = f.points()
    nodes, c0, c1 = _all_faces(f)
    sizes = np.array([len(x) for x in nodes])
    fconn = np.concatenate(nodes).astype(np.int64)
    foff = np.concatenate([[0], np.cumsum(sizes)])
    fid = np.arange(len(nodes))
    owner = np.concatenate([c0, c1[c1 > 0]])
    face = np.concatenate([fid, fid[c1 > 0]])
    order = np.argsort(owner, kind="stable")
    cell_faces = face[order]
    counts = np.bincount(owner[order])[1:] if len(owner) else np.zeros(0, int)
    coff = np.concatenate([[0], np.cumsum(counts)])
    blocks, skipped = standard_cells(fconn, foff, cell_faces, coff)
    if debug and skipped:
        print(f"  {skipped:,} polyhedral cells not shown")
    return pts, orient_each(blocks, pts)
