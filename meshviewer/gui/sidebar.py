"""Side panel: | icon bar | sections (scroll if needed) + Boundaries/Parts list |

The icon bar shows or hides each section (gui/sections.py lists them). Every section
is there for every file; one that doesn't apply says why in grey. Which are on is
remembered per file (scene.sidebar_sections), defaults on first open. The parts list
is always shown. Talks only to a Scene. Selection works both ways: click a part in
the 3D view -> it is selected in the list; select it in the list -> highlighted.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QSettings, QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QAction, QColor, QDesktopServices, QPainter, QPalette
from PySide6.QtWidgets import (
    QColorDialog, QFrame, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMessageBox, QPushButton,
    QScrollArea, QSizePolicy, QSplitter, QSplitterHandle, QToolButton, QVBoxLayout, QWidget,
)

from meshviewer.render.scene import Scene
from meshviewer.gui.icons import icon
from meshviewer.gui.panels.edit import EditPanel
from meshviewer.gui.panels.cfd import CfdPanel
from meshviewer.gui.panels.inflation import InflationPanel
from meshviewer.gui.panels.plots import PlotsPanel
from meshviewer.gui.panels.results import ResultsPanel
from meshviewer.gui.panels.info import InfoPanel
from meshviewer.gui.panels.measure import MeasurePanel
from meshviewer.gui.panels.quality import QualityPanel
from meshviewer.gui.panels.section import SectionPanel
from meshviewer.gui.panels.parts import PartTree, is_line_part, mcmaster_number
from meshviewer.gui.sections import BY_KEY, SECTIONS, default_sections
from meshviewer.gui.widgets import CollapsibleSection, Menu, NoWheelSlider


def open_mcmaster(part_number):
    QDesktopServices.openUrl(QUrl(f"https://www.mcmaster.com/{part_number}"))


def _divider():
    line = QFrame()
    line.setObjectName("Divider")
    line.setFixedHeight(1)
    return line


class _FitScroll(QScrollArea):
    """A scroll area exactly as tall as its content, so no empty scrollbar track shows;
    it only shrinks (and scrolls) when the window is too short for everything."""

    def __init__(self, inner):
        super().__init__()
        self.setObjectName("SideScroll")
        self.setWidget(inner)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)   # sidebar narrower than a section
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        inner.installEventFilter(self)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(0)
        self._timer.timeout.connect(self._fit)

    def refit(self):
        """Match the content's height again (soon: after the layouts settle)."""
        self._timer.start()

    def content_height(self):
        lay = self.widget().layout()
        w = max(self.viewport().width(), self.widget().minimumSizeHint().width(), 50)
        h = lay.totalHeightForWidth(w) if lay.hasHeightForWidth() else -1
        h = h if h >= 0 else self.widget().sizeHint().height()
        if self.widget().minimumSizeHint().width() > self.viewport().width():
            h += self.horizontalScrollBar().sizeHint().height()   # room for the side scrollbar
        return h

    def _fit(self):
        h = self.content_height()
        if self.maximumHeight() != h or self.height() < h:
            self.setMaximumHeight(h)
            self.updateGeometry()               # the layout caches the size hint
        QTimer.singleShot(30, self._bar)

    def _bar(self):
        """Scrollbar only when the content really doesn't fit (checked after the layout
        settles — not while a section is opening)."""
        need = self.height() < self.content_height() - 1
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded if need else Qt.ScrollBarAlwaysOff)

    def eventFilter(self, obj, ev):
        if ev.type() in (QEvent.LayoutRequest, QEvent.Show):
            self.refit()
        return False

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self.refit()                               # wrapping labels change height
        self._bar()

    def showEvent(self, ev):
        super().showEvent(ev)
        self.refit()

    def sizeHint(self):
        return QSize(260, self.content_height())

    def minimumSizeHint(self):
        return QSize(244, min(120, self.content_height()))   # narrower than a section: clipped


class _Handle(QSplitterHandle):
    """The line above the parts list: full width, 1 px, easy to grab (7 px)."""

    def paintEvent(self, ev):
        p = QPainter(self)
        c = self.palette().color(QPalette.WindowText)
        c.setAlphaF(0.12)
        p.fillRect(0, 0, self.width(), 1, c)          # at the top: the sections end on it


class _Split(QSplitter):
    def __init__(self):
        super().__init__(Qt.Vertical)
        self.setHandleWidth(7)
        self.setChildrenCollapsible(False)

    def createHandle(self):
        return _Handle(self.orientation(), self)

    def setHandleEnabled(self, on):
        h = self.handle(1)
        if h is not None:
            h.setEnabled(on)
            h.setCursor(Qt.SplitVCursor if on else Qt.ArrowCursor)


