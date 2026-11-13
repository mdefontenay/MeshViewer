"""Mesh Viewer ▸ Settings… (⌘,): how the app behaves and looks, the same in every
window. Like any Mac app's settings: a window of its own with a tab per subject in its
toolbar, every change applied at once and remembered — no OK button.

    General      theme, parts list spacing, the meshing control CAD files open at
    Appearance   the 3D view: background, shading, axis label size, edge lines
    Units        the unit lengths are shown in, the unit of files that don't say theirs,
                 whether to ask when a file is opened the first time

WHAT is shown (axes, grid, edges, faces…) is switched in the toolbar, per window.
The values live in MeshViewerApp.appearance and .prefs (gui/app.py).
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import (
    QFileDialog, QFormLayout, QHBoxLayout, QLabel, QMainWindow, QPushButton, QStackedWidget,
    QToolBar, QVBoxLayout, QWidget,
)

from meshviewer.core.model import CAD_QUALITY_NAMES
from meshviewer.gui.access import name_controls
from meshviewer.gui.forms import segmented
from meshviewer.gui.icons import icon
from meshviewer.gui.store import settings
from meshviewer.gui.widgets import ColorField, MenuSelect, NoWheelSlider, Switch

IMAGE_FILTER = "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)"
UNITS = (("mm", "Millimeters (mm)"), ("cm", "Centimeters (cm)"), ("m", "Meters (m)"),
         ("in", "Inches (in)"), ("ft", "Feet (ft)"))
TABS = (("general", "General"), ("appearance", "Appearance"), ("units", "Units"))


def _form():
    f = QFormLayout()
    f.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
    f.setFormAlignment(Qt.AlignHCenter | Qt.AlignTop)
    f.setHorizontalSpacing(12)
    f.setVerticalSpacing(10)
    f.setFieldGrowthPolicy(QFormLayout.FieldsStayAtSizeHint)
    return f


def _note(text):
    """A gray line under a control, saying what it does."""
    n = QLabel(text)
    n.setObjectName("InfoLine")
    n.setWordWrap(True)
    n.setFixedWidth(270)
    return n


def _switch_row(switch, text):
    row = QWidget()
    h = QHBoxLayout(row)
    h.setContentsMargins(0, 0, 0, 0)
    h.addWidget(switch)
    h.addWidget(QLabel(text))
    h.addStretch(1)
    return row


def _page(form):
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(28, 22, 28, 24)
    lay.addLayout(form)
    lay.addStretch(1)
    return w


class SettingsWindow(QMainWindow):
    def __init__(self, app):
        super().__init__(None)
        self.app = app                                 # MeshViewerApp: holds the settings
        self.setUnifiedTitleAndToolBarOnMac(True)
        self.setWindowFlag(Qt.WindowMinimizeButtonHint, False)
        self.setWindowFlag(Qt.WindowMaximizeButtonHint, False)
        bar = QToolBar("Settings")
        bar.setMovable(False)
        bar.setFloatable(False)
        bar.toggleViewAction().setVisible(False)
        bar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.addToolBar(bar)
        self.pages = QStackedWidget()
        self.setCentralWidget(self.pages)
        group = QActionGroup(self)
        self.tabs = {}
        builders = {"general": self._general, "appearance": self._appearance,
                    "units": self._units}
        for key, title in TABS:
            a = QAction(icon(f"settings_{key}"), title, self)
            a.setCheckable(True)
            a.triggered.connect(lambda _=False, k=key: self.show_tab(k))
            group.addAction(a)
            bar.addAction(a)
            page = builders[key]()
            self.pages.addWidget(page)
            self.tabs[key] = (a, page, title)
        close = QAction(self)                          # ⌘W, as any window
        close.setShortcut(QKeySequence.Close)
        close.triggered.connect(self.close)
        self.addAction(close)
        self.show_tab(settings().value("settings/tab", "general"))
        name_controls(self)                            # VoiceOver: the switches' names

    def show_tab(self, key):
        a, page, title = self.tabs.get(key, self.tabs["general"])
        a.setChecked(True)
        self.pages.setCurrentWidget(page)
        self.setWindowTitle(title)                      # as macOS settings windows do
        settings().setValue("settings/tab", key)
        self.adjustSize()
        self.setFixedSize(self.sizeHint())

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(e)

    # ---- General ------------------------------------------------------------------------
    def _general(self):
        a, p = self.app.appearance, self.app.prefs
        f = _form()
        self.theme, w = segmented(self, (("system", "System"), ("light", "Light"),
                                          ("dark", "Dark")),
                                  lambda k: self.app.set_appearance(theme=k))
        self.theme.get(a["theme"], self.theme["system"]).setChecked(True)
        f.addRow("Theme:", w)
        self.density, w = segmented(self, (("compact", "Compact"),
                                           ("comfortable", "Comfortable")),
                                    lambda k: self.app.set_appearance(density=k))
        self.density.get(a["density"], self.density["compact"]).setChecked(True)
        f.addRow("Parts list:", w)
        self.quality = MenuSelect()
        self.quality.addItem("Same as Last Time", "last")
        for i, name in enumerate(CAD_QUALITY_NAMES):
            self.quality.addItem(name, i)
        self.quality.setCurrentIndex(max(0, self.quality.findData(p["cad_quality"])))
        self.quality.currentIndexChanged.connect(
            lambda _: self.app.set_pref(cad_quality=self.quality.currentData()))
        f.addRow("CAD meshing control:", self.quality)
        f.addRow("", _note("STEP, IGES and BREP files open at this level (Meshing Control)."))
        return _page(f)

    # ---- Appearance (the 3D view) ----------------------------------------------------------
    def _appearance(self):
        a = self.app.appearance
        f = _form()
        self.bg, w = segmented(self, (("default", "Default"), ("color", "Color"),
                                      ("image", "Image")), self._bg_mode)
        f.addRow("Background:", w)
        self.color = ColorField(a["bg_color"])
        self.color.changed.connect(lambda h: self.app.set_appearance(bg="color", bg_color=h))
        self.color_label = QLabel("Color:")
        f.addRow(self.color_label, self.color)
        self.image_row = QWidget()
        il = QHBoxLayout(self.image_row)
        il.setContentsMargins(0, 0, 0, 0)
        choose = QPushButton("Choose…")
        choose.clicked.connect(lambda: self._choose_image())
        self.image_name = QLabel("")
        self.image_name.setObjectName("InfoLine")
        self.image_name.setMaximumWidth(200)
        il.addWidget(choose)
        il.addWidget(self.image_name, 1)
        self.image_label = QLabel("Image:")
        f.addRow(self.image_label, self.image_row)

        self.shading = Switch(bool(a["shading"]))
        self.shading.toggled.connect(lambda on: self.app.set_appearance(shading=on))
        f.addRow("Shading:", _switch_row(self.shading, "Light and shadow"))
        f.addRow("", _note("Off: flat part colors."))

        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        self.axis_font = NoWheelSlider(Qt.Horizontal)
        self.axis_font.setRange(10, 28)
        self.axis_font.setPageStep(2)
        self.axis_font.setFixedWidth(170)
        self.axis_font.setValue(int(a["axis_font"]))
        self.axis_font_value = QLabel()
        self.axis_font_value.setObjectName("InfoLine")
        self.axis_font_value.setMinimumWidth(40)
        self.axis_font.valueChanged.connect(self._axis_font_changed)
        h.addWidget(self.axis_font)
        h.addWidget(self.axis_font_value)
        f.addRow("Axis labels:", row)

        self.edge_width, w = segmented(self, (("thin", "Thin"), ("medium", "Medium"),
                                              ("thick", "Thick")),
                                       lambda k: self.app.set_appearance(edge_width=k))
        self.edge_width.get(a["edge_width"], self.edge_width["thin"]).setChecked(True)
        f.addRow("Edge lines:", w)
        self.hide_edges = Switch(bool(a["hide_edges_moving"]))
        self.hide_edges.toggled.connect(
            lambda on: self.app.set_appearance(hide_edges_moving=on))
        f.addRow("", _switch_row(self.hide_edges, "Hide while the view moves"))
        f.addRow("", _note("Smoother turning on big models. Thin lines are the fastest."))

        self._axis_font_changed(self.axis_font.value(), save=False)
        mode = a["bg"] if not (a["bg"] == "image" and not a["bg_image"]) else "default"
        self.bg[mode].setChecked(True)
        self._show_rows(mode)
        self._image_text(a["bg_image"])
        return _page(f)

    def _axis_font_changed(self, pt, save=True):
        self.axis_font_value.setText(f"{pt} pt")
        if save:
            self.app.set_appearance(axis_font=int(pt))

    def _show_rows(self, mode):
        for w, on in ((self.color, mode == "color"), (self.color_label, mode == "color"),
                      (self.image_row, mode == "image"), (self.image_label, mode == "image")):
            w.setVisible(on)
        if self.pages.count() == len(TABS):            # (not while building)
            self.adjustSize()
            self.setFixedSize(self.sizeHint())

    def _bg_mode(self, mode):
        self._show_rows(mode)
        if mode == "image" and not self.app.appearance["bg_image"]:
            self._choose_image(cancelled=self._no_image)  # cancelled: back to default
            return
        elif mode == "color" and self.color.is_valid():
            self.app.set_appearance(bg="color", bg_color=self.color.value)
            return
        self.app.set_appearance(bg=mode)

    def _choose_image(self, cancelled=None):
        """A sheet on this window to pick the picture."""
        start = self.app.appearance["bg_image"] or str(Path.home())
        d = QFileDialog(self, "Background Image", start, IMAGE_FILTER)
        d.setFileMode(QFileDialog.ExistingFile)
        d.setWindowModality(Qt.WindowModal)
        d.fileSelected.connect(self._image_chosen)
        if cancelled is not None:
            d.rejected.connect(cancelled)
        self._image_dialog = d
        d.open()

    def _image_chosen(self, fn):
        if fn:
            self._image_text(fn)
            self.app.set_appearance(bg="image", bg_image=fn)

    def _no_image(self):
        self.bg["default"].setChecked(True)
        self._show_rows("default")
        self.app.set_appearance(bg="default")

    def _image_text(self, path):
        self.image_name.setText(Path(path).name if path else "No image chosen")
        self.image_name.setToolTip(path or "")

    # ---- Units ----------------------------------------------------------------------------
    def _units(self):
        p = self.app.prefs
        f = _form()
        self.shown = MenuSelect()
        self.shown.addItem("The File's Unit", "file")
        for k, text in UNITS:
            self.shown.addItem(text, k)
        self.shown.setCurrentIndex(max(0, self.shown.findData(p["shown_unit"])))
        self.shown.currentIndexChanged.connect(
            lambda _: self.app.set_pref(shown_unit=self.shown.currentData()))
        f.addRow("Show lengths in:", self.shown)
        f.addRow("", _note("For files opened the first time; the toolbar changes it per file."))
        self.unit_menus = {}
        for key, label in (("unit_mesh", "Meshes:"), ("unit_cad", "Triangle CAD (STL, OBJ…):")):
            m = MenuSelect()
            for k, text in UNITS:
                m.addItem(text, k)
            m.setCurrentIndex(max(0, m.findData(p[key])))
            m.currentIndexChanged.connect(
                lambda _, mm=m, kk=key: self.app.set_pref(**{kk: mm.currentData()}))
            self.unit_menus[key] = m
            f.addRow(label, m)
        f.addRow("", _note("The unit of files that don't say theirs. STEP and IGES always do."))
        self.ask = Switch(bool(p["ask_unit"]))
        self.ask.toggled.connect(lambda on: self.app.set_pref(ask_unit=on))
        f.addRow("", _switch_row(self.ask, "Ask when a file is opened the first time"))
        return _page(f)
