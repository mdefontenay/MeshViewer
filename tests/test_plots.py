"""F13 Plots (section plots in tabs under the 3D view) and F15 (gradient); Flip Y, Swap
Axes, View ▸ Fit on a plot, a plot's tab and its fold-out opened together."""
import numpy as np
from PySide6.QtCore import Qt

from conftest import ContourTool, check, open_file, run


def test(app, files):
    from meshviewer.core import plots
    w = open_file(app, files["tecplot"])
    sc, sb = w.scene, w.sidebar
    pp = sb.plots_panel
    check([a.text() for a in w.view_bar_actions()] == ["3D View", "Contour 1"],
          "before a plot: 3D Model and the file's contour")
    i = pp.add("section", "Mid")
    app.processEvents()
    check(w.view_bar.isVisible() and w._page == f"plot:{i}"
          and w.stack.currentWidget() is w.plot_page, "New Plot: a tab, shown")
    check(set(pp.editors) == {i} and pp.editors[i][0].title_label.text() == "Mid",
          "a sub-section named Mid")
    r = pp.results[i]
    check(not r["empty"] and r["value"] == "cp" and r["flip"], f"cp, negative up {r['value']}")
    sphere = [c for c in r["curves"] if c["part"] == "SPHERE"]
    check(sphere and abs(sphere[0]["y"].min() + 1.25) < 0.02, "cp −1.25 at the top of the sphere")
    # the page: hover anywhere along a line; cp is drawn with y flipped (negative up)
    w._show_page(f"plot:{i}")
    pl = w.plot_page.plot
    check(pl.titles[1].startswith("cp") and r["flip"] and pl.view.get("y_flip"),
          f"cp: y flipped, the values as they are ({pl.titles[1]})")
    x, y, _c, _part = pl.curves[0]
    k = int(np.argmax(np.abs(np.diff(x)) + np.abs(np.diff(y))))     # the longest step
    pa, pb = pl._px(x[k], y[k]), pl._px(x[k + 1], y[k + 1])
    h = pl._nearest((pa + pb) / 2)
    check(h is not None and abs(h[0] - (x[k] + x[k + 1]) / 2) < 1e-6 * max(1, abs(x[k]))
          and abs(h[1] - (y[k] + y[k + 1]) / 2) < 1e-6 * max(1, abs(y[k])),
          "hover: between two points, the values in between")
    cp = r["curves"][0]["y"]
    check(np.allclose(np.nanmax(cp), np.nanmax(y)), "the values as they are")
    ally = np.concatenate([np.asarray(cc[1], dtype=float) for cc in pl.curves])
    top = pl._px(x[0], float(np.nanmin(ally))).y()
    bottom = pl._px(x[0], float(np.nanmax(ally))).y()
    check(top < bottom, "y flipped: the lowest cp at the top")
    # Axes: ranges, log, flip (only how it is drawn); the wheel zooms, Fit
    ed0 = pp.editors[i][1]
    n_before = len(pp.results)
    ed0._view(x_flip=True)
    check(pl.view.get("x_flip") and pl._px(float(np.nanmin(x)), 0).x() >
          pl._px(float(np.nanmax(x)), 0).x(), "Flip X: the x axis reversed")
    ed0._view(x_flip=False)
    ed0.set_ranges(-1.0, 1.0, None, None)
    check(pl._r[0] == (-1.0, 1.0) and ed0.axis_range["x_min"].value() == -1.0,
          "typed X min / max: the plot's range, the fields")
    from PySide6.QtCore import QPoint, QPointF
    from PySide6.QtGui import QWheelEvent
    c = QPointF(pl.width() / 2, pl.height() / 2)
    pl.wheelEvent(QWheelEvent(c, c, QPoint(0, 0), QPoint(0, 240), Qt.NoButton,
                              Qt.NoModifier, Qt.NoScrollPhase, False))
    m0 = pp.plot(i)
    check(m0["x_max"] - m0["x_min"] < 2.0 and m0["y_min"] is not None,
          f"the wheel zooms in: its ranges in Axes ({m0['x_min']:.3g}…{m0['x_max']:.3g})")
    cam = sc.camera_snapshot()
    w.a_fit.trigger()                                   # View ▸ Fit, ⌘0
    check(all(pp.plot(i)[k] is None for k in ("x_min", "x_max", "y_min", "y_max"))
          and pl._r is not None and sc.same_camera(cam, sc.camera_snapshot()),
          "View ▸ Fit (⌘0) on a plot's tab: the plot back to its data, the 3D view as it was")
    from PySide6.QtWidgets import QPushButton
    check(not any(b.text() == "Fit" for b in ed0.findChildren(QPushButton)),
          "no Fit button under Axes any more")
    # Flip Y: the y axis reversed at once (cp: on by default)
    fy = ed0.axis_flip["y"]
    lo_y, hi_y = float(np.nanmin(ally)), float(np.nanmax(ally))
    check(fy.isChecked() and pl._px(x[0], lo_y).y() < pl._px(x[0], hi_y).y(), "Flip Y on (cp)")
    fy.setChecked(False)
    app.processEvents()
    check(not pl.view["y_flip"] and pl._px(x[0], lo_y).y() > pl._px(x[0], hi_y).y()
          and pp.plot(i)["flip"] is False, "Flip Y off: the y axis turned over at once")
    fy.setChecked(True)
    app.processEvents()
    check(pl.view["y_flip"] and pl._px(x[0], lo_y).y() < pl._px(x[0], hi_y).y(), "Flip Y on")
    # Swap Axes: X ↔ Y, with their ranges, log and flip
    ed0.set_ranges(-1.0, 1.0, None, None)
    titles = pl.titles
    xs0 = np.asarray(pl.curves[0][0])
    ys0 = np.asarray(pl.curves[0][1])
    ed0.swap.trigger()
    app.processEvents()
    m = pp.plot(i)
    check(m["swap"] and pl.titles == (titles[1], titles[0])
          and np.allclose(pl.curves[0][0], ys0) and np.allclose(pl.curves[0][1], xs0),
          f"Swap Axes: cp across, the position up {pl.titles}")
    check(m["y_min"] == -1.0 and m["y_max"] == 1.0 and m["x_min"] is None
          and m["x_flip"] is True and m["flip"] is False and pl.view["x_flip"]
          and not pl.view["y_flip"] and ed0.axis_range["y_min"].value() == -1.0
          and ed0.axis_flip["x"].isChecked() and not ed0.axis_flip["y"].isChecked(),
          "their ranges and flips swapped too")
    ed0.swap.trigger()
    app.processEvents()
    check(not m["swap"] and pl.titles == titles and m["x_min"] == -1.0 and m["flip"] is True
          and not m["x_flip"] and pl.view["y_flip"], "Swap Axes again: back")
    ed0.fit_view()
    filter_checks(app, w, i)
    # the layout: Plane, Plot (Values, Along, their filters), ▸ Axes (names, Swap), Data
    g = ed0.slider.parentWidget().layout()
    grid = next(c for c in (g.itemAt(n).layout() for n in range(g.count()))
                if c is not None and c.indexOf(ed0.slider) >= 0)
    check(grid.getItemPosition(grid.indexOf(ed0.slider))[1:] == (0, 1, 4),
          "the plane's slider: the whole width")
    check(ed0.axis_names["x"].text() == "Y" and ed0.axis_names["y"].text() == "cp"
          and ed0.swap.text() == "Swap", f"Axes: the plot's names "
          f"({ed0.axis_names['x'].text()}, {ed0.axis_names['y'].text()}) and Swap")
    ed0.swap.trigger()
    check(ed0.axis_names["x"].text() == "cp" and ed0.axis_names["y"].text() == "Y",
          "swapped: the names follow")
    ed0.swap.trigger()
    check([a.text() for a in ed0.data_buttons.buttons and
           [b.defaultAction() for b in ed0.data_buttons.buttons]] == ["Import…", "Export…"],
          "Data: Import… · Export…")
    # a plot's tab and its fold-out open together (the others fold)
    other = pp.add("section", "Other")
    app.processEvents()
    check(pp.editors[other][0].expanded and not pp.editors[i][0].expanded
          and sb.is_open("plots") and sb.current_tab() == "analyze",
          "new plot: its fold-out open in the sidebar, the other folded")
    w._plot_acts[i].trigger()
    app.processEvents()
    check(pp.editors[i][0].expanded and not pp.editors[other][0].expanded,
          "its tab chosen: its fold-out open, the other folded")
    pp.editors[other][0].set_expanded(True)
    app.processEvents()
    check(w._page == f"plot:{other}" and not pp.editors[i][0].expanded,
          "a fold-out opened: its tab shown")
    pp.remove(other)
    w._show_page(f"plot:{i}")
    plot_parts(app, w, i)
    ed0._view(y_log=True)
    check(pl.view.get("y_log") and (pl._r is None and "log" in pl._why
                                    or all(t[0] > 0 for t in pl._ticks("y", 5))),
          "Log Y: values above 0 only (here none: it says so)")
    ed0._view(y_log=False)
    check(ed0.axes_section.rule is not None, "Axes: a subsection, a line above it")
    sb.show_section("plots", True, expand=True)
    w._show_cuts()
    check(sc.plot_cut._actor is not None, "the cut drawn in 3D")
    check(sb.current_tab() == "analyze" and sb.tab_shown("plots"), "Plots: the Analyze tab")
    sb.show_tab("view")                                  # another tab: no cuts in 3D
    check(sc.plot_cut._actor is None, "another tab: the cut hidden")
    sb.show_tab("analyze")
    check(sc.plot_cut._actor is not None, "Analyze tab again: the cut back")
    ed = pp.editors[i][1]
    sb._visibility_changed(["FLOOR"], False)            # the chord of what is shown
    ed.chord.setChecked(True)
    r = pp.results[i]
    xs = np.concatenate([c["x"] for c in r["curves"] if c["part"] == "SPHERE"])
    check(r["chord_on"] and abs(xs.min()) < 1e-9 and abs(xs.max() - 1) < 1e-9, "x/c 0…1")
    sb._visibility_changed(["FLOOR"], True)
    r = pp.results[i]
    ed.slider.setValue(900)                              # the plane moves
    ed.flush()
    r2 = pp.results[i]
    check(abs(r2["origin"][plots.AXES.index(pp.plot(i)["axis"])] -
              r["origin"][plots.AXES.index(pp.plot(i)["axis"])]) > 0.1, "slider moves it")
    a, b = plots.in_plane(pp.plot(i)["axis"])
    ed.along[b].trigger()
    check(ed.along[b].isChecked() and not ed.along[a].isChecked() and pp.results[i]["along"] == b,
          f"Along {b.upper()} lit")
    ed.along[a].trigger()
    check(ed.along[a].isChecked() and not ed.along[b].isChecked(), f"Along {a.upper()} lit again")
    own = pp.plot(i)["axis"]
    check(not ed._along_cap.buttons[plots.AXES.index(own)].isVisible()
          and ed.chord.text() == "Normalize", "the plane's own axis hidden; Normalize")
    # Advanced: a tilted plane through the same origin
    ed.edit_plane.setChecked(True)
    check(ed.advanced.isVisible(), "Edit Plane (✎): origin and normal shown")
    for box, v in zip(ed.normal, (1.0, 0.0, 1.0)):
        box.setValue(v)
    ed._normal_typed()
    r = pp.results[i]
    check(abs(abs(r["normal"][0]) - 2 ** -0.5) < 1e-6 and not any(a.isChecked()
          for a in ed.axis.values()), "tilted plane: no X / Y / Z lit")
    check([b.value() for b in ed.normal] == [1.0, 0.0, 1.0],
          f"the normal stays as typed ({[b.value() for b in ed.normal]})")
    ed.axis["x"].trigger()
    check(pp.plot(i)["normal"] is None and ed.axis["x"].isChecked(), "X: straight again")
    # the eye: cut drawn or not
    sec = pp.editors[i][0]
    from meshviewer.gui.widgets import IconToggle
    eye = sec.header.findChild(IconToggle)
    sb.show_section("plots", True)
    w._show_cuts()
    check(sc.plot_cut._actor is not None, "eye open: the cut in 3D")
    eye.setChecked(False)
    check(sc.plot_cut._actor is None and pp.plot(i)["show"] is False, "eye shut: no cut")
    eye.setChecked(True)
    ed.set_reference("test.csv", [(0.1, -0.5), (0.5, 0.2)])
    check(w.plot_page.plot.ref == [(0.1, -0.5), (0.5, 0.2)],
          f"reference points on the plot ({w.plot_page.plot.ref})")
    csv = plots.to_csv(pp.plot(i), pp.results[i])
    check(csv.startswith("part,x/c,cp,X,Y,Z"), "CSV export: " + csv.splitlines()[0])
    j = pp.add("section", "Shape")
    m2 = pp.plot(j)
    pp.editors[j][1].value.setCurrentIndex(pp.editors[j][1].value.findData("coord:z"))
    check(m2["value"] == "coord:z" and not pp.results[j]["flip"], "second one: the shape (Z)")
    check(len(w._plot_acts) == 2 and w._page == f"plot:{j}", "two tabs")
    w._show_page("model")
    check(w.stack.currentWidget() is w.plotter, "back to the 3D model")
    pp.rename(i, "Root")
    check(w._plot_acts[i].text() == "Root" and pp.editors[i][0].title_label.text() == "Root",
          "renamed: tab and sub-section")
    sb._visibility_changed(["SPHERE"], False)            # hidden in the 3D View
    check("SPHERE" in {c["part"] for c in pp.results[i]["curves"]},
          "hidden in the 3D View: the plot (its own parts) still cuts it")
    sb._visibility_changed(["SPHERE"], True)
    w._show_page(f"plot:{i}")
    sb._visibility_changed(["SPHERE"], False)            # in its tab: only the floor left
    check({c["part"] for c in pp.results[i]["curves"]} <= {"FLOOR"}, "hidden boundary not cut")
    sb._visibility_changed(["SPHERE"], True)
    w._show_page("model")
    rng = np.random.default_rng(1)                      # slide fast (crashed in 2.4.4)
    for k in range(200):
        ed.slider.setValue(int(rng.integers(0, 1000)))
        if k % 5 == 0:
            ed.flush()
            app.processEvents()
        w._show_page("model" if k % 2 else f"plot:{i}")
    ed.flush()
    check(not pp.results[i]["empty"] or True, "200 fast slides, no crash")
    many = [pp.add("section", f"Station {k}") for k in range(14)]    # tabs scroll sideways
    app.processEvents()
    bar = w._pages_scroll.horizontalScrollBar()
    check(bar.maximum() > 0 and bar.value() > 0, f"many tabs: they scroll, the last in view "
          f"({bar.value()} / {bar.maximum()})")
    btn = next(b for b in w._pages_scroll.widget().buttons
               if b.defaultAction() is w._plot_acts[many[0]])
    check(btn.contextMenuPolicy() == Qt.CustomContextMenu, "right-click on a plot's tab")
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    def pick(text):
        menu = QApplication.activePopupWidget()
        act = next(a for a in menu.actions() if a.text() == text)
        menu.close()
        act.trigger()
    QTimer.singleShot(100, lambda: pick("Delete"))
    w._tab_menu("plot", many[0], btn.mapToGlobal(btn.rect().center()))
    app.processEvents()
    check(many[0] not in w._plot_acts and pp.plot(many[0]) is None, "tab menu ▸ Delete")
    QTimer.singleShot(100, lambda: pick("Open"))
    w._tab_menu("plot", many[1], w.mapToGlobal(w.rect().center()))
    app.processEvents()
    check(w._page == f"plot:{many[1]}", "tab menu ▸ Open")
    for k in many[1:]:
        pp.remove(k)
    pp.ask_new()                                        # the New Plot sheet
    d = pp._dialog
    d.name.setText("Tip")
    d.accept()
    k = max(pp.editors)
    check(pp.plot(k)["name"] == "Tip" and w._page == f"plot:{k}", "sheet: named Tip")
    pp.remove(k)
    pp.remove(j)
    check(set(w._plot_acts) == {i}, "deleted: its tab too")
    w._show_page(f"plot:{i}")
    w.remember_view()
    from meshviewer.gui import memory
    st = memory.load(w.path)
    check([m["name"] for m in st["plots"]] == ["Root"] and st["inflation_page"]["page"] ==
          f"plot:{i}", "remembered: the plot and its tab")
    # F15: gradient
    rp = ContourTool(sb.contours_panel)
    rp.field.setCurrentIndex(rp.field.findData("cp"))
    rp.show_acts["gradient"].trigger()
    app.processEvents()
    check(rp.shown == "gradient" and "__grad__cp" in sc.model.parts["SPHERE"].point_data
          and sc.results.spec[0] == "__grad__cp", "Show ▸ Gradient: |∇cp| coloured")
    check(not hasattr(rp, "jumps_on"), "no sharp-change highlight any more")
    check(w._page == "contour:1", "editing a contour: its tab shown")
    w._show_page(f"plot:{i}")
    w.close()
    w = open_file(app, files["tecplot"])
    check([m["name"] for m in w.scene.plots] == ["Root"] and w._page == f"plot:{i}"
          and w.view_bar.isVisible(), "reopened: Root and its tab")
    w.close()                                           # (not for 2D: in test_formats.py)


