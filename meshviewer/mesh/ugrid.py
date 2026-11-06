"""FUN3D / AFLR3 UGRID mesh reader (.lb8.ugrid, .b8.ugrid, .lb4.ugrid, .b4.ugrid).

MESH format. Returns {boundary_name: pv.PolyData}, one surface per boundary tag.
Boundary names come from a sibling .mapbc file when present.
Code moved unchanged from the original mesh_viewer.py.
"""
from __future__ import annotations

import numpy as np
import pyvista as pv


UGRID_VARIANTS = {
    ".lb8.ugrid": ("<", 8),
    ".b8.ugrid":  (">", 8),
    ".lb4.ugrid": ("<", 4),
    ".b4.ugrid":  (">", 4),
}


def _ugrid_sniff(path):
    """Probe the file header to identify (endian, isize).

    Tries each (little/big × 4/8) variant and returns the one whose 7-int
    header passes a plausibility test: n_nodes positive and < 10**10, all
    element counts non-negative and < 10**11. Filename suffix is used as a
    tiebreaker / hint but is not trusted blindly.
    """
    candidates = [("<", 8), (">", 8), ("<", 4), (">", 4)]

    # Hint from filename — try this first if present
    name = path.name.lower()
    for suffix, info in UGRID_VARIANTS.items():
        if name.endswith(suffix):
            candidates.remove(info)
            candidates.insert(0, info)
            break

    with open(path, "rb") as f:
        head_bytes = f.read(7 * 8)  # enough for any variant

    for endian, isize in candidates:
        if len(head_bytes) < 7 * isize:
            continue
        dt = np.dtype(f"{endian}i{isize}")
        h = np.frombuffer(head_bytes[: 7 * isize], dtype=dt)
        n_nodes = int(h[0])
        rest = [int(x) for x in h[1:]]
        if (1 <= n_nodes < 10**10
                and all(0 <= x < 10**11 for x in rest)
                and (rest[0] + rest[1]) > 0):  # need some surface elements
            return endian, isize

    raise ValueError(
        f"Could not identify UGRID format for {path.name}.\n"
        f"Header bytes (hex): {head_bytes[:32].hex()}\n"
        f"None of the standard variants (lb8/b8/lb4/b4) produced a plausible header."
    )


def _strip_ugrid_suffix(name):
    """Strip the .{lb8,b8,lb4,b4,}.ugrid tail; used to find sibling .mapbc."""
    lower = name.lower()
    for suffix in (".lb8.ugrid", ".b8.ugrid", ".lb4.ugrid", ".b4.ugrid", ".ugrid"):
        if lower.endswith(suffix):
            return name[: -len(suffix)]
    return name


def read_mapbc(path):
    """Parse a FUN3D .mapbc file. Returns dict {tag: name}.

    Tolerant to optional leading count line, comment lines (#, !), and the
    common "tag bc_type name" or "tag bc_type 'name with spaces'" formats.
    """
    if not path or not path.exists():
        return {}
    names = {}
    for line in path.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "!", "//")):
            continue
        toks = line.split(None, 2)
        if len(toks) < 3:
            continue
        try:
            tag = int(toks[0])
            int(toks[1])              # bc_type code, must be int (validates the row)
        except ValueError:
            continue
        names[tag] = toks[2].strip().strip("'\"")
    return names


