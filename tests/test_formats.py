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
    dxf_text_and_solids()
    # in the app: opens, the right sections, a distance on the drawing
    w = open_file(app, files["dxf"])
    sb = w.sidebar
    check(sb.current_tab() == "measure" and sb.is_active("info")
          and not sb.is_active("measure"),
          f"drawing opens on Measure ▸ Info, not measuring ({sb.current_tab()})")
    ins = sb.inspector
    check(not ins.tab_actions["view"].isEnabled() and not ins.tab_actions["analyze"].isEnabled()
          and ins.tab_actions["measure"].isEnabled(), "drawing: View and Analyze grayed")
    sb.show_tab("view")
    check(sb.current_tab() == "measure", "drawing: View can't be shown")
    check(not sb.isVisible() and not w.a_sidebar.isEnabled(), "drawing: no left sidebar")
    check(bool(sb._boxes["section"].parts[0][1].text()), "Section: not for 2D")
    # 2D: seen from +Z, never turned
    sc = w.scene
    cam = sc.p.camera
    check(abs(abs(cam.direction[2]) - 1) < 1e-9, f"drawing seen along Z {cam.direction}")
    check(not any(a.isVisible() for a in (*w.a_views, w.a_parallel))
          and not any(b.isVisible() for b in w.view_capsule.buttons[1:])
          and w.view_capsule.buttons[0].isVisible(), "2D: no Iso / X / Y / Z / Perspective")
    check(sc.state["parallel"], "2D: parallel projection")
    gone = ("mesh_edges", "feature_edges", "faces", "origin")
    check(not any(w.a_show[k].isVisible() for k in gone) and w.a_show["grid"].isVisible()
          and w.a_show["bbox"].isVisible() and w.a_show_menu.menu() is not None,
          "drawing: no edges / faces / origin buttons; Grid, Axes, Bounding Box")
    check(sc.state["bbox"] and w.a_show["bbox"].isChecked() and not sc.state["grid"]
          and not w.a_show["grid"].isChecked() and not w.a_show["axes"].isChecked(),
          "drawing: bounding box on, grid and axes off by default")
    w.a_show["grid"].trigger()                          # the drawing's own setting
    check(w.ctl.appearance["drawing_axes"] == "grid" and w.ctl.appearance["axes"] != "grid"
          and sc.state["grid"], "drawing: Grid on is kept for drawings only")
    w.a_show["grid"].trigger()
    sc.set_origin(True)
    check(not sc.state["origin"], "drawing: origin stays off")
    check(not sb.parts_section.isVisible(), "drawing: no layer list")
    import pyvista as pv
    sc.set_theme(False)                  # light first (the app follows the Mac, maybe dark)
    cols = {tuple(round(c, 3) for c in sc._attrs["surf"][sc._index[n]].color)
            for n in sc.names}
    sc.set_theme(True)
    cols_dark = {tuple(round(c, 3) for c in sc._attrs["surf"][sc._index[n]].color)
                 for n in sc.names}
    bg = tuple(round(c, 3) for c in sc.p.renderer.GetBackground())
    check({c[:3] for c in cols} == {(0, 0, 0)} and {c[:3] for c in cols_dark} == {(1, 1, 1)}
          and bg == (0, 0, 0),
          f"drawing: black lines (light), white lines on black (dark) {cols} {cols_dark} {bg}")
    bb = sc._bbox_actor                  # the bounding box: the lines' color
    white = bb.GetProperty().GetColor()
    sc.set_theme(False)
    black = bb.GetProperty().GetColor()
    sc.set_theme(True)
    check(white == (1.0, 1.0, 1.0) and black == (0.0, 0.0, 0.0) and not bb.GetPickable(),
          f"drawing: bounding box white in dark mode, black in light {white} {black}")
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
    e = sc._attrs["edges"]
    blk = sc._edges.GetMapper().GetInputDataObject(0, 0).GetBlock(sc._index["fluid"])
    check(sc.state["feature_edges"] and e[sc._index["fluid"]].visible and blk.GetNumberOfCells()
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
    # Section: ✎ Edit Plane, right of X | Y | Z, shows the origin and normal under Normal to
    check(sp.edit_plane.icon() is not None and not sp.edit_plane.isChecked()
          and sp.advanced.isHidden(), "Section: Edit Plane off at first")
    sp.edit_plane.setChecked(True)
    app.processEvents()
    lay = sp.details.layout().itemAt(1).layout()           # the Plane grid
    idx = lay.indexOf(sp.advanced)
    check(not sp.advanced.isHidden() and idx >= 0 and lay.getItemPosition(idx)[0] == 1,
          "Section: Edit Plane shows the origin and normal right under Normal to")
    w.close()

    # CGNS / UGRID: the summary counts the volume cells, from the file's header
    from meshviewer.core.mesh import cgns, ugrid
    n = cgns.cell_count(files["cgns"])
    check(n and n > 0, f"CGNS: {n} cells from the zone size")
    w = open_file(app, files["cgns"])
    check(w.sidebar.summary.endswith(f"{n:,} cells"), f"CGNS summary: {w.sidebar.summary}")
    w.close()
    check(ugrid.cell_count(files["ugrid"]) is not None, "UGRID: cells from the header")
    # STEP materials and colors (an assembly made in memory, as the reader sees it)
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
    from OCP.Quantity import Quantity_Color, Quantity_TOC_RGB
    from OCP.TCollection import TCollection_ExtendedString, TCollection_HAsciiString
    from OCP.TDocStd import TDocStd_Document
    from OCP.XCAFDoc import XCAFDoc_ColorType, XCAFDoc_DocumentTool
    from meshviewer.core.cad import occt
    doc = TDocStd_Document(TCollection_ExtendedString("MDTV-XCAF"))
    st = XCAFDoc_DocumentTool.ShapeTool_s(doc.Main())
    lab = st.AddShape(BRepPrimAPI_MakeBox(1, 2, 3).Shape(), False)
    mt = XCAFDoc_DocumentTool.MaterialTool_s(doc.Main())
    h = TCollection_HAsciiString
    mt.SetMaterial(lab, mt.AddMaterial(h("Aluminum 6061"), h("T6"), 2.7, h("g/cm3"),
                                       h("POSITIVE_RATIO_MEASURE")))
    XCAFDoc_DocumentTool.ColorTool_s(doc.Main()).SetColor(
        lab, Quantity_Color(1.0, 0.0, 0.0, Quantity_TOC_RGB), XCAFDoc_ColorType.XCAFDoc_ColorGen)
    mat = occt._label_material(lab)
    check(mat and mat["name"] == "Aluminum 6061" and abs(mat["density"] - 2.7) < 1e-9
          and mat["density_unit"] == "g/cm3", f"STEP material read ({mat})")
    check(occt._shape_color([None, lab]) == "#ff0000", "STEP color read")
    lab2 = st.AddShape(BRepPrimAPI_MakeBox(1, 1, 1).Shape(), False)
    check(occt._label_material(lab2) is None, "no material: None")



def _segments(poly):
    """Length of each line segment of a part."""
    seg = poly.lines.reshape(-1, 3)[:, 1:]
    return np.linalg.norm(np.diff(poly.points[seg], axis=1)[:, 0], axis=1)


def dxf_text_and_solids():
    """TEXT, MTEXT and dimensions as the letters' outlines; SOLID / TRACE / 3DFACE
    (arrowheads), also inside a block, as their closed outlines."""
    import tempfile
    from pathlib import Path
    import ezdxf
    from meshviewer.core.cad.dxf import read_dxf
    doc = ezdxf.new(setup=True)
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (100, 0), (100, 50), (0, 50)], close=True,
                       dxfattribs={"layer": "PROFILE"})
    msp.add_text("A-42", height=5, dxfattribs={"layer": "TEXT"}).set_placement((10, 10))
    msp.add_mtext("Note one\\PNote two", dxfattribs={"char_height": 3, "insert": (10, 40),
                                                     "layer": "NOTES"})
    msp.add_solid([(0, 0), (6, 0), (0, 8)], dxfattribs={"layer": "ARROWS"})   # 6-8-10
    msp.add_trace([(20, 0), (30, 0), (20, 2), (30, 2)], dxfattribs={"layer": "ARROWS"})
    blk = doc.blocks.new("TICK")
    blk.add_solid([(0, 0), (1, 0), (0, 1), (1, 1)])                  # layer 0: the INSERT's
    msp.add_blockref("TICK", (60, 20), dxfattribs={"layer": "BLOCKS"})
    dim = msp.add_linear_dim(base=(0, 60), p1=(0, 50), p2=(100, 50), dimstyle="EZDXF",
                             dxfattribs={"layer": "DIMS"})
    dim.render()
    path = Path(tempfile.mkdtemp()) / "text_solids.dxf"
    doc.saveas(str(path))
    parts, _info = read_dxf(path, debug=False)
    t = parts.get("TEXT")
    check(t is not None and t.n_lines > 40 and 9.5 < t.bounds[0] and t.bounds[1] < 40
          and 9 < t.bounds[2] and t.bounds[3] <= 15.1,
          f"DXF TEXT: its letters as line segments ({t.n_lines if t else 0}, "
          f"{t.bounds[:4] if t else None})")
    n = parts.get("NOTES")
    check(n is not None and n.n_lines > 40, f"DXF MTEXT: as line segments "
          f"({n.n_lines if n else 0})")
    a = parts.get("ARROWS")
    seg = np.sort(_segments(a)) if a is not None else []
    check(a is not None and a.n_lines == 3 + 4 and np.allclose(seg[-3:], [10, 10, 10])
          and np.isclose(seg.sum(), 6 + 8 + 10 + 2 * (10 + 2)),
          f"DXF SOLID (a 6-8-10 triangle) and TRACE (10 × 2) as closed outlines {seg}")
    b = parts.get("BLOCKS")
    check(b is not None and b.n_lines == 4 and np.isclose(_segments(b).sum(), 4)
          and np.allclose(b.bounds[:4], (60, 61, 20, 21)),
          "DXF: a SOLID inside a block, on the block's layer, where the block is")
    # a font that isn't installed (Onshape's Noto Sans): one that has the letters instead
    from meshviewer.core.cad.dxf import _covers, _mtext_parts, text_font
    doc.styles.add("NOTO", font="NotoSans-Regular.ttf")
    words = "UNLESS OTHERWISE SPECIFIED ±.01 30°"
    t = msp.add_text(words, height=2, dxfattribs={"style": "NOTO"})
    check(_covers(text_font(t, words).filename, words),
          f"DXF: a missing font -> one with every letter ({text_font(t, words).filename})")
    m = msp.add_mtext("\\A1;%%c2.150\\S+.000^ \\U+2212.010;")
    texts = [x.dxf.text for x in _mtext_parts(m, doc.blocks.new("*T"))]
    check("−.010" in texts and not any("U+" in x for x in texts),
          f"DXF MTEXT: \\U+2212 in a tolerance is a minus sign {texts}")
    d = parts.get("DIMS")
    check(d is not None and d.n_lines > 10 and d.bounds[3] > 59 and "Defpoints" not in parts,
          f"DXF DIMENSION: its lines, arrows and value, on its layer "
          f"({d.n_lines if d else 0}; {sorted(parts)})")


if __name__ == "__main__":
    run(test)
