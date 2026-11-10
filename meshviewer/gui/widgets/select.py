"""Pop-up choice buttons (MenuSelect, and GradientSelect for colour maps) and the
colour scale bar."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPalette, QPen
from PySide6.QtWidgets import QPushButton, QWidget

from meshviewer.gui.style import accent
from meshviewer.gui.widgets.basics import Menu


# ---------------------------------------------------------------------------
# pop-up choice button — opens the same menu as a right-click (replaces
# QComboBox, whose macOS pop-up couldn't be styled without spacing glitches)
# ---------------------------------------------------------------------------
class MenuSelect(QPushButton):
    """Looks like a field with a chevron; click -> right-click-style menu with
    the choices (a check mark on the current one). QComboBox-like API."""
    currentIndexChanged = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("MenuSelect")
        self.setCursor(Qt.PointingHandCursor)
        self._items = []                      # [(text, data)]
        self._icons = []                      # optional icon per item
        self._index = -1
        self._widest, self._has_icon = 0, False   # widest text so far (px), any icon?
        self.clicked.connect(self._open)
        # macOS: lay out by the drawn box, not the native button's smaller rect
        # (without it, two menus in a row overlap)
        self.setAttribute(Qt.WA_LayoutUsesWidgetRect)

    # ---- QComboBox-like API ----
    def addItem(self, text, data=None, icon=None):
        self._items.append((text, data))
        self._icons.append(icon)
        if self._index < 0:
            self.setCurrentIndex(0)
        self._widest = max(self._widest, self.fontMetrics().horizontalAdvance(text))
        self._has_icon = self._has_icon or icon is not None
        self._fit_width()

    def count(self):
        return len(self._items)

    def clear(self):
        self._items, self._icons, self._index = [], [], -1
        self._widest, self._has_icon = 0, False
        self.setText("")
        self.setIcon(QIcon())

    def setItemIcon(self, i, icon):
        """e.g. a part's colour dot."""
        if 0 <= i < len(self._icons):
            self._icons[i] = icon
            if icon is not None and not self._has_icon:
                self._has_icon = True
                self._fit_width()
            if i == self._index:
                self.setIcon(icon or QIcon())

    def currentIndex(self):
        return self._index

    def currentData(self):
        return self._items[self._index][1] if 0 <= self._index < len(self._items) else None

    def currentText(self):
        return self._items[self._index][0] if 0 <= self._index < len(self._items) else ""

    def findData(self, data):
        return next((i for i, (_, d) in enumerate(self._items) if d == data), -1)

    def setCurrentIndex(self, i):
        if not 0 <= i < len(self._items):
            return
        changed = i != self._index
        self._index = i
        self.setText(self._items[i][0])
        self.setIcon(self._icons[i] or QIcon())
        if changed:
            self.currentIndexChanged.emit(i)

    # ---- menu ----
    def _open(self):
        menu = Menu(self)
        for i, (text, _) in enumerate(self._items):
            a = menu.addAction(text)
            if self._icons[i] is not None:
                a.setIcon(self._icons[i])
            a.setCheckable(True)
            a.setChecked(i == self._index)
            a.triggered.connect(lambda _=False, k=i: self.setCurrentIndex(k))
        menu.setMinimumWidth(self.width())
        menu.exec(self.mapToGlobal(self.rect().bottomLeft()))

    def _fit_width(self):
        icon = 18 if self._has_icon else 0
        self.setMinimumWidth(self._widest + 44 + icon)     # text + padding + chevron

    def paintEvent(self, e):
        super().paintEvent(e)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen(self.palette().color(QPalette.PlaceholderText), 1.5)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        cx, cy = self.width() - 14, self.height() / 2
        path = QPainterPath(QPointF(cx - 3.5, cy - 1.5))
        path.lineTo(QPointF(cx, cy + 2))
        path.lineTo(QPointF(cx + 3.5, cy - 1.5))
        p.drawPath(path)


