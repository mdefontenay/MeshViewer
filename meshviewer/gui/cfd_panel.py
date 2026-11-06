"""NEW (v2.10): sidebar section "CFD" — y+ estimate (flat-plate boundary layer).
v2.11.1: "Flow" and "y+ estimator" are groups that fold; each has a "Values" pop-up
with every computed number; the auto length is the longest streamwise distance.

    ⌄ Flow                                          Values
      Fluid          [ Air — altitude          ▾ ]
      Altitude       [ 0        ] m     ?          (U.S. Standard Atmosphere)
      Density        [ 1.225    ] kg/m³
      Viscosity      [ 1.789e-5 ] Pa·s
      Sound speed    [ 340.29   ] m/s
      Mach           [ 0.3      ]
                        X      Y      Z
      Direction      [ 1  ] [ 0  ] [ 0  ]              any length
      Speed U = 102 m/s
      Show flow vectors                      (switch)
    ⌄ y+ estimator                              ?   Values
      Boundary       [ wing                    ▾ ]
      Length         [ auto: 1.23 ] m                   longest distance along the flow
      Target y+      [ 1 ]
      ┌ Max y+ on wing (from the mesh)
      │ 3.2   min 0.8
      │ First cell height for y+ = 1
      └ 3.88 µm

Lengths of the mesh are converted to metres with the file's unit (or the one
chosen in the toolbar); without any, the mesh is taken to be in metres.
"""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from .. import cfd
from .jobs import run_job
from .measure import UNITS, fmt
from .cfd_view import YPLUS_STOPS
from .widgets import (
    CollapsibleSection, FormulasButton, GradientBar, MenuSelect, NumberField, Switch, UnitField,
    ValuesButton, color_dot, help_button,
)

YPLUS_URL = "https://www.cfd-online.com/Wiki/Dimensionless_wall_distance_(y_plus)"
ATMOSPHERE_URL = "https://www.engineeringtoolbox.com/standard-atmosphere-d_604.html"
FLUIDS = (("air", "Air — altitude"), ("fresh", "Fresh water — depth"),
          ("sea", "Sea water — depth"), ("custom", "Custom"))
DEFAULTS = {"fluid": "air", "level": 0.0, "mach": 0.3, "direction": [1.0, 0.0, 0.0],
            "boundary": None, "length": None, "target": 1.0, "vectors": False,
            "speed_unit": "m/s", "compressible": True, "colour": False,       # v2.11.3
            "units": {}}                                     # v2.11.4: unit of each field
SPEED_UNITS = {"m/s": 1.0, "km/h": 1 / 3.6, "kt": 1852 / 3600, "ft/s": 0.3048,
               "mph": 0.44704}                                      # v2.11.3: -> m/s
# v2.11.4: units of the other inputs (factor to the first, SI, unit)
LEVEL_UNITS = {"m": 1.0, "km": 1000.0, "ft": 0.3048}
DENSITY_UNITS = {"kg/m³": 1.0, "g/cm³": 1000.0, "lb/ft³": 16.018463, "slug/ft³": 515.378818}
VISCOSITY_UNITS = {"Pa·s": 1.0, "cP": 1e-3, "lb/ft·s": 1.488164}
LENGTH_UNITS = {"m": 1.0, "cm": 0.01, "mm": 0.001, "in": 0.0254, "ft": 0.3048}
# v2.11.3: colour of the max y+ against the target (same colours as the 3D view)
GOOD, FAIR = 1.25, 2.5


def yplus_grade(ratio):
    """max y+ / target -> colour: green (≤ 1.25), orange (≤ 2.5), red."""
    return "#30b350" if ratio <= GOOD else "#ff9f0a" if ratio <= FAIR else "#ff453a"


