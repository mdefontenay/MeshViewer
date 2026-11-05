"""Small reusable widgets: switch, collapsible section, capsule button group…"""
from __future__ import annotations

import re

from PySide6.QtCore import (
    Property, QEasingCurve, QPointF, QPropertyAnimation, QRectF, QRegularExpression, QSettings,
    QSize, Qt, Signal,
)
from PySide6.QtGui import (
    QColor, QIcon, QPainter, QPainterPath, QPalette, QPen, QPixmap, QRegularExpressionValidator,
)
from PySide6.QtWidgets import (
    QAbstractButton, QColorDialog, QDoubleSpinBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QMenu,
    QPushButton, QSizePolicy, QSlider, QToolButton, QVBoxLayout, QWidget,
)

from .style import accent


# ---------------------------------------------------------------------------
# macOS-style on/off switch (like System Settings)
# ---------------------------------------------------------------------------

class Switch(QAbstractButton):
    W, H = 32, 18

    def __init__(self, checked=False, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(self.W, self.H)
        self._pos = 1.0 if checked else 0.0
        self._anim = QPropertyAnimation(self, b"knob", self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.toggled.connect(self._animate)

    def _animate(self, on):
        self._anim.stop()
        self._anim.setStartValue(self._pos)
        self._anim.setEndValue(1.0 if on else 0.0)
        self._anim.start()

    def _get_knob(self):
        return self._pos

    def _set_knob(self, v):
        self._pos = v
        self.update()

    knob = Property(float, _get_knob, _set_knob)

    def sizeHint(self):
        return QSize(self.W, self.H)

    @staticmethod
    def set_silently(sw, on):
        """Set the state without emitting toggled or animating."""
        sw.blockSignals(True)
        sw.setChecked(bool(on))
        sw._pos = 1.0 if on else 0.0
        sw.blockSignals(False)
        sw.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pal = self.palette()
        dark = pal.window().color().lightness() < 128
        off = QColor("#48484a" if dark else "#d9d9de")
        on = QColor(accent())                              # system accent (vivid in light mode)
        t = self._pos
        track = QColor(
            int(off.red() + (on.red() - off.red()) * t),
            int(off.green() + (on.green() - off.green()) * t),
            int(off.blue() + (on.blue() - off.blue()) * t),
        )
        if not self.isEnabled():
            track.setAlpha(110)
        r = self.H / 2
        p.setPen(Qt.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(QRectF(0, 0, self.W, self.H), r, r)
        d = self.H - 4
        x = 2 + t * (self.W - d - 4)
        p.setBrush(QColor(0, 0, 0, 40))                    # soft knob shadow
        p.drawEllipse(QRectF(x, 2.6, d, d))
        p.setBrush(QColor("white"))
        p.drawEllipse(QRectF(x, 2, d, d))


def section_header(text):
    lbl = QLabel(text)
    lbl.setObjectName("SectionHeader")
    return lbl


def color_dot(hex_color, size=12):
    pm = QPixmap(size * 2, size * 2)            # 2x for Retina
    pm.setDevicePixelRatio(2)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(QColor(0, 0, 0, 60))
    p.setBrush(QColor(hex_color))
    p.drawEllipse(QRectF(1, 1, size - 2, size - 2))
    p.end()
    return QIcon(pm)


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
                 parent=None, remember=True, start_open=True):
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
        h.addWidget(section_header(title))
        h.addStretch(1)
        if trailing is not None:
            # FIX (v2.17): keep a widget's own cursor (the Section switch is a hand)
            if not trailing.testAttribute(Qt.WA_SetCursor):
                trailing.setCursor(Qt.ArrowCursor)
            h.addWidget(trailing)
        self.header.clicked.connect(lambda: self.set_expanded(not self.expanded))
        lay.addWidget(self.header)
        lay.addWidget(content)

        # remember=False: always start in the start_open state (not remembered).
        self._remember = remember
        collapsed = QSettings("local", "Mesh Viewer").value(self._key, False, type=bool) \
            if remember else not start_open
        self.expanded = not collapsed
        content.setVisible(self.expanded)
        self.chevron.set_open(self.expanded, animate=False)

    def set_expanded(self, on):
        self.expanded = bool(on)
        self.content.setVisible(self.expanded)
        self.chevron.set_open(self.expanded)
        if self._remember:
            QSettings("local", "Mesh Viewer").setValue(self._key, not self.expanded)
        self.toggled.emit(self.expanded)
        # Re-layout up the chain: without this a closed section could keep its
        # old height (when its content changed while hidden), leaving a gap.
        w = self
        while w is not None:
            if w.layout() is not None:
                w.layout().invalidate()
            w.updateGeometry()
            w = w.parentWidget()


# ---------------------------------------------------------------------------
# capsule = rounded group of buttons (toolbar groups, segmented controls)
# ---------------------------------------------------------------------------

class Capsule(QFrame):
    """Buttons for the given QActions inside one rounded, lightly tinted shape."""

    def __init__(self, actions, name="Capsule", icon_size=18, dividers=True, parent=None):
        super().__init__(parent)
        self.setObjectName(name)
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(0)
        self.buttons = []
        for i, a in enumerate(actions):
            if i and dividers:
                d = QFrame()
                d.setObjectName("CapsuleDivider")
                d.setFixedSize(1, 14)
                lay.addWidget(d, 0, Qt.AlignVCenter)
            b = QToolButton()
            b.setDefaultAction(a)
            b.setAutoRaise(True)
            b.setFocusPolicy(Qt.NoFocus)
            b.setIconSize(QSize(icon_size, icon_size))
            b.setToolButtonStyle(Qt.ToolButtonTextOnly if a.icon().isNull()
                                 else Qt.ToolButtonIconOnly)
            lay.addWidget(b)
            self.buttons.append(b)


# ---------------------------------------------------------------------------
# Sliders / number boxes that ignore the scroll wheel, so scrolling the
# sidebar never changes a value by accident. (The wheel goes to the sidebar.)
# ---------------------------------------------------------------------------

class NoWheelSlider(QSlider):
    def wheelEvent(self, e):
        e.ignore()


class NoWheelSpinBox(QDoubleSpinBox):
    def wheelEvent(self, e):
        e.ignore()


# ---------------------------------------------------------------------------
# roomy, rounded context menu (macOS style); look set in style.py
# ---------------------------------------------------------------------------

class Menu(QMenu):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ContextMenu")
        # Transparent window so the rounded corners show (macOS adds the shadow).
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)


# ---------------------------------------------------------------------------
# HEX colour field + swatch (click the swatch for the colour picker)
# ---------------------------------------------------------------------------

class ColorField(QWidget):
    changed = Signal(str)            # emitted with a valid "#RRGGBB" only

    HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")

    def __init__(self, value="#FFFFFF", parent=None):
        super().__init__(parent)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.edit = QLineEdit(value)
        self.edit.setValidator(QRegularExpressionValidator(QRegularExpression(r"#?[0-9A-Fa-f]{0,6}")))
        self.edit.setPlaceholderText("#RRGGBB")
        self.edit.setFixedWidth(110)
        self.edit.textChanged.connect(self._typed)
        self.swatch = QPushButton()
        self.swatch.setFixedSize(28, 22)
        self.swatch.setToolTip("Pick a colour")
        self.swatch.clicked.connect(self._pick)
        lay.addWidget(self.edit)
        lay.addWidget(self.swatch)
        lay.addStretch(1)
        self._typed(value)

    @property
    def value(self):
        return ("#" + self.edit.text().strip().lstrip("#")).upper()

    def is_valid(self):
        return bool(self.HEX.match(self.value))

    def _typed(self, _):
        ok = self.is_valid()
        self.swatch.setStyleSheet(f"background: {self.value if ok else 'transparent'}; "
                                  f"border: 1px solid palette(mid); border-radius: 5px;")
        if ok:
            self.changed.emit(self.value)

    def _pick(self):
        c = QColorDialog.getColor(QColor(self.value if self.is_valid() else "#FFFFFF"), self,
                                  "Choose a colour")
        if c.isValid():
            self.edit.setText(c.name().upper())
