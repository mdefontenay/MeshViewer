"""Sidebar: icon bar toggles, per-file memory, defaults, 'not available' notes, fit."""
from conftest import check, open_file, run


def test(app, files):
    # CAD (STEP): defaults Mesh quality, Section, Measure; Edit / Cells / Results greyed
    w = open_file(app, files["step"])
    sb = w.sidebar
    check(sb.shown_sections() == ["quality", "section", "measure"], f"CAD defaults {sb.shown_sections()}")
    edit_note = sb._boxes["edit"].parts[0][1]
    check(bool(edit_note.text()), "STEP: Edit says why it's unavailable")
    sb.section_actions["edit"].setChecked(True)
    check(not sb.edit_section.expanded, "a section shown from its icon starts closed")
    sb.edit_section.set_expanded(True)
    app.processEvents()
    check(edit_note.isVisible() and not sb.edit_panel.isVisible(), "Edit shown: note, no controls")
    check(sb.inflation_section.isVisibleTo(sb._boxes["cfd"].widget) and not sb.cfd_section.isVisibleTo(sb._boxes["cfd"].widget),
          "CFD on CAD = CFD mode")
    check(not sb.tools.verticalScrollBar().isVisible() or
          sb.tools.height() < sb.tools.content_height(), "no scrollbar when it fits")
    # Section icon off -> plane off; on again -> plane back
    sp = sb.section_panel
    sp.enable.setChecked(True)
    sb.section_actions["section"].setChecked(False)
    check(not w.scene.section.enabled, "hiding Section switches the plane off")
    sb.section_actions["section"].setChecked(True)
    check(w.scene.section.enabled and not sb.section_section.expanded,
          "showing it again: plane back on, section closed")
    # CFD icon off -> CFD mode off; on again -> back on
    sb.show_section("cfd")
    sb.inflation_panel.enable.setChecked(True)
    sb.section_actions["cfd"].setChecked(False)
    check(not sb.inflation_panel.enable.isChecked(), "hiding CFD switches CFD mode off")
    sb.section_actions["cfd"].setChecked(True)
    check(sb.inflation_panel.enable.isChecked(), "showing CFD again: CFD mode back on")
    sb.inflation_panel.enable.setChecked(False)
    sb.section_actions["cfd"].setChecked(False)
    # the parts list can be dragged down to a small height
    total = sum(sb.split.sizes())
    sb.split.setSizes([total - 120, 120])
    app.processEvents()
    check(sb.split.sizes()[1] <= 0.19 * total, f"parts list down to {sb.split.sizes()[1]} of {total} px")
    # Analysis Tools: an icon left out of the bar
    sb.show_section("results")
    sb.icon_actions["results"].setChecked(False)
    check(not sb._icon_buttons["results"].isVisible() and "results" not in sb.shown_sections(),
          "Results icon hidden (and its section)")
    sb.icon_actions["results"].setChecked(True)
    check(sb._icon_buttons["results"].isVisible() and "results" not in sb.shown_sections(),
          "icon back, section still off")
    # parts list closed: header at the bottom
    sb.parts_section.set_expanded(False)
    app.processEvents()
    bottom = sb.parts_section.mapTo(sb, sb.parts_section.rect().bottomLeft()).y()
    check(bottom > sb.height() - 80, f"closed parts list sits at the bottom ({bottom} of {sb.height()})")
    sb.parts_section.set_expanded(True)
    w.remember_view()
    w.close()
    # same file again: what was on comes back
    w = open_file(app, files["step"])
    check(w.sidebar.shown_sections() == ["quality", "section", "edit", "measure"],
          f"remembered per file {w.sidebar.shown_sections()}")
    w.close()
    # mesh: defaults Section, Edit, Measure; CFD = y+ estimate
    w = open_file(app, files["cgns"])
    sb = w.sidebar
    check(sb.shown_sections() == ["section", "edit", "measure"], f"mesh defaults {sb.shown_sections()}")
    check(sb.cfd_section.isVisibleTo(sb._boxes["cfd"].widget) and not sb.inflation_section.isVisibleTo(sb._boxes["cfd"].widget),
          "CFD on a mesh = y+ estimate")
    sb.set_measuring(False)
    sb.section_actions["measure"].setChecked(False)
    check(not sb.measure_section.expanded, "hiding Measure stops measuring")
    sb.set_measuring(True)
    check(sb.section_actions["measure"].isChecked(), "View ▸ Measure shows the section")
    w.close()
    # results file: Results on too; STEP has no results (pyvistaOriginalPointIds)
    w = open_file(app, files["tecplot"])
    check("results" in w.sidebar.shown_sections(), "results file opens on Results")
    w.close()
    from meshviewer.core.fields import solution_fields
    w = open_file(app, files["step"])
    check(solution_fields(w.scene.model.parts) == [], "STEP: no solution fields")
    w.close()


if __name__ == "__main__":
    run(test)
