"""▸ Animation in a contour's card (gui/panels/contour_editor.py), under ▸ Color Bar:

    ─ ▸ Animation ─────────────────────────────── (switch)
        Color scale range  [ Timeline | Current Step ]
        Time step                     t = 0.5 · Step 2 / 3

On: the playback bar shows under the 3D view while this contour's tab is shown, and the
tab shows the animation's step; off, or any other tab: the latest step, as the case
opened (gui/window_animation.py). Color scale range doesn't apply to a gradient (each
step's own) nor with Min and Max both typed: grayed then, with why. Timeline: Min / Max (auto) over every time step, so the colors
mean the same all along; Current Step: the step shown's. Always there; grayed with one
note on a file with a single time step (or none) and for a field that is the same at
every step (UMean, pMean: switched off then); "Off — …" when switched off.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget

from meshviewer.gui.forms import _grid, _row, note, readout, segmented
from meshviewer.gui.widgets import CollapsibleSection, Switch

ANIM_DEFAULTS = {"on": False, "range": "timeline"}
RANGES = (("timeline", "Timeline", "Min / Max over every time step"),
          ("step", "Current Step", "Min / Max of the step shown"))
SINGLE = "Single time step — open a multi-step case to animate."
CONSTANT = "Field is constant across time steps."
OFF = "Off — switch on to animate across time steps."


def anim_settings(saved):
    """A contour's Animation settings from what was saved (odd ones: the default)."""
    out = dict(ANIM_DEFAULTS)
    if isinstance(saved, dict):
        out["on"] = bool(saved.get("on", False))
        out["range"] = saved.get("range") if saved.get("range") in {k for k, *_ in RANGES} \
            else "timeline"
    return out


class AnimationSection:
    """The subsection and its header switch, for one contour's editor."""

    def __init__(self, editor):
        self.editor = editor
        self.on = Switch()
        self.on.setToolTip("Animate")
        self.on.setAccessibleName("Animate")
        self.on.toggled.connect(self._switched)
        w = QWidget()
        col = QVBoxLayout(w)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(6)
        self.note = note(OFF)
        col.addWidget(self.note)
        self.details = QWidget()
        g = _grid()
        self.details.setLayout(g)
        self.range_acts, cap = segmented(editor, RANGES, self._range)
        _row(g, 0, "Color scale range", cap, wide=True, align=Qt.AlignLeft)
        self.range_note = note()                       # why Color scale range doesn't apply
        g.addWidget(self.range_note, 1, 0, 1, 4)
        _k, self.step_label, _n = readout(g, 2, "Time step", "")
        col.addWidget(self.details)
        self.section = CollapsibleSection("Animation", w, f"contour_anim{editor.c['id']}",
                                          trailing=self.on, sub=True, remember=False,
                                          start_open=False)

    @property
    def settings(self):
        return self.editor.c["anim"]

    def sync(self):
        """Available (several time steps)? On? Its range and the step shown."""
        panel, a = self.editor.panel, self.settings
        why = SINGLE if panel.time_count() < 2 else \
            CONSTANT if panel.field_varies(self.editor.c["field"]) is False else ""
        available = not why
        self.section.set_unavailable(why or False)
        if a["on"] and not available:                  # nothing to animate: off, no bar
            a["on"] = False
            panel.animation_changed.emit()
        Switch.set_silently(self.on, a["on"])
        self.note.setText(why or OFF)
        self.note.setVisible(not (available and a["on"]))
        self.details.setVisible(available and a["on"])
        self.range_acts[a["range"]].setChecked(True)
        self.step_label.setText(panel.time_text())
        self.sync_range()

    def sync_range(self):
        """Color scale range grayed where it means nothing, and why."""
        c = self.editor.c
        why = ("Gradient: each step has its own range." if c["show"] == "gradient" else
               "Min and Max are typed: the range stays as typed."
               if c["lo"] is not None and c["hi"] is not None else "")
        for act in self.range_acts.values():
            act.setEnabled(not why)
        self.range_note.setText(why)
        self.range_note.setVisible(bool(why))

    def _switched(self, on):
        self.settings["on"] = bool(on)
        if on:
            self.section.set_expanded(True)
        self.sync()
        self.editor.panel.animation_changed_for(self.editor.c["id"])

    def _range(self, key):
        self.settings["range"] = key
        self.editor.panel.animation_changed_for(self.editor.c["id"])
