"""Contours: Tecplot fields colored on the boundaries; several contours, each with its
tab; the color bar."""
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
    drawn = lambda: np.nansum(np.asarray(sc.results._surf.point_data["ResultT"]))   # noqa: E731
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
    check(span(rp.cmap) == (1, 1, 3) and span(ed.height_slider) == (1, 1, 2)
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


if __name__ == "__main__":
    run(test)
