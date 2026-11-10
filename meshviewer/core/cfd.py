"""y+ estimate for the sidebar's "CFD" section. No Qt.

Flat-plate boundary-layer estimate, wall temperature = free-stream temperature:

    U   = M · a                       free-stream speed (Mach × speed of sound)
    Re  = ρ U L / μ                   L = reference length along the flow
    Cf  = (2 log10(Re) − 0.65)^−2.3   skin friction (Schlichting)
    τw  = Cf · ½ ρ U²                 wall shear stress
    u*  = √(τw / ρ)                   friction velocity
    y+  = y · u* · ρ / μ              y = first cell height at the wall

Fluid properties, from an altitude (U.S. Standard Atmosphere 1976, 0–86 km)
or a depth (fresh or sea water at 15 °C).
A temperature can be typed (air: same pressure as the altitude; water: density,
viscosity and speed of sound follow it); the law of the wall. Internal flow (pipe or
duct): Reynolds number on the hydraulic diameter D, skin friction of fully developed
pipe flow.
"""
from __future__ import annotations

import numpy as np

from meshviewer.core.quality import _EDGES
from meshviewer.core.polys import bare

# ---- fluids ---------------------------------------------------------------------------
R_AIR, GAMMA, G0, R_EARTH = 287.05287, 1.4, 9.80665, 6_356_766.0
# U.S. Standard Atmosphere 1976 layers: geopotential base height (m), base T (K), lapse (K/m)
_LAYERS = [(0, 288.15, -0.0065), (11_000, 216.65, 0.0), (20_000, 216.65, 0.001),
           (32_000, 228.65, 0.0028), (47_000, 270.65, 0.0), (51_000, 270.65, -0.0028),
           (71_000, 214.65, -0.002), (84_852, 186.946, 0.0)]


def _layer_pressures():
    p, out = 101_325.0, []
    for i, (h, t, lapse) in enumerate(_LAYERS):
        out.append(p)
        if i + 1 < len(_LAYERS):
            dh = _LAYERS[i + 1][0] - h
            if lapse == 0:
                p *= np.exp(-G0 * dh / (R_AIR * t))
            else:
                p *= (t / (t + lapse * dh)) ** (G0 / (R_AIR * lapse))
    return out


_P_BASE = _layer_pressures()


def air(altitude_m, temperature=None):
    """Air at a geometric altitude (m): density, viscosity, speed of sound, T, p.
    temperature: instead of the standard one — the pressure stays the
    altitude's, density, viscosity and speed of sound follow the temperature."""
    z = float(np.clip(altitude_m, -5_000, 86_000))
    h = R_EARTH * z / (R_EARTH + z)                       # geopotential altitude
    i = max(k for k, layer in enumerate(_LAYERS) if h >= layer[0] or k == 0)
    hb, tb, lapse = _LAYERS[i]
    t = tb + lapse * (h - hb)
    if lapse == 0:
        p = _P_BASE[i] * np.exp(-G0 * (h - hb) / (R_AIR * tb))
    else:
        p = _P_BASE[i] * (tb / t) ** (G0 / (R_AIR * lapse))
    t_std = t
    if temperature is not None and temperature > 0:
        t = float(temperature)
    mu = 1.458e-6 * t ** 1.5 / (t + 110.4)                # Sutherland
    return {"rho": p / (R_AIR * t), "mu": mu, "a": float(np.sqrt(GAMMA * R_AIR * t)),
            "T": t, "p": p, "T_std": t_std}


WATER = {  # at 15 °C: density at the surface, bulk modulus, viscosity, speed of sound
    "fresh": dict(rho=999.1, K=2.15e9, mu=1.138e-3, a=1466.0),
    "sea": dict(rho=1025.9, K=2.34e9, mu=1.220e-3, a=1507.0),
}
T_WATER = 288.15                                       # 15 °C, the default


def _fresh(tc):
    """fresh water at tc °C (0–100): density (Thiesen), viscosity (Vogel),
    speed of sound (Marczak)."""
    rho = 1000.0 * (1 - (tc + 288.9414) / (508929.2 * (tc + 68.12963)) * (tc - 3.9863) ** 2)
    mu = 2.414e-5 * 10 ** (247.8 / (tc + 273.15 - 140.0))
    a = (1402.385 + 5.038813 * tc - 5.799136e-2 * tc ** 2 + 3.287156e-4 * tc ** 3
         - 1.398845e-6 * tc ** 4 + 2.787860e-9 * tc ** 5)
    return rho, mu, a


