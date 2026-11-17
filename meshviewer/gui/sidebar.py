"""The two side panels of a window, and everything in them:

    Sidebar (left)      the parts list: filter, selection, show / hide, its summary line
    Inspector (right)   the tools, in three tabs — View · Measure · Analyze
                        (gui/sections.py lists them; gui/inspector.py is the panel)

One Sidebar object builds both and owns the tools' panels (sb.section_panel,
sb.measure_panel…); the window puts sb and sb.inspector either side of the 3D view.
Talks only to a Scene. Selection works both ways: click a part in the 3D view -> it is
selected in the list; select it in the list -> highlighted.

A tool works while it is in view: open, in the tab shown, with the inspector shown
(Measure measures, Plots draws its cuts in 3D, Cell Quality and CFD compute). The tab
and the open tools are remembered per file (scene.inspector_state).
"""
from __future__ import annotations

import shiboken6
from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QActionGroup, QPalette
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QSizePolicy, QToolButton,
    QVBoxLayout, QWidget,
)

from meshviewer.gui.forms import link
from meshviewer.gui.icons import icon
from meshviewer.gui.inspector import Inspector
from meshviewer.gui.panels.cfd import CfdPanel
from meshviewer.gui.panels.contours import ContoursPanel
from meshviewer.gui.panels.edit import EditPanel
from meshviewer.gui.panels.inflation import InflationPanel
from meshviewer.gui.panels.info import InfoPanel
from meshviewer.gui.panels.measure import MeasurePanel
from meshviewer.gui.panels.meshing import MeshingPanel
from meshviewer.gui.panels.parts import PartTree
from meshviewer.gui.panels.plots import PlotsPanel
from meshviewer.gui.panels.quality import QualityPanel
from meshviewer.gui.panels.section import SectionPanel
from meshviewer.gui.panels.selected import SelectedPanel
from meshviewer.gui.sections import BY_KEY, default_open, default_tab, tabs_for
from meshviewer.gui.sidebar_layout import Box
from meshviewer.gui.sidebar_menu import PartMenu
from meshviewer.gui.store import settings
from meshviewer.gui.widgets import CollapsibleSection, Menu, rule
from meshviewer.render.scene import Scene


