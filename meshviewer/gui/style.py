"""Look & feel (macOS 27 style): shaded sidebar column, capsule toolbar groups,
rounded fields. Colours are chosen per light/dark mode; the accent colour is
the one picked in System Settings ▸ Appearance.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
import numpy as np
from PySide6.QtGui import QColor, QGuiApplication, QPalette

from meshviewer.gui.macos import increase_contrast

LIGHT = dict(
    text="#1d1d1f", secondary="#6e6e73", sidebar="#ebebee", divider="rgba(0,0,0,0.10)",
    capsule="rgba(0,0,0,0.045)", capsule_border="rgba(0,0,0,0.08)",
    hover="rgba(0,0,0,0.07)", pressed="rgba(0,0,0,0.13)",
    field="#ffffff", field_border="rgba(0,0,0,0.15)", field_solid="#ffffff", page="#f5f5f7",
    menu="rgba(246,246,246,0.98)", menu_border="rgba(0,0,0,0.12)",
)
DARK = dict(
    text="#f5f5f7", secondary="#98989d", sidebar="#262628", divider="rgba(255,255,255,0.09)",
    capsule="rgba(255,255,255,0.07)", capsule_border="rgba(255,255,255,0.10)",
    hover="rgba(255,255,255,0.10)", pressed="rgba(255,255,255,0.17)",
    field="rgba(255,255,255,0.06)", field_border="rgba(255,255,255,0.14)", field_solid="#1e1e20",
    page="#1c1c1e",
    menu="rgba(40,40,42,0.98)", menu_border="rgba(255,255,255,0.14)",
)

TEMPLATE = """
/* ---- side columns ---- */
/* the parts list (left) and the inspector (right), on the same shade */
#SideScroll, #SideScroll > QWidget, #Sidebar, #Inspector, #InspectorPage {{ background: {sidebar}; border: none; }}
#UnavailableNote {{ color: {secondary}; font-size: 11px; padding: 0 2px 2px 2px; }}
#SectionHeader {{ color: {secondary}; font-size: 12px; font-weight: 600; }}
#SmallLabel {{ color: {text}; font-size: 11px; }}
#AxisLabel {{ color: {secondary}; font-size: 11px; }}
#ValueLabel {{ color: {text}; font-size: 12px; }}
#InfoLine {{ color: {secondary}; font-size: 11px; padding: 2px 2px 0 2px; }}
#ResultCard {{ background: {capsule}; border: 1px solid {capsule_border}; border-radius: 9px; }}
/* every sidebar section sits on a card like this one; inside it, cards and segmented
   controls are a shade lighter so they still stand out */
#SectionCard {{ background: {capsule}; border: 1px solid {capsule_border}; border-radius: 9px; }}
#SectionCard #ResultCard {{ background: {field}; }}
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
#WelcomeTitle {{ font-size: 24px; font-weight: 700; }}
#WelcomeRow {{ border: none; border-radius: 6px; background: transparent; text-align: left; }}
#WelcomeRow:hover {{ background: {divider}; }}
#WelcomeRow:focus {{ background: {divider}; }}
#WelcomeRowTitle {{ font-size: 13px; }}
QSplitter::handle {{ background: {divider}; }}

#LinkButton {{ color: {accent}; border: none; background: transparent;
               padding: 0 2px; font-size: 12px; }}
#LinkButton:hover {{ text-decoration: underline; }}
#LinkButton:disabled {{ color: {secondary}; text-decoration: none; }}

/* ---- part list ---- */
#PartList {{ background: transparent; border: none; outline: none; }}
/* Rows (rounded selection, hover) and fold-out arrows are painted by part_tree.py. */

/* ---- text fields ---- */
/* one height for every box and menu (22 px), like macOS's small controls */
QLineEdit, QDoubleSpinBox {{
    background: {field}; color: {text};
    border: 1px solid {field_border}; border-radius: 6px;
    padding: 1px 6px; min-height: 18px; max-height: 18px; font-size: 12px;
    selection-background-color: {accent};
}}
QLineEdit:focus, QDoubleSpinBox:focus {{ border: 1px solid {accent}; }}
/* No arrow buttons: without this, styled spin boxes give the text no room. */
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border; width: 0px; height: 0px; border: none;
}}

