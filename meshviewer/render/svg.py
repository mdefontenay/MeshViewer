"""Save Screenshot as SVG: the 3D view (3D View and contour tabs) as real vector shapes.

    svg_text(scene, k=1, transparent=False) -> the SVG, as text

What is drawn, as in the view: every visible part's facets as <polygon>s (its color,
lit from the camera as the view is; a contour's colors on the boundaries it covers),
cut by the section plane with its filled cut faces, the mesh edges as their outlines,
the feature edges and a drawing's lines as <line>s; then the color bar and the XYZ
axis indicator over it. The background is the view's (its gradient), or none.

Hidden surfaces: the painter's algorithm — every facet and line projected through the
camera and drawn back to front (lines a hair in front of the faces they lie on). Facets
outside the picture, behind the camera or seen edge-on are left out (both sides drawn:
the boundaries of a CFD mesh are often open). Not drawn: the grid,
the axes' numbers, the y+ / wall / cell-quality colors, measurement marks.
"""
from __future__ import annotations

import numpy as np
from vtkmodules.util.numpy_support import vtk_to_numpy

from meshviewer.core.fields import ramp_table
from meshviewer.render.measure import AXIS_COLORS
from meshviewer.render.style import THEMES, lighter, rgb

LINE_BIAS = 2e-4              # lines drawn this much (depth, -1…1) in front of faces
SPLIT_T = 1 / 48              # a contour's facet is split while its colors differ more…
SPLIT_PX = 6.0                # …and it is bigger than this on screen (pixels)
SPLIT_LEVELS = 6              # at most 4⁶ pieces per facet


def _hex(c):
    c = np.clip(np.asarray(c, dtype=float), 0.0, 1.0)
    return "#%02x%02x%02x" % tuple(int(round(v * 255)) for v in c[:3])


def _part_rgb(sc, n):
    """A part's color as drawn (selected: lighter; a drawing: its line color)."""
    sel = n in sc.selected_parts
    if sc.is_drawing:
        return np.array(rgb(sc.accent if sel else sc.line_color))
    return np.array(lighter(sc.colors[n]) if sel else rgb(sc.colors[n]))


class _Projector:
    """World points -> SVG pixels (y down) and depth (-1 near … 1 far)."""

    def __init__(self, sc, k):
        ren = sc.p.renderer
        self.w, self.h = ren.GetSize()
        self.k = float(k)
        cam = ren.GetActiveCamera()
        m = cam.GetCompositeProjectionTransformMatrix(self.w / max(self.h, 1), -1, 1)
        self.m = np.array([[m.GetElement(i, j) for j in range(4)] for i in range(4)])
        self.view_dir = np.asarray(cam.GetDirectionOfProjection(), dtype=float)
        v = cam.GetViewTransformMatrix()
        self.rot = np.array([[v.GetElement(i, j) for j in range(3)] for i in range(3)])

    def __call__(self, pts):
        pts = np.asarray(pts, dtype=float)
        hp = np.c_[pts, np.ones(len(pts))] @ self.m.T
        wv = hp[:, 3]
        ok = wv > 1e-12
        safe = np.where(ok, wv, 1.0)
        ndc = hp[:, :3] / safe[:, None]
        x = (ndc[:, 0] + 1) / 2 * self.w * self.k
        y = (1 - ndc[:, 1]) / 2 * self.h * self.k
        return x, y, ndc[:, 2], ok


def _keep_side(sc):
    """The section's half-space as a test on points (None: no section)."""
    sec = sc.section
    if not sec.enabled:
        return None
    o = np.asarray(sec._plane.GetOrigin(), dtype=float)
    n = np.asarray(sec._plane.GetNormal(), dtype=float)
    return lambda pts: (np.asarray(pts, dtype=float) - o) @ n >= 0


def _triangles(poly):
    """(points, (m, 3) triangles, the cell each comes from)."""
    from meshviewer.core.polys import bare
    surf = bare(poly)
    surf.cell_data["__cell"] = np.arange(surf.n_cells)
    tri = surf.triangulate()
    if not tri.n_cells or not tri.GetNumberOfPolys():
        return None, None, None
    faces = np.asarray(tri.faces).reshape(-1, 4)[:, 1:]
    return (np.asarray(tri.points, dtype=float), faces,
            np.asarray(tri.cell_data["__cell"], dtype=int))


