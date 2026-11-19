"""Probe (Analyze tab): points, lines and areas from Select ▾ or typed X / Y / Z — on a
file with one step (every field in the card) and on an OpenFOAM case with several (the
field over time in a tab, its line synced with the step shown both ways)."""
import shutil
import tempfile
import time
from pathlib import Path

import numpy as np

from conftest import check, open_file, run, wait


def static(app, files):
    """Tecplot .dat: the values in the card, no tab; exact at a node, length- / area-
    weighted along edges and over faces (as Measure Selected); Copy Values, Export CSV."""
    from PySide6.QtWidgets import QApplication
    from meshviewer.core.fields import field_values
    from meshviewer.gui.panels.contour_editor import field_label
    from meshviewer.render.element_details import field_values as selected_values
    w = open_file(app, files["tecplot"])
    sc, sb, pp = w.scene, w.sidebar, w.sidebar.probes_panel
    el = sc.elements
    check(not sb._boxes["probes"].parts[0][1].text(), "Probe: available with solution fields")
    w.set_select_kind("mesh_node")
    el._take(("FLOOR", 3), False)
    app.processEvents()
    i = pp.add()
    app.processEvents()
    p = pp.probe(i)
    rows = dict((label, v) for label, v, _u in pp.rows(i))
    cp = float(np.asarray(field_values(sc.model.parts["FLOOR"], "cp")[0])[3])
    check(p["target"] == {"kind": "point", "how": "nodes", "nodes": [["FLOOR", 3]]}
          and abs(rows[field_label("cp")][0] - cp) < 1e-12 and not w._probe_acts,
          "a node from Select ▾: its exact values, every field, no tab (one step)")
    ed = pp.editors[i][1]
    check(not ed.static_buttons.isHidden() and ed.series_buttons.isHidden()
          and ed.field.isHidden() and len(ed._rows) == 2 * len(rows),
          "one step: the card lists every field, Copy Values and Export CSV")
    pp.copy_values(i)
    text = QApplication.clipboard().text()
    check(field_label("cp") in text and f"{cp:.10g}" in text, "Copy Values: field, value…")
    w.set_select_kind("mesh_edge")
    sphere = sc.model.parts["SPHERE"]
    ids = list(sphere.get_cell(0).point_ids)
    el._take(("SPHERE", tuple(sorted(ids[:2]))), False)
    el._take(("SPHERE", tuple(sorted(ids[1:3]))), True)
    app.processEvents()
    j = pp.add()
    want = dict(selected_values(el)["fields"])
    got = dict((label, v) for label, v, _u in pp.rows(j))
    check(pp.probe(j)["target"]["kind"] == "line"
          and abs(got[field_label("cp")][0] - want["cp"]) < 1e-9
          and got[field_label("cp")][1] <= got[field_label("cp")][0] <= got[field_label("cp")][2],
          "two edges: a line, length-weighted (as Measure Selected), with min … max")
    w.set_select_kind("mesh_cell")
    el._take(("SPHERE", 0), False)
    el._take(("SPHERE", 5), True)
    app.processEvents()
    k = pp.add()
    want = dict(selected_values(el)["fields"])
    got = dict((label, v) for label, v, _u in pp.rows(k))
    check(pp.probe(k)["target"]["kind"] == "area"
          and abs(got[field_label("cp")][0] - want["cp"]) < 1e-9,
          "two faces: an area, area-weighted (as Measure Selected)")
    node = np.asarray(sphere.points[ids[0]], dtype=float)
    pp.probe(k)["target"] = {"kind": "point", "how": "xyz", "xyz": [float(v) for v in node]}
    pp._update(k)
    got = dict((label, v) for label, v, _u in pp.rows(k))
    check(got[field_label("cp")] is not None and "on SPHERE" in pp.describe(pp.probe(k)),
          f"typed X / Y / Z: the face there ({pp.describe(pp.probe(k))})")
    tmp = Path(tempfile.mkdtemp(prefix="probe-csv-"))
    try:
        fn = pp.write_csv(i, tmp / "p.csv")
        lines = Path(fn).read_text().splitlines()
        check(lines[0] == "field,value,min,max,unit" and len(lines) == 1 + len(rows),
              f"Export CSV (one step): a row per field ({len(lines) - 1})")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    marks = [n for n, _m in sc.probe_marks.shown]
    check(marks == ["Probe 1", "Probe 2", "Probe 3"], f"a marker per probe ({marks})")
    sec, _ed = pp.editors[i]
    sec.trailing.setChecked(False)
    check([n for n, _m in sc.probe_marks.shown] == ["Probe 2", "Probe 3"],
          "its eye off: no marker")
    # Select Vertex Point: the next vertex clicked, Measure Selected not opened
    opened, show = [], sb.show_section
    sb.show_section = lambda key, *a, **k: opened.append(key) or show(key, *a, **k)
    w.set_select_kind("mesh_cell")
    ed.pick.trigger()
    check(el.kind == "mesh_node" and ed.pick.text() == "Cancel" and not ed.pick_note.isHidden(),
          "Select Vertex Point: Select ▾ on Mesh Node, the button now Cancel")
    el._take(("FLOOR", 2), False)
    app.processEvents()
    check(pp.probe(i)["target"] == {"kind": "point", "how": "nodes", "nodes": [["FLOOR", 2]]}
          and el.kind == "mesh_cell" and w.select_kind == "mesh_cell" and not el.items
          and "selected" not in opened and pp.picking is None
          and ed.pick.text() == "Select Vertex Point",
          "a vertex clicked: the probe's point, Select ▾ back, Measure Selected not opened")
    ed.pick.trigger()
    ed.pick.trigger()
    check(pp.picking is None and el.kind == "mesh_cell", "pressed again: cancelled")
    sb.show_section = show
    w.close()
    w = open_file(app, files["step"])                     # CAD: nothing to probe
    check(w.sidebar._boxes["probes"].parts[0][1].text() ==
          "Open a simulation result file to probe fields.", "CAD: Probe unavailable, and why")
    w.close()