def paint_gradient(p, rect, stops):
    """A rounded colour bar, stops low -> high, left to right."""
    g = QLinearGradient(rect.topLeft(), rect.topRight())
    for i, c in enumerate(stops):
        g.setColorAt(i / (len(stops) - 1), QColor(c))
    p.setPen(Qt.NoPen)
    p.setBrush(g)
    p.drawRoundedRect(rect, 3, 3)


class _GradientRow(QWidget):
    """One choice in the GradientSelect menu: the colour bar itself."""

    def __init__(self, stops, current, pick, parent=None):
        super().__init__(parent)
        self.stops, self.current, self.pick = stops, current, pick
        self.setFixedHeight(26)
        self.setMinimumWidth(170)
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)
        self._hover = False

    def enterEvent(self, e):
        self._hover = True
        self.update()

    def leaveEvent(self, e):
        self._hover = False
        self.update()

    def mouseReleaseEvent(self, e):
        self.pick()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        if self._hover or self.current:                  # hover: filled · current: outlined
            c = QColor(accent())
            p.setPen(Qt.NoPen if self._hover else QPen(c, 1.5))
            p.setBrush(c if self._hover else Qt.NoBrush)
            p.drawRoundedRect(r.adjusted(0.75, 0.75, -0.75, -0.75), 5, 5)
        paint_gradient(p, r.adjusted(10, 8, -10, -8), self.stops)
        p.end()


class GradientSelect(MenuSelect):
    """MenuSelect whose choices are colour bars (no names): the button shows the
    current one, the menu all of them."""

    def addItem(self, stops, data=None):
        self._items.append(("", data))
        self._icons.append(None)
        self._stops = getattr(self, "_stops", []) + [tuple(stops)]
        if self._index < 0:
            self.setCurrentIndex(0)
        self.setMinimumWidth(110)

    def clear(self):
        super().clear()
        self._stops = []

    def currentStops(self):
        return self._stops[self._index] if 0 <= self._index < len(self._items) else None

    def _open(self):
        from PySide6.QtWidgets import QWidgetAction
        menu = Menu(self)
        for i, stops in enumerate(self._stops):
            wa = QWidgetAction(menu)

            def pick(k=i):
                menu.close()
                self.setCurrentIndex(k)
            row = _GradientRow(stops, i == self._index, pick)
            row.setMinimumWidth(max(170, self.width() - 12))
            wa.setDefaultWidget(row)
            menu.addAction(wa)
        menu.exec(self.mapToGlobal(self.rect().bottomLeft()))

    def paintEvent(self, e):
        super().paintEvent(e)                            # the field and its chevron
        stops = self.currentStops()
        if stops:
            p = QPainter(self)
            p.setRenderHint(QPainter.Antialiasing)
            h = 10
            r = QRectF(10, (self.height() - h) / 2, self.width() - 38, h)
            paint_gradient(p, r, stops)
            p.end()


class GradientBar(QWidget):
    """thin colour scale with labels under it (the y+ colours)."""

    def __init__(self, stops, labels, parent=None):
        super().__init__(parent)
        self._stops = stops               # [(0..1, "#hex")]
        self._labels = labels             # [(0..1, "text")]
        self.setFixedHeight(26)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(1, 1, self.width() - 2, 8)
        g = QLinearGradient(r.topLeft(), r.topRight())
        for pos, c in self._stops:
            g.setColorAt(pos, QColor(c))
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawRoundedRect(r, 4, 4)
        f = p.font()
        f.setPixelSize(10)
        p.setFont(f)
        p.setPen(self.palette().color(QPalette.PlaceholderText))
        fm = p.fontMetrics()
        for pos, text in self._labels:
            w = fm.horizontalAdvance(text)
            x = min(max(r.left() + pos * r.width() - w / 2, 0), self.width() - w)
            p.drawText(QPointF(x, 24), text)
        p.end()