def _lines(poly):
    """(points, (m, 2) segments) of a dataset's lines."""
    if poly is None or not poly.n_cells or not poly.GetNumberOfLines():
        return None, None
    lines = poly.lines
    pts = np.asarray(poly.points, dtype=float)
    segs, i = [], 0
    while i < len(lines):
        n = int(lines[i])
        ids = lines[i + 1:i + 1 + n]
        segs += [(int(a), int(b)) for a, b in zip(ids[:-1], ids[1:])]
        i += n + 1
    return pts, (np.asarray(segs, dtype=int).reshape(-1, 2) if segs else None)


class _Items:
    """Facets and lines with their depth, drawn back to front."""

    def __init__(self):
        self.depth, self.text = [], []

    def add(self, depth, texts):
        self.depth.extend(np.asarray(depth, dtype=float).tolist())
        self.text.extend(texts)

    def svg(self):
        order = np.argsort(-np.asarray(self.depth, dtype=float), kind="stable")
        return "\n".join(self.text[i] for i in order)


def _facets(items, proj, pts, tri, colors, keep, stroke=None, fill=True, light=True):
    """Add triangles (points, (m, 3)) with an RGB per triangle to the items (fill False:
    nothing — with Faces off, only lines are drawn)."""
    if not fill:
        return
    if tri is None or not len(tri):
        return
    x, y, z, ok = proj(pts)
    good = ok[tri].all(axis=1)
    if keep is not None:
        good &= keep(pts)[tri].all(axis=1)
    W, H = proj.w * proj.k, proj.h * proj.k
    tx, ty = x[tri], y[tri]
    good &= ~((tx < 0).all(1) | (tx > W).all(1) | (ty < 0).all(1) | (ty > H).all(1))
    area = (tx[:, 1] - tx[:, 0]) * (ty[:, 2] - ty[:, 0]) - (tx[:, 2] - tx[:, 0]) * (ty[:, 1] - ty[:, 0])
    good &= np.abs(area) > 1e-6
    p = pts[tri]
    nrm = np.cross(p[:, 1] - p[:, 0], p[:, 2] - p[:, 0])
    nrm /= np.maximum(np.linalg.norm(nrm, axis=1), 1e-300)[:, None]
    shade = 0.45 + 0.55 * np.abs(nrm @ proj.view_dir) if light else np.ones(len(tri))
    cols = np.clip(np.asarray(colors, dtype=float) * shade[:, None], 0, 1)
    idx = np.flatnonzero(good)
    depth = z[tri[idx]].mean(axis=1)
    texts = []
    for j in idx:
        c = _hex(cols[j])
        ptxt = " ".join(f"{tx[j, q]:.1f},{ty[j, q]:.1f}" for q in range(3))
        if fill:
            line = stroke or c                       # its own color: no hairline gaps
            sw = "0.6" if stroke else "0.4"
            texts.append(f'<polygon points="{ptxt}" fill="{c}" stroke="{line}" '
                         f'stroke-width="{sw}" stroke-linejoin="round"/>')
        else:
            texts.append(f'<polygon points="{ptxt}" fill="none" stroke="{stroke or c}" '
                         f'stroke-width="0.6"/>')
    items.add(depth, texts)


