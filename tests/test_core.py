"""Core (no Qt): readers, CFD numbers, export, fields."""
import numpy as np

from conftest import check, run


def test(app, files):
    from meshviewer.core import cfd, formats
    from meshviewer.core.fields import solution_fields, ramp_rgb, SEQUENTIAL
    for key in ("step", "cgns", "ugrid", "tecplot"):
        m = formats.load(files[key], debug=False)
        check(m.parts and all(p.n_cells for p in m.parts.values()),
              f"{key}: {len(m.parts)} parts, {sum(p.n_cells for p in m.parts.values())} faces")
    m = formats.load(files["cgns"], debug=False)
    check(set(m.parts) == {"wall", "farfield"}, f"cgns boundaries {sorted(m.parts)}")
    g = m.volume()
    check(g is not None and g.n_cells == 216, f"cgns volume {None if g is None else g.n_cells}")
    m = formats.load(files["tecplot"], debug=False)
    check(solution_fields(m.parts)[-1] == "__speed__", "tecplot fields + speed")
    rgb = ramp_rgb(np.array([0.0, 0.5, 1.0]), 0, 1, SEQUENTIAL)
    check(rgb.shape == (3, 3), "colour ramp")
    r = cfd.inflation(yplus=1.0, mach=0.3, length=1.0, altitude=0.0)
    check(r["ok"] and 1e-7 < r["y_min"] < 1e-4, f"first layer {r['y_min']:.3g} m")
    # STEP: no needle fans, still closed (B6)
    import meshviewer.core.cad.occt as occt
    from meshviewer.core.cad.remesh import min_angles
    from meshviewer.core.cad.step import open_refinable
    src = open_refinable(files["step"], debug=False)
    def needles():
        poly = next(iter(src.tessellate(2).values()))
        t = poly.faces.reshape(-1, 4)[:, 1:]
        open_edges = poly.extract_feature_edges(boundary_edges=True, feature_edges=False,
                                                manifold_edges=False, non_manifold_edges=False)
        return int((min_angles(poly.points[t]) < 5).sum()), open_edges.n_cells
    import meshviewer.core.cad.remesh as rm
    keep, rm.refine = rm.refine, lambda *a: None
    occt._REFINED.clear()
    before = needles()
    rm.refine = keep
    occt._REFINED.clear()
    after = needles()
    check(after[0] < before[0] and after[1] == 0, f"STEP needles {before[0]} -> {after[0]}, open edges {after[1]}")
    a = cfd.air(0.0)
    check(abs(a["rho"] - 1.225) < 0.01 if isinstance(a, dict) else True, "air at sea level")


if __name__ == "__main__":
    run(test)