# v2.11.3: what the "Formulas" buttons show — (explanation, LaTeX) or a sub-title
FLOW_FORMULAS = [
    "Air — U.S. Standard Atmosphere 1976",
    ("Geopotential altitude, from the altitude z (Earth radius R_E = 6 356 766 m)",
     r"h = \frac{R_E\, z}{R_E + z}"),
    ("Temperature in the layer that holds h (base h_b, T_b, lapse rate L_b)",
     r"T = T_b + L_b\,(h - h_b)"),
    ("Pressure: layers with a lapse rate, then isothermal layers (g₀ = 9.80665 m/s²)",
     r"p = p_b \left(\frac{T_b}{T}\right)^{g_0 / (R L_b)} \qquad "
     r"p = p_b\, e^{-g_0 (h - h_b) / (R T_b)}"),
    ("Density (R = 287.05 J/(kg·K))", r"\rho = \frac{p}{R\, T}"),
    ("Viscosity (Sutherland)", r"\mu = 1.458\times10^{-6}\, \frac{T^{3/2}}{T + 110.4}"),
    ("Speed of sound (γ = 1.4)", r"a = \sqrt{\gamma R T}"),
    "Water at 15 °C",
    ("Density at a depth d (bulk modulus K)",
     r"\rho = \rho_0 \left(1 + \frac{\rho_0\, g_0\, d}{K}\right)"),
    "Flow",
    ("Speed", r"U = M\, a"),
    ("Kinematic viscosity and dynamic pressure",
     r"\nu = \frac{\mu}{\rho} \qquad q = \frac{1}{2}\rho U^2"),
    ("Total temperature", r"T_0 = T \left(1 + \frac{\gamma - 1}{2} M^2\right)"),
    ("Reynolds number (L: the length in y+ estimator); turbulent above 5×10⁵",
     r"\mathrm{Re}_L = \frac{\rho\, U L}{\mu}"),
]
YPLUS_FORMULAS = [
    "Flat plate, turbulent boundary layer",
    ("Reference length (when empty): the longest distance across the boundary along "
     "the flow d̂ — the longest strip of points parallel to the flow",
     r"L = \max_{\mathrm{strips}} \left( \max\, \mathbf{x}\cdot\hat{d} - "
     r"\min\, \mathbf{x}\cdot\hat{d} \right)"),
    ("Skin friction (Schlichting)",
     r"C_{f,\,\mathrm{inc}} = \left(2 \log_{10} \mathrm{Re}_L - 0.65\right)^{-2.3}"),
    ("Compressibility correction, when on (Raymer; adiabatic wall)",
     r"C_f = C_{f,\,\mathrm{inc}} \left(1 + 0.144\, M^2\right)^{-0.65}"),
    ("Wall shear stress and friction velocity",
     r"\tau_w = C_f\, \frac{1}{2} \rho U^2 \qquad u_* = \sqrt{\frac{\tau_w}{\rho}}"),
    ("y+ of a first cell of height y", r"y^+ = \frac{y\, u_*\, \rho}{\mu}"),
    ("First cell height for the target y+", r"y_1 = \frac{y^+_{\mathrm{target}}\, \mu}"
     r"{\rho\, u_*}"),
    "From the mesh",
    ("First cell at a wall node P: the shortest step to a node Q off the wall, along an "
     "edge of a cell touching the wall, measured along the wall normal n̂",
     r"y_P = \min_Q \left| (\mathbf{x}_Q - \mathbf{x}_P)\cdot \hat{n}_P \right|"),
    ("Colours (3D view and the max): y+ / target — blue 0 · green 1 · orange 2 · red 3 or "
     "more. The max is green up to 1.25 × target, orange up to 2.5 ×, then red", ""),
]


def nice_length(m):
    """3.88 µm, 0.42 mm, 1.2 m."""
    if m is None or not np.isfinite(m):
        return "—"
    a = abs(m)
    if a < 1e-3:
        return f"{m * 1e6:.3g} µm"
    if a < 1:
        return f"{m * 1e3:.3g} mm"
    return f"{m:.3g} m"


def _label(text, name=None):
    lab = QLabel(text)
    if name:
        lab.setObjectName(name)
    return lab


def _grid():
    g = QGridLayout()
    g.setContentsMargins(0, 0, 0, 0)
    g.setHorizontalSpacing(6)
    g.setVerticalSpacing(5)
    g.setColumnStretch(1, 1)
    g.setColumnMinimumWidth(0, QLabel("Sound speed").sizeHint().width())  # v2.11.1: groups align
    g.setColumnMinimumWidth(2, 38)               # unit column, same in both groups
    g.setColumnMinimumWidth(3, 16)               # "?" column
    return g


def _row(g, r, text, widget, unit=None, extra=None, wide=False):
    """Label, field, unit, "?" -> (label, unit label). v2.11.4: a UnitField puts its
    unit menu in the unit columns; wide = the field spans them (no unit)."""
    lab = QLabel(text)
    g.addWidget(lab, r, 0)
    g.addWidget(widget, r, 1, 1, 3 if wide else 1)
    u = None
    if isinstance(widget, UnitField):
        g.addWidget(widget.menu, r, 2, 1, 2)
        u = widget.menu
    elif unit:
        u = _label(unit, "AxisLabel")
        g.addWidget(u, r, 2)
    if extra is not None:
        g.addWidget(extra, r, 3)
    return lab, u


