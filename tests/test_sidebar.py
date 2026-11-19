"""Parts list on the left, the inspector on the right: tabs, tools in view, per-file
memory, defaults, 'not available' notes, the toolbar and Customize Toolbar."""
from PySide6.QtCore import Qt

from conftest import check, open_file, run

from meshviewer.gui.sections import IN_TAB


def test(app, files):
    # CAD (STEP): the View tab, nothing open; Edit says why it is unavailable
    w = open_file(app, files["step"])
    sb, ins = w.sidebar, w.sidebar.inspector
    check(w.splitter.widget(0) is sb and w.splitter.widget(2) is ins,
          "parts list left, inspector right")
    check(sb.current_tab() == "view" and not any(sb.is_open(k) for k in sb._boxes),
          f"CAD opens on View, tools closed ({sb.current_tab()})")
    check(IN_TAB == {"view": ["quality", "section", "edit"],
                     "measure": ["info", "measure", "selected"],
                     "analyze": ["cfd", "cells", "contours", "plots", "probes"]}, f"tabs {IN_TAB}")
    firsts = {tab: keys[0] for tab, keys in IN_TAB.items()}    # no line above the first tool
    check(all(sb._boxes[k].divider.isHidden() == (k in firsts.values())
              for keys in IN_TAB.values() for k in keys),
          "a line between tools, none above Meshing Control, Info, CFD")
    for tab, keys in IN_TAB.items():                 # each tool in its tab's page
        page = ins.pages[tab][2]
        check(all(page.isAncestorOf(sb._boxes[k].widget) for k in keys), f"{tab} page")
    edit_note = sb._boxes["edit"].parts[0][1]
    check(bool(edit_note.text()), "STEP: Edit says why it's unavailable")
    sb.edit_section.set_expanded(True)
    app.processEvents()
    check(edit_note.isVisible() and not sb.edit_panel.isVisible(), "Edit open: note, no controls")
    check(sb.inflation_section.isVisibleTo(sb._boxes["cfd"].widget)
          and not sb.cfd_section.isVisibleTo(sb._boxes["cfd"].widget), "CFD on CAD = Inflation Layers")
    # Measure: works while in view (open, its tab shown, the inspector shown)
    sb.show_section("measure", expand=True)
    check(sb.current_tab() == "measure" and sb.is_active("measure")
          and w.scene.measure.mode != "off" and w.a_measure.isChecked(),
          "Measure tab, Measure open: measuring, View ▸ Measure on")
    sb.show_tab("view")
    check(not sb.is_active("measure") and w.scene.measure.picking == "off"
          and not w.a_measure.isChecked(), "another tab: not measuring (its marks stay)")
    w.a_tabs[1].trigger()                            # ⌥⌘2
    check(sb.current_tab() == "measure" and w.scene.measure.mode != "off", "⌥⌘2: measuring again")
    w.a_inspector.trigger()                          # ⌥⌘I: hidden
    check(ins.isHidden() and w.scene.measure.picking == "off", "inspector hidden: not measuring")
    w.a_measure.trigger()                            # ⇧⌘M shows it again
    check(not ins.isHidden() and w.a_inspector.isChecked() and sb.is_active("measure"),
          "View ▸ Measure: inspector back, measuring")
    w.a_measure.trigger()
    check(not sb.measure_section.expanded and not w.a_measure.isChecked(), "View ▸ Measure off")
    check(not ins.pages["view"][0].verticalScrollBar().isVisible()
          or ins.pages["view"][0].height() < ins.pages["view"][0].content_height(),
          "no scrollbar when it fits")
    # the parts list: the whole height of the left column
    check(sb.list.height() > 0.5 * sb.height(), f"parts list {sb.list.height()} of {sb.height()}")
    ps = sb.parts_section                               # always open: no chevron, no fold
    ps.header.clicked.emit()
    ps.set_expanded(False)
    check(ps.expanded and sb.list.isVisible() and ps.chevron.isHidden(),
          "the parts list can't be folded")
    # STEP: the summary counts parts; the file's assemblies and colors; sort; limits
    check(sb.info.text().endswith("1 part") or "part" in sb.summary,
          f"STEP summary: parts ({sb.summary})")
    sc = w.scene
    name = sc.names[0]
    sc.model.part_info[name] = {"path": ("Top", "Sub"), "color": "#123456", "material": None}
    sb.refresh_parts()
    top = sb.list.topLevelItem(0)
    check(top.text(0).startswith("Top") and top.child(0).text(0).startswith("Sub")
          and top.child(0).child(0).data(0, Qt.UserRole) == name,
          "the file's assemblies: Top ▸ Sub ▸ the part")
    sc.model.part_info.clear()
    sb.refresh_parts()
    from meshviewer.core import part_filter
    check(part_filter.parse("bolt size >= 2.5 vol<10") ==
          ("bolt", [("size", ">=", 2.5), ("volume", "<", 10.0)]), "filter: name and limits")
    check(part_filter.passes({"size": 3, "volume": None}, [("size", ">", 2)])
          and not part_filter.passes({"size": 3, "volume": None}, [("volume", ">", 0)]),
          "filter: no volume never passes a volume limit")
    big = sc.part_size(name) * sc.measure.unit_scale()[0]
    sb.filter.setText(f"size > {big * 2:g}")
    check(sb.list._parts[name].isHidden(), "size limit hides a smaller part")
    sb.filter.setText(f"size < {big * 2:g}")
    check(not sb.list._parts[name].isHidden(), "…and shows it under a larger one")
    v = sc.part_volume(name)
    check(v is not None and v > 0, f"the STEP box's volume ({v})")
    sb.filter.setText("")
    sb.set_sort("volume")
    check(sb.list.sort_by == "volume" and sb.sort_actions["volume"].isChecked(), "Sort ▸ Volume")
    sb.set_sort("name")
    from meshviewer.gui.sidebar_menu import material_text
    check(material_text(None)[0] == "No material metadata embedded"
          and material_text({"name": "Steel", "density": 7.85, "density_unit": "g/cm3"})
          == ("Steel", "Density: 7.85 g/cm3"), "Material… text")
    check(w.ctl.prefs["cad_quality"] == 2, "CAD meshing control: Medium by default")
    # the meshing level is remembered per file
    from conftest import wait
    w._retessellate(0)
    wait(app, lambda: w.scene.model.quality == 0)
    path = w.path
    w.remember_view()
    w.close()
    w = open_file(app, path)
    sb, sc = w.sidebar, w.scene
    check(sc.model.quality == 0, f"meshing level kept for the file ({sc.model.quality})")
    w._retessellate(2)
    wait(app, lambda: w.scene.model.quality == 2)
    sc = w.scene
    check(sb.measure_section.title_label.text() == "Measuring Tool"
          and sb.selected_section.title_label.text() == "Measure Selected"
          and sb.options_button.objectName() == "FilterButton",
          "Measuring Tool, Measure Selected; the rounded filter button")
    # renaming a group: its parts (one undo step); an assembly: its row
    from meshviewer.gui.panels.parts import KIND
    old = sc.names[0]
    sc.model.part_info[old] = {"path": ("Top",), "color": None, "material": None}
    sb.refresh_parts()
    top = sb.list.topLevelItem(0)
    check(top.data(0, KIND) == "assembly" and bool(top.flags() & Qt.ItemIsEditable),
          "an assembly row can be renamed")
    sb._rename_group("assembly", "Top", "Frame", [old])
    check(sb.list.topLevelItem(0).text(0).startswith("Frame")
          and w.a_undo.text() == "Undo Rename Top", "assembly renamed in the list")
    w.a_undo.trigger()
    check(sb.list.topLevelItem(0).text(0).startswith("Top"), "undo: Top again")
    sc.model.part_info.clear()
    sb._rename_group("group", old, "Mount", [old])          # (one part: the same way)
    check("Mount" in sc.model.parts and w.a_undo.text() == f"Undo Rename {old}",
          "a group renamed: its parts")
    w.a_undo.trigger()
    check(old in sc.model.parts, "undo: the old name back")
    sb.refresh_parts()
    # the filter menu: colors, McMaster, a compact tree; the part menu's groups
    check(sb.options_button.menu() is not None and sb.list.indentation() == 13,
          "filter options button; tree indented 13 px (was 20)")
    sc.model.part_info[name] = {"path": (), "color": "#123456", "material": None}
    sb.set_color_mode("random")                         # (as opened: the palette)
    sb.set_color_mode("file")
    check(sc.colors[name] == "#123456", f"File Color: the file's ({sc.colors[name]})")
    sb.set_color_mode("random")
    check(sc.colors[name] == sc._palette[name], "Randomized Color: the palette's")
    sc.set_color([name], "#abcdef")
    sb.set_color_mode("file")
    check(sc.colors[name] == "#abcdef", "a color you chose stays")
    sc.model.part_info.clear()
    sc.set_color_mode("random", render=False)
    sc.set_color_mode("file", render=False)
    sc.set_color([name], sc.default_colors[name])
    old = sc.names[0]
    sc.rename_part(old, "91251A540 Screw")
    sb.refresh_parts()
    tops = [sb.list.topLevelItem(i).text(0) for i in range(sb.list.topLevelItemCount())]
    check(not any(t.startswith("McMaster") for t in tops), "McMaster Parts: none by default")
    sb.mcmaster_action.setChecked(True)
    top = sb.list.topLevelItem(0)
    check(top.text(0).startswith("McMaster Parts"), "Isolate McMaster Parts: on top")
    sb.filter.setText("size > 1e9")
    check(not sb.list._parts["91251A540 Screw"].isHidden(), "…shown whatever the size limit")
    sb.filter.setText("")
    sb.mcmaster_action.setChecked(False)
    sc.rename_part("91251A540 Screw", old)
    sb.refresh_parts()
    from meshviewer.gui.widgets import Menu
    shown = []
    orig_exec = Menu.exec
    Menu.exec = lambda m, *_a: shown.append([a.text() or "—" for a in m.actions()])
    try:
        sb.part_menu([old], [old], None)
    finally:
        Menu.exec = orig_exec
    items = shown[0] if shown else []
    i = items.index("Rename…") if "Rename…" in items else -1
    check(i > 0 and items[i - 1] == "—" and items[i + 1] == "Color…"
          and items[i + 2] == "Material…" and items[i + 3] == "—",
          f"part menu: Rename…, Color…, Material… between lines ({items})")
    sc = w.scene                                        # the XYZ arrows stay in their corner
    sc.set_axis_font(10)
    vp10 = sc._axes_viewport()
    sc.set_axis_font(28)
    check(sc._axes_viewport() == vp10, "bigger axis labels: the XYZ arrows don't move")
    sc.set_axis_font(10)
    # remembered per file: the tab and the open tools
    sb.show_tab("view")
    w.remember_view()
    w.close()
    w = open_file(app, files["step"])
    check(w.sidebar.current_tab() == "view" and w.sidebar.is_open("edit"),
          f"remembered per file ({w.sidebar.current_tab()}, edit open {w.sidebar.is_open('edit')})")
    # toolbar: light, and Customize Toolbar…
    names = [a.text() for a in (w.a_sidebar, w.a_inspector)]
    check(names == ["Left Sidebar", "Right Sidebar"], "Left Sidebar and Right Sidebar buttons")
    pill = w._tb_items["export"].defaultWidget() if hasattr(w._tb_items["export"],
                                                            "defaultWidget") else None
    from meshviewer.gui.widgets import Capsule
    caps = [c for c in w.toolbar.findChildren(Capsule)]
    acts = [[b.defaultAction() for b in c.buttons] for c in caps]
    check([w.a_export, w.a_shot] in acts, "Export and Screenshot: one pill")
    check([w.a_undo_tb, w.a_redo_tb] in acts and w._tb_items["undo"].isVisible(),
          "Undo and Redo in the toolbar")
    check(w.a_rotate_left in [b.defaultAction() for b in w.view_capsule.buttons]
          and w.a_rotate_left.isVisible(), "Rotate Camera 90° Left in the views' pill")
    check(w.toolbar.isVisible() and w.a_toolbar.text() == "Hide Toolbar", "the toolbar shown")
    w.a_toolbar.trigger()
    check(not w.toolbar.isVisible() and w.a_toolbar.text() == "Show Toolbar", "Hide Toolbar")
    w.a_toolbar.trigger()
    check(w.toolbar.isVisible(), "Show Toolbar")
    # Show ▾ Axis Indicator: the XYZ arrows in the corner, on by default, every window
    ai = w.a_show["axis_indicator"]
    show_menu = w.a_show_menu.menu().actions()
    view_show = next(a.menu() for a in w.menuBar().actions()[2].menu().actions()
                     if a.menu() is not None and a.text() == "Show")
    check(ai in show_menu and ai in view_show.actions() and ai.isCheckable()
          and ai.isChecked() and ai.text() == "Axis Indicator" and not ai.icon().isNull(),
          "Axis Indicator in Show ▾ and View ▸ Show, on by default")
    widget = lambda win: win.scene.p.renderer.axes_widget          # noqa: E731
    check(w.scene.state["axis_indicator"] and widget(w).GetEnabled(), "the XYZ arrows shown")
    ai.trigger()
    check(not w.scene.state["axis_indicator"] and not widget(w).GetEnabled()
          and w.ctl.appearance["axis_indicator"] is False, "Axis Indicator off: hidden")
    from meshviewer.gui.store import settings
    check(settings().value("appearance/axis_indicator", True, type=bool) is False,
          "remembered")
    w.scene.set_theme(w.scene._ui_dark)                 # (the axes are rebuilt with the theme)
    check(not widget(w).GetEnabled(), "stays off when the theme rebuilds the view")
    w2 = open_file(app, files["tecplot"])
    check(w2.sidebar.current_tab() == "analyze" and w2.sidebar.is_open("contours"),
          "results file opens on Contours")
    check(not w2.a_show["axis_indicator"].isChecked()
          and not w2.scene.state["axis_indicator"], "another window: off too")
    # the color bar dragged with the mouse (gui/viewport.py)
    from PySide6.QtCore import QEvent, QPointF
    from PySide6.QtGui import QMouseEvent
    sc2, rp2 = w2.scene, w2.sidebar.contours_panel
    w2._show_page("contour:1")                      # the bar: in a contour's tab
    app.processEvents()
    sc2.p.render_now()
    bar = sc2.colorbar
    vp = sc2.p
    r = float(vp.devicePixelRatioF())
    ax, ay = bar._anchor.GetComputedDoubleDisplayValue(sc2.p.renderer)[:2]
    at = QPointF((ax + 4) / r, vp.height() - (ay - 40) / r - 1)      # on the bar, in points
    start = tuple(bar.offset)
    cam = sc2.camera_snapshot()

    def mouse(kind, pos, buttons):
        ev = QMouseEvent(kind, pos, vp.mapToGlobal(pos), Qt.LeftButton, buttons,
                         Qt.NoModifier)
        app.sendEvent(vp, ev)

    mouse(QEvent.MouseButtonPress, at, Qt.LeftButton)
    mouse(QEvent.MouseMove, at + QPointF(30, 20), Qt.LeftButton)
    mouse(QEvent.MouseButtonRelease, at + QPointF(30, 20), Qt.NoButton)
    app.processEvents()
    check(abs(bar.offset[0] - start[0] - 30) < 0.6 and abs(bar.offset[1] - start[1] - 20) < 0.6
          and sc2.same_camera(cam, sc2.camera_snapshot()),
          f"the color bar dragged by the mouse {start} -> {bar.offset}, the camera still")
    check(rp2.current["bar"]["pos"] == [round(bar.offset[0], 1), round(bar.offset[1], 1)]
          and rp2.settings()["contours"][0]["bar"]["pos"] == rp2.current["bar"]["pos"],
          "its new place saved with the file (its contour's)")
    w2.close()
    ai.trigger()
    check(w.scene.state["axis_indicator"] and widget(w).GetEnabled(), "Axis Indicator on again")
    rs = w.sidebar.contours_section                      # Contours: no switch in its title
    from meshviewer.gui.widgets import Switch
    check(rs.header.findChild(Switch) is None and rs.title_label.text() == "Contours",
          "Contours: no Color the boundaries switch in its title")
    check(not w._tb_items["settings"].isVisible() and w._tb_items["show"].isVisible()
          and w._tb_items["units"].isVisible(), "Settings off by default; Show ▾, units ▾")
    check(w.a_units_menu.text() in [a.data() for a in w.a_units],
          f"the unit in its pull-down: {w.a_units_menu.text()}")
    from meshviewer.gui.dialogs.toolbar import CustomizeToolbar
    d = CustomizeToolbar(w)
    d.changed.connect(w.apply_toolbar)
    d.boxes["export"].setChecked(False)
    d.boxes["settings"].setChecked(True)
    check(not w._tb_items["export"].isVisible() and w._tb_items["settings"].isVisible(),
          "Customize: Export · Screenshot off, Settings on")
    d._defaults()
    check(w._tb_items["export"].isVisible() and not w._tb_items["settings"].isVisible(),
          "Restore Defaults")
    d.close()
    check(w.createPopupMenu().actions()[0] is w.a_customize, "right-click: Customize Toolbar…")
    from meshviewer.core.fields import solution_fields
    check(solution_fields(w.scene.model.parts) == [], "STEP: no solution fields")
    w.close()
    # mesh: CFD = y+ estimate, in Analyze; the summary counts the volume cells, from the
    # file's header
    from meshviewer.core.mesh import cgns
    n = cgns.cell_count(files["cgns"])
    check(n and n > 0, f"CGNS: {n} cells from the zone size")
    w = open_file(app, files["cgns"])
    sb = w.sidebar
    check(sb.summary.endswith(f"{n:,} cells"), f"CGNS summary: {sb.summary}")
    check(sb.current_tab() == "view", "mesh opens on View")
    check(sb.cfd_section.isVisibleTo(sb._boxes["cfd"].widget)
          and not sb.inflation_section.isVisibleTo(sb._boxes["cfd"].widget), "CFD on a mesh = y+ estimate")
    sb.show_section("cfd", expand=True)
    check(sb.current_tab() == "analyze" and sb.is_active("cfd"), "CFD: the Analyze tab")
    w.close()
    # an empty window: no parts list, no inspector
    w = app.new_window()
    w.show()
    app.processEvents()
    check(not w.sidebar.isVisible() and not w.sidebar.inspector.isVisible()
          and not w.a_inspector.isEnabled(), "empty window: the welcome only")
    w.close()


