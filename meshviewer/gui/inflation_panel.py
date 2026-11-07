"""NEW (v2.11): sidebar section "CFD mode" (CAD files) — the inputs of the
inflation layer calculator. Its plots are on the Inflation page (the pill under
the 3D view switches between the model and that page).
v2.12: laid out like the CFD section of meshes — "Flow" and "Inflation layers"
fold, each with Formulas and Values; unit menus; the speed U can be typed; flow
direction and arrows; the walls that get the layers (a part, or faces of one part
picked in the 3D view) give the auto length L.

v2.12.1: the Flow group is the same as in the CFD section of meshes (fluid, altitude
or depth, density / viscosity / sound speed locked unless Custom); the growth rate is
kept between 1 and 2; the desired cell is a factor of the largest layer.
v2.12.2: plain names — First layer, Layers, Growth rate, Next cell (× max layer height).
v2.14: Temperature (empty = standard); "?" next to Target y+ (resolve the wall or wall
functions, with the law of the wall); the y+ along the flow; export_info() for
Export ▸ CFD settings.
v2.14.2: Flow — external (length L) or internal, a pipe or duct (hydraulic diameter D);
the colours on the walls are gone (the y+ along the flow is the page's curve only).

    CFD mode                                          (switch)
    ⌄ Flow                                  Formulas   Values
      Fluid            [ Air — altitude          ▾ ]
      Altitude ?       [ 3000  ] [ m      ▾ ]
      Temperature      [ 268.7 ] [ K ▾ ]           (v2.14; v2.14.1: locked for air)
      Density          [ 0.909 ] [ kg/m³  ▾ ]      (locked unless Custom)
      Viscosity        [ 1.69e-5 ] [ Pa·s ▾ ]
      Sound speed      [ 328.6 ] [ m/s    ▾ ]
      Mach             [ 3     ]
      Speed U          [ 986   ] [ m/s    ▾ ]
                          X      Y      Z
      Direction        [ 1  ] [ 0  ] [ 0  ]
      Show flow vectors                              (switch)
    ⌄ Inflation layers                      Formulas   Values
      Walls            [ ● wing — 3 faces ▾ ]
                                            Pick faces…
      Flow             [ External — around the walls ▾ ]   (v2.14.2: or Internal — pipe)
      Length L         [ auto: 0.3 ] [ m ▾ ]      longest distance along the flow
                                                  (internal: Diameter D, hydraulic)
      Target y+ ?      [ 1     ]                   (v2.14: ? = which y+)
      Compressibility correction                     (switch)
      First layer      [ auto  ] [ µm ▾ ]
      Layers           [ 30    ]
      Growth rate      [ 1.3   ]                   1 – 2
      Next cell        [ 2     ] × max layer height
    ✓ covers the boundary layer · ✓ smooth transition
"""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget

from .. import cfd
from .cfd_panel import (
    ATMOSPHERE_URL, DENSITY_UNITS, FLOW_FORMULAS as MESH_FLOW_FORMULAS, FLUIDS, LENGTH_UNITS,
    LEVEL_UNITS, SPEED_UNITS, VISCOSITY_UNITS, _grid, _row, nice_length,
)
from .inflation_view import show_length
from .measure import UNITS
from .wall_help import label_with_help, wall_help_button
from .widgets import (
    CollapsibleSection, FormulasButton, MenuSelect, NumberField, Switch,
    TemperatureField, UnitField, ValuesButton, color_dot, help_button,
)

DEFAULTS = {"on": False, "yplus": 1.0, "mach": 0.3, "length": None,
            "altitude": 0.0, "temperature": None, "y_min": None, "layers": 30, "growth": 1.2,
            "fluid": "air", "rho": None, "mu": None, "a": None,       # v2.12.1: as the
            "y_des_factor": 2.0,                                     # CFD section
            "compressible": True,                                   # v2.11.3
            "direction": [1.0, 0.0, 0.0], "vectors": False,         # v2.12
            "kind": "external",                                     # v2.14.2: or internal
            "walls": None, "units": {}}       # walls: {"part": name, "faces": [ids] | None}
CELL_UNITS = {"m": 1.0, "mm": 1e-3, "µm": 1e-6, "in": 0.0254}       # v2.12
MODEL = "__model__"                     # Walls menu: the whole model
FACES = "__faces__"                     # Walls menu: the faces picked

# v2.12.1: the Flow formulas are the CFD section's (same fluid models)
FLOW_FORMULAS = [it if isinstance(it, str) else
                 (it[0].replace("in y+ estimator", "in Inflation layers"), it[1])
                 for it in MESH_FLOW_FORMULAS]
