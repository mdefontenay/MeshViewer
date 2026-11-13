"""Results section: Tecplot fields coloured on the boundaries."""
from conftest import check, open_file, run


def test(app, files):
    w = open_file(app, files["tecplot"])
    sc, sb = w.scene, w.sidebar
    rp = sb.results_panel
    check(rp.field.currentData() == "yplus", f"default field {rp.field.currentData()}")
    rp.colour_on.setChecked(True)
    app.processEvents()
    check(sc.results.shown, "boundaries coloured")
    rp.field.setCurrentIndex(rp.field.findData("cp"))
    app.processEvents()
    from meshviewer.core.fields import COLORMAPS
    check(rp.cmap.currentData() == "rainbow" and rp.bar.stops == COLORMAPS["rainbow"]
          and rp.bar.lo < -1.0 and 0.9 < rp.bar.hi <= 1.0,
          f"cp: rainbow by default, real range {rp.bar.lo:.3g}..{rp.bar.hi:.3g}")
    lo0, hi0 = rp.bar.lo, rp.bar.hi
    rp.cmap.setCurrentIndex(rp.cmap.findData("coolwarm"))
    app.processEvents()
    check(rp.bar.stops == COLORMAPS["coolwarm"] and (rp.bar.lo, rp.bar.hi) == (lo0, hi0)
          and rp.cmap.text() == "", f"blue–white–red: same real range, menu shows colours only")
    check("diverging" not in COLORMAPS, "blue–grey–red removed")
    import numpy as np
    drawn = lambda: np.asarray(sc.results._surf.point_data["ResultRGB"]).astype(int).sum()   # noqa: E731
    before = drawn()
    sc.set_selection(["SPHERE"])
    app.processEvents()
    check(drawn() > before, "selected boundary lighter over the colours (B3)")
    sc.set_selection([])
    check(drawn() == before, "deselected: colours back")
    sb._visibility_changed(["SPHERE"], False)          # FLOOR alone: cp = 0 there
    app.processEvents()
    check(abs(rp.bar.lo) < 1e-3 and abs(rp.bar.hi) < 1e-3, f"auto range follows the shown "
          f"boundaries {lo0:.3g}..{hi0:.3g} -> {rp.bar.lo:.3g}..{rp.bar.hi:.3g}")
    sb._visibility_changed(["SPHERE"], True)
    app.processEvents()
    check((rp.bar.lo, rp.bar.hi) == (lo0, hi0), "and back when SPHERE is shown again")
    sb._visibility_changed(["FLOOR"], False)
    app.processEvents()
    check(sc.results.shown, "still shown after hiding FLOOR")
    rp.field.setCurrentIndex(rp.field.findData("__speed__"))
    app.processEvents()
    check(rp.bar.hi > rp.bar.lo and not hasattr(rp, "values"), "speed shown; no Values button")
    # units: p in Pa in the file, shown in kPa
    rp.field.setCurrentIndex(rp.field.findData("p"))
    app.processEvents()
    check(not rp.file_unit.isHidden() and rp.shown_unit.isHidden()
          and rp.file_unit.currentData() == "" and rp.file_unit.findData("GPa") > 0
          and rp.file_unit.findData("K") < 0 and not rp.unit_note.isHidden(),
          "p: Unit in file (As written, pressure units), Shown in once it is known")
    lo0, hi0 = rp.bar.lo, rp.bar.hi
    rp.file_unit.setCurrentIndex(rp.file_unit.findData("Pa"))
    rp.shown_unit.setCurrentIndex(rp.shown_unit.findData("kPa"))
    app.processEvents()
    check(not rp.shown_unit.isHidden() and rp.unit_note.isHidden(), "p in Pa: Shown in appears")
    check(abs(rp.bar.hi - hi0 / 1000) < 1e-9 * max(1, hi0) and rp.hi_unit.text() == "kPa",
          f"p in kPa: {hi0} Pa -> {rp.bar.hi} {rp.hi_unit.text()}")
    rp.field.setCurrentIndex(rp.field.findData("cp"))
    app.processEvents()
    check(rp.file_unit.isHidden() and rp.shown_unit.isHidden() and rp.hi_unit.text() == ""
          and rp.unit_note.text() == "Pressure coefficient cp has no unit.",
          f"cp: a known field with no unit, nothing to pick ({rp.unit_note.text()})")
    rp.field.setCurrentIndex(rp.field.findData("__speed__"))
    app.processEvents()
    rp.hi.setValue(1.0)
    rp._update()
    check(rp.bar.hi == 1.0, "typed max")
    w.remember_view()
    from meshviewer.gui import memory
    st = memory.load(w.path)
    check(st["results"]["units"].get("p") == ["Pa", "kPa"], "p's units remembered")
    check(st["results"]["field"] == "__speed__" and st["results"]["hi"] == 1.0
          and st["results"]["cmap"] == "coolwarm", "remembered (field, range, colour map)")

    # a log scale: Min the smallest value above zero, the middle the geometric one
    import numpy as np
    rp.field.setCurrentIndex(rp.field.findData("p"))
    rp.lo.setValue(None)
    rp.hi.setValue(None)
    app.processEvents()
    rp.scale_acts["log"].trigger()
    app.processEvents()
    vals = rp.shown_values("p", rp._values("p"))
    pos = vals[vals > 0]
    check(rp.log and abs(rp.bar.lo - pos.min()) < 1e-9 * pos.max() and rp.bar.log
          and abs(rp.bar.value_at(0.5) - np.sqrt(rp.bar.lo * rp.bar.hi)) < 1e-6 * rp.bar.hi
          and sc.results.spec is not None and sc.results.spec[4] is True,
          f"log scale: {rp.bar.lo:.4g}…{rp.bar.hi:.4g}, middle {rp.bar.value_at(0.5):.4g}")
    rp.lo.setValue(-1.0)                       # typed at or below zero: the auto Min
    app.processEvents()
    check(rp.bar.lo > 0, "log: a Min at or below zero is not used")
    rp.lo.setValue(None)
    rp.scale_acts["linear"].trigger()
    app.processEvents()
    check(not rp.log and sc.results.spec[4] is False, "back to linear")

    # Position X / Y / Z: the nodes' coordinates, in the toolbar's unit
    rp.hi.setValue(None)
    rp.field.setCurrentIndex(rp.field.findData("coord:z"))
    app.processEvents()
    shown = [sc.model.parts[n].bounds for n in sc.names if sc.visible[n]]
    b = [None] * 4 + [min(x[4] for x in shown), max(x[5] for x in shown)]
    check(abs(rp.bar.lo - b[4]) < 1e-9 and abs(rp.bar.hi - b[5]) < 1e-9
          and rp.hi_unit.text() == sc.model.units and sc.results.shown,
          f"Position Z: {rp.bar.lo}…{rp.bar.hi} {rp.hi_unit.text()}")
    from PySide6.QtGui import QAction
    w._unit_chosen(next(a for a in w.findChildren(QAction) if a.data() == "mm"))
    check(abs(rp.bar.hi - b[5] * 1000) < 1e-6 and rp.hi_unit.text() == "mm"
          and rp.shown_unit.currentData() == "mm" and rp.file_unit.isHidden()
          and "m (File ▸ File Unit…)" in rp.unit_note.text(),
          "Position Z follows the toolbar's unit; in the file's (a note, no menu)")
    rp.shown_unit.setCurrentIndex(rp.shown_unit.findData("cm"))  # its own unit
    app.processEvents()
    w._unit_chosen(next(a for a in w.findChildren(QAction) if a.data() == "m"))
    check(abs(rp.bar.hi - b[5] * 100) < 1e-6 and rp.hi_unit.text() == "cm",
          "Position Z in a unit of its own: the toolbar no longer moves it")

    # a saved plot cut across a flat boundary (only the floor shown, cut along Z):
    # its range is ~0 wide, the file still opens (was: OverflowError, the window hung)
    sb = w.sidebar
    sb._visibility_changed([n for n in sc.names if n != "FLOOR"], False)
    sc.plots = [{"id": 1, "name": "Flat", "kind": "section", "axis": "z", "pos": 0.2,
                 "normal": None, "value": "cp", "along": None, "chord": False,
                 "flip": None, "ref": None, "show": True}]
    try:
        sb.plots_panel.bind(sc)
        ed = sb.plots_panel.editors[1][1]
        ed._range = lambda: (0.0, 1e-18)       # flat to rounding, as a real symmetry plane
        ed.sync_position()
        ok = 0 <= ed.slider.value() <= 1000
    except OverflowError:
        ok = False
    check(ok, "a plot across a flat boundary: the slider stays within its ends")

    # a field Mesh Viewer doesn't know: no unit until one is picked, any unit offered
    from meshviewer.core.field_kinds import field_kind
    from meshviewer.gui.panels.results import grouped
    check(field_kind("S_Mises").quantity == "pressure" and field_kind("Mach").quantity is None
          and field_kind("YPLUS").title == "y+" and field_kind("foo") is None,
          "field kinds: von Mises a stress, Mach and y+ no unit, foo unknown")
    check([g for g, _ in grouped(["foo", "mises", "cp", "mach", "coord:x", "dx"])]
          == ["Flow", "Pressure", "Displacement", "Stress", "Other", "Position"],
          "the Field menu by subject: CFD, FEA, Other, Position")
    for part in sc.model.parts.values():
        part.point_data["foo_bar"] = np.linspace(1.0, 2.0, part.n_points)
    sb._visibility_changed(list(sc.names), True)         # every boundary shown again
    rp.bind(sc)
    rp.field.setCurrentIndex(rp.field.findData("foo_bar"))
    app.processEvents()
    check(not rp.file_unit.isHidden() and rp.shown_unit.isHidden()
          and rp.file_unit.findData("K") > 0 and rp.file_unit.findData("mm") > 0
          and rp.file_unit.findData("ksi") > 0 and rp.hi_unit.text() == ""
          and "doesn't know" in rp.unit_note.text(),
          "an unknown field: every unit to pick, no unit until one is")
    rp.file_unit.setCurrentIndex(rp.file_unit.findData("kPa"))
    app.processEvents()
    check(not rp.shown_unit.isHidden() and rp.shown_unit.findData("Pa") >= 0
          and rp.shown_unit.findData("K") < 0 and rp.hi_unit.text() == "kPa",
          f"given kPa: shown in pressure units ({rp.hi_unit.text()})")
    hi_k = rp.bar.hi
    rp.shown_unit.setCurrentIndex(rp.shown_unit.findData("Pa"))
    app.processEvents()
    check(abs(rp.bar.hi - hi_k * 1000) < 1e-9 * hi_k * 1000 and rp.hi_unit.text() == "Pa",
          f"kPa shown in Pa: {hi_k} -> {rp.bar.hi}")
    rp.file_unit.setCurrentIndex(rp.file_unit.findData(""))
    app.processEvents()
    check(rp.hi_unit.text() == "" and rp.shown_unit.isHidden() and abs(rp.bar.hi - hi_k) < 1e-9,
          "back to no unit")


if __name__ == "__main__":
    run(test)
