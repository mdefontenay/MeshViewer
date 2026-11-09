"""CFD tools on a CGNS mesh whose cells are polyhedra (B7): cut cells on the section,
first cell height (y+), cell quality histogram and colours."""
import numpy as np

from conftest import check, open_file, run, wait


def test(app, files):
    for key in ("cgns", "ngon", "mixed"):
        w = open_file(app, files[key])
        sc, sb = w.scene, w.sidebar
        sp = sb.section_panel
        sp.enable.setChecked(True)
        sp.fill.setChecked(True)
        sc.section.set_plane(origin=(0.5, 0.5, 0.5), normal=(1, 0, 0))
        sc.section.update_caps() if hasattr(sc.section, "update_caps") else None
        wait(app, lambda: sc.section._volume is not None, 30)
        app.processEvents()
        check(sc.section._vol_cut is not None, f"{key}: the section shows the cut cells")
        # CFD: first cell layer on the wall -> y+
        sb.show_section("cfd")
        cp = sb.cfd_panel
        cp.boundary.setCurrentIndex(cp.boundary.findData("wall"))
        cp.activate(True)
        wait(app, lambda: "wall" in cp._heights, 30)
        h = cp._heights["wall"]
        hv = np.nanmax(np.asarray(h, dtype=float)) if h is not None else np.nan
        check(np.isfinite(hv) and 0.005 < hv < 0.05, f"{key}: first cell height on the wall {hv:.4g}")
        # Cell quality: a real histogram (several bars), colours on the cut
        sb.show_section("cells")
        qp = sb.cell_panel
        qp.metric.setCurrentIndex(qp.metric.findData("aspect"))
        qp.activate(True)
        wait(app, lambda: qp.hist.counts is not None, 30)
        n_bars = int(np.count_nonzero(qp.hist.counts))
        check(sc.quality.is_volume and n_bars > 1, f"{key}: volume cells, {n_bars} bars")
        w.close()


if __name__ == "__main__":
    run(test)