LAYER_FORMULAS = [
    "Wall shear (flat plate, turbulent)",
    ("Reference length (when empty): the longest distance across the walls along the "
     "flow d̂", r"L = \max_{\mathrm{strips}} \left( \max\, \mathbf{x}\cdot\hat{d} - "
                r"\min\, \mathbf{x}\cdot\hat{d} \right)"),
    ("Skin friction (Schlichting), and the compressibility correction when on (Raymer)",
     r"C_f = \left(2 \log_{10} \mathrm{Re}_L - 0.65\right)^{-2.3} "
     r"\left(1 + 0.144\, M^2\right)^{-0.65}"),
    ("Wall shear stress and friction velocity",
     r"\tau_w = C_f\, \frac{1}{2} \rho U^2 \qquad u_* = \sqrt{\frac{\tau_w}{\rho}}"),
    ("First cell for the target y+, and the y+ of the first cell used",
     r"y_{\mathrm{calc}} = \frac{y^+\, \mu}{\rho\, u_*} \qquad "
     r"y^+_{\mathrm{est}} = \frac{y_{\min}\, u_*\, \rho}{\mu}"),
    "Inflation layers",
    ("Height of layer n (n = 0 … N−1) and of the largest one",
     r"y_n = y_{\min}\, G^{\,n} \qquad y_{\max} = y_{\min}\, G^{\,N-1}"),
    ("Total height", r"y_{\mathrm{tot}} = \sum_{n=0}^{N-1} y_{\min} G^{\,n} = "
                     r"y_{\min} \frac{1 - G^N}{1 - G}"),
    "Boundary layer",
    ("Thickness: turbulent above Re 5×10⁵, else laminar",
     r"\delta_{99} = \frac{0.38\, L}{\mathrm{Re}_L^{1/5}} \qquad "
     r"\delta_{99} = \frac{4.91\, L}{\sqrt{\mathrm{Re}_L}}"),
    ("Supersonic (M > 1): divided by the recovery factor",
     r"\delta_{99,\,\mathrm{sup}} = \frac{\delta_{99}}{r_c^{1/9}} \qquad "
     r"r_c = 1 + \frac{\gamma - 1}{2} M^2"),
    "y+ along the flow (v2.14)",
    ("Distance x from the leading edge; local Reynolds number and skin friction of a flat "
     "plate, turbulent from the leading edge (Re_x held above 10⁴). The wall shear falls as "
     "the boundary layer thickens, so y+ falls too", r"\mathrm{Re}_x = \frac{\rho U x}{\mu}"
     r" \qquad C_{f,x} = \left(2 \log_{10} \mathrm{Re}_x - 0.65\right)^{-2.3}"),
    ("y+ of the first layer at x: highest near the leading edge, the target at x = L "
     "when the first layer is auto", r"y^+(x) = \frac{y_{\min}\, \rho}{\mu}\, U "
     r"\sqrt{\frac{C_{f,x}}{2}}"),
    "Internal flow — pipe or duct (v2.14.2)",
    ("Hydraulic diameter (when empty): from the walls' widths a, b across the flow — a "
     "round pipe gives its diameter", r"D = \frac{2ab}{a + b} \qquad "
     r"\mathrm{Re}_D = \frac{\rho U D}{\mu}"),
    ("Developed flow, smooth pipe: laminar below Re 2300, else Petukhov (Fanning Cf)",
     r"C_f = \frac{16}{\mathrm{Re}_D} \qquad C_f = \frac{(0.790 \ln \mathrm{Re}_D - "
     r"1.64)^{-2}}{4}"),
    ("Along the pipe: the entrance acts like a flat plate from the inlet, until it reaches "
     "the developed value; the boundary layer then fills the pipe (the check: the layers "
     "fit in the radius)", r"C_f(x) = \max\left(C_{f,x},\, C_f\right) \qquad "
     r"y_{\mathrm{tot}} < \frac{D}{2}"),
    "Checks",
    ("The layers are thicker than the boundary layer, and the next (ordinary) cell is a "
     "smooth step up: next cell size = factor × max layer height (2 by default)", r"y_{\mathrm{tot}} > \delta_{99} \qquad "
                       r"1.5 \leq \frac{y_{\mathrm{des}}}{y_{\max}} \leq 3"),
]


def _label(text, name=None):
    lab = QLabel(text)
    if name:
        lab.setObjectName(name)
    return lab


def _link(text, tip, slot):
    b = QPushButton(text)
    b.setObjectName("LinkButton")
    b.setFlat(True)
    b.setCursor(Qt.PointingHandCursor)
    b.setToolTip(tip)
    b.clicked.connect(slot)
    return b


