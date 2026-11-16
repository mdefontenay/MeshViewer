"""Edit ▸ Undo / Redo (and the toolbar's Undo / Redo): one stack per window.

What can be undone: showing and hiding parts, their colors, their names, hidden CAD
faces, the Edit tool's rotations, mirrors and moves — and the parts selected and the
camera. Camera moves of one kind (turning, panning, zooming, the view buttons), one
after another with no pause over CAMERA_PAUSE s, are one step (`_Done.mergeWith`; the
scene names the gesture: `camera_gesture`). The tools' settings are not.

Each change is a command that holds the state before and after it; the stack runs
redo() when it is pushed, so the change itself happens there — except for a selection
or a camera move, already made when it is recorded (`_Done`). While a command is
applied, the selection and camera changes it causes are not recorded (`_applying`).

    changes = Changes(window)
    changes.visibility(["Wing"], False)        # Edit ▸ Undo Hide Wing
    changes.edit(r, t, "Rotate 90° about Z")
"""
from __future__ import annotations

import copy
import time

import numpy as np
from PySide6.QtGui import QUndoCommand, QUndoStack


class _Command(QUndoCommand):
    def __init__(self, text, apply, before, after):
        super().__init__(text)
        self._apply, self._before, self._after = apply, before, after

    def redo(self):
        self._apply(self._after)

    def undo(self):
        self._apply(self._before)


class _Done(QUndoCommand):
    """A change already made (a click, a camera move): pushing it doesn't redo it.
    `merge`: changes with the same id one after another are one (the camera), while
    `gesture` = (kind, serial, time) allows it: the same gesture (serial), or the same
    kind with no pause over CAMERA_PAUSE s."""

    def __init__(self, text, apply, before, after, merge=-1, same=None, gesture=None):
        super().__init__(text)
        self._apply, self._before, self._after = apply, before, after
        self._merge, self._same, self._fresh = merge, same, True
        self._gesture = gesture

    def id(self):
        return self._merge

    def mergeWith(self, other):
        if self._merge < 0 or other.id() != self._merge:
            return False
        if self._gesture is not None and other._gesture is not None:
            (kind, serial, t), (k2, s2, t2) = self._gesture, other._gesture
            if serial != s2 and (kind != k2 or t2 - t > CAMERA_PAUSE):
                return False                       # another gesture: its own step
            self._gesture = other._gesture
        self._after = other._after
        if self._same is not None and self._same(self._before, self._after):
            self.setObsolete(True)                 # back where it was: no step
        return True

    def redo(self):
        if self._fresh:
            self._fresh = False
            return
        self._apply(self._after)

    def undo(self):
        self._apply(self._before)


CAMERA = 1                                         # the camera's merge id
CAMERA_PAUSE = 0.8                                 # s: a pause longer ends the step


