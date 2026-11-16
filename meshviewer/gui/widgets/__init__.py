"""Small reusable widgets, by kind (import them from here):

    basics     switch, button capsule, icon toggle, colour dot / field, menu, "?" link, line
    sections   the folding sidebar section
    select     pop-up choice buttons, colour-map choice, colour scale bar
    numbers    number boxes (plain, stepping, with a unit, temperature, list of values)
    formulas   the Formulas window
"""
from meshviewer.gui.widgets.basics import (
    Capsule, color_dot, ColorField, help_button, IconToggle, Menu, NoWheelSlider,
    NoWheelSpinBox, rule, section_header, Switch,
)
from meshviewer.gui.widgets.formulas import FormulasButton, FormulasDialog, render_tex
from meshviewer.gui.widgets.numbers import (
    format_number, NumberField, SpinField, TemperatureField, UnitField, ValuesButton,
)
from meshviewer.gui.widgets.sections import CollapsibleSection
from meshviewer.gui.widgets.select import GradientBar, GradientSelect, MenuSelect, paint_gradient

__all__ = [
    "Capsule", "CollapsibleSection", "color_dot", "ColorField", "format_number",
    "FormulasButton", "FormulasDialog", "GradientBar", "GradientSelect", "help_button",
    "IconToggle", "Menu", "MenuSelect", "NoWheelSlider", "NoWheelSpinBox", "NumberField",
    "paint_gradient", "render_tex", "rule", "section_header", "SpinField", "Switch",
    "TemperatureField", "UnitField",
    "ValuesButton",
]
