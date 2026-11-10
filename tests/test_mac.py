"""2.5: the app organized the macOS way — menu bar, undo, Settings, names, title, beta."""
import numpy as np
from conftest import check, open_file, run


def _menus(w):
    """{menu title: [item texts]} of the window's menu bar."""
    out = {}
    for top in w.menuBar().actions():
        if top.menu() is not None:
            out[top.menu().title()] = [a.text() for a in top.menu().actions() if a.text()]
    return out


def test(app, files):
    pump = lambda: [app.processEvents() for _ in range(5)]        # noqa: E731
    # ---- the beta version -------------------------------------------------------------
    from meshviewer import __version__, version_label
    from meshviewer.gui.dialogs.about import compare_versions as cmp
    check(version_label("2.5b1") == "2.5 beta 1" and version_label("2.4.11") == "2.4.11",
          f"version shown as {version_label()} ({__version__})")
    check(cmp("2.5b1", "v2.4.11") == 1 and cmp("2.5b1", "v2.5") == -1
          and cmp("2.5b1", "v2.5b2") == -1 and cmp("2.5", "v2.5b1") == 1,
          "a beta is newer than 2.4.11, older than its release")

    # ---- the menu bar -----------------------------------------------------------------------
    w = open_file(app, files["cgns"])
    sc, sb = w.scene, w.sidebar
    m = _menus(w)
    check(list(m) == ["File", "Edit", "View", "Window", "Help"], f"menus {list(m)}")
    acts = app.app_menu_actions()
    check(acts is app.app_menu_actions() and [a.text() for a in acts] ==
          ["About Mesh Viewer", "Check for Updates…", "Settings…"]
          and acts[2].menuRole() != acts[2].MenuRole.PreferencesRole,
          "app menu items made once; Settings… keeps its name (not Preferences…)")
    check({"Select All", "Deselect All", "Hide Selection", "Isolate Selection", "Show All",
           "Find…"} <= set(m["Edit"]) and m["Edit"][0].startswith("Undo"), "Edit menu")
    check({"Minimize", "Zoom", "Bring All to Front"} <= set(m["Window"])
          and {"Mesh Viewer Help", "Keyboard Shortcuts", "Release Notes"} <= set(m["Help"]),
          "Window and Help menus")
    check({"Inspector", "View Tools", "Measure Tools", "Analyze Tools", "Units", "Show",
           "Customize Toolbar…"} <= set(m["View"]) and "Settings…" in m["File"]
          and "Tools" not in m["View"],
          "View ▸ Inspector, its tabs, Units, Customize Toolbar…; Settings… (app menu on macOS)")
    in_menus = set()

    def walk(menu):
        for a in menu.actions():
            in_menus.add(a)
            if a.menu() is not None:
                walk(a.menu())
    walk(w.menuBar())
    from PySide6.QtWidgets import QToolBar, QToolButton
    bar = w.findChildren(QToolBar)[0]                     # the window's toolbar only
    tb = {b.defaultAction() for b in bar.findChildren(QToolButton) if b.defaultAction()}
    tb = {a for a in tb if a.text()}
    pulls = {a for a in tb if a.menu() is not None}      # Show ▾, the unit ▾: their items
    tb = (tb - pulls) | {x for a in pulls for x in a.menu().actions() if x.text()}
    texts = {a.text() for a in in_menus}
    missing = [a.text() for a in tb if a not in in_menus and a.text() not in texts]
    check(not missing, f"every toolbar button is also in a menu (missing: {missing})")
    from meshviewer.gui.dialogs.shortcuts import shortcuts
    keys = dict(shortcuts(w.menuBar()))
    check("Edit" in keys and any(t == "Select All" for t, _ in keys["Edit"]),
          "Help ▸ Keyboard Shortcuts reads the menus")

    # ---- undo: hide, show all, isolate, color, rename ------------------------------------------
    names = list(sc.names)
    st = w.changes.stack
    sb._visibility_changed([names[0]], False)
    check(not sc.visible[names[0]] and w.a_undo.text() == f"Undo Hide {names[0]}",
          f"hide: {w.a_undo.text()!r}")
    w.a_undo.trigger()
    pump()
    check(sc.visible[names[0]], "⌘Z shows it again")
    w.a_redo.trigger()
    check(not sc.visible[names[0]], "⇧⌘Z hides it again")
    sb._set_all(True)
    check(all(sc.visible.values()) and w.a_undo.text() == "Undo Show All", "Show All, undoable")
    sb._isolate([names[1]])
    check([n for n in names if sc.visible[n]] == [names[1]], "isolate")
    w.a_undo.trigger()
    check(all(sc.visible.values()), "undo isolate: all back")
    before = sc.colors[names[0]]
    w.changes.color([names[0]], "#123456")
    check(sc.colors[names[0]] == "#123456", "color")
    w.a_undo.trigger()
    check(sc.colors[names[0]] == before, "undo color")
    sb._rename(names[0], "Renamed")
    check("Renamed" in sc.names and w.a_undo.text() == f"Undo Rename {names[0]}", "rename")
    w.a_undo.trigger()
    check(names[0] in sc.names and "Renamed" not in sc.names, "undo rename")
    w.a_redo.trigger()
    check("Renamed" in sc.names, "redo rename")
    w.a_undo.trigger()

    # ---- undo: the Edit tool ------------------------------------------------------------------
    from meshviewer.core import transform as xf
    p0 = np.array(sc.model.parts[names[0]].points)
    sb.edit_panel.edit_requested.emit(xf.rotation("z", 90), (0.0, 0.0, 0.0), "Rotate 90° about Z")
    pump()
    moved = not np.allclose(sc.model.parts[names[0]].points, p0)
    check(moved and sc.model.edited and "— Edited" in w.windowTitle() and w.isWindowModified(),
          f"rotate: title {w.windowTitle()!r}")
    w.a_undo.trigger()
    pump()
    check(np.allclose(sc.model.parts[names[0]].points, p0) and not sc.model.edited
          and "Edited" not in w.windowTitle(), "⌘Z: back as opened, title clean")
    w.a_redo.trigger()
    sb.edit_panel.edit_requested.emit(np.eye(3), (1.0, 0.0, 0.0), "Move 1, 0, 0")
    check(len(sc.edit_labels) == 2, "two edits")
    sb.edit_panel.undo_requested.emit()                  # the Edit tool's own Undo
    check(sc.edit_labels == ["Rotate 90° about Z"], "Edit ▸ Undo button: last edit gone")
    w.a_undo.trigger()
    check(len(sc.edit_labels) == 2, "…and ⌘Z brings it back")
    sb.edit_panel.reset_requested.emit()
    check(not sc.model.edited and np.allclose(sc.model.parts[names[0]].points, p0), "Reset")
    w.a_undo.trigger()
    check(len(sc.edit_labels) == 2 and sc.model.edited, "undo Reset")
    st.clear()
    sb.edit_panel.reset_requested.emit()

    # ---- Edit ▸ Select All, Find, Deselect -----------------------------------------------------
    w.a_select_all.trigger()
    check(set(sc.selected_parts) == {n for n in sc.names if sc.visible[n]}, "Select All")
    w.a_hide_sel.trigger()
    check(not any(sc.visible.values()), "Hide Selection")
    w.a_undo.trigger()
    w.a_deselect.trigger()
    check(not sc.selected_parts, "Deselect All")
    w.a_find.trigger()
    pump()
    check(w.focusWidget() is sb.filter and sb.filter.isVisible(), "Find… goes to the filter")

    # ---- names ---------------------------------------------------------------------------------
    from meshviewer.gui.sections import BY_KEY
    from meshviewer.core import plots
    check(BY_KEY["quality"].title == "Mesh Quality" and BY_KEY["cells"].title == "Cell Quality"
          and plots.KINDS["section"]["title"] == "Section", "Title Case tool names; Section plot")
    check(sb.plots_panel.new.text() == "New Plot…", "New Plot…")
    w.close()

    # ---- CAD: hidden faces undo, Inflation Layers ---------------------------------------------
    w = open_file(app, files["step"])
    sc, sb = w.scene, w.sidebar
    n = sc.names[0]
    sb._hide_face(n, 0)
    check(sc.n_hidden_faces == 1 and w.a_undo.text() == "Undo Hide Face", "Hide Face")
    w.a_undo.trigger()
    check(sc.n_hidden_faces == 0, "undo Hide Face")
    check(sb.inflation_section.header.title.text() == "Inflation Layers"
          if hasattr(sb.inflation_section.header, "title") else True, "CFD ▸ Inflation Layers")
    w.close()

    # ---- Settings ------------------------------------------------------------------------------
    app.show_settings()
    s = app._settings
    pump()
    check(s.windowTitle() in ("General", "Appearance", "Units") and len(s.tabs) == 3,
          f"Settings window, tab {s.windowTitle()!r}")
    for key, title in (("units", "Units"), ("appearance", "Appearance"), ("general", "General")):
        s.show_tab(key)
        check(s.windowTitle() == title and s.pages.currentWidget() is s.tabs[key][1], f"tab {title}")
    s.quality.setCurrentIndex(s.quality.findData(0))            # Very coarse
    s.shown.setCurrentIndex(s.shown.findData("cm"))
    s.ask.setChecked(False)
    check(app.prefs["cad_quality"] == 0 and app.prefs["shown_unit"] == "cm"
          and app.prefs["ask_unit"] is False, "settings saved at once")
    from meshviewer.gui.store import settings
    from meshviewer.gui import memory
    path = files["step"]
    st = settings()
    st.remove("views")                                   # as if the file were new
    w = open_file(app, path)
    pump()
    check(w.scene.model.quality == 0, "opens at Settings ▸ CAD mesh quality (Very coarse)")
    check(w.scene.measure.display_unit == "cm", "lengths shown in Settings ▸ Units (cm)")
    check(getattr(w, "_unit_dialog", None) is None or not w._unit_dialog.isVisible(),
          "Ask when opened: off -> no unit sheet")
    w.close()
    s.close()
    for k, v in (("cad_quality", "last"), ("shown_unit", "file"), ("ask_unit", True)):
        app.set_pref(**{k: v})
    _ = memory