def water(depth_m, kind="fresh", temperature=None):
    """Water at a depth (m): density rises a little with pressure. 15 °C unless
    `temperature` is given: then density, viscosity and speed of sound
    follow it (sea water: fresh water's values scaled to the 15 °C ones, speed of
    sound from Mackenzie at 35 ‰)."""
    w = WATER[kind]
    depth = max(float(depth_m), 0.0)
    if temperature is None or temperature <= 0:
        rho0, mu, a, t = w["rho"], w["mu"], w["a"], T_WATER
    else:
        t = float(temperature)
        tc = float(np.clip(t - 273.15, 0.0, 100.0))
        rho0, mu, a = _fresh(tc)
        if kind == "sea":
            f_rho, f_mu, _ = _fresh(15.0)
            rho0 *= WATER["sea"]["rho"] / f_rho
            mu *= WATER["sea"]["mu"] / f_mu
            a = (1448.96 + 4.591 * tc - 5.304e-2 * tc ** 2 + 2.374e-4 * tc ** 3
                 + 1.630e-2 * depth + 1.675e-7 * depth ** 2 - 7.139e-13 * tc * depth ** 3)
    p_gauge = rho0 * G0 * depth
    return {"rho": rho0 * (1 + p_gauge / w["K"]), "mu": mu, "a": a,
            "T": t, "p": 101_325.0 + p_gauge, "T_std": T_WATER}


# ---- boundary layer ---------------------------------------------------------------------
def compressibility(mach):
    """Cf(M) / Cf(incompressible) = (1 + 0.144 M²)^−0.65 — turbulent flat
    plate, adiabatic wall (Raymer, Aircraft Design: A Conceptual Approach)."""
    return (1 + 0.144 * mach * mach) ** -0.65


def flow(rho, mu, a, mach, length, compressible=False, internal=False):
    """Free-stream numbers for the y+ estimate (SI units).
    compressible: Cf multiplied by compressibility(M) (external flow only).
    internal: `length` is the hydraulic diameter D, Cf of developed pipe flow."""
    u = mach * a
    re = rho * u * length / mu if mu > 0 else 0.0
    if re <= 1:
        return {"U": u, "Re": re, "Cf": None, "Cf_inc": None, "tau": None, "u_star": None,
                "internal": internal}
    cf_inc = pipe_cf(re) if internal else (2 * np.log10(re) - 0.65) ** -2.3
    cf = cf_inc * (compressibility(mach) if compressible and not internal else 1.0)
    tau = cf * 0.5 * rho * u * u
    return {"U": u, "Re": re, "Cf": cf, "Cf_inc": cf_inc, "tau": tau,
            "u_star": float(np.sqrt(tau / rho)), "internal": internal}


def y_plus(y, rho, mu, u_star):
    return np.asarray(y, dtype=float) * u_star * rho / mu


def y_for(target, rho, mu, u_star):
    """First cell height (m) that gives y+ = target."""
    return target * mu / (rho * u_star)


def streamwise_length(points, direction, bins=60):
    """the longest distance along `direction` across `points`.

    The points are sorted into thin strips parallel to the flow (a grid on the
    plane across it); the length is the longest strip. A swept wing gives its
    root chord, not the distance from the root's leading edge to the tip's
    trailing edge."""
    p = np.asarray(points, dtype=float)
    d = np.asarray(direction, dtype=float)
    n = np.linalg.norm(d)
    if n == 0 or len(p) < 2:
        return 0.0
    d = d / n
    # two directions across the flow
    e1 = np.cross(d, [1.0, 0, 0] if abs(d[0]) < 0.9 else [0, 1.0, 0])
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(d, e1)
    s = p @ d
    k = max(4, min(bins, int(np.sqrt(len(p)) / 2)))            # strips per side
    cells = []
    for e in (e1, e2):
        c = p @ e
        lo, span = c.min(), np.ptp(c)
        cells.append(np.zeros(len(p), int) if span <= 0 else
                     np.minimum(((c - lo) / span * k).astype(int), k - 1))
    strip = cells[0] * k + cells[1]
    smax = np.full(k * k, -np.inf)
    smin = np.full(k * k, np.inf)
    np.maximum.at(smax, strip, s)
    np.minimum.at(smin, strip, s)
    used = np.isfinite(smax)
    return float((smax[used] - smin[used]).max())


