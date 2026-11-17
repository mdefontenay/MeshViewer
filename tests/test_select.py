"""Select ▾: what a click picks — the part, mesh nodes / edges / triangles (meshes only),
feature nodes / edges / faces — and the feature faces, edges and nodes themselves (on a
mesh: smooth edges found, gaps bridged, cut at corners and where another meets them)."""
import numpy as np
import pyvista as pv
from conftest import check, open_file, run

from meshviewer.core.features import components, cut_at_junctions, Features


def _core():
    check(list(components(5, [0, 3], [1, 4])) == [0, 0, 1, 2, 2], "components")
    f = Features(pv.Box(level=3).triangulate())
    check((f.region.max() + 1, f.curve.max() + 1, len(f.nodes)) == (6, 12, 8),
          f"box: 6 faces, 12 edges, 8 nodes ({f.region.max() + 1}, {f.curve.max() + 1}, "
          f"{len(f.nodes)})")
    f = Features(pv.Cylinder(resolution=40).triangulate())
    check((f.region.max() + 1, f.curve.max() + 1, len(f.nodes)) == (3, 2, 0),
          "cylinder: 3 faces, 2 circles, no node")
    f = Features(pv.Sphere())
    check(f.region.max() == 0 and not len(f.seg), "sphere: one face, no feature edge")
    box = pv.Box(level=3).triangulate()
    f = Features(box)
    pts = np.asarray(box.points)
    n = f.nearest_node(pts, (1.2, 1.1, 1.3))
    check(np.allclose(pts[n], (1, 1, 1)), "nearest node: the corner")
    c = f.nearest_curve(pts, (1.0, 1.0, 0.1))
    seg = pts[f.curve_segments(c)]
    check(np.allclose(seg[..., :2], 1.0), "nearest feature edge: the one along Z at x = y = 1")
    _straight_or_planar()


def _counts(f):
    return (int(f.curve.max()) + 1 if len(f.curve) else 0), len(f.nodes)


def _straight_or_planar():
    # a flat plate: its outline is coplanar, but cut at the corners -> 4 straight edges
    f = Features(pv.Plane(i_resolution=10, j_resolution=6).triangulate())
    check(_counts(f) == (4, 4), f"plate: 4 edges, 4 nodes {_counts(f)}")
    # a ring: two circles, each planar -> two edges, no node
    f = Features(pv.Disc(c_res=40))
    check(_counts(f) == (2, 0), f"ring: 2 circles, no node {_counts(f)}")
    # a twisted strip: its helical sides twist gently in 3D -> each one feature edge,
    # cut only at the strip's square ends
    t = np.linspace(0, 4 * np.pi, 200)
    side = np.c_[np.cos(t), np.sin(t), 0.3 * t]
    n = len(t)
    strip = pv.PolyData(np.r_[side, side + [0, 0, 0.2]],
                        np.concatenate([[4, i, i + 1, n + i + 1, n + i] for i in range(n - 1)]))
    f = Features(strip)
    longest = max(len(f.curve_segments(c)) for c in range(f.curve.max() + 1))
    check(_counts(f) == (4, 4) and longest == n - 1,
          f"helix: each side one feature edge, not cut by its twist {_counts(f)}, {longest}")
    _corners()
    # two plates crossing: each one's side edges are cut where the other's meet them
    a = pv.Plane(i_size=2, j_size=2, i_resolution=4, j_resolution=4).triangulate()
    b = pv.Plane(direction=(0, 1, 0), i_size=2, j_size=2, i_resolution=4,
                 j_resolution=4).triangulate()
    fa, fb = Features(a, tol=1e-7), Features(b, tol=1e-7)
    cut_at_junctions([fa, fb])
    check(_counts(fa) == (6, 6) and _counts(fb) == (6, 6),
          f"crossing plates: 2 sides each cut in two {_counts(fa)} {_counts(fb)}")
    # two plates sharing a side: lying on each other, nothing is cut
    c = pv.Plane(center=(2, 0, 0), i_size=2, j_size=2, i_resolution=4,
                 j_resolution=4).triangulate()
    fa, fc = Features(a, tol=1e-7), Features(c, tol=1e-7)
    cut_at_junctions([fa, fc])
    check(_counts(fa) == (4, 4) and _counts(fc) == (4, 4), "a shared side cuts nothing")
    _smooth()
    _creases()
    _zigzags()
    _bridges()