def _ys(pl):
    return np.concatenate([np.asarray(c[1], dtype=float) for c in pl.curves])


def _xs(pl):
    return np.concatenate([np.asarray(c[0], dtype=float) for c in pl.curves])


def _type(box, text):
    box.setText(text)
    box.editingFinished.emit()


def filter_checks(app, w, i):
    """Values and Along data filters (> min, < max, their units); Min / Max to 4
    significant figures unless typed; Lock."""
    pp = w.sidebar.plots_panel
    ed = pp.editors[i][1]
    pl = w.plot_page.plot
    w._show_page(f"plot:{i}")
    every, xs = _ys(pl), _xs(pl)
    n_all = int(np.isfinite(every).sum())
    mid = float((np.nanmin(every) + np.nanmax(every)) / 2)
    vb, ab = ed.filters["value"], ed.filters["along"]
    _type(vb["min"], f"{mid}")
    app.processEvents()
    k = _ys(pl)[np.isfinite(_ys(pl))]
    lo_r = float(pl._data(pl._r[1][0], "y"))
    check(abs(pp.plot(i)["value_min"] - mid) < 1e-9 and np.all(k > mid) and len(k) < n_all
          and lo_r > float(np.nanmin(every)),
          f"Values > {mid:.3g}: the rest left out, the auto range follows ({lo_r:.3g})")
    _type(vb["min"], "")
    _type(vb["max"], f"{mid}")
    app.processEvents()
    k = _ys(pl)[np.isfinite(_ys(pl))]
    check(len(k) and np.all(k < mid) and len(k) < n_all, "Values < max: the rest left out")
    _type(vb["max"], "")
    xmid = float((np.nanmin(xs) + np.nanmax(xs)) / 2)
    _type(ab["min"], f"{xmid}")
    app.processEvents()
    ok = np.isfinite(_ys(pl))
    check(np.all(_xs(pl)[ok] > xmid) and ok.sum() < n_all,
          f"Along > {xmid:.3g}: the points before it left out")
    _type(ab["max"], f"{xmid + 0.5 * (np.nanmax(xs) - xmid)}")
    app.processEvents()
    ok = np.isfinite(_ys(pl))
    check(np.all(_xs(pl)[ok] < xmid + 0.5 * (np.nanmax(xs) - xmid)), "Along < max too")
    s, unit = w.scene.measure.unit_scale()
    check(ed.filter_units["along"].text() == unit and ed.filter_units["value"].text() == "",
          f"the units beside them: '{ed.filter_units['along'].text()}' and none for cp")
    for box in (ab["min"], ab["max"]):
        _type(box, "")
    app.processEvents()
    check(int(np.isfinite(_ys(pl)).sum()) == n_all and pp.plot(i)["along_min"] is None,
          "filters empty: every point again")
    # Min / Max: 4 significant figures when set by the zoom, as typed when typed
    ed.set_ranges(-1.234567891, 2.718281828, None, None)
    check(ed.axis_range["x_min"].text() == "-1.235" and ed.axis_range["x_max"].text() == "2.718",
          f"zoom: 4 significant figures ({ed.axis_range['x_min'].text()})")
    _type(ed.axis_range["x_min"], "-1.2345678")
    app.processEvents()
    ed.sync_axes()
    check(ed.axis_range["x_min"].text() == "-1.2345678" and pp.plot(i)["x_min"] == -1.2345678,
          "typed: kept as typed")
    ed.fit_view()
    w._show_page(f"plot:{i}")
    ph = ed.axis_range["y_min"].placeholderText()
    digits = ph.lstrip("-").split("e")[0].replace(".", "").lstrip("0")
    check(ph and ph != "auto" and float(ph) is not None and len(digits) <= 4,
          f"empty: its auto value in gray, 4 significant figures ({ph})")
    # Lock: the wheel, a drag and a double-click leave the plot alone
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtGui import QWheelEvent
    ed.lock.setChecked(True)
    app.processEvents()
    r0 = pl._r
    c = QPointF(pl.width() / 2, pl.height() / 2)
    pl.wheelEvent(QWheelEvent(c, c, QPoint(0, 0), QPoint(0, 240), Qt.NoButton,
                              Qt.NoModifier, Qt.NoScrollPhase, False))
    pl.mouseDoubleClickEvent(None)
    check(pp.plot(i)["lock"] and pl._r == r0 and pp.plot(i)["x_min"] is None,
          "Lock: the wheel and a double-click no longer zoom or fit")
    ed.lock.setChecked(False)
    app.processEvents()
    pl.wheelEvent(QWheelEvent(c, c, QPoint(0, 0), QPoint(0, 240), Qt.NoButton,
                              Qt.NoModifier, Qt.NoScrollPhase, False))
    check(pp.plot(i)["x_min"] is not None, "unlocked: the wheel zooms again")
    ed.fit_view()


