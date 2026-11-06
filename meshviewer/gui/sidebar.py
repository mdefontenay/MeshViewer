"""Side panel: Display · Mesh quality (STEP) · Section · Edit · Measure ·
Boundaries/Parts.

Talks only to a Scene. Selection works both ways: click a part in the 3D
view -> it is selected in the list; select it in the list -> highlighted in 3D.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QPalette
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMessageBox, QPushButton, QSizePolicy,
    QVBoxLayout, QWidget,
)

from .scene import Scene
from .icons import icon
from .edit_panel import EditPanel
from .measure_panel import MeasurePanel
from .section_panel import SectionPanel
from .part_tree import PartTree, mcmaster_number
from .widgets import Capsule, CollapsibleSection, Menu, NoWheelSlider, Switch


def open_mcmaster(part_number):
    QDesktopServices.openUrl(QUrl(f"https://www.mcmaster.com/{part_number}"))


def _divider():
    line = QFrame()
    line.setObjectName("Divider")
    line.setFixedHeight(1)
    return line


class Sidebar(QWidget):
    quality_requested = Signal(int)     # window re-tessellates in the background
    axes_changed = Signal(str)          # v2.21: Display ▸ Axes, saved app-wide by the window
    appearance_requested = Signal()     # v2.25: "Style… Appearance" link under Display
    renamed = Signal()                  # v2.26: a part was renamed (window: unsaved dot)

    # Display = one "Axes" choice + switches. (v2.22: parallel projection moved to
    # the toolbar; evenly spaced rows, no group gaps.)
    AXES = (("off", "Off"), ("axes", "Axes"), ("grid", "Grid"), ("both", "Both"))
    DISPLAY = [
        ("Bounding box",  "bbox",          "set_bbox"),         # v2.23: under Axes
        ("Mesh edges",    "mesh_edges",    "set_mesh_edges"),
        ("Feature edges", "feature_edges", "set_feature_edges"),
        ("Origin",        "origin",        "set_origin"),
        ("Shading",       "shading",       "set_shading"),      # v2.25: off = flat colours
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setMinimumWidth(270)
        self.scene: Scene | None = None
        self.summary = ""

        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 10, 12, 10)
        lay.setSpacing(8)
        self._lay = lay

        # ---- Display -----------------------------------------------------
        display = QWidget()
        dl = QVBoxLayout(display)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.setSpacing(5)
        # Axes: frame + numbers, grid lines, both, or nothing (was 3 separate switches)
        group = QActionGroup(self)
        group.setExclusive(True)
        self.axes_actions = {}
        for key, text in self.AXES:
            act = QAction(text, self)
            act.setCheckable(True)
            act.setData(key)
            group.addAction(act)
            self.axes_actions[key] = act
        self.axes_actions["axes"].setToolTip("Axis frame with numbers and titles")
        self.axes_actions["grid"].setToolTip("Grid lines behind the model, no numbers")
        self.axes_actions["both"].setToolTip("Axis frame, numbers and grid lines")
        group.triggered.connect(lambda act: self.axes_changed.emit(act.data()))
        row = QHBoxLayout()
        row.setContentsMargins(2, 1, 2, 1)
        row.addWidget(QLabel("Axes"))
        row.addStretch(1)
        row.addWidget(Capsule(list(self.axes_actions.values()), name="Segmented"))
        dl.addLayout(row)

        self.switches = {}
        for label, key, method in self.DISPLAY:
            row = QHBoxLayout()
            row.setContentsMargins(2, 1, 2, 1)
            lbl = QLabel(label)
            if key == "origin":
                lbl.setToolTip("Marker at (0, 0, 0) with X / Y / Z arrows")
            elif key == "shading":
                lbl.setToolTip("Light and shadow on the model. Off: flat part colours")
            row.addWidget(lbl)
            row.addStretch(1)
            sw = Switch()
            sw.toggled.connect(lambda on, m=method: self.scene and getattr(self.scene, m)(on))
            row.addWidget(sw)
            dl.addLayout(row)
            self.switches[key] = sw
        # v2.25: Display = WHAT is shown (on / off); Appearance = HOW it looks
        # (colours, sizes, thickness), the same in every window. Say so here.
        row = QHBoxLayout()
        row.setContentsMargins(2, 3, 2, 0)
        hint = QLabel("Colours, sizes, line thickness:")
        hint.setObjectName("InfoLine")
        row.addWidget(hint)
        link = QPushButton("Appearance…")
        link.setObjectName("LinkButton")
        link.setFlat(True)
        link.setCursor(Qt.PointingHandCursor)
        link.setToolTip("How things look, the same in every window (⌘,)")
        link.clicked.connect(self.appearance_requested.emit)
        row.addWidget(link)
        row.addStretch(1)
        dl.addLayout(row)
        lay.addWidget(CollapsibleSection("Display", display, "display"))

        # ---- Mesh quality (STEP only) -------------------------------------
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
        self.quality_section = CollapsibleSection("Mesh quality", quality, "quality",
                                                  trailing=self.quality_value,
                                                  remember=False, start_open=False)
        self.quality_box = QWidget()                # divider + section, hidden if not STEP
        qb = QVBoxLayout(self.quality_box)
        qb.setContentsMargins(0, 0, 0, 0)
        qb.setSpacing(8)
        qb.addWidget(_divider())
        qb.addWidget(self.quality_section)
        lay.addWidget(self.quality_box)
        self.quality_box.setVisible(False)

        # ---- Section ---------------------------------------------------------
        lay.addWidget(_divider())
        self.section_panel = SectionPanel()
        self.section_section = CollapsibleSection("Section", self.section_panel, "section",
                                                  trailing=self.section_panel.enable,
                                                  remember=False, start_open=False)
        lay.addWidget(self.section_section)
        # Switching the section on opens its controls (v2.16); off closes them (v2.25)
        self.section_panel.enable.toggled.connect(self.section_section.set_expanded)
        lay.addWidget(_divider())

        # ---- Edit: rotate / mirror / move (v2.24: always here, starts closed) ----
        self.edit_panel = EditPanel()
        self.edit_section = CollapsibleSection("Edit", self.edit_panel, "edit",
                                               remember=False, start_open=False)
        lay.addWidget(self.edit_section)
        lay.addWidget(_divider())

        # ---- Measure: measuring is active while this section is open --------
        self.measure_panel = MeasurePanel()
        self.measure_section = CollapsibleSection("Measure", self.measure_panel, "measure",
                                                  remember=False, start_open=False)
        self.measure_section.toggled.connect(self.measure_panel.activate)
        lay.addWidget(self.measure_section)
        lay.addWidget(_divider())

        # ---- Boundaries / Parts -----------------------------------------
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

        # "3 parts selected · Clear" — NEW (v2.10): always shown (greyed at 0), so
        # selecting something no longer pushes the list down.
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

        # a tree — parts sharing a base name fold into one group row.
        self.list = PartTree()
        self.list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.list.setMinimumHeight(140)
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
        self.parts_section.toggled.connect(self._parts_toggled)
        lay.addWidget(self.parts_section, 1)
        self._tail = QWidget()                      # takes the space when Parts is closed
        lay.addWidget(self._tail, 0)

        self.info = QLabel("")
        self.info.setObjectName("InfoLine")
        self.info.setWordWrap(True)
        lay.addWidget(self.info)
        self._parts_toggled(self.parts_section.expanded)
        self.setEnabled(False)

    def _parts_toggled(self, expanded):
        self._lay.setStretchFactor(self.parts_section, 1 if expanded else 0)
        self._lay.setStretchFactor(self._tail, 0 if expanded else 1)

    def set_axes_mode(self, mode):
        """Show the saved Axes choice (no signal)."""
        act = self.axes_actions.get(mode) or self.axes_actions["both"]
        act.setChecked(True)

    # ---- binding to a scene -------------------------------------------
    def bind(self, scene: Scene):
        self.scene = scene
        scene.on_pick = self.show_selection
        for key, sw in self.switches.items():
            Switch.set_silently(sw, scene.state[key])
        self.section_panel.bind(scene.section)
        self.edit_panel.bind(scene)
        self.measure_panel.bind(scene)

        m = scene.model
        self.quality_box.setVisible(scene.can_retessellate)
        if scene.can_retessellate:
            self.quality.blockSignals(True)
            self.quality.setRange(0, len(m.quality_levels) - 1)
            self.quality.setValue(m.quality)
            self.quality.blockSignals(False)
        self.refresh_parts()
        self.setEnabled(True)

    def refresh_parts(self):
        """(Re)fill the list and summary — after loading or re-tessellating."""
        scene, m = self.scene, self.scene.model
        self.parts_section.header.findChild(QLabel, "SectionHeader").setText(
            f"{m.group_title}  ({len(scene.names)})")
        self.list.populate(scene)
        self.list.set_selected(scene.selected_parts)
        self._apply_filter(self.filter.text())

        n_faces = sum(p.n_cells for p in m.parts.values())
        self.summary = f"{m.fmt} {m.kind_title.lower()} · {n_faces:,} faces"
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
            self.scene.set_selection([], notify=True)

    def _show_info(self, names):
        names = [] if not names else ([names] if isinstance(names, str) else list(names))
        if self.scene:
            what = self.scene.model.group_title.lower()
            if len(names) == 1:
                what = what[:-3] + "y" if what.endswith("ies") else what.rstrip("s")
            self.sel_label.setText(f"{len(names)} {what} selected")
        empty = not names                                     # greyed, not hidden
        if self.sel_label.property("empty") != empty:
            self.sel_label.setProperty("empty", empty)
            self.sel_label.style().unpolish(self.sel_label)
            self.sel_label.style().polish(self.sel_label)
        self.sel_clear.setEnabled(not empty)
        if self.scene and len(names) == 1:
            self.info.setText(f"{names[0]}\n{self.scene.info(names[0])}")
        elif self.scene and names:
            n = sum(self.scene.model.parts[x].n_cells for x in names)
            self.info.setText(f"{len(names)} selected\n{n:,} faces")
        else:
            self.info.setText(self.summary)

    def set_measuring(self, on):
        self.measure_section.set_expanded(on)

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
        if not self.scene:
            return
        for n in names:
            self.scene.set_visible(n, on, render=False)
        self.list.sync_checks(self.scene.visible)
        self.scene._after_visibility_change()

    def _set_all(self, on):
        if self.scene:
            self._visibility_changed(list(self.scene.names), on)

    def _isolate(self, names):
        if self.scene:
            self.scene.isolate(names)
            self._sync_checks()

    # ---- right-click menu (part list and 3D view) ------------------------
    def part_menu(self, names, clicked, global_pos):
        """names: what Hide / Isolate / Zoom act on (the selection when right-clicking
        inside it); clicked: the row / part under the cursor (McMaster search)."""
        if not self.scene:
            return
        names = [n for n in names if n in self.scene.visible]
        clicked = [n for n in clicked if n in self.scene.visible]
        menu = Menu(self)
        if names:
            title = names[0] if len(names) == 1 else f"{len(names)} parts"
            head = menu.addAction(title)
            head.setEnabled(False)
            what = "" if len(names) == 1 else f" {len(names)} Parts"
            menu.addAction(f"Hide{what}", lambda: self._visibility_changed(names, False))
            menu.addAction(f"Isolate{what}", lambda: self._isolate(names))
            menu.addAction("Zoom To", lambda: self.scene.zoom_to(names))
            if len(names) == 1 and clicked == names:           # v2.26
                menu.addAction("Rename…", lambda: self.rename(names[0]))
            # McMaster-Carr parts -> open their catalogue page
            # NEW (v2.11): only the part / group that was right-clicked, not the selection
            numbers = sorted({mcmaster_number(n) for n in clicked} - {None})
            if len(numbers) == 1:
                menu.addSeparator()
                menu.addAction(f"Search in McMaster  ({numbers[0]})",
                               lambda pn=numbers[0]: open_mcmaster(pn))
            elif numbers:
                menu.addSeparator()
                sub = Menu(menu)
                sub.setTitle("Search in McMaster")
                for pn in numbers[:15]:
                    sub.addAction(pn, lambda pn=pn: open_mcmaster(pn))
                menu.addMenu(sub)
            menu.addSeparator()
        menu.addAction("Show All", lambda: self._set_all(True))
        menu.addAction("Fit View", self.scene.fit)
        menu.exec(global_pos)
        self.scene.end_stuck_drag()            # no zoom mode left behind

    # ---- NEW (v2.26): rename a part ---------------------------------------------------
    def rename(self, name):
        """Edit the name in the list (or, with the sidebar hidden, in a small dialog)."""
        if not self.scene:
            return
        if self.isVisible():
            self.parts_section.set_expanded(True)
            if self.list.start_rename(name):
                return
            self.filter.clear()                       # filtered out: show it, try again
            if self.list.start_rename(name):
                return
        new, ok = QInputDialog.getText(self.window(), "Rename", "New name:", text=name)
        if ok:
            self._rename(name, new)

    def _rename(self, old, new):
        new = new.strip()
        if not self.scene or not new or new == old:
            return
        if new in self.scene.model.parts:
            QMessageBox.warning(self.window(), "Rename",
                                f"There is already a {self._one_part()} named “{new}”.")
            return
        if self.scene.rename_part(old, new):
            self.refresh_parts()
            self.renamed.emit()

    def _one_part(self):
        what = self.scene.model.group_title.lower()
        return what[:-3] + "y" if what.endswith("ies") else what.rstrip("s")

    def _apply_filter(self, text):
        self.list.apply_filter(text)

    def _sync_checks(self):
        self.list.sync_checks(self.scene.visible)
