"""Parts list on the left, the inspector on the right: tabs, tools in view, per-file
memory, defaults, 'not available' notes, the toolbar and Customize Toolbar."""
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
                     "measure": ["info", "measure"],
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
    # remembered per file: the tab and the open tools
    sb.show_tab("view")
    w.remember_view()
    w.close()
    w = open_file(app, files["step"])
    check(w.sidebar.current_tab() == "view" and w.sidebar.is_open("edit"),
          f"remembered per file ({w.sidebar.current_tab()}, edit open {w.sidebar.is_open('edit')})")
    # toolbar: light, and Customize Toolbar…
    names = [a.text() for a in (w.a_sidebar, w.a_inspector)]
    check(names == ["Sidebar", "Inspector"], "Sidebar and Inspector buttons")
    check(not w._tb_items["settings"].isVisible() and w._tb_items["show"].isVisible()
          and w._tb_items["units"].isVisible(), "Settings off by default; Show ▾, units ▾")
    check(w.a_units_menu.text() in [a.data() for a in w.a_units],
          f"the unit in its pull-down: {w.a_units_menu.text()}")
    from meshviewer.gui.dialogs.toolbar import CustomizeToolbar
    d = CustomizeToolbar(w)
    d.changed.connect(w.apply_toolbar)
    d.boxes["screenshot"].setChecked(False)
    d.boxes["settings"].setChecked(True)
    check(not w._tb_items["screenshot"].isVisible() and w._tb_items["settings"].isVisible(),
          "Customize: Screenshot off, Settings on")
    d._defaults()
    check(w._tb_items["screenshot"].isVisible() and not w._tb_items["settings"].isVisible(),
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
