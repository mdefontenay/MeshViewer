"""Export ▸ CFD settings — the inflation layers of CFD mode, written for a
mesher, or every input and value as a CSV. No Qt.

    export(kind, path, info)

info: InflationPanel.export_info() — {"file", "walls", "patch", "version", "r" (the
cfd.inflation result), "inputs" / "flow" / "layers" / "yplus": [(name, value, unit)]}.

    openfoam   snappyHexMeshDict "addLayersControls" (paste it in, or #include the file)
    fluent     Fluent Meshing ▸ Add Boundary Layers (watertight workflow) — the fields
    starccm    STAR-CCM+ Prism Layer Mesher — the fields
    pointwise  Pointwise T-Rex — the fields
    csv        every input and computed value, then the layer table
"""
from __future__ import annotations

import csv
import re
from pathlib import Path

FORMATS = {   # key: (menu text, file extension)
    "openfoam": ("OpenFOAM — snappyHexMesh layers (addLayersControls)", ".txt"),
    "fluent": ("Ansys Fluent Meshing — boundary layer settings", ".txt"),
    "starccm": ("Simcenter STAR-CCM+ — prism layer settings", ".txt"),
    "pointwise": ("Cadence Fidelity Pointwise — T-Rex settings", ".txt"),
    "csv": ("CSV — every input and value, and the layers", ".csv"),
}
SUFFIX = {"openfoam": "_snappy_layers", "fluent": "_fluent_layers", "starccm": "_starccm_prisms",
          "pointwise": "_pointwise_trex", "csv": "_cfd"}


def _e(v, d=4):
    return f"{v:.{d}g}"


def _head(info, comment):
    r = info["r"]
    lines = [f"Mesh Viewer {info['version']} — inflation layers for {info['walls']} "
             f"({info['file']})",
             f"First layer {_e(r['y_min'])} m · {r['N']} layers · growth rate {r['G']:g} · "
             f"total {_e(r['y_tot'])} m · last layer {_e(r['y_max'])} m",
             f"For target y+ {r['target']:g} (estimated {_e(r['yplus_est'], 3)}): U {_e(r['U'])} m/s, "
             f"{'D' if r.get('internal') else 'L'} {_e(r['L'])} m, Re {_e(r['Re'], 3)}, "
             f"{'pipe radius' if r.get('internal') else 'boundary layer'} {_e(r['d99'])} m"]
    return [comment + " " + x if x else comment for x in lines]


def _patch(info):
    name = info.get("patch") or "wall"
    return re.sub(r"[^A-Za-z0-9_.]+", "_", name).strip("_") or "wall"


def _openfoam(info):
    r = info["r"]
    out = ["/*"] + [" " + x for x in _head(info, "")] + [
        "",
        " In system/snappyHexMeshDict: set \"addLayers true;\", then replace the",
        " addLayersControls block with this one (or #include this file there).",
        " Thicknesses are absolute (relativeSizes false), in metres. If the geometry",
        " is still in millimetres when snappyHexMesh runs, use firstLayerThickness",
        f" {_e(r['y_min'] * 1e3)} and minThickness {_e(r['y_min'] * 1e2)} instead.",
        " Rename the patch below to your wall patch (a regex is fine).",
        "*/",
        "",
        "addLayersControls",
        "{",
        "    relativeSizes           false;",
        f"    firstLayerThickness     {_e(r['y_min'])};",
        f"    expansionRatio          {r['G']:g};",
        f"    minThickness            {_e(r['y_min'] * 0.1)};",
        "    nGrow                   0;",
        "    featureAngle            130;",
        "    slipFeatureAngle        30;",
        "    nRelaxIter              5;",
        "    nSmoothSurfaceNormals   1;",
        "    nSmoothNormals          3;",
        "    nSmoothThickness        10;",
        "    maxFaceThicknessRatio   0.5;",
        "    maxThicknessToMedialRatio 0.3;",
        "    minMedialAxisAngle      90;",
        "    nBufferCellsNoExtrude   0;",
        "    nLayerIter              50;",
        "",
        "    layers",
        "    {",
        f"        \"{_patch(info)}.*\"",
        "        {",
        f"            nSurfaceLayers  {r['N']};",
        "        }",
        "    }",
        "}",
    ]
    text = "\n".join(out) + "\n"
    for u, plain in (("·", ","), ("—", "-"), ("–", "-"), ("µ", "u")):   # plain ASCII for OpenFOAM
        text = text.replace(u, plain)
    return text


