"""CFD tool ▸ "Inflation Layers" (CAD files) — the inputs of the inflation layer
calculator; its plots are on the Inflation page (the pill under the 3D view switches
between the model and that page). Laid out like the CFD tool of meshes (panels/cfd.py):
two groups, each with Formulas and Values; unit menus; the speed U can be typed; the
walls that get the layers (a part, or faces of one part picked in the 3D view) give the
auto length L. Flow — external (length L) or internal, a pipe or duct (diameter D).

    Inflation Layers                                  (switch)
    Fluid & Freestream                      Formulas   Values
      Fluid            [ Air — altitude          ▾ ]
      Altitude ?       [ 3000  ] [ m      ▾ ]
      ▸ Properties  (268.7 K · 0.909 kg/m³ · 1.69e-5 Pa·s)   folded: T, ρ, μ, a
      Mach / Speed     [ 3 ] │ [ 986 ] [ m/s ▾ ]
      Direction        [ 1 ] [ 0 ] [ 0 ]   Vectors (switch)
    ───────────────────────────────────────────
    Boundary Layer & Sizing                 Formulas   Values
      Walls            [ ● wing — 3 faces ▾ ]   Pick…
      Regime           [ External — around the walls ▾ ]
      Length L         [ auto: 0.3 ] [ m ▾ ]      longest distance along the flow
      Target y+ ?      [ 1 ]   Compressible (switch)
      First layer      [ auto  ] [ µm ▾ ]
      Layers / Rate    [ 30 ] layers │ [ 1.2 ] growth
      Next cell        [ 2     ] × max layer height
    ───────────────────────────────────────────
    ✓ Stack · δ99 / ✓ Next cell · y+

The Flow group is shared with the CFD tool of meshes (panels/fluid.py): density,
viscosity and sound speed locked unless Custom; the temperature empty = standard. The
growth rate is kept between 1 and 2; the next cell is a factor of the largest layer.
export_info() for Export ▸ CFD Settings.
"""
from __future__ import annotations

import numpy as np
import pyvista as pv
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSizePolicy, QWidget

from meshviewer.core import cfd
from meshviewer.render.overlays import auto_side
from meshviewer.gui.panels.cfd import ATMOSPHERE_URL, FLOW_FORMULAS as MESH_FLOW_FORMULAS, FLUIDS
from meshviewer.core.units import (DENSITY_UNITS, LENGTH_UNITS, LEVEL_UNITS, SPEED_UNITS,
                                   VISCOSITY_UNITS, nice_length)
from meshviewer.gui.panels.fluid import FluidInputs
from meshviewer.gui.forms import (
    _grid, _label, _row, column, group_head, link, note, pair, rule, status_mark,
)
from meshviewer.core.units import show_length
from meshviewer.core.units import UNITS
from meshviewer.gui.dialogs.wall_help import YPLUS_URL, label_with_help, wall_help_button
from meshviewer.gui.widgets import (
    CollapsibleSection, FormulasButton, MenuSelect, NumberField, Switch,
    TemperatureField, UnitField, ValuesButton, color_dot, help_button,
)
from meshviewer.core.units import CELL_UNITS

DEFAULTS = {"on": False, "yplus": 1.0, "mach": 0.3, "length": None,
            "altitude": 0.0, "temperature": None, "y_min": None, "layers": 30, "growth": 1.2,
            "fluid": "air", "rho": None, "mu": None, "a": None,       # as the
            "y_des_factor": 2.0,                                     # CFD section
            "compressible": True,
            "direction": [1.0, 0.0, 0.0], "vectors": False,
            "thickness": False, "flip": False,    # the layers in 3D (the Inflation page)
            "kind": "external",                                     # or internal
            "walls": None, "units": {}}       # walls: {"part": name, "faces": [ids] | None}
MODEL = "__model__"                     # Walls menu: the whole model
FACES = "__faces__"                     # Walls menu: the faces picked

# the Flow formulas are the CFD section's (same fluid models)
FLOW_FORMULAS = [it if isinstance(it, str) else
                 (it[0].replace("in y+ Estimator", "in Boundary Layer & Sizing"), it[1])
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
    ("First cell for the target y+, and the y+ of the first cell used (click it: CFD Online)",
     r"y_{\mathrm{calc}} = \frac{y^+\, \mu}{\rho\, u_*} \qquad "
     r"y^+_{\mathrm{est}} = \frac{y_{\min}\, u_*\, \rho}{\mu}", YPLUS_URL),
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
    ("link", "Dimensionless wall distance (y plus) — CFD Online ↗", YPLUS_URL),
]


