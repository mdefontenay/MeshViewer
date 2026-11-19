"""The playback bar under the 3D view: a case's time steps, one after another.

    [ ⏮ | ▶ | ⏭ ]  ━━━━━━━━●━━━━━━━━━━━━  t = 0.45 · Step 9 / 20   [ 🔁 ]  [ 10 ] fps

Step Backward / Play–Pause (Space) / Step Forward, the scrubber (drag, or click to jump),
the time and step in tabular figures, as wide as the widest step's (the scrubber never
moves), Loop (on: back to the first step after the last; off: stops there) and the frame
rate (1 – 120 a second). The bar only says which step to show (`index_changed`); the
window shows it. While playing, the next step is asked 1000 / fps ms after the last one
was handled, so a heavy step never piles up frames (the UI keeps answering).
"""
from __future__ import annotations

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QAction, QFont
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QSizePolicy, QSlider, QStyle,
                               QStyleOptionSlider, QWidget)

from meshviewer.gui.icons import icon
from meshviewer.gui.widgets.basics import Capsule
from meshviewer.gui.widgets.numbers import SpinField

FPS = (1, 120)                                  # frames (steps) a second
DEFAULT_FPS = 10


class _Scrubber(QSlider):
    """A slider whose click jumps to where it was clicked (not a page step)."""

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            opt = QStyleOptionSlider()
            self.initStyleOption(opt)
            groove = self.style().subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderGroove,
                                                 self)
            handle = self.style().subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderHandle,
                                                 self)
            if not handle.contains(e.position().toPoint()):
                x = int(e.position().x()) - groove.x() - handle.width() // 2
                span = groove.width() - handle.width()
                self.setValue(QStyle.sliderValueFromPosition(self.minimum(), self.maximum(),
                                                             x, max(span, 1)))
        super().mousePressEvent(e)

    def wheelEvent(self, e):
        e.ignore()                                  # (the 3D view's zoom, not the steps)


class AnimationBar(QWidget):
    index_changed = Signal(int)                 # the step to show

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("AnimationBar")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.labels, self.index, self.playing = [], 0, False
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._tick)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(10, 6, 10, 2)
        lay.setSpacing(10)
        self.a_back = QAction(icon("step_back"), "Step Backward", self)
        self.a_play = QAction(icon("play"), "Play", self)
        self.a_forward = QAction(icon("step_forward"), "Step Forward", self)
        self.a_back.triggered.connect(lambda: self.step(-1))
        self.a_play.triggered.connect(self.toggle)
        self.a_forward.triggered.connect(lambda: self.step(1))
        self.a_play.setToolTip("Play  (Space)")
        self.transport = Capsule([self.a_back, self.a_play, self.a_forward], icon_size=16)
        lay.addWidget(self.transport)
        self.slider = _Scrubber(Qt.Horizontal)
        self.slider.setAccessibleName("Time Step")
        self.slider.setToolTip("Time Step")
        self.slider.setPageStep(1)
        self.slider.setMinimumWidth(120)
        self.slider.valueChanged.connect(self._slid)
        lay.addWidget(self.slider, 1)
        self.readout = QLabel("")
        self.readout.setObjectName("InfoLine")
        font = QFont(self.readout.font())
        font.setFeature(QFont.Tag("tnum"), 1)       # tabular figures: no jitter
        self.readout.setFont(font)
        self.readout.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        lay.addWidget(self.readout)
        self.a_loop = QAction(icon("loop"), "Loop", self)
        self.a_loop.setCheckable(True)
        self.a_loop.setChecked(True)
        self.loop_box = Capsule([self.a_loop], icon_size=16)
        lay.addWidget(self.loop_box)
        self.fps = SpinField(*FPS, 0)
        self.fps.setValue(DEFAULT_FPS)
        self.fps.setToolTip("Frame Rate")
        self.fps.setAccessibleName("Frame Rate")
        self.fps.setFixedWidth(self.fps.fontMetrics().horizontalAdvance("1200") + 16)
        self.fps.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        rate = QHBoxLayout()
        rate.setSpacing(4)
        rate.addWidget(self.fps)
        unit = QLabel("fps")
        unit.setObjectName("AxisLabel")
        rate.addWidget(unit)
        lay.addLayout(rate)

    # ---- state ---------------------------------------------------------------------------
    @property
    def count(self):
        return len(self.labels)

    @property
    def loop(self):
        return self.a_loop.isChecked()

    @property
    def interval(self):
        """Milliseconds between two steps at the frame rate typed."""
        return int(round(1000 / max(FPS[0], self.fps.value())))

    def _text(self, i):
        return f"t = {self.labels[i]} · Step {i + 1} / {self.count}"

    def set_steps(self, labels, index):
        """The time folders' names ("0", "0.5"…) and the step shown."""
        self.labels = list(labels)
        self.slider.blockSignals(True)
        self.slider.setRange(0, max(0, self.count - 1))
        self.slider.blockSignals(False)
        fm = self.readout.fontMetrics()                # as wide as the widest step's text
        self.readout.setFixedWidth(max((fm.horizontalAdvance(self._text(i))
                                        for i in range(self.count)), default=0) + 6)
        self.set_index(index or 0, emit=False)

    def set_index(self, i, emit=True):
        """Show step i (clamped) in the bar; emit: ask for it to be shown."""
        i = max(0, min(int(i), self.count - 1)) if self.count else 0
        self.index = i
        self.slider.blockSignals(True)
        self.slider.setValue(i)
        self.slider.blockSignals(False)
        if self.count:
            self.readout.setText(self._text(i))
        self.a_back.setEnabled(i > 0)
        self.a_forward.setEnabled(i < self.count - 1)
        if emit:
            self.index_changed.emit(i)

    # ---- transport -----------------------------------------------------------------------
    def step(self, d):
        self.pause()
        self.set_index(self.index + d)

    def _slid(self, v):
        self.set_index(v)

    def toggle(self):
        self.pause() if self.playing else self.play()

    def play(self):
        if self.count < 2 or self.playing:
            return
        if self.index >= self.count - 1:            # at the end: from the start
            self.set_index(0)
        self.playing = True
        self.a_play.setIcon(icon("pause"))
        self.a_play.setText("Pause")
        self.a_play.setToolTip("Pause  (Space)")
        self.timer.start(self.interval)

    def pause(self):
        self.timer.stop()
        if not self.playing:
            return
        self.playing = False
        self.a_play.setIcon(icon("play"))
        self.a_play.setText("Play")
        self.a_play.setToolTip("Play  (Space)")

    def _tick(self):
        """The next step (the last: back to the first with Loop, else stop)."""
        if not self.playing:
            return
        nxt = self.index + 1
        if nxt >= self.count:
            if not self.loop:
                self.pause()
                return
            nxt = 0
        self.set_index(nxt)                         # shown before the next one is asked
        if self.playing:
            self.timer.start(self.interval)

    def hideEvent(self, e):
        self.pause()
        super().hideEvent(e)