def _corners():
    from meshviewer.core.features import _runs
    t = np.linspace(0, 6 * np.pi, 120)                 # a helix: no corner
    check(_runs(np.c_[np.cos(t), np.sin(t), 0.2 * t], 30.0) == [], "helix: not cut")
    kink = np.array([[i, 0.0, 0.0] for i in range(6)] +
                    [[5 + i * np.cos(np.radians(27)), i * np.sin(np.radians(27)), 0] for i in (1, 2, 3)])
    check(_runs(kink, 30.0) == [5], f"a lone 27° kink: a corner ({_runs(kink, 30.0)})")
    a = np.radians(27) * np.arange(14)                 # a coarse circle, 27° at each point
    check(_runs(np.c_[np.cos(a), np.sin(a), 0 * a], 30.0) == [],
          "a coarse curve turning 27° at each point: not cut")
    check(_runs(np.array([[0, 0, 0], [1, 0, 0], [1, 1, 0.0]]), 30.0) == [1], "90°: cut")


def _line(pts, closed=False):
    """Mesh edges joining the points in turn (and back to the first)."""
    k = np.arange(len(pts) - (0 if closed else 1))
    return k, (k + 1) % len(pts)


def _zigzags():
    from meshviewer.core.features import _anchored
    def kept(pts, closed=False, anchor=(True, True)):
        lo, hi = _line(pts, closed)
        p = np.asarray(pts, dtype=float)
        n = len(p)
        found = np.ones(len(lo), bool)
        sharp = np.zeros(len(lo), bool)
        for end, on in zip((0, n - 1), anchor):         # a sharp edge going up at an end
            if on:
                p = np.r_[p, [p[end] + (0, 0, 1)]]
                lo, hi = np.r_[lo, end], np.r_[hi, len(p) - 1]
                found, sharp = np.r_[found, False], np.r_[sharp, True]
        return int(_anchored(found, lo, hi, sharp, p, 30.0).sum())
    x = np.arange(21.0)
    zig = np.c_[x, 0.2 * (x % 2), 0 * x]                # ±22°, back and forth
    check(kept(zig) == 0, "a zig-zag between two sharp edges: dropped")
    arc = np.c_[30 * np.sin(x / 30), 30 * np.cos(x / 30), 0 * x]
    check(kept(arc) == 20, f"a smooth arc between two sharp edges: kept ({kept(arc)})")
    s = np.c_[x, np.where(x < 10, 0.02 * (x - 0) ** 2, 4 - 0.02 * (20 - x) ** 2), 0 * x]
    check(kept(s) == 20, f"an S curve (one turn back): kept ({kept(s)})")
    line = np.c_[x, 0 * x, 0 * x]
    check(kept(line, anchor=(False, False)) == 0, "a floating line, both ends open: dropped")
    check(kept(line, anchor=(True, False)) == 20, "a line from a sharp edge, its end open: kept")
    a = np.linspace(0, 2 * np.pi, 40, endpoint=False)
    loop = np.c_[np.cos(a), np.sin(a), 0 * a]
    check(kept(loop, closed=True, anchor=(False, False)) == 40, "a floating closed loop: kept")