def timed(app, files):
    import shutil as _sh
    tmp = Path(tempfile.mkdtemp(prefix="probe-steps-"))
    try:
        _timed(app, tmp)
    finally:
        _sh.rmtree(tmp, ignore_errors=True)


def _timed(app, tmp):
    from fixtures import FOAM_FIELDS, foam_case
    from meshviewer.gui import memory
    case = foam_case(tmp / "box", n=(5, 4, 3), times=("0", "0.5", "1", "1.5"))
    w = open_file(app, case)
    sc, sb, pp = w.scene, w.sidebar, w.sidebar.probes_panel
    m = sc.model
    pump = lambda: [app.processEvents() for _ in range(5)]          # noqa: E731
    wait(app, lambda: sb.contours_panel._steps_job is None, 30)
    xyz = [0.3, 0.4, 0.5]                                      # inside a cell (not on a face)
    t0 = time.perf_counter()
    i = pp.add(target={"kind": "point", "how": "xyz", "xyz": xyz})
    pp.probe(i)["field"] = "p"
    pp._update(i)
    wait(app, lambda: not pp.busy, 30)
    made = (time.perf_counter() - t0) * 1000
    pump()
    vol = sc.section._volume_orig
    c = vol.find_containing_cell(xyz)
    cc = np.asarray(vol.extract_cells([c]).points).mean(axis=0)
    want = np.array([FOAM_FIELDS["p"][1](*cc, t) for t in m.times])
    got = pp.series[i]["mean"]
    check(np.allclose(got, want, atol=1e-5),
          f"a typed point: its cell's p at every step ({np.round(got, 3)}; {made:.0f} ms)")
    check(w._page == f"probe:{i}" and not w.anim_bar.isHidden()
          and w.stack.currentWidget() is w.probe_page
          and w.probe_page.plot.playhead == m.times[m.time_index],
          "its plot over time opens in a tab, the playback bar under it, the step drawn")
    w.anim_bar.set_index(1)
    pump()
    check(w.probe_page.plot.playhead == m.times[1], "the bar moves the plot's line")
    w.probe_page.plot.time_picked.emit(1.4)
    pump()
    check(m.time_index == 3 and w.anim_bar.index == 3 and w.probe_page.plot.playhead == 1.5,
          "a click on the plot: the 3D view and the bar go to that step")
    rows = dict((label, v) for label, v, _u in pp.rows(i))
    check(abs(rows["At this step"][0] - want[3]) < 1e-5, "the card: the value at this step")
    fn = pp.write_csv(i, tmp / "series.csv")
    lines = Path(fn).read_text().splitlines()
    check(len(lines) == 1 + len(m.times) and lines[0].startswith("time,Pressure p")
          and lines[-1].startswith("1.5,"), f"Export CSV: (time, value) ({lines[0]})")
    # a line through the cells (two nodes picked), an area (a boundary): mean, min, max
    w.set_select_kind("mesh_node")
    el = sc.elements
    inlet, outlet = m.parts["inlet"], m.parts["outlet"]
    el._take(("inlet", int(np.argmin(np.linalg.norm(inlet.points - [0, .5, .5], axis=1)))), False)
    el._take(("outlet", int(np.argmin(np.linalg.norm(outlet.points - [1, .5, .5], axis=1)))), True)
    j = pp.add()
    pp.probe(j)["field"] = "p"
    pp._update(j)
    wait(app, lambda: not pp.busy, 30)
    r = pp.series[j]
    check(pp.probe(j)["target"]["how"] == "through"
          and np.all(r["min"][1:] < r["mean"][1:]) and np.all(r["mean"][1:] < r["max"][1:]),
          "two nodes: a line through the cells, with min < mean < max at each step")
    w.set_select_kind("part")
    sc.set_selection(["outlet"])
    k = pp.add()
    wait(app, lambda: not pp.busy, 30)
    check(pp.probe(k)["target"] == {"kind": "area", "how": "parts", "parts": ["outlet"]}
          and k in pp.series, "a boundary selected: an area probe over time")
    # Follow Select ▾: each pick moves it
    pp.editors[j][1].follow.setChecked(True)
    w.set_select_kind("mesh_node")
    el._take(("walls", 0), False)
    el.on_changed()
    check(pp.probe(j)["target"] == {"kind": "point", "how": "nodes", "nodes": [["walls", 0]]},
          "Follow Select ▾: the next pick moves the probe")
    # speed: a step shown with probes, from memory
    for s in range(4):
        w.anim_bar.set_index(s)
        pump()
    t0 = time.perf_counter()
    for _ in range(2):
        for s in range(4):
            w.anim_bar.set_index(s)
            app.processEvents()
    per = (time.perf_counter() - t0) / 8 * 1000
    check(per < 100, f"a step with three probes: {per:.1f} ms")
    w.remember_view()
    saved = (memory.load(case) or {}).get("probes") or []
    check([p["name"] for p in saved] == ["Probe 1", "Probe 2", "Probe 3"]
          and saved[0]["target"]["xyz"] == xyz, "the probes are remembered with the file")
    w.close()
    w = open_file(app, case)
    check(len(w.sidebar.probes_panel.editors) == 3 and len(w._probe_acts) == 3,
          "opened again: its probes and their tabs")
    w.close()


def _all(app, files):
    static(app, files)
    timed(app, files)


if __name__ == "__main__":
    run(_all)
