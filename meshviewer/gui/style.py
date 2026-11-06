"""Look & feel (macOS 27 style): shaded sidebar column, capsule toolbar groups,
rounded fields. Colours are chosen per light/dark mode; the accent colour is
the one picked in System Settings ▸ Appearance.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
import numpy as np
from PySide6.QtGui import QColor, QGuiApplication, QPalette

LIGHT = dict(
    text="#1d1d1f", secondary="#6e6e73", sidebar="#ebebee", divider="rgba(0,0,0,0.10)",
    capsule="rgba(0,0,0,0.045)", capsule_border="rgba(0,0,0,0.08)",
    hover="rgba(0,0,0,0.07)", pressed="rgba(0,0,0,0.13)",
    field="#ffffff", field_border="rgba(0,0,0,0.15)", field_solid="#ffffff",
    menu="rgba(246,246,246,0.98)", menu_border="rgba(0,0,0,0.12)",
)
DARK = dict(
    text="#f5f5f7", secondary="#98989d", sidebar="#262628", divider="rgba(255,255,255,0.09)",
    capsule="rgba(255,255,255,0.07)", capsule_border="rgba(255,255,255,0.10)",
    hover="rgba(255,255,255,0.10)", pressed="rgba(255,255,255,0.17)",
    field="rgba(255,255,255,0.06)", field_border="rgba(255,255,255,0.14)", field_solid="#1e1e20",
    menu="rgba(40,40,42,0.98)", menu_border="rgba(255,255,255,0.14)",
)

TEMPLATE = """
/* ---- sidebar column ---- */
#SideScroll, #SideScroll > QWidget, #Sidebar {{ background: {sidebar}; border: none; }}
#SectionHeader {{ color: {secondary}; font-size: 12px; font-weight: 600; }}
#SmallLabel {{ color: {text}; font-size: 11px; }}
#AxisLabel {{ color: {secondary}; font-size: 11px; }}
#ValueLabel {{ color: {text}; font-size: 12px; }}
#InfoLine {{ color: {secondary}; font-size: 11px; padding: 2px 2px 0 2px; }}
#ResultCard {{ background: {capsule}; border: 1px solid {capsule_border}; border-radius: 9px; }}
#GroupTitle {{ color: {secondary}; font-size: 11px; font-weight: 600; padding-top: 4px; }}
#SelectionCount {{ color: {accent}; font-size: 12px; font-weight: 600; }}
#SelectionCount[empty="true"] {{ color: {secondary}; font-weight: 500; }}
#SelectionPill {{ color: white; background: {accent}; border-radius: 9px;
                  padding: 1px 8px; font-size: 11px; font-weight: 600; }}
#Caption {{ color: {secondary}; font-size: 11px; font-weight: 600; }}
#Tag {{ color: {secondary}; font-size: 10px; }}
#BigValue {{ color: {text}; font-size: 20px; font-weight: 600; }}
#MutedValue {{ color: {secondary}; font-size: 16px; font-weight: 500; }}
#Divider {{ background: {divider}; border: none; min-height: 1px; max-height: 1px; }}
#EmptyState {{ color: {secondary}; font-size: 15px; }}
QSplitter::handle {{ background: {divider}; }}

#LinkButton {{ color: {accent}; border: none; background: transparent;
               padding: 0 2px; font-size: 12px; }}
#LinkButton:hover {{ text-decoration: underline; }}
#LinkButton:disabled {{ color: {secondary}; text-decoration: none; }}

/* ---- part list ---- */
#PartList {{ background: transparent; border: none; outline: none; }}
/* Rows (rounded selection, hover) and fold-out arrows are painted by part_tree.py. */

/* ---- text fields ---- */
QLineEdit, QDoubleSpinBox {{
    background: {field}; color: {text};
    border: 1px solid {field_border}; border-radius: 6px;
    padding: 3px 6px; selection-background-color: {accent};
}}
QLineEdit:focus, QDoubleSpinBox:focus {{ border: 1px solid {accent}; }}
/* No arrow buttons: without this, styled spin boxes give the text no room. */
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border; width: 0px; height: 0px; border: none;
}}

/* ---- capsules: toolbar groups and segmented controls ---- */
#Capsule, #Segmented {{
    background: {capsule}; border: 1px solid {capsule_border};
}}
#Capsule {{ border-radius: 15px; }}
#Segmented {{ border-radius: 7px; }}
#CapsuleDivider {{ background: {capsule_border}; border: none; }}
#Capsule QToolButton, #Segmented QToolButton {{
    color: {text}; background: transparent; border: none;
}}
#Capsule QToolButton {{ min-width: 26px; min-height: 24px; padding: 1px 6px;
                        border-radius: 12px; font-size: 12px; font-weight: 500; }}