class InflationPanel(QWidget):
    mode_toggled = Signal(bool)                # CFD mode on / off
    changed = Signal(object)                   # new result dict (cfd.inflation)
    wants_model = Signal()                     # v2.12: picking faces -> show the 3D view

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = None
        self.result = None
        self.walls = None                      # {"part": name, "faces": [ids] | None}
        self._names = []
        self._picking = False
        self._pick_part = None                 # files without CAD faces: a whole part
        self._props = None                     # v2.12.1: air / water at the altitude / depth
        lay = QVBoxLayout(self)
        lay.setContentsMargins(2, 0, 2, 0)
        lay.setSpacing(6)

        # On / off: shown in the section header by the sidebar.
        self.enable = Switch()
        self.enable.setToolTip("Inflation layer calculator: its plots open under the 3D view")
        self.enable.toggled.connect(self._enabled)
        self.hint = _label("Off — switch on for the inflation layer calculator.", "InfoLine")
        self.hint.setWordWrap(True)
        lay.addWidget(self.hint)

        self.details = QWidget()
        d = QVBoxLayout(self.details)
        d.setContentsMargins(0, 0, 0, 0)
        d.setSpacing(6)
        lay.addWidget(self.details)

        # ---- flow (v2.12: a group that folds) ---------------------------------------------
        flow = QWidget()
        fl = QVBoxLayout(flow)
        fl.setContentsMargins(0, 0, 0, 0)
        fl.setSpacing(6)
        g = _grid()                                      # v2.12.1: as the CFD section
        self.fluid = MenuSelect()
        for key, text in FLUIDS:
            self.fluid.addItem(text, key)
        self.fluid.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.fluid.currentIndexChanged.connect(self._fluid_changed)
        _row(g, 0, "Fluid", self.fluid, wide=True)
        self.altitude = UnitField(LEVEL_UNITS, 0.0)
        self.altitude.valueChanged.connect(self._fluid_changed)
        _, self.level_unit = _row(g, 1, "", self.altitude)
        self.level_label = QLabel("Altitude")
        self.level_help = help_button(ATMOSPHERE_URL, "U.S. Standard Atmosphere (1976)")
        self.level_head = QWidget()                      # "?" right after the name
        hl = QHBoxLayout(self.level_head)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.setSpacing(5)
        hl.addWidget(self.level_label)
        hl.addWidget(self.level_help)
        hl.addStretch(1)
        g.addWidget(self.level_head, 1, 0)
        self.temp = TemperatureField()                   # v2.14: empty = the standard one
        self.temp.setToolTip("Free-stream temperature. Air: the standard one at the altitude\n"
                             "(U.S. Standard Atmosphere), locked like ρ, μ and a. Water: type\n"
                             "it (empty = 15 °C)")
        self._temp_auto = False                    # v2.14.1: showing air's standard T
        self.temp.valueChanged.connect(self._fluid_changed)
        self.temp.unitChanged.connect(self._fluid_changed)
        self.temp_label, self.temp_unit = _row(g, 2, "Temperature", self.temp)
        self.rho = UnitField(DENSITY_UNITS)
        self.mu = UnitField(VISCOSITY_UNITS)
        self.a = UnitField(SPEED_UNITS)
        for r_, (text, box, tip) in enumerate((
                ("Density", self.rho, "ρ of the free stream"),
                ("Viscosity", self.mu, "Dynamic viscosity μ of the free stream"),
                ("Sound speed", self.a, "Speed of sound a (speed U = Mach × a)")), start=3):
            box.setToolTip(tip)
            box.valueChanged.connect(self._update)
            _row(g, r_, text, box)
        self.mach = NumberField(0.3)
        self.mach.setToolTip("Free-stream Mach number (U = Mach × a)")
        _row(g, 6, "Mach", self.mach)
        self.u = UnitField(SPEED_UNITS)                  # typed U -> Mach
        self.u.setToolTip("Free-stream speed U (Mach = U / a)")
        self.u.valueChanged.connect(self._speed_typed)
        _row(g, 7, "Speed U", self.u)
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
            b_ = NumberField(v)
            b_.setMinimumWidth(0)
            b_.setAlignment(Qt.AlignCenter)
            b_.setToolTip(f"Flow direction, {k} (any length: only the direction counts)")
            b_.valueChanged.connect(self._direction_changed)
            dl.addWidget(b_, 1)
            self.direction.append(b_)
        g.addWidget(axes, 8, 1, 1, 3)
        lab = QLabel("Direction")
        lab.setToolTip("Flow direction X / Y / Z (any length): gives the auto length L")
        g.addWidget(lab, 9, 0)
        g.addWidget(dirs, 9, 1, 1, 3)
        fl.addLayout(g)
        r = QHBoxLayout()
        r.addWidget(QLabel("Show flow vectors"))
        r.addStretch(1)
        self.vectors = Switch()
        self.vectors.setToolTip("Small arrows before and after the walls, along the flow")
        self.vectors.toggled.connect(self._vectors_toggled)
        r.addWidget(self.vectors)
        fl.addLayout(r)
        self.flow_values = ValuesButton("Flow", tip="Every flow value: Re, T, p, ν, q…")
        self.flow_section = CollapsibleSection(
            "Flow", flow, "cfdmode_flow", sub=True,
            trailing=self._tail(FormulasButton("Flow — formulas", FLOW_FORMULAS),
                                self.flow_values))
        d.addWidget(self.flow_section)

        # ---- inflation layers (v2.12: a group that folds) ---------------------------------
        lw = QWidget()
        ll = QVBoxLayout(lw)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.setSpacing(6)
        g = _grid()
        self.wall_menu = MenuSelect()                    # v2.12: the walls
        self.wall_menu.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.wall_menu.setToolTip("Surfaces that get the inflation layers: they give the\n"
                                  "auto length L, and are tinted in the 3D view")
        self.wall_menu.currentIndexChanged.connect(self._wall_chosen)
        _row(g, 0, "Walls", self.wall_menu, wide=True)
        ll.addLayout(g)
        r = QHBoxLayout()                                # Pick faces… / picking: Apply, Cancel
        r.setContentsMargins(0, 0, 0, 0)
        self.pick_info = _label("", "InfoLine")
        self.pick_info.setWordWrap(True)
        r.addWidget(self.pick_info, 1)
        r.addStretch(0)
        self.pick_btn = _link("Pick faces…", "Click faces of one part in the 3D view\n"
                              "(⇧-click to add more), then Apply", self._start_pick)
        self.apply_btn = QPushButton("Apply")
        self.apply_btn.clicked.connect(self._apply_pick)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self._cancel_pick)
        for b in (self.pick_btn, self.cancel_btn, self.apply_btn):
            r.addWidget(b)
        ll.addLayout(r)
        g = _grid()
        self.kind = MenuSelect()                         # v2.14.2: external / internal flow
        self.kind.addItem("External — around the walls", "external")
        self.kind.addItem("Internal — pipe or duct", "internal")
        self.kind.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.kind.setToolTip("External: a flat plate from the leading edge, Reynolds number on L.\n"
                             "Internal: developed pipe flow, Reynolds number on the hydraulic\n"
                             "diameter D; the entrance acts like a flat plate from the inlet")
        self.kind.currentIndexChanged.connect(self._kind_changed)
        _row(g, 0, "Flow", self.kind, wide=True)
        self.length = UnitField(LENGTH_UNITS)
        self.length.setToolTip("Reference length for the Reynolds number. Empty = the longest\n"
                               "distance across the walls along the flow")
        self.length_label, _ = _row(g, 1, "Length L", self.length)
        self.yplus = NumberField(1.0)
        self.yplus.setToolTip("The y+ you want at the wall")
        lab, _ = _row(g, 2, "Target y+", self.yplus)
        lab.hide()                                       # v2.14: "?" = which y+ to aim for
        g.addWidget(label_with_help("Target y+", wall_help_button(
            self.yplus.value, self._set_target)), 2, 0)
        ll.addLayout(g)
        r = QHBoxLayout()
        r.setContentsMargins(0, 0, 0, 0)
        r.addStretch(1)
        self.auto_length = _link("Back to auto length", "Forget the typed length: use the "
                                 "longest distance across the walls along the flow",
                                 self._auto_length)
        r.addWidget(self.auto_length)
        ll.addLayout(r)
        r = QHBoxLayout()                              # v2.11.3: same as the y+ estimator
        r.addWidget(QLabel("Compressibility correction"))
        r.addStretch(1)
        self.compressible = Switch(True)
        self.compressible.setToolTip("Lower skin friction at high Mach (Raymer):\n"
                                     "Cf × (1 + 0.144 M²)^−0.65. Off = the plain flat-plate\n"
                                     "Cf, as in the original calculator")
        self.compressible.toggled.connect(self._update)
        r.addWidget(self.compressible)
        ll.addLayout(r)
        g = _grid()
        self.y_min = UnitField(CELL_UNITS)
        self.y_min.setToolTip("Height of the first layer, at the wall (y_min).\n"
                              "Empty = the height that gives the target y+")
        _row(g, 0, "First layer", self.y_min)            # v2.12.2: plain names
        self.layers = NumberField(30)
        self.layers.setToolTip("Number of inflation layers (N)")
        _row(g, 1, "Layers", self.layers)
        self.growth = NumberField(1.2)
        self.growth.setRange(1.0, 2.0)                   # v2.12.1
        self.growth.setToolTip("Growth rate G: each layer is G times taller than the one\n"
                               "below it (between 1 and 2)")
        _row(g, 2, "Growth rate", self.growth)
        self.y_des = NumberField(2.0)                    # v2.12.1: a factor of y_max
        self.y_des.setRange(1.0, 10.0)
        self.y_des.setToolTip("Size of the first ordinary mesh cell above the layers, as a\n"
                              "multiple of the max layer height (about 2 is a smooth step; 1 – 10)")
        _row(g, 3, "Next cell", self.y_des)
        g.addWidget(_label("× max layer height", "AxisLabel"), 3, 2, 1, 2)
        ll.addLayout(g)
        self.summary = _label("", "InfoLine")
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(Qt.RichText)
        ll.addWidget(self.summary)
        self.note = _label("", "InfoLine")
        self.note.setWordWrap(True)
        ll.addWidget(self.note)
        self.layer_values = ValuesButton("Inflation layers",
                                         tip="Every value: Cf, τw, u*, layers, δ99…")
        self.layer_section = CollapsibleSection(
            "Inflation layers", lw, "cfdmode_layers", sub=True,
            trailing=self._tail(FormulasButton("Inflation layers — formulas", LAYER_FORMULAS),
                                self.layer_values))
        d.addWidget(self.layer_section)

        for box in (self.yplus, self.mach, self.length, self.altitude, self.y_min, self.layers,
                    self.growth, self.y_des):
            box.valueChanged.connect(self._update)
        for box in self._unit_fields().values():
            box.unitChanged.connect(self._update)
        w = max(b.menu.minimumWidth() for b in self._unit_fields().values())
        for b in self._unit_fields().values():           # unit menus line up
            b.menu.setMinimumWidth(w)
        self._show_pick_buttons()
        self._fill_properties()
        self.details.setVisible(False)

    @staticmethod
    def _tail(*widgets):
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(10)
        for x in widgets:
            h.addWidget(x)
        return w

    def _unit_fields(self):
        return {"altitude": self.altitude, "rho": self.rho, "mu": self.mu, "a": self.a,
                "u": self.u, "length": self.length, "y_min": self.y_min,
                "temperature": self.temp}

    # ---- binding / settings ------------------------------------------------------------
    def bind(self, scene):
        if self.scene is not None:
            self._cancel_pick()
            self.scene.walls.hide(render=False)
            self.scene.flow.hide(render=False)
        self.scene = scene
        st = {**DEFAULTS, **(getattr(scene, "inflation_settings", None) or {})}
        for key, box in self._unit_fields().items():
            box.set_unit((st.get("units") or {}).get(key, next(iter(box.units))))
        self._temp_auto = False
        for box, key in ((self.yplus, "yplus"), (self.mach, "mach"), (self.length, "length"),
                         (self.altitude, "altitude"), (self.y_min, "y_min"),
                         (self.temp, "temperature"),
                         (self.layers, "layers"), (self.growth, "growth"),
                         (self.y_des, "y_des_factor")):
            box.setValue(st[key])
        self.fluid.blockSignals(True)
        self.fluid.setCurrentIndex(max(self.fluid.findData(st["fluid"]), 0))
        self.fluid.blockSignals(False)
        self._fill_properties(custom=st if st["fluid"] == "custom" else None)
        for b, v in zip(self.direction, st["direction"]):
            b.setValue(v)
        Switch.set_silently(self.enable, bool(st["on"]))
        Switch.set_silently(self.compressible, bool(st["compressible"]))
        Switch.set_silently(self.vectors, bool(st["vectors"]))
        self.kind.blockSignals(True)
        self.kind.setCurrentIndex(max(self.kind.findData(st.get("kind", "external")), 0))
        self.kind.blockSignals(False)
        self._kind_labels()
        w = st.get("walls")
        self.walls = w if w and w.get("part") in scene.model.parts else None
        self._names = list(scene.names)
        self._fill_walls()
        self.details.setVisible(self.enable.isChecked())
        self.hint.setVisible(not self.enable.isChecked())
        self._update(save=False)

    @property
    def enabled(self):
        return self.enable.isChecked()

    def settings(self):
        return {"on": self.enabled, "yplus": self.yplus.value(), "mach": self.mach.value(),
                "fluid": self.fluid.currentData(), "rho": self.rho.value(),
                "mu": self.mu.value(), "a": self.a.value(),
                "length": self.length.value(), "altitude": self.altitude.value(),
                "temperature": None if self._temp_auto else self.temp.value(),
                "kind": self.kind.currentData(),
                "y_min": self.y_min.value(), "layers": self.layers.value(),
                "growth": self.growth.value(), "y_des_factor": self.y_des.value(),
                "compressible": self.compressible.isChecked(),
                "direction": [b.value() or 0.0 for b in self.direction],
                "vectors": self.vectors.isChecked(), "walls": self.walls,
                "units": {k: b.unit() for k, b in self._unit_fields().items()}}

    def refresh_names(self):
        """Parts renamed / re-meshed: the walls follow (same place in the list)."""
        sc = self.scene
        if sc is None:
            return
        if self.walls and self.walls["part"] not in sc.model.parts:
            old = self.walls["part"]
            if old in self._names and len(self._names) == len(sc.names):
                self.walls = {**self.walls, "part": sc.names[self._names.index(old)]}
            else:
                self.walls = None
        self._names = list(sc.names)
        self._fill_walls()
        self._update()

    def refresh_colors(self):
        if self.scene is None:
            return
        for i in range(self.wall_menu.count()):
            n = self.wall_menu._items[i][1]
            if n in self.scene.colors:
                self.wall_menu.setItemIcon(i, color_dot(self.scene.colors[n]))
        if self.walls and self.walls.get("faces"):
            i = self.wall_menu.findData(FACES)
            self.wall_menu.setItemIcon(i, color_dot(self.scene.colors[self.walls["part"]]))

    def model_changed(self):
        """The model moved or its unit changed: auto length, walls and arrows follow."""
        self._update(save=False)

    # ---- walls (v2.12) -------------------------------------------------------------------
    def _fill_walls(self):
        sc = self.scene
        m = self.wall_menu
        m.blockSignals(True)
        m.clear()
        m.addItem("Whole model", MODEL)
        for n in sc.names:
            m.addItem(n, n, color_dot(sc.colors[n]))
        w = self.walls
        if w and w.get("faces"):
            k = len(w["faces"])
            m.addItem(f"{w['part']} — {k} face{'s' if k > 1 else ''}", FACES,
                      color_dot(sc.colors[w["part"]]))
            m.setCurrentIndex(m.findData(FACES))
        elif w:
            m.setCurrentIndex(m.findData(w["part"]))
        else:
            m.setCurrentIndex(0)
        m.blockSignals(False)

    def _wall_chosen(self, *_):
        key = self.wall_menu.currentData()
        if key == FACES:
            return
        self.walls = None if key == MODEL else {"part": key, "faces": None}
        self._fill_walls()                               # the picked faces item goes
        self._update()

    def _wall_mesh(self):
        """The walls as a surface (model units), or None for the whole model."""
        sc, w = self.scene, self.walls
        if not w or w["part"] not in sc.model.parts:
            return None
        poly = sc.model.parts[w["part"]]
        if w.get("faces") and "face_id" in poly.cell_data:
            drop = ~np.isin(poly.cell_data["face_id"], w["faces"])
            return poly.remove_cells(np.flatnonzero(drop), inplace=False)
        return poly

    def _along(self, r, length_along):
        """v2.14: y+ of the first layer along the flow, from the leading edge (external) or
        the inlet (internal: flat plate in the entrance, then developed pipe flow) to the
        end of the walls — the curve of the page's third tab, and its max / min / mean.
        v2.14.2: from the curve only (the per-point colours on the walls are gone)."""
        if not r.get("U") or not r.get("y_min") or not length_along or length_along <= 0:
            return None
        xs = np.linspace(0.0, length_along, 241)[1:]
        kw = dict(rho=r["rho"], mu=r["mu"], u=r["U"], mach=self.mach.value() or 0.0,
                  compressible=self.compressible.isChecked(),
                  cf_developed=r["Cf"] if r.get("internal") else None)
        yp = cfd.yplus_along(xs, r["y_min"], **kw)
        i = int(np.argmax(yp))
        return {"target": r["target"], "max": float(yp[i]), "x_max": float(xs[i]),
                "min": float(yp.min()), "mean": float(np.trapezoid(yp, xs) / (xs[-1] - xs[0]))
                if len(xs) > 1 else float(yp[0]), "curve": (xs, yp),
                "above": float(np.mean(yp > 1.25 * r["target"])),
                "internal": bool(r.get("internal")), "length": float(length_along)}

    def _wall_points(self):
        mesh = self._wall_mesh()
        if mesh is not None:
            return np.asarray(mesh.points)
        sc = self.scene
        pts = [np.asarray(sc.model.parts[n].points) for n in sc.names if sc.visible.get(n)]
        return np.vstack(pts) if pts else np.zeros((0, 3))

    def _wall_area(self):
        """Area of the walls (model units²): exact for CAD faces, else the triangles."""
        sc, w = self.scene, self.walls
        names = [w["part"]] if w else [n for n in sc.names if sc.visible.get(n)]
        src = sc.model.source
        if src is not None and hasattr(src, "exact_area"):
            orig = {v: k for k, v in sc._alias.items()}
            try:
                a = sum(src.exact_area(orig.get(n, n), w.get("faces") if w else None)
                        for n in names)
                if a > 0:
                    return a
            except Exception:                             # noqa: BLE001
                pass
        mesh = self._wall_mesh()
        return mesh.area if mesh is not None else sum(sc.model.parts[n].area for n in names)

    def _start_pick(self):
        sc = self.scene
        if sc is None:
            return
        self._picking = True
        self._pick_part = None
        sc.face_pick = self._picked
        sc.set_selection([], render=False)
        sc.selected_faces = {}
        if self.walls and self.walls.get("faces"):
            sc.selected_faces = {self.walls["part"]: set(self.walls["faces"])}
        sc._refresh_face_overlay()
        self.wants_model.emit()
        self._show_pick_buttons()
        self._sync_overlays()

    def _picked(self, name, face_id, additive):
        """A click in the 3D view while picking (faces of one part)."""
        sc = self.scene
        if name is None:
            if not additive:
                sc.selected_faces = {}
                self._pick_part = None
                sc.set_selection([], render=False)
        elif face_id is None:                            # no CAD faces: the whole part
            sc.selected_faces = {}
            self._pick_part = name
            sc.set_selection([name], render=False)
        else:
            self._pick_part = None
            sc.set_selection([], render=False)
            if not additive or set(sc.selected_faces) - {name}:
                sc.selected_faces = {}                   # one part only
            ids = sc.selected_faces.setdefault(name, set())
            ids.symmetric_difference_update({face_id})
            if not ids:
                sc.selected_faces.pop(name)
        sc._refresh_face_overlay()
        sc.p.render()
        self._show_pick_buttons()

    def _apply_pick(self):
        sc = self.scene
        if sc.selected_faces:
            part, ids = next(iter(sc.selected_faces.items()))
            self.walls = {"part": part, "faces": sorted(int(i) for i in ids)}
        elif self._pick_part:
            self.walls = {"part": self._pick_part, "faces": None}
        self._end_pick()
        self._fill_walls()
        self._update()

    def _cancel_pick(self):
        if self._picking:
            self._end_pick()
            self._sync_overlays()

    def _end_pick(self):
        sc = self.scene
        self._picking = False
        self._pick_part = None
        if sc is not None:
            sc.face_pick = None
            sc.clear_face_selection(render=False)
            sc.set_selection([], render=False)
        self._show_pick_buttons()

    def _show_pick_buttons(self):
        p = self._picking
        self.pick_btn.setVisible(not p)
        self.apply_btn.setVisible(p)
        self.cancel_btn.setVisible(p)
        sc = self.scene
        self.pick_info.setVisible(p)
        if hasattr(self, "layer_section"):
            self._relayout()
        if not p or sc is None:
            self.pick_info.setText("")
            return
        if sc.selected_faces:
            part, ids = next(iter(sc.selected_faces.items()))
            self.pick_info.setText(f"{len(ids)} face{'s' if len(ids) > 1 else ''} on {part}")
        elif self._pick_part:
            self.pick_info.setText(f"{self._pick_part} (no CAD faces: the whole part)")
        else:
            self.pick_info.setText("Click faces of one part (⇧ adds)")
        self.apply_btn.setEnabled(bool(sc.selected_faces or self._pick_part))

    def _relayout(self):
        """Rows shown / hidden: shrink back (no gap left where the picking row was)."""
        for w in (self.layer_section.content, self.flow_section.content):
            while w is not None:
                if w.layout() is not None:
                    w.layout().invalidate()
                    w.layout().activate()
                w.updateGeometry()
                w = w.parentWidget()

    # ---- flow direction / arrows -------------------------------------------------------
    def _dir(self):
        return np.array([b.value() or 0.0 for b in self.direction], dtype=float)

    def _direction_changed(self, *_):
        self._update()

    def _vectors_toggled(self, *_):
        self._save()
        self._sync_overlays()

    def _sync_overlays(self):
        sc = self.scene
        if sc is None:
            return
        on = self.enabled
        mesh = self._wall_mesh() if on and not self._picking else None
        sc.walls.show(mesh)
        if on and self.vectors.isChecked() and np.linalg.norm(self._dir()):
            b = mesh.bounds if mesh is not None else sc.model_bounds()
            sc.flow.show(self._dir(), b)
        else:
            sc.flow.hide()

    # ---- handlers -----------------------------------------------------------------------
    def _enabled(self, on):
        self.details.setVisible(on)
        self.hint.setVisible(not on)
        if not on:
            self._cancel_pick()
        self._save()
        self._sync_overlays()
        self.mode_toggled.emit(on)

    # ---- fluid (v2.12.1: the CFD section's) ---------------------------------------------
    def _fluid_changed(self, *_):
        self._fill_properties()
        self._update()

    def _fill_properties(self, custom=None):
        kind = self.fluid.currentData()
        for w in (self.altitude, self.level_head, self.level_unit, self.temp, self.temp_label,
                  self.temp_unit):
            w.setVisible(kind != "custom")
        for box in (self.rho, self.mu, self.a):          # only typed for "Custom"
            box.setEnabled(kind == "custom")
        self.level_label.setText("Altitude" if kind == "air" else "Depth")
        self.level_help.setVisible(kind == "air")
        self.altitude.setToolTip("Geometric altitude above sea level (U.S. Standard Atmosphere"
                                 " 1976)" if kind == "air" else "Depth below the surface "
                                                               "(water at 15 °C)")
        if kind == "custom":
            self._props = None
            if custom:
                self.rho.setValue(custom.get("rho"))
                self.mu.setValue(custom.get("mu"))
                self.a.setValue(custom.get("a"))
            return
        h = self.altitude.value() or 0.0
        t = self._temperature(kind)                      # v2.14: None = standard
        self._props = cfd.air(h, t) if kind == "air" else cfd.water(h, kind, t)
        if kind == "air":
            self.temp.setValue(self._props["T"])
        self.temp.setPlaceholderText(f"auto: {self.temp.shown(self._props['T_std']):.4g}")
        self.rho.setValue(self._props["rho"])
        self.mu.setValue(self._props["mu"])
        self.a.setValue(self._props["a"])

    def _temperature(self, kind):
        """v2.14.1: air at an altitude — its standard temperature, greyed out like ρ, μ
        and a; water — typed (empty = 15 °C). Returns the temperature to use, or None."""
        air = kind == "air"
        if not air and self._temp_auto:              # leaving air: forget its standard T
            self.temp.setValue(None)
        self._temp_auto = air
        self.temp.setEnabled(not air)
        return None if air else self.temp.value()

    def _speed_typed(self, u):
        a = self.a.value()
        if u is not None and a:
            self.mach.setValue(u / a)
        self._update()

    def _auto_length(self):
        self.length.setValue(None)
        self._update()

    def _set_target(self, v):
        """v2.14: "Use y+ = …" in the wall-function card."""
        self.yplus.setValue(v)
        self._update()

    def _kind_changed(self, *_):
        self._kind_labels()
        self._update()

    def _kind_labels(self):
        """v2.14.2: external flow (length L) or internal (hydraulic diameter D)."""
        internal = self.kind.currentData() == "internal"
        self.length_label.setText("Diameter D" if internal else "Length L")
        self.length.setToolTip(
            "Hydraulic diameter D of the pipe or duct (Reynolds number, developed flow).\n"
            "Empty = 2ab / (a + b) from the walls' widths across the flow (a round pipe: "
            "its diameter)" if internal else
            "Reference length for the Reynolds number. Empty = the longest\n"
            "distance across the walls along the flow")
        self.auto_length.setText("Back to auto diameter" if internal else "Back to auto length")
        self.compressible.setEnabled(not internal)       # flat-plate correction: external only

    def _to_metres(self):
        sc = self.scene
        unit = sc.model.units or sc.measure.display_unit
        if unit in UNITS:
            return UNITS[unit], ""
        return 1.0, "No unit in this file: the model is taken to be in metres " \
                    "(pick its unit in the toolbar)."

    def _save(self):
        if self.scene is not None:
            self.scene.inflation_settings = self.settings()

    def _update(self, *_, save=True):
        if save:
            self._save()
        s = self.settings()
        sc = self.scene
        internal = s.get("kind") == "internal"           # v2.14.2
        auto, note, area, along = None, "", None, None
        if sc is not None:
            to_m, note = self._to_metres()
            pts = self._wall_points()
            if len(pts) and np.linalg.norm(self._dir()):
                along = cfd.streamwise_length(pts, self._dir()) * to_m
                auto = cfd.hydraulic_diameter(pts, self._dir()) * to_m if internal else along
            area = self._wall_area() * to_m * to_m
        self.length.setPlaceholderText(f"auto: {auto / self.length.factor:.4g}" if auto
                                       else "auto")
        self.auto_length.setVisible(self.length.value() is not None)
        self.note.setText(note)
        self.note.setVisible(bool(note))
        length = s["length"] or auto or 0.0
        rho, mu, a = self.rho.value(), self.mu.value(), self.a.value()
        try:
            if not (rho and mu and a) or rho <= 0 or mu <= 0:
                raise ValueError("no fluid")
            props = self._props or {}
            fluid = {"rho": rho, "mu": mu, "a": a, "T": props.get("T"), "p": props.get("p"),
                     "air": self.fluid.currentData() == "air"}
            r = cfd.inflation(yplus=s["yplus"] or 1.0, mach=s["mach"] or 0.0,
                              length=length, y_min=s["y_min"], layers=int(s["layers"] or 1),
                              growth=s["growth"] or 1.0, y_des_factor=s["y_des_factor"] or 2.0,
                              compressible=s["compressible"], fluid=fluid, internal=internal)
        except (ValueError, OverflowError, ZeroDivisionError):
            r = {"ok": False}
        r["L"] = length
        r["internal"] = internal
        r["walls"] = self.wall_menu.currentText() if sc is not None else ""
        r["wall_area"] = area
        # y+ along the flow: external from the leading edge to L, internal along the pipe
        r["local"] = self._along(r, (along or length) if internal else length) \
            if r.get("ok") else None
        self.result = r
        if "U" in r and not self.u.hasFocus():
            self.u.setValue(r["U"])
        if r.get("ok"):
            self.y_min.setPlaceholderText(f"auto: {r['y_calc'] / self.y_min.factor:.3g}")
            ok, warn = "<span style='color:#30b350'>✓</span>", \
                "<span style='color:#ff9f0a'>⚠</span>"
            self.summary.setText(
                f"{ok if r['covers_bl'] else warn} layers {show_length(r['y_tot'])} thick · "
                f"{'pipe radius' if internal else 'boundary layer'} {show_length(r['d99'])}<br>"
                f"{ok if r['smooth'] else warn} next cell {show_length(r['y_des'])} · "
                + (f"max y+ {r['local']['max']:.3g} (min {r['local']['min']:.3g})"
                   if r.get("local") else f"y+ ≈ {r['yplus_est']:.3g}"))
        else:
            self.summary.setText("Fill in a speed, a length and the layers.")
        self._values(r)
        self._sync_overlays()
        self.changed.emit(r)

    # ---- NEW (v2.14): Export ▸ CFD settings ---------------------------------------------
    def export_info(self, file_name=""):
        """Everything Export ▸ CFD settings writes (raw numbers, SI units)."""
        from .. import __version__
        r = self.result or {}
        s = self.settings()
        sc = self.scene
        dvec = self._dir()
        inputs = [("Fluid", self.fluid.text(), ""),
                  ("Altitude" if s["fluid"] == "air" else "Depth", s["altitude"] or 0.0, "m"),
                  ("Temperature (typed)", s["temperature"] if s["temperature"] else "standard",
                   "K" if s["temperature"] else ""),
                  ("Mach", s["mach"], ""),
                  ("Flow direction", " ".join(f"{v:g}" for v in dvec), ""),
                  ("Walls", r.get("walls") or self.wall_menu.currentText(), ""),
                  ("Flow", "internal (pipe or duct)" if s["kind"] == "internal" else "external",
                   ""),
                  ("Diameter D" if s["kind"] == "internal" else "Length L",
                   s["length"] if s["length"] else "auto", "m" if s["length"] else ""),
                  ("Target y+", s["yplus"], ""),
                  ("Compressibility correction", "on" if s["compressible"] else "off", ""),
                  ("First layer (typed)", s["y_min"] if s["y_min"] else "auto",
                   "m" if s["y_min"] else ""),
                  ("Layers", int(s["layers"] or 0), ""), ("Growth rate", s["growth"], ""),
                  ("Next cell factor (× max layer height)", s["y_des_factor"], "")]
        flow, layers, yp = [], [], []
        if "rho" in r:
            flow = [("Temperature T", r.get("T"), "K"), ("Pressure p", r.get("p"), "Pa"),
                    ("Density", r["rho"], "kg/m3"), ("Viscosity", r["mu"], "Pa s"),
                    ("Kinematic viscosity", r["mu"] / r["rho"], "m2/s"),
                    ("Sound speed", r["a"], "m/s"), ("Speed U", r["U"], "m/s"),
                    ("Dynamic pressure q", 0.5 * r["rho"] * r["U"] ** 2, "Pa"),
                    ("Length L used", r.get("L"), "m"), ("Reynolds number (L)", r.get("Re"), ""),
                    ("Boundary layer", "turbulent" if r.get("turbulent") else "laminar", "")]
            flow = [x for x in flow if x[1] is not None]
        if r.get("ok"):
            layers = [("Wall area", r.get("wall_area"), "m2"),
                      ("Skin friction Cf", r["Cf"], ""), ("Wall shear stress", r["tau"], "Pa"),
                      ("Friction velocity u*", r["u_star"], "m/s"),
                      ("Viscous length nu/u*", r["mu"] / (r["rho"] * r["u_star"]), "m"),
                      ("First layer height for the target y+", r["y_calc"], "m"),
                      ("First layer height used", r["y_min"], "m"),
                      ("Estimated y+ of the first layer", r["yplus_est"], ""),
                      ("Number of layers", r["N"], ""), ("Growth rate", r["G"], ""),
                      ("Max layer height", r["y_max"], "m"),
                      ("Total thickness of the layers", r["y_tot"], "m"),
                      ("Boundary layer thickness d99", r["d99"], "m"),
                      ("Next cell size", r["y_des"], "m"),
                      ("Layers cover the boundary layer", "yes" if r["covers_bl"] else "no", ""),
                      ("Smooth step to the mesh", "yes" if r["smooth"] else "no", "")]
            layers = [x for x in layers if x[1] is not None]
            loc = r.get("local")
            if loc:
                yp = [("y+ max along the flow", loc["max"], ""),
                      ("y+ mean along the walls", loc["mean"], ""),
                      ("y+ min (end of the walls)", loc["min"], ""),
                      ("Share of the length above 1.25 x target", loc["above"], "")]
        part = self.walls["part"] if self.walls else None
        return {"version": __version__, "file": file_name, "walls": r.get("walls") or "walls",
                "patch": part, "r": r, "inputs": inputs, "flow": flow, "layers": layers,
                "yplus": yp, "model_unit": sc.model.units if sc is not None else None}

    def _values(self, r):
        """v2.12: the two "Values" pop-ups."""
        g = lambda v, d=4: "—" if v is None else f"{v:.{d}g}"          # noqa: E731
        rows = [("Fluid", self.fluid.text(), "")]       # v2.12.1: as the CFD section
        if r.get("T") is not None:
            rows += [("Temperature T", g(r["T"]), "K"), ("Pressure p", f"{r['p']:,.0f}", "Pa")]
        if "rho" in r:
            m = self.mach.value() or 0.0
            rows += [("Density ρ", g(r["rho"]), "kg/m³"), ("Viscosity μ", g(r["mu"]), "Pa·s"),
                     ("Kinematic viscosity ν", g(r["mu"] / r["rho"]), "m²/s")]
            if r.get("k") is not None:
                rows.append(("Conductivity k", g(r["k"]), "W/(m·K)"))
            rows += [("Sound speed a", g(r["a"]), "m/s"), ("Mach M", g(m), ""),
                     ("Speed U", g(r["U"]), "m/s")]
            if self.u.factor != 1.0:
                rows.append(("", g(r["U"] / self.u.factor), self.u.unit()))
            rows.append(("Dynamic pressure q", g(0.5 * r["rho"] * r["U"] ** 2), "Pa"))
            if r.get("T") is not None:
                rows.append(("Total temperature T₀", g(r["T"] * r["rc"]), "K"))
            if r.get("Re"):
                rows += [("Reynolds Re (diameter D)" if r.get("internal") else
                          "Reynolds Re (length L)", f"{r['Re']:.4g}", ""),
                         ("Boundary layer", "turbulent" if r["turbulent"] else "laminar", "")]
        self.flow_values.set_rows(rows)
        rows = [("Walls", r.get("walls") or "—", "")]
        if r.get("wall_area"):
            rows.append(("Wall area", g(r["wall_area"]), "m²"))
        typed = self.length.value() is not None
        what = "Diameter D" if r.get("internal") else "Length L"
        rows.append((f"{what} (typed)" if typed else f"{what} (auto)", g(r.get("L")), "m"))
        if r.get("ok"):
            rows += [("Skin friction Cf", g(r["Cf"]), "")]
            if self.compressible.isChecked() and not r.get("internal"):
                rows += [("Cf incompressible", g(r["Cf_inc"]), ""),
                         ("Compressibility factor", g(r["Cf"] / r["Cf_inc"]), "")]
            if r.get("supersonic"):                         # v2.13.2: was on the page
                rows += [("Recovery factor rc (supersonic δ99)", g(r["rc"]), "")]
            rows += [("Wall shear τw", g(r["tau"]), "Pa"),
                     ("Friction velocity u*", g(r["u_star"]), "m/s"),
                     ("Viscous length ν/u*", nice_length(r["mu"] / (r["rho"] * r["u_star"])), ""),
                     (f"First layer height for y+ = {r['target']:g}", nice_length(r["y_calc"]),
                      ""),
                     ("Layers", None, None),
                     ("First layer height", nice_length(r["y_min"]), ""),
                     ("Estimated y+ of the first layer", g(r["yplus_est"], 3), ""),
                     ("Number of layers · growth rate", f"{r['N']} · {r['G']:g}", ""),
                     ("Max layer height", nice_length(r["y_max"]), ""),
                     ("Total thickness of the layers", nice_length(r["y_tot"]), ""),
                     ("Pipe radius (the boundary layer fills it)" if r.get("internal") else
                      "Boundary layer thickness (δ99)", nice_length(r["d99"]), ""),
                     ("Next cell size", nice_length(r["y_des"]), ""),
                     ("Next cell ÷ max layer height", g(r["y_des"] / r["y_max"], 3), "")]
            loc = r.get("local")
            if loc is not None:                             # v2.14
                edge = "inlet" if loc["internal"] else "leading edge"
                rows += [("y+ along the flow", None, None),
                         (f"y+ max (near the {edge})", g(loc["max"], 3), ""),
                         ("y+ mean along the walls", g(loc["mean"], 3), ""),
                         ("y+ min (end of the walls)", g(loc["min"], 3), ""),
                         ("Length above 1.25 × target", f"{loc['above'] * 100:.0f} %", "")]
        self.layer_values.set_rows(rows)
