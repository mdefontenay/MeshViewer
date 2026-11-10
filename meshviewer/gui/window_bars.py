"""The window's actions, toolbar and menus (built once, by ViewerWindow.__init__).

The menu bar, as Mac apps lay it out — every toolbar button is in it too:

    Mesh Viewer   About, Check for Updates…, Settings… ⌘,          (macOS's app menu)
    File          Open… ⌘O, Open Recent, Open Sample, Close ⌘W, Revert to Original…, Export… ⇧⌘E,
                  Save Screenshot… ⇧⌘S, File Unit…
    Edit          Undo ⌘Z, Redo ⇧⌘Z, Select All ⌘A, Deselect All ⌥⌘A, Hide / Isolate
                  Selection, Show All, Find… ⌘F
    View          Sidebar ⌃⌘S, Inspector ⌥⌘I, View / Measure / Analyze Tools ⌥⌘1–3,
                  Section, Measure, Show, Units, Perspective, Fit, views ⌘1–4,
                  Next / Previous Tab ⌃⇥, Customize Toolbar…
    Window        Minimize ⌘M, Zoom, Bring All to Front, the open windows
    Help          Mesh Viewer Help, Keyboard Shortcuts, Release Notes, Report a Problem…

The toolbar is light: the sidebar on the left; the views; Show ▾ and the unit ▾
(pull-down menus); then Export and Screenshot; the inspector on the right. View ▸
Customize Toolbar… (or a right-click on it) picks which groups it shows.
"""
from __future__ import annotations

import sys

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QKeySequence
from PySide6.QtWidgets import QSizePolicy, QToolBar, QToolButton, QWidget

from meshviewer.gui.dialogs.toolbar import CustomizeToolbar, hidden_items
from meshviewer.gui.feedback import Spinner
from meshviewer.gui.icons import icon
from meshviewer.gui.report import report_problem
from meshviewer.gui.sections import TABS
from meshviewer.gui.welcome import add_sample_menu
from meshviewer.gui.widgets import Capsule, Menu

HELP_URL = "https://github.com/mdefontenay/MeshViewer#readme"
NOTES_URL = "https://github.com/mdefontenay/MeshViewer/releases"