#Segmented QToolButton {{ min-height: 20px; padding: 1px 9px;
                          border-radius: 5px; font-size: 12px; }}
#Capsule QToolButton:hover, #Segmented QToolButton:hover {{ background: {hover}; }}
#Capsule QToolButton:pressed, #Segmented QToolButton:pressed {{ background: {pressed}; }}
#Capsule QToolButton:checked, #Segmented QToolButton:checked {{ background: {accent}; color: white; }}
#Capsule QToolButton:disabled, #Segmented QToolButton:disabled {{ color: {secondary}; }}

QToolBar {{ spacing: 8px; padding: 3px 8px; border: none; }}

/* ---- right-click menu: roomy and rounded, like macOS ---- */
/* v2.25: choice button that opens the right-click-style menu (widgets.MenuSelect) */
#MenuSelect {{
    background: {field}; border: 1px solid {field_border}; border-radius: 6px;
    padding: 3px 28px 3px 10px; text-align: left; color: {text}; min-height: 18px;
}}
#MenuSelect:hover {{ border-color: {accent}; }}
/* v2.27: Edit ▸ Apply, the list of changes, renaming a part in the list (an
   opaque field: a see-through one showed the old name under the new one) */
#ApplyButton {{ background: {accent}; color: white; border: none; border-radius: 6px;
    padding: 4px 10px; min-height: 18px; font-weight: 600; }}
#ApplyButton:hover {{ background: {accent}; border: 1px solid rgba(255,255,255,0.35); }}
#ApplyButton:pressed {{ background: {pressed}; }}
#HistoryLine {{ color: {text}; font-size: 12px; }}
#RenameField {{ background: {field_solid}; color: {text}; border: 1px solid {accent};
    border-radius: 4px; padding: 0px 3px; selection-background-color: {accent};
    selection-color: white; }}
#ContextMenu {{
    background: {menu}; border: 1px solid {menu_border}; border-radius: 10px;
    padding: 6px 5px;
}}
#ContextMenu::item {{
    color: {text}; padding: 5px 30px 5px 12px; margin: 0 0; border-radius: 5px;
    font-size: 13px; min-width: 150px;
}}
#ContextMenu::item:selected {{ background: {accent}; color: white; }}
#ContextMenu::item:disabled {{ color: {secondary}; font-size: 12px; font-weight: 600; }}
#ContextMenu::separator {{ height: 1px; background: {divider}; margin: 5px 10px; }}
#ContextMenu::right-arrow {{ width: 8px; height: 8px; right: 10px; }}
"""


def is_dark() -> bool:
    hints = QGuiApplication.styleHints()
    try:
        scheme = hints.colorScheme()
        if scheme != Qt.ColorScheme.Unknown:
            return scheme == Qt.ColorScheme.Dark
    except AttributeError:      # Qt < 6.5
        pass
    return QGuiApplication.palette().window().color().lightness() < 128


def _luminance(c: QColor) -> float:
    """Relative luminance (WCAG): 0 = black, 1 = white."""
    rgb = np.array([c.redF(), c.greenF(), c.blueF()])
    lin = np.where(rgb <= 0.04045, rgb / 12.92, ((rgb + 0.055) / 1.055) ** 2.4)
    return float(lin @ np.array([0.2126, 0.7152, 0.0722]))


def _vivid(c: QColor, max_lum=0.30) -> QColor:
    """light mode only. macOS hands Qt a pale accent for light mode
    (e.g. a washed-out orange); make it saturated and dark enough that white
    text on it and accent-coloured text on the sidebar stay readable."""
    h, s, l, _ = c.getHslF()
    if h < 0 or s < 0.15:                      # graphite / grey accent: leave it
        return c
    s = max(s, 0.90)
    out = QColor.fromHslF(h, s, l)
    while _luminance(out) > max_lum and l > 0.2:
        l -= 0.01
        out = QColor.fromHslF(h, s, l)
    return out


def accent(dark=None) -> str:
    pal = QGuiApplication.palette()
    if is_dark() if dark is None else dark:
        return pal.highlight().color().name()          # dark mode: unchanged
    try:                                               # Qt 6.6+: the real control accent
        c = pal.color(QPalette.Accent)
    except AttributeError:
        c = pal.highlight().color()
    return _vivid(c).name()


def colors(dark=None) -> dict:
    c = dict(DARK if (is_dark() if dark is None else dark) else LIGHT)
    c["accent"] = accent(dark)
    return c


def stylesheet(dark=None) -> str:
    return TEMPLATE.format(**colors(dark))
