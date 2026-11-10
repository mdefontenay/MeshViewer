"""Edit ▸ Undo / Redo: every change to the model, one stack per window.

What can be undone is what changes the model or how its parts look: showing and
hiding parts, their colors, their names, hidden CAD faces, and the Edit tool's
rotations, mirrors and moves. The camera, the selection and the tools' settings are
not (as in other Mac apps, they are the view, not the document).

Each change is a command that holds the state before and after it; the stack runs
redo() when it is pushed, so the change itself happens there.

    changes = Changes(window)
    changes.visibility(["Wing"], False)        # Edit ▸ Undo Hide Wing
    changes.edit(r, t, "Rotate 90° about Z")
"""
from __future__ import annotations

import copy

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


class Changes:
    def __init__(self, window):
        self.w = window
        self.stack = QUndoStack(window)

    @property
    def scene(self):
        return self.w.scene

    @property
    def sidebar(self):
        return self.w.sidebar

    def clear(self):
        """A new file, or new parts (another mesh quality): nothing to go back to."""
        self.stack.clear()

    def _push(self, text, apply, before, after):
        if before != after:                        # nothing changes: nothing to undo
            self.stack.push(_Command(text, apply, before, after))

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
        self.stack.push(_Command(f"Rename {old}", self._rename, (new, old), (old, new)))

    def _rename(self, pair):
        old, new = pair
        if self.scene.rename_part(old, new):
            self.sidebar.refresh_parts()
            self.sidebar.renamed.emit()

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
        self.stack.push(_Command(label, self._set_edit, (r0, t0, hist),
                                 (r1, t1, hist + [((r0, t0), label)])))
        return True

    def undo_last_edit(self):
        """The Edit tool's Undo button: back one rotation / move (itself undoable)."""
        r0, t0, hist = self._edit_state()
        if hist:
            (r1, t1), label = hist[-1]
            self.stack.push(_Command(f"Remove {label}", self._set_edit, (r0, t0, hist),
                                     (np.array(r1, float), np.array(t1, float), hist[:-1])))

    def reset_edits(self):
        """The Edit tool's Reset button: back to the file as opened."""
        from meshviewer.core import transform as xf
        r0, t0, hist = self._edit_state()
        if self.scene.model.edited:
            self.stack.push(_Command("Reset Edits", self._set_edit, (r0, t0, hist),
                                     (xf.identity(), np.zeros(3), [])))

    def _set_edit(self, state):
        r, t, hist = state
        sc = self.scene
        sc._edit_history = list(hist)
        sc._set_edit_state(np.array(r, float), np.array(t, float))
        self.w._edited_changed()