def _table(info, title, rows, notes):
    head = _head(info, "#")
    w = max(len(k) for k, _ in rows)
    body = [f"{k.ljust(w)}   {v}" for k, v in rows]
    return "\n".join(head + ["", title, "-" * len(title)] + body + [""] + notes) + "\n"


def _fluent(info):
    r = info["r"]
    rows = [("Offset Method Type", "uniform"), ("Number of Layers", str(r["N"])),
            ("First Height", f"{_e(r['y_min'])} m  ({_e(r['y_min'] * 1e3)} mm)"),
            ("Growth Rate", f"{r['G']:g}"), ("Add in", info["walls"])]
    notes = ["Fluent Meshing, watertight geometry workflow ▸ Add Boundary Layers: pick",
             "'uniform' so the first height is used as it is. Same values in the",
             "Boundary Layers / Scoped Prisms dialog of the fault-tolerant workflow.",
             f"Total thickness {_e(r['y_tot'])} m; last layer {_e(r['y_max'])} m — the next",
             f"(volume) cell should be about {_e(r['y_des'])} m."]
    return _table(info, "Fluent Meshing — Add Boundary Layers", rows, notes)


def _starccm(info):
    r = info["r"]
    rows = [("Number of Prism Layers", str(r["N"])),
            ("Prism Layer Stretching", f"{r['G']:g}"),
            ("Prism Layer Total Thickness", f"{_e(r['y_tot'])} m (absolute)"),
            ("Prism Layer Near Wall Thickness", f"{_e(r['y_min'])} m"),
            ("Boundaries", info["walls"])]
    notes = ["STAR-CCM+ ▸ Automated Mesh ▸ Prism Layer Mesher ▸ Default Controls (or a",
             "Custom Control on the wall boundaries): set the total thickness as an",
             "absolute size. Three of the four numbers fix the fourth: stretching and",
             "near-wall thickness are the ones the y+ needs.",
             f"Surface size near the walls: about {_e(r['y_des'])} m or more (the next cell)."]
    return _table(info, "STAR-CCM+ — Prism Layer Mesher", rows, notes)


def _pointwise(info):
    r = info["r"]
    rows = [("Wall Spacing", f"{_e(r['y_min'])} m"), ("Growth Rate", f"{r['G']:g}"),
            ("Max Layers", str(r["N"])), ("Full Layers", "0"),
            ("Wall boundary", info["walls"])]
    notes = ["Pointwise ▸ Grid ▸ Solve ▸ T-Rex (2D: on the domains, 3D: on the blocks):",
             "add the walls as Wall boundary conditions with this spacing. Pointwise works",
             "in the model's units: convert the spacing if the model is not in metres",
             f"({_e(r['y_min'] * 1e3)} mm).",
             f"Total thickness {_e(r['y_tot'])} m; last layer {_e(r['y_max'])} m."]
    return _table(info, "Pointwise — T-Rex", rows, notes)


def _csv(path, info):
    r = info["r"]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:      # Excel reads the BOM
        w = csv.writer(f)
        w.writerow([f"Mesh Viewer {info['version']}", info["file"], info["walls"]])
        w.writerow(["section", "quantity", "value", "unit"])
        for section in ("inputs", "flow", "layers", "yplus"):
            for name, value, unit in info.get(section) or []:
                w.writerow([section, name, value, unit])
        w.writerow([])
        w.writerow(["layer", "height (m)", "top of the layer (m)"])
        for n, (h, top) in enumerate(zip(r["heights"], r["total"][1:]), start=1):
            w.writerow([n, f"{h:.6g}", f"{top:.6g}"])


def export(kind, path, info):
    path = Path(path)
    r = info.get("r") or {}
    if not r.get("ok"):
        raise ValueError("fill in the CFD mode inputs first (no inflation layers yet)")
    if kind == "csv":
        _csv(path, info)
        return path
    text = {"openfoam": _openfoam, "fluent": _fluent, "starccm": _starccm,
            "pointwise": _pointwise}[kind](info)
    path.write_text(text, encoding="utf-8")
    return path
