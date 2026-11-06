"""NEW (v2.9): each file reopens the way you left it.

Saved when its window closes (and when the app quits), restored when it opens:
camera, projection, display toggles, unit, part colours, renamed and hidden
parts, and the section plane. Edits (moves, rotations) are not: they belong to
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
        "renames": dict(alias),
        "colors": {orig.get(n, n): scene.colors[n] for n in scene.names},
        "hidden": [orig.get(n, n) for n in scene.names if not scene.visible[n]],
        "cfd": scene.cfd_settings,                                # v2.10
        "inflation": scene.inflation_settings,                    # v2.11: CFD mode
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
    if state.get("cfd"):
        scene.cfd_settings = state["cfd"]
    if state.get("inflation"):
        scene.inflation_settings = state["inflation"]
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
