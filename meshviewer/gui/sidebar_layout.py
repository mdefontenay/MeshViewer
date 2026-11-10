"""Layout pieces of the side columns: a scroll area as tall as its content (each
inspector tab), a tool's place in its tab."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QSize, Qt, QTimer
from PySide6.QtWidgets import QFrame, QScrollArea, QSizePolicy



def divider():
    line = QFrame()
    line.setObjectName("Divider")
    line.setFixedHeight(1)
    return line


class FitScroll(QScrollArea):
    """A scroll area exactly as tall as its content, so no empty scrollbar track shows;
    it only shrinks (and scrolls) when the window is too short for everything."""

    def __init__(self, inner):
        super().__init__()
        self.setObjectName("SideScroll")
        self.setWidget(inner)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)   # narrower than a tool's card
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


class Box:
    """One tool in its inspector tab: its widget (section + divider), and per
    CollapsibleSection inside it the grey note, the panel and the header switch."""

    def __init__(self, widget):
        self.widget = widget
        self.divider = None
        self.parts = []                 # (section, note, panel, trailing)