# ---- first cell height from a volume mesh -------------------------------------------------
def first_layer(grid, wall):
    """Height of the first cell layer at each wall node (model units), or None.

    For every wall node: the shortest step, measured along the wall normal, to
    a neighbouring node off the wall (along an edge of a cell touching the wall).
    Prisms / hexes in a boundary layer give exactly the first layer height."""
    if grid is None or not hasattr(grid, "cells_dict"):      # no volume cells
        return None
    wpts = np.asarray(wall.points, dtype=float)
    vpts = np.asarray(grid.points, dtype=float)
    if not len(wpts):
        return None
    # wall nodes -> volume node numbers (same coordinates, matched exactly)
    allp = np.vstack([vpts, wpts]) + 0.0
    _, first, inv = np.unique(allp, axis=0, return_index=True, return_inverse=True)
    inv = np.ravel(inv)
    wid = first[inv[len(vpts):]]
    ok = wid < len(vpts)
    if not ok.any():
        return None
    on_wall = np.zeros(len(vpts), dtype=bool)
    on_wall[wid[ok]] = True
    normals = np.zeros_like(vpts)
    n = bare(wall, wpts).compute_normals(
        cell_normals=False, point_normals=True, split_vertices=False,
        consistent_normals=True, auto_orient_normals=False)["Normals"]   # faces may disagree
    normals[wid[ok]] = n[ok]

    best = np.full(len(vpts), np.inf)
    for ctype, conn in grid.cells_dict.items():
        edges = _EDGES.get(ctype)
        if edges is None:
            continue
        touch = on_wall[conn].any(axis=1)
        c = conn[touch]
        if not len(c):
            continue
        for a, b in edges:
            for p, q in ((c[:, a], c[:, b]), (c[:, b], c[:, a])):
                m = on_wall[p] & ~on_wall[q]
                if not m.any():
                    continue
                p, q = p[m], q[m]
                h = np.abs(np.einsum("ij,ij->i", vpts[q] - vpts[p], normals[p]))
                np.minimum.at(best, p, h)
    out = best[wid[ok]]
    out[~np.isfinite(out)] = np.nan
    return out


# --- inflation layer calculator (Inflation Layers, CAD files) ------------------
# Constants as in the original calculator (air)
RU, M_AIR = 8.31446261815324, 0.0289647            # J/(mol K), kg/mol
R_GAS = RU / M_AIR                                 # 287.055 J/(kg K)
MU0, S_MU, K0, S_K, T0 = 1.716e-5, 111.0, 0.0241, 194.0, 273.15
TURBULENT_RE = 5e5


def sutherland(t, ref=MU0, s=S_MU):
    """Viscosity (or, with K0 / S_K, conductivity) of air at temperature t (K)."""
    return ref * (t / T0) ** 1.5 * (T0 + s) / (t + s)


