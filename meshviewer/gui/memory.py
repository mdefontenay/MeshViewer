"""Each file reopens the way you left it.

Saved when its window closes (and when the app quits), restored when it opens:
camera, projection, display toggles, unit, part colours, renamed and hidden
parts, and the section plane. CFD inputs; Plots (the measurements); the Inflation page —
which page and tab, Flip side, the flow arrow, the cross-section zoom. Edits (moves, rotations) are not: they belong to
an export. Stored in the app's settings, for the last 200 files.

    state = capture(scene)          ->  dict (JSON-friendly)
    restore(scene, state)           before the sidebar is bound
    restore_camera(scene, state)    last, after the view is set up
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PySide6.QtCore import QSettings

KEEP = 200
TOGGLES = ("mesh_edges", "feature_edges", "faces", "bbox", "origin")


def _key(path):
    return "views/" + hashlib.sha1(str(Path(path).resolve()).encode()).hexdigest()[:20]


def load(path):
    try:
        raw = QSettings("local", "Mesh Viewer").value(_key(path))
        return json.loads(raw) if raw else None
    except (TypeError, ValueError):
        return None


def save(path, state):
    st = QSettings("local", "Mesh Viewer")
    key = _key(path)
    st.setValue(key, json.dumps(state))
    try:
        order = [k for k in json.loads(st.value("views/_order") or "[]") if k != key]
    except ValueError:
        order = []
    order.insert(0, key)
    for old in order[KEEP:]:                        # forget the oldest files
        st.remove(old)
    st.setValue("views/_order", json.dumps(order[:KEEP]))


def capture(scene):
    alias = scene._alias
    orig = {new: old for old, new in alias.items()}          # current name -> file name
    sec = scene.section
    cam = scene.p.camera
    return {
        "camera": [list(map(float, v)) for v in scene.p.camera_position],
        "parallel_scale": float(cam.parallel_scale),
        "parallel": scene.state["parallel"],
        "toggles": {k: bool(scene.state.get(k)) for k in TOGGLES},
        "unit": scene.measure.display_unit,
        "file_unit": scene.model.units or None,
        "renames": dict(alias),
        "colors": {orig.get(n, n): scene.colors[n] for n in scene.names},
        "hidden": [orig.get(n, n) for n in scene.names if not scene.visible[n]],
        "cfd": scene.cfd_settings,
        "inflation": scene.inflation_settings,                    # CFD mode
        "inflation_page": getattr(scene, "inflation_page", None),  # tab, zoom…
        "results": getattr(scene, "results_settings", None),      # field, range
        "plots": list(getattr(scene, "plots", None) or []),      # measurements (Plots)
        "sections": getattr(scene, "sidebar_sections", None),     # sidebar sections shown
        "section_restore": bool(getattr(scene, "section_restore", False)),
        "cfd_restore": list(getattr(scene, "cfd_restore", None) or []),
        "hidden_faces": {orig.get(n, n): sorted(v) for n, v in scene.hidden_faces.items()
                         if v},
        "section": {"enabled": sec.enabled, "origin": list(map(float, sec.origin)),
                    "normal": list(map(float, sec.normal_raw)), "fill": sec.fill,
                    "handle": sec.show_handle},
    }


def restore(scene, state):
    """Everything but the camera. Names that are no longer in the file are skipped."""
    if not state:
        return
    for old, new in state.get("renames", {}).items():
        if old in scene.model.parts and new not in scene.model.parts:
            scene.rename_part(old, new)
    current = lambda n: scene._alias.get(n, n)               # noqa: E731
    colors = {current(n): c for n, c in state.get("colors", {}).items()
              if current(n) in scene.colors}
    for name, c in colors.items():
        scene.set_color([name], c, render=False)
    for n in state.get("hidden", []):
        if current(n) in scene.visible:
            scene.set_visible(current(n), False, render=False)
    t = state.get("toggles", {})
    for key, method in (("mesh_edges", "set_mesh_edges"), ("feature_edges", "set_feature_edges"),
                        ("faces", "set_faces"), ("bbox", "set_bbox"), ("origin", "set_origin")):
        if key in t and bool(t[key]) != bool(scene.state.get(key)):
            getattr(scene, method)(bool(t[key]), render=False)
    if "parallel" in state:
        scene.set_parallel(bool(state["parallel"]), render=False)
    if "unit" in state:
        scene.measure.display_unit = state["unit"]
    if state.get("file_unit"):
        scene.model.units = state["file_unit"]
    if state.get("cfd"):
        scene.cfd_settings = state["cfd"]
    if state.get("inflation"):
        scene.inflation_settings = state["inflation"]
    if state.get("inflation_page"):
        scene.inflation_page = state["inflation_page"]
    if state.get("results"):
        scene.results_settings = state["results"]
    if isinstance(state.get("plots"), list):
        scene.plots = [dict(m) for m in state["plots"] if isinstance(m, dict) and "id" in m]
    if isinstance(state.get("sections"), list):
        scene.sidebar_sections = state["sections"]
    scene.section_restore = bool(state.get("section_restore", False))
    scene.cfd_restore = [k for k in state.get("cfd_restore") or [] if isinstance(k, str)]
    hidden = {current(n): set(v) for n, v in (state.get("hidden_faces") or {}).items()
              if current(n) in scene.model.parts}                # hidden surfaces
    if hidden:
        scene.hidden_faces = hidden
        scene._rebuild_surfaces()
    s = state.get("section")
    if s:
        sec = scene.section
        sec.set_plane(origin=s["origin"], normal=s["normal"], caps=False)
        sec.fill = bool(s.get("fill", sec.fill))
        sec.show_handle = bool(s.get("handle", sec.show_handle))
        if s.get("enabled"):
            sec.set_enabled(True)


def restore_camera(scene, state):
    if not state or "camera" not in state:
        return
    try:
        scene.p.camera_position = [tuple(np.asarray(v, dtype=float)) for v in state["camera"]]
        if state.get("parallel_scale"):
            scene.p.camera.parallel_scale = float(state["parallel_scale"])
        scene.p.renderer.ResetCameraClippingRange()
    except (TypeError, ValueError, KeyError):
        pass
    if scene.model.dim == 2:                         # 2D: square to Z whatever was saved
        scene.snap_to_z()
