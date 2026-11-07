"""NEW (v2.14): the "?" next to "Target y+" (CFD section and CFD mode) — which y+
to aim for: resolve the wall (y+ ≈ 1) or use wall functions (30 < y+ < 300), with
a plot of the law of the wall.

    ┌ Target y+ — resolve the wall, or use wall functions ──────────────────┐
    │  u+  ▲            viscous │ buffer │ log layer                         │
    │      │  ░░ blue band ░░  │        │ ▒▒ orange band ▒▒                  │
    │      │     ╱ u+ = y+ ─ ─ ─ ─ Spalding ─────── log law                  │
    │      └────────────────────────────────────────▶ y+ (log)               │
    │  ■ Resolve the wall: y+ ≈ 1 …                     [Use y+ = 1]         │
    │  ■ Wall functions: 30 – 300 …                     [Use y+ = 50]        │
    │  ⚠ Avoid 5 – 30 (buffer layer) …                                       │
    └────────────────────────────────────────────────────────────────────────┘

Drawn with QPainter in the app's colours; the two approaches use the inflation
plot's two series colours (blue / orange), labels stay in the text colours.
"""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPalette, QPen
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QToolTip, QVBoxLayout, QWidget,
)

from .. import cfd

X0, X1 = 0.1, 1000.0                  # y+ range (log)
Y0, Y1 = 0.0, 30.0                    # u+ range
ZONES = ((X0, 5.0, "Viscous sublayer"), (5.0, 30.0, "Buffer"), (30.0, 300.0, "Log layer"),
         (300.0, X1, "Outer"))
RESOLVED = (X0, 1.0)                  # the y+ range each approach aims for
WALL_FN = (30.0, 300.0)
SERIES = {"resolved": ("#2a78d6", "#3987e5"), "wallfn": ("#eb6834", "#d95926")}


def _dark(w):
    return w.palette().color(QPalette.Window).lightness() < 128


def _series(w, key):
    return QColor(SERIES[key][1 if _dark(w) else 0])


def zone_of(yp):
    for lo, hi, name in ZONES:
        if yp < hi:
            return name
    return ZONES[-1][2]