/* ---- capsules: toolbar groups and segmented controls ---- */
#Capsule {{ background: {capsule_solid}; border: 1px solid {capsule_border_solid}; }}
#Segmented {{ background: {capsule_side}; border: 1px solid {capsule_border_side}; }}
#SectionCard #Segmented, #ResultCard #Segmented {{ background: {field}; }}
/* small icon buttons in headers and cards (Plots: show the cut, Advanced) */
#IconToggle {{ border: none; border-radius: 5px; padding: 2px; background: transparent; }}
#IconToggle:hover {{ background: {hover}; }}
#IconToggle:checked {{ background: {pressed}; }}
#IconToggle[eye="true"]:checked {{ background: transparent; }}
#IconToggle[eye="true"]:checked:hover {{ background: {hover}; }}
#Capsule {{ border-radius: 15px; }}
#Segmented {{ border-radius: 7px; }}
#CapsuleDivider {{ background: {capsule_border_solid}; border: none; }}
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
#Capsule QToolButton:checked:disabled {{ background: transparent; }}   /* an empty window */

/* thin scrollbars on the side columns: just the handle, no wide grey track */
#Sidebar QScrollBar:vertical, #Inspector QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px 1px; border: none; }}
#Sidebar QScrollBar::handle:vertical, #Inspector QScrollBar::handle:vertical {{ background: {scroll}; border-radius: 3px; min-height: 28px; }}
#Sidebar QScrollBar::add-line:vertical, #Sidebar QScrollBar::sub-line:vertical, #Inspector QScrollBar::add-line:vertical, #Inspector QScrollBar::sub-line:vertical {{ height: 0; border: none; }}
#Sidebar QScrollBar::add-page:vertical, #Sidebar QScrollBar::sub-page:vertical, #Inspector QScrollBar::add-page:vertical, #Inspector QScrollBar::sub-page:vertical {{ background: transparent; }}
#Sidebar QScrollBar:horizontal, #Inspector QScrollBar:horizontal {{ background: transparent; height: 8px; margin: 1px 2px; border: none; }}
#Sidebar QScrollBar::handle:horizontal, #Inspector QScrollBar::handle:horizontal {{ background: {scroll}; border-radius: 3px; min-width: 28px; }}
#Sidebar QScrollBar::add-line:horizontal, #Sidebar QScrollBar::sub-line:horizontal, #Inspector QScrollBar::add-line:horizontal, #Inspector QScrollBar::sub-line:horizontal {{ width: 0; border: none; }}
#Sidebar QScrollBar::add-page:horizontal, #Sidebar QScrollBar::sub-page:horizontal, #Inspector QScrollBar::add-page:horizontal, #Inspector QScrollBar::sub-page:horizontal {{ background: transparent; }}

QToolBar {{ spacing: 8px; padding: 3px 8px; border: none; border-bottom: 1px solid {divider_solid}; }}

/* ---- right-click menu: roomy and rounded, like macOS ---- */
/* choice button that opens the right-click-style menu (widgets.MenuSelect) */
#MenuSelect {{
    background: {field}; border: 1px solid {field_border}; border-radius: 6px;
    padding: 1px 28px 1px 10px; text-align: left; color: {text}; min-height: 18px;
    max-height: 18px; font-size: 12px;
}}
#MenuSelect:hover {{ border-color: {accent}; }}
/* Edit ▸ Apply, the list of changes, renaming a part in the list (an
   opaque field: a see-through one showed the old name under the new one) */
#ApplyButton {{ background: {accent}; color: white; border: none; border-radius: 6px;
    padding: 4px 10px; min-height: 18px; font-weight: 600; }}
#ApplyButton:hover {{ background: {accent}; border: 1px solid rgba(255,255,255,0.35); }}
#ApplyButton:pressed {{ background: {pressed}; }}
#HistoryLine {{ color: {text}; font-size: 12px; }}
/* "?" links to a web page, number boxes with a typo */
#HelpButton {{ color: {secondary}; background: transparent; border: 1px solid {field_border};
    border-radius: 8px; font-size: 10px; font-weight: 600; padding: 0; }}
