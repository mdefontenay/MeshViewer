"""The fluid and flow inputs the two CFD panels share (CFD tool: meshes, and Inflation
Layers for CAD): fluid properties from an altitude / depth and a temperature, the speed and
Mach number, the flow direction.

The panel provides the widgets — fluid, level (+ level_head, level_unit), temp
(+ temp_label), rho, mu, a, speed, mach, length, direction — and its own _update()
and _kind_labels()."""
from __future__ import annotations

import numpy as np

from meshviewer.core import cfd


class FluidInputs:
    def _dir(self):
        return np.array([b.value() or 0.0 for b in self.direction], dtype=float)

    def _fluid_changed(self, *_):
        self._fill_properties()
        self._update()

    def _fill_properties(self, custom=None):
        kind = self.fluid.currentData()
        for w in (self.level, self.level_head, self.level_unit, self.temp, self.temp_label,
                  self.temp_unit):
            w.setVisible(kind != "custom")
        for box in (self.rho, self.mu, self.a):     # only typed for "Custom"
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
        t = self._temperature(kind)                 # None = standard
        props = cfd.air(h, t) if kind == "air" else cfd.water(h, kind, t)
        if kind == "air":
            self.temp.setValue(props["T"])
        self.temp.setPlaceholderText(f"auto: {self.temp.shown(props['T_std']):.4g}")
        self._props = props
        self.rho.setValue(props["rho"])
        self.mu.setValue(props["mu"])
        self.a.setValue(props["a"])

    def _temperature(self, kind):
        """air at an altitude — its standard temperature, greyed out like ρ, μ
        and a; water — typed (empty = 15 °C). Returns the temperature to use, or None."""
        air = kind == "air"
        if not air and self._temp_auto:              # leaving air: forget its standard T
            self.temp.setValue(None)
        self._temp_auto = air
        self.temp.setEnabled(not air)
        return None if air else self.temp.value()

    def _speed_typed(self, u):
        """a typed speed sets the Mach number (M = U / a)."""
        a = self.a.value()
        if u is not None and a:
            self.mach.setValue(u / a)          # u in m/s (UnitField)
        self._update()

    def _auto_length(self):
        self.length.setValue(None)
        self._update()

    def _kind_changed(self, *_):
        self._kind_labels()
        self._update()
