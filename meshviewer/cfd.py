"""NEW (v2.10): y+ estimate for the sidebar's "CFD" section. No Qt.

Flat-plate boundary-layer estimate, wall temperature = free-stream temperature:

    U   = M · a                       free-stream speed (Mach × speed of sound)
    Re  = ρ U L / μ                   L = reference length along the flow
    Cf  = (2 log10(Re) − 0.65)^−2.3   skin friction (Schlichting)
    τw  = Cf · ½ ρ U²                 wall shear stress
    u*  = √(τw / ρ)                   friction velocity
    y+  = y · u* · ρ / μ              y = first cell height at the wall

Fluid properties, from an altitude (U.S. Standard Atmosphere 1976, 0–86 km)
or a depth (fresh or sea water at 15 °C).
"""
from __future__ import annotations

import numpy as np
import pyvista as pv

from .quality import _EDGES

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


def air(altitude_m):
    """Air at a geometric altitude (m): density, viscosity, speed of sound, T, p."""
    z = float(np.clip(altitude_m, -5_000, 86_000))
    h = R_EARTH * z / (R_EARTH + z)                       # geopotential altitude
    i = max(k for k, layer in enumerate(_LAYERS) if h >= layer[0] or k == 0)
    hb, tb, lapse = _LAYERS[i]
    t = tb + lapse * (h - hb)
    if lapse == 0:
        p = _P_BASE[i] * np.exp(-G0 * (h - hb) / (R_AIR * tb))
    else:
        p = _P_BASE[i] * (tb / t) ** (G0 / (R_AIR * lapse))
    mu = 1.458e-6 * t ** 1.5 / (t + 110.4)                # Sutherland
    return {"rho": p / (R_AIR * t), "mu": mu, "a": float(np.sqrt(GAMMA * R_AIR * t)),
            "T": t, "p": p}


WATER = {  # at 15 °C: density at the surface, bulk modulus, viscosity, speed of sound
    "fresh": dict(rho=999.1, K=2.15e9, mu=1.138e-3, a=1466.0),
    "sea": dict(rho=1025.9, K=2.34e9, mu=1.220e-3, a=1507.0),
}


def water(depth_m, kind="fresh"):
    """Water at a depth (m), 15 °C: density rises a little with pressure."""
    w = WATER[kind]
    p_gauge = w["rho"] * G0 * max(float(depth_m), 0.0)
    return {"rho": w["rho"] * (1 + p_gauge / w["K"]), "mu": w["mu"], "a": w["a"],
            "T": 288.15, "p": 101_325.0 + p_gauge}


# ---- boundary layer ---------------------------------------------------------------------
def compressibility(mach):
    """NEW (v2.11.3): Cf(M) / Cf(incompressible) = (1 + 0.144 M²)^−0.65 — turbulent flat
    plate, adiabatic wall (Raymer, Aircraft Design: A Conceptual Approach)."""
    return (1 + 0.144 * mach * mach) ** -0.65


def flow(rho, mu, a, mach, length, compressible=False):
    """Free-stream numbers for the y+ estimate (SI units).
    compressible (v2.11.3): Cf multiplied by compressibility(M)."""
    u = mach * a
    re = rho * u * length / mu if mu > 0 else 0.0
    if re <= 1:
        return {"U": u, "Re": re, "Cf": None, "Cf_inc": None, "tau": None, "u_star": None}
    cf_inc = (2 * np.log10(re) - 0.65) ** -2.3
    cf = cf_inc * (compressibility(mach) if compressible else 1.0)
    tau = cf * 0.5 * rho * u * u
    return {"U": u, "Re": re, "Cf": cf, "Cf_inc": cf_inc, "tau": tau,
            "u_star": float(np.sqrt(tau / rho))}


def y_plus(y, rho, mu, u_star):
    return np.asarray(y, dtype=float) * u_star * rho / mu


def y_for(target, rho, mu, u_star):
    """First cell height (m) that gives y+ = target."""
    return target * mu / (rho * u_star)


def length_along(points, direction):
    """Extent of `points` along `direction` (any length; not changed)."""
    d = np.asarray(direction, dtype=float)
    n = np.linalg.norm(d)
    if n == 0:
        return 0.0
    s = np.asarray(points, dtype=float) @ (d / n)
    return float(s.max() - s.min()) if len(s) else 0.0


def streamwise_length(points, direction, bins=60):
    """NEW (v2.11.1): the longest distance along `direction` across `points`.

    The points are sorted into thin strips parallel to the flow (a grid on the
    plane across it); the length is the longest strip. A swept wing gives its
    root chord, not the distance from the root's leading edge to the tip's
    trailing edge (that is length_along)."""
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
    n = pv.PolyData(wpts, faces=wall.faces).compute_normals(
        cell_normals=False, point_normals=True, split_vertices=False,
        consistent_normals=False, auto_orient_normals=False)["Normals"]
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


# ---- NEW (v2.11): inflation layer calculator ("CFD mode" for CAD files) --------------------
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
              y_des_factor=2.0):
    """Everything the inflation layer calculator shows (SI units).

    speed: "local" -> U = M · √(γ R T) at the altitude; "sea" -> U = M · 343 m/s.
    y_min: first cell height (None -> the one that gives `yplus`).
    y_des: desired size of the first cell outside the inflation layers.
    compressible (v2.11.3): Cf multiplied by compressibility(M) (Raymer).
    fluid (v2.12.1): {"rho", "mu", "a"[, "T", "p"]} — the free stream from the CFD
        section (air at an altitude, water, custom); U = M · a. None: the original
        calculator's air at `altitude` (speed "local" / "sea").
    y_des_factor (v2.12.1): y_des = factor × the largest layer (when y_des is None).
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
           "turbulent": re > TURBULENT_RE, "supersonic": mach > 1,
           "rc": 1 + (GAMMA - 1) / 2 * mach ** 2}
    if re <= 1 or length <= 0:
        return {**out, "ok": False}
    cf_inc = (2 * np.log10(re) - 0.65) ** -2.3
    cf = cf_inc * (compressibility(mach) if compressible else 1.0)
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
    y_des = y_des if y_des else (y_des_factor or 2.0) * heights[-1]
    return {**out, "ok": True, "target": yplus, "Cf": cf, "Cf_inc": cf_inc, "tau": tau, "u_star": u_star,
            "y_calc": y_calc,
            "y_min": y_min, "N": n, "G": g, "heights": heights, "total": total,
            "y_max": float(heights[-1]), "y_tot": float(total[-1]), "y_des": y_des,
            "yplus_est": y_min * u_star * rho / mu, "d99": float(d99),
            "d99_sub": float(d_sub), "covers_bl": float(total[-1]) > d99,
            "smooth": 1.5 <= y_des / heights[-1] <= 3.0}
