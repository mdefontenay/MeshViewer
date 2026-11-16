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
                     "analyze": ["cfd", "cells", "results", "plots"]}, f"tabs {IN_TAB}")
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
    check(not sb.is_active("measure") and w.scene.measure.mode == "off"
          and not w.a_measure.isChecked(), "another tab: not measuring")
    w.a_tabs[1].trigger()                            # ⌥⌘2
    check(sb.current_tab() == "measure" and w.scene.measure.mode != "off", "⌥⌘2: measuring again")
    w.a_inspector.trigger()                          # ⌥⌘I: hidden
    check(ins.isHidden() and w.scene.measure.mode == "off", "inspector hidden: not measuring")
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
    rs = w.sidebar.results_section                       # Results: its switch in the title
    check(w.sidebar.results_panel.colour_on.parent() is not None and
          rs.header.isAncestorOf(w.sidebar.results_panel.colour_on),
          "Color the boundaries: the switch in the Results title")
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
    w.close()
    # mesh: CFD = y+ estimate, in Analyze
    w = open_file(app, files["cgns"])
    sb = w.sidebar
    check(sb.current_tab() == "view", "mesh opens on View")
    check(sb.cfd_section.isVisibleTo(sb._boxes["cfd"].widget)
          and not sb.inflation_section.isVisibleTo(sb._boxes["cfd"].widget), "CFD on a mesh = y+ estimate")
    sb.show_section("cfd", expand=True)
    check(sb.current_tab() == "analyze" and sb.is_active("cfd"), "CFD: the Analyze tab")
    w.close()
    # results file: Analyze, Results open
    w = open_file(app, files["tecplot"])
    check(w.sidebar.current_tab() == "analyze" and w.sidebar.is_open("results"),
          "results file opens on Results")
    w.close()
    from meshviewer.core.fields import solution_fields
    w = open_file(app, files["step"])
    check(solution_fields(w.scene.model.parts) == [], "STEP: no solution fields")
    w.close()
    # an empty window: no parts list, no inspector
    w = app.new_window()
    w.show()
    app.processEvents()
    check(not w.sidebar.isVisible() and not w.sidebar.inspector.isVisible()
          and not w.a_inspector.isEnabled(), "empty window: the welcome only")
    w.close()


if __name__ == "__main__":
    run(test)