class LawOfWallPlot(QWidget):
    """u+ against y+ (log): Spalding's law, its two limits (u+ = y+ and the log law),
    the zones, and the y+ ranges of the two approaches. Hover for the numbers."""
    PAD_L, PAD_R, PAD_T, PAD_B = 44, 16, 24, 36

    def __init__(self, target=None, parent=None):
        super().__init__(parent)
        self.target = target
        self.hover = None
        self.setMinimumSize(520, 270)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMouseTracking(True)
        u = np.linspace(0.0, 32.0, 400)
        self._yp, self._up = cfd.spalding(u), u

    def _px(self, yp, up):
        w = self.width() - self.PAD_L - self.PAD_R
        h = self.height() - self.PAD_T - self.PAD_B
        fx = (np.log10(yp) - np.log10(X0)) / (np.log10(X1) - np.log10(X0))
        return QPointF(self.PAD_L + fx * w, self.PAD_T + (1 - (up - Y0) / (Y1 - Y0)) * h)

    def _path(self, xs, ys):
        ok = (xs >= X0) & (xs <= X1) & (ys >= Y0 - 1) & (ys <= Y1 + 1)
        xs, ys = xs[ok], np.clip(ys[ok], Y0, Y1)
        path = QPainterPath(self._px(xs[0], ys[0]))
        for x, y in zip(xs[1:], ys[1:]):
            path.lineTo(self._px(x, y))
        return path

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pal = self.palette()
        text = pal.color(QPalette.WindowText)
        muted = pal.color(QPalette.PlaceholderText)
        grid = QColor(text)
        grid.setAlphaF(0.07)
        font = QFont(p.font())
        font.setPixelSize(11)
        p.setFont(font)
        left, right = self.PAD_L, self.width() - self.PAD_R
        top, base = self.PAD_T, self.height() - self.PAD_B

        # the y+ ranges of the two approaches (soft bands, under everything)
        for (lo, hi), key in ((RESOLVED, "resolved"), (WALL_FN, "wallfn")):
            c = _series(self, key)
            c.setAlphaF(0.14)
            a, b = self._px(lo, 0).x(), self._px(hi, 0).x()
            p.fillRect(QRectF(a, top, b - a, base - top), c)
        # zones: thin dividers + names along the top
        for lo, hi, name in ZONES:
            a, b = self._px(lo, 0).x(), self._px(hi, 0).x()
            if lo > X0:
                p.setPen(QPen(grid, 1))
                p.drawLine(QPointF(a, top), QPointF(a, base))
            p.setPen(muted)
            p.drawText(QRectF(a, 4, b - a, 14), Qt.AlignHCenter | Qt.AlignVCenter, name)
        # grid + axis labels
        for up in range(0, 31, 10):
            y = self._px(1, up).y()
            p.setPen(QPen(grid, 1))
            p.drawLine(QPointF(left, y), QPointF(right, y))
            p.setPen(muted)
            p.drawText(QRectF(0, y - 7, left - 8, 14), Qt.AlignRight | Qt.AlignVCenter, str(up))
        for yp in (0.1, 1, 10, 100, 1000):
            x = self._px(yp, 0).x()
            p.drawText(QRectF(x - 24, base + 5, 48, 14), Qt.AlignHCenter, f"{yp:g}")
        p.drawText(QRectF(left, self.height() - 15, right - left, 14), Qt.AlignHCenter,
                   "y+  (first cell height in viscous lengths ν / u*)")
        p.save()
        p.translate(11, (top + base) / 2)
        p.rotate(-90)
        p.drawText(QRectF(-60, -7, 120, 14), Qt.AlignCenter, "u+ = u / u*")
        p.restore()

        # the two limits (dashed, text colour) and the law (solid, first series colour)
        xs = np.logspace(np.log10(X0), np.log10(X1), 300)
        lim = QColor(text)
        lim.setAlphaF(0.45)
        pen = QPen(lim, 1.2)
        pen.setStyle(Qt.DashLine)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawPath(self._path(xs[xs <= 30], xs[xs <= 30]))
        p.drawPath(self._path(xs[xs >= 1.5], np.log(xs[xs >= 1.5]) / cfd.KAPPA + cfd.B_LOG))
        law = QColor(text)
        p.setPen(QPen(law, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(self._path(self._yp, self._up))
        # direct labels on the curves
        p.setPen(muted)
        q = self._px(2.2, 2.2)
        p.drawText(QRectF(q.x() + 4, q.y() - 4, 80, 14), Qt.AlignLeft, "u+ = y+")
        y9 = self._px(1, 4).y()                          # empty corner under the curves
        p.drawText(QRectF(right - 264, y9, 258, 14), Qt.AlignRight,
                   "dashed: log law  u+ = ln(y+) / 0.41 + 5.2")
        p.setPen(text)
        q = self._px(9, float(np.interp(9, self._yp, self._up)))
        p.drawText(QRectF(q.x() + 6, q.y() + 2, 140, 14), Qt.AlignLeft, "law of the wall")

        # the target typed in the sidebar
        if self.target and X0 < self.target < X1:
            x = self._px(self.target, 0).x()
            tc = QColor(text)
            tc.setAlphaF(0.7)
            pen = QPen(tc, 1.2)
            pen.setStyle(Qt.DotLine)
            p.setPen(pen)
            p.drawLine(QPointF(x, top + 14), QPointF(x, base))
            p.setPen(text)
            p.drawText(QRectF(x + 4, top + 16, 160, 14), Qt.AlignLeft,
                       f"your target {self.target:g}")
        # hover: crosshair + point on the law
        if self.hover is not None:
            yp = self.hover
            up = float(np.interp(yp, self._yp, self._up))
            x = self._px(yp, 0).x()
            cross = QColor(text)
            cross.setAlphaF(0.25)
            p.setPen(QPen(cross, 1))
            p.drawLine(QPointF(x, top), QPointF(x, base))
            p.setPen(QPen(pal.color(QPalette.Window), 2))
            p.setBrush(text)
            p.drawEllipse(self._px(yp, up), 4.5, 4.5)

    def mouseMoveEvent(self, e):
        w = self.width() - self.PAD_L - self.PAD_R
        fx = (e.position().x() - self.PAD_L) / max(w, 1)
        if not 0 <= fx <= 1:
            return self.leaveEvent(None)
        yp = 10 ** (np.log10(X0) + fx * (np.log10(X1) - np.log10(X0)))
        self.hover = yp
        self.update()
        up = float(np.interp(yp, self._yp, self._up))
        QToolTip.showText(e.globalPosition().toPoint(),
                          f"y+ {yp:.3g}  ·  u+ {up:.3g}\n{zone_of(yp)}", self)

    def leaveEvent(self, _):
        self.hover = None
        QToolTip.hideText()
        self.update()


class _Swatch(QWidget):
    def __init__(self, key):
        super().__init__()
        self.key = key
        self.setFixedSize(12, 16)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        p.setBrush(_series(self, self.key))
        p.drawRoundedRect(QRectF(0, 3, 10, 10), 2, 2)


class WallHelpCard(QFrame):
    """A card in the middle of the window. Click outside or press Esc to close."""

    def __init__(self, parent, target=None, set_target=None):
        super().__init__(parent.window(), Qt.Popup | Qt.FramelessWindowHint |
                         Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self._set_target = set_target
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        body = QFrame()
        body.setObjectName("ValuesBody")
        outer.addWidget(body)
        lay = QVBoxLayout(body)
        lay.setContentsMargins(20, 14, 20, 16)
        lay.setSpacing(6)
        t = QLabel("Target y+ — resolve the wall, or use wall functions")
        t.setObjectName("PageTitle")
        lay.addWidget(t)
        intro = QLabel("y+ is the height of the first cell measured in viscous lengths (ν / u*). "
                       "Close to a wall the speed follows the law of the wall, with three zones. "
                       "Put the first cell in the zone your turbulence model expects.")
        intro.setObjectName("InfoLine")
        intro.setWordWrap(True)
        lay.addWidget(intro)
        self.plot = LawOfWallPlot(target)
        lay.addWidget(self.plot)
        for key, title, text, value in (
                ("resolved", "Resolve the wall — y+ ≈ 1 (below 5)",
                 "The first cell sits in the viscous sublayer and the solver resolves the whole "
                 "profile: 10 – 20 layers or more inside the boundary layer. For k-ω SST, "
                 "Spalart-Allmaras and transition models; the one to use for separation, drag "
                 "and heat transfer.", 1.0),
                ("wallfn", "Wall functions — 30 < y+ < 300",
                 "The first cell sits in the log layer and a formula bridges the gap to the "
                 "wall: far fewer cells. For k-ε models and attached flows. Keep the first cell "
                 "well inside the boundary layer: at low Reynolds numbers the upper limit is "
                 "lower.", 50.0)):
            row = QHBoxLayout()
            row.setSpacing(8)
            row.addWidget(_Swatch(key), 0, Qt.AlignTop)
            col = QVBoxLayout()
            col.setSpacing(1)
            head = QLabel(title)
            head.setObjectName("SubHeader")
            col.addWidget(head)
            lab = QLabel(text)
            lab.setObjectName("InfoLine")
            lab.setWordWrap(True)
            col.addWidget(lab)
            row.addLayout(col, 1)
            if set_target is not None:
                b = QPushButton(f"Use y+ = {value:g}")
                b.setObjectName("LinkButton")
                b.setFlat(True)
                b.setCursor(Qt.PointingHandCursor)
                b.clicked.connect(lambda _=False, v=value: self._use(v))
                row.addWidget(b, 0, Qt.AlignTop)
            lay.addLayout(row)
        warn = QLabel("<span style='color:#ff9f0a'>⚠</span> Avoid 5 &lt; y+ &lt; 30 (the buffer "
                      "layer): neither approach is right there — unless the solver blends "
                      "them (Fluent Enhanced Wall Treatment, STAR-CCM+ All y+, OpenFOAM "
                      "nutUSpaldingWallFunction).")
        warn.setTextFormat(Qt.RichText)
        warn.setObjectName("InfoLine")
        warn.setWordWrap(True)
        lay.addWidget(warn)
        note = QLabel("The y+ here is a flat-plate estimate: on real walls it is highest near "
                      "the leading edge (CFD mode ▸ Inflation layers ▸ y+ along the flow).")
        note.setObjectName("Caption")
        note.setWordWrap(True)
        lay.addWidget(note)
        body.setFixedWidth(600)
        self.adjustSize()
        win = parent.window().geometry()
        self.move(win.center().x() - self.width() // 2,
                  max(win.top() + 30, win.center().y() - self.height() // 2))

    def _use(self, v):
        if self._set_target is not None:
            self._set_target(v)
        self.close()

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(e)


def wall_help_button(get_target=None, set_target=None):
    """The "?" (same look as the others) that opens the card."""
    b = QPushButton("?")
    b.setObjectName("HelpButton")
    b.setCursor(Qt.PointingHandCursor)
    b.setToolTip("Which y+? Resolve the wall (y+ ≈ 1) or use wall functions (30 – 300)")
    b.setFixedSize(16, 16)

    def show():
        b.card = WallHelpCard(b, get_target() if get_target else None, set_target)
        b.card.show()
    b.clicked.connect(show)
    return b


def label_with_help(text, button):
    """A row label with its "?" right after the name."""
    w = QWidget()
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 0, 0, 0)
    h.setSpacing(5)
    h.addWidget(QLabel(text))
    h.addWidget(button)
    h.addStretch(1)
    return w
