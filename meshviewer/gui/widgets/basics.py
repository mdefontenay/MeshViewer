"""Small controls: on/off switch, button capsule, icon toggle, colour dot and field,
context menu, wheel-proof slider / spin box, "?" link."""
from __future__ import annotations

from functools import lru_cache
import re

from PySide6.QtCore import (
    Property, QEasingCurve, QPropertyAnimation, QRect, QRectF, QRegularExpression, QSize, Qt,
    QUrl, Signal,
)
from PySide6.QtGui import (
    QColor, QDesktopServices, QIcon, QPainter, QPalette, QPen, QPixmap,
    QRegularExpressionValidator,
)
from PySide6.QtWidgets import (
    QAbstractButton, QDoubleSpinBox, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QMenu, QPushButton, QSizePolicy, QSlider, QToolButton, QWidget,
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
        if self.hasFocus():                                # keyboard focus (Tab): a ring
            ring = QColor(on)
            ring.setAlpha(150)
            p.setPen(QPen(ring, 2))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(QRectF(1, 1, self.W - 2, self.H - 2), r - 1, r - 1)


def section_header(text):
    lbl = QLabel(text)
    lbl.setObjectName("SectionHeader")
    return lbl


@lru_cache(maxsize=512)
def color_dot(hex_color, size=12):
    """A round colour swatch (one icon per colour: lists ask for hundreds)."""
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
    """The app's pop-up menu (rounded, accent highlight). Checkable items with an icon
    (View ▸ Show) get a check mark column on the left, as in macOS menus: Qt's styled
    menus draw the icon in the check's place, so what is on didn't show."""

    CHECK_COLUMN = 18                            # px left of the icons, for the mark

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ContextMenu")
        # Transparent window so the rounded corners show (macOS adds the shadow).
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.aboutToShow.connect(self._check_column)

    def _marked(self):
        return [a for a in self.actions() if a.isCheckable() and not a.icon().isNull()]

    def _check_column(self):
        on = bool(self._marked())
        if self.property("checks") != on:
            self.setProperty("checks", on)       # #ContextMenu[checks="true"]: room
            self.style().unpolish(self)
            self.style().polish(self)

    def paintEvent(self, e):
        super().paintEvent(e)
        marked = [a for a in self._marked() if a.isChecked() and a.isVisible()]
        if not marked:
            return
        from meshviewer.gui.icons import icon
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        col = self.CHECK_COLUMN
        for a in marked:
            r = self.actionGeometry(a)                # the row, the margin included
            on_it = a is self.activeAction() and a.isEnabled()
            ic = _white_check() if on_it else icon("checkmark")
            ic.paint(p, QRect(r.left() + 4, r.center().y() - 6, 12, 12), Qt.AlignCenter,
                     QIcon.Normal if a.isEnabled() else QIcon.Disabled)
        p.end()


@lru_cache(maxsize=1)
def _white_check():
    """The check mark on the highlighted (accent) row: white, as the text."""
    from meshviewer.gui.icons import icon
    return icon("checkmark", role=QPalette.HighlightedText)


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
        self.swatch.setToolTip("Pick a color")
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
        from meshviewer.gui.sheets import ask_color          # a sheet on its window
        ask_color(self.window(), self.value if self.is_valid() else "#FFFFFF", "Choose a Color",
                  lambda c: self.edit.setText(c.upper()))


def help_button(url, tip):
    b = QPushButton("?")
    b.setObjectName("HelpButton")
    b.setCursor(Qt.PointingHandCursor)
    b.setToolTip(f"{tip}\n{url}")
    b.setFixedSize(16, 16)
    b.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(url)))
    return b
