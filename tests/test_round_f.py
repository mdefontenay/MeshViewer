"""F1, F2, F3, F5, F7: Next cell hover, no y+ along the flow, formula links,
file unit (asked once, Info menu), Distance with one point."""
import numpy as np

from conftest import check, open_file, run, wait


def test(app, files):
    # F5: the unit is asked the first time; STEP preselects its own (mm)
    w = open_file(app, files["step"])
    d = getattr(w, "_unit_dialog", None)
    check(d is not None and d.unit == "mm", f"STEP: asked, mm preselected ({d and d.unit})")
    d.actions["cm"].setChecked(True)
    d._ok()
    check(w.scene.model.units == "cm" and w.scene.measure.unit_scale()[1] == "cm",
          "chosen unit used")
    check(not any(a.data() is None for a in w.a_units), "no 'no unit' button")
    ip = w.sidebar.info_panel
    ip.file_unit.setCurrentIndex(ip.file_unit.findData("m"))
    check(w.scene.model.units == "m", "Info ▸ File unit changes it")
    w.remember_view()
    w.close()
    w = open_file(app, files["step"])
    check(getattr(w, "_unit_dialog", None) is None and w.scene.model.units == "m",
          "remembered: not asked again")
    w.a_file_unit.trigger()                              # toolbar ✎: the sheet again
    d = getattr(w, "_unit_dialog", None)
    check(d is not None and d.unit == "m", f"✎ opens the unit sheet on the current unit")
    d.actions["in"].setChecked(True)
    d._ok()
    check(w.scene.model.units == "in" and w.scene.model.file_units == "mm",
          "✎ changes it; the file still says mm")
    # F1: Next cell explains itself
    sb = w.sidebar
    tip = sb.inflation_panel.y_des.toolTip()
    check("smooth" in tip and "aspect ratio" in tip, "Next cell hover text")
    # F2: no y+ along the flow tab
    check(set(w.inflation_view.tabs) == {"plot", "section"}, f"tabs {sorted(w.inflation_view.tabs)}")
    w.close()
    # F7: Distance, one point = from the origin; two = between them
    w = open_file(app, files["cgns"])
    m = w.scene.measure
    m.set_mode("distance")
    m.add_point(np.array([3.0, 4.0, 0.0]))
    r = m.result()
    check("from_origin" not in r and len(r["points"]) == 1, "toggle off: 1 / 2 points, no origin")
    m.add_point(np.array([3.0, 4.0, 2.0]))
    r = m.result()
    check(abs(r["distance"] - 2.0) < 1e-9 and "from_origin" not in r, "two points: 2 apart")
    sb = w.sidebar
    sb.measure_panel.from_origin.setChecked(True)            # the old Point tool
    m.add_point(np.array([3.0, 4.0, 0.0]))
    r = m.result()
    check(abs(r["from_origin"] - 5.0) < 1e-9 and r["xyz"][:2] == [3.0, 4.0],
          "From origin: one point, 5 from the origin")
    m.add_point(np.array([6.0, 8.0, 0.0]))
    r = m.result()
    check(abs(r["from_origin"] - 10.0) < 1e-9 and "distance" not in r,
          "From origin: the next click is a new point")
    sb.measure_panel.from_origin.setChecked(False)
    check([a.data() for a in sb.measure_panel.mode_actions] == ["distance", "angle", "area"]
          if all(a.data() for a in sb.measure_panel.mode_actions) else
          len(sb.measure_panel.mode_actions) == 3, "no Point mode")
    # F3: the y+ formulas popup has CFD Online links and opens next to the sidebar
    from meshviewer.gui.panels.cfd import YPLUS_FORMULAS
    check(any(isinstance(i, tuple) and i[0] == "link" for i in YPLUS_FORMULAS) and
          any(isinstance(i, tuple) and len(i) == 3 and i[0] != "link" for i in YPLUS_FORMULAS),
          "y+ formula linked + CFD Online link")
    fb = sb.cfd_panel.yplus_formulas
    sb.show_section("cfd", expand=True)
    fb.open()
    app.processEvents()
    side_right = sb.mapToGlobal(sb.rect().topRight()).x()
    check(fb.dialog.x() >= side_right, f"popup next to the sidebar ({fb.dialog.x()} ≥ {side_right})")
    fb.dialog.close()
    w.close()


if __name__ == "__main__":
    run(test)