def inflation(yplus=1.0, mach=0.3, length=1.0, altitude=0.0, y_min=None, layers=30,
              growth=1.2, y_des=None, speed="local", compressible=False, fluid=None,
              y_des_factor=2.0, internal=False):
    """Everything the inflation layer calculator shows (SI units).

    speed: "local" -> U = M · √(γ R T) at the altitude; "sea" -> U = M · 343 m/s.
    y_min: first cell height (None -> the one that gives `yplus`).
    y_des: desired size of the first cell outside the inflation layers.
    compressible: Cf multiplied by compressibility(M) (Raymer).
    fluid: {"rho", "mu", "a"[, "T", "p"]} — the free stream from the CFD
        section (air at an altitude, water, custom); U = M · a. None: the original
        calculator's air at `altitude` (speed "local" / "sea").
    y_des_factor: y_des = factor × the largest layer (when y_des is None).
    internal: pipe or duct — `length` is the hydraulic diameter D; Cf of
        developed pipe flow; the "boundary layer" is the radius (it fills the pipe) and
        the check is that the layers fit in it.
    """
    if fluid is not None:
        rho, mu, a = float(fluid["rho"]), float(fluid["mu"]), float(fluid["a"])
        t, p = fluid.get("T"), fluid.get("p")
        k = sutherland(t, K0, S_K) if t is not None and fluid.get("air") else None
        u = mach * a
    else:
        atm = air(altitude)
        t, p = atm["T"], atm["p"]
        rho = p / (R_GAS * t)
        mu = sutherland(t)
        k = sutherland(t, K0, S_K)
        a = float(np.sqrt(GAMMA * R_GAS * t))
        u = mach * (a if speed == "local" else 343.0)
    re = rho * u * length / mu if mu > 0 else 0.0
    out = {"T": t, "p": p, "rho": rho, "mu": mu, "k": k, "a": a, "U": u, "Re": re,
           "turbulent": re > (RE_PIPE if internal else TURBULENT_RE), "supersonic": mach > 1,
           "rc": 1 + (GAMMA - 1) / 2 * mach ** 2, "internal": internal}
    if re <= 1 or length <= 0:
        return {**out, "ok": False}
    cf_inc = pipe_cf(re) if internal else (2 * np.log10(re) - 0.65) ** -2.3
    cf = cf_inc * (compressibility(mach) if compressible and not internal else 1.0)
    tau = cf * 0.5 * rho * u * u
    u_star = float(np.sqrt(tau / rho))
    y_calc = yplus * mu / (rho * u_star)
    y_min = y_calc if not y_min else y_min
    n = max(int(layers), 1)
    g = float(growth)
    heights = y_min * g ** np.arange(n)                       # cell n = y_min · G^n
    total = np.concatenate([[0.0], np.cumsum(heights)])       # top of layer n
    # Boundary-layer thickness (flat plate); supersonic: divided by rc^(1/9)
    d_sub = 0.38 * length / re ** 0.2 if out["turbulent"] else 4.91 * length / np.sqrt(re)
    d99 = d_sub / out["rc"] ** (1 / 9) if mach > 1 else d_sub
    if internal:                                     # developed: it fills the pipe
        d_sub = d99 = length / 2
    y_des = y_des if y_des else (y_des_factor or 2.0) * heights[-1]
    return {**out, "ok": True, "target": yplus, "Cf": cf, "Cf_inc": cf_inc, "tau": tau, "u_star": u_star,
            "y_calc": y_calc,
            "y_min": y_min, "N": n, "G": g, "heights": heights, "total": total,
            "y_max": float(heights[-1]), "y_tot": float(total[-1]), "y_des": y_des,
            "yplus_est": y_min * u_star * rho / mu, "d99": float(d99),
            "d99_sub": float(d_sub), "covers_bl": (float(total[-1]) < d99) if internal else (float(total[-1]) > d99),
            "smooth": 1.5 <= y_des / heights[-1] <= 3.0}


# --- internal flow (pipe or duct) --------------------------------------------
RE_PIPE = 2300.0                  # pipe flow is turbulent above this


def pipe_cf(re):
    """Fanning skin friction of fully developed flow in a smooth pipe: laminar 16 / Re
    below Re 2300, else Petukhov (f_Darcy = (0.790 ln Re − 1.64)⁻², Cf = f / 4)."""
    re = float(re)
    if re < RE_PIPE:
        return 16.0 / re
    return (0.790 * np.log(re) - 1.64) ** -2 / 4


def hydraulic_diameter(points, direction):
    """D = 2ab / (a + b) from the walls' two widths a, b across the flow: the diameter
    of a round pipe, 4 × area / perimeter of a rectangular duct."""
    p = np.asarray(points, dtype=float)
    d = np.asarray(direction, dtype=float)
    n = np.linalg.norm(d)
    if n == 0 or len(p) < 3:
        return 0.0
    d = d / n
    e1 = np.cross(d, [1.0, 0, 0] if abs(d[0]) < 0.9 else [0, 1.0, 0])
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(d, e1)
    a, b = float(np.ptp(p @ e1)), float(np.ptp(p @ e2))
    return 2 * a * b / (a + b) if a + b > 0 else 0.0


# --- law of the wall (the "?" next to Target y+) ------------------------------
KAPPA, B_LOG = 0.41, 5.2


def spalding(u_plus):
    """Spalding's law of the wall: y+ for a given u+ (one formula from the wall to
    the log layer)."""
    k = KAPPA * np.asarray(u_plus, dtype=float)
    return u_plus + np.exp(-KAPPA * B_LOG) * (np.exp(k) - 1 - k - k ** 2 / 2 - k ** 3 / 6)
