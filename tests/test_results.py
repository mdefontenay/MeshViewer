"""Contours: Tecplot fields colored on the boundaries; several contours, each with its
tab; the color bar. OpenFOAM time steps and fields (3D and 2D), Measure Selected on them;
▸ Color Bar / ▸ Animation header switches, the playback bar, Timeline / Current Step."""
from conftest import ContourTool, check, open_file, run


def test(app, files):
    w = open_file(app, files["tecplot"])
    sc, sb = w.scene, w.sidebar
    rp = ContourTool(sb.contours_panel)
    check(len(rp.panel.contours) == 1 and rp.panel.contours[0]["name"] == "Contour 1"
          and list(w._contour_acts) == [1] and w._contour_acts[1].text() == "Contour 1"
          and w.a_page_model.text() == "3D View", "a results file starts with Contour 1, its "
          "tab under the view, after 3D View")
    app.processEvents()
    check(w._page == "model" and not sc.results.shown and not sc.colorbar.shown,
          "the 3D View: the model alone, no contour, no color bar")
    w._show_page("contour:1")
    check(rp.field.currentData() == "yplus", f"default field {rp.field.currentData()}")
    app.processEvents()
    check(sc.results.shown, "boundaries coloured")
    rp.field.setCurrentIndex(rp.field.findData("cp"))
    app.processEvents()
    from meshviewer.core.fields import COLORMAPS
    check(rp.cmap.currentData() == "rainbow" and sc.colorbar.spec["stops"] == COLORMAPS["rainbow"]
          and rp.range[0] < -1.0 and 0.9 < rp.range[1] <= 1.0,
          f"cp: rainbow by default, real range {rp.range[0]:.3g}..{rp.range[1]:.3g}")
    lo0, hi0 = rp.range[0], rp.range[1]
    rp.cmap.setCurrentIndex(rp.cmap.findData("coolwarm"))
    app.processEvents()
    check(sc.colorbar.spec["stops"] == COLORMAPS["coolwarm"] and rp.range == (lo0, hi0)
          and rp.cmap.text() == "", f"blue–white–red: same real range, menu shows colours only")
    check("diverging" not in COLORMAPS, "blue–grey–red removed")
    import numpy as np
    import pyvista as pv
    drawn = lambda: np.nansum(np.asarray(pv.wrap(                                  # noqa: E731
        sc.results._actor.GetMapper().GetInput()).point_data["ResultT"]))  # what is drawn
    before = drawn()
    sc.set_selection(["SPHERE"])
    app.processEvents()
    check(drawn() > before, "selected boundary lighter over the colours (B3)")
    sc.set_selection([])
    check(drawn() == before, "deselected: colours back")
    sb._visibility_changed(["SPHERE"], False)          # FLOOR alone: cp = 0 there
    app.processEvents()
    check(abs(rp.range[0]) < 1e-3 and abs(rp.range[1]) < 1e-3, f"auto range follows the shown "
          f"boundaries {lo0:.3g}..{hi0:.3g} -> {rp.range[0]:.3g}..{rp.range[1]:.3g}")
    sb._visibility_changed(["SPHERE"], True)
    app.processEvents()
    check(rp.range == (lo0, hi0), "and back when SPHERE is shown again")
    sb._visibility_changed(["FLOOR"], False)
    app.processEvents()
    check(sc.results.shown, "still shown after hiding FLOOR")
    rp.field.setCurrentIndex(rp.field.findData("__speed__"))
    app.processEvents()
    check(rp.range[1] > rp.range[0] and not hasattr(rp, "values"), "speed shown; no Values button")
    # units: p in Pa in the file, shown in kPa
    rp.field.setCurrentIndex(rp.field.findData("p"))
    app.processEvents()
    check(not rp.file_unit.isHidden() and rp.shown_unit.isHidden()
          and rp.file_unit.currentData() == "" and rp.file_unit.findData("GPa") > 0
          and rp.file_unit.findData("K") < 0 and not rp.unit_note.isHidden(),
          "p: Unit in file (As written, pressure units), Shown in once it is known")
    lo0, hi0 = rp.range[0], rp.range[1]
    rp.file_unit.setCurrentIndex(rp.file_unit.findData("Pa"))
    rp.shown_unit.setCurrentIndex(rp.shown_unit.findData("kPa"))
    app.processEvents()
    check(not rp.shown_unit.isHidden() and rp.unit_note.isHidden(), "p in Pa: Shown in appears")
    check(abs(rp.range[1] - hi0 / 1000) < 1e-9 * max(1, hi0) and rp.hi_unit.text() == "kPa",
          f"p in kPa: {hi0} Pa -> {rp.range[1]} {rp.hi_unit.text()}")
    rp.field.setCurrentIndex(rp.field.findData("cp"))
    app.processEvents()
    check(rp.file_unit.isHidden() and rp.shown_unit.isHidden() and rp.hi_unit.text() == ""
          and rp.unit_note.text() == "Pressure coefficient cp has no unit.",
          f"cp: a known field with no unit, nothing to pick ({rp.unit_note.text()})")
    rp.field.setCurrentIndex(rp.field.findData("__speed__"))
    app.processEvents()
    rp.hi.setValue(1.0)
    rp._update()
    check(rp.range[1] == 1.0, "typed max")
    w.remember_view()
    from meshviewer.gui import memory
    st = memory.load(w.path)
    check(st["results"]["units"].get("p") == ["Pa", "kPa"], "p's units remembered")
    c0 = st["results"]["contours"][0]
    check(c0["field"] == "__speed__" and c0["hi"] == 1.0 and c0["cmap"] == "coolwarm",
          "remembered (field, range, colour map)")

    # a log scale: Min the smallest value above zero, the middle the geometric one
    import numpy as np
    rp.field.setCurrentIndex(rp.field.findData("p"))
    rp.lo.setValue(None)
    rp.hi.setValue(None)
    app.processEvents()
    rp.scale_acts["log"].trigger()
    app.processEvents()
    vals = rp.panel.shown_values("p", rp.panel._values("p"))
    pos = vals[vals > 0]
    from meshviewer.core.fields import ticks
    mid = ticks(rp.range[0], rp.range[1], 3, log=True, tick_log=False)[1][1]
    check(rp.log and abs(rp.range[0] - pos.min()) < 1e-9 * pos.max()
          and abs(mid - np.sqrt(rp.range[0] * rp.range[1])) < 1e-6 * rp.range[1]
          and sc.results.spec is not None and sc.results.spec[4] is True,
          f"log scale: {rp.range[0]:.4g}…{rp.range[1]:.4g}, middle {mid:.4g}")
    rp.lo.setValue(-1.0)                       # typed at or below zero: the auto Min
    app.processEvents()
    check(rp.range[0] > 0, "log: a Min at or below zero is not used")
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
    check(abs(rp.range[0] - b[4]) < 1e-9 and abs(rp.range[1] - b[5]) < 1e-9
          and rp.hi_unit.text() == sc.model.units and sc.results.shown,
          f"Position Z: {rp.range[0]}…{rp.range[1]} {rp.hi_unit.text()}")
    from PySide6.QtGui import QAction
    w._unit_chosen(next(a for a in w.findChildren(QAction) if a.data() == "mm"))
    check(abs(rp.range[1] - b[5] * 1000) < 1e-6 and rp.hi_unit.text() == "mm"
          and rp.shown_unit.currentData() == "mm" and rp.file_unit.isHidden()
          and "m (File ▸ File Unit…)" in rp.unit_note.text(),
          "Position Z follows the toolbar's unit; in the file's (a note, no menu)")
    rp.shown_unit.setCurrentIndex(rp.shown_unit.findData("cm"))  # its own unit
    app.processEvents()
    w._unit_chosen(next(a for a in w.findChildren(QAction) if a.data() == "m"))
    check(abs(rp.range[1] - b[5] * 100) < 1e-6 and rp.hi_unit.text() == "cm",
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
    from meshviewer.gui.panels.contour_editor import grouped
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
    hi_k = rp.range[1]
    rp.shown_unit.setCurrentIndex(rp.shown_unit.findData("Pa"))
    app.processEvents()
    check(abs(rp.range[1] - hi_k * 1000) < 1e-9 * hi_k * 1000 and rp.hi_unit.text() == "Pa",
          f"kPa shown in Pa: {hi_k} -> {rp.range[1]}")
    rp.file_unit.setCurrentIndex(rp.file_unit.findData(""))
    app.processEvents()
    check(rp.hi_unit.text() == "" and rp.shown_unit.isHidden() and abs(rp.range[1] - hi_k) < 1e-9,
          "back to no unit")
    color_bar(app, w)


def color_bar(app, w):
    """Contours ▸ the color bar over the 3D view: ticks, sliders, tick spacing, text
    color, title, reset, layout, dragged, remembered, in Save Screenshot."""
    import numpy as np
    from meshviewer.core.fields import DEFAULT_MAP, ramp_rgb, ramp_table, ticks
    from meshviewer.render.colorbar import BASE, TEXT, ColorBar, tick_label
    from meshviewer.render.overlays import results_lut
    sc = w.scene
    panel = w.sidebar.contours_panel
    rp = ContourTool(panel)
    bar = sc.colorbar
    # the maths: ticks (Tick spacing apart from the Color scale), bands, numbers
    t = ticks(0.0, 1.0, 5)
    check([p for p, _ in t] == [0, 0.25, 0.5, 0.75, 1.0] and t[2][1] == 0.5,
          "linear colors, Linear spacing: evenly up the bar")
    t = ticks(1.0, 1000.0, 4, log=True)
    check(np.allclose([p for p, _ in t], [0, 1 / 3, 2 / 3, 1])
          and np.allclose([v for _, v in t], [1, 10, 100, 1000]),
          "log colors, Linear spacing: evenly up the bar, the values there (geometric)")
    t = ticks(1.0, 1000.0, 4, log=False, tick_log=True)
    check(np.allclose([v for _, v in t], [1, 10, 100, 1000]) and t[2][0] < 0.1,
          "linear colors, Log spacing: evenly in log10, crowded near the bottom")
    t = ticks(0.375, 1000.0, 9, log=True, tick_log=True)
    check([round(v, 6) for _, v in t] == [0.375, 1, 3, 10, 30, 100, 300, 1000]
          and abs(t[1][0] - np.log10(1 / 0.375) / np.log10(1000 / 0.375)) < 1e-9,
          f"log colors, Log spacing: the round values, where they fall {[v for _, v in t]}")
    lin = [v for _, v in ticks(0.375, 1000.0, 9, log=True, tick_log=False)]
    check(len(lin) == 9 and abs(lin[1] - 0.375 * (1000 / 0.375) ** 0.125) < 1e-9,
          "…not the values Linear spacing puts evenly up the bar")
    check([round(v, 6) for _, v in ticks(1e-3, 250.0, 7, log=True, tick_log=True)]
          == [0.001, 0.01, 0.1, 1, 10, 100, 250]
          and len(ticks(1e-3, 1e6, 4, log=True, tick_log=True)) <= 4,
          "log on log: the decades, never more than Ticks")
    check([len(ticks(1e-3, 1e6, n, log=g, tick_log=k)) for n in (2, 9, 15)
           for g, k in ((True, False), (False, True))] == [2, 2, 9, 9, 15, 15]
          and len(ticks(0, 1, 40)) == 15 and len(ticks(0, 1, 1)) == 2,
          "exactly the count asked, 2 to 15 (but log on log: the round values)")
    check(ticks(-1.0, 1.0, 5, tick_log=True)[2][1] == 0.0,
          "Log spacing with values at or below zero: evenly up the bar")
    stops = ("#000000", "#ffffff")
    rgb = ramp_rgb([0.1, 0.4, 0.6, 0.9, np.nan], 0, 1, stops, edges=[0, 0.5, 1])
    check((rgb[0] == rgb[1]).all() and (rgb[0] == 0).all() and (rgb[2] == 255).all()
          and tuple(rgb[4]) == (142, 142, 147), "bands: one color each, the map's ends; NaN gray")
    check(len({tuple(c) for c in ramp_table(stops, [0, 0.5, 1], 8)}) == 2,
          "the lookup table in the same bands")
    lut = results_lut(stops, None, 16)
    check(lut.GetNumberOfTableValues() == 48 and lut.GetTableValue(16) == lut.GetTableValue(15)
          and lut.GetTableValue(32)[0] > lut.GetTableValue(0)[0] + 0.2,
          "lookup table: the colors, the top one in the gap, then lighter (selected)")
    check([tick_label(v) for v in (1000.0, 0.375, -0.689, 12345.6, 2e5, 1e-4, 0.0)]
          == ["1000", "0.375", "-0.689", "12346", "2.00e+05", "1.00e-04", "0"],
          "tick numbers: 1000 written out, powers of ten outside 0.001…99999")
    crowd = [(0.0, 1.0), (0.84, 334.0), (0.94, 667.0), (1.0, 1000.0)]
    check([v for _, v in ColorBar._labeled(crowd, 190, 11)] == [1.0, 334.0, 1000.0],
          "a number too close to the top one left out")

    # on screen
    rp.field.setCurrentIndex(rp.field.findData("cp"))
    rp.scale_acts["linear"].trigger()
    rp.lo.setValue(None)
    rp.hi.setValue(None)
    app.processEvents()
    ed = rp.ed
    check(ed.bar_on.isChecked() and bar.shown and bar._actors and not ed.bar_section.expanded,
          "Show color bar: on by default, Color Bar folded")
    check(bar.spec["title"] == "Pressure coefficient cp" and len(bar.spec["ticks"]) == 5
          and bar.spec["smooth"] and sc.results.spec[5] is None,
          f"the field's name on top, 5 ticks, smooth ({bar.spec['title']})")

    def title_actor():
        return next((a for a in bar._actors if hasattr(a, "GetTextProperty")
                     and a.GetInput() == bar.spec["title"]), None)

    first = title_actor().GetTextProperty().GetFontSize()
    check(first == round(BASE[2] * 1.1) and not title_actor().GetTextProperty().GetBold(),
          f"the title in points, regular weight ({first})")
    ed.ticks_slider.setValue(6)
    app.processEvents()
    check(title_actor().GetTextProperty().GetFontSize() == first,
          "the title the same size after an update as when first drawn")
    # Ticks: a slider, 2 to 15, its number beside it
    ed.ticks_slider.setValue(8)
    app.processEvents()
    check(len(bar.spec["ticks"]) == 8 and ed.ticks_label.text() == "8"
          and panel.current["bar"]["ticks"] == 8
          and (ed.ticks_slider.minimum(), ed.ticks_slider.maximum()) == (2, 15),
          "Ticks slider: 8 ticks, its number beside it, 2 to 15")
    ed.smooth.setChecked(False)
    app.processEvents()
    check(not bar.spec["smooth"] and sc.results.spec[5] == tuple(p for p, _ in bar.spec["ticks"]),
          "Smooth colors off: the boundaries in the bar's bands")
    ed.ticks_slider.setValue(7)
    app.processEvents()
    check(len(bar.spec["ticks"]) == 7 and len(sc.results.spec[5]) == 7, "7 ticks: 6 bands")
    # Height and Width
    sc.p.render_now()
    s0 = float(sc.p.devicePixelRatioF())
    w0, h0 = bar._box
    ed.height_slider.setValue(150)
    app.processEvents()
    sc.p.render_now()
    check(bar.spec["height"] == 150 and ed.height_label.text() == "150%"
          and bar._box[1] > 1.3 * h0 and abs(bar._box[0] - w0) < 1.0,
          f"Height 150%: taller ({h0:.0f} -> {bar._box[1]:.0f} px), as wide")
    ed.width_slider.setValue(60)
    app.processEvents()
    check(bar.spec["width"] == 60 and ed.width_label.text() == "60%"
          and abs(bar._geom[0] - (BASE[1] * 0.6 + 9) * s0) < 0.5,
          "Width 60%: the bar narrower")
    ed.width_slider.setValue(10)
    check(ed.width_slider.value() == 60, "60 % at least")
    ed.width_slider.setValue(100)
    ed.height_slider.setValue(140)
    # Color scale and Tick spacing: one doesn't move the other
    rp.field.setCurrentIndex(rp.field.findData("p"))
    rp.scale_acts["log"].trigger()
    app.processEvents()
    pos = [p for p, _ in bar.spec["ticks"]]
    vals = [v for _, v in bar.spec["ticks"]]
    check(rp.log and not panel.current["bar"]["tick_log"] and sc.results.spec[4] is True
          and np.allclose(np.diff(pos), 1 / 6) and np.allclose(np.diff(np.log10(vals)),
                                                                np.log10(vals[1] / vals[0])),
          "Color scale Log, Tick spacing Linear: evenly up the bar, geometric values")
    rp.tick_acts["log"].trigger()
    app.processEvents()
    vals = [v for _, v in bar.spec["ticks"]]
    inner = vals[1:-1]
    check(rp.log and panel.current["bar"]["tick_log"] and inner
          and all(abs(np.log10(v) - round(np.log10(v))) < 1e-9
                  or abs(v / 10 ** np.floor(np.log10(v)) - round(v / 10 ** np.floor(np.log10(v))))
                  < 1e-9 for v in inner),
          f"Color scale Log, Tick spacing Log: round values across the range {vals}")
    rp.scale_acts["linear"].trigger()
    app.processEvents()
    check(not rp.log and panel.current["bar"]["tick_log"] and sc.results.spec[4] is False
          and bar.spec["ticks"][1][0] < 1 / 6, "Color scale Linear, Tick spacing Log: crowded low")
    rp.tick_acts["linear"].trigger()
    rp.field.setCurrentIndex(rp.field.findData("cp"))
    app.processEvents()
    check(not rp.tick_acts["log"].isEnabled(), "cp below zero: no log tick spacing")
    check(bar.labeled[0] == bar.spec["ticks"][0][1] and bar.labeled[-1] == bar.spec["ticks"][-1][1],
          "both ends written")
    # Text color
    texts = lambda: [a for a in bar._actors if hasattr(a, "GetTextProperty")]   # noqa: E731
    from meshviewer.render.style import rgb as to_rgb
    check(all(tuple(a.GetTextProperty().GetColor()) == to_rgb(TEXT[sc._dark]) for a in texts()),
          "Text color Auto: for the background")
    for k, want in (("white", TEXT[True]), ("black", TEXT[False])):
        rp.text_acts[k].trigger()
        app.processEvents()
        check(all(tuple(a.GetTextProperty().GetColor()) == to_rgb(want) for a in texts()),
              f"Text color {k.title()}")
    rp.text_acts["auto"].trigger()
    # Show title
    ed.show_title.setChecked(False)
    app.processEvents()
    check(bar.spec["title"] == "" and title_actor() is None, "Show title off: no title")
    ed.show_title.setChecked(True)
    app.processEvents()
    check(bar.spec["title"] == "Pressure coefficient cp", "Show title on")
    # dragged
    sc.p.render_now()
    ax, ay = bar._anchor.GetComputedDoubleDisplayValue(sc.p.renderer)[:2]
    check(bar.hit(ax + 3, ay - 20) and not bar.hit(ax + 600, ay - 600), "hit: on the bar only")
    s = float(sc.p.devicePixelRatioF())
    bar.drag(40 * s, -30 * s)
    bar.drag_done()
    check(abs(bar.offset[0] - 56) < 1e-6 and abs(bar.offset[1] - 46) < 1e-6,
          f"dragged 40 right, 30 down: {bar.offset}")
    bar.drag(-1e5, 1e5)
    check(bar.offset == (0.0, 0.0), "kept inside the view")
    bar.drag(56 * s, -46 * s)
    bar.drag_done()
    # remembered
    w.remember_view()
    from meshviewer.gui import memory
    st = memory.load(w.path)["results"]
    b = st["contours"][0]["bar"]
    check(b == {"on": True, "height": 140, "width": 100, "ticks": 7, "tick_log": False,
                "text": "auto", "smooth": False, "title": True, "pos": [56.0, 46.0]},
          f"remembered per contour {b}")
    from meshviewer.gui.panels.contour_editor import last_bar_settings
    check(last_bar_settings()["height"] == 140, "and the start for a new contour")
    # Save Screenshot: drawn too
    import tempfile
    from pathlib import Path
    path = Path(tempfile.mkdtemp()) / "shot.png"
    added = []
    real = bar.add_to
    bar.add_to = lambda ren, k, dark=None: added.append(k) or real(ren, k, dark)
    sc.screenshot(path, scale=2)
    bar.add_to = real
    check(path.exists() and added == [2], "Save Screenshot: the color bar at 2×")
    # Reset Color Bar: right-aligned on the bottom row, no line above it
    from PySide6.QtCore import Qt
    rp.cmap.setCurrentIndex(rp.cmap.findData("coolwarm"))
    rp.text_acts["white"].trigger()
    ed.show_title.setChecked(False)
    ed.bar_section.set_expanded(True)
    grid = next(c for c in (ed.reset_cap.parentWidget().layout().itemAt(i).layout()
                            for i in range(ed.reset_cap.parentWidget().layout().count()))
                if c is not None and c.indexOf(ed.reset_cap) >= 0)
    item = grid.itemAt(grid.indexOf(ed.reset_cap))
    from meshviewer.gui.widgets.basics import rule as _rule   # noqa: F401
    lay = ed.reset_cap.parentWidget().layout()
    above = lay.itemAt(lay.count() - 2).widget()
    check(bool(item.alignment() & Qt.AlignRight) and ed.reset_bar.text() == "Reset Color Bar"
          and above is not None and above.objectName() != "Rule"
          and "rule" not in type(above).__name__.lower() and above.findChild(type(ed.smooth)),
          "Reset Color Bar: right-aligned on the last row, under Show title (no line)")
    ed.reset_bar.trigger()
    app.processEvents()
    b = panel.current["bar"]
    from meshviewer.render.colorbar import MARGIN
    check(b["height"] == 100 and b["width"] == 100 and b["ticks"] == 5 and not b["tick_log"]
          and b["smooth"] and b["title"] and b["text"] == "auto"
          and rp.cmap.currentData() == DEFAULT_MAP and ed.height_label.text() == "100%"
          and b["on"], "reset: 100 %, 100 %, 5 ticks, linear, auto, smooth, title, rainbow")
    check(b["pos"] == [MARGIN, MARGIN] and bar.offset == (MARGIN, MARGIN),
          "reset: the bar back at the top-left corner")
    # the layout: label · field · unit · ?
    g = ed.height_slider.parentWidget().layout()
    grid = next(c for c in (g.itemAt(i).layout() for i in range(g.count()))
                if c is not None and c.indexOf(ed.height_slider) >= 0)
    span = lambda wdg: grid.getItemPosition(grid.indexOf(wdg))[1:]   # noqa: E731
    cmap_grid = rp.cmap.parentWidget().layout()
    cmap_grid = next(c for c in (cmap_grid.itemAt(i).layout() for i in range(cmap_grid.count()))
                     if c is not None and c.indexOf(rp.cmap) >= 0)
    check(cmap_grid.getItemPosition(cmap_grid.indexOf(rp.cmap))[1:] == (1, 1, 3)
          and span(ed.height_slider) == (1, 1, 2)
          and span(ed.height_label) == (3, 1, 1) and span(ed.width_slider) == (1, 1, 2)
          and span(ed.ticks_slider) == (1, 1, 2) and span(ed.ticks_label) == (3, 1, 1),
          "Colors across; Height, Width, Ticks: slider + its value")
    # off
    ed.bar_on.setChecked(False)
    app.processEvents()
    check(not bar.shown and not bar._actors and sc.results.shown, "Show color bar off")
    ed.bar_on.setChecked(True)
    app.processEvents()
    check(not hasattr(panel, "colour_on") and sc.results.shown and bar.shown
          and w.sidebar.contours_section.header.findChild(type(ed.bar_on)) is None,
          "no Color the boundaries switch: a contour's tab always shows it")
    contours(app, w)


def contours(app, w):
    """Several contours: each its tab under the view and its fold-out, independent; the
    tab and the fold-out open together; deleted with its tab; remembered."""
    sc, panel = w.scene, w.sidebar.contours_panel
    sb = w.sidebar
    first = panel.active
    panel.editors[first][0].set_expanded(False)
    sb.show_tab("view")
    k = panel.add()
    app.processEvents()
    check(k == 2 and set(w._contour_acts) == {1, 2} and w._contour_acts[2].text() == "Contour 2"
          and w._page == "contour:2" and w._contour_acts[2].isChecked(),
          "New Contour: Contour 2, its tab open")
    check(sb.current_tab() == "analyze" and sb.is_open("contours")
          and panel.editors[2][0].expanded and not panel.editors[1][0].expanded,
          "its fold-out opened in the right sidebar, the other folded")
    ed2 = panel.editors[2][1]
    ed2.field.setCurrentIndex(ed2.field.findData("mach"))
    app.processEvents()
    check(sc.results.spec[0] == "mach" and panel.contour(1)["field"] == "cp"
          and sc.colorbar.spec["title"] == "Mach number",
          f"Contour 2 its own field: Mach drawn, Contour 1 still cp ({sc.colorbar.spec['title']})")
    ed2.hi.setText("0.5")                             # typed
    ed2.hi.editingFinished.emit()
    app.processEvents()
    check(panel.range[1] == 0.5 and panel.contour(1)["hi"] is None, "its own range")
    w._contour_acts[1].trigger()
    app.processEvents()
    check(w._page == "contour:1" and panel.active == 1 and sc.results.spec[0] == "cp"
          and panel.editors[1][0].expanded and not panel.editors[2][0].expanded,
          "Contour 1's tab: cp drawn, its fold-out open, Contour 2's folded")
    panel.editors[2][0].set_expanded(True)            # its fold-out opened: its tab too
    app.processEvents()
    check(w._page == "contour:2" and sc.results.spec[0] == "mach"
          and not panel.editors[1][0].expanded, "Contour 2 opened in the sidebar: its tab")
    w._show_page("model")
    check(not sc.results.shown and not sc.colorbar.shown and panel.tab is None,
          "3D View: no contour drawn, no color bar")
    view_checks(app, w)
    panel.rename(2, "Mach")
    check(w._contour_acts[2].text() == "Mach" and panel.editors[2][0].title_label.text()
          == "Mach", "renamed: its tab and its fold-out")
    w.remember_view()
    from meshviewer.gui import memory
    st = memory.load(w.path)["results"]
    check([c["name"] for c in st["contours"]] == ["Contour 1", "Mach"] and st["active"] == 2,
          "remembered: both, and which is shown")
    parts_checks(app, w)
    w._show_page("contour:2")
    w.remember_view()
    st = memory.load(w.path)
    views = [c["view"] for c in st["results"]["contours"]]
    check(st["toggles"]["mesh_edges"] == w._model_view["show"]["mesh_edges"]
          and views[0]["show"]["mesh_edges"] != st["toggles"]["mesh_edges"]
          and w._page == "contour:2" and views[1]["camera"] is not None
          and w.a_show["mesh_edges"].isChecked() == views[1]["show"]["mesh_edges"],
          "saved from a contour's tab: the file keeps the 3D View's view, the tab its own")
    panel.remove(2)
    app.processEvents()
    check(set(w._contour_acts) == {1} and 2 not in panel.editors and w._page == "model"
          and panel.active == 1 and not sc.results.shown,
          "deleted: its tab and its fold-out go, back to the 3D View")
    # a file remembered by 2.5 (one Results tool): Contour 1
    sc.results_settings = {"field": "mach", "lo": None, "hi": 2.0, "on": True,
                           "cmap": "thermal", "show": "value", "log": False,
                           "units": {"p": ["Pa", "kPa"]}}
    panel.bind(sc)
    w._rebuild_view_bar()
    c = panel.contours[0]
    check(len(panel.contours) == 1 and c["field"] == "mach" and c["hi"] == 2.0
          and c["cmap"] == "thermal" and panel.unit_label("p") == "kPa"
          and list(w._contour_acts) == [1],
          "a file saved by 2.5: its Results settings as Contour 1")
    from meshviewer.gui.sections import BY_KEY
    check(BY_KEY["contours"].title == "Contours" and "results" not in BY_KEY
          and sb.contours_section.title_label.text() == "Contours", "the tool is Contours")


def parts_checks(app, w):
    """Each tab its own shown / hidden parts: Contour 1, Contour 2 and the 3D View."""
    sc, sb, panel = w.scene, w.sidebar, w.sidebar.contours_panel
    w._show_page("contour:1")
    lo_all = panel.range[0]
    order = [sb.list.topLevelItem(i).text(0) for i in range(sb.list.topLevelItemCount())] \
        if hasattr(sb.list, "topLevelItem") else None
    sb._visibility_changed(["SPHERE"], False)           # hidden in Contour 1 only
    app.processEvents()
    check(not sc.visible["SPHERE"] and abs(panel.range[0]) < 1e-3,
          f"Contour 1: SPHERE hidden, its auto range the floor's ({panel.range[0]:.3g})")
    w._show_page("model")
    check(sc.visible["SPHERE"], "the 3D View: SPHERE still shown")
    w._show_page("contour:2")
    check(sc.visible["SPHERE"] and "SPHERE" in {n for n, _, _ in sc.results._pieces},
          "Contour 2: SPHERE shown, and colored")
    ed1 = panel.editors[1][1]
    check(ed1.lo.placeholderText().endswith("0"),
          f"Contour 1's auto Min from its own parts while not shown ({ed1.lo.placeholderText()})")
    w._show_page("contour:1")
    check(not sc.visible["SPHERE"] and abs(panel.range[0] - lo_all) > 0.1,
          "back to Contour 1: SPHERE hidden again")
    if order is not None:
        check([sb.list.topLevelItem(i).text(0) for i in range(sb.list.topLevelItemCount())]
              == order, "the parts list in the same order")
    sb._visibility_changed(["SPHERE"], True)
    app.processEvents()


def view_checks(app, w):
    """Each 3D tab its own view: the camera and Show ▾ (3D View, Contour 1, Contour 2)."""
    import numpy as np
    sc = w.scene
    snap = lambda: np.concatenate([np.ravel(v) for v in sc.camera_snapshot()]).astype(float)   # noqa: E731
    w._show_page("model")
    cam0, edges0 = snap(), sc.state["mesh_edges"]
    ind0 = w.ctl.appearance["axis_indicator"]
    w._show_page("contour:1")
    sc.p.camera.Azimuth(40)                             # turn the view in Contour 1
    sc.p.renderer.ResetCameraClippingRange()
    w.a_show["mesh_edges"].trigger()                    # and its mesh edges
    w.a_show["axis_indicator"].trigger()                # and its corner arrows
    cam1, edges1 = snap(), sc.state["mesh_edges"]
    check(edges1 != edges0 and not sc.state["axis_indicator"] == ind0
          and w.ctl.appearance["axis_indicator"] == ind0,
          "Contour 1: its own mesh edges and axis indicator (Settings untouched)")
    w._show_page("model")
    check(np.allclose(snap(), cam0) and sc.state["mesh_edges"] == edges0
          and w.a_show["mesh_edges"].isChecked() == edges0
          and sc.state["axis_indicator"] == ind0 and w.a_show["axis_indicator"].isChecked()
          == ind0, "3D View: its camera, edges and axis indicator as they were")
    w._show_page("contour:2")
    check(np.allclose(snap(), cam0) and sc.state["mesh_edges"] == edges0,
          "Contour 2: its own (as the 3D View it was opened from)")
    sc.p.camera.Elevation(25)
    sc.p.renderer.ResetCameraClippingRange()
    cam2 = snap()
    w._show_page("contour:1")
    check(np.allclose(snap(), cam1) and sc.state["mesh_edges"] == edges1
          and not sc.state["axis_indicator"] == ind0 and sc.results.spec[0] == "cp",
          "back to Contour 1: its camera and Show ▾, its field")
    w._show_page("contour:2")
    check(np.allclose(snap(), cam2), "Contour 2: its own camera")
    w._show_page("contour:1")                          # Contour 1's view put back as it was
    w.a_show["axis_indicator"].trigger()
    w._show_page("contour:2")


def openfoam(app, files):
    """OpenFOAM cases with time folders: the latest step, its fields (kinds and units),
    Contours, Measure Selected ▸ Field Values — a 3D case and a 2D one."""
    import shutil
    import tempfile
    from pathlib import Path
    tmp = Path(tempfile.mkdtemp(prefix="foam-fields-"))
    try:
        _openfoam_core(tmp)
        _openfoam_3d(app, tmp)
        _openfoam_2d(app, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _at(name, c, t=1.0):
    """A field of tests/fixtures.FOAM_FIELDS at a point (U: its magnitude)."""
    import numpy as np
    from fixtures import FOAM_FIELDS
    v = FOAM_FIELDS[name][1](*c, t)
    return float(np.linalg.norm(v)) if name == "U" else float(v)


def _openfoam_core(tmp):
    import numpy as np
    from fixtures import foam_case
    from meshviewer.core import formats
    from meshviewer.core.field_kinds import SPEED, field_kind
    from meshviewer.core.fields import solution_fields
    case = foam_case(tmp / "box", times=("0", "0.5", "1"))
    (case / "2").mkdir()                                   # a time folder without fields
    (case / "system").mkdir()
    m = formats.load(case, debug=False)
    check(m.times == [0.0, 0.5, 1.0] and m.time_labels == ["0", "0.5", "1"]
          and m.time_index == 2, f"OpenFOAM: time steps {m.time_labels}, the latest shown "
          f"({m.time_index})")
    fields = set(solution_fields(m.parts))
    kinds = {"p": "p", "Ux": "u", "Uy": "v", "Uz": "w", SPEED: SPEED, "k": "k",
             "omega": "omega", "epsilon": "epsilon", "nut": "nut", "T": "t", "yPlus": "yplus"}
    check(set(kinds) <= fields and all(field_kind(f).key == k for f, k in kinds.items()),
          f"OpenFOAM fields found and known: {sorted(fields - {SPEED})}")
    u = m.field_units
    check(u["p"] == "m²/s²" and u["Ux"] == u[SPEED] == "m/s" and u["T"] == "K"
          and u["omega"] == "1/s" and u["epsilon"] == "m²/s³" and u["nut"] == "m²/s"
          and u["yPlus"] == "", "their units from the files' dimensions")
    check(field_kind("alpha.water").group == "Multiphase" and field_kind("ux") is None
          and field_kind("wallShearStressx").key == "taux"
          and field_kind("mag(wallShearStress)").key == "tau",
          "alpha.water: a phase fraction; ux still unknown; wallShearStress x / magnitude")
    inlet = m.parts["inlet"]
    cen = np.asarray(inlet.cell_centers().points)
    p = np.asarray(inlet.cell_data["p"])
    check(np.allclose(p, [_at("p", c) for c in cen], atol=1e-5)
          and "p" in inlet.point_data and "Ux" in inlet.cell_data,
          "the inlet's own face values (and at the nodes)")
    vol = m.volume()
    cc = np.asarray(vol.cell_centers().points)
    check(np.allclose(np.asarray(vol.cell_data["k"]), [_at("k", c) for c in cc], atol=1e-5),
          "the cells carry their values (Section)")
    early = m.case.step_arrays(1)
    check(np.allclose(np.asarray(early["inlet"][1]["p"]), p / 2, atol=1e-5),
          "another time step (0.5): read from the same readers")
    mesh = foam_case(tmp / "mesh_only")
    (mesh / "0").mkdir()
    m = formats.load(mesh, debug=False)
    check(m.times == [] and m.time_index is None and not solution_fields(m.parts),
          "a case without fields: the mesh only, no time steps")
    _catalog(tmp)


def _catalog(tmp):
    """The other OpenFOAM fields: known, grouped, in the files' units; R split in the
    order OpenFOAM writes it; phi on the patches' faces."""
    import numpy as np
    from fixtures import FOAM_FIELDS
    from meshviewer.core import formats
    from meshviewer.core.field_kinds import field_kind
    from meshviewer.core.fields import solution_fields
    m = formats.load(tmp / "box", debug=False)
    fields = set(solution_fields(m.parts))
    want = {"p_rgh": ("Pressure", "m²/s²"), "pMean": ("Pressure", "m²/s²"),
            "phi": ("Flow", "m³/s"), "alpha.water": ("Multiphase", ""),
            "nuTilda": ("Turbulence", "m²/s"), "Rxy": ("Turbulence", "m²/s²"),
            "UMeanx": ("Flow", "m/s"), "mag(UMean)": ("Flow", "m/s"),
            "CourantNo": ("Flow", ""), "Q": ("Flow", "1/s²"), "Lambda2": ("Flow", "1/s²"),
            "vorticityz": ("Turbulence", "1/s"), "mag(vorticity)": ("Turbulence", "1/s")}
    got = {f: (field_kind(f).group if field_kind(f) else None, m.field_units.get(f))
           for f in want}
    check(set(want) <= fields and got == want, f"the OpenFOAM catalog: {got}")
    from meshviewer.core.units import QUANTITIES, unit_quantity
    pp2, phi0 = field_kind("pPrime2Mean"), field_kind("phi_0")
    check(pp2.group == "Pressure" and pp2.title == "Mean pressure variance p'²"
          and m.field_units["pPrime2Mean"] == "Pa²" and set(QUANTITIES[pp2.quantity]) ==
          {"Pa²", "kPa²"} and unit_quantity("m⁴/s⁴") == "kinematic_sq"
          and phi0.group == "Flow" and phi0.title == "Previous face flux φ₀"
          and m.field_units["phi_0"] == "m³/s" and unit_quantity("kg/s") == "mass_flow",
          "pPrime2Mean (Pressure: Pa², kPa², m⁴/s⁴) and phi_0 (Flow: m³/s, kg/s)")
    check(field_kind("UPrime2Meanxy").title == "Mean Reynolds stress xy"
          and field_kind("Q").title == "Q criterion" and field_kind("q").key == "q"
          and field_kind("mag(UMean)").title == "Mean speed"
          and field_kind("CourantNo").key == field_kind("Co").key,
          "UPrime2Mean, Q (not the heat flux q), Mean speed, Co")
    inlet, outlet = m.parts["inlet"], m.parts["outlet"]
    c = np.asarray(inlet.cell_centers().points)
    r = FOAM_FIELDS["R"][1]
    check(all(np.allclose(np.asarray(inlet.cell_data["R" + k]), [r(*p, 1.0)[i] for p in c],
                          atol=1e-5) for i, k in enumerate(("xx", "xy", "xz", "yy", "yz", "zz"))),
          "R: Rxx, Rxy, Rxz, Ryy, Ryz, Rzz as written")
    check(np.allclose(np.asarray(outlet.cell_data["phi"]), 1.0)
          and "phi" not in outlet.point_data, "phi: each outlet face's own flux")


def _openfoam_3d(app, tmp):
    import numpy as np
    from meshviewer.core.field_kinds import SPEED
    from meshviewer.render.element_details import field_values
    from meshviewer.render.elements import VOLUME
    w = open_file(app, tmp / "box")
    sc, sb = w.scene, w.sidebar
    rp = ContourTool(sb.contours_panel)
    check(sb.current_tab() == "analyze" and sb.is_open("contours")
          and [c["name"] for c in rp.panel.contours] == ["Contour 1"] and rp.panel.active == 1,
          "OpenFOAM with fields: opens on Analyze ▸ Contours, Contour 1")
    check(rp.field.currentData() == "yPlus", f"its field: y+ ({rp.field.currentData()})")
    w._show_page("contour:1")
    app.processEvents()
    rp.field.setCurrentIndex(rp.field.findData("p"))
    app.processEvents()
    panel = sb.contours_panel
    check(sc.results.shown and sc.results.spec[0] == "p" and panel.unit_label("p") == "m²/s²",
          f"Contour of p, in the file's unit ({panel.unit_label('p')})")
    rp.field.setCurrentIndex(rp.field.findData(SPEED))
    app.processEvents()
    top = max(float(np.max(np.sqrt(sum(np.asarray(p.point_data[k], dtype=float) ** 2
                                           for k in ("Ux", "Uy", "Uz")))))
              for p in sc.model.parts.values())
    check(sc.results.spec[0] == SPEED and abs(rp.range[1] - top) < 1e-6,
          f"Speed from Ux, Uy, Uz (max {rp.range[1]:.4g}, {top:.4g} at the nodes)")
    el, sp = sc.elements, sb.selected_panel
    w.set_select_kind("mesh_cell")
    el._take(("inlet", 0), False)
    app.processEvents()
    c = np.asarray(sc.model.parts["inlet"].cell_centers().points)[0]
    got = dict(field_values(el)["fields"])
    fv = field_values(el)
    check(abs(got["p"] - _at("p", c)) < 1e-5 and abs(got[SPEED] - _at("U", c)) < 1e-5
          and not fv["mean"], "Measure Selected, a boundary face: its own values (p, speed)")
    rows = dict(sp.field_rows)
    check(rows.get("Pressure p", "").endswith("m²/s²"),
          f"…in Contours' units ({rows.get('Pressure p')})")
    w.set_select_kind("volume_cell")
    grid = el.volume_grid()
    el._take((VOLUME, 5), False)
    app.processEvents()
    c = np.asarray(grid.cell_centers().points)[5]
    got = dict(field_values(el)["fields"])
    check(abs(got["omega"] - _at("omega", c)) < 1e-5 and abs(got["T"] - _at("T", c)) < 1e-4,
          "a volume cell: its own values")
    w.set_select_kind("part")
    sc.set_selection(["outlet"])
    app.processEvents()
    got = dict(field_values(el)["fields"])
    outlet = sc.model.parts["outlet"]
    a = outlet.compute_cell_sizes(length=False, volume=False).cell_data["Area"]
    want = float(np.sum(np.asarray(outlet.cell_data["k"]) * a) / np.sum(a))
    check(abs(got["k"] - want) < 1e-6, "a part: area-weighted over its faces")
    w.close()


def _openfoam_2d(app, tmp):
    import numpy as np
    from fixtures import foam_case
    from meshviewer.render.element_details import field_values
    case = foam_case(tmp / "channel", n=(8, 4, 1), size=(2.0, 1.0, 0.1), two_d=True,
                     times=("0", "1"))
    w = open_file(app, case)
    sc, sb = w.scene, w.sidebar
    rp = ContourTool(sb.contours_panel)
    from meshviewer.core.field_kinds import SPEED
    from meshviewer.gui.panels.contour_editor import field_label
    menu = [rp.field._items[i][1] for i in range(rp.field.count())]
    gone = {"Uz", "UMeanz", "vorticityz", "coord:z", "Rzz", "Rxz", "Ryz", "UPrime2Meanzz",
            "UPrime2Meanxz", "UPrime2Meanyz"}
    check(not gone & set(menu) and {"Ux", "Uy", SPEED, "coord:x", "coord:y", "Rxx", "Ryy",
                                    "UPrime2Meanxx"} <= set(menu)
          and field_label(SPEED) == "Speed",
          f"2D: no out-of-plane Uz, UMeanz, vorticity z, tensors' z or Position Z; Speed "
          f"plainly named ({sorted(gone & set(menu))})")
    from conftest import wait
    panel = sb.contours_panel
    wait(app, lambda: panel._steps_job is None, 30)
    app.processEvents()
    menu = [rp.field._items[i][1] for i in range(rp.field.count())]
    check("phi_0" not in menu and "phi" not in menu and "p" in menu,
          "2D: not offered — phi_0 (zero everywhere), phi (only on the boundary lines: "
          "nothing for the cells, no gradient, no color bar)")
    ed = panel.editors[panel.active][1]
    ed.field.setCurrentIndex(ed.field.findData("UMeanx"))
    app.processEvents()
    t = ed.anim.section.title_label
    check("UMeanx" in menu and t.property("unavailable") and not ed.anim.on.isEnabled(),
          "UMeanx (varies in space, not in time): offered, ▸ Animation grayed")
    ed.field.setCurrentIndex(ed.field.findData("p"))
    app.processEvents()
    zone = sc.model.parts["internalMesh"]
    cen = np.asarray(zone.cell_centers().points) + [0, 0, 0.05]   # the cells, mid-depth
    check(sc.model.file_type == "mesh2d" and sb.current_tab() == "analyze"
          and rp.field.currentData() == "p",
          f"2D OpenFOAM with fields: Contours, p first ({rp.field.currentData()})")
    check(np.allclose(np.asarray(zone.cell_data["p"]), [_at("p", c) for c in cen], atol=1e-5),
          "the 2D cells carry their cells' values")
    w._show_page("contour:1")
    app.processEvents()
    check(sc.results.shown and sc.results.spec[0] == "p", "the 2D flow colored by p")
    w.set_select_kind("mesh_cell")
    x, y = sc.p.renderer.GetSize()
    sc.click(x // 2, y // 2)
    app.processEvents()
    items = list(sc.elements.items)
    got = dict(field_values(sc.elements)["fields"]) if items else {}
    check("Uz" not in got and "Ux" in got, "Measure Selected (2D): no Uz")
    k = items[0][1] if items else 0
    check(items and items[0][0] == "internalMesh" and abs(got.get("p", 1e9) - _at("p", cen[k])) < 1e-5,
          f"Measure Selected, a 2D cell: its value (p = {got.get('p')})")
    walls = sc.model.parts["walls"]
    check(walls.n_lines == 16 and "k" in walls.cell_data and "k" in walls.point_data,
          "the 2D walls carry their face values")
    # Plots on a 2D file: a line across the zone, X / Y only
    pp = sb.plots_panel
    check(not sb._boxes["plots"].parts[0][1].text(), "Plots: available on a 2D file")
    i = pp.add("section", "Profile")
    app.processEvents()
    m, ed = pp.plot(i), pp.editors[i][1]
    r = pp.results[i]
    shown = [k for k, a in ed.axis.items() if ed._axis_cap.buttons[
        list(ed.axis).index(k)].isHidden() is False]
    values = [ed.value._items[k][1] for k in range(ed.value.count())]
    check(m["axis"] == "x" and shown == ["x", "y"] and ed.plane_caption.text() == "Line"
          and "coord:z" not in values and "coord:y" in values,
          f"2D: Normal to X | Y (no Z), a Line, no Position Z ({m['axis']}, {shown})")
    c = r["curves"][0] if r["curves"] else None
    check(not r["empty"] and r["along"] == "y" and c is not None
          and np.allclose(c["xyz"][:, 0], 1.0) and np.allclose(c["xyz"][:, 2], 0)
          and np.ptp(c["x"]) > 0.99,
          f"the line x = 1 across the channel, along Y ({r['along']})")
    m["value"] = "p"
    pp._compute(i)
    c = pp.results[i]["curves"][0]
    want = [_at("p", [1.0, y, 0.05]) for y in c["xyz"][:, 1]]
    check(np.allclose(c["y"][1:-1], want[1:-1], atol=1e-4),
          "p along the line: the nodes' values (from the cells, as in 3D)")
    ed.edit_plane.setChecked(True)
    zs = [b for b in (*ed.origin, *ed.normal)][2::3]
    check(all(b.isHidden() for b in zs), "✎ Edit Plane: Origin / Normal without Z")
    for b, v in zip(ed.normal, (1, 1, 5)):
        b.setValue(v)
    ed._normal_typed()
    check(m["normal"] is not None and m["normal"][2] == 0 and not pp.results[i]["empty"],
          f"a tilted line: its normal stays in XY ({m['normal']})")
    w.close()


def headers(app, files):
    """▸ Color Bar: its switch in the header (on: unfolds, off: a note); ▸ Animation under
    it, grayed on a file with one time step."""
    from meshviewer.gui.panels.contour_animation import SINGLE
    w = open_file(app, files["tecplot"])
    sc, panel = w.scene, w.sidebar.contours_panel
    w._show_page("contour:1")
    app.processEvents()
    ed = panel.editors[panel.active][1]
    sec = ed.bar_section
    check(ed.bar_on.parent() is sec.header and not sec.expanded,
          "Show color bar: the switch on the ▸ Color Bar header, folded at first")
    ed.bar_on.setChecked(False)
    app.processEvents()
    sec.set_expanded(True)
    check(not sc.colorbar.shown and not ed.bar_note.isHidden() and ed.bar_details.isHidden()
          and ed.bar_note.text().startswith("Off — switch on to show the color bar"),
          "off: the color bar hidden; unfolded, one note instead of its controls")
    sec.set_expanded(False)
    ed.bar_on.setChecked(True)
    app.processEvents()
    check(sec.expanded and sc.colorbar.shown and ed.bar_note.isHidden()
          and not ed.bar_details.isHidden(), "on: ▸ Color Bar unfolds, the bar shows")
    card = ed.bar_section.parentWidget().layout()
    an = ed.anim
    check(card.indexOf(an.section) == card.indexOf(ed.bar_section) + 1,
          "▸ Animation right below ▸ Color Bar")
    an.section.set_expanded(True)
    check(an.section.title_label.property("unavailable") and not an.on.isEnabled()
          and an.note.text() == SINGLE and an.details.isHidden() and w.anim_bar.isHidden(),
          "one time step: ▸ Animation grayed, its switch off, why in a note")
    w.close()


def animation(app, files):
    import shutil
    import tempfile
    from pathlib import Path
    tmp = Path(tempfile.mkdtemp(prefix="foam-anim-"))
    try:
        _animation(app, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _animation(app, tmp):
    """A case with three time steps: ▸ Animation on shows the playback bar; steps, the
    scrubber, Loop, speed; Timeline vs Current Step; the section's cut cells follow."""
    import numpy as np
    import pyvista as pv
    from conftest import wait
    from fixtures import foam_case
    from meshviewer.gui.panels.contour_animation import OFF
    from meshviewer.gui.widgets.animation_bar import DEFAULT_FPS
    case = foam_case(tmp / "steps", n=(4, 3, 3), times=("0", "0.5", "1"))
    w = open_file(app, case)
    sc, panel = w.scene, w.sidebar.contours_panel
    m, bar = sc.model, w.anim_bar
    w._show_page("contour:1")
    ed = panel.editors[panel.active][1]
    ed.field.setCurrentIndex(ed.field.findData("p"))
    an = ed.anim
    an.section.set_expanded(True)
    check(an.on.isEnabled() and not an.on.isChecked() and an.note.text() == OFF
          and bar.isHidden(), "three steps: ▸ Animation off at first, a note, no bar")
    an.section.set_expanded(False)
    an.on.setChecked(True)
    app.processEvents()
    check(an.section.expanded and not an.details.isHidden() and not bar.isHidden()
          and bar.count == 3 and bar.index == 2 and bar.readout.text() == "t = 1 · Step 3 / 3",
          f"on: unfolds, the playback bar shows the latest step ({bar.readout.text()})")
    wait(app, lambda: panel._steps_job is None, 30)
    app.processEvents()
    m.case.read_ranges(range(3), ["p"])
    tops = [max(r["p"][1] for r in m.case.known_ranges(i).values() if "p" in r) for i in range(3)]
    timeline = panel.range
    check(abs(timeline[1] - max(tops)) < 1e-9 and an.range_acts["timeline"].isChecked(),
          f"Timeline (default): Min / Max over every step ({timeline})")
    actor = sc.results._actor
    bar.step(-1)
    app.processEvents()
    check(m.time_index == 1 and bar.index == 1 and panel.range == timeline
          and an.step_label.text() == "t = 0.5 · Step 2 / 3",
          "Step Backward: step 2, the same range (no flicker)")
    check(sc.results._actor is actor, "another step: the same actor, its colors changed in place")
    w._show_page("model")
    app.processEvents()
    check(m.time_index == 2 and bar.isHidden(), "the 3D View tab: the latest step, no bar")
    w._show_page("contour:1")
    app.processEvents()
    check(m.time_index == 1 and not bar.isHidden() and bar.index == 1,
          "back to the animated contour: its step again")
    ed.show_acts["gradient"].trigger()
    app.processEvents()
    check(not an.range_acts["timeline"].isEnabled() and "Gradient" in an.range_note.text(),
          "Gradient: Color scale range grayed (each step its own), and why")
    ed.show_acts["value"].trigger()
    ed.lo.setValue(0.5)
    ed.hi.setValue(3.0)
    ed.commit()
    panel.contour_changed(ed.c["id"])
    app.processEvents()
    check(not an.range_acts["timeline"].isEnabled() and panel.range == (0.5, 3.0)
          and "typed" in an.range_note.text(), "Min and Max typed: grayed too")
    ed.lo.setValue(None)
    ed.hi.setValue(None)
    ed.commit()
    panel.contour_changed(ed.c["id"])
    app.processEvents()
    check(an.range_acts["timeline"].isEnabled() and an.range_note.isHidden(),
          "cleared: Color scale range back")
    p_in = np.asarray(m.parts["inlet"].cell_data["p"])
    check(np.allclose(p_in, np.asarray(m.case.step_arrays(1)["inlet"][1]["p"])),
          "the parts carry step 2's values")
    an.range_acts["step"].trigger()
    app.processEvents()
    check(abs(panel.range[1] - tops[1]) < 1e-6 and panel.range[1] < timeline[1],
          f"Current Step: this step's own Min / Max ({panel.range})")
    ed.lo.setValue(0.25)
    ed.commit()
    panel.contour_changed(ed.c["id"])
    bar.step(1)
    app.processEvents()
    check(panel.range[0] == 0.25 and abs(panel.range[1] - tops[2]) < 1e-6,
          "a typed Min stays; Max follows the step")
    ed.lo.setValue(None)
    ed.commit()
    an.range_acts["timeline"].trigger()
    bar.slider.setValue(0)
    app.processEvents()
    check(m.time_index == 0 and bar.index == 0 and bar.readout.text() == "t = 0 · Step 1 / 3",
          "the scrubber jumps to the first step")
    bar.a_loop.setChecked(True)
    bar.play()
    bar.set_index(2)
    bar._tick()
    check(bar.index == 0 and bar.playing, "Loop on: after the last step, the first")
    bar.set_index(2)
    bar.a_loop.setChecked(False)
    bar._tick()
    check(bar.index == 2 and not bar.playing and bar.a_play.text() == "Play",
          "Loop off: stops at the last step")
    first = bar.interval
    bar.fps.setValue(24)
    fast = bar.interval
    bar.fps.setValue(500)                              # (1 – 120)
    check(bar.fps.value() == 120 and first == round(1000 / DEFAULT_FPS) and fast == 42
          and bar.interval == 8, f"frame rate typed: {DEFAULT_FPS} fps at first, the timer "
          f"follows ({first}, {fast}, {bar.interval} ms)")
    widths = set()
    for i in range(3):
        bar.set_index(i, emit=False)
        widths.add((bar.readout.width(), bar.slider.geometry().x(), bar.slider.width()))
    check(len(widths) == 1 and bar.readout.minimumWidth() == bar.readout.maximumWidth(),
          "the time readout keeps one width: the scrubber never moves")
    bar.fps.setValue(60)
    bar.a_loop.setChecked(True)
    w._play_pause()                                     # Space
    wait(app, lambda: bar.index == 1, 10)
    w._play_pause()
    check(not bar.playing and m.time_index == bar.index,
          "Space plays (the steps follow the timer) and pauses")
    sp = w.sidebar.section_panel
    sp.enable.setChecked(True)
    sp.fill.setChecked(True)
    sc.section.set_plane(origin=(0.3, 0.5, 0.5), normal=(1, 0, 0))
    wait(app, lambda: sc.section._volume is not None, 30)
    app.processEvents()
    bar.set_index(1)
    app.processEvents()
    cut = lambda: sc.section.cut_cells                                  # noqa: E731
    first = np.asarray(cut().point_data["ResultT"]).copy()
    p1 = float(np.nanmax(cut().point_data["p"]))
    bar.set_index(2)
    app.processEvents()
    p2 = float(np.nanmax(cut().point_data["p"]))
    check("ResultT" in cut().point_data and abs(p2 - 2 * p1) < 1e-4
          and not np.allclose(first, cut().point_data["ResultT"]),
          f"the section's cut cells: colored by p, and follow the step (max {p1:.4g} → {p2:.4g})")
    src = sc.section._cut_src
    check(list(src.point_data.keys()) == ["p"] and not len(src.cell_data.keys()),
          "the cutter is given p only (not every field to interpolate)")
    bar.set_index(0)
    an.on.setChecked(False)
    app.processEvents()
    check(m.time_index == len(m.times) - 1 and bar.isHidden() and not bar.playing,
          f"▸ Animation off: no bar, back to the latest step ({m.time_index})")
    an.on.setChecked(True)
    app.processEvents()
    w._show_page("model")
    app.processEvents()
    check(bar.isHidden() and not bar.playing, "the 3D View tab: no playback bar")
    w.close()


def units_and_constants(app, files):
    """Custom… units for one file only; ▸ Animation grayed for a field the same at
    every step."""
    import shutil
    import tempfile
    from pathlib import Path
    tmp = Path(tempfile.mkdtemp(prefix="foam-units-"))
    try:
        _units_and_constants(app, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _units_and_constants(app, tmp):
    import numpy as np
    from conftest import wait
    from fixtures import foam_case
    from meshviewer.core.units import QUANTITIES, is_custom
    from meshviewer.gui import memory
    from meshviewer.gui.panels.contour_animation import CONSTANT
    from meshviewer.gui.panels.contour_editor import CUSTOM_ITEM
    from meshviewer.gui.store import settings
    from meshviewer.render.element_details import field_values
    case = foam_case(tmp / "box", times=("0", "0.5", "1"))
    w = open_file(app, case)
    sc, sb, panel = w.scene, w.sidebar, w.sidebar.contours_panel
    w._show_page("contour:1")
    ed = panel.editors[panel.active][1]
    ed.field.setCurrentIndex(ed.field.findData("k"))
    app.processEvents()
    menu = [ed.file_unit._items[i][1] for i in range(ed.file_unit.count())]
    check(menu[-1] == CUSTOM_ITEM and ed.file_unit._items[-1][0] == "Custom…",
          "Unit in file ends with Custom…")
    before = panel.range
    ed.set_custom_unit("file", "m^2/s^2")
    app.processEvents()
    check(panel.unit_label("k") == "m^2/s^2" and is_custom("m^2/s^2")
          and ed.file_unit.currentData() == "m^2/s^2" and panel.range == before
          and sc.colorbar.spec["title"].endswith("(m^2/s^2)"),
          f"a custom unit: the values as written, labeled with it ({sc.colorbar.spec['title']})")
    w.set_select_kind("mesh_cell")
    sc.elements._take(("outlet", 0), False)
    app.processEvents()
    rows = dict(sb.selected_panel.field_rows)
    check(rows.get("Turbulent kinetic energy k", "").endswith("m^2/s^2"),
          f"Measure Selected labels it too ({rows.get('Turbulent kinetic energy k')})")
    ed.field.setCurrentIndex(ed.field.findData("p"))
    ed.set_custom_unit("shown", "my p")
    app.processEvents()
    v = float(np.asarray(sc.model.parts["outlet"].cell_data["p"])[0])
    check(panel.unit_label("p") == "my p" and panel.shown_values("p", v) == v,
          "Shown in a custom unit: the file's numbers, labeled with it")
    w.remember_view()
    saved = (memory.load(case) or {}).get("results", {}).get("units", {})
    st = settings()
    leaks = [k for k in st.allKeys() if k != memory._key(case)
             and "m^2/s^2" in str(st.value(k))]
    check(saved.get("k", [None])[0] == "m^2/s^2" and saved.get("p", [None, None])[1] == "my p"
          and not any("m^2/s^2" in t or "my p" in t for t in QUANTITIES.values())
          and not leaks, "kept with this file only: not in the unit tables or the app's settings")
    # ▸ Animation: a field the same at every step can't be animated
    wait(app, lambda: panel._steps_job is None, 30)
    app.processEvents()
    an = ed.anim
    ed.field.setCurrentIndex(ed.field.findData("p"))
    an.on.setChecked(True)
    app.processEvents()
    check(an.on.isEnabled() and not w.anim_bar.isHidden(), "p varies: Animation on, the bar")
    ed.field.setCurrentIndex(ed.field.findData("UMeanx"))
    app.processEvents()
    title = an.section.title_label
    check(title.property("unavailable") and not an.on.isEnabled() and not an.on.isChecked()
          and an.note.text() == CONSTANT and title.toolTip() == CONSTANT
          and w.anim_bar.isHidden(),
          "UMeanx (the same each step): title and switch grayed, off, no bar")
    ed.field.setCurrentIndex(ed.field.findData("T"))
    app.processEvents()
    check(not title.property("unavailable") and an.on.isEnabled(),
          "T (varies): ▸ Animation available again")
    w.close()
    other = foam_case(tmp / "other", n=(2, 2, 2), times=("0", "1"))
    w = open_file(app, other)
    check(w.sidebar.contours_panel.unit_label("k") == "m²/s²",
          "another file: its own units (no custom one)")
    w.close()


def menus_and_cache(app, files):
    """Field menus in submenus per group (Contours, Plots); the timeline cache: 512 MB by
    default, set in Settings, its byte limit kept; reading ahead."""
    import shutil
    import tempfile
    from pathlib import Path
    tmp = Path(tempfile.mkdtemp(prefix="foam-cache-"))
    try:
        _menus_and_cache(app, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _submenus(select):
    """{group: ([field], checked)} of a cascading MenuSelect's menu, and the field checked."""
    menu, out, on = select.build_menu(), {}, None
    for a in menu.actions():
        sub = a.menu()
        if sub is None:
            continue
        fields = [s.text() for s in sub.actions()]
        out[sub.title()] = (fields, a.isChecked())
        on = next((s.text() for s in sub.actions() if s.isChecked()), on)
    return out, on


def _menus_and_cache(app, tmp):
    import numpy as np
    from fixtures import foam_case
    from meshviewer.core.mesh import openfoam_cache as oc
    from meshviewer.gui.store import settings
    case = foam_case(tmp / "box", n=(3, 3, 3), times=("0", "0.5", "1", "1.5"))
    w = open_file(app, case)
    sc, sb, panel = w.scene, w.sidebar, w.sidebar.contours_panel
    ed = panel.editors[panel.active][1]
    ed.field.setCurrentIndex(ed.field.findData("p"))
    groups, on = _submenus(ed.field)
    checked = [g for g, (_f, c) in groups.items() if c]
    check({"Flow", "Pressure", "Turbulence", "Wall", "Position"} <= set(groups)
          and checked == ["Pressure"] and on == "Pressure p"
          and "Pressure p" in groups["Pressure"][0] and "Speed" in groups["Flow"][0]
          and not any(a.text() == "Pressure p" for a in ed.field.build_menu().actions()),
          f"Contours ▸ Field: a submenu per group, the field and its group checked "
          f"({sorted(groups)})")
    check("Face flux φ" in groups["Flow"][0], "3D: phi offered (on the patches' faces)")
    w._show_page("contour:1")
    names = list(sc.names)
    sb._visibility_changed(names, False)
    app.processEvents()
    check(ed.stats.text() == "No visible boundary has this field."
          and ed.lo.placeholderText() == "auto" and ed.hi.placeholderText() == "auto",
          "nothing shown: no old auto Min / Max left beside why")
    sb._visibility_changed(names, True)
    app.processEvents()
    pp = sb.plots_panel
    sb.show_tab("analyze")
    i = pp.add("section", "Cut")
    app.processEvents()
    pe = pp.editors[i][1]
    pgroups, _on = _submenus(pe.value)
    check(pe.value.cascade and "Pressure" in pgroups and "Position" in pgroups,
          f"Plots ▸ Values: the same submenus ({sorted(pgroups)})")
    # the cache: everything read stays (no limit, no setting)
    app.show_settings()
    app.processEvents()
    check(not hasattr(app._settings, "cache") and "timeline_cache_mb" not in app.prefs
          and settings().value("prefs/timeline_cache_mb") is None,
          "no Timeline cache limit in Settings or the saved settings")
    app._settings.close()
    case_ = sc.model.case
    case_.cache.wait(10)
    case_.prefetch(0)
    case_.cache.wait(10)
    keys = set(case_.cache._items)
    check(all(("field", s, "p") in keys for s in range(1, 4)),
          "reading ahead: the next steps' fields in the cache")
    entry = case_.cache.get(("field", 1, "p"))
    check(all(a.dtype == np.float32 for pt, ce in entry.values() for a in (*pt.values(),
                                                                          *ce.values())),
          "kept as float32")
    for s in range(4):
        case_.step_arrays(s)
    n = len(case_.cache._items)
    for s in range(4):
        case_.step_arrays(s)
    check(all(("field", s, f) in keys | set(case_.cache._items) for s in range(4)
              for f in case_.fields_at(s)) and len(case_.cache._items) == n
          and case_.cache.nbytes > 0 and not hasattr(oc, "set_limit_mb"),
          f"every step stays in memory, nothing evicted ({n} entries, "
          f"{case_.cache.nbytes / 2 ** 20:.2f} MB)")
    w.close()


def _all(app, files):
    test(app, files)
    openfoam(app, files)
    menus_and_cache(app, files)
    units_and_constants(app, files)
    headers(app, files)
    animation(app, files)


if __name__ == "__main__":
    run(_all)
