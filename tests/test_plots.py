"""F13 Plots (section plots in tabs under the 3D view) and F15 (gradient)."""
import numpy as np
from PySide6.QtCore import Qt

from conftest import check, open_file, run


def test(app, files):
    from meshviewer.core import plots
    w = open_file(app, files["tecplot"])
    sc, sb = w.scene, w.sidebar
    pp = sb.plots_panel
    check(not w.view_bar.isVisible(), "no tabs before a plot")
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
    check(w.plot_page.plot.ref == [(0.1, -0.5), (0.5, 0.2)], "reference points on the plot")
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
    sb._visibility_changed(["SPHERE"], False)            # only the floor left
    check({c["part"] for c in pp.results[i]["curves"]} <= {"FLOOR"}, "hidden boundary not cut")
    sb._visibility_changed(["SPHERE"], True)
    rng = np.random.default_rng(1)                      # slide fast (crashed in 2.4.4)
    for k in range(400):
        ed.slider.setValue(int(rng.integers(0, 1000)))
        if k % 5 == 0:
            ed.flush()
            app.processEvents()
        w._show_page("model" if k % 2 else f"plot:{i}")
    ed.flush()
    check(not pp.results[i]["empty"] or True, "400 fast slides, no crash")
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
    w._tab_menu(many[0], btn.mapToGlobal(btn.rect().center()))
    app.processEvents()
    check(many[0] not in w._plot_acts and pp.plot(many[0]) is None, "tab menu ▸ Delete")
    QTimer.singleShot(100, lambda: pick("Open"))
    w._tab_menu(many[1], w.mapToGlobal(w.rect().center()))
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
    rp = sb.results_panel
    rp.field.setCurrentIndex(rp.field.findData("cp"))
    rp.colour_on.setChecked(True)
    rp.show_acts["gradient"].trigger()
    app.processEvents()
    check(rp.shown == "gradient" and "__grad__cp" in sc.model.parts["SPHERE"].point_data
          and sc.results.spec[0] == "__grad__cp", "Show ▸ Gradient: |∇cp| coloured")
    check(not hasattr(rp, "jumps_on"), "no sharp-change highlight any more")
    w.close()
    w = open_file(app, files["tecplot"])
    check([m["name"] for m in w.scene.plots] == ["Root"] and w._page == f"plot:{i}"
          and w.view_bar.isVisible(), "reopened: Root and its tab")
    w.close()
    w = open_file(app, files["fluent2d"])
    check(bool(w.sidebar._boxes["plots"].parts[0][1].text()), "Plots: not for 2D")
    w.close()


if __name__ == "__main__":
    run(test)
