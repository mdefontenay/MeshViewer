"""Select ▾: what a click picks — the part, mesh nodes / edges / triangles (meshes only),
feature nodes / edges / faces — and the feature faces, edges and nodes themselves (on a
mesh: smooth edges found, straight or planar, cut where another meets them)."""
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
    # a twisted strip: its helical sides are cut into planar pieces
    t = np.linspace(0, 4 * np.pi, 200)
    side = np.c_[np.cos(t), np.sin(t), 0.3 * t]
    n = len(t)
    strip = pv.PolyData(np.r_[side, side + [0, 0, 0.2]],
                        np.concatenate([[4, i, i + 1, n + i + 1, n + i] for i in range(n - 1)]))
    f = Features(strip)
    pts = np.asarray(strip.points)
    flat = True
    for c in range(f.curve.max() + 1):
        p = pts[np.unique(f.curve_segments(c))]
        if len(p) > 3:                                 # the points of one edge: one plane
            s = np.linalg.svd(p - p.mean(axis=0), compute_uv=False)
            flat &= s[-1] <= 0.05 * s[0]
    check(_counts(f)[0] > 10 and flat, f"helix: planar pieces ({_counts(f)[0]})")
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
    name, face = el.items[0]
    poly = w.scene.model.parts[name]
    cells = el.features(name).face_cells(face)
    check(0 < len(cells) <= poly.n_cells, f"feature face: {len(cells)} of {poly.n_cells} cells")
    check(set(el._features) == set(w.scene.model.parts), "mesh: every boundary done together")
    w.scene.click(0, 0)                                  # empty space
    check(not el.items, "a click on nothing clears")
    w.set_select_kind("mesh_cell")
    w.close()
    w = open_file(app, files["dxf"])                     # a drawing: no Select ▾
    check(not w._select_shown and not w.m_select.menuAction().isVisible(),
          "drawing: no Select")
    w.close()


if __name__ == "__main__":
    run(test)