def test_beta2(app, files):
    """2.5 beta 2: welcome screen, samples, Revert to Original, spinner, sheets, VoiceOver."""
    import shutil
    import tempfile
    from pathlib import Path
    from PySide6.QtWidgets import QAbstractButton
    from meshviewer.gui import samples, memory
    from meshviewer.gui.widgets import Switch
    pump = lambda: [app.processEvents() for _ in range(5)]        # noqa: E731
    tmp = Path(tempfile.mkdtemp())                              # samples, as in the app
    shutil.copy(files["step"], tmp / "avbay.step")
    samples._folders = lambda: [tmp]
    w = app.new_window()
    pump()
    wel = w.welcome
    check(w.stack.currentWidget() is wel and wel.open.isVisible(), "an empty window: the welcome screen")
    rows = [b for b in wel.findChildren(QAbstractButton) if b.objectName() == "WelcomeRow"]
    sample = [b for b in rows if b.accessibleName() == "Avionics Bay"]
    check(sample and any(b.accessibleName() == Path(files["cgns"]).name for b in rows),
          "it lists the recent files and the samples")
    file_menu = next(a.menu() for a in w.menuBar().actions() if a.menu().title() == "File")
    sub = next(a.menu() for a in file_menu.actions() if a.menu() and a.menu().title() == "Open Sample")
    check([a.text() for a in sub.actions()] == ["Avionics Bay"], "File ▸ Open Sample")
    sample[0].click()
    from conftest import wait
    wait(app, lambda: w.scene is not None)
    pump()
    check(w.path == tmp / "avbay.step" and samples.is_sample(w.path), "a sample opens in this window")
    from meshviewer.gui.sheets import save_folder
    check(save_folder(w.path) != tmp, "a sample saves to Documents, not inside the app")
    check(not w.spinner.busy and not w.spinner.slot.isVisible(), "spinner stopped once open")
    w.spinner.begin("Testing…")
    check(w.spinner.slot.isVisible() and "Testing" in w.spinner.toolTip(), "spinner turns while busy")
    w.spinner.end()
    check(not w.spinner.slot.isVisible(), "…and hides at the end")
    switches = [s for s in w.findChildren(Switch) if s.isVisibleTo(w)]
    unnamed = [s for s in w.findChildren(QAbstractButton)
               if s.isVisibleTo(w) and not s.text().strip() and not s.accessibleName()]
    check(switches and not unnamed, f"VoiceOver: every icon button / switch has a name "
          f"(without: {[(type(b).__name__, b.objectName(), b.toolTip()) for b in unnamed]})")
    from meshviewer.gui.report import report_url
    u = report_url("boom", "x.step")
    check("issues/new" in u and "boom" in u and "Mesh+Viewer" in u, "Report a Problem: the issue is filled in")
    # ---- Revert to Original ----------------------------------------------------------------
    sc = w.scene
    n = sc.names[0]
    w.changes.color([n], "#123456")
    w.sidebar._visibility_changed([n], False)
    w.remember_view()
    check(memory.load(w.path) is not None, "the file is remembered")
    path = w.path
    w.revert_to_original()
    pump()
    check(w._revert_box.isVisible(), "Revert to Original… asks first (a sheet)")
    w._revert_box.reject()
    pump()
    check(w in app.windows and not sc.visible[n], "Cancel: nothing changes")
    w._revert()
    new = app.windows[-1]
    wait(app, lambda: new.scene is not None)
    pump()
    check(w not in app.windows and new.path == path, "reverted: the file again, in a fresh window")
    check(all(new.scene.visible.values()) and new.scene.colors[n] != "#123456",
          "…as the first time: everything shown, its first colors")
    new.close()
    pump()


def _both(app, files):
    test(app, files)
    test_beta2(app, files)


if __name__ == "__main__":
    run(_both)
