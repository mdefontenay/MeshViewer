"""The inspector: the panel right of the 3D view, with the tools in three tabs.

    ┌─────────────────────────────┐
    │  [ View | Measure | Analyze ] │   a segmented control (⌥⌘1 / ⌥⌘2 / ⌥⌘3)
    │  Mesh Quality              ›  │
    │  Section             [on]  ›  │   the tools of the tab shown (gui/sections.py)
    │  Edit                      ›  │
    └─────────────────────────────┘

The Sidebar builds the tools and puts them here (`add`); it decides what the tab shown
means for them (a tool works while it is in view). This is only the panel.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QHBoxLayout, QStackedWidget, QVBoxLayout, QWidget

from meshviewer.gui.sections import TABS
from meshviewer.gui.sidebar_layout import FitScroll
from meshviewer.gui.widgets import Capsule


class Inspector(QWidget):
    tab_changed = Signal(str)            # "view" / "measure" / "analyze"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Inspector")
        self.setAttribute(Qt.WA_StyledBackground, True)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 10, 0, 10)
        lay.setSpacing(10)

        group = QActionGroup(self)
        group.setExclusive(True)
        self.tab_actions = {}
        for key, title in TABS:
            a = QAction(title, self)
            a.setCheckable(True)
            a.setData(key)
            a.setToolTip(f"{title} Tools")
            group.addAction(a)
            a.toggled.connect(lambda on, k=key: on and self._picked(k))
            self.tab_actions[key] = a
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 12, 0)
        row.addStretch(1)
        self.tabs = Capsule(list(self.tab_actions.values()), name="Segmented")
        self.tabs.setAccessibleName("Tool Tabs")
        row.addWidget(self.tabs)
        row.addStretch(1)
        lay.addLayout(row)

        self.stack = QStackedWidget()
        self.pages = {}                          # tab -> (FitScroll, its column)
        for key, _title in TABS:
            page = QWidget()
            page.setObjectName("InspectorPage")
            col = QVBoxLayout(page)
            col.setContentsMargins(0, 0, 12, 0)  # the scrollbar sits at the edge
            col.setSpacing(8)
            scroll = FitScroll(page)
            holder = QWidget()                   # the tools on top, room below
            hl = QVBoxLayout(holder)
            hl.setContentsMargins(0, 0, 0, 0)
            hl.addWidget(scroll)
            hl.addStretch(1)
            self.stack.addWidget(holder)
            self.pages[key] = (scroll, col, holder)
        lay.addWidget(self.stack, 1)
        self._current = TABS[0][0]
        self.tab_actions[self._current].setChecked(True)

    def add(self, tab, widget):
        """Put a tool (its box) at the end of tab `tab`."""
        self.pages[tab][1].addWidget(widget)

    def current(self):
        return self._current

    def show_tab(self, key):
        if key not in self.pages:
            return
        a = self.tab_actions[key]
        if not a.isChecked():
            a.setChecked(True)                  # -> _picked
        elif self.stack.currentWidget() is not self.pages[key][2]:
            self._picked(key)

    def _picked(self, key):
        self._current = key
        self.stack.setCurrentWidget(self.pages[key][2])
        self.refit()
        self.tab_changed.emit(key)

    def refit(self):
        for scroll, _col, _h in self.pages.values():
            scroll.refit()