def _split(proj, pts, tri, t):
    """A contour's facets split in four, again and again, where the value changes across
    one that is big on screen: flat SVG polygons can't blend, many small ones do.
    -> (points, triangles, the value at each point)."""
    pts = np.asarray(pts, dtype=float)
    t = np.asarray(t, dtype=float)
    done, todo = [], np.asarray(tri, dtype=int)
    for _ in range(SPLIT_LEVELS):
        if not len(todo):
            break
        x, y, _z, _ok = proj(pts)
        tv = np.nan_to_num(t[todo], nan=0.0)
        spread = tv.max(axis=1) - tv.min(axis=1)
        ex = np.abs(x[todo] - np.roll(x[todo], 1, axis=1))
        ey = np.abs(y[todo] - np.roll(y[todo], 1, axis=1))
        big = np.hypot(ex, ey).max(axis=1) > SPLIT_PX
        split = (spread > SPLIT_T) & big
        done.append(todo[~split])
        todo = todo[split]
        if not len(todo):
            break
        a, b, c = todo[:, 0], todo[:, 1], todo[:, 2]
        n0 = len(pts)
        m = len(todo)
        mids = np.vstack([(pts[a] + pts[b]) / 2, (pts[b] + pts[c]) / 2, (pts[c] + pts[a]) / 2])
        tmid = np.concatenate([(t[a] + t[b]) / 2, (t[b] + t[c]) / 2, (t[c] + t[a]) / 2])
        pts = np.vstack([pts, mids])
        t = np.concatenate([t, tmid])
        ab, bc, ca = n0 + np.arange(m), n0 + m + np.arange(m), n0 + 2 * m + np.arange(m)
        todo = np.vstack([np.c_[a, ab, ca], np.c_[ab, b, bc], np.c_[ca, bc, c],
                          np.c_[ab, bc, ca]])
    done.append(todo)
    return pts, np.vstack([d for d in done if len(d)]) if any(len(d) for d in done) \
        else np.zeros((0, 3), int), t


def _segments(items, proj, pts, seg, color, width, keep):
    if seg is None or not len(seg):
        return
    x, y, z, ok = proj(pts)
    good = ok[seg].all(axis=1)
    if keep is not None:
        good &= keep(pts)[seg].all(axis=1)
    idx = np.flatnonzero(good)
    c = _hex(color)
    depth = z[seg[idx]].min(axis=1) - LINE_BIAS
    items.add(depth, [f'<line x1="{x[a]:.1f}" y1="{y[a]:.1f}" x2="{x[b]:.1f}" '
                      f'y2="{y[b]:.1f}" stroke="{c}" stroke-width="{width:.2f}" '
                      f'stroke-linecap="round"/>' for a, b in seg[idx]])


def _results_colors(sc, surf):
    """The contour's colors per triangle of its surface (the same table as the view)."""
    spec = sc.results.spec
    t = None
    if "ResultT" in surf.point_data:                  # (as the view: per point, else cell)
        t = (np.asarray(surf.point_data["ResultT"], dtype=float), True)
    elif "ResultT" in surf.cell_data:
        t = (np.asarray(surf.cell_data["ResultT"], dtype=float), False)
    if t is None or spec is None:
        return None
    lut = sc.results._actor.GetMapper().GetLookupTable()
    table = vtk_to_numpy(lut.GetTable()).astype(float) / 255.0
    return t, table


def _background(sc, w, h, transparent):
    if transparent:
        return ""
    mode, value = sc.bg_mode
    t = THEMES[sc._dark]
    if mode == "color" and value:
        return f'<rect width="{w}" height="{h}" fill="{value}"/>'
    if sc.is_drawing and sc._dark:
        return f'<rect width="{w}" height="{h}" fill="#000000"/>'
    return (f'<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" stop-color="{t["bg_top"]}"/>'
            f'<stop offset="1" stop-color="{t["bg"]}"/></linearGradient></defs>'
            f'<rect width="{w}" height="{h}" fill="url(#bg)"/>')


def _axis_indicator(sc, proj):
    """The XYZ arrows in the bottom-right corner, turned as the camera is."""
    if not sc.state.get("axis_indicator", True):
        return ""
    W, H = proj.w * proj.k, proj.h * proj.k
    x0, y0, x1, y1 = sc._axes_viewport()
    cx, cy = (x0 + x1) / 2 * W, (1 - (y0 + y1) / 2) * H
    size = 0.32 * min((x1 - x0) * W, (y1 - y0) * H)
    out = []
    axes = [(proj.rot @ e, AXIS_COLORS[i], "XYZ"[i]) for i, e in enumerate(np.eye(3))]
    if sc.model.dim == 2:
        axes = axes[:2]
    for v, color, letter in sorted(axes, key=lambda a: a[0][2]):     # far ones first
        ex, ey = cx + v[0] * size, cy - v[1] * size
        out.append(f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{ex:.1f}" y2="{ey:.1f}" '
                   f'stroke="{color}" stroke-width="{2 * proj.k:.1f}" stroke-linecap="round"/>')
        out.append(f'<text x="{cx + v[0] * size * 1.25:.1f}" y="{cy - v[1] * size * 1.25:.1f}" '
                   f'font-family="Helvetica, Arial, sans-serif" font-size="{11 * proj.k:.0f}" '
                   f'fill="{color}" text-anchor="middle" dominant-baseline="middle">'
                   f'{letter}</text>')
    return "\n".join(out)