class Bars:
    def _act(self, text, slot, shortcut=None, checkable=False):
        a = QAction(text, self)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        a.setCheckable(checkable)
        a.triggered.connect(slot)
        return a

    def _build_actions(self):
        self.a_open = self._act("Open…", self.ctl.open_dialog, QKeySequence.Open)
        self.a_close = self._act("Close", self.close, QKeySequence.Close)
        self.a_revert = self._act("Revert to Original…", self.revert_to_original)
        self.a_shot = self._act("Save Screenshot…", self.save_screenshot, "Ctrl+Shift+S")
        self.a_appearance = self._act("Settings…", self.ctl.show_settings)   # toolbar button
        self.a_appearance.setMenuRole(QAction.NoRole)    # (the menu's Settings…: app menu)
        self.a_sidebar = self._act("Sidebar", self.toggle_sidebar, "Meta+Ctrl+S", checkable=True)
        self.a_sidebar.setChecked(True)
        self.a_inspector = self._act("Inspector", self.toggle_inspector, "Ctrl+Alt+I",
                                     checkable=True)
        self.a_inspector.setChecked(True)
        self.a_tabs = [self._act(f"{title} Tools", lambda _=False, k=key: self.show_tools(k),
                                 f"Ctrl+Alt+{i}")
                       for i, (key, title) in enumerate(TABS, 1)]
        self.a_customize = self._act("Customize Toolbar…", self.customize_toolbar)
        self.a_section = self._act("Section", self._toggle_section, "Ctrl+Alt+X", checkable=True)
        self.a_measure = self._act("Measure", self._toggle_measure, "Ctrl+Shift+M", checkable=True)
        # ---- Edit menu: undo, selection, visibility, find
        self.a_undo = self.changes.stack.createUndoAction(self, "Undo")
        self.a_undo.setShortcut(QKeySequence.Undo)
        self.a_redo = self.changes.stack.createRedoAction(self, "Redo")
        self.a_redo.setShortcuts([QKeySequence("Ctrl+Shift+Z"), QKeySequence.Redo])
        self.a_select_all = self._act("Select All", self._select_all, QKeySequence.SelectAll)
        self.a_deselect = self._act("Deselect All", self._deselect)
        self.a_deselect.setShortcuts([QKeySequence("Ctrl+Alt+A"), QKeySequence("Esc")])
        self.a_hide_sel = self._act("Hide Selection", lambda: self._selection_visible(False))
        self.a_isolate_sel = self._act("Isolate Selection", self._isolate_selection)
        self.a_show_all = self._act("Show All", lambda: self.scene and self.sidebar._set_all(True))
        self.a_find = self._act("Find…", self._find, QKeySequence.Find)
        # ---- View ▸ tabs under the view, Window, Help
        self.a_next_tab = self._act("Show Next Tab", lambda: self._step_tab(1), "Meta+Tab")
        self.a_prev_tab = self._act("Show Previous Tab", lambda: self._step_tab(-1),
                                    "Meta+Shift+Tab")
        self.a_minimize = self._act("Minimize", self.showMinimized, "Ctrl+M")
        self.a_zoom = self._act("Zoom", self._zoom_window)
        self.a_front = self._act("Bring All to Front", self.ctl.bring_all_to_front)
        self.a_help = self._act("Mesh Viewer Help", lambda: QDesktopServices.openUrl(QUrl(HELP_URL)),
                                "Ctrl+?")
        self.a_keys = self._act("Keyboard Shortcuts", self.show_shortcuts)
        self.a_notes = self._act("Release Notes", lambda: QDesktopServices.openUrl(QUrl(NOTES_URL)))
        self.a_report = self._act("Report a Problem…", lambda: report_problem(
            file_name=self.path.name if self.path else ""))
        # display units for measurements (lengths, areas, volumes)
        self.unit_group = QActionGroup(self)
        self.unit_group.setExclusive(True)
        self.a_units = []
        for key, text, tip in (("mm", "mm", "Millimeters"), ("cm", "cm", "Centimeters"),
                               ("m", "m", "Meters"), ("in", "in", "Inches"), ("ft", "ft", "Feet")):
            a = QAction(text, self)
            a.setCheckable(True)
            a.setData(key)
            a.setToolTip(tip)
            self.unit_group.addAction(a)
            self.a_units.append(a)
        self.unit_group.triggered.connect(self._unit_chosen)
        # where the old "no unit" button was: what unit are the file's numbers in?
        self.a_file_unit = self._act("File Unit…", self._edit_file_unit)
        self.a_file_unit.setIcon(icon("edit_unit"))
        self.a_fit = self._act("Fit", lambda: self.scene and self.scene.fit(), "Ctrl+0")
        # parallel projection is a toolbar toggle next to the views
        self.a_parallel = self._act("Perspective",          # on: perspective, off: parallel
                                    lambda on: self.scene and self.scene.set_parallel(not on),
                                    "Ctrl+5", checkable=True)
        # what is shown, as toolbar toggles. Edges: one pill; axes, grid, bounding box,
        # origin: another.
        self.a_show = {}
        for key, text in (("mesh_edges", "Mesh Edges"), ("feature_edges", "Feature Edges"),
                          ("faces", "Faces"), ("axes", "Axes"), ("grid", "Grid"),
                          ("bbox", "Bounding Box"), ("origin", "Origin")):
            a = self._act(text, lambda on, k=key: self._show_toggled(k, on), checkable=True)
            a.setIcon(icon(key))
            self.a_show[key] = a
        # Export. (Edit lives in the sidebar.)
        self.a_export = self._act("Export…", self.export_model, "Ctrl+Shift+E")
        self.a_views = [
            self._act("Iso", lambda: self.scene and self.scene.view("iso"), "Ctrl+1"),
            self._act("X", lambda: self.scene and self.scene.view("x"), "Ctrl+2"),
            self._act("Y", lambda: self.scene and self.scene.view("y"), "Ctrl+3"),
            self._act("Z", lambda: self.scene and self.scene.view("z"), "Ctrl+4"),
        ]
        # Icons (drawn, follow light/dark). X / Y / Z stay as letters.
        for a, name in ((self.a_sidebar, "sidebar"), (self.a_inspector, "inspector"),
                        (self.a_fit, "fit"),
                        (self.a_views[0], "iso"), (self.a_section, "section"),
                        (self.a_shot, "camera"), (self.a_measure, "ruler"),
                        (self.a_appearance, "appearance"), (self.a_parallel, "parallel"),
                        (self.a_export, "export")):
            a.setIcon(icon(name))
        # hover: the name and the shortcut, nothing more
        names = {self.a_views[0]: "Isometric", self.a_shot: "Screenshot",
                 self.a_appearance: "Settings", self.a_export: "Export",
                 self.a_fit: "Fit View"}
        for a in (self.a_sidebar, self.a_inspector, self.a_fit, *self.a_views, self.a_section, self.a_shot,
                  self.a_measure, self.a_appearance, self.a_parallel, self.a_export,
                  self.a_file_unit, *self.a_show.values()):
            name = names.get(a, a.text().rstrip("…"))
            keys = a.shortcut().toString(QKeySequence.NativeText)
            a.setToolTip(f"{name}  ({keys})" if keys else name)
        keys = QKeySequence("Ctrl+,").toString(QKeySequence.NativeText)
        self.a_appearance.setToolTip(f"Settings  ({keys})")        # its shortcut: app menu

    def _pulldown(self, text, menu, icon_name=None):
        """A toolbar button that opens `menu` (its own QMenu: the menu bar has the same
        items): an icon or a word, then ▾."""
        a = QAction(f"{text} ▾" if icon_name is None else "▾", self)
        if icon_name:
            a.setIcon(icon(icon_name))
        a.setMenu(menu)
        a.setToolTip(text)
        cap = Capsule([a])
        b = cap.buttons[0]
        b.setPopupMode(QToolButton.InstantPopup)
        b.setToolButtonStyle(Qt.ToolButtonTextBesideIcon if icon_name else Qt.ToolButtonTextOnly)
        b.setStyleSheet("QToolButton::menu-indicator { image: none; width: 0; }")
        b.setAccessibleName(text)
        return a, cap

    def _build_toolbar(self):
        tb = QToolBar("Toolbar")
        self.toolbar = tb
        tb.setMovable(False)
        tb.setFloatable(False)
        tb.toggleViewAction().setVisible(False)
        tb.setContextMenuPolicy(Qt.PreventContextMenu)   # the window's menu: Customize…
        # Groups of related buttons, each in one capsule (macOS 27 toolbar style).
        items = {}
        items["sidebar"] = tb.addWidget(Capsule([self.a_sidebar]))
        self.view_capsule = Capsule([self.a_fit, *self.a_views, self.a_parallel])
        items["views"] = tb.addWidget(self.view_capsule)
        show = Menu(self)                              # what is shown (= View ▸ Show)
        for k, a in self.a_show.items():
            if k == "axes":
                show.addSeparator()
            show.addAction(a)
        self.a_show_menu, cap = self._pulldown("Show", show, "eye")
        items["show"] = tb.addWidget(cap)
        units = Menu(self)                             # the shown unit (= View ▸ Units)
        for a in self.a_units:
            units.addAction(a)
        units.addSeparator()
        units.addAction(self.a_file_unit)
        self.a_units_menu, cap = self._pulldown("Units", units)
        items["units"] = tb.addWidget(cap)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        tb.addWidget(spacer)
        self.spinner = Spinner()                       # turns while background work runs
        self.spinner.slot = tb.addWidget(self.spinner)
        self.spinner.slot.setVisible(False)
        items["export"] = tb.addWidget(Capsule([self.a_export]))
        items["screenshot"] = tb.addWidget(Capsule([self.a_shot]))
        items["settings"] = tb.addWidget(Capsule([self.a_appearance]))
        items["inspector"] = tb.addWidget(Capsule([self.a_inspector]))
        self._tb_items = items                         # a toolbar widget hides by its action
        self.addToolBar(tb)
        self.apply_toolbar()

    def apply_toolbar(self):
        """Show the groups Customize Toolbar… left on (and the views only for 3D files)."""
        hidden = hidden_items()
        for key, slot in self._tb_items.items():
            on = key not in hidden
            if key == "views":
                on = on and getattr(self.view_capsule, "has_shown", True)
            slot.setVisible(on)

    def customize_toolbar(self):
        self._customize = CustomizeToolbar(self)
        self._customize.changed.connect(
            lambda: [w.apply_toolbar() for w in getattr(self.ctl, "windows", [self])])
        self._customize.open()

    def createPopupMenu(self):
        """Right-click on the toolbar (or the title bar): Customize Toolbar…."""
        m = Menu(self)
        m.addAction(self.a_customize)
        return m

    def _build_menus(self):
        bar = self.menuBar()
        m = bar.addMenu("File")
        if sys.platform != "darwin":                   # macOS: the shared app menu has them
            for a in self.ctl.app_menu_actions():
                m.addAction(a)
        m.addAction(self.a_open)
        self.ctl.add_recent_menu(m)                     # Open Recent
        add_sample_menu(m, lambda p: self.ctl.open_path(p, prefer=self))
        m.addSeparator()
        m.addAction(self.a_close)
        m.addAction(self.a_revert)
        m.addSeparator()
        m.addAction(self.a_export)
        m.addAction(self.a_shot)
        m.addSeparator()
        m.addAction(self.a_file_unit)

        e = bar.addMenu("Edit")
        e.addAction(self.a_undo)
        e.addAction(self.a_redo)
        e.addSeparator()
        e.addAction(self.a_select_all)
        e.addAction(self.a_deselect)
        e.addSeparator()
        e.addAction(self.a_hide_sel)
        e.addAction(self.a_isolate_sel)
        e.addAction(self.a_show_all)
        e.addSeparator()
        e.addAction(self.a_find)

        v = bar.addMenu("View")
        v.addAction(self.a_sidebar)
        v.addAction(self.a_inspector)
        v.addSeparator()
        for a in self.a_tabs:                          # the inspector's tabs
            v.addAction(a)
        v.addSeparator()
        v.addAction(self.a_section)
        v.addAction(self.a_measure)
        v.addSeparator()
        show = v.addMenu("Show")                       # the toolbar toggles
        for k, a in self.a_show.items():
            if k == "axes":
                show.addSeparator()
            show.addAction(a)
        units = v.addMenu("Units")                     # the toolbar's units
        for a in self.a_units:
            units.addAction(a)
        units.addSeparator()
        units.addAction(self.a_file_unit)
        v.addSeparator()
        v.addAction(self.a_parallel)
        v.addAction(self.a_fit)
        for a in self.a_views:
            v.addAction(a)
        v.addSeparator()
        v.addAction(self.a_next_tab)
        v.addAction(self.a_prev_tab)
        v.addSeparator()
        v.addAction(self.a_customize)

        w = bar.addMenu("Window")
        w.addAction(self.a_minimize)
        w.addAction(self.a_zoom)
        w.addSeparator()
        w.addAction(self.a_front)
        w.addSeparator()
        self._windows_at = len(w.actions())            # the open windows come after this
        w.aboutToShow.connect(lambda: self._fill_windows(w))

        h = bar.addMenu("Help")
        h.addAction(self.a_help)
        h.addAction(self.a_keys)
        h.addAction(self.a_notes)
        h.addSeparator()
        h.addAction(self.a_report)

    # ---- what the menus do ---------------------------------------------------------------
    def _fill_windows(self, menu):
        for a in menu.actions()[self._windows_at:]:
            menu.removeAction(a)
        for win in self.ctl.windows:
            a = menu.addAction(win.windowTitle().replace("[*]", "") or "Mesh Viewer")
            a.setCheckable(True)
            a.setChecked(win is self)
            a.triggered.connect(lambda _=False, x=win: (x.showNormal() if x.isMinimized() else None,
                                                        x.raise_(), x.activateWindow()))

    def _zoom_window(self):
        self.showNormal() if self.isMaximized() else self.showMaximized()

    def _select_all(self):
        if self.scene:
            shown = [n for n in self.scene.names if self.scene.visible.get(n)]
            self.scene.set_selection(shown, notify=True)

    def _selection_visible(self, on):
        if self.scene and self.scene.selected_parts:
            self.sidebar._visibility_changed(list(self.scene.selected_parts), on)

    def _isolate_selection(self):
        if self.scene and self.scene.selected_parts:
            self.sidebar._isolate(list(self.scene.selected_parts))

    def _find(self):
        """⌘F: the parts list's filter field."""
        if not self.scene:
            return
        if not self.a_sidebar.isChecked():
            self.a_sidebar.trigger()
        self.sidebar.parts_section.set_expanded(True)
        self.sidebar.filter.setFocus()
        self.sidebar.filter.selectAll()

    def _step_tab(self, step):
        """⌃⇥ / ⌃⇧⇥: the next / previous tab under the 3D view."""
        tabs = self.view_bar_actions()
        if len(tabs) < 2:
            return
        now = next((i for i, a in enumerate(tabs) if a.isChecked()), 0)
        tabs[(now + step) % len(tabs)].trigger()

    def show_shortcuts(self):
        """Help ▸ Keyboard Shortcuts: every menu item that has one, by menu."""
        from meshviewer.gui.dialogs.shortcuts import ShortcutsDialog
        self._shortcuts = ShortcutsDialog(self, self.menuBar(), self.ctl.app_menu_actions())
        self._shortcuts.show()
        self._shortcuts.raise_()

    def _set_loaded(self, loaded):
        for a in [self.a_shot, self.a_fit, self.a_section, self.a_measure, *self.a_views,
                  *self.a_units, self.a_file_unit, *self.a_show.values(), self.a_export,
                  self.a_revert,
                  self.a_parallel, self.a_select_all, self.a_deselect, self.a_hide_sel,
                  self.a_isolate_sel, self.a_show_all, self.a_find, self.a_next_tab,
                  self.a_prev_tab, self.a_inspector, *self.a_tabs, self.a_show_menu,
                  self.a_units_menu]:
            a.setEnabled(loaded)
        if loaded and self.scene is not None:
            self._fit_toolbar(self.scene.model)
        self.stack.setCurrentWidget(self.plotter if loaded else self.empty)
        self.sidebar.setVisible(loaded and self.a_sidebar.isChecked())   # empty: welcome only
        self.sidebar.set_inspector_visible(loaded and self.a_inspector.isChecked())
        self.a_sidebar.setEnabled(loaded)

    def _fit_toolbar(self, model):
        """Only the buttons that mean something for this file: 2D files are always seen
        from above (no views, no perspective); drawings are lines only (no edges or
        faces toggles, no bounding box or origin)."""
        flat, drawing = model.dim == 2, model.file_type == "drawing"
        hide = set()
        if flat:
            hide |= {*self.a_views, self.a_parallel}
        if drawing:
            hide |= {self.a_show[k] for k in ("mesh_edges", "feature_edges", "faces",
                                               "bbox", "origin")}
        for a in (*self.a_views, self.a_parallel, *self.a_show.values()):
            a.setVisible(a not in hide)              # menus and shortcuts too
        cap = self.view_capsule
        cap.show_only([b.defaultAction() for b in cap.buttons if b.defaultAction() not in hide])
        self.apply_toolbar()
