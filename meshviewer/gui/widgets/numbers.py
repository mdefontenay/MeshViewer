"""Number boxes: any notation, with a unit, a temperature, and a list of values."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout

from meshviewer.gui.widgets.select import MenuSelect

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
