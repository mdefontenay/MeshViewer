"""The time steps of a case in the window: the playback bar under the 3D view
(gui/widgets/animation_bar.py) and the step shown.

The bar shows while a contour's tab is shown whose ▸ Animation is on, or a probe's
(its plot over time), for a case with several time steps (`_animating`). That tab shows the animation's step (`_anim_step`, the
latest at first); every other tab — the 3D View, a plot, a contour not animated — the
latest step, as the case opened; with no contour animated any more, the animation starts
again from the latest. A step picked on the bar (a button, the scrubber, playing) is shown
by the scene (`Scene.set_time_index`: the fields swapped in place); then its listeners
follow (`scene.time_listeners`): Contours (and the section's cut cells), Plots, Measure
Selected — each panel its own — and the bar (here). Space
plays / pauses while the 3D view has the focus and the bar shows.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut

from meshviewer.gui.widgets.animation_bar import AnimationBar


class Animation:
    def _build_animation(self, layout, at):
        self.anim_bar = AnimationBar()
        self.anim_bar.setVisible(False)
        layout.insertWidget(at, self.anim_bar)
        self.anim_bar.index_changed.connect(self._time_picked)
        space = QShortcut(QKeySequence(Qt.Key_Space), self.plotter)
        space.setContext(Qt.WidgetWithChildrenShortcut)
        space.activated.connect(self._play_pause)
        self._space = space
        self.sidebar.contours_panel.animation_changed.connect(self._sync_animation)
        self._anim_step = None                              # the animation's step

    def _bind_animation(self):
        """A file opened: its time steps followed."""
        self._anim_step = None
        self.scene.time_listeners.append(self._time_changed)
        self._sync_animation()

    def _animating(self):
        """Is the tab shown a contour with ▸ Animation on, or a probe's, on a case with
        several steps?"""
        sc = self.scene
        if sc is None or sc.time_count < 2:
            return False
        if str(self._page).startswith("probe:"):
            return True
        if not str(self._page).startswith("contour:"):
            return False
        c = self.sidebar.contours_panel.contour(int(self._page.split(":", 1)[1]))
        return bool(c and c["anim"]["on"])

    def _sync_animation(self):
        """The bar, and the step shown, for the tab shown (see above)."""
        sc = self.scene
        if sc is None or sc.time_count < 2:
            self.anim_bar.pause()
            self.anim_bar.setVisible(False)
            return
        m = sc.model
        last = len(m.times) - 1
        if not any(c["anim"]["on"] for c in self.sidebar.contours_panel.contours):
            self._anim_step = None                          # none left: from the end
        on = self._animating()
        if on:
            step = last if self._anim_step is None else self._anim_step
            if self.anim_bar.isHidden():
                self.anim_bar.set_steps(m.time_labels, step)
            sc.set_time_index(step)
            m.case.prefetch(step, sc.wanted_fields())       # the next steps, ahead
        else:
            self.anim_bar.pause()
            sc.set_time_index(last)
        self.anim_bar.setVisible(on)

    def _time_picked(self, i):
        if self.scene is not None:
            self.scene.set_time_index(i)

    def _time_changed(self):
        """Another step shown (from the bar or not): the bar, the animation's step."""
        if self._animating():
            self._anim_step = self.scene.model.time_index
        self.anim_bar.set_index(self.scene.model.time_index, emit=False)

    def _play_pause(self):
        if not self.anim_bar.isHidden():
            self.anim_bar.toggle()
