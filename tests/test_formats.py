"""F11 / F12: .msh (Gmsh, Fluent; 2D and 3D) and DXF drawings."""
import numpy as np

from conftest import check, open_file, run, wait


def test(app, files):
    from meshviewer.core import formats
    want = {"gmsh3d": ("Gmsh", "mesh", {"wall", "farfield"}, 384),
            "fluent3d": ("Fluent", "mesh", {"wall", "farfield"}, 64),
            "fluent3d_bin": ("Fluent", "mesh", {"wall", "farfield"}, 64),
            "gmsh2d": ("Gmsh", "mesh2d", {"domain", "wall", "farfield"}, None),
            "fluent2d": ("Fluent", "mesh2d", {"fluid", "wall", "farfield"}, None),
            "dxf": ("DXF", "drawing", {"PROFILE", "HOLES"}, None)}
    for key, (fmt, ftype, names, cells) in want.items():
        m = formats.load(files[key], debug=False)
        vol = m.volume() if m.volume else None
        check(m.fmt == fmt and m.file_type == ftype and set(m.parts) == names
              and (vol.n_cells if vol is not None else None) == cells,
              f"{key}: {m.fmt} {m.file_type} {sorted(m.parts)} volume {vol.n_cells if vol is not None else None}")
    m = formats.load(files["fluent2d"], debug=False)
    check(m.parts["fluid"].n_cells == 72 and np.allclose(m.parts["fluid"].points[:, 2], 0),
          "Fluent 2D: 72 quads, flat")
    check(m.parts["wall"].n_lines == 12, "Fluent 2D: the wall as 12 edges")
    m = formats.load(files["dxf"], debug=False)
    L = sum(np.linalg.norm(np.diff(p.points[p.lines.reshape(-1, 3)[:, 1:]], axis=1)[:, 0], axis=1).sum()
            for p in m.parts.values())
    exact = 120 + 2 * np.pi * 4 + np.pi * 5 + 10
    check(abs(L - exact) / exact < 1e-3, f"DXF: total length {L:.3f} (exact {exact:.3f})")
    # in the app: opens, the right sections, a distance on the drawing
    w = open_file(app, files["dxf"])
    sb = w.sidebar
    check(sb.shown_sections() == ["measure"], f"drawing opens on Measure {sb.shown_sections()}")
    check(bool(sb._boxes["section"].parts[0][1].text()), "Section: not for 2D")
    # 2D: seen from +Z, never turned
    sc = w.scene
    cam = sc.p.camera
    check(abs(abs(cam.direction[2]) - 1) < 1e-9, f"drawing seen along Z {cam.direction}")
    check(not any(a.isVisible() for a in (*w.a_views, w.a_parallel))
          and not any(b.isVisible() for b in w.view_capsule.buttons[1:])
          and w.view_capsule.buttons[0].isVisible(), "2D: no Iso / X / Y / Z / Perspective")
    check(sc.state["parallel"], "2D: parallel projection")
    gone = ("mesh_edges", "feature_edges", "faces", "bbox", "origin")
    check(not any(w.a_show[k].isVisible() for k in gone) and w.a_show["grid"].isVisible()
          and not w._tb_slot[w.edges_capsule].isVisible(),
          "drawing: no edges / faces / bounding box / origin buttons")
    sc.set_bbox(True)
    sc.set_origin(True)
    check(not sc.state["bbox"] and not sc.state["origin"], "drawing: bbox, origin stay off")
    check(not sb.parts_section.isVisible(), "drawing: no layer list")
    import pyvista as pv
    cols = {tuple(round(c, 3) for c in sc._surf_map.block_attr[sc._block(n)].color)
            for n in sc.names}
    sc.set_theme(True)
    cols_dark = {tuple(round(c, 3) for c in sc._surf_map.block_attr[sc._block(n)].color)
                 for n in sc.names}
    bg = tuple(round(c, 3) for c in sc.p.renderer.GetBackground())
    check({c[:3] for c in cols} == {(0, 0, 0)} and {c[:3] for c in cols_dark} == {(1, 1, 1)}
          and bg == (0, 0, 0),
          f"drawing: black lines (light), white lines on black (dark) {cols} {cols_dark} {bg}")
    sc.set_theme(False)
    sc.p.camera.Azimuth(30)
    sc.p.camera.Elevation(20)
    from meshviewer.gui import memory
    memory.restore_camera(sc, {"camera": [list(map(float, v)) for v in sc.p.camera_position]})
    check(abs(abs(cam.direction[2]) - 1) < 1e-9 and abs(cam.up[1] - 1) < 1e-9,
          "an angled saved view comes back square to Z")
    sc.view("x")
    check(abs(abs(cam.direction[2]) - 1) < 1e-9, "view('x') stays along Z")
    sc.end_stuck_drag = lambda: None                   # no real mouse button here
    f0 = cam.focal_point
    iren = sc.p.iren.interactor
    W, H = sc.p.window_size
    cx, cy = W // 2, H // 2
    iren.SetEventInformation(cx, cy, 0, 0)
    iren.InvokeEvent("LeftButtonPressEvent")
    for k in range(1, 6):
        iren.SetEventInformation(cx + 30 * k, cy + 20 * k, 0, 0)
        iren.InvokeEvent("MouseMoveEvent")
    iren.InvokeEvent("LeftButtonReleaseEvent")
    check(abs(abs(cam.direction[2]) - 1) < 1e-9 and cam.focal_point != f0,
          f"left drag pans, no turn {cam.direction}")
    iren.InvokeEvent("StartRotateEvent")
    iren.InvokeEvent("RotateEvent")
    iren.InvokeEvent("EndRotateEvent")
    check(abs(abs(cam.direction[2]) - 1) < 1e-9, "trackpad rotate ignored")
    ep = sb.edit_panel
    ep.kind.setCurrentIndex(ep.kind.findData("rotate"))
    check(ep._axis_key() == "z" and not ep.axis["x"].isEnabled(), "2D Edit: rotate about Z only")
    ep.kind.setCurrentIndex(ep.kind.findData("mirror"))
    check(ep._axis_key() in "xy" and not ep.axis["z"].isEnabled(), "2D Edit: mirror X or Y")
    w.close()
    # 2D mesh: right-click menu, and Feature edges show the zones' outline
    w = open_file(app, files["fluent2d"])
    sc, sb = w.scene, w.sidebar
    got = []
    sc.on_context = lambda names, clicked: got.append(names)
    iren = sc.p.iren.interactor
    W, H = sc.p.window_size
    iren.SetEventInformation(W // 2, H // 2, 0, 0)
    iren.InvokeEvent("RightButtonPressEvent")
    iren.InvokeEvent("RightButtonReleaseEvent")
    check(got == [["fluid"]], f"2D: right-click menu on the zone {got}")
    # two kinds of rows: Faces (areas) and Boundaries (lines); menu words to match
    tops = [sb.list.topLevelItem(i) for i in range(sb.list.topLevelItemCount())]
    check([t.text(0).split()[0] for t in tops] == ["Faces", "Boundaries"]
          and sorted(tops[1].data(0, 0x0101)) == ["farfield", "wall"],
          f"2D list: Faces / Boundaries {[t.text(0) for t in tops]}")
    check(sb._menu_word(["fluid"]) == " Face" and sb._menu_word(["wall"]) == " Boundary"
          and sb._menu_word(["wall", "farfield"]) == " 2 Boundaries",
          "menu: Hide Face / Hide Boundary")
    check(not sc.hide_edges_moving, "2D: lines stay while moving")
    sc.set_edge_options(hide_while_moving=True)
    check(not sc.hide_edges_moving, "2D: even with the Appearance setting on")
    ax = sc.p.renderer.axes_actor
    check(ax.GetZAxisShaftProperty().GetOpacity() == 0 and ax.GetZAxisLabelText() == "",
          "2D: no Z arrow in the corner")
    # angle: two lines, in XY
    m = sc.measure
    m.set_mode("angle")
    wall, far = sc.model.parts["wall"], sc.model.parts["farfield"]
    c0 = wall.get_cell(0).points.mean(axis=0)
    m.add_face(c0, "wall", 0)
    j = next(i for i in range(far.n_cells)
             if abs(np.ptp(np.asarray(far.get_cell(i).points)[:, 0])) < 1e-9)   # a vertical one
    m.add_face(np.asarray(far.get_cell(j).points).mean(axis=0), "farfield", j)
    r = m.result()
    check(r.get("lines") and abs(r["planes"] - 90) < 1e-6 and all(abs(n[2]) < 1e-12
          for n in m.normals), f"2D angle: wall ⟂ side = {r.get('planes')}°, in XY")
    m.set_mode("off")
    w.a_show["feature_edges"].trigger()
    sb._visibility_changed(["wall"], False)
    e = sc._edges_map.block_attr
    blk = sc._edges.GetMapper().GetInputDataObject(0, 0).GetBlock(sc._block("fluid") - 1)
    check(sc.state["feature_edges"] and e[sc._block("fluid")].visible and blk.GetNumberOfCells()
          and sc._edges.GetProperty().GetLineWidth() >= 2.5,
          "2D: Feature edges = the zone outline (shows the hidden wall)")
    w.close()
    w = open_file(app, files["fluent3d"])
    sp = w.sidebar.section_panel
    sp.enable.setChecked(True)
    sp.fill.setChecked(True)
    w.scene.section.set_plane(origin=(0.5, 0.5, 0.5), normal=(1, 0, 0))
    wait(app, lambda: w.scene.section._volume is not None, 30)
    app.processEvents()
    check(w.scene.section._vol_cut is not None, "Fluent 3D: cut cells on the section")
    w.close()


if __name__ == "__main__":
    run(test)
