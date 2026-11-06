"""NEW (v2.11): sidebar section "CFD mode" (CAD files) — the inputs of the
inflation layer calculator. Its plots are on the Inflation page (the pill under
the 3D view switches between the model and that page).

    CFD mode                                          (switch)
    Flow
      Target y+        [ 1     ]
      Mach             [ 3     ]
      Sound speed      [ Altitude | 343 m/s ]          a for U = M · a
      Length L         [ 0.3   ] m        (Use model length)
      Altitude         [ 3000  ] m    ?
      T 268.7 K · p 70,121 Pa · ρ 0.909 kg/m³ · μ 1.69e-5 Pa·s
    Inflation layers
      First cell       [ auto  ] m        empty = for the target y+
      Layers N         [ 30    ]
      Growth rate G    [ 1.3   ]
      Desired cell     [ auto  ] m        first cell outside the layers
    ✓ covers the boundary layer · ✓ smooth transition
"""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import (
    QGridLayout, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from .. import cfd
from .cfd_panel import ATMOSPHERE_URL
from .inflation_view import show_length
from .measure import UNITS
from .widgets import Capsule, NumberField, Switch, help_button

DEFAULTS = {"on": False, "yplus": 1.0, "mach": 0.3, "speed": "local", "length": 1.0,
            "altitude": 0.0, "y_min": None, "layers": 30, "growth": 1.2, "y_des": None,
            "compressible": True}                                   # v2.11.3


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

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = None
        self.result = None
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

        def grid():
            g = QGridLayout()
            g.setContentsMargins(0, 0, 0, 0)
            g.setHorizontalSpacing(6)
            g.setVerticalSpacing(5)
            g.setColumnStretch(1, 1)
            g.setColumnMinimumWidth(2, 22)
            g.setColumnMinimumWidth(3, 16)
            return g

        def row(g, r, text, widget, unit=None, extra=None, tip=""):
            lab = QLabel(text)
            lab.setToolTip(tip)
            widget.setToolTip(tip)
            g.addWidget(lab, r, 0)
            g.addWidget(widget, r, 1)
            if unit:
                g.addWidget(_label(unit, "AxisLabel"), r, 2)
            if extra is not None:
                g.addWidget(extra, r, 3)

        # ---- flow ----------------------------------------------------------------------
        d.addWidget(_label("Flow", "Caption"))
        g = grid()
        self.yplus = NumberField(1.0)
        row(g, 0, "Target y+", self.yplus, tip="The y+ you want at the wall")
        self.mach = NumberField(0.3)
        row(g, 1, "Mach", self.mach, tip="Free-stream Mach number (gives the speed U)")
        group = QActionGroup(self)
        group.setExclusive(True)
        self.speed = {}
        for key, text, tip in (
                ("local", "Altitude", "U = M · √(γ R T): sound speed at the altitude"),
                ("sea", "343 m/s", "U = M × 343 m/s (sea-level sound speed)")):
            a = QAction(text, self)
            a.setCheckable(True)
            a.setToolTip(tip)
            a.triggered.connect(self._update)
            group.addAction(a)
            self.speed[key] = a
        self.speed["local"].setChecked(True)
        cap = Capsule(list(self.speed.values()), name="Segmented")
        cap.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        for b in cap.buttons:
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        lab = QLabel("Sound speed")
        lab.setToolTip("Speed of sound a used for U = M · a")
        g.addWidget(lab, 2, 0)
        g.addWidget(cap, 2, 1, 1, 3)                 # wider: the units column too
        self.length = NumberField(1.0)
        row(g, 3, "Length L", self.length, "m",
            tip="Reference length for the Reynolds number (e.g. the body length)")
        self.altitude = NumberField(0.0)
        row(g, 4, "Altitude", self.altitude, "m",
            help_button(ATMOSPHERE_URL, "U.S. Standard Atmosphere (1976)"),
            tip="Geometric altitude: air from the U.S. Standard Atmosphere")
        d.addLayout(g)
        r = QHBoxLayout()
        r.addStretch(1)
        self.use_model = _link("Use the model's length", "L = the model's longest side, in "
                               "metres (with the file's unit)", self._model_length)
        r.addWidget(self.use_model)
        d.addLayout(r)
        self.air = _label("", "InfoLine")
        self.air.setWordWrap(True)
        d.addWidget(self.air)
        r = QHBoxLayout()                              # v2.11.3: same as the y+ estimator
        r.addWidget(QLabel("Compressibility correction"))
        r.addStretch(1)
        self.compressible = Switch(True)
        self.compressible.setToolTip("Lower skin friction at high Mach (Raymer):\n"
                                     "Cf × (1 + 0.144 M²)^−0.65. Off = the plain flat-plate\n"
                                     "Cf, as in the original calculator")
        self.compressible.toggled.connect(self._update)
        r.addWidget(self.compressible)
        d.addLayout(r)

        # ---- layers --------------------------------------------------------------------
        d.addWidget(_label("Inflation layers", "Caption"))
        g = grid()
        self.y_min = NumberField()
        row(g, 0, "First cell", self.y_min, "m",
            tip="Height of the first layer y_min. Empty = the one for the target y+")
        self.layers = NumberField(30)
        row(g, 1, "Layers N", self.layers, tip="Number of inflation layers")
        self.growth = NumberField(1.2)
        row(g, 2, "Growth rate G", self.growth, tip="Each layer is G times the one below")
        self.y_des = NumberField()
        row(g, 3, "Desired cell", self.y_des, "m",
            tip="Size of the first ordinary cell above the layers (y_des).\n"
                "Empty = 2 × the largest layer (a smooth transition)")
        d.addLayout(g)
        self.summary = _label("", "InfoLine")
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(Qt.RichText)
        d.addWidget(self.summary)

        for box in (self.yplus, self.mach, self.length, self.altitude, self.y_min, self.layers,
                    self.growth, self.y_des):
            box.valueChanged.connect(self._update)
        self.details.setVisible(False)

    # ---- binding / settings ------------------------------------------------------------
    def bind(self, scene):
        self.scene = scene
        st = {**DEFAULTS, **(getattr(scene, "inflation_settings", None) or {})}
        for box, key in ((self.yplus, "yplus"), (self.mach, "mach"), (self.length, "length"),
                         (self.altitude, "altitude"), (self.y_min, "y_min"),
                         (self.layers, "layers"), (self.growth, "growth"), (self.y_des, "y_des")):
            box.setValue(st[key])
        self.speed.get(st["speed"], self.speed["local"]).setChecked(True)
        Switch.set_silently(self.enable, bool(st["on"]))
        Switch.set_silently(self.compressible, bool(st["compressible"]))
        self.details.setVisible(self.enable.isChecked())
        self.hint.setVisible(not self.enable.isChecked())
        self._update(save=False)

    @property
    def enabled(self):
        return self.enable.isChecked()

    def settings(self):
        return {"on": self.enabled, "yplus": self.yplus.value(), "mach": self.mach.value(),
                "speed": next(k for k, a in self.speed.items() if a.isChecked()),
                "length": self.length.value(), "altitude": self.altitude.value(),
                "y_min": self.y_min.value(), "layers": self.layers.value(),
                "growth": self.growth.value(), "y_des": self.y_des.value(),
                "compressible": self.compressible.isChecked()}

    # ---- handlers -----------------------------------------------------------------------
    def _enabled(self, on):
        self.details.setVisible(on)
        self.hint.setVisible(not on)
        self._save()
        self.mode_toggled.emit(on)

    def _model_length(self):
        sc = self.scene
        if sc is None:
            return
        b = np.array(sc.model_bounds(), dtype=float).reshape(3, 2)
        unit = sc.model.units or sc.measure.display_unit
        self.length.setValue(float((b[:, 1] - b[:, 0]).max()) * UNITS.get(unit, 1.0))
        self._update()

    def _save(self):
        if self.scene is not None:
            self.scene.inflation_settings = self.settings()

    def _update(self, *_, save=True):
        if save:
            self._save()
        s = self.settings()
        try:
            r = cfd.inflation(yplus=s["yplus"] or 1.0, mach=s["mach"] or 0.0,
                              length=s["length"] or 0.0, altitude=s["altitude"] or 0.0,
                              y_min=s["y_min"], layers=int(s["layers"] or 1),
                              growth=s["growth"] or 1.0, y_des=s["y_des"], speed=s["speed"],
                              compressible=s["compressible"])
        except (ValueError, OverflowError, ZeroDivisionError):
            r = {"ok": False}
        self.result = r
        if "T" in r:
            self.air.setText(f"T {r['T']:.4g} K · p {r['p']:,.0f} Pa · ρ {r['rho']:.4g} kg/m³ · "
                             f"μ {r['mu']:.3g} Pa·s · U {r['U']:.4g} m/s")
        if r.get("ok"):
            self.y_min.setPlaceholderText(f"auto: {r['y_calc']:.3g}")
            self.y_des.setPlaceholderText(f"auto: {2 * r['y_max']:.3g}")
            ok, warn = "<span style='color:#30b350'>✓</span>", \
                "<span style='color:#ff9f0a'>⚠</span>"
            self.summary.setText(
                f"{ok if r['covers_bl'] else warn} total {show_length(r['y_tot'])} vs δ99 "
                f"{show_length(r['d99'])}<br>"
                f"{ok if r['smooth'] else warn} desired cell = {r['y_des'] / r['y_max']:.2g} × "
                f"largest layer · y+ ≈ {r['yplus_est']:.3g}")
        else:
            self.summary.setText("Fill in a speed, a length and the layers.")
        self.changed.emit(r)
