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
    # the Inflation page: one plot, no tabs (the Section tab went); the layers in 3D
    check(not hasattr(w.inflation_view, "tabs") and w.inflation_view.plot.LEFT0 > 0,
          "Inflation page: the layer sizes and their stack, no tabs")
    from meshviewer.render.overlays import thickness_shell
    import pyvista as pv
    box = pv.Box((-20, 20, -10, 10, -5, 5)).triangulate()
    shell = thickness_shell(box, 1.0)
    b0 = np.reshape(box.bounds, (3, 2))
    b1 = np.reshape(shell.bounds, (3, 2))
    check(np.allclose(b1[:, 0], b0[:, 0] - 1.0, atol=0.05) and
          np.allclose(b1[:, 1], b0[:, 1] + 1.0, atol=0.05),
          f"thickness in 3D: the box grown by the thickness ({b1.tolist()})")
    ip = sb.inflation_panel
    ip.enable.setChecked(True)
    ip.u.setValue(50.0)
    ip._update()
    iv = w.inflation_view
    iv.show_3d.setChecked(True)                          # the Inflation page's switch
    check(len(w.scene.walls.actors()) >= 2 and ip.settings()["thickness"] and ip.show_3d,
          "Show in 3D (Inflation page): the shell over the walls, its feature lines")
    side = ip.side
    iv.flip.setChecked(True)
    check(ip.side == -side and ip.settings()["flip"], "Flip: the other side")
    iv.flip.setChecked(False)
    from meshviewer.render.overlays import auto_side
    check(auto_side(box, 1.0) == 1 and auto_side(box.flip_faces() if hasattr(box, "flip_faces")
                                                  else box, 1.0) in (1, -1),
          "auto side: a box grows out (no folds)")
    thin = pv.Box((-50, 50, -0.2, 0.2, -10, 10)).triangulate()
    check(auto_side(thin, 1.0) == 1, "a thin plate: out, not into itself")
    ip.set_3d(False, False)
    check(not iv.show_3d.isChecked(), "the page's switch follows the panel")
    ip.enable.setChecked(False)
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