class Changes:
    def __init__(self, window):
        self.w = window
        self.stack = QUndoStack(window)
        self._busy = False                         # applying a command
        self._watched = None                       # the scene whose clicks / camera count

    @property
    def scene(self):
        return self.w.scene

    @property
    def sidebar(self):
        return self.w.sidebar

    def clear(self):
        """A new file, or new parts (another mesh quality): nothing to go back to."""
        self.stack.clear()
        if self.scene is not None:
            self.scene._cam_base = None            # where the camera is now: the start

    def watch(self, scene):
        """Record this scene's selection and camera moves (a file just opened)."""
        old = self._watched
        if old is not None and old is not scene:
            old.on_selection = old.on_camera = None
        self._watched = scene
        scene.on_selection = self._selection_made
        scene.on_camera = self._camera_moved
        scene._cam_base = None

    def _applying(self, apply, state):
        self._busy = True
        try:
            apply(state)
        finally:
            self._busy = False
            if self.scene is not None:
                self.scene._cam_base = None        # a camera it moved is part of it

    def _cmd(self, text, apply, before, after):
        return _Command(text, lambda s: self._applying(apply, s), before, after)

    def _push(self, text, apply, before, after):
        if before != after:                        # nothing changes: nothing to undo
            self.stack.push(self._cmd(text, apply, before, after))

    # ---- the selection and the camera (already done when recorded) -----------------
    def _selection_made(self, before, after):
        if self._busy or self.scene is None:
            return
        self.stack.push(_Done("Selection", lambda s: self._applying(self._set_selection, s),
                              list(before), list(after)))

    def _set_selection(self, names):
        sc = self.scene
        sc.set_selection([n for n in names if n in sc.visible], notify=True)

    def _camera_moved(self, before, after):
        if self._busy or self.scene is None:
            return
        kind, serial = getattr(self.scene, "camera_gesture", ("move", 0))
        self.stack.push(_Done("Camera Change",
                              lambda s: self._applying(self._set_camera, s),
                              before, after, merge=CAMERA, same=self.scene.same_camera,
                              gesture=(kind, serial, time.monotonic())))

    def _set_camera(self, snap):
        self.scene.set_camera_snapshot(snap)
        a = self.w.a_parallel                      # Perspective follows
        a.blockSignals(True)
        a.setChecked(not self.scene.state["parallel"])
        a.blockSignals(False)

    def _label(self, names, verb):
        """ "Hide Wing", "Hide 3 Parts" (the file's own word for its parts)."""
        if len(names) == 1:
            return f"{verb} {names[0]}"
        return f"{verb} {len(names)} {self.scene.model.item_words[1].title()}"

    # ---- showing and hiding -----------------------------------------------------------
    def visibility(self, names, on, text=None):
        sc = self.scene
        names = [n for n in names if n in sc.visible]
        before = {n: sc.visible[n] for n in names}
        after = {n: bool(on) for n in names}
        self._push(text or self._label(names, "Show" if on else "Hide"),
                   self._set_visible, before, after)

    def isolate(self, names):
        sc = self.scene
        keep = set(names)
        before = dict(sc.visible)
        after = {n: n in keep for n in sc.names}
        self._push(self._label(list(names), "Isolate"), self._set_visible, before, after)

    def _set_visible(self, state):
        sc = self.scene
        for on in (True, False):
            names = [n for n, v in state.items() if v == on and n in sc.visible]
            if names:
                sc.set_visible(names, on, render=False)
        self.sidebar.list.sync_checks(sc.visible)
        sc._after_visibility_change()

    # ---- hidden CAD faces ---------------------------------------------------------------
    def faces(self, hidden, text):
        """hidden: the new {part: {face ids}}."""
        before = copy.deepcopy(self.scene.hidden_faces)
        self._push(text, self._set_faces, before, copy.deepcopy(hidden))

    def _set_faces(self, state):
        sc = self.scene
        sc.hidden_faces = copy.deepcopy(state)
        sc._rebuild_surfaces()

    # ---- colors ---------------------------------------------------------------------------
    def color(self, names, hex_color):
        sc = self.scene
        before = {n: sc.colors[n] for n in names if n in sc.colors}
        after = {n: hex_color for n in before}
        self._push(self._label(list(before), "Color"), self._set_colors, before, after)

    def _set_colors(self, state):
        sc, sb = self.scene, self.sidebar
        for c in set(state.values()):
            sc.set_color([n for n, v in state.items() if v == c], c, render=False)
        for n in state:
            sb.list.set_color(n, sc.colors[n])
        sb.cfd_panel.refresh_colors()                  # Boundary menu dots
        sb.inflation_panel.refresh_colors()            # Walls menu dots
        sc.p.render()

    # ---- names ----------------------------------------------------------------------------
    def rename(self, old, new):
        self.stack.push(self._cmd(f"Rename {old}", self._rename, (new, old), (old, new)))

    def _rename(self, pair):
        old, new = pair
        if self.scene.rename_part(old, new):
            self.sidebar.refresh_parts()
            self.sidebar.renamed.emit()

    def rename_group(self, pairs, label):
        """A group of the parts list renamed: every part in it, one step."""
        if pairs:
            back = [(n, o) for o, n in reversed(pairs)]
            self.stack.push(self._cmd(f"Rename {label}", self._rename_many, back, list(pairs)))

    def _rename_many(self, pairs):
        done = [self.scene.rename_part(o, n) for o, n in pairs]
        if any(done):
            self.sidebar.refresh_parts()
            self.sidebar.renamed.emit()

    def assembly_name(self, original, new):
        """An assembly row renamed (the file's tree): shown under its new name."""
        sc = self.scene
        before = sc.group_names.get(original)
        self._push(f"Rename {sc.group_names.get(original, original)}", self._set_assembly,
                   (original, before), (original, new if new != original else None))

    def _set_assembly(self, state):
        original, name = state
        if name is None:
            self.scene.group_names.pop(original, None)
        else:
            self.scene.group_names[original] = name
        self.sidebar.refresh_parts()

    # ---- the Edit tool: rotate, mirror, move --------------------------------------------------
    def _edit_state(self):
        m, sc = self.scene.model, self.scene
        return (np.array(m.transform, dtype=float), np.array(m.offset, dtype=float),
                list(sc._edit_history))

    def edit(self, r, t, label):
        """Rotate / mirror (R) then move (t), after the changes so far."""
        from meshviewer.core import transform as xf
        sc = self.scene
        if not sc.model.editable:
            return False
        r0, t0, hist = self._edit_state()
        r1, t1 = xf.compose((r, t), (r0, t0))
        self.stack.push(self._cmd(label, self._set_edit, (r0, t0, hist),
                                 (r1, t1, hist + [((r0, t0), label)])))
        return True

    def undo_last_edit(self):
        """The Edit tool's Undo button: back one rotation / move (itself undoable)."""
        r0, t0, hist = self._edit_state()
        if hist:
            (r1, t1), label = hist[-1]
            self.stack.push(self._cmd(f"Remove {label}", self._set_edit, (r0, t0, hist),
                                     (np.array(r1, float), np.array(t1, float), hist[:-1])))

    def reset_edits(self):
        """The Edit tool's Reset button: back to the file as opened."""
        from meshviewer.core import transform as xf
        r0, t0, hist = self._edit_state()
        if self.scene.model.edited:
            self.stack.push(self._cmd("Reset Edits", self._set_edit, (r0, t0, hist),
                                     (xf.identity(), np.zeros(3), [])))

    def _set_edit(self, state):
        r, t, hist = state
        sc = self.scene
        sc._edit_history = list(hist)
        sc._set_edit_state(np.array(r, float), np.array(t, float))
        self.w._edited_changed()
