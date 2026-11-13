"""The fields solvers usually write, so Results and Plots know what a field is.

    kind = field_kind("p")       -> Kind(title="Pressure p", group="Pressure",
                                         quantity="pressure", ...)
    field_kind("mach").quantity  -> None: a known field with no unit (Mach, y+, cp, cf…)
    field_kind("foo")            -> None: unknown, the user picks its unit

CFD (FUN3D, Fluent, STAR-CCM+, OpenFOAM, SU2…) and FEA (Abaqus, Ansys, Nastran…)
names, matched in lower case. A quantity is a key of core/units.QUANTITIES; its
units are the ones offered. Names that mean two things (ux: a velocity in CFD, a
displacement in FEA) are left out: they are asked like any unknown field.
"""
from __future__ import annotations

from dataclasses import dataclass

SPEED = "__speed__"                  # |u, v, w| (core/fields.SPEED)


@dataclass(frozen=True)
class Kind:
    key: str
    title: str                       # in the Field menu, sentence case
    group: str                       # its header in the menu (Title Case)
    quantity: str | None             # None: no unit (Mach, y+, cp…)
    names: tuple = ()                # how files write it (lower case)


def _k(key, title, group, quantity, *names):
    return Kind(key, title, group, quantity, (key, *names))


# In menu order: the groups, and the fields in each, as listed here.
KINDS = (
    # ---- CFD ------------------------------------------------------------------------------
    _k("mach", "Mach number", "Flow", None, "m", "mach_number", "ma"),
    _k(SPEED, "Speed |u, v, w|", "Flow", "speed", "speed", "vmag", "umag", "velocity",
       "velocity_magnitude", "vel", "velmag"),
    _k("u", "Velocity u", "Flow", "speed", "vx", "velocity_x", "x_velocity", "x-velocity"),
    _k("v", "Velocity v", "Flow", "speed", "vy", "velocity_y", "y_velocity", "y-velocity"),
    _k("w", "Velocity w", "Flow", "speed", "vz", "velocity_z", "z_velocity", "z-velocity"),
    _k("cp", "Pressure coefficient cp", "Pressure", None, "c_p", "pressure_coefficient"),
    _k("p", "Pressure p", "Pressure", "pressure", "pressure", "press", "pstat",
       "static_pressure"),
    _k("p0", "Total pressure", "Pressure", "pressure", "ptot", "pt", "total_pressure"),
    _k("cp0", "Total pressure coefficient", "Pressure", None, "cpt", "cptot"),
    _k("rho", "Density ρ", "Density and Temperature", "density", "density", "dens"),
    _k("t", "Temperature", "Density and Temperature", "temperature", "temperature",
       "temp", "static_temperature"),
    _k("t0", "Total temperature", "Density and Temperature", "temperature", "ttot", "tt",
       "total_temperature"),
    _k("h", "Enthalpy", "Density and Temperature", "energy", "enthalpy"),
    _k("yplus", "y+", "Wall", None, "y+", "y_plus", "wall_yplus"),
    _k("cf", "Skin friction cf", "Wall", None, "c_f", "skin_friction",
       "skin_friction_coefficient"),
    _k("cfx", "Skin friction cf x", "Wall", None),
    _k("cfy", "Skin friction cf y", "Wall", None),
    _k("cfz", "Skin friction cf z", "Wall", None),
    _k("tau", "Wall shear stress", "Wall", "pressure", "tau_w", "tauw", "wall_shear",
       "wall_shear_stress"),
    _k("taux", "Wall shear stress x", "Wall", "pressure", "tau_x"),
    _k("tauy", "Wall shear stress y", "Wall", "pressure", "tau_y"),
    _k("tauz", "Wall shear stress z", "Wall", "pressure", "tau_z"),
    _k("q", "Heat flux", "Heat", "heat_flux", "qw", "heat_flux", "wall_heat_flux"),
    _k("htc", "Heat transfer coefficient", "Heat", "htc", "heat_transfer_coefficient"),
    _k("k", "Turbulent kinetic energy k", "Turbulence", "tke", "tke", "turb_k"),
    _k("epsilon", "Dissipation ε", "Turbulence", "dissipation", "eps", "turb_eps"),
    _k("omega", "Specific dissipation ω", "Turbulence", "rate", "turb_omega", "sdr"),
    _k("vort", "Vorticity", "Turbulence", "rate", "vorticity", "vortmag",
       "vorticity_magnitude"),
    _k("mu", "Viscosity μ", "Turbulence", "viscosity", "viscosity", "visc", "mu_lam",
       "laminar_viscosity"),
    _k("mut", "Eddy viscosity μt", "Turbulence", "viscosity", "mu_t", "eddy_viscosity",
       "mu_turb", "turbulent_viscosity"),
    _k("nut", "Kinematic eddy viscosity νt", "Turbulence", "kinematic", "nu_t", "nutilde",
       "nu_tilde"),
    # ---- FEA ------------------------------------------------------------------------------
    _k("disp", "Displacement |d|", "Displacement", "length", "displacement", "dmag",
       "usum", "displacement_magnitude"),
    _k("dx", "Displacement x", "Displacement", "length", "u1", "disp_x", "displacement_x"),
    _k("dy", "Displacement y", "Displacement", "length", "u2", "disp_y", "displacement_y"),
    _k("dz", "Displacement z", "Displacement", "length", "u3", "disp_z", "displacement_z"),
    _k("mises", "Von Mises stress", "Stress", "pressure", "von_mises", "vonmises",
       "s_mises", "seqv", "svm", "von_mises_stress"),
    _k("tresca", "Tresca stress", "Stress", "pressure", "sint", "s_tresca"),
    _k("s1", "Principal stress σ1", "Stress", "pressure", "smax", "s_max_principal"),
    _k("s2", "Principal stress σ2", "Stress", "pressure", "smid", "s_mid_principal"),
    _k("s3", "Principal stress σ3", "Stress", "pressure", "smin", "s_min_principal"),
    _k("sxx", "Stress σxx", "Stress", "pressure", "s11", "sigma_xx", "stress_xx"),
    _k("syy", "Stress σyy", "Stress", "pressure", "s22", "sigma_yy", "stress_yy"),
    _k("szz", "Stress σzz", "Stress", "pressure", "s33", "sigma_zz", "stress_zz"),
    _k("sxy", "Shear stress τxy", "Stress", "pressure", "s12", "sigma_xy", "stress_xy"),
    _k("syz", "Shear stress τyz", "Stress", "pressure", "s23", "sigma_yz", "stress_yz"),
    _k("sxz", "Shear stress τxz", "Stress", "pressure", "s13", "sigma_xz", "stress_xz"),
    _k("fos", "Safety factor", "Stress", None, "safety_factor", "factor_of_safety"),
    _k("strain", "Equivalent strain", "Strain", "strain", "eqv_strain", "epeq",
       "e_mises", "equivalent_strain"),
    _k("peeq", "Plastic strain", "Strain", "strain", "plastic_strain", "eppleqv"),
    _k("exx", "Strain εxx", "Strain", "strain", "e11", "eps_xx", "strain_xx"),
    _k("eyy", "Strain εyy", "Strain", "strain", "e22", "eps_yy", "strain_yy"),
    _k("ezz", "Strain εzz", "Strain", "strain", "e33", "eps_zz", "strain_zz"),
    _k("rf", "Reaction force", "Force", "force", "reaction_force", "rfmag"),
)

_BY_NAME = {n: k for k in KINDS for n in k.names}
GROUP_ORDER = tuple(dict.fromkeys(k.group for k in KINDS))


def field_kind(name):
    """The Kind of a field from its name (as the file writes it), or None."""
    return _BY_NAME.get((name or "").lower().strip())