def plot_parts(app, w, i):
    """A plot's tab: its own shown / hidden boundaries."""
    sc, sb, pp = w.scene, w.sidebar, w.sidebar.plots_panel
    w._show_page(f"plot:{i}")
    names = {c["part"] for c in pp.results[i]["curves"]}
    check("SPHERE" in names, "the plot cuts SPHERE")
    sb._visibility_changed(["SPHERE"], False)
    app.processEvents()
    check("SPHERE" not in {c["part"] for c in pp.results[i]["curves"]}
          and not sc.visible["SPHERE"], "hidden in the plot's tab: not cut")
    w._show_page("model")
    check(sc.visible["SPHERE"] and sb.list.sync_checks is not None
          and "SPHERE" not in {c["part"] for c in pp.results[i]["curves"]},
          "the 3D View: SPHERE shown; the plot keeps its own (still without it)")
    j = pp.add("section", "Other")
    app.processEvents()
    check("SPHERE" in {c["part"] for c in pp.results[j]["curves"]} or pp.results[j]["empty"],
          "another plot: SPHERE shown in its tab")
    w._show_page(f"plot:{i}")
    check(not sc.visible["SPHERE"], "back to the first plot: SPHERE hidden")
    sb._visibility_changed(["SPHERE"], True)
    pp.remove(j)
    w._show_page(f"plot:{i}")


if __name__ == "__main__":
    run(test)