class _Box:
    """One section in the sidebar: its widget (section + divider), and per
    CollapsibleSection inside it the grey note, the panel and the header switch."""

    def __init__(self, widget):
        self.widget = widget
        self.divider = None
        self.parts = []                 # (section, note, panel, trailing)


class Sidebar(QWidget):
    quality_requested = Signal(int)     # window re-tessellates in the background
    renamed = Signal()                  # a part was renamed (window: unsaved dot)
    sections_changed = Signal()         # a section was shown / hidden (icon bar)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.scene: Scene | None = None
        self.summary = ""
        self._boxes: dict[str, _Box] = {}

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.icon_bar = QFrame()
        self.icon_bar.setObjectName("IconBar")
        self.icon_bar.setAttribute(Qt.WA_StyledBackground, True)
        self.icon_bar.setFixedWidth(44)
        ib = QVBoxLayout(self.icon_bar)
        ib.setContentsMargins(6, 10, 6, 10)
        ib.setSpacing(4)
        outer.addWidget(self.icon_bar)

        # sections on top; below a line you can drag, the parts list (kept at the bottom)
        self.split = _Split()
        self.split.setObjectName("SideMain")
        outer.addWidget(self.split, 1)
        top = QWidget()                                # the sections
        top.setObjectName("SideTop")
        lay = QVBoxLayout(top)
        lay.setContentsMargins(14, 10, 0, 0)           # sections end at the line and the edge
        lay.setSpacing(8)
        self.split.addWidget(top)

        tools = QWidget()
        tools.setObjectName("SideTools")
        self._tools_lay = QVBoxLayout(tools)
        self._tools_lay.setContentsMargins(0, 0, 12, 0)   # the scrollbar sits at the edge
        self._tools_lay.setSpacing(8)
        self.tools = _FitScroll(tools)
        lay.addWidget(self.tools)
        lay.addStretch(1)

        self._build_sections()
        self.section_actions = {}              # key -> checkable QAction (icon bar, menus)
        self.icon_actions = {}                 # analysis tools: icon in the bar or not
        self._icon_buttons = {}
        hidden = set(QSettings("local", "Mesh Viewer").value("sidebar/hidden_icons", [],
                                                             type=list) or [])
        self._analysis_sep = None                   # grey line above the analysis tools
        for spec in SECTIONS:
            if spec.analysis and self._analysis_sep is None:
                self._analysis_sep = QWidget()
                sl = QVBoxLayout(self._analysis_sep)
                sl.setContentsMargins(0, 4, 0, 4)
                line = QFrame()
                line.setObjectName("Divider")
                line.setFixedSize(20, 1)
                sl.addWidget(line, 0, Qt.AlignHCenter)
                ib.addWidget(self._analysis_sep, 0, Qt.AlignHCenter)
            a = QAction(icon(spec.icon, on_accent=True), spec.title, self)
            a.setCheckable(True)
            a.setToolTip(spec.title)
            a.toggled.connect(lambda on, k=spec.key: self._section_toggled(k, on))
            self.section_actions[spec.key] = a
            if spec.analysis:
                v = QAction(spec.title, self)
                v.setCheckable(True)
                v.setChecked(spec.key not in hidden)
                v.toggled.connect(lambda on, k=spec.key: self.set_icon_shown(k, on))
                self.icon_actions[spec.key] = v
                a.setVisible(spec.key not in hidden)
            b = QToolButton()
            self._icon_buttons[spec.key] = b
            b.setVisible(a.isVisible())
            b.setDefaultAction(a)
            b.setAutoRaise(True)
            b.setFocusPolicy(Qt.NoFocus)
            b.setFixedSize(32, 32)
            b.setIconSize(QSize(18, 18))
            ib.addWidget(b, 0, Qt.AlignHCenter)
        # + : which analysis tools have an icon in the bar
        sep = QFrame()
        sep.setObjectName("Divider")
        sep.setFixedSize(20, 1)
        ib.addSpacing(4)
        ib.addWidget(sep, 0, Qt.AlignHCenter)
        ib.addSpacing(4)
        self.add_button = QToolButton()
        self.add_button.setIcon(icon("plus"))
        self.add_button.setToolTip("Analysis Tools")
        self.add_button.setAutoRaise(True)
        self.add_button.setFocusPolicy(Qt.NoFocus)
        self.add_button.setFixedSize(32, 32)
        self.add_button.setIconSize(QSize(18, 18))
        self.add_button.setPopupMode(QToolButton.InstantPopup)
        self.add_button.setStyleSheet("QToolButton::menu-indicator { image: none; width: 0; }")
        menu = Menu(self)
        head = menu.addAction("Analysis Tools in the Sidebar")
        head.setEnabled(False)
        for v in self.icon_actions.values():
            menu.addAction(v)
        self.add_button.setMenu(menu)
        ib.addWidget(self.add_button, 0, Qt.AlignHCenter)
        ib.addStretch(1)
        self._sync_analysis_sep()
        for box in self._boxes.values():
            box.widget.setVisible(False)

        bottom = QWidget()
        bottom.setObjectName("SideBottom")
        bl = QVBoxLayout(bottom)
        bl.setContentsMargins(14, 6, 12, 10)
        bl.setSpacing(8)
        self._bottom = bottom
        self.split.addWidget(bottom)
        self.split.setStretchFactor(0, 1)             # a taller window: more room on top
        self.split.setStretchFactor(1, 0)
        self.split.setCollapsible(0, False)
        self.split.setCollapsible(1, False)
        self.split.splitterMoved.connect(self._parts_moved)
        self._build_parts(bl)
        self.setEnabled(False)

    # ---- the sections -----------------------------------------------------------------
    def _add(self, key, panel, trailing=None, title=None, card=True):
        """Put panel in a CollapsibleSection of section `key` (several for "cfd"), on a
        grey card (card=False: the panel draws its own cards, e.g. Plots)."""
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
            box = self._boxes[key] = _Box(w)
            self._tools_lay.addWidget(w)
            box.divider = _divider()                  # between this section and the one above
            bl.addWidget(box.divider)
            bl.addWidget(sec)
        else:
            box.widget.layout().addWidget(sec)
        box.parts.append((sec, note, panel, trailing))
        sec.toggled.connect(lambda _on: self.tools.refit())
        return sec

    def _build_sections(self):
        self.info_panel = InfoPanel()
        self.info_section = self._add("info", self.info_panel)
        self.info_section.toggled.connect(self.info_panel.activate)
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
        self.measure_section.toggled.connect(self.measure_panel.activate)

        # CFD: the y+ estimate for meshes, CFD mode (inflation layers) for CAD files
        self.cfd_panel = CfdPanel()
        self.cfd_section = self._add("cfd", self.cfd_panel)
        self.cfd_section.toggled.connect(self.cfd_panel.activate)
        self.inflation_panel = InflationPanel()
        self.inflation_section = self._add("cfd", self.inflation_panel,
                                           trailing=self.inflation_panel.enable,
                                           title="CFD mode")
        self.inflation_panel.enable.toggled.connect(self.inflation_section.set_expanded)

        self.cell_panel = QualityPanel()
        self.cell_section = self._add("cells", self.cell_panel)
        self.cell_section.toggled.connect(self.cell_panel.activate)
        self.cell_panel.wants_section.connect(self._section_for_colors)
        self.cell_panel.computed.connect(self.info_panel.refresh)    # volume row
        self.cfd_panel.measured.connect(self.info_panel.refresh)     # volume row

        self.results_panel = ResultsPanel()
        self.results_section = self._add("results", self.results_panel)

        self.plots_panel = PlotsPanel()                # measurements -> tabs under the view
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

    def _section_toggled(self, key, on):
        """Icon clicked: show the section closed, or hide it (closing it first)."""
        box = self._boxes[key]
        if key == "section":
            self._section_plane(on)
        elif key == "cfd":
            self._cfd_switches(on)
        if not on:
            for sec, *_ in box.parts:
                sec.set_expanded(False)
        box.widget.setVisible(on)
        if self.scene is not None:
            self.scene.sidebar_sections = self.shown_sections()
        self._update_dividers()
        self.tools.refit()
        self.sections_changed.emit()

    def _section_plane(self, on):
        """Hiding Section switches the plane off; showing it again puts back what it was."""
        sc, sw = self.scene, self.section_panel.enable
        if sc is None:
            return
        if not on:
            sc.section_restore = sw.isChecked()
            if sw.isChecked():
                sw.setChecked(False)
        elif getattr(sc, "section_restore", False) and not sw.isChecked():
            sc.section_restore = False
            sw.setChecked(True)
            self.section_section.set_expanded(False)        # closed at first

    def _cfd_switches(self, on):
        """Hiding CFD switches CFD mode (CAD) or the flow vectors and y+ colours (meshes)
        off; showing it again switches back on what was on. The inputs stay as they are."""
        sc = self.scene
        if sc is None:
            return
        sws = {"mode": self.inflation_panel.enable, "vectors": self.cfd_panel.vectors,
               "colour": self.cfd_panel.colour, "mode_vectors": self.inflation_panel.vectors}
        if not on:
            sc.cfd_restore = [k for k, sw in sws.items() if sw.isChecked()]
            for k in sc.cfd_restore:
                sws[k].setChecked(False)
        else:
            for k in getattr(sc, "cfd_restore", None) or []:
                if not sws[k].isChecked():
                    sws[k].setChecked(True)
            sc.cfd_restore = []
            for sec, *_ in self._boxes["cfd"].parts:
                sec.set_expanded(False)                   # closed at first

    def set_icon_shown(self, key, on):
        """Analysis Tools menu: the tool's icon in the bar or not (hidden: section too)."""
        a = self.section_actions[key]
        if not on and a.isChecked():
            a.setChecked(False)
        a.setVisible(on)
        self._icon_buttons[key].setVisible(on)
        if self.icon_actions[key].isChecked() != on:
            self.icon_actions[key].setChecked(on)
        self._sync_analysis_sep()
        st = QSettings("local", "Mesh Viewer")
        hidden = [k for k, v in self.icon_actions.items() if not v.isChecked()]
        st.setValue("sidebar/hidden_icons", hidden)

    def _sync_analysis_sep(self):
        """The line above the analysis tools: only when one of them has an icon."""
        if self._analysis_sep is not None:
            self._analysis_sep.setVisible(any(v.isChecked() for v in self.icon_actions.values()))

    def _update_dividers(self):
        first = True
        for box in self._boxes.values():
            if box.widget.isVisibleTo(self):
                box.divider.setVisible(not first)
                first = False

    def shown_sections(self):
        return [k for k, a in self.section_actions.items() if a.isChecked()]

    def show_section(self, key, on=True, expand=False):
        """Show (or hide) a section, as if its icon was clicked; expand: open it too."""
        a = self.section_actions[key]
        if on and key in self.icon_actions and not self.icon_actions[key].isChecked():
            self.set_icon_shown(key, True)
        if a.isChecked() != on:
            a.setChecked(on)
        if on and expand:
            for sec, *_ in self._boxes[key].parts:
                if sec.isVisibleTo(self._boxes[key].widget):
                    sec.set_expanded(True)

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
        self.parts_section.toggled.connect(self._parts_toggled)
        lay.addWidget(self.parts_section, 1)

        self.info = QLabel("")
        self.info.setObjectName("InfoLine")
        self.info.setWordWrap(True)
        lay.addWidget(self.info)
        self._parts_toggled(self.parts_section.expanded)

    def _parts_toggled(self, expanded):
        """Open: the list at the bottom, as tall as last time (drag the line above it).
        Closed: only its header, at the bottom."""
        b = self._bottom
        if getattr(self, "_no_parts", False):         # drawings: no layer list
            b.setMaximumHeight(b.sizeHint().height())
            self.split.setHandleEnabled(False)
            QTimer.singleShot(0, self._place_parts)
            return
        if not expanded:
            b.setMaximumHeight(b.sizeHint().height())
            self.split.setHandleEnabled(False)
        else:
            b.setMaximumHeight(16777215)
            self.split.setHandleEnabled(True)
        QTimer.singleShot(0, self._place_parts)

    def _place_parts(self):
        total = sum(self.split.sizes())
        if total <= 0:
            return
        if self.parts_section.expanded and not getattr(self, "_no_parts", False):
            h = QSettings("local", "Mesh Viewer").value("sidebar/parts_height", 280, type=int)
        else:
            h = self._bottom.sizeHint().height()
        h = max(min(h, total - 60), self._bottom.minimumSizeHint().height())
        self.split.setSizes([total - h, h])

    def _parts_moved(self, *_):
        if self.parts_section.expanded and not getattr(self, "_no_parts", False):
            QSettings("local", "Mesh Viewer").setValue("sidebar/parts_height",
                                                       self.split.sizes()[1])

    def showEvent(self, ev):
        super().showEvent(ev)
        QTimer.singleShot(0, self._place_parts)

    # ---- binding to a scene -------------------------------------------
    def bind(self, scene: Scene):
        self.scene = None                           # no saving while setting up
        scene.on_pick = self.show_selection
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
        self._no_parts = m.file_type == "drawing"   # drawings: one colour, no layer list
        self.parts_section.setVisible(not self._no_parts)
        self._parts_toggled(self.parts_section.expanded)
        if scene.can_retessellate:
            self.quality.blockSignals(True)
            self.quality.setRange(0, len(m.quality_levels) - 1)
            self.quality.setValue(m.quality)
            self.quality.blockSignals(False)
        self.scene = scene
        self.refresh_parts()

        on = scene.sidebar_sections
        if on is None:                              # first time this file is opened
            on = default_sections(scene)
        on = [k for k in on if self.section_actions[k].isVisible() or k not in self.icon_actions]
        for key, a in self.section_actions.items():
            a.blockSignals(True)
            a.setChecked(key in on)
            a.blockSignals(False)
            self._boxes[key].widget.setVisible(key in on)
        for key, box in self._boxes.items():         # open what is shown, close the rest
            for sec, *_ in box.parts:
                if not sec.isVisibleTo(box.widget):
                    continue
                if key == "section":                  # closed, unless the plane is on
                    sec.set_expanded(key in on and scene.section.enabled)
                elif key == "cfd" and sec is self.inflation_section:
                    sec.set_expanded(key in on and self.inflation_panel.enabled)
                else:
                    sec.set_expanded(False)
        scene.sidebar_sections = self.shown_sections()
        self._update_dividers()
        self.setEnabled(True)
        self.tools.refit()
        self.sections_changed.emit()

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
            self.scene.set_selection([], notify=True)

    def _show_info(self, names):
        names = [] if not names else ([names] if isinstance(names, str) else list(names))
        if self.scene:
            one, many = self.scene.model.item_words
            what = one if len(names) == 1 else many
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
        if not self.scene:
            return
        for n in names:
            self.scene.set_visible(n, on, render=False)
        self.list.sync_checks(self.scene.visible)
        self.scene._after_visibility_change()

    def _set_all(self, on):
        if self.scene:
            self._visibility_changed(list(self.scene.names), on)
            if on and self.scene.n_hidden_faces:      # hidden surfaces too
                self.scene.show_faces()

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
            what = self._menu_word(names)
            menu.addAction(f"Hide{what}", lambda: self._visibility_changed(names, False))
            hit = self.scene.context_hit                 # the CAD face under the cursor
            if hit and hit[1] is not None and hit[0] in names:
                menu.addAction("Hide Surface", lambda h=hit: self.scene.hide_face(*h))
            menu.addAction(f"Isolate{what}", lambda: self._isolate(names))
            menu.addAction("Zoom To", lambda: self.scene.zoom_to(names))
            if len(names) == 1 and clicked == names:
                menu.addAction("Rename…", lambda: self.rename(names[0]))
            menu.addAction("Colour…", lambda: self.choose_color(names))
            # McMaster-Carr parts -> open their catalogue page
            # only the part / group that was right-clicked, not the selection
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
        k = self.scene.n_hidden_faces
        if k:
            menu.addAction(f"Show Hidden Surfaces ({k})", self.scene.show_faces)
        menu.addAction("Fit View", self.scene.fit)
        menu.exec(global_pos)
        self.scene.context_hit = None
        self.scene.end_stuck_drag()            # no zoom mode left behind

    def _menu_word(self, names):
        """" Part", " 3 Parts"; 2D meshes: " Face" (the cells) / " Boundary" (a line)."""
        word, words = "Part", "Parts"
        if self.scene.model.file_type == "mesh2d":
            lines = {is_line_part(self.scene.model.parts[n]) for n in names}
            if lines == {True}:
                word, words = "Boundary", "Boundaries"
            elif lines == {False}:
                word, words = "Face", "Faces"
        return f" {word}" if len(names) == 1 else f" {len(names)} {words}"

    def _section_for_colors(self):
        """Colour by quality on a volume mesh: the colours show on the cut."""
        sp = self.section_panel
        self.show_section("section")
        if not sp.enable.isChecked():
            sp.enable.setChecked(True)
        if not sp.fill.isChecked():
            sp.fill.setChecked(True)

    # --- part colour ------------------------------------------------------
    def choose_color(self, names):
        if not self.scene or not names:
            return
        title = names[0] if len(names) == 1 else f"{len(names)} parts"
        c = QColorDialog.getColor(QColor(self.scene.colors[names[0]]), self.window(),
                                  f"Colour of {title}")
        self.scene.end_stuck_drag()
        if not c.isValid():
            return
        self.scene.set_color(names, c.name())
        for n in names:
            self.list.set_color(n, self.scene.colors[n])
        self.cfd_panel.refresh_colors()                # Boundary menu dots
        self.inflation_panel.refresh_colors()          # Walls menu dots

    # --- rename a part ---------------------------------------------------
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
        return self.scene.model.item_words[0]

    def _apply_filter(self, text):
        self.list.apply_filter(text)

    def _sync_checks(self):
        self.list.sync_checks(self.scene.visible)