def _bridges():
    from meshviewer.core.features import _bridge
    # a triangulated plate, 20 x 4 squares; feature edges along y = 2 with a gap
    plate = pv.Plane(center=(10, 2, 0), i_size=20, j_size=4, i_resolution=20,
                     j_resolution=4).triangulate()
    p, lo, hi = _all_edges(plate)
    on = lambda y: (np.abs(p[lo, 1] - y) < 1e-9) & (np.abs(p[hi, 1] - y) < 1e-9)  # noqa: E731
    row, xm = on(2), (p[lo, 0] + p[hi, 0]) / 2
    for gap, want in ((4, 4), (10, 0)):
        net = row & ((xm < 4) | (xm > 4 + gap))
        add = _bridge(net, lo, hi, p, 30.0)
        check(add.sum() == want and (row[add] & (xm[add] > 4) & (xm[add] < 4 + gap)).all(),
              f"a {gap}-edge gap on a line: {want} mesh edges bridged ({add.sum()})")
        if want:                                         # then one feature edge
            both = net | add
            lines = pv.PolyData(p, lines=np.c_[np.full(both.sum(), 2), lo[both], hi[both]].ravel())
            check(_counts(Features(lines)) == (1, 2), "bridged: one feature edge, two ends")
    net = (row & (xm < 4)) | (on(3) & (xm > 8))          # facing, but not on one line
    check(not _bridge(net, lo, hi, p, 30.0).any(), "two edges side by side: not bridged")
    # a ring of a disc with 4 mesh edges missing: bridged along the ring
    disc = pv.Disc(inner=0.5, outer=1.5, r_res=4, c_res=48).triangulate()
    p, lo, hi = _all_edges(disc)
    r = np.linalg.norm(p[:, :2], axis=1)
    ring = (np.abs(r[lo] - 1) < 1e-6) & (np.abs(r[hi] - 1) < 1e-6)
    mid = (p[lo] + p[hi]) / 2
    ang = np.degrees(np.arctan2(mid[:, 1], mid[:, 0]))
    gap = ring & (ang > 0) & (ang < 4 * 7.5)
    add = _bridge(ring & ~gap, lo, hi, p, 30.0)
    check(gap.sum() == 4 and (add == gap).all(),
          f"a 4-edge gap in a circle: bridged along it ({add.sum()} of {gap.sum()})")


def _all_edges(poly):
    """Points (one per place) and every mesh edge (lo, hi) of a polygon mesh."""
    p, inv = np.unique(np.round(np.asarray(poly.points, dtype=float), 9), axis=0,
                       return_inverse=True)
    inv = inv.reshape(-1)
    faces = np.asarray(poly.faces).reshape(-1, 4)[:, 1:]          # triangles
    e = inv[np.r_[faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]]]
    e = np.unique(np.sort(e, axis=1), axis=0)
    return p, e[:, 0], e[:, 1]


def _creases():
    from meshviewer.core.features import _hysteresis, _tidy
    # a line of 6 mesh edges along x (points 0–6) and a branch going off at 90° (7)
    p = np.array([[i, 0.0, 0.0] for i in range(7)] + [[3.0, 1.0, 0.0]])
    e_lo, e_hi = np.array([0, 1, 2, 3, 4, 5, 3]), np.array([1, 2, 3, 4, 5, 6, 7])
    strong = np.array([1, 1, 0, 1, 1, 1, 0], bool)    # the third bends a little less
    weak = np.ones(7, bool)
    got = _hysteresis(strong, weak, e_lo, e_hi, p, 30.0)
    check(list(got) == [1, 1, 1, 1, 1, 1, 0], f"a gap in a sharp line is filled, not the branch {got}")
    # a short loose crease is mesh noise; the same along where the surface ends stays
    crease = np.array([0, 0, 0, 0, 0, 0, 1], bool)
    none = np.zeros(7, bool)
    check(not _tidy(crease, none, e_lo, e_hi, len(p)).any(), "a short loose crease goes")
    ends = np.array([1, 1, 1, 1, 1, 1, 0], bool)
    check(not _tidy(crease, ends, e_lo, e_hi, len(p)).any(),
          "a short crease branching off the surface's end goes too")
    long_p = np.array([[i, 0.0, 0.0] for i in range(21)])  # 20 mesh edges: a real crease
    lo, hi = np.arange(20), np.arange(1, 21)
    check(_tidy(np.ones(20, bool), np.zeros(20, bool), lo, hi, 21).all(), "a long crease stays")