class InflationPanel(FluidInputs, QWidget):
    mode_toggled = Signal(bool)                # Inflation Layers on / off
    changed = Signal(object)                   # new result dict (cfd.inflation)
    wants_model = Signal()                     # picking faces -> show the 3D view

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = None
        self.result = None
        self.walls = None                      # {"part": name, "faces": [ids] | None}
        self._names = []
        self._picking = False
        self._pick_part = None                 # files without CAD faces: a whole part
        self._props = None                     # air / water at the altitude / depth
        self.show_3d = False                   # the layers' thickness in 3D (Inflation page)
        self.flip_3d = False                   # …on the other side than the one chosen
        self._auto_side = None                 # (walls, thickness) -> +1 / -1, the side
        self.side = 1                          # the side shown: +1 along the normals
        lay = column(self)

        # On / off: shown in the section header by the sidebar.
        self.enable = Switch()
        self.enable.setToolTip("Inflation layer calculator: its plots open under the 3D view")
        self.enable.toggled.connect(self._enabled)
        self.hint = note("Off — switch on for the inflation layer calculator.")
        lay.addWidget(self.hint)

        self.details = QWidget()
        d = column(self.details)
        lay.addWidget(self.details)

        # ---- Fluid & Freestream ---------------------------------------------------
        self.flow_values = ValuesButton("Flow", tip="Every flow value: Re, T, p, ν, q…")
        d.addLayout(group_head("Fluid & Freestream",
                                     FormulasButton("Flow — formulas", FLOW_FORMULAS),
                                     self.flow_values))
        g = _grid()                                      # as the CFD section
        self.fluid = MenuSelect()
        for key, text in FLUIDS:
            self.fluid.addItem(text, key)
        self.fluid.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.fluid.currentIndexChanged.connect(self._fluid_changed)
        _row(g, 0, "Fluid", self.fluid, wide=True)
        self.level = UnitField(LEVEL_UNITS, 0.0)
        self.level.valueChanged.connect(self._fluid_changed)
        _, self.level_unit = _row(g, 1, "", self.level)
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
        d.addLayout(g)
        # the fluid's properties, folded: their values in the title
        props = QWidget()
        pg = _grid()
        props.setLayout(pg)
        self.temp = TemperatureField()                   # empty = the standard one
        self.temp.setToolTip("Free-stream temperature. Air: the standard one at the altitude\n"
                             "(U.S. Standard Atmosphere), locked like ρ, μ and a. Water: type\n"
                             "it (empty = 15 °C)")
        self._temp_auto = False                    # showing air's standard T
        self.temp.valueChanged.connect(self._fluid_changed)
        self.temp.unitChanged.connect(self._fluid_changed)
        self.temp_label, self.temp_unit = _row(pg, 0, "Temperature", self.temp)
        self.rho = UnitField(DENSITY_UNITS)
        self.mu = UnitField(VISCOSITY_UNITS)
        self.a = UnitField(SPEED_UNITS)
        for r_, (text, box, tip) in enumerate((
                ("Density", self.rho, "ρ of the free stream"),
                ("Viscosity", self.mu, "Dynamic viscosity μ of the free stream"),
                ("Sound speed", self.a, "Speed of sound a (speed U = Mach × a)")), start=1):
            box.setToolTip(tip)
            box.valueChanged.connect(self._update)
            _row(pg, r_, text, box)
        self.props_section = CollapsibleSection("Properties", props, "cfdmode_props",
                                                sub=True, start_open=False)
        d.addWidget(self.props_section)
        g = _grid()
        self.mach = NumberField(0.3)
        self.mach.setToolTip("Free-stream Mach number (U = Mach × a)")
        self.u = UnitField(SPEED_UNITS)                  # typed U -> Mach
        self.u.setToolTip("Free-stream speed U (Mach = U / a)")
        self.u.valueChanged.connect(self._speed_typed)
        g.addWidget(QLabel("Mach / Speed"), 0, 0)
        g.addWidget(pair(self.mach, None, self.u, None), 0, 1)
        g.addWidget(self.u.menu, 0, 2, 1, 2)
        dirs = QWidget()
        dl = QHBoxLayout(dirs)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.setSpacing(4)
        self.direction = []
        for k, v in zip("XYZ", (1.0, 0.0, 0.0)):
            b_ = NumberField(v)
            b_.setMinimumWidth(0)
            b_.setAlignment(Qt.AlignCenter)
            b_.setToolTip(f"Flow direction, {k} (any length: only the direction counts)")
            b_.valueChanged.connect(self._direction_changed)
            dl.addWidget(b_, 1)
            self.direction.append(b_)
        dl.addSpacing(8)
        dl.addWidget(QLabel("Vectors"))
        self.vectors = Switch()
        self.vectors.setToolTip("Show Flow Vectors")
        self.vectors.setAccessibleName("Show flow vectors")
        self.vectors.toggled.connect(self._vectors_toggled)
        dl.addWidget(self.vectors)
        lab = QLabel("Direction")
        lab.setToolTip("Flow direction X / Y / Z (any length): gives the auto length L")
        g.addWidget(lab, 1, 0)
        g.addWidget(dirs, 1, 1, 1, 3)
        d.addLayout(g)
        d.addWidget(rule())

        # ---- Boundary Layer & Sizing ------------------------------------------------
        self.layer_values = ValuesButton("Inflation layers",
                                         tip="Every value: Cf, τw, u*, layers, δ99…")
        d.addLayout(group_head("Boundary Layer & Sizing",
                                     FormulasButton("Inflation layers — formulas",
                                                    LAYER_FORMULAS),
                                     self.layer_values))
        g = _grid()
        self.wall_menu = MenuSelect()                    # the walls
        self.wall_menu.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.wall_menu.setToolTip("Surfaces that get the inflation layers: they give the\n"
                                  "auto length L, and are tinted in the 3D view")
        self.wall_menu.currentIndexChanged.connect(self._wall_chosen)
        g.addWidget(QLabel("Walls"), 0, 0)
        g.addWidget(self.wall_menu, 0, 1)
        self.pick_btn = link("Pick…", "Click faces of one part in the 3D view\n"
                              "(⇧-click to add more), then Apply", self._start_pick)
        g.addWidget(self.pick_btn, 0, 2, 1, 2)
        d.addLayout(g)
        self.pick_row = QWidget()                        # picking: what is picked, Apply, Cancel
        r = QHBoxLayout(self.pick_row)
        r.setContentsMargins(0, 0, 0, 0)
        self.pick_info = note()
        r.addWidget(self.pick_info, 1)
        self.apply_btn = QPushButton("Apply")
        self.apply_btn.clicked.connect(self._apply_pick)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self._cancel_pick)
        for b in (self.cancel_btn, self.apply_btn):
            r.addWidget(b)
        d.addWidget(self.pick_row)
        g = _grid()
        self.kind = MenuSelect()                         # external / internal flow
        self.kind.addItem("External — around the walls", "external")
        self.kind.addItem("Internal — pipe or duct", "internal")
        self.kind.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.kind.setToolTip("External: a flat plate from the leading edge, Reynolds number on L.\n"
                             "Internal: developed pipe flow, Reynolds number on the hydraulic\n"
                             "diameter D; the entrance acts like a flat plate from the inlet")
        self.kind.currentIndexChanged.connect(self._kind_changed)
        _row(g, 0, "Regime", self.kind, wide=True)
        self.length = UnitField(LENGTH_UNITS)
        self.length.setToolTip("Reference length for the Reynolds number. Empty = the longest\n"
                               "distance across the walls along the flow")
        self.length_label, _ = _row(g, 1, "Length L", self.length)
        self.auto_length = link("Back to Auto Length", "Forget the typed length: use the "
                                 "longest distance across the walls along the flow",
                                 self._auto_length)
        g.addWidget(self.auto_length, 2, 1, 1, 3, Qt.AlignRight)
        self.yplus = NumberField(1.0)
        self.yplus.setToolTip("The y+ you want at the wall")
        g.addWidget(label_with_help("Target y+", wall_help_button(
            self.yplus.value, self._set_target)), 3, 0)
        self.compressible = Switch(True)                 # same as the y+ Estimator
        self.compressible.setToolTip("Compressibility Correction")
        self.compressible.setAccessibleName("Compressibility correction")
        self.compressible.toggled.connect(self._update)
        yr = QWidget()
        yl = QHBoxLayout(yr)
        yl.setContentsMargins(0, 0, 0, 0)
        yl.setSpacing(6)
        yl.addWidget(self.yplus, 1)
        yl.addSpacing(6)
        comp = QLabel("Compressible")
        comp.setToolTip("Lower skin friction at high Mach (Raymer):\n"
                        "Cf × (1 + 0.144 M²)^−0.65. Off = the plain flat-plate Cf")
        yl.addWidget(comp)
        yl.addWidget(self.compressible)
        g.addWidget(yr, 3, 1, 1, 3)
        self.y_min = UnitField(CELL_UNITS)
        self.y_min.setToolTip("Height of the first layer, at the wall (y_min).\n"
                              "Empty = the height that gives the target y+")
        _row(g, 4, "First layer", self.y_min)            # plain names
        self.layers = NumberField(30)
        self.layers.setToolTip("Number of inflation layers (N)")
        self.growth = NumberField(1.2)
        self.growth.setRange(1.0, 2.0)
        self.growth.setToolTip("Growth rate G: each layer is G times taller than the one\n"
                               "below it (between 1 and 2)")
        g.addWidget(QLabel("Layers / Rate"), 5, 0)
        g.addWidget(pair(self.layers, "layers", self.growth, "growth"), 5, 1, 1, 3)
        self.y_des = NumberField(2.0)                    # a factor of y_max
        self.y_des.setRange(1.0, 10.0)
        tip = ("Next cell: the first ordinary cell of the volume mesh above the layers,\n"
               "as a multiple of the largest layer (1 – 10).\n\n"
               "About 2 × gives a smooth step from the inflation layers into the volume\n"
               "mesh (no sudden jump in cell size, which hurts the solution).\n"
               "Use about the same size for the surface cells on these walls: cells\n"
               "about as wide as they are tall keep a low aspect ratio.")
        lab, _ = _row(g, 6, "Next cell", self.y_des)
        factor = _label("× max layer height", "AxisLabel")
        g.addWidget(factor, 6, 2, 1, 2)
        for w in (lab, self.y_des, factor):
            w.setToolTip(tip)
        d.addLayout(g)
        d.addWidget(rule())
        self.summary = note()                            # ✓ Stack · δ99 / ✓ Next cell · y+
        self.summary.setTextFormat(Qt.RichText)
        d.addWidget(self.summary)
        self.note = note()
        d.addWidget(self.note)

        for box in (self.yplus, self.mach, self.length, self.level, self.y_min, self.layers,
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

    def _unit_fields(self):
        return {"altitude": self.level, "rho": self.rho, "mu": self.mu, "a": self.a,
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
                         (self.level, "altitude"), (self.y_min, "y_min"),
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
        self.show_3d = bool(st.get("thickness", False))
        self.flip_3d = bool(st.get("flip", False))
        self._auto_side = None
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
                "length": self.length.value(), "altitude": self.level.value(),
                "temperature": None if self._temp_auto else self.temp.value(),
                "kind": self.kind.currentData(),
                "y_min": self.y_min.value(), "layers": self.layers.value(),
                "growth": self.growth.value(), "y_des_factor": self.y_des.value(),
                "compressible": self.compressible.isChecked(),
                "direction": [b.value() or 0.0 for b in self.direction],
                "vectors": self.vectors.isChecked(), "walls": self.walls,
                "thickness": self.show_3d, "flip": self.flip_3d,
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

    # ---- walls -------------------------------------------------------------------
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
        self.pick_row.setVisible(p)                      # no gap when not picking
        if hasattr(self, "summary"):
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
        for w in (self.details,):
            while w is not None:
                if w.layout() is not None:
                    w.layout().invalidate()
                    w.layout().activate()
                w.updateGeometry()
                w = w.parentWidget()

    # ---- flow direction / arrows -------------------------------------------------------
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
        thick, over, lines = None, mesh, None
        r = self.result or {}
        if on and not self._picking and self.show_3d and r.get("ok"):
            to_m, _ = self._to_metres()
            names = [self.walls["part"]] if mesh is not None else \
                [n for n in sc.names if sc.visible.get(n)]
            if over is None:                                 # the whole model: what shows
                shown = [sc.model.parts[n] for n in names]
                over = pv.merge(shown) if len(shown) > 1 else (shown[0] if shown else None)
            thick = r["y_tot"] / to_m
            if over is not None:
                key = (id(over) if mesh is None else (self.walls["part"],
                       tuple(self.walls.get("faces") or ())), tuple(names), round(thick, 12))
                if self._auto_side is None or self._auto_side[0] != key:
                    self._auto_side = (key, auto_side(over, thick))   # fewest folds
                self.side = self._auto_side[1] * (-1 if self.flip_3d else 1)
                thick *= self.side
                lines = self._wall_lines(names)
        sc.walls.show(mesh, thick, over, lines)
        if on and self.vectors.isChecked() and np.linalg.norm(self._dir()):
            b = mesh.bounds if mesh is not None else sc.model_bounds()
            sc.flow.show(self._dir(), b)
        else:
            sc.flow.hide()

    def _wall_lines(self, names):
        """The walls' feature edges (a CAD part's face borders; only those of the picked
        faces), to draw on the layers' shell."""
        sc, el = self.scene, self.scene.elements
        out = []
        for n in names:
            hidden = None
            faces = (self.walls or {}).get("faces")
            if faces:
                f = el.features(n)
                if f.face_ids is not None:
                    hidden = set(int(i) for i in f.face_ids) - set(int(i) for i in faces)
            try:
                lines = el.feature_lines(n, hidden)
            except Exception:                                # noqa: BLE001
                continue
            if lines.n_points:
                out.append(lines)
        if not out:
            return None
        return pv.merge(out) if len(out) > 1 else out[0]

    def set_3d(self, show=None, flip=None):
        """The Inflation page's Show in 3D and Flip: the layers' total thickness over the
        walls, on the side with the fewest folds (Flip: the other)."""
        if show is not None:
            self.show_3d = bool(show)
        if flip is not None:
            self.flip_3d = bool(flip)
        self._save()
        self._sync_overlays()
        self.changed.emit(self.result or {"ok": False})     # the page's switches follow

    # ---- handlers -----------------------------------------------------------------------
    def _enabled(self, on):
        self.details.setVisible(on)
        self.hint.setVisible(not on)
        if not on:
            self._cancel_pick()
        self._save()
        self._sync_overlays()
        self.mode_toggled.emit(on)

    # ---- fluid (the CFD section's) ---------------------------------------------
    def _set_target(self, v):
        """The "Use y+ = …" in the wall-function card."""
        self.yplus.setValue(v)
        self._update()

    def _kind_labels(self):
        """external flow (length L) or internal (hydraulic diameter D)."""
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
        return 1.0, "No unit in this file: the model is taken to be in meters " \
                    "(pick its unit in the toolbar)."

    def _save(self):
        if self.scene is not None:
            self.scene.inflation_settings = self.settings()

    def _update(self, *_, save=True):
        if save:
            self._save()
        s = self.settings()
        sc = self.scene
        internal = s.get("kind") == "internal"
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
        self.result = r
        if "U" in r and not self.u.hasFocus():
            self.u.setValue(r["U"])
        if r.get("ok"):
            self.y_min.setPlaceholderText(f"auto: {r['y_calc'] / self.y_min.factor:.3g}")
            ok, warn = status_mark(True), status_mark(False)
            self.summary.setText(
                f"{ok if r['covers_bl'] else warn} Stack: {show_length(r['y_tot'])}  ·  "
                f"{'Pipe radius' if internal else 'δ₉₉'}: {show_length(r['d99'])}<br>"
                f"{ok if r['smooth'] else warn} Next cell: {show_length(r['y_des'])}  ·  "
                f"y+ ≈ {r['yplus_est']:.3g}")
        else:
            self.summary.setText("Fill in a speed, a length and the layers.")
        self._values(r)
        self._props_title()
        self._sync_overlays()
        self.changed.emit(r)

    # --- Export ▸ CFD settings ---------------------------------------------
    def export_info(self, file_name=""):
        """Everything Export ▸ CFD settings writes (raw numbers, SI units)."""
        from meshviewer import __version__
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
        part = self.walls["part"] if self.walls else None
        return {"version": __version__, "file": file_name, "walls": r.get("walls") or "walls",
                "patch": part, "r": r, "inputs": inputs, "flow": flow, "layers": layers,
                "yplus": yp, "model_unit": sc.model.units if sc is not None else None}

    def _values(self, r):
        """the two "Values" pop-ups."""
        g = lambda v, d=4: "—" if v is None else f"{v:.{d}g}"          # noqa: E731
        rows = [("Fluid", self.fluid.text(), "")]       # as the CFD section
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
            if r.get("supersonic"):
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
        self.layer_values.set_rows(rows)