def svg_text(sc, k=1, transparent=False):
    """The 3D view as SVG vector shapes, `k` × the view's size."""
    proj = _Projector(sc, k)
    W, H = int(round(proj.w * k)), int(round(proj.h * k))
    keep = _keep_side(sc)
    items = _Items()
    t = THEMES[sc._dark]
    st = sc.state
    faces, mesh = st.get("faces", True), st.get("mesh_edges", False)
    light = bool(st.get("shading", True))
    covered = set()
    rv = sc.results
    if rv.shown and getattr(rv, "_surf", None) is not None:       # the contour's colors
        got = _results_colors(sc, rv._surf)
        pts, tri, cell = _triangles(rv._surf)
        if got is not None and tri is not None:
            (tv, at_points), table = got
            if at_points:                             # smooth across: split where it changes
                pts, tri, tv = _split(proj, pts, tri, tv)
                per = tv[tri].mean(axis=1)
            else:                                     # (a cell's number, if it has one)
                per = np.where(cell < len(tv), tv[np.minimum(cell, len(tv) - 1)], np.nan)
            n = len(table)
            idx = np.clip(np.floor(np.nan_to_num(per, nan=0.0) / 3.0 * n), 0, n - 1).astype(int)
            cols = table[idx, :3]
            cols[~np.isfinite(per)] = rgb("#8e8e93")
            _facets(items, proj, pts, tri, cols, keep, fill=faces, light=light)
            covered = {name for name, _, _ in rv._pieces}
    for n in sc.names:
        if not sc.visible.get(n):
            continue
        poly = sc._display.get(n, sc.model.parts[n])
        color = _part_rgb(sc, n)
        if n not in covered and poly.GetNumberOfPolys():
            pts, tri, _cell = _triangles(poly)
            if tri is not None:
                _facets(items, proj, pts, tri, np.tile(color, (len(tri), 1)), keep,
                        fill=faces, light=light)
        if mesh and poly.GetNumberOfPolys():          # the mesh's own edges (not the pieces)
            edges = poly.extract_all_edges()
            pts, seg = _lines(edges)
            _segments(items, proj, pts, seg, rgb(t["edge"] if faces else "#808080")
                      if faces else color, 1.0 * k, keep)
        if poly.GetNumberOfLines():                   # a drawing's lines, 2D boundaries
            pts, seg = _lines(poly)
            _segments(items, proj, pts, seg, color, 1.5 * k, keep)
    if st.get("feature_edges") and sc._edges is not None:          # feature edges
        blocks = sc._edges_map.GetInputDataObject(0, 0)
        import pyvista as pv
        for i, n in enumerate(sc.names):
            if not sc.visible.get(n):
                continue
            b = blocks.GetBlock(i)
            if b is None or not b.GetNumberOfCells():
                continue
            pts, seg = _lines(pv.wrap(b))
            _segments(items, proj, pts, seg, rgb(t["edge"]),
                      sc._edges.GetProperty().GetLineWidth() * k, keep)
    for a in sc.section.cap_actors():                 # the cut faces, filled
        if not a.GetVisibility():
            continue
        import pyvista as pv
        cap = pv.wrap(a.GetMapper().GetInputDataObject(0, 0))
        if cap is None or not cap.n_cells:
            continue
        pts, tri, _cell = _triangles(cap)
        if tri is not None:
            col = np.array(a.GetProperty().GetColor())
            _facets(items, proj, pts, tri, np.tile(col, (len(tri), 1)), None, light=light)
    bar = sc.colorbar.svg(W, H, k, dark=False if transparent else None) \
        if sc.colorbar.shown else ""
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
            f'viewBox="0 0 {W} {H}">\n'
            f'{_background(sc, W, H, transparent)}\n'
            f'<g id="model">\n{items.svg()}\n</g>\n'
            f'<g id="axis-indicator">\n{_axis_indicator(sc, proj)}\n</g>\n'
            f'<g id="color-bar">\n{bar}\n</g>\n</svg>\n')