#HelpButton:hover {{ color: {accent}; border-color: {accent}; }}
QLineEdit[invalid="true"] {{ border: 1px solid #ff453a; }}
QLineEdit:disabled {{ color: {secondary}; background: {capsule}; border-color: {capsule_border}; }}
/* Inflation Layers — its page and the bar under the 3D view */
#InflationView, #InflationPage {{ background: {page}; border: none; }}
#PageTitle {{ color: {text}; font-size: 17px; font-weight: 700; }}
#TileValue {{ color: {text}; font-size: 17px; font-weight: 600; }}
#ViewBar {{ background: {page}; border-top: 1px solid {divider}; }}
#TabScroll, #TabScroll > QWidget {{ background: transparent; border: none; }}
#TabScroll QScrollBar:horizontal {{ background: transparent; height: 6px; margin: 0 2px; border: none; }}
#TabScroll QScrollBar::handle:horizontal {{ background: {scroll}; border-radius: 3px; min-width: 28px; }}
#TabScroll QScrollBar::add-line:horizontal, #TabScroll QScrollBar::sub-line:horizontal {{ width: 0; border: none; }}
#TabScroll QScrollBar::add-page:horizontal, #TabScroll QScrollBar::sub-page:horizontal {{ background: transparent; }}
/* sub-groups in a section, the "Values" pop-up */
#SubHeader {{ color: {text}; font-size: 12px; font-weight: 600; }}
#ValuesBody {{ background: {menu}; border: 1px solid {menu_border}; border-radius: 10px; }}
#ValuesBody QLabel {{ background: transparent; }}
#FormulasScroll, #FormulasInner {{ background: transparent; }}
#ValueText {{ color: {text}; font-weight: 600; }}
#SmallNote {{ color: {secondary}; font-size: 12px; }}
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


# System Settings ▸ Accessibility ▸ Display ▸ Increase contrast: stronger lines and text
HIGH_CONTRAST = {
    False: dict(secondary="#3a3a3c", divider="rgba(0,0,0,0.32)", capsule_border="rgba(0,0,0,0.35)",
                field_border="rgba(0,0,0,0.50)", menu_border="rgba(0,0,0,0.40)"),
    True: dict(secondary="#d1d1d6", divider="rgba(255,255,255,0.32)",
               capsule_border="rgba(255,255,255,0.38)", field_border="rgba(255,255,255,0.50)",
               menu_border="rgba(255,255,255,0.40)"),
}


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


def _solid(rgba, base: QColor) -> str:
    """'rgba(r,g,b,a)' painted over base, as one solid colour (no see-through edges
    where shapes overlap)."""
    if not rgba.startswith("rgba"):
        return rgba
    r, g, b, a = (float(v) for v in rgba[5:-1].split(","))
    mix = [round(base.red() * (1 - a) + r * a), round(base.green() * (1 - a) + g * a),
           round(base.blue() * (1 - a) + b * a)]
    return QColor(*mix).name()


def colors(dark=None) -> dict:
    d = is_dark() if dark is None else dark
    c = dict(DARK if d else LIGHT)
    if increase_contrast():
        c.update(HIGH_CONTRAST[d])
    c["accent"] = accent(dark)
    base = QGuiApplication.palette().window().color()
    side = QColor(c["sidebar"])
    for k in ("capsule", "capsule_border", "divider"):
        c[k + "_solid"] = _solid(c[k], base)                 # on the window (toolbar)
        c[k + "_side"] = _solid(c[k], side)                  # on the sidebar
    # fields, cards, "?" and lines: solid too (see-through edges show where they overlap)
    for k in ("field", "field_border", "capsule", "capsule_border", "divider"):
        c[k] = _solid(c[k], side)
    c["scroll"] = _solid("rgba(%s,0.32)" % ("255,255,255" if d else "0,0,0"), side)
    return c


def stylesheet(dark=None) -> str:
    return TEMPLATE.format(**colors(dark))
