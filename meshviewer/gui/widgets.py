"""Small reusable widgets: switch, collapsible section, capsule button group…"""
from __future__ import annotations

import re

from PySide6.QtCore import (
    QPoint,
    Property, QEasingCurve, QPointF, QPropertyAnimation, QRectF, QRegularExpression, QSettings,
    QSize, Qt, QUrl, Signal,
)
from PySide6.QtGui import (
    QColor, QDesktopServices, QIcon, QLinearGradient, QPainter, QPainterPath, QPalette, QPen,
    QPixmap, QRegularExpressionValidator,
)
from PySide6.QtWidgets import (
    QAbstractButton, QColorDialog, QDoubleSpinBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QMenu, QPushButton, QScrollArea, QSizePolicy, QSlider, QToolButton, QVBoxLayout, QWidget,
)

from meshviewer.gui.style import accent


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
        collapsed = QSettings("local", "Mesh Viewer").value(self._key, not start_open,
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

class IconToggle(QToolButton):
    """A small checkable icon button (header / card): the eye that shows a cut, the gear
    that opens Advanced. icons = (on, off) names in gui/icons.py, or one for both."""

    def __init__(self, icons, tip, checked=False, eye=False, parent=None):
        super().__init__(parent)
        from meshviewer.gui.icons import icon
        self._icons = (icon(icons[0]), icon(icons[1])) if isinstance(icons, tuple) \
            else (icon(icons), icon(icons))
        self.setObjectName("IconToggle")
        self.setProperty("eye", eye)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setAutoRaise(True)
        self.setFocusPolicy(Qt.NoFocus)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(22, 22)
        self.setIconSize(QSize(15, 15))
        self.setToolTip(tip)
        self.toggled.connect(self._icon)
        self._icon(checked)

    def _icon(self, on):
        self.setIcon(self._icons[0 if on else 1])


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
            self._dividers = getattr(self, "_dividers", []) + [d if i and dividers else None]

    def show_only(self, actions):
        """Hide the buttons of the other actions (and their dividers); the whole
        capsule when none is left."""
        keep = set(actions)
        first = True
        for b, d in zip(self.buttons, self._dividers):
            on = b.defaultAction() in keep
            b.setVisible(on)
            if d is not None:
                d.setVisible(on and not first)
            first = first and not on
        self.has_shown = bool(keep & {b.defaultAction() for b in self.buttons})


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
        self._fit_width()

    def count(self):
        return len(self._items)

    def clear(self):
        self._items, self._icons, self._index = [], [], -1
        self.setText("")
        self.setIcon(QIcon())

    def setItemIcon(self, i, icon):
        """e.g. a part's colour dot."""
        if 0 <= i < len(self._icons):
            self._icons[i] = icon
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
        fm = self.fontMetrics()
        widest = max(fm.horizontalAdvance(t) for t, _ in self._items)
        icon = 18 if any(i is not None for i in self._icons) else 0
        self.setMinimumWidth(widest + 44 + icon)     # text + padding + chevron

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


# ---------------------------------------------------------------------------
# a number box that takes any notation ("1.8e-5", "0,3"), and a
# small round "?" button that opens a web page.
# ---------------------------------------------------------------------------

def format_number(v):
    if v is None:
        return ""
    a = abs(v)
    if a and (a >= 1e6 or a < 1e-3):
        return f"{v:.4g}"
    return f"{v:.6g}"


class NumberField(QLineEdit):
    """Text box for one number. Empty = None (e.g. "auto"). valueChanged is
    sent when the user finishes typing (Return or leaving the box)."""
    valueChanged = Signal(object)

    def __init__(self, value=None, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.setMinimumWidth(56)
        self._value = None
        self._range = None                     # (low, high) typed values snap into
        self.setValue(value)
        self.editingFinished.connect(self._finished)

    def value(self):
        return self._value

    def setRange(self, low, high):
        """typed numbers outside [low, high] snap to the nearest end."""
        self._range = (float(low), float(high))

    def setValue(self, v):
        self._value = None if v is None else float(v)
        self.setText(format_number(self._value))
        self.setProperty("invalid", False)
        self.style().unpolish(self)
        self.style().polish(self)

    def _finished(self):
        text = self.text().strip().replace(",", ".").replace(" ", "")
        try:
            v = float(text) if text else None
        except ValueError:
            self.setProperty("invalid", True)          # red border until fixed
            self.style().unpolish(self)
            self.style().polish(self)
            return
        if v is not None and self._range is not None:
            v = min(max(v, self._range[0]), self._range[1])
        changed = v != self._value
        NumberField.setValue(self, v)
        if changed:
            self.valueChanged.emit(self.value())


class UnitField(NumberField):
    """a NumberField with a unit menu (`self.menu`, put it beside the
    box). value() / setValue() / valueChanged are always in the first unit (SI);
    the box shows the number in the unit picked."""
    unitChanged = Signal(str)

    def __init__(self, units, value=None, parent=None):
        self.units = dict(units)               # name -> factor to the first unit
        self.factor = 1.0
        super().__init__(None, parent)
        self.menu = MenuSelect()
        for k in self.units:
            self.menu.addItem(k, k)
        self.menu.setToolTip("Unit")
        self.menu.currentIndexChanged.connect(self._unit_picked)
        self.setValue(value)

    def value(self):
        v = self._value
        return None if v is None else v * self.factor

    def setValue(self, v):
        NumberField.setValue(self, None if v is None else v / self.factor)

    def unit(self):
        return self.menu.currentData()

    def set_unit(self, key, emit=False):
        i = self.menu.findData(key)
        if i < 0:
            return
        self.menu.blockSignals(True)
        self.menu.setCurrentIndex(i)
        self.menu.blockSignals(False)
        self._unit_picked(i, emit)

    def _unit_picked(self, i, emit=True):
        si = self.value()
        self.factor = self.units[self.menu.currentData()]
        self.setValue(si)                      # same quantity, new unit
        if emit:
            self.unitChanged.emit(self.menu.currentData())


class TemperatureField(UnitField):
    """a UnitField for temperatures — K, °C, °F have an offset, not
    only a factor. value() / setValue() are in kelvin."""
    UNITS = {"K": (1.0, 0.0), "°C": (1.0, 273.15), "°F": (5 / 9, 459.67 * 5 / 9)}

    def __init__(self, value=None, parent=None):
        self._offset = 0.0
        super().__init__({k: f for k, (f, _) in self.UNITS.items()}, value, parent)
        self.menu.setToolTip("Unit")

    def value(self):
        v = self._value
        return None if v is None else v * self.factor + self._offset

    def setValue(self, v):
        NumberField.setValue(self, None if v is None else (v - self._offset) / self.factor)

    def _unit_picked(self, i, emit=True):
        si = self.value()
        self.factor, self._offset = self.UNITS[self.menu.currentData()]
        self.setValue(si)
        if emit:
            self.unitChanged.emit(self.menu.currentData())

    def shown(self, kelvin):
        """A temperature in kelvin, in the unit picked (for placeholders)."""
        return (kelvin - self._offset) / self.factor


class ValuesButton(QPushButton):
    """small "Values" link; click -> a pop-up list of computed numbers.

        set_rows([("Reynolds Re", "1.2e7", ""), ("Temperature T", "288", "K"), ...])
    """

    def __init__(self, title, text="Values", tip="All the computed values", parent=None):
        super().__init__(text, parent)
        self.setObjectName("LinkButton")
        self.setFlat(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(tip)
        self._title = title
        self._rows = []
        self.popup = None
        self.clicked.connect(self.open)

    def set_rows(self, rows):
        self._rows = list(rows)
        self.setEnabled(bool(self._rows))
        if self.popup is not None and self.popup.isVisible():
            self.open()                         # refresh what is shown

    def open(self):
        if self.popup is not None:
            self.popup.close()
        pop = QFrame(self.window(), Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        pop.setObjectName("ValuesPopup")
        pop.setAttribute(Qt.WA_TranslucentBackground)
        pop.setAttribute(Qt.WA_DeleteOnClose)
        outer = QVBoxLayout(pop)
        outer.setContentsMargins(0, 0, 0, 0)
        body = QFrame()
        body.setObjectName("ValuesBody")
        outer.addWidget(body)
        lay = QVBoxLayout(body)
        lay.setContentsMargins(14, 10, 14, 12)
        lay.setSpacing(6)
        t = QLabel(self._title)
        t.setObjectName("SubHeader")
        lay.addWidget(t)
        g = QGridLayout()
        g.setHorizontalSpacing(10)
        g.setVerticalSpacing(4)
        for r, (name, value, unit) in enumerate(self._rows):
            if value is None:                   # a sub-title
                lab = QLabel(name)
                lab.setObjectName("Caption")
                g.addWidget(lab, r, 0, 1, 3)
                continue
            g.addWidget(QLabel(name), r, 0)
            v = QLabel(value)
            v.setObjectName("ValueText")
            v.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            v.setTextInteractionFlags(Qt.TextSelectableByMouse)
            g.addWidget(v, r, 1)
            u = QLabel(unit)
            u.setObjectName("AxisLabel")
            g.addWidget(u, r, 2)
        lay.addLayout(g)
        pop.adjustSize()
        # under the button, kept on the screen
        pos = self.mapToGlobal(self.rect().bottomRight())
        x = pos.x() - pop.width()
        screen = self.screen().availableGeometry()
        x = max(screen.left() + 4, min(x, screen.right() - pop.width() - 4))
        y = pos.y() + 4
        if y + pop.height() > screen.bottom():
            y = self.mapToGlobal(self.rect().topLeft()).y() - pop.height() - 4
        pop.move(x, y)
        pop.show()
        self.popup = pop
        pop.destroyed.connect(lambda *_: setattr(self, "popup", None))


# ---------------------------------------------------------------------------
# "Formulas" — a window in the middle of the app with the equations
# ---------------------------------------------------------------------------

def render_tex(tex, color="#000000", size=17):
    """LaTeX-like formula -> QPixmap (matplotlib's mathtext: no TeX install needed),
    or None when matplotlib is not there."""
    try:
        import io

        import matplotlib
        from matplotlib import mathtext
        from matplotlib.font_manager import FontProperties
    except ImportError:
        return None
    try:
        with matplotlib.rc_context({"mathtext.fontset": "cm",      # Computer Modern
                                    "savefig.transparent": True}):
            buf = io.BytesIO()
            tex = tex.replace(r"\frac", r"\dfrac")              # full-size fractions
            mathtext.math_to_image(f"${tex}$", buf, prop=FontProperties(size=size), dpi=144,
                                   format="png", color=color)
    except Exception:                                           # noqa: BLE001
        return None
    pm = QPixmap()
    pm.loadFromData(buf.getvalue(), "PNG")
    pm.setDevicePixelRatio(2)
    return pm


def _plain(tex):
    """Readable fallback for a formula without matplotlib."""
    t = tex
    for a, b in ((r"\frac", ""), (r"\sqrt", "√"), (r"\left", ""), (r"\right", ""),
                 (r"\rho", "ρ"), (r"\mu", "μ"), (r"\nu", "ν"), (r"\tau", "τ"),
                 (r"\gamma", "γ"), (r"\delta", "δ"), (r"\cdot", "·"), (r"\,", " "),
                 (r"\max", "max"), (r"\min", "min"), (r"\log", "log"), (r"\times", "×"),
                 (r"\mathrm", ""), ("{", "("), ("}", ")"), ("\\", "")):
        t = re.sub(a, b, t)
    return t


class FormulasDialog(QFrame):
    """A card next to the "Formulas" link that opened it: title, then for each formula a
    short explanation and the formula. Items: a sub-title string, (explanation, LaTeX),
    (explanation, LaTeX, url) — the formula links to the url — or ("link", text, url).
    Click outside or press Esc to close."""

    def __init__(self, title, items, parent):
        super().__init__(parent.window(), Qt.Popup | Qt.FramelessWindowHint |
                         Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        body = QFrame()
        body.setObjectName("ValuesBody")
        outer.addWidget(body)
        bl = QVBoxLayout(body)
        bl.setContentsMargins(2, 2, 2, 2)
        scroll = QScrollArea()                     # scrolls when the window is small
        scroll.setObjectName("FormulasScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        bl.addWidget(scroll)
        inner = QWidget()
        inner.setObjectName("FormulasInner")
        scroll.setWidget(inner)
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(20, 14, 20, 16)
        lay.setSpacing(4)
        inner.setMinimumWidth(500)
        t = QLabel(title)
        t.setObjectName("PageTitle")
        lay.addWidget(t)
        color = self.palette().color(QPalette.WindowText).name()
        for item in items:
            if isinstance(item, str):                    # a sub-title
                lab = QLabel(item)
                lab.setObjectName("Caption")
                lab.setContentsMargins(0, 10, 0, 0)
                lay.addWidget(lab)
                continue
            if item[0] == "link":                        # ("link", text, url)
                _, text, url = item
                b = QPushButton(text)
                b.setObjectName("LinkButton")
                b.setFlat(True)
                b.setCursor(Qt.PointingHandCursor)
                b.setToolTip(url)
                b.clicked.connect(lambda _=False, u=url: QDesktopServices.openUrl(QUrl(u)))
                lay.addSpacing(8)
                lay.addWidget(b, 0, Qt.AlignLeft)
                continue
            text, tex = item[0], item[1]
            url = item[2] if len(item) > 2 else None
            lab = QLabel(text)
            lab.setObjectName("InfoLine")
            lab.setWordWrap(True)
            lab.setContentsMargins(0, 6, 0, 0)
            lay.addWidget(lab)
            if tex:
                f = QLabel()
                pm = render_tex(tex, color)
                if pm is None:
                    f.setText(_plain(tex))
                else:
                    f.setPixmap(pm)
                f.setContentsMargins(12, 0, 0, 0)
                if url:                                  # the formula is a link
                    f.setCursor(Qt.PointingHandCursor)
                    f.setToolTip(f"Open {url}")
                    f.mousePressEvent = lambda _e, u=url: QDesktopServices.openUrl(QUrl(u))
                lay.addWidget(f)
        win = parent.window().geometry()
        width = max(inner.sizeHint().width(), 500) + 24        # + room for the scroll bar
        inner.setFixedWidth(width - 24)
        h = min(inner.heightForWidth(width - 24) if inner.hasHeightForWidth()
                else inner.sizeHint().height(), win.height() - 60) + 8
        self.resize(width, h)
        scroll.setFixedHeight(h - 4)
        # next to the link that opened it (just right of the sidebar), inside the window
        at = parent.mapToGlobal(QPoint(parent.width(), 0))
        side = parent.window().findChild(QWidget, "Sidebar")
        x = (side.mapToGlobal(QPoint(side.width(), 0)).x() + 8) if side is not None \
            else at.x() + 8
        x = min(x, win.right() - self.width() - 8)
        y = min(max(at.y() - 12, win.top() + 40), win.bottom() - self.height() - 8)
        self.move(max(x, win.left() + 8), max(y, win.top() + 8))

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(e)


class FormulasButton(QPushButton):
    """Small "Formulas" link; `items` is a list (or a function returning one) of
    sub-title strings and (explanation, LaTeX formula) pairs."""

    def __init__(self, title, items, text="Formulas", parent=None):
        super().__init__(text, parent)
        self.setObjectName("LinkButton")
        self.setFlat(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("The formulas used here")
        self._title = title
        self._items = items
        self.dialog = None
        self.clicked.connect(self.open)

    def open(self):
        items = self._items() if callable(self._items) else self._items
        self.dialog = FormulasDialog(self._title, items, self)
        self.dialog.show()


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


def help_button(url, tip):
    b = QPushButton("?")
    b.setObjectName("HelpButton")
    b.setCursor(Qt.PointingHandCursor)
    b.setToolTip(f"{tip}\n{url}")
    b.setFixedSize(16, 16)
    b.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(url)))
    return b
