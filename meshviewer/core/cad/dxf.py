"""DXF drawings (2D profiles): lines, polylines, arcs, circles, ellipses, splines and
blocks, read with ezdxf and drawn as lines, one part per layer.

The drawing's unit ($INSUNITS) is passed on when it has one.
read_dxf returns (parts, {"dim": 2, "units": "mm" | … | ""}).
"""
from __future__ import annotations

import numpy as np
import pyvista as pv

from meshviewer.core.model import MissingDependency

INSUNITS = {1: "in", 2: "ft", 4: "mm", 5: "cm", 6: "m"}
CURVES = ("LINE", "LWPOLYLINE", "POLYLINE", "ARC", "CIRCLE", "ELLIPSE", "SPLINE")


def read_dxf(path, debug=True):
    try:
        import ezdxf
        from ezdxf import disassemble, path as dxf_path
    except ImportError as exc:
        raise MissingDependency("ezdxf", "DXF drawings") from exc
    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()
    ext = [e for e in disassemble.recursive_decompose(msp) if e.dxftype() in CURVES]
    # chord tolerance: 1/2000 of the drawing's size
    pts_all = []
    for e in ext[:2000]:
        try:
            pts_all.extend(dxf_path.make_path(e).control_vertices())
        except Exception:                                    # noqa: BLE001
            pass
    size = float(np.ptp(np.array([(v.x, v.y) for v in pts_all]), axis=0).max()) if pts_all else 1.0
    tol = max(size, 1e-9) / 2000
    layers = {}
    for e in ext:
        try:
            verts = [(v.x, v.y, v.z) for v in dxf_path.make_path(e).flattening(tol)]
        except Exception:                                    # noqa: BLE001 skip what can't be drawn
            continue
        if len(verts) >= 2:
            layers.setdefault(e.dxf.layer or "0", []).append(np.array(verts, dtype=float))
    parts = {}
    for layer, polys in layers.items():
        pts = np.vstack(polys)
        lines, start = [], 0
        for p in polys:
            n = len(p)
            idx = np.arange(start, start + n)
            lines.append(np.column_stack([np.full(n - 1, 2), idx[:-1], idx[1:]]))
            start += n
        parts[layer] = pv.PolyData(pts, lines=np.vstack(lines).ravel()).clean()
    if not parts:
        raise ValueError("no lines, arcs, circles or curves in this DXF")
    units = INSUNITS.get(int(doc.header.get("$INSUNITS", 0) or 0), "")
    if debug:
        print(f"  {len(parts)} layers · {sum(p.n_cells for p in parts.values()):,} segments"
              + (f" · {units}" if units else ""))
    return parts, {"dim": 2, "units": units}
