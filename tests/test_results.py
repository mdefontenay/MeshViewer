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
    check(not rp.file_unit.isHidden() and not rp.shown_unit.isHidden(), "p: unit menus shown")
    lo0, hi0 = rp.bar.lo, rp.bar.hi
    rp.file_unit.setCurrentIndex(rp.file_unit.findData("Pa"))
    rp.shown_unit.setCurrentIndex(rp.shown_unit.findData("kPa"))
    app.processEvents()
    check(abs(rp.bar.hi - hi0 / 1000) < 1e-9 * max(1, hi0) and rp.hi_unit.text() == "kPa",
          f"p in kPa: {hi0} Pa -> {rp.bar.hi} {rp.hi_unit.text()}")
    rp.field.setCurrentIndex(rp.field.findData("cp"))
    app.processEvents()
    check(rp.file_unit.isHidden() and rp.hi_unit.text() == "", "cp: no unit")
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


if __name__ == "__main__":
    run(test)