def measure_checks(app, files):
    """What the Measuring Tool measured stays drawn when another tool or tab is shown;
    meanwhile a click picks parts; back in the tool, measuring goes on."""
    import numpy as np
    w = open_file(app, files["step"])
    sc, sb = w.scene, w.sidebar
    sb.show_section("measure", expand=True)
    for _ in range(5):
        app.processEvents()
    m = sc.measure
    check(m.mode == "distance" and m.picking == "distance", "Measuring Tool: distance")
    b = np.asarray(sc.model_bounds(), dtype=float).reshape(3, 2)
    m.add_point(b[:, 0])
    m.add_point(b[:, 1])
    n = len(m._marker_actors)
    check(len(m.points) == 2 and n > 0, f"two points, their marks ({n})")
    sb.show_tab("view")                                 # another tab of tools
    for _ in range(5):
        app.processEvents()
    check(len(m.points) == 2 and len(m._marker_actors) == n and m.picking == "off"
          and m.paused, "another tab: the marks stay, clicks pick parts")
    sb.show_tab("measure")
    for _ in range(5):
        app.processEvents()
    check(len(m.points) == 2 and m.picking == "distance" and not m.paused,
          "back to the Measuring Tool: the same points, measuring again")
    sb.show_section("measure", False)                   # the tool folded
    for _ in range(5):
        app.processEvents()
    check(len(m._marker_actors) == n and m.paused, "the tool folded: the marks stay")
    w.close()


