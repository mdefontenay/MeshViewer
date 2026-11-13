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

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from meshviewer.gui.icons import icon
from meshviewer.gui.inspector import Inspector
from meshviewer.gui.panels.cfd import CfdPanel
from meshviewer.gui.panels.edit import EditPanel
from meshviewer.gui.panels.inflation import InflationPanel
from meshviewer.gui.panels.info import InfoPanel
from meshviewer.gui.panels.measure import MeasurePanel
from meshviewer.gui.panels.parts import PartTree
from meshviewer.gui.panels.plots import PlotsPanel
from meshviewer.gui.panels.quality import QualityPanel
from meshviewer.gui.panels.results import ResultsPanel
from meshviewer.gui.panels.section import SectionPanel
from meshviewer.gui.sections import BY_KEY, default_open, default_tab
from meshviewer.gui.sidebar_layout import Box, divider
from meshviewer.gui.sidebar_menu import PartMenu
from meshviewer.gui.widgets import CollapsibleSection, NoWheelSlider
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
            box.divider = divider()                  # between this tool and the one above
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

        self.results_panel = ResultsPanel()
        self.results_section = self._add("results", self.results_panel)

        self.plots_panel = PlotsPanel()                # plots -> tabs under the view
        self.plots_section = self._add("plots", self.plots_panel, card=False)

    def _build_quality(self):
        quality = QWidget()
        ql = QVBoxLayout(quality)
        ql.setContentsMargins(2, 0, 2, 0)
        ql.setSpacing(4)
        row = QHBoxLayout()
        coarse, fine = QLabel("Coarse"), QLabel("Fine")
        coarse.setObjectName("SmallLabel")
        fine.setObjectName("SmallLabel")
        self.quality = NoWheelSlider(Qt.Horizontal)
        self.quality.setPageStep(1)
        self.quality.setToolTip("How finely curved CAD faces are triangulated for display")
        self.quality.valueChanged.connect(self._quality_moved)
        self.quality.sliderReleased.connect(self._quality_released)
        row.addWidget(coarse)
        row.addWidget(self.quality, 1)
        row.addWidget(fine)
        ql.addLayout(row)
        self.quality_label = QLabel("")
        self.quality_label.setObjectName("InfoLine")
        ql.addWidget(self.quality_label)
        self.quality_value = QLabel("")             # level name, in the header
        self.quality_value.setObjectName("ValueLabel")
        self.quality_section = self._add("quality", quality, trailing=self.quality_value)

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
        """Grey note instead of the controls where a section doesn't fit the file."""
        for key, box in self._boxes.items():
            reason = BY_KEY[key].unavailable(scene)
            for sec, note, panel, trailing in box.parts:
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
        self.filter.setPlaceholderText("Filter")
        self.filter.setClearButtonEnabled(True)
        self.filter.addAction(icon("search", QPalette.PlaceholderText), QLineEdit.LeadingPosition)
        self.filter.textChanged.connect(self._apply_filter)
        pl.addWidget(self.filter)

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
        self.sel_clear = QPushButton("Clear")
        self.sel_clear.setObjectName("LinkButton")
        self.sel_clear.setCursor(Qt.PointingHandCursor)
        self.sel_clear.setFlat(True)
        self.sel_clear.clicked.connect(self._clear_selection)
        sbl.addWidget(self.sel_clear)
        pl.addWidget(self.sel_bar)

        # a tree — parts sharing a base name fold into one group row
        self.list = PartTree()
        self.list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.list.setMinimumHeight(24)                # drag the line above down to here
        self.list.visibility_changed.connect(self._visibility_changed)
        self.list.selection_changed.connect(self._selection_changed)
        self.list.zoom_requested.connect(lambda names: self.scene and self.scene.zoom_to(names))
        self.list.isolate_requested.connect(self._isolate)
        self.list.context_requested.connect(self.part_menu)
        self.list.rename_requested.connect(self._rename)
        pl.addWidget(self.list, 1)

        links = QWidget()
        ll = QHBoxLayout(links)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(8)
        for text, on in (("Show All", True), ("Hide All", False)):
            b = QPushButton(text)
            b.setObjectName("LinkButton")
            b.setCursor(Qt.PointingHandCursor)
            b.setFlat(True)
            b.clicked.connect(lambda _=False, v=on: self._set_all(v))
            ll.addWidget(b)
        self.parts_section = CollapsibleSection("Parts", parts, "parts", trailing=links)
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
        scene.elements.on_changed = lambda: self._show_info(scene.selected_parts)
        self.section_panel.bind(scene.section)
        self.edit_panel.bind(scene)
        self.measure_panel.bind(scene)
        self.cell_panel.bind(scene)
        self.info_panel.bind(scene)
        self.cfd_panel.bind(scene)
        self.results_panel.bind(scene)
        self.plots_panel.bind(scene)
        self.inflation_panel.bind(scene)
        self._apply_support(scene)

        m = scene.model
        self._no_parts = m.file_type == "drawing"   # drawings: one color, no layer list
        self.parts_section.setVisible(not self._no_parts)
        if scene.can_retessellate:
            self.quality.blockSignals(True)
            self.quality.setRange(0, len(m.quality_levels) - 1)
            self.quality.setValue(m.quality)
            self.quality.blockSignals(False)
        self.refresh_parts_of(scene)

        state = getattr(scene, "inspector_state", None) or {}
        tab = state.get("tab") or default_tab(scene)
        opened = state.get("open") if "open" in state else default_open(scene)
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
        self.inspector.show_tab(tab if tab in ("view", "measure", "analyze") else "view")
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
        self.summary = f"{m.fmt} {kt} · {n_faces:,} {m.cell_word}"
        if scene.can_retessellate:
            self.quality_value.setText(m.quality_levels[m.quality])
            self.quality_label.setText(f"{n_faces:,} triangles")
            self.quality.setEnabled(True)
        self._show_info(scene.selected_parts)

    # ---- selection (multi: ⌘/⇧-click in the list or in 3D) ---------------
    def show_selection(self, names):
        """Called by the scene after a click in the 3D view (list of names)."""
        names = [] if names is None else ([names] if isinstance(names, str) else list(names))
        if self.list.set_selected(names):             # a selected part was filtered out
            self.filter.clear()
            self.list.set_selected(names)
        self._show_info(names)

    def _selection_changed(self, names):
        if self.scene:
            self.scene.set_selection(names)
            self._show_info(names)

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
    def _quality_moved(self, level):
        if self.scene and not self.quality.isSliderDown():   # keyboard / click on track
            self._request_quality(level)
        elif self.scene:
            self.quality_value.setText(self.scene.model.quality_levels[level])

    def _quality_released(self):
        self._request_quality(self.quality.value())

    def _request_quality(self, level):
        if level != self.scene.model.quality:
            self.quality.setEnabled(False)
            self.quality_value.setText(self.scene.model.quality_levels[level])
            self.quality_label.setText("Re-meshing…")
            self.quality_requested.emit(level)

    def quality_failed(self):
        self.quality.blockSignals(True)
        self.quality.setValue(self.scene.model.quality)
        self.quality.blockSignals(False)
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
    def _apply_filter(self, text):
        self.list.apply_filter(text)

    def _sync_checks(self):
        self.list.sync_checks(self.scene.visible)