class Sidebar(PartMenu, QWidget):
    quality_requested = Signal(int)     # window re-tessellates in the background
    renamed = Signal()                  # a part was renamed (window: unsaved dot)
    activity_changed = Signal()         # the tab shown changed, or a tool came into view or left it

    def __init__(self, parent=None):
        super().__init__(parent)
        self.changes = None                 # Edit ▸ Undo (gui/undo.py), set by the window
        self.setObjectName("Sidebar")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.scene: Scene | None = None
        self.summary = ""
        self._boxes: dict[str, Box] = {}
        self._active = {}                   # tool -> it was in view (activate called)

        self.inspector = Inspector()
        self.inspector.tab_changed.connect(lambda _k: self._tools_changed())
        self._build_sections()

        lay = QVBoxLayout(self)             # the parts list, the whole height
        lay.setContentsMargins(12, 10, 10, 10)
        lay.setSpacing(8)
        self._build_parts(lay)
        self.setEnabled(False)
        self.inspector.setEnabled(False)

    # ---- the sections -----------------------------------------------------------------
    def _add(self, key, panel, trailing=None, title=None, card=True):
        """Put panel in a CollapsibleSection of tool `key` (several for "cfd"), on a
        gray card (card=False: the panel draws its own cards, e.g. Plots), in its tab."""
        holder = QFrame() if card else QWidget()
        if card:
            holder.setObjectName("SectionCard")
        v = QVBoxLayout(holder)
        v.setContentsMargins(*((8, 9, 8, 10) if card else (0, 0, 0, 0)))
        v.setSpacing(0)
        note = QLabel("")
        note.setObjectName("UnavailableNote")
        note.setProperty("card", not card)          # its own card (the panel has none)
        note.setWordWrap(True)
        note.setVisible(False)
        v.addWidget(note)
        v.addWidget(panel)
        sec = CollapsibleSection(title or BY_KEY[key].title, holder, key, trailing=trailing,
                                 remember=False, start_open=False)
        box = self._boxes.get(key)
        if box is None:
            w = QWidget()
            bl = QVBoxLayout(w)
            bl.setContentsMargins(0, 0, 0, 0)
            bl.setSpacing(8)
            box = self._boxes[key] = Box(w)
            self.inspector.add(BY_KEY[key].tab, w)
            box.divider = rule()                     # between this tool and the one above
            bl.addWidget(box.divider)
            bl.addWidget(sec)
        else:
            box.widget.layout().addWidget(sec)
        box.parts.append((sec, note, panel, trailing))
        sec.toggled.connect(lambda _on: self._tools_changed())
        return sec

    def _build_sections(self):
        self.info_panel = InfoPanel()
        self.info_section = self._add("info", self.info_panel)
        self.info_panel.activate(False)

        self._build_quality()

        self.section_panel = SectionPanel()
        self.section_section = self._add("section", self.section_panel,
                                         trailing=self.section_panel.enable)
        # switching the plane on opens its controls; off closes them
        self.section_panel.enable.toggled.connect(self.section_section.set_expanded)

        self.edit_panel = EditPanel()
        self.edit_section = self._add("edit", self.edit_panel)

        self.measure_panel = MeasurePanel()            # measuring while this is open
        self.measure_section = self._add("measure", self.measure_panel)
        self.selected_panel = SelectedPanel()          # what Select ▾ picked, in numbers
        self.selected_section = self._add("selected", self.selected_panel)

        # CFD: the y+ estimate for meshes, Inflation Layers for CAD files
        self.cfd_panel = CfdPanel()
        self.cfd_section = self._add("cfd", self.cfd_panel)
        self.inflation_panel = InflationPanel()
        self.inflation_section = self._add("cfd", self.inflation_panel,
                                           trailing=self.inflation_panel.enable,
                                           title="Inflation Layers")
        self.inflation_panel.enable.toggled.connect(self.inflation_section.set_expanded)

        self.cell_panel = QualityPanel()
        self.cell_section = self._add("cells", self.cell_panel)
        self.cell_panel.wants_section.connect(self._section_for_colors)
        self.cell_panel.computed.connect(self.info_panel.refresh)    # volume row
        self.cfd_panel.measured.connect(self.info_panel.refresh)     # volume row

        self.contours_panel = ContoursPanel()          # contours -> tabs under the view
        self.contours_section = self._add("contours", self.contours_panel, card=False)
        self.selected_panel.units = self.contours_panel   # field values in its units
        self.contours_panel.units_changed.connect(self.selected_panel.refresh)

        self.plots_panel = PlotsPanel()                # plots -> tabs under the view
        self.plots_section = self._add("plots", self.plots_panel, card=False)

    def _build_quality(self):
        self.meshing_panel = MeshingPanel()          # its level: in the header
        self.meshing_panel.level_requested.connect(self.quality_requested)
        self.quality = self.meshing_panel.slider
        self.quality_section = self._add("quality", self.meshing_panel,
                                         trailing=self.meshing_panel.value)

    # ---- tabs, open tools, what is in view -------------------------------------------------
    ACTIVE = ("info", "measure", "cfd", "cells", "plots")   # tools that work only in view

    def _panel_of(self, key):
        return {"info": self.info_panel, "measure": self.measure_panel,
                "cfd": self.cfd_panel, "cells": self.cell_panel}.get(key)

    def current_tab(self):
        return self.inspector.current()

    def show_tab(self, key):
        self.inspector.show_tab(key)

    def tab_shown(self, key):
        """Is tool `key`'s tab the one shown, in a shown inspector?"""
        return not self.inspector.isHidden() and self.current_tab() == BY_KEY[key].tab

    def is_open(self, key):
        return any(sec.expanded and sec.isVisibleTo(self._boxes[key].widget)
                   for sec, *_ in self._boxes[key].parts)

    def is_active(self, key):
        """In view: open, in the tab shown, with the inspector shown."""
        return self.tab_shown(key) and self.is_open(key)

    def show_section(self, key, on=True, expand=False):
        """on: bring tool `key`'s tab forward (and open the tool: expand); off: close it."""
        if on:
            if self.inspector.isHidden():
                self.set_inspector_visible(True)
            self.show_tab(BY_KEY[key].tab)
            if expand:
                for sec, *_ in self._boxes[key].parts:
                    if sec.isVisibleTo(self._boxes[key].widget):
                        sec.set_expanded(True)
        else:
            for sec, *_ in self._boxes[key].parts:
                sec.set_expanded(False)

    def reveal(self, key, ident):
        """A contour's or a plot's tab opened: its tool shown, its fold-out open (the
        others folded) and scrolled into view."""
        panel = {"contours": self.contours_panel, "plots": self.plots_panel}[key]
        if ident not in panel.editors:
            return
        self.show_section(key, expand=True)
        sec = panel.expand_only(ident)
        if sec is not None:
            QTimer.singleShot(0, lambda: shiboken6.isValid(sec) and self.inspector.reveal(sec))

    def set_inspector_visible(self, on):
        self.inspector.setVisible(bool(on))
        self._tools_changed()

    def _tools_changed(self):
        """A tab, a tool opened or closed, the inspector shown or hidden: tell the tools
        that came into view or left it, and remember the tab and the open tools."""
        if not hasattr(self, "plots_section"):     # still building the tools
            return
        shown = None if self.scene is None or self.inspector.isHidden() else self.current_tab()
        changed = shown != getattr(self, "_shown_tab", None)
        self._shown_tab = shown
        for key in self.ACTIVE:
            on = self.scene is not None and self.is_active(key)
            if self._active.get(key) != on:
                self._active[key] = on
                panel = self._panel_of(key)
                if panel is not None:
                    panel.activate(on)
                changed = True
        if self.scene is not None:
            self.scene.inspector_state = {
                "tab": self.current_tab(),
                "open": [k for k in self._boxes if self.is_open(k)]}
        self.inspector.refit()
        if changed:
            self.activity_changed.emit()

    def _update_dividers(self):
        """A line between tools, none above the first of each tab. (A tool's own hidden
        state counts, not its tab's: the tabs not shown are hidden pages.)"""
        for key in ("view", "measure", "analyze"):
            first = True
            for k, box in self._boxes.items():
                if BY_KEY[k].tab == key and not box.widget.isHidden():
                    box.divider.setVisible(not first)
                    first = False

    def _apply_support(self, scene):
        """Gray reason instead of the controls where a tool doesn't fit the file; its
        name lighter, so the tools that apply stand out at a glance."""
        for key, box in self._boxes.items():
            reason = BY_KEY[key].unavailable(scene)
            for sec, note, panel, trailing in box.parts:
                sec.set_unavailable(bool(reason))
                note.setText(reason or "")
                note.setVisible(bool(reason))
                panel.setVisible(not reason)
                if trailing is not None:
                    trailing.setVisible(not reason)
        cad = scene.model.is_cad                    # CFD: one of its two sections
        self.cfd_section.setVisible(not cad)
        self.inflation_section.setVisible(cad)

    # ---- Boundaries / Parts (always shown) -------------------------------------------
    def _build_parts(self, lay):
        parts = QWidget()
        pl = QVBoxLayout(parts)
        pl.setContentsMargins(0, 0, 0, 0)
        pl.setSpacing(6)
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Name, size > 10, volume < 5")
        self.filter.setToolTip("Filter")
        self.filter.setClearButtonEnabled(True)
        self.filter.addAction(icon("search", QPalette.PlaceholderText), QLineEdit.LeadingPosition)
        self.filter.textChanged.connect(self._apply_filter)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        row.addWidget(self.filter, 1)
        row.addWidget(self._build_options())
        pl.addLayout(row)

        # "3 parts selected · Clear", always shown (greyed at 0) so selecting
        # something doesn't push the list down
        self.sel_bar = QWidget()
        self.sel_bar.setObjectName("SelectionBar")
        self.sel_bar.setAttribute(Qt.WA_StyledBackground, True)
        sbl = QHBoxLayout(self.sel_bar)
        sbl.setContentsMargins(8, 3, 6, 3)
        self.sel_label = QLabel("")
        self.sel_label.setObjectName("SelectionCount")
        sbl.addWidget(self.sel_label)
        sbl.addStretch(1)
        self.sel_clear = link("Clear", "", self._clear_selection)
        sbl.addWidget(self.sel_clear)
        pl.addWidget(self.sel_bar)

        # a tree — parts sharing a base name fold into one group row
        self.list = PartTree()
        self.list.sort_by, self.list.reverse = self._sort_start
        self.list.mcmaster = self._mcmaster_start
        self.list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.list.setMinimumHeight(24)                # drag the line above down to here
        self.list.visibility_changed.connect(self._visibility_changed)
        self.list.selection_changed.connect(self._selection_changed)
        self.list.zoom_requested.connect(lambda names: self.scene and self.scene.zoom_to(names))
        self.list.isolate_requested.connect(self._isolate)
        self.list.context_requested.connect(self.part_menu)
        self.list.rename_requested.connect(self._rename)
        self.list.group_rename_requested.connect(self._rename_group)
        pl.addWidget(self.list, 1)

        links = QWidget()
        ll = QHBoxLayout(links)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(8)
        for text, on in (("Show All", True), ("Hide All", False)):
            ll.addWidget(link(text, "", lambda _=False, v=on: self._set_all(v)))
        self.parts_section = CollapsibleSection("Parts", parts, "parts", trailing=links,
                                                 locked=True)      # always open
        lay.addWidget(self.parts_section, 1)

        self.info = QLabel("")
        self.info.setObjectName("InfoLine")
        self.info.setWordWrap(True)
        lay.addWidget(self.info)

    # ---- binding to a scene -------------------------------------------
    def bind(self, scene: Scene):
        self.scene = None                           # no saving while setting up
        if self.changes is not None:
            self.changes.clear()                    # a new file: nothing to undo
        scene.on_pick = self.show_selection
        scene.elements.on_changed = lambda: self._elements_changed(scene)
        self.section_panel.bind(scene.section)
        self.edit_panel.bind(scene)
        self.measure_panel.bind(scene)
        self.selected_panel.bind(scene)
        self.cell_panel.bind(scene)
        self.info_panel.bind(scene)
        self.cfd_panel.bind(scene)
        self.contours_panel.bind(scene)
        self.plots_panel.bind(scene)
        self.inflation_panel.bind(scene)
        self._apply_support(scene)

        m = scene.model
        self._no_parts = m.file_type == "drawing"   # drawings: one color, no layer list
        self.parts_section.setVisible(not self._no_parts)
        self.meshing_panel.bind(scene)
        self.refresh_parts_of(scene)

        state = getattr(scene, "inspector_state", None) or {}
        tab = state.get("tab") or default_tab(scene)
        opened = state.get("open") if "open" in state else default_open(scene)
        opened = ["contours" if k == "results" else k for k in opened]   # (2.5: Results)
        self._active = {}
        self._shown_tab = None
        for key, box in self._boxes.items():         # open what was open, close the rest
            for sec, *_ in box.parts:
                if key == "section":                  # follows the plane's switch
                    sec.set_expanded(scene.section.enabled)
                elif sec is self.inflation_section:   # follows Inflation Layers' switch
                    sec.set_expanded(self.inflation_panel.enabled)
                else:
                    sec.set_expanded(key in opened)
        self._update_dividers()
        self.scene = scene
        tabs = tabs_for(scene)                       # a drawing: Measure only
        self.inspector.enable_tabs(tabs)
        self.inspector.show_tab(tab if tab in tabs else tabs[0])
        self.setEnabled(True)
        self.inspector.setEnabled(True)
        self._tools_changed()

    def refresh_parts_of(self, scene):
        self.scene = scene
        self.refresh_parts()

    def refresh_parts(self):
        """(Re)fill the list and summary — after loading or re-tessellating."""
        scene, m = self.scene, self.scene.model
        self.parts_section.header.findChild(QLabel, "SectionHeader").setText(
            f"{m.group_title}  ({len(scene.names)})")
        self.list.populate(scene)
        self.list.set_selected(scene.selected_parts)
        self.cfd_panel.refresh_names()                 # boundary list (renames)
        self.inflation_panel.refresh_names()           # walls list
        self._apply_filter(self.filter.text())

        n_faces = sum(p.n_cells for p in m.parts.values())
        kt = m.kind_title                              # "2D mesh", "CAD" stay as they are
        kt = kt if kt[0].isdigit() or kt.isupper() else kt.lower()
        if m.source is not None:                       # STEP, IGES, BREP: its parts
            n = len(scene.names)
            count = f"{n:,} {'part' if n == 1 else 'parts'}"
        elif m.n_cells:                                # CGNS, UGRID: the volume cells
            count = f"{m.n_cells:,} cells"
        else:
            count = f"{n_faces:,} {m.cell_word}"
        self.summary = f"{m.fmt} {kt} · {count}"
        if scene.can_retessellate:
            self.meshing_panel.refresh(n_faces)
        self._show_info(scene.selected_parts)

    # ---- selection (multi: ⌘/⇧-click in the list or in 3D) ---------------
    def show_selection(self, names):
        """Called by the scene after a click in the 3D view (list of names)."""
        names = [] if names is None else ([names] if isinstance(names, str) else list(names))
        if self.list.set_selected(names):             # a selected part was filtered out
            self.filter.clear()
            self.list.set_selected(names)
        self._show_info(names)
        if self.scene is not None and self.scene.elements.kind == "part":
            self.selected_panel.refresh()              # Part: the parts' field values

    def _elements_changed(self, scene):
        """Select ▾ picked or cleared: Info and Measure Selected follow; something picked
        opens Measure Selected (its Measure tab in front, when the inspector is shown)."""
        self._show_info(scene.selected_parts)
        self.selected_panel.refresh()
        if scene.elements.items and not self.inspector.isHidden():
            self.show_section("selected", expand=True)

    def _selection_changed(self, names):
        if self.scene:
            self.scene.set_selection(names)
            self._show_info(names)
            if self.scene.elements.kind == "part":
                self.selected_panel.refresh()          # Part: the parts' field values

    def _clear_selection(self):
        if self.scene:
            self.scene.elements.clear()
            self.scene.set_selection([], notify=True)

    def _show_info(self, names):
        names = [] if not names else ([names] if isinstance(names, str) else list(names))
        picked = self.scene.elements.describe() if self.scene else None
        if picked:                                            # Select ▾: nodes, edges, faces
            self.sel_label.setText(picked[0])
        elif self.scene:
            one, many = self.scene.model.item_words
            what = one if len(names) == 1 else many
            self.sel_label.setText(f"{len(names)} {what} selected")
        empty = not names and not picked                      # greyed, not hidden
        if self.sel_label.property("empty") != empty:
            self.sel_label.setProperty("empty", empty)
            self.sel_label.style().unpolish(self.sel_label)
            self.sel_label.style().polish(self.sel_label)
        self.sel_clear.setEnabled(not empty)
        if picked:
            self.info.setText(picked[1])
        elif self.scene and len(names) == 1:
            self.info.setText(f"{names[0]}\n{self.scene.info(names[0])}")
        elif self.scene and names:
            n = sum(self.scene.model.parts[x].n_cells for x in names)
            self.info.setText(f"{len(names)} selected\n{n:,} faces")
        else:
            self.info.setText(self.summary)

    def set_measuring(self, on):
        """View ▸ Measure (⇧⌘M): the Measure tab, its tool open — or closed."""
        if on:
            self.show_section("measure", expand=True)
        else:
            self.measure_section.set_expanded(False)

    # ---- mesh quality ----------------------------------------------
    def quality_failed(self):
        self.meshing_panel.failed()
        self.refresh_parts()

    # ---- list behaviour ----------------------------------------------
    def _visibility_changed(self, names, on):
        """Show / hide parts (the list's boxes, Hide in the menus): Edit ▸ Undo takes it back."""
        if not self.scene:
            return
        if self.changes is None:                       # (no window: tests of the sidebar alone)
            self.scene.set_visible(names, on, render=False)
            self.list.sync_checks(self.scene.visible)
            self.scene._after_visibility_change()
            return
        self.changes.visibility(names, on)

    def _set_all(self, on):
        if not self.scene:
            return
        if self.changes is None:
            self.scene.set_visible(list(self.scene.names), on, render=False)
            self._sync_checks()
            self.scene._after_visibility_change()
            return
        faces = on and self.scene.n_hidden_faces
        if all(v == on for v in self.scene.visible.values()) and not faces:
            return                                    # nothing to show / hide: no undo step
        st = self.changes.stack
        st.beginMacro("Show All" if on else "Hide All")
        self.changes.visibility(list(self.scene.names), on)
        if faces:                                     # hidden CAD faces too
            self.changes.faces({}, "Show Hidden Faces")
        st.endMacro()

    def _isolate(self, names):
        if not self.scene:
            return
        names = [names] if isinstance(names, str) else list(names)
        if self.changes is None:
            self.scene.isolate(names)
            self._sync_checks()
            return
        self.changes.isolate(names)
        self.scene.zoom_to(names)

    # ---- right-click menu (part list and 3D view) ------------------------
    # --- part colour ------------------------------------------------------
    # --- rename a part ---------------------------------------------------
    def _apply_filter(self, text=None):
        text = self.filter.text() if text is None else text
        s = self.scene.measure.unit_scale()[0] if self.scene is not None else 1.0
        self.list.apply_filter(text, s)

    # ---- the filter menu: order, colors, McMaster ---------------------------------------
    def _choices(self, menu, title, items, current, slot):
        """A gray header, then one-of-many checkable items: {key: QAction}."""
        head = menu.addAction(title)
        head.setEnabled(False)
        group = QActionGroup(self)
        group.setExclusive(True)
        acts = {}
        for key, text in items:
            a = QAction(text, self)
            a.setCheckable(True)
            a.setChecked(key == current)
            a.triggered.connect(lambda _=False, k=key: slot(k))
            group.addAction(a)
            menu.addAction(a)
            acts[key] = a
        return acts

    def _build_options(self):
        """The button right of the filter (SF Symbol line.3.horizontal.decrease), a menu:
        Sort By Name / Size / Volume, Reverse Order · Colors: File Color / Randomized
        Color · Isolate McMaster Parts. Kept for every file (settings "parts/…")."""
        st = settings()
        by = st.value("parts/sort", "name")
        by = by if by in ("name", "size", "volume") else "name"
        reverse = st.value("parts/reverse", False, type=bool)
        self._sort_start = (by, reverse)            # (the list is made after this row)
        self._mcmaster_start = st.value("parts/mcmaster", False, type=bool)
        mode = st.value("parts/colors", "file")
        self.color_mode = mode if mode in ("file", "random") else "file"
        menu = Menu(self)
        self.sort_actions = self._choices(
            menu, "Sort By", (("name", "Name"), ("size", "Size"), ("volume", "Volume")),
            by, self.set_sort)
        self.sort_reverse = QAction("Reverse Order", self)
        self.sort_reverse.setCheckable(True)
        self.sort_reverse.setChecked(reverse)
        self.sort_reverse.toggled.connect(lambda on: self.set_sort(reverse=on))
        menu.addAction(self.sort_reverse)
        menu.addSeparator()
        self.color_actions = self._choices(
            menu, "Colors", (("file", "File Color"), ("random", "Randomized Color")),
            self.color_mode, self.set_color_mode)
        menu.addSeparator()
        self.mcmaster_action = QAction("Isolate McMaster Parts", self)
        self.mcmaster_action.setCheckable(True)
        self.mcmaster_action.setChecked(self._mcmaster_start)
        self.mcmaster_action.toggled.connect(self.set_mcmaster)
        menu.addAction(self.mcmaster_action)
        b = QToolButton()
        b.setObjectName("FilterButton")
        b.setIcon(icon("filter_menu"))
        b.setToolTip("Filter Options")
        b.setAccessibleName("Filter Options")
        b.setPopupMode(QToolButton.InstantPopup)
        b.setIconSize(QSize(14, 14))
        b.setMenu(menu)
        self.options_button = b
        return b

    def set_color_mode(self, mode):
        """"file": the file's own colors (STEP), the palette for the others; "random":
        the palette for every part. Colors you chose stay."""
        self.color_mode = mode if mode in ("file", "random") else "file"
        self.color_actions[self.color_mode].setChecked(True)
        settings().setValue("parts/colors", self.color_mode)
        if self.scene is None:
            return
        for n in self.scene.set_color_mode(self.color_mode, render=False):
            self.list.set_color(n, self.scene.colors[n])
        self.cfd_panel.refresh_colors()                # Boundary menu dots
        self.inflation_panel.refresh_colors()          # Walls menu dots
        self.scene.p.render()

    def set_mcmaster(self, on):
        """Isolate McMaster Parts: all of them in one section on top (whatever the size /
        volume limits), or in their places like any part (default)."""
        self.list.mcmaster = bool(on)
        settings().setValue("parts/mcmaster", self.list.mcmaster)
        if self.scene is not None:
            self.refresh_parts()

    def set_sort(self, key=None, reverse=None):
        """Sort the parts list by "name", "size" (bounding-box diagonal) or "volume"."""
        if key is not None:
            self.list.sort_by = key
            self.sort_actions[key].setChecked(True)
        if reverse is not None:
            self.list.reverse = bool(reverse)
        st = settings()
        st.setValue("parts/sort", self.list.sort_by)
        st.setValue("parts/reverse", self.list.reverse)
        if self.scene is not None:
            self.refresh_parts()

    def _sync_checks(self):
        self.list.sync_checks(self.scene.visible)