def read_ugrid(path, debug=True):
    """Read a UGRID file. Returns dict {bc_label: pv.PolyData}.

    Stops reading immediately after the boundary tags — the volume cell
    blocks that follow are skipped entirely.
    """
    endian, isize = _ugrid_sniff(path)
    int_dt = np.dtype(f"{endian}i{isize}")
    real_dt = np.dtype(f"{endian}f8")

    if debug:
        print(f"  format: endian={'little' if endian == '<' else 'big'}, int{isize * 8}")

    with open(path, "rb") as f:
        header = np.fromfile(f, dtype=int_dt, count=7)
        if len(header) != 7:
            raise ValueError(f"truncated UGRID header in {path}")
        n_nodes, n_tri, n_quad, n_tet, n_pyr, n_pri, n_hex = (int(x) for x in header)

        if debug:
            print(f"  nodes={n_nodes:,}  tri={n_tri:,}  quad={n_quad:,}  "
                  f"tet={n_tet:,}  pyr={n_pyr:,}  pri={n_pri:,}  hex={n_hex:,}")

        if n_tri + n_quad == 0:
            print("  no surface elements — nothing to display")
            return {}

        pts = np.fromfile(f, dtype=real_dt, count=n_nodes * 3)
        if pts.size != n_nodes * 3:
            raise ValueError("truncated coordinate block")
        pts = pts.reshape(n_nodes, 3).astype(np.float64, copy=False)

        tris = np.fromfile(f, dtype=int_dt, count=n_tri * 3).reshape(n_tri, 3) \
            if n_tri else np.empty((0, 3), dtype=np.int64)
        quads = np.fromfile(f, dtype=int_dt, count=n_quad * 4).reshape(n_quad, 4) \
            if n_quad else np.empty((0, 4), dtype=np.int64)
        tri_tags = np.fromfile(f, dtype=int_dt, count=n_tri) \
            if n_tri else np.empty(0, dtype=np.int64)
        quad_tags = np.fromfile(f, dtype=int_dt, count=n_quad) \
            if n_quad else np.empty(0, dtype=np.int64)

    # Optional .mapbc sibling for human-readable names
    mapbc_path = path.parent / f"{_strip_ugrid_suffix(path.name)}.mapbc"
    name_map = read_mapbc(mapbc_path)
    if debug:
        if name_map:
            print(f"  found {mapbc_path.name} with {len(name_map)} named patches")
        else:
            print(f"  no {mapbc_path.name} found — using numeric tags")

    all_tags = np.concatenate([tri_tags, quad_tags]).astype(np.int64)
    unique_tags = np.unique(all_tags)

    bcs = {}
    for tag in unique_tags:
        tag_int = int(tag)
        tri_mask = tri_tags == tag if n_tri else None
        quad_mask = quad_tags == tag if n_quad else None
        n_t = int(tri_mask.sum()) if tri_mask is not None else 0
        n_q = int(quad_mask.sum()) if quad_mask is not None else 0

        # Build flat VTK face array. Triangles -> [3, v0, v1, v2]; quads -> [4, ...].
        cells_parts = []
        if n_t:
            blk = np.empty((n_t, 4), dtype=np.int64)
            blk[:, 0] = 3
            blk[:, 1:] = tris[tri_mask].astype(np.int64) - 1   # 1-indexed -> 0-indexed
            cells_parts.append(blk.ravel())
        if n_q:
            blk = np.empty((n_q, 5), dtype=np.int64)
            blk[:, 0] = 4
            blk[:, 1:] = quads[quad_mask].astype(np.int64) - 1
            cells_parts.append(blk.ravel())
        cells = np.concatenate(cells_parts) if cells_parts else np.empty(0, dtype=np.int64)

        try:
            poly = pv.PolyData(pts, faces=cells).clean()
        except Exception as exc:
            if debug:
                print(f"  tag {tag_int}: build failed: {exc}")
            continue

        label = name_map.get(tag_int, f"tag_{tag_int}")
        # If two tags map to the same name, disambiguate
        if label in bcs:
            label = f"{label}_{tag_int}"
        bcs[label] = poly
        if debug:
            print(f"  {label}: tri={n_t} quad={n_q} -> "
                  f"{poly.n_points} pts, {poly.n_cells} cells")

    return bcs


# ---- NEW (v2.19): volume cells, read only when the cut mesh is shown ------------------
def read_volume(path, debug=True):
    """Tetrahedra, pyramids, prisms and hexahedra as one pv.UnstructuredGrid
    (None if the file has surfaces only). They follow the boundary tags:
    tet (4 nodes), pyramid (5), prism (6), hex (8); node numbers 1-based."""
    import os

    from .volume import HEXA, PYRAMID, TETRA, WEDGE, build_grid, describe

    endian, isize = _ugrid_sniff(path)
    int_dt = np.dtype(f"{endian}i{isize}")
    with open(path, "rb") as f:
        header = np.fromfile(f, dtype=int_dt, count=7)
        n_nodes, n_tri, n_quad, n_tet, n_pyr, n_pri, n_hex = (int(x) for x in header)
        if n_tet + n_pyr + n_pri + n_hex == 0:
            return None
        pts = np.fromfile(f, dtype=np.dtype(f"{endian}f8"), count=n_nodes * 3)
        if pts.size != n_nodes * 3:
            raise ValueError("truncated coordinate block")
        # skip triangles, quads and their boundary tags
        f.seek(isize * (4 * n_tri + 5 * n_quad), os.SEEK_CUR)
        blocks = {}
        for ctype, n, npe in ((TETRA, n_tet, 4), (PYRAMID, n_pyr, 5),
                              (WEDGE, n_pri, 6), (HEXA, n_hex, 8)):
            if not n:
                continue
            c = np.fromfile(f, dtype=int_dt, count=n * npe)
            if c.size != n * npe:
                raise ValueError("truncated volume cell block")
            c = c.reshape(n, npe).astype(np.int64) - 1
            if ctype == PYRAMID:                 # UGRID pyramid node order -> VTK
                c = c[:, [1, 0, 3, 4, 2]]
            blocks[ctype] = [c]
    grid = build_grid(pts.reshape(n_nodes, 3), blocks)
    if debug and grid is not None:
        print(f"  volume: {describe(grid)}")
    return grid
