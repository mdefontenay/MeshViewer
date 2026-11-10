"""A sidebar section that folds: chevron + title + an optional control on the right."""
from __future__ import annotations

from PySide6.QtCore import Property, QPointF, QPropertyAnimation, Qt, Signal
from PySide6.QtGui import QPainter, QPainterPath, QPalette, QPen
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from meshviewer.gui.store import settings
from meshviewer.gui.widgets.basics import section_header

# ---------------------------------------------------------------------------
# collapsible sidebar section (disclosure chevron + title + optional
# control on the right). Open/closed state is remembered.
# ---------------------------------------------------------------------------

class _Chevron(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(12, 12)
        self._angle = 90.0          # 90 = pointing down (open), 0 = right (closed)
        self._anim = QPropertyAnimation(self, b"angle", self)
        self._anim.setDuration(140)

    def _get(self):
        return self._angle

    def _set(self, v):
        self._angle = v
        self.update()

    angle = Property(float, _get, _set)

    def set_open(self, on, animate=True):
        end = 90.0 if on else 0.0
        if animate:
            self._anim.stop()
            self._anim.setStartValue(self._angle)
            self._anim.setEndValue(end)
            self._anim.start()
        else:
            self._set(end)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen(self.palette().color(QPalette.PlaceholderText), 1.6)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.translate(6, 6)
        p.rotate(self._angle)
        path = QPainterPath(QPointF(-1.5, -3.5))
        path.lineTo(QPointF(2, 0))
        path.lineTo(QPointF(-1.5, 3.5))
        p.drawPath(path)


class _Header(QWidget):
    clicked = Signal()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()


class CollapsibleSection(QWidget):
    toggled = Signal(bool)      # True = expanded

    def __init__(self, title, content: QWidget, key: str, trailing: QWidget | None = None,
                 parent=None, remember=True, start_open=True, sub=False):
        super().__init__(parent)
        self.content = content
        self._key = f"sidebar/collapsed/{key}"
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(6)

        self.header = _Header()
        self.header.setCursor(Qt.PointingHandCursor)
        self.header.setToolTip("Click to show or hide")
        h = QHBoxLayout(self.header)
        h.setContentsMargins(0, 2, 4, 2)
        h.setSpacing(6)
        self.chevron = _Chevron()
        h.addWidget(self.chevron)
        title_label = section_header(title)
        self.title_label = title_label
        if sub:                                 # a smaller group inside a section
            title_label.setObjectName("SubHeader")
            h.setContentsMargins(0, 4, 0, 0)
        h.addWidget(title_label)
        h.addStretch(1)
        if trailing is not None:
            # FIX: keep a widget's own cursor (the Section switch is a hand)
            if not trailing.testAttribute(Qt.WA_SetCursor):
                trailing.setCursor(Qt.ArrowCursor)
            h.addWidget(trailing)
        self.header.clicked.connect(lambda: self.set_expanded(not self.expanded))
        lay.addWidget(self.header)
        lay.addWidget(content)

        # remember=False: always start in the start_open state (not remembered).
        self._remember = remember
        collapsed = settings().value(self._key, not start_open,
                                                            type=bool) \
            if remember else not start_open
        self.expanded = not collapsed
        content.setVisible(self.expanded)
        self.chevron.set_open(self.expanded, animate=False)

    def set_title(self, text):
        self.title_label.setText(text)

    def set_expanded(self, on):
        self.expanded = bool(on)
        self.content.setVisible(self.expanded)
        self.chevron.set_open(self.expanded)
        if self._remember:
            settings().setValue(self._key, not self.expanded)
        self.toggled.emit(self.expanded)
        # Re-layout up the chain: without this a closed section could keep its
        # old height (when its content changed while hidden), leaving a gap.
        w = self
        while w is not None:
            if w.layout() is not None:
                w.layout().invalidate()
            w.updateGeometry()
            w = w.parentWidget()