def scroll_checks(app, files):
    """The right sidebar scrolling: its scrollbar floats over the margin, the cards keep
    their width (no gutter)."""
    w = open_file(app, files["tecplot"], size=(1400, 520))
    sb = w.sidebar
    sb.show_tab("analyze")
    sb.show_section("contours", expand=True)
    ed = sb.contours_panel.editors[1]
    ed[0].set_expanded(True)
    ed[1].bar_section.set_expanded(True)
    sb.show_section("plots", expand=True)
    for _ in range(20):
        app.processEvents()
    scroll = sb.inspector.pages["analyze"][0]
    card = sb._boxes["contours"].widget
    right = lambda: card.mapTo(scroll, card.rect().topRight()).x()   # noqa: E731
    check(scroll.verticalScrollBarPolicy() == Qt.ScrollBarAlwaysOff
          and scroll.overlay.isVisible() and scroll.viewport().width() == scroll.width(),
          "too tall: an overlay scrollbar, the page keeps its width")
    bar = scroll.overlay.geometry()
    check(bar.right() == scroll.viewport().geometry().right() and bar.left() > right(),
          "the scrollbar in the right margin, clear of the cards")
    edge = right()
    ed[0].set_expanded(False)                          # short enough now
    sb.show_section("plots", False)
    for _ in range(20):
        app.processEvents()
    check(not scroll.overlay.isVisible() and right() == edge,
          f"tall enough: no scrollbar, the cards' right edge where it was ({edge} -> "
          f"{right()}, bar {scroll.overlay.isVisible()}, {scroll.height()} / "
          f"{scroll.content_height()})")
    ed[0].set_expanded(True)
    for _ in range(20):
        app.processEvents()
    v = scroll.verticalScrollBar()
    scroll.overlay.setValue(scroll.overlay.maximum())
    check(v.value() == v.maximum() > 0, "the overlay scrolls the page")
    w.close()


def _all(app, files):
    test(app, files)
    measure_checks(app, files)
    scroll_checks(app, files)


if __name__ == "__main__":
    run(_all)
