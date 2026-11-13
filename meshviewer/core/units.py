"""Units and number formatting shared by the panels (no Qt)."""
from __future__ import annotations

import numpy as np


def length_unit(m):
    """Unit that reads best for lengths up to m: (factor, label)."""
    a = abs(m or 0)
    if a and a < 1e-4:
        return 1e6, "µm"
    if a < 0.1:
        return 1e3, "mm"
    return 1.0, "m"


def show_length(m, unit=None):
    if m is None or not np.isfinite(m):
        return "—"
    f, u = unit or length_unit(m)
    return f"{m * f:.3g} {u}"


def nice_step(span, target=6):
    raw = span / max(target, 1)
    p = 10 ** np.floor(np.log10(raw)) if raw > 0 else 1
    for m in (1, 2, 2.5, 5, 10):
        if m * p >= raw:
            return m * p
    return 10 * p


SPEED_UNITS = {"m/s": 1.0, "km/h": 1 / 3.6, "kt": 1852 / 3600, "ft/s": 0.3048,
               "mph": 0.44704}                                      # -> m/s


LEVEL_UNITS = {"m": 1.0, "km": 1000.0, "ft": 0.3048}


DENSITY_UNITS = {"kg/m³": 1.0, "g/cm³": 1000.0, "lb/ft³": 16.018463, "slug/ft³": 515.378818}


VISCOSITY_UNITS = {"Pa·s": 1.0, "cP": 1e-3, "lb/ft·s": 1.488164}


LENGTH_UNITS = {"m": 1.0, "cm": 0.01, "mm": 0.001, "in": 0.0254, "ft": 0.3048}


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


CELL_UNITS = {"m": 1.0, "mm": 1e-3, "µm": 1e-6, "in": 0.0254}


def nice_num(v):
    if v is None or not np.isfinite(v):
        return "—"
    a = abs(v)
    return f"{v:.3g}" if a == 0 or 1e-3 <= a < 1e5 else f"{v:.2e}"


UNITS = {"mm": 1e-3, "cm": 1e-2, "m": 1.0, "in": 0.0254, "ft": 0.3048}


def fmt(v, units=""):
    """At least 5 significant digits (0.026907 m, 60.022 mm, 1,935.221 mm²)."""
    if v is None:
        return "—"
    a = abs(v)
    if a == 0:
        s = "0"
    elif a >= 1e7 or a < 1e-4:
        s = f"{v:.5g}"
    else:
        dec = int(min(8, max(3, 4 - np.floor(np.log10(a)))))
        s = f"{v:,.{dec}f}".rstrip("0").rstrip(".")
    return f"{s} {units}".strip()


# ---- units of solution fields (Results, Plots) --------------------------------------------
PRESSURE_UNITS = {"Pa": 1.0, "kPa": 1e3, "MPa": 1e6, "GPa": 1e9, "bar": 1e5,
                  "atm": 101325.0, "psi": 6894.757, "ksi": 6894757.0}   # also stresses
TEMPERATURE_UNITS = {"K": (1.0, 0.0), "°C": (1.0, 273.15), "°F": (5 / 9, 459.67 * 5 / 9)}
STRAIN_UNITS = {"m/m": 1.0, "%": 0.01, "µε": 1e-6}
FORCE_UNITS = {"N": 1.0, "kN": 1e3, "lbf": 4.4482216}
HEAT_FLUX_UNITS = {"W/m²": 1.0, "kW/m²": 1e3, "BTU/(h·ft²)": 3.1545907}
HTC_UNITS = {"W/(m²·K)": 1.0, "BTU/(h·ft²·°F)": 5.6782633}
ENERGY_UNITS = {"J/kg": 1.0, "kJ/kg": 1e3, "BTU/lb": 2326.0}            # per mass
TKE_UNITS = {"m²/s²": 1.0, "ft²/s²": 0.09290304}
DISSIPATION_UNITS = {"m²/s³": 1.0, "ft²/s³": 0.09290304}
RATE_UNITS = {"1/s": 1.0, "1/min": 1 / 60}
KINEMATIC_UNITS = {"m²/s": 1.0, "cSt": 1e-6, "ft²/s": 0.09290304}
# a field's quantity -> its units (the first one: SI). Every unit name is in one table
# only (unit_quantity relies on it); lengths add µm for displacements.
QUANTITIES = {"pressure": PRESSURE_UNITS, "density": DENSITY_UNITS, "speed": SPEED_UNITS,
              "temperature": TEMPERATURE_UNITS, "viscosity": VISCOSITY_UNITS,
              "kinematic": KINEMATIC_UNITS, "length": {**LENGTH_UNITS, "µm": 1e-6},
              "strain": STRAIN_UNITS, "force": FORCE_UNITS, "heat_flux": HEAT_FLUX_UNITS,
              "htc": HTC_UNITS, "energy": ENERGY_UNITS, "tke": TKE_UNITS,
              "dissipation": DISSIPATION_UNITS, "rate": RATE_UNITS}
QUANTITY_TITLES = {"pressure": "Pressure and Stress", "density": "Density",
                   "speed": "Speed", "temperature": "Temperature", "viscosity": "Viscosity",
                   "kinematic": "Kinematic Viscosity", "length": "Length",
                   "strain": "Strain", "force": "Force", "heat_flux": "Heat Flux",
                   "htc": "Heat Transfer Coefficient", "energy": "Energy per Mass",
                   "tke": "Turbulent Kinetic Energy", "dissipation": "Dissipation",
                   "rate": "Rate"}
NO_UNIT = ""                       # the file's numbers as they are (often non-dimensional)


def unit_quantity(unit):
    """The quantity a unit measures ("kPa" -> "pressure"), or None. (Every unit is in
    one table only, so a field the app doesn't know gets its quantity from its unit.)"""
    return next((q for q, table in QUANTITIES.items() if unit in table), None) \
        if unit else None


def field_quantity(name):
    """What a solution field measures, from its name (core/field_kinds): "pressure",
    "speed"… or None (cp, Mach, y+… have no unit; unknown fields neither)."""
    from meshviewer.core.field_kinds import field_kind
    kind = field_kind(name)
    return kind.quantity if kind is not None else None


def _to_si(v, unit, table):
    f = table[unit]
    return v * f[0] + f[1] if isinstance(f, tuple) else v * f


def _from_si(v, unit, table):
    f = table[unit]
    return (v - f[1]) / f[0] if isinstance(f, tuple) else v / f


def convert_field(v, quantity, file_unit, shown_unit):
    """Field values (numbers or arrays) from the file's unit to the one shown. No
    quantity, or a unit missing: unchanged."""
    table = QUANTITIES.get(quantity)
    if not table or file_unit not in table or shown_unit not in table:
        return v
    return _from_si(_to_si(v, file_unit, table), shown_unit, table)


def field_scale(quantity, file_unit, shown_unit):
    """Only the factor (for gradients and differences: no offset)."""
    table = QUANTITIES.get(quantity)
    if not table or file_unit not in table or shown_unit not in table:
        return 1.0
    f, g = table[file_unit], table[shown_unit]
    return (f[0] if isinstance(f, tuple) else f) / (g[0] if isinstance(g, tuple) else g)