def _hull(pts):
    return pv.PolyData(pts).delaunay_3d().extract_surface(
        algorithm="dataset_surface").triangulate().clean()


def _smooth():
    # a capsule (cylinder, a half sphere on each end), meshed from random points but for
    # the two circles where they meet: no sharp edge, two smooth ones
    rng = np.random.default_rng(1)
    t = np.linspace(0, 2 * np.pi, 240, endpoint=False)
    rings = [np.c_[np.cos(t), np.sin(t), np.full(len(t), z)] for z in (-1, 1)]
    a, z = rng.uniform(0, 2 * np.pi, 1500), rng.uniform(-0.97, 0.97, 1500)
    v = rng.normal(size=(1800, 3))
    v /= np.linalg.norm(v, axis=1)[:, None]
    v = v[np.abs(v[:, 2]) > 0.05]
    caps = v + np.c_[0 * v[:, :2], np.sign(v[:, 2])]
    capsule = _hull(np.r_[rings[0], rings[1], np.c_[np.cos(a), np.sin(a), z], caps])
    for dtype in (float, np.float32):                  # STL files are float32
        capsule.points = np.asarray(capsule.points, dtype=dtype)
        f = Features(capsule)
        check((f.region.max() + 1, *_counts(f)) == (3, 2, 0),
              f"capsule ({np.dtype(dtype).name}): 3 faces, the 2 circles where the "
              f"cylinder meets the caps ({f.region.max() + 1}, {_counts(f)})")
    v = rng.normal(size=(5000, 3))                     # a random sphere: no edge at all
    f = Features(_hull(v / np.linalg.norm(v, axis=1)[:, None]))
    check(not len(f.seg), f"random sphere: no chance edge ({len(f.seg)} mesh edges)")
    grid = pv.CylinderStructured(radius=np.array([1.0]), height=1.0, theta_resolution=61,
                                 z_resolution=21).extract_surface(
        algorithm="dataset_surface").clean()
    for mesh in (grid, grid.triangulate()):            # every grid line is straight / planar
        f = Features(mesh)
        check(_counts(f)[0] == 2, f"regular grid: only its 2 rims ({_counts(f)})")