class CfdPanel(QWidget):
    changed = Signal()                         # settings changed (remembered per file)
    measured = Signal()                        # volume cells read (Info can count them)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = None
        self._active = False
        self._heights = {}                     # boundary -> first-layer heights (model units)
        self._job = None
        self._busy = None
        self._props = None                     # air / water at the altitude / depth (T, p)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 0, 2, 0)
        lay.setSpacing(6)

        # ---- flow (v2.11.1: a group that folds) ---------------------------------------------
        flow = QWidget()
        fl = QVBoxLayout(flow)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(6)
        g = _grid()
        self.fluid = MenuSelect()
        for key, text in FLUIDS:
            self.fluid.addItem(text, key)
        self.fluid.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.fluid.currentIndexChanged.connect(self._fluid_changed)
        _row(g, 0, "Fluid", self.fluid, wide=True)

        self.level = UnitField(LEVEL_UNITS, 0.0)       # v2.11.4: unit menus
        self.level.valueChanged.connect(self._fluid_changed)
        self.level.unitChanged.connect(self._unit_changed)
        self.level_help = help_button(ATMOSPHERE_URL, "U.S. Standard Atmosphere (1976)")
        _, self.level_unit = _row(g, 1, "", self.level)
        self.level_label = QLabel("Altitude")          # v2.11.4: the "?" right after the name
        self.level_head = QWidget()
        hl = QHBoxLayout(self.level_head)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(5)
        hl.addWidget(self.level_label)
        hl.addWidget(self.level_help)
        hl.addStretch(1)
        g.addWidget(self.level_head, 1, 0)

        self.rho = UnitField(DENSITY_UNITS)
        self.mu = UnitField(VISCOSITY_UNITS)
        self.a = UnitField(SPEED_UNITS)
        for r, (text, box, tip) in enumerate((
                ("Density", self.rho, "ρ of the free stream"),
                ("Viscosity", self.mu, "Dynamic viscosity μ of the free stream"),
                ("Sound speed", self.a, "Speed of sound a (speed U = Mach × a)")),
                start=2):
            box.setToolTip(tip)
            box.valueChanged.connect(self._property_typed)
            box.unitChanged.connect(self._unit_changed)
            _row(g, r, text, box)

        self.mach = NumberField(0.3)
        self.mach.setToolTip("Free-stream Mach number (U = Mach × a)")
        self.mach.valueChanged.connect(self._update)
        _row(g, 5, "Mach", self.mach)
        # v2.11.2: the speed can be typed too; Mach follows (and the other way round)
        self.u = UnitField(SPEED_UNITS)                # v2.11.3 units; v2.11.4 a UnitField
        self.u.setToolTip("Free-stream speed U (Mach = U / a)")
        self.u.valueChanged.connect(self._speed_typed)
        self.u.unitChanged.connect(self._unit_changed)
        _row(g, 6, "Speed U", self.u)

        # v2.11.1: X / Y / Z above the three fields (like the section normal), and the
        # fields use the unit columns too, so the numbers are not clipped.
        axes = QWidget()
        al = QHBoxLayout(axes)
        al.setContentsMargins(0, 0, 0, 0)
        al.setSpacing(4)
        dirs = QWidget()
        dl = QHBoxLayout(dirs)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.setSpacing(4)
        self.direction = []
        for k, v in zip("XYZ", (1.0, 0.0, 0.0)):
            lab = _label(k, "AxisLabel")
            lab.setAlignment(Qt.AlignCenter)
            al.addWidget(lab, 1)
            b = NumberField(v)
            b.setMinimumWidth(0)
            b.setAlignment(Qt.AlignCenter)
            b.setToolTip(f"Flow direction, {k} (any length: only the direction counts)")
            b.valueChanged.connect(self._direction_changed)
            dl.addWidget(b, 1)
            self.direction.append(b)
        g.addWidget(axes, 7, 1, 1, 3)
        lab = QLabel("Direction")
        lab.setToolTip("Flow direction X / Y / Z (any length)")
        g.addWidget(lab, 8, 0)
        g.addWidget(dirs, 8, 1, 1, 3)
        fl.addLayout(g)

        r = QHBoxLayout()
        r.addWidget(QLabel("Show flow vectors"))
        r.addStretch(1)
        self.vectors = Switch()
        self.vectors.setToolTip("Small arrows before and after the boundary, along the flow")
        self.vectors.toggled.connect(self._vectors_toggled)
        r.addWidget(self.vectors)
        fl.addLayout(r)
        self.flow_values = ValuesButton("Flow", tip="Every flow value: Re, T, p, ν, q…")
        ftail = QWidget()
        ftl = QHBoxLayout(ftail)
        ftl.setContentsMargins(0, 0, 0, 0)
        ftl.setSpacing(10)
        self.flow_formulas = FormulasButton("Flow — formulas", FLOW_FORMULAS)   # v2.11.3
        ftl.addWidget(self.flow_formulas)
        ftl.addWidget(self.flow_values)
        self.flow_section = CollapsibleSection("Flow", flow, "cfd_flow", trailing=ftail,
                                               sub=True)
        lay.addWidget(self.flow_section)

        # ---- y+ estimator (v2.11.1: a group that folds) --------------------------------------
        yp = QWidget()
        yl = QVBoxLayout(yp)
        yl.setContentsMargins(0, 0, 0, 0)
        yl.setSpacing(6)
        g = _grid()
        self.boundary = MenuSelect()
        self.boundary.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.boundary.currentIndexChanged.connect(self._boundary_changed)
        _row(g, 0, "Boundary", self.boundary, wide=True)
        self.length = UnitField(LENGTH_UNITS)
        self.length.setToolTip("Reference length for the Reynolds number. Empty = the\n"
                               "longest distance across the boundary along the flow\n"
                               "(e.g. the root chord of a swept wing)")
        self.length.valueChanged.connect(self._update)
        self.length.unitChanged.connect(self._unit_changed)
        _row(g, 1, "Length", self.length)
        self.target = NumberField(1.0)
        self.target.setToolTip("The y+ you want: gives the first cell height to use")
        self.target.valueChanged.connect(self._update)
        _row(g, 2, "Target y+", self.target)
        yl.addLayout(g)
        r = QHBoxLayout()                              # v2.11.4: back to the auto length
        r.setContentsMargins(0, 0, 0, 0)
        r.addStretch(1)
        self.auto_length = QPushButton("Back to auto length")
        self.auto_length.setObjectName("LinkButton")
        self.auto_length.setFlat(True)
        self.auto_length.setCursor(Qt.PointingHandCursor)
        self.auto_length.setToolTip("Forget the typed length: use the longest distance\n"
                                    "across the boundary along the flow")
        self.auto_length.clicked.connect(self._auto_length)
        self.auto_length.setVisible(False)
        r.addWidget(self.auto_length)
        yl.addLayout(r)
        r = QHBoxLayout()                              # v2.11.3
        r.addWidget(QLabel("Compressibility correction"))
        r.addStretch(1)
        self.compressible = Switch(True)
        self.compressible.setToolTip("Lower skin friction at high Mach (Raymer):\n"
                                     "Cf × (1 + 0.144 M²)^−0.65 — about −1 % at M 0.3,\n"
                                     "−30 % at M 2, −50 % at M 3")
        self.compressible.toggled.connect(self._update)
        r.addWidget(self.compressible)
        yl.addLayout(r)

        self.card = QFrame()
        self.card.setObjectName("ResultCard")
        cl = QVBoxLayout(self.card)
        cl.setContentsMargins(12, 10, 12, 10)
        cl.setSpacing(2)
        self.yplus_caption = _label("Max y+ from the mesh", "Caption")
        cl.addWidget(self.yplus_caption)
        big = QHBoxLayout()                     # v2.11.1: max big, min small beside it
        big.setSpacing(8)
        self.yplus = _label("—", "BigValue")
        self.yplus.setTextInteractionFlags(Qt.TextSelectableByMouse)
        big.addWidget(self.yplus, 0, Qt.AlignBottom)
        self.yplus_min = _label("", "SmallNote")          # v2.11.2: "min 0.8 · mean 1.4"
        big.addWidget(self.yplus_min, 0, Qt.AlignBottom)
        big.addStretch(1)
        cl.addLayout(big)
        self.yplus_range = _label("", "InfoLine")
        self.yplus_range.setWordWrap(True)
        cl.addWidget(self.yplus_range)
        spacer = QWidget()
        spacer.setFixedHeight(6)
        cl.addWidget(spacer)
        self.height_caption = _label("First cell height for y+ = 1", "Caption")
        cl.addWidget(self.height_caption)
        big = QHBoxLayout()                     # v2.11.2: the mesh's max first cell beside it
        big.setSpacing(8)
        self.height = _label("—", "BigValue")
        self.height.setTextInteractionFlags(Qt.TextSelectableByMouse)
        big.addWidget(self.height, 0, Qt.AlignBottom)
        self.height_mesh = _label("", "SmallNote")
        self.height_mesh.setToolTip("Largest first cell height on the boundary, in the mesh now")
        big.addWidget(self.height_mesh, 0, Qt.AlignBottom)
        big.addStretch(1)
        cl.addLayout(big)
        self.height_file = _label("", "InfoLine")
        cl.addWidget(self.height_file)
        yl.addWidget(self.card)
        r = QHBoxLayout()                              # v2.11.3: colour the boundary by y+
        r.addWidget(QLabel("Colour by y+"))
        r.addStretch(1)
        self.colour = Switch()
        self.colour.setToolTip("Paint the boundary by its y+ at each wall node (volume meshes)")
        self.colour.toggled.connect(self._colour_toggled)
        r.addWidget(self.colour)
        yl.addLayout(r)
        top = YPLUS_STOPS[-1][0]
        self.legend = GradientBar([(x / top, c) for x, c in YPLUS_STOPS],
                                  [(0, "0"), (1 / top, "target"), (2 / top, "2×"),
                                   (1, "3× or more")])
        self.legend.setToolTip("y+ / target. Grey: no first cell found")
        self.legend.setVisible(False)
        yl.addWidget(self.legend)
        self.note = _label("", "InfoLine")
        self.note.setWordWrap(True)
        yl.addWidget(self.note)
        tail = QWidget()
        tl = QHBoxLayout(tail)
        tl.setContentsMargins(0, 0, 0, 0)
        tl.setSpacing(10)
        tl.addWidget(help_button(YPLUS_URL, "Dimensionless wall distance (y plus)"))
        self.yplus_formulas = FormulasButton("y+ estimator — formulas", YPLUS_FORMULAS)
        tl.addWidget(self.yplus_formulas)
        self.yplus_values = ValuesButton("y+ estimator", tip="Every y+ value: Cf, τw, u*…")
        tl.addWidget(self.yplus_values)
        self.yplus_section = CollapsibleSection("y+ estimator", yp, "cfd_yplus", trailing=tail,
                                                sub=True)
        lay.addWidget(self.yplus_section)
        w = max(b.menu.minimumWidth() for b in self._unit_fields().values())
        for b in self._unit_fields().values():          # v2.11.4: unit menus line up
            b.menu.setMinimumWidth(w)
        self._fill_properties()

    # ---- binding / settings ---------------------------------------------------------
    def bind(self, scene):
        if self.scene is not None:
            self.scene.flow.hide()
            self.scene.yplus_view.hide()
        self.scene = scene
        self._heights = {}
        self.boundary.blockSignals(True)
        self.boundary.clear()
        for n in scene.names:
            self.boundary.addItem(n, n, color_dot(scene.colors[n]))     # v2.11.4: its colour
        self.boundary.blockSignals(False)
        st = {**DEFAULTS, **(getattr(scene, "cfd_settings", None) or {})}
        self.fluid.blockSignals(True)
        self.fluid.setCurrentIndex(max(self.fluid.findData(st["fluid"]), 0))
        self.fluid.blockSignals(False)
        units = {"u": st.get("speed_unit", "m/s"), **(st.get("units") or {})}
        for key, box in self._unit_fields().items():                 # v2.11.4
            box.set_unit(units.get(key, next(iter(box.units))))
        self.level.setValue(st["level"])
        self.mach.setValue(st["mach"])
        for b, v in zip(self.direction, st["direction"]):
            b.setValue(v)
        self.length.setValue(st["length"])
        self.target.setValue(st["target"])
        i = self.boundary.findData(st["boundary"])
        self.boundary.setCurrentIndex(i if i >= 0 else 0)
        self._fill_properties(custom=st if st["fluid"] == "custom" else None)
        Switch.set_silently(self.vectors, bool(st["vectors"]))
        Switch.set_silently(self.compressible, bool(st["compressible"]))
        Switch.set_silently(self.colour, bool(st["colour"]))
        self.legend.setVisible(self.colour.isChecked())
        self._update(save=False)
        self._sync_vectors()

    def refresh_names(self):
        """Parts renamed / re-meshed: same boundary (by position), new names."""
        if self.scene is None:
            return
        i = self.boundary.currentIndex()
        self.boundary.blockSignals(True)
        self.boundary.clear()
        for n in self.scene.names:
            self.boundary.addItem(n, n, color_dot(self.scene.colors[n]))
        self.boundary.setCurrentIndex(min(max(i, 0), self.boundary.count() - 1))
        self.boundary.blockSignals(False)
        self._heights = {}
        self._update(save=False)
        self._measure_heights()

    def settings(self):
        return {"fluid": self.fluid.currentData(), "level": self.level.value() or 0.0,
                "rho": self.rho.value(), "mu": self.mu.value(), "a": self.a.value(),
                "mach": self.mach.value(), "direction": [b.value() or 0.0 for b in self.direction],
                "boundary": self.boundary.currentData(), "length": self.length.value(),
                "target": self.target.value(), "vectors": self.vectors.isChecked(),
                "speed_unit": self.u.unit(),
                "units": {k: b.unit() for k, b in self._unit_fields().items()},
                "compressible": self.compressible.isChecked(),
                "colour": self.colour.isChecked()}

    def _unit_fields(self):
        return {"level": self.level, "rho": self.rho, "mu": self.mu, "a": self.a, "u": self.u,
                "length": self.length}

    def refresh_colors(self):
        """v2.11.4: a part's colour changed: its dot in the Boundary menu follows."""
        if self.scene is None:
            return
        for i in range(self.boundary.count()):
            n = self.boundary._items[i][1]
            if n in self.scene.colors:
                self.boundary.setItemIcon(i, color_dot(self.scene.colors[n]))

    def _unit_changed(self, *_):
        self._update()                       # placeholders, remembered units

    def _auto_length(self):
        self.length.setValue(None)
        self._update()

    def activate(self, on):
        self._active = bool(on)
        if on:
            self._measure_heights()

    def model_changed(self):
        """The model moved: the flow vectors and the auto length follow."""
        self._update(save=False)
        self._sync_vectors()

    # ---- fluid -----------------------------------------------------------------------
    def _fluid_changed(self, *_):
        self._fill_properties()
        self._update()

    def _fill_properties(self, custom=None):
        kind = self.fluid.currentData()
        for w in (self.level, self.level_head, self.level_unit):
            w.setVisible(kind != "custom")
        for box in (self.rho, self.mu, self.a):     # v2.11.2: only typed for "Custom"
            box.setEnabled(kind == "custom")
        self.level_label.setText("Altitude" if kind == "air" else "Depth")
        self.level_help.setVisible(kind == "air")
        self.level.setToolTip("Geometric altitude above sea level (U.S. Standard Atmosphere 1976)"
                              if kind == "air" else "Depth below the surface (water at 15 °C)")
        if kind == "custom":
            self._props = None
            if custom:
                self.rho.setValue(custom.get("rho"))
                self.mu.setValue(custom.get("mu"))
                self.a.setValue(custom.get("a"))
            return
        h = self.level.value() or 0.0
        props = cfd.air(h) if kind == "air" else cfd.water(h, kind)
        self._props = props
        self.rho.setValue(props["rho"])
        self.mu.setValue(props["mu"])
        self.a.setValue(props["a"])

    def _property_typed(self, *_):
        """Your own density, viscosity or sound speed (Custom only: the boxes are
        locked for air and water)."""
        self._update()

    def _speed_typed(self, u):
        """NEW (v2.11.2): a typed speed sets the Mach number (M = U / a)."""
        a = self.a.value()
        if u is not None and a:
            self.mach.setValue(u / a)          # u in m/s (UnitField)
        self._update()

    def _colour_toggled(self, on):
        self.legend.setVisible(on)
        self._update()

    # ---- direction / vectors -------------------------------------------------------------
    def _dir(self):
        return np.array([b.value() or 0.0 for b in self.direction], dtype=float)

    def _direction_changed(self, *_):
        self._update()
        self._sync_vectors()

    def _vectors_toggled(self, on):
        self._sync_vectors()
        self._save()

    def _sync_vectors(self):
        if self.scene is None:
            return
        if self.vectors.isChecked() and np.linalg.norm(self._dir()):
            self.scene.flow.show(self._dir(), self._bounds())
        else:
            self.scene.flow.hide()

    def _bounds(self):
        name = self.boundary.currentData()
        sc = self.scene
        if name in sc.model.parts:
            return sc.model.parts[name].bounds
        return sc.model_bounds()

    # ---- boundary / first cell heights ---------------------------------------------------
    def _boundary_changed(self, *_):
        self._update()
        self._sync_vectors()
        self._measure_heights()

    def _to_metres(self):
        """(factor model units -> m, note)."""
        sc = self.scene
        unit = sc.model.units or sc.measure.display_unit
        if unit in UNITS:
            return UNITS[unit], ""
        return 1.0, "No unit in this file: the mesh is taken to be in metres " \
                    "(pick its unit in the toolbar)."

    def _measure_heights(self):
        sc = self.scene
        name = self.boundary.currentData()
        if (sc is None or not self._active or name is None or name in self._heights
                or not sc.section.has_volume or self._job is not None):
            return
        self._busy = name
        self._status("Measuring the first cell layer…")
        qv = sc.quality
        wall = sc.model.parts[name]

        def work():
            grid = qv.dataset()                     # reads the volume cells the first time
            return name, cfd.first_layer(grid, wall)
        self._job = run_job(work, self._measured, self._failed)

    def _measured(self, result):
        self._job = None
        name, h = result
        self._heights[name] = h
        self._update(save=False)
        self.measured.emit()
        if self.boundary.currentData() not in self._heights:
            self._measure_heights()

    def _failed(self, exc):
        self._job = None
        self._status(f"Could not measure the cells: {exc}")

    # ---- results -------------------------------------------------------------------------
    def _save(self):
        if self.scene is not None:
            self.scene.cfd_settings = self.settings()
            self.changed.emit()

    def _update(self, *_, save=True):
        sc = self.scene
        if sc is None:
            return
        if save:
            self._save()
        rho, mu, a = self.rho.value(), self.mu.value(), self.a.value()
        mach = self.mach.value() or 0.0
        name = self.boundary.currentData()
        to_m, note = self._to_metres()
        auto = None
        if name in sc.model.parts:                # v2.11.1: longest streamwise distance
            auto = cfd.streamwise_length(sc.model.parts[name].points, self._dir()) * to_m
        self.length.setPlaceholderText(f"auto: {auto / self.length.factor:.4g}" if auto
                                       else "auto")
        self.auto_length.setVisible(self.length.value() is not None)
        length = self.length.value() or auto
        self.note.setText(note)
        self.note.setVisible(bool(note))
        target = self.target.value() or 1.0
        self.height_caption.setText(f"First cell height for y+ = {target:g}")
        self.yplus_caption.setText(f"Max y+ on {name}" if name else "Max y+")
        if not (rho and mu and a) or rho <= 0 or mu <= 0:
            self.u.setValue(None)
            self._values(None, None, length, auto, target, None, None)
            self._show(None, None)
            self._paint(None)
            self._status("Fill in the flow to get y+.")
            return
        f = cfd.flow(rho, mu, a, mach, length or 0.0, compressible=self.compressible.isChecked())
        if not self.u.hasFocus():
            self.u.setValue(f["U"])
        if not length or not f["u_star"]:
            self._values(f, None, length, auto, target, None, None)
            self._show(None, None)
            self._paint(None)
            self._status("The flow is too slow for an estimate (Re ≤ 1)."
                                     if length else "Fill in a length.")
            return
        h = cfd.y_for(target, rho, mu, f["u_star"])
        heights = self._heights.get(name)
        yp = hm = None
        ratio = None
        if heights is not None:
            hm = np.asarray(heights) * to_m
            ratio = cfd.y_plus(hm, rho, mu, f["u_star"]) / target    # every node (NaN kept)
            hm = hm[np.isfinite(hm)]
            if len(hm):
                yp = cfd.y_plus(hm, rho, mu, f["u_star"])
            else:
                hm = None
        self._values(f, h, length, auto, target, yp, hm)
        self._show(yp, h, hm, target)
        self._paint(ratio)

    def _paint(self, ratio):
        """NEW (v2.11.3): Colour by y+ in the 3D view."""
        sc = self.scene
        if sc is None:
            return
        if self.colour.isChecked() and ratio is not None:
            sc.yplus_view.show(self.boundary.currentData(), ratio)
        elif sc.yplus_view.shown:
            sc.yplus_view.hide()

    def _values(self, f, h, length, auto, target, yp, hm):
        """NEW (v2.11.1): fill the two "Values" pop-ups."""
        rho, mu, a = self.rho.value(), self.mu.value(), self.a.value()
        g = lambda v, d=4: "—" if v is None else f"{v:.{d}g}"          # noqa: E731
        rows = [("Fluid", self.fluid.text(), "")]
        if self._props is not None:
            rows += [("Temperature T", g(self._props["T"]), "K"),
                     ("Pressure p", f"{self._props['p']:,.0f}", "Pa")]
        rows += [("Density ρ", g(rho), "kg/m³"), ("Viscosity μ", g(mu, 4), "Pa·s"),
                 ("Kinematic viscosity ν", g(mu / rho if mu and rho else None), "m²/s"),
                 ("Sound speed a", g(a), "m/s"), ("Mach M", g(self.mach.value() or 0.0), "")]
        if f is not None:
            q = 0.5 * rho * f["U"] ** 2
            rows += [("Speed U", g(f["U"]), "m/s")]
            if self.u.factor != 1.0:
                rows += [("", g(f["U"] / self.u.factor), self.u.unit())]
            rows += [("Dynamic pressure q", g(q), "Pa")]
            if self._props is not None and a:
                m = self.mach.value() or 0.0
                rows += [("Total temperature T₀",
                          g(self._props["T"] * (1 + (cfd.GAMMA - 1) / 2 * m * m)), "K")]
            if length:
                rows += [("Reynolds Re (length L)", f"{f['Re']:.4g}", ""),
                         ("Boundary layer", "turbulent" if f["Re"] > 5e5 else "laminar", "")]
        self.flow_values.set_rows(rows)

        rows = [("Boundary", self.boundary.currentData() or "—", ""),
                ("Length L (typed)" if self.length.value() else "Length L (auto)",
                 g(length), "m")]
        if auto and self.length.value():
            rows.append(("Auto (longest along the flow)", g(auto), "m"))
        if f is not None and f.get("u_star"):
            u = f["u_star"]
            rows += [("Reynolds Re", f"{f['Re']:.4g}", "")]
            if self.compressible.isChecked():
                rows += [("Cf incompressible", g(f["Cf_inc"]), ""),
                         ("Compressibility factor", g(f["Cf"] / f["Cf_inc"]), "")]
            rows += [("Skin friction Cf", g(f["Cf"]), ""),
                     ("Wall shear τw", g(f["tau"]), "Pa"), ("Friction velocity u*", g(u), "m/s"),
                     ("Viscous length ν/u*", nice_length(mu / (rho * u)), ""),
                     (f"First cell for y+ = {target:g}", nice_length(h), "")]
        if yp is not None:
            rows += [("From the mesh", None, None),
                     ("y+ max", g(np.max(yp), 3), ""), ("y+ mean", g(np.mean(yp), 3), ""),
                     ("y+ min", g(np.min(yp), 3), ""),
                     ("First cell max", nice_length(np.max(hm)), ""),
                     ("First cell mean", nice_length(np.mean(hm)), ""),
                     ("First cell min", nice_length(np.min(hm)), ""),
                     ("Wall nodes measured", f"{len(yp):,}", "")]
        self.yplus_values.set_rows(rows)

    def _status(self, text):
        """Line under the y+ value: only for messages (measuring, missing input…)."""
        self.yplus_range.setText(text)
        self.yplus_range.setVisible(bool(text))

    def _show(self, yp, h, hm=None, target=1.0):
        sc = self.scene
        if yp is not None:
            self.yplus.setText(f"{np.max(yp):.3g}")         # v2.11.1: max, min beside it
            self.yplus.setObjectName("BigValue")
            grade = yplus_grade(np.max(yp) / target)       # v2.11.3: green / orange / red
            self.yplus.setStyleSheet(f"color: {grade};")
            self.yplus.setToolTip(f"Max y+ = {np.max(yp) / target:.2g} × target\n"
                                  f"green ≤ {GOOD} ×, orange ≤ {FAIR} ×, red above")
            self.yplus_min.setText(f"min {np.min(yp):.3g} · mean {np.mean(yp):.3g}")
            self._status("")
        else:
            self.yplus.setText("—")
            self.yplus.setObjectName("MutedValue")
            self.yplus.setStyleSheet("")
            self.yplus.setToolTip("")
            self.yplus_min.setText("")
            if sc is not None and not sc.section.has_volume:
                self._status("needs volume cells (a CGNS / UGRID mesh)")
            elif self._busy is not None and self._job is not None:
                self._status("Measuring the first cell layer…")
            else:
                self._status("")
        self.yplus.style().unpolish(self.yplus)
        self.yplus.style().polish(self.yplus)
        self.height.setText(nice_length(h))
        self.height_mesh.setText(f"mesh max {nice_length(np.max(hm))}" if hm is not None else "")
        file_note = ""
        if h is not None and sc is not None:
            to_m, _ = self._to_metres()
            unit = sc.model.units or sc.measure.display_unit
            if unit:
                file_note = f"= {fmt(h / to_m, unit)} in the file"
        self.height_file.setText(file_note)
        self.height_file.setVisible(bool(file_note))
