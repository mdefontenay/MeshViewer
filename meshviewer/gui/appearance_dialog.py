"""Appearance sheet, in four groups:
    Window         theme, parts list spacing
    3D background  default gradient, a colour, or an image
    Axes & grid    label size, grid lines, axis lines
    Edges          line thickness, hide while the view moves
Changes apply live and are remembered for every window."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QFrame, QHBoxLayout, QLabel, QLayout,
    QPushButton, QVBoxLayout, QWidget,
)

from .widgets import Capsule, ColorField, NoWheelSlider, Switch

IMAGE_FILTER = "Images (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)"


def _segmented(parent, items, slot):
    group = QActionGroup(parent)
    group.setExclusive(True)
    actions = {}
    for key, text in items:
        a = QAction(text, parent)
        a.setCheckable(True)
        a.setData(key)
        group.addAction(a)
        actions[key] = a
    group.triggered.connect(lambda a: slot(a.data()))
    return actions, Capsule(list(actions.values()), name="Segmented")


def _group_title(text):
    t = QLabel(text)
    t.setObjectName("GroupTitle")
    return t


def _separator():
    line = QFrame()
    line.setObjectName("Divider")
    line.setFixedHeight(1)
    return line


def _switch_row(switch, hint):
    row = QWidget()
    hl = QHBoxLayout(row)
    hl.setContentsMargins(0, 0, 0, 0)
    label = QLabel(hint)
    label.setObjectName("InfoLine")
    hl.addWidget(switch)
    hl.addWidget(label)
    hl.addStretch(1)
    return row


class AppearanceDialog(QDialog):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app                                 # MeshViewerApp: holds the settings
        self.setWindowTitle("Appearance")
        self.setWindowModality(Qt.WindowModal)         # a sheet on macOS
        a = app.appearance

        lay = QVBoxLayout(self)
        lay.setSizeConstraint(QLayout.SetFixedSize)
        lay.setContentsMargins(20, 18, 20, 14)
        lay.setSpacing(12)
        title = QLabel("Appearance")
        title.setStyleSheet("font-size: 15px; font-weight: 600;")
        lay.addWidget(title)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(10)

        # v2.16: four groups, each under a title and separated by a line.
        # ---- Window ------------------------------------------------------------------
        form.addRow(_group_title("Window"))
        self.theme, w = _segmented(self, (("system", "System"), ("light", "Light"),
                                          ("dark", "Dark")),
                                   lambda k: self.app.set_appearance(theme=k))
        form.addRow("Theme", w)
        self.density, w = _segmented(self, (("compact", "Compact"), ("comfortable", "Comfortable")),
                                     lambda k: self.app.set_appearance(density=k))
        form.addRow("Parts list", w)

        # ---- 3D background ---------------------------------------------------------------
        form.addRow(_separator())
        form.addRow(_group_title("3D background"))
        self.bg, w = _segmented(self, (("default", "Default"), ("color", "Colour"),
                                       ("image", "Image")), self._bg_mode)
        form.addRow("Style", w)

        self.color = ColorField(a["bg_color"])
        self.color.changed.connect(lambda h: self.app.set_appearance(bg="color", bg_color=h))
        self.color_label = QLabel("Colour")
        form.addRow(self.color_label, self.color)

        self.image_row = QWidget()
        il = QHBoxLayout(self.image_row)
        il.setContentsMargins(0, 0, 0, 0)
        self.image_name = QLabel("")
        self.image_name.setObjectName("InfoLine")
        self.image_name.setMaximumWidth(220)
        choose = QPushButton("Choose…")
        choose.clicked.connect(self._choose_image)
        il.addWidget(choose)
        il.addWidget(self.image_name, 1)
        self.image_label = QLabel("Image")
        form.addRow(self.image_label, self.image_row)

        # ---- Axes & grid ----------------------------------------------------------------
        form.addRow(_separator())
        form.addRow(_group_title("Axes & grid"))
        font_row = QWidget()                       # label size slider (10 pt = original)
        fl = QHBoxLayout(font_row)
        fl.setContentsMargins(0, 0, 0, 0)
        self.axis_font = NoWheelSlider(Qt.Horizontal)
        self.axis_font.setRange(10, 28)
        self.axis_font.setPageStep(2)
        self.axis_font.setFixedWidth(180)
        self.axis_font.setValue(int(a["axis_font"]))
        self.axis_font_value = QLabel()
        self.axis_font_value.setObjectName("InfoLine")
        self.axis_font_value.setMinimumWidth(40)
        self.axis_font.valueChanged.connect(self._axis_font_changed)
        fl.addWidget(self.axis_font)
        fl.addWidget(self.axis_font_value)
        fl.addStretch(1)
        form.addRow("Label size", font_row)

        # Grid lines (walls behind the model) and, NEW (v2.16), axis lines (frame +
        # tick marks) side by side. Numbers and titles always stay;
        # Display ▸ Grid hides everything.
        self.grid_lines = Switch(bool(a["grid_lines"]))
        self.grid_lines.toggled.connect(lambda on: self.app.set_appearance(grid_lines=on))
        self.axis_lines = Switch(bool(a["axis_lines"]))
        self.axis_lines.toggled.connect(lambda on: self.app.set_appearance(axis_lines=on))
        show_row = QWidget()
        sl = QHBoxLayout(show_row)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(6)
        for sw, text, tip in ((self.grid_lines, "Grid lines", "Lines on the walls behind the model"),
                              (self.axis_lines, "Axis lines", "Axis frame and tick marks")):
            lab = QLabel(text)
            lab.setToolTip(tip)
            sw.setToolTip(tip)
            sl.addWidget(sw)
            sl.addWidget(lab)
            sl.addSpacing(14)
        sl.addStretch(1)
        form.addRow("Show", show_row)

        # ---- Edges ------------------------------------------------------------------------
        form.addRow(_separator())
        form.addRow(_group_title("Edges"))
        self.edge_width, w = _segmented(self, (("thin", "Thin"), ("medium", "Medium"),
                                               ("thick", "Thick")),
                                        lambda k: self.app.set_appearance(edge_width=k))
        w.setToolTip("Thickness of the feature edge lines (1 / 1.5 / 2 px).\n"
                     "Thin is the fastest to draw.")
        form.addRow("Thickness", w)
        self.hide_edges = Switch(bool(a["hide_edges_moving"]))
        self.hide_edges.toggled.connect(lambda on: self.app.set_appearance(hide_edges_moving=on))
        form.addRow("While moving", _switch_row(self.hide_edges, "hide them — smoother"))
        lay.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.button(QDialogButtonBox.Ok).setText("Done")
        buttons.accepted.connect(self.accept)
        lay.addWidget(buttons)

        self.theme[a["theme"]].setChecked(True)
        self.density.get(a["density"], self.density["compact"]).setChecked(True)
        self.edge_width.get(a["edge_width"], self.edge_width["thin"]).setChecked(True)
        self._axis_font_changed(self.axis_font.value(), save=False)
        mode = a["bg"] if not (a["bg"] == "image" and not a["bg_image"]) else "default"
        self.bg[mode].setChecked(True)
        self._show_rows(mode)
        self._image_text(a["bg_image"])

    # ---- handlers ---------------------------------------------------------------
    def _axis_font_changed(self, pt, save=True):
        self.axis_font_value.setText(f"{pt} pt")
        if save:
            self.app.set_appearance(axis_font=int(pt))

    def _show_rows(self, mode):
        for widget, on in ((self.color, mode == "color"), (self.color_label, mode == "color"),
                           (self.image_row, mode == "image"), (self.image_label, mode == "image")):
            widget.setVisible(on)

    def _bg_mode(self, mode):
        self._show_rows(mode)
        if mode == "image" and not self.app.appearance["bg_image"]:
            if not self._choose_image():                 # cancelled: back to default
                self.bg["default"].setChecked(True)
                self._show_rows("default")
                mode = "default"
        elif mode == "color" and self.color.is_valid():
            self.app.set_appearance(bg="color", bg_color=self.color.value)
            return
        self.app.set_appearance(bg=mode)

    def _choose_image(self):
        start = self.app.appearance["bg_image"] or str(Path.home())
        fn, _ = QFileDialog.getOpenFileName(self, "Background image", start, IMAGE_FILTER)
        if not fn:
            return False
        self._image_text(fn)
        self.app.set_appearance(bg="image", bg_image=fn)
        return True

    def _image_text(self, path):
        self.image_name.setText(Path(path).name if path else "No image chosen")
        self.image_name.setToolTip(path or "")