def _click_middle(w):
    x, y = w.scene.p.renderer.GetSize()
    w.scene.click(x // 2, y // 2)


def test(app, files):
    _core()
    # CAD: no mesh kinds; the feature ones pick a face, an edge, a node
    w = open_file(app, files["step"])
    shown = [k for k, a in w.a_select.items() if a.isVisible()]
    check(shown == ["part", "feature_node", "feature_edge", "feature_face"],
          f"STEP: Part and the feature kinds ({shown})")
    el = w.scene.elements
    for kind, word in (("feature_face", "feature face"), ("feature_edge", "feature edge"),
                       ("feature_node", "feature node")):
        w.set_select_kind(kind)
        _click_middle(w)
        app.processEvents()
        check(len(el.items) == 1 and el.actors(), f"{kind}: one picked, drawn")
        check(w.sidebar.sel_label.text() == f"1 {word} selected",
              f"{kind}: the selection line ({w.sidebar.sel_label.text()})")
        check(not w.scene.selected_parts, f"{kind}: no part selected")
    check("X" in w.sidebar.info.text(), "feature node: its coordinates")
    w.set_select_kind("feature_face")
    _click_middle(w)
    check("area" in w.sidebar.info.text(), f"feature face: its area ({w.sidebar.info.text()})")
    w.a_deselect.trigger()
    check(not el.items and not el.actors(), "Deselect All clears the picked face")
    # Show ▸ Feature Edges on CAD: the borders of its faces, as in the CAD program
    sc = w.scene
    f = el.features("box")
    lines = el.feature_lines("box")
    check(lines.n_lines == len(f.seg) > 0, f"STEP: feature edges = face borders ({lines.n_lines})")
    two = {int(f.face_ids[r]) for r in f.seg_faces[0]}          # two faces side by side
    same = el.feature_lines("box", {next(iter(two))}).n_lines
    fewer = el.feature_lines("box", two).n_lines
    check(same == lines.n_lines and 0 < fewer < lines.n_lines,
          f"hidden faces: a border goes once no face beside it shows ({same}, {fewer})")
    check(sc._edges is not None and sc._edges.GetVisibility(), "STEP: feature edges drawn")
    sc.select("box")                                     # the outline: those edges too
    if sc._outline is not None:
        sc._outline.GetMapper().Update()
    out =sc._outline.GetMapper().GetInput() if sc._outline is not None else None
    check(out is not None and out.GetNumberOfLines() >= lines.n_lines,
          "part outline: silhouette + the feature edges")
    sc.select(None)
    # Measure Selected: an edge of the box (its faces at 90°), a face, a node
    from meshviewer.render.element_details import details
    w.set_select_kind("feature_edge")
    _click_middle(w)
    got = details(el)
    rows = dict(got[1]) if got else {}
    check(got and "Length" in rows and rows.get("Dihedral angle") == "90°"
          and w.sidebar.selected_panel.title.text() == got[0],
          f"Measure Selected: an edge, 90° between its faces ({rows})")
    w.set_select_kind("feature_face")
    _click_middle(w)
    rows = dict(details(el)[1])
    check({"Area", "Centroid", "Perimeter"} <= set(rows) and
          ("Normal" in rows or "Mean normal" in rows), "Measure Selected: a face")
    w.set_select_kind("feature_node")
    _click_middle(w)
    rows = dict(details(el)[1])
    check({"Coordinates", "Distance to origin"} <= set(rows), "Measure Selected: a node")
    from meshviewer.core import element_info as ei
    t = np.linspace(0, np.pi, 20)
    arc = np.column_stack([3 * np.cos(t) + 1, 3 * np.sin(t), np.zeros_like(t)])
    c = ei.fit_circle(arc)
    check(c and abs(c["radius"] - 3) < 1e-9 and np.allclose(c["center"], [1, 0, 0])
          and not c["closed"], "an arc: radius 3, center (1, 0, 0)")
    check(ei.fit_circle(np.array([[0, 0, 0], [1, 0, 0], [2, 0, 0.0]])) is None
          and ei.straight(np.array([[0, 0, 0], [1, 0, 0], [2, 0, 0.0]])) is not None,
          "a straight edge: no circle, a direction")
    check(abs(ei.dihedral([0, 0, 1], [1, 0, 0]) - 90) < 1e-9
          and abs(ei.dihedral([0, 0, 1], [0, 0, 1]) - 180) < 1e-9, "dihedral: 90°, flat 180°")
    w.set_select_kind("mesh_node")
    check(w.select_kind == "part" and w.a_select["part"].isChecked(),
          "CAD: a mesh kind falls back to Part")
    _click_middle(w)
    check(w.scene.selected_parts, "Part: a click selects the part")
    w.close()

    # a mesh: every kind
    w = open_file(app, files["cgns"])
    check(all(a.isVisible() for a in w.a_select.values()), "mesh: every kind")
    el = w.scene.elements
    for kind in ("mesh_node", "mesh_edge", "mesh_cell", "feature_face"):
        w.set_select_kind(kind)
        _click_middle(w)
        check(len(el.items) == 1 and el.actors(), f"mesh {kind}: one picked")
    w.set_select_kind("volume_cell")                     # a volume cell, under the click
    _click_middle(w)
    rows = dict(details(el)[1]) if el.items else {}
    check(len(el.items) == 1 and rows.get("Type") == "Hexahedron" and "Volume" in rows
          and "Skewness" in rows and el.actors(),
          f"Volume Cell: picked, its type, volume and quality ({rows})")
    check(w.a_select["volume_cell"].isVisible(), "Volume Cell offered on a mesh with cells")
    w.set_select_kind("feature_face")
    _click_middle(w)
    name, face = el.items[0]
    poly = w.scene.model.parts[name]
    cells = el.features(name).face_cells(face)
    check(0 < len(cells) <= poly.n_cells, f"feature face: {len(cells)} of {poly.n_cells} cells")
    check(set(el._features) == set(w.scene.model.parts), "mesh: every boundary done together")
    w.scene.click(0, 0)                                  # empty space
    check(not el.items, "a click on nothing clears")
    w.set_select_kind("mesh_cell")
    w.close()
    # a 2D mesh: mesh cells (quads), no feature face; its boundaries are lines
    w = open_file(app, files["fluent2d"])
    shown = [a.text() for a in w.a_select.values() if a.isVisible()]
    check(shown == ["Part", "Mesh Node", "Mesh Edge", "Mesh Cell", "Feature Node",
                    "Feature Edge"], f"2D mesh: its kinds ({shown})")
    el, sc = w.scene.elements, w.scene
    for kind, word in (("mesh_cell", "mesh cell"), ("feature_edge", "feature edge"),
                       ("feature_node", "feature node"), ("mesh_edge", "mesh edge")):
        w.set_select_kind(kind)
        _click_middle(w)
        check(len(el.items) == 1 and w.sidebar.sel_label.text() == f"1 {word} selected",
              f"2D {kind}: one picked ({w.sidebar.sel_label.text()})")
    lines = [n for n, p in sc.model.parts.items() if not p.GetNumberOfPolys()]
    zone = next(n for n in sc.model.parts if n not in lines)
    check(all(len(el.features(n).seg) == sc.model.parts[n].n_cells for n in lines),
          "2D boundaries: their lines are feature edges")
    w.set_select_kind("mesh_cell")
    pt = sc.model.parts[lines[0]].points[0]
    check(el._cell_beside(pt) is not None and el._cell_beside(pt)[0] == zone,
          "Mesh Cell on a boundary line: the cell beside it")
    w.set_select_kind("feature_face")
    check(w.select_kind == "part", "2D mesh: no feature face")
    w.close()
    w = open_file(app, files["dxf"])                     # a drawing: Edge and Node
    shown = [a.text() for a in w.a_select.values() if a.isVisible()]
    check(sorted(shown) == ["Edge", "Node"] and w.scene.elements.kind == "feature_edge",
          f"drawing: Select ▸ Edge, Node ({shown}, {w.scene.elements.kind})")
    sc = w.scene
    poly = sc.model.parts["PROFILE"]
    p = (np.asarray(poly.points[0]) + np.asarray(poly.points[1])) / 2
    r = sc.p.renderer
    r.SetWorldPoint(*p, 1.0)
    r.WorldToDisplay()
    x, y, _ = r.GetDisplayPoint()
    sc.click(int(x), int(y))
    sp = w.sidebar.selected_panel                       # open for drawings (no parts list)
    keys = lambda: [c.text() for c in sp._cells[::2]]   # noqa: E731
    check(w.sidebar.is_open("selected") and len(sc.elements.items) == 1
          and sp.title.text().startswith("Edge") and "Length" in keys(),
          f"drawing: a click picks an edge, Measure Selected says so ({sp.title.text()})")
    w.set_select_kind("feature_node")
    sc.click(int(x), int(y))
    check(sp.title.text().startswith("Node"), f"drawing: a node ({sp.title.text()})")
    # 2D: Node / Edge reach the nearest one on screen (PICK_PX), a node before its line
    def at(p, dx=0.0, dy=0.0):                          # display pixels, offset in points
        r.SetWorldPoint(*p, 1.0)
        r.WorldToDisplay()
        px, py, _ = r.GetDisplayPoint()
        return int(round(px + sc.pixels(dx))), int(round(py + sc.pixels(dy)))
    w.set_select_kind("feature_edge")
    w.sidebar.selected_section.set_expanded(False)
    sc.click(*at((20.0, 0.0, 0.0), dy=-6))
    el = sc.elements
    picked = el.items and np.asarray(poly.points)[
        el.features(el.items[0][0]).curve_segments(el.items[0][1]).reshape(-1)]
    check(len(el.items) == 1 and np.allclose(picked[:, 1], 0.0),
          f"2D: a line 6 points away picked ({el.items})")
    check(w.sidebar.is_open("selected"), "a pick opens Measure Selected")
    sc.click(*at((20.0, 0.0, 0.0), dy=-20))
    check(not el.items, f"2D: nothing 20 points away ({el.items})")
    w.set_select_kind("feature_node")
    sc.click(*at((40.0, 20.0, 0.0), dx=5, dy=-5))
    check(len(el.items) == 1 and np.allclose(poly.points[el.items[0][1]], (40, 20, 0)),
          f"2D: the corner node near the click ({el.items})")
    w.set_select_kind("feature_edge")
    # the Measuring Tool on a 2D file: a point anywhere inside the axes
    w.sidebar.show_section("measure", expand=True)
    m = sc.measure
    m.set_mode("distance")
    mp = w.sidebar.measure_panel
    check(mp.snap_row.label.text() == "Snap to edges", "2D: Snap to edges")
    m.snap = True                                    # a line, then a corner over its line
    sc.click(*at((12.0, 20.0, 0.0), dy=6))
    sc.click(*at((0.0, 0.0, 0.0), dx=4, dy=-4))
    check(len(m.points) == 2 and abs(m.points[0][1] - 20) < 1e-9 and abs(m.points[0][0] - 12) < 0.5
          and np.allclose(m.points[1], 0.0),
          f"2D: snapped to the line and the corner ({[list(np.round(q, 3)) for q in m.points]})")
    m.snap = False
    m.set_mode("distance")
    for px in ((5.0, 5.0), (25.0, 15.0)):
        r.SetWorldPoint(px[0], px[1], 0.0, 1.0)
        r.WorldToDisplay()
        dx, dy, _ = r.GetDisplayPoint()
        sc.click(int(dx), int(dy))
    check(len(m.points) == 2 and abs(m.points[0][0] - 5) < 0.2 and abs(m.points[1][1] - 15) < 0.2,
          f"2D: two points in empty space ({[list(np.round(q, 2)) for q in m.points]})")
    r.SetWorldPoint(500.0, 500.0, 0.0, 1.0)
    r.WorldToDisplay()
    check(sc.flat_point(*r.GetDisplayPoint()[:2]) is None, "2D: not outside the axes")
    m.set_mode("off")
    w.close()
    w = open_file(app, files["step"])
    check(w.select_kind == "part", "after a drawing: the window's kind as before")
    w.close()


def field_checks(app, files):
    """Measure Selected ▸ Field Values: a node's values, an edge's length-weighted and
    triangles' and parts' area-weighted means, in Contours' units; none without fields."""
    from meshviewer.core.fields import field_values as values_of
    from meshviewer.core.units import nice_num
    from meshviewer.render.element_details import field_values
    w = open_file(app, files["tecplot"])
    sc, sb = w.scene, w.sidebar
    el, sp = sc.elements, sb.selected_panel
    floor = sc.model.parts["FLOOR"]
    cp_floor = np.asarray(values_of(floor, "cp")[0], dtype=float)
    p_floor = np.asarray(values_of(floor, "p")[0], dtype=float)
    w.set_select_kind("mesh_node")
    el._take(("FLOOR", 3), False)
    app.processEvents()
    fv = field_values(el)
    got = dict(fv["fields"])
    check(not fv["mean"] and abs(got["cp"] - cp_floor[3]) < 1e-12
          and abs(got["p"] - p_floor[3]) < 1e-9 and "__speed__" in got,
          "a node: every field's own value (speed too)")
    rows = dict(sp.field_rows)
    check(not sp.fields_box.isHidden() and "Pressure coefficient cp" in rows
          and rows["Pressure coefficient cp"] == nice_num(cp_floor[3])
          and not any(k.startswith("Avg.") for k in rows),
          f"the panel: Field Values, no Avg. for a node ({list(rows)[:3]})")
    w.set_select_kind("mesh_edge")
    ids = list(floor.get_cell(0).point_ids)
    a, b = sorted(ids[:2])
    el._take(("FLOOR", (a, b)), False)
    app.processEvents()
    got = dict(field_values(el)["fields"])
    check(abs(got["cp"] - (cp_floor[a] + cp_floor[b]) / 2) < 1e-12,
          "an edge: the mean along it")
    c, d = sorted(ids[1:3])
    el._take(("FLOOR", (c, d)), True)                  # and a second one: length-weighted
    pts = np.asarray(floor.points)
    la, lb = np.linalg.norm(pts[b] - pts[a]), np.linalg.norm(pts[d] - pts[c])
    want = (la * (cp_floor[a] + cp_floor[b]) / 2 + lb * (cp_floor[c] + cp_floor[d]) / 2) / (la + lb)
    got = dict(field_values(el)["fields"])
    check(abs(got["cp"] - want) < 1e-12, "two edges: length-weighted")
    check(any(k == "Avg. Pressure coefficient cp" for k, _ in sp.field_rows)
          and "Length-weighted" in sp.fields_note.text(), "the panel: Avg., length-weighted")
    w.set_select_kind("mesh_cell")
    sphere = sc.model.parts["SPHERE"]
    cp_s = np.asarray(values_of(sphere, "cp")[0], dtype=float)
    el._take(("SPHERE", 0), False)
    el._take(("SPHERE", 1), True)
    app.processEvents()
    sizes = sphere.compute_cell_sizes(length=False, volume=False).cell_data["Area"]
    means = [cp_s[list(sphere.get_cell(k).point_ids)].mean() for k in (0, 1)]
    want = (sizes[0] * means[0] + sizes[1] * means[1]) / (sizes[0] + sizes[1])
    got = dict(field_values(el)["fields"])
    check(abs(got["cp"] - want) < 1e-9, f"two triangles: area-weighted ({got['cp']:.5g})")
    w.set_select_kind("part")
    sb._selection_changed(["SPHERE"])
    app.processEvents()
    fv = field_values(el)
    got = dict(fv["fields"])
    tri = sphere.compute_cell_sizes(length=False, volume=False).cell_data["Area"]
    cell = np.asarray(sphere.point_data_to_cell_data().cell_data["cp"], dtype=float)
    check(fv["how"] == "area" and abs(got["cp"] - (tri * cell).sum() / tri.sum()) < 1e-9
          and sp.title.text().endswith("SPHERE") and not sp.fields_box.isHidden(),
          "a part: area-weighted over it, its name on top")
    # in Contours' units: p in Pa shown in kPa
    cp_panel = sb.contours_panel
    cp_panel.set_units("p", "Pa", "kPa")
    app.processEvents()
    rows = dict(sp.field_rows)
    check(rows.get("Avg. Pressure p", "").endswith("kPa")
          and abs(float(rows["Avg. Pressure p"].split()[0]) - got["p"] / 1000)
          < 1e-3 * abs(got["p"] / 1000) + 1e-12, f"in Contours' units ({rows.get('Avg. Pressure p')})")
    sb._selection_changed([])
    app.processEvents()
    check(sp.fields_box.isHidden(), "nothing selected: no Field Values")
    w.close()
    w = open_file(app, files["step"])                  # no solution fields
    w.set_select_kind("feature_face")
    w.scene.elements._take(("box", 0), False)
    app.processEvents()
    check(w.sidebar.selected_panel.fields_box.isHidden() and field_values(w.scene.elements)
          is None, "no solution fields: no Field Values")
    w.close()


def _all(app, files):
    test(app, files)
    field_checks(app, files)


if __name__ == "__main__":
    run(_all)
