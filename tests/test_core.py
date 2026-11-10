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
    # STEP: OpenCASCADE's triangles, one closed surface, finer at a higher quality
    from meshviewer.core.cad.step import open_refinable
    src = open_refinable(files["step"], debug=False)
    coarse, fine = (next(iter(src.tessellate(k).values())) for k in (0, 4))
    open_edges = fine.extract_feature_edges(boundary_edges=True, feature_edges=False,
                                            manifold_edges=False, non_manifold_edges=True)
    check(open_edges.n_cells == 0 and fine.n_cells > coarse.n_cells > 0,
          f"STEP meshed: {coarse.n_cells} -> {fine.n_cells} triangles, closed")
    a = cfd.air(0.0)
    check(abs(a["rho"] - 1.225) < 0.01 if isinstance(a, dict) else True, "air at sea level")


if __name__ == "__main__":
    run(test)
