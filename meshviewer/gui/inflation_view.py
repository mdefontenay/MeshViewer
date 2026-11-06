"""NEW (v2.11): the "Inflation" page of CFD mode (CAD files) — plots and visuals
of the inflation layer calculator. Inputs are in the sidebar (CFD mode).

    Inflation layers                          Turbulent · Supersonic
    [Reynolds] [y_min for y+] [Estimated y+] [δ99] [Total height] [Largest cell]
    ┌ Height vs layer # ───────────────────────────────┐ ┌ Near the wall ┐
    │ blue: total height · red: cell height · stack     │ │ cells to scale │
    │ green: boundary layer δ99 · red dots: y_des       │ │                │
    └──────────────────────────────────────────────────┘ └────────────────┘
    ✓ / ⚠ checks
    U, T, p, ρ, μ, Cf, τw, u*

Everything is drawn with QPainter in the app's colours (light and dark).
"""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPalette, QPen
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea, QSizePolicy, QToolTip, QVBoxLayout,
    QWidget,
)

BLUE, RED, GREEN, PURPLE = "#0a84ff", "#ff453a", "#30b350", "#9b59d0"


def length_unit(m):
    """Unit that reads best for lengths up to m: (factor, label)."""
    a = abs(m or 0)
    if a and a < 1e-4:
        return 1e6, "µm"
    if a < 0.1:
        return 1e3, "mm"
    return 1.0, "m"


def show_length(m, unit=None):
    if m is None or not np.isfinite(m):
        return "—"
    f, u = unit or length_unit(m)
    return f"{m * f:.3g} {u}"


def nice_step(span, target=6):
    raw = span / max(target, 1)
    p = 10 ** np.floor(np.log10(raw)) if raw > 0 else 1
    for m in (1, 2, 2.5, 5, 10):
        if m * p >= raw:
            return m * p
    return 10 * p


def _dark(widget):
    return widget.palette().color(QPalette.Window).lightness() < 128


# ---- numbers at the top ----------------------------------------------------------------
class _Tile(QFrame):
    def __init__(self, caption, tip):
        super().__init__()
        self.setObjectName("ResultCard")
        self.setToolTip(tip)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 8, 12, 8)
        lay.setSpacing(1)
        cap = QLabel(caption)
        cap.setObjectName("Caption")
        lay.addWidget(cap)
        self.value = QLabel("—")
        self.value.setObjectName("TileValue")
        self.value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(self.value)
        self.note = QLabel("")
        self.note.setObjectName("InfoLine")
        lay.addWidget(self.note)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set(self, value, note="", state=None):
        self.value.setText(value)
        self.note.setText(note)
        color = {"ok": GREEN, "warn": "#ff9f0a", "bad": RED}.get(state)
        self.value.setStyleSheet(f"color: {color};" if color else "")


# ---- the plot ---------------------------------------------------------------------------
class InflationPlot(QWidget):
    """Height against layer number, like the original calculator's graph."""
    PAD_L, PAD_R, PAD_T, PAD_B = 64, 18, 16, 40

    def __init__(self, parent=None):
        super().__init__(parent)
        self.r = None
        self.setMinimumHeight(320)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)

    def set_result(self, r):
        self.r = r if r and r.get("ok") else None
        self.update()

    # data -> pixels
    def _ranges(self):
        r = self.r
        top = max(r["y_tot"], r["d99"], r["y_des"]) * 1.15
        return (-1.0, r["N"] + 1.0), (-0.06 * top, top)

    def _px(self, x, y):
        (x0, x1), (y0, y1) = self._ranges()
        w = self.width() - self.PAD_L - self.PAD_R
        h = self.height() - self.PAD_T - self.PAD_B
        return QPointF(self.PAD_L + (x - x0) / (x1 - x0) * w,
                       self.PAD_T + (1 - (y - y0) / (y1 - y0)) * h)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pal = self.palette()
        text = pal.color(QPalette.WindowText)
        grid = QColor(text)
        grid.setAlphaF(0.08)
        axis = QColor(text)
        axis.setAlphaF(0.35)
        frame = QColor(text)
        frame.setAlphaF(0.04)
        p.setPen(Qt.NoPen)
        p.setBrush(frame)
        p.drawRoundedRect(QRectF(0, 0, self.width(), self.height()), 10, 10)
        if self.r is None:
            p.setPen(pal.color(QPalette.PlaceholderText))
            p.drawText(self.rect(), Qt.AlignCenter, "Fill in the CFD mode inputs in the sidebar")
            return
        r = self.r
        (x0, x1), (y0, y1) = self._ranges()
        f, unit = length_unit(y1)
        font = QFont(p.font())
        font.setPixelSize(11)
        p.setFont(font)

        # grid + tick labels
        ystep = nice_step(y1 - y0)
        xstep = max(1, int(nice_step(x1 - x0, 12)))
        for gx in range(0, int(x1) + 1, xstep):
            a, b = self._px(gx, y0), self._px(gx, y1)
            p.setPen(QPen(grid, 1))
            p.drawLine(a, b)
            p.setPen(axis)
            p.drawText(QRectF(a.x() - 20, self.height() - self.PAD_B + 4, 40, 14),
                       Qt.AlignHCenter, str(gx))
        gy = np.ceil(y0 / ystep) * ystep
        while gy <= y1:
            gy = 0.0 if abs(gy) < ystep * 1e-6 else gy            # no "−0"
            a, b = self._px(x0, gy), self._px(x1, gy)
            p.setPen(QPen(axis if abs(gy) < ystep * 1e-6 else grid, 1))
            p.drawLine(a, b)
            p.setPen(axis)
            p.drawText(QRectF(0, a.y() - 7, self.PAD_L - 8, 14), Qt.AlignRight | Qt.AlignVCenter,
                       f"{gy * f:.3g}")
            gy += ystep
        p.setPen(QPen(axis, 1))
        a = self._px(0, y0)
        p.drawLine(a, self._px(0, y1))
        p.setPen(pal.color(QPalette.WindowText))
        p.drawText(QRectF(self.PAD_L, self.height() - 18, self.width() - self.PAD_L - self.PAD_R,
                          14), Qt.AlignRight, "Layer #")
        p.save()
        p.translate(14, self.PAD_T + (self.height() - self.PAD_T - self.PAD_B) / 2)
        p.rotate(-90)
        p.drawText(QRectF(-80, -8, 160, 16), Qt.AlignCenter, f"Height ({unit})")
        p.restore()

        n, ymin, g = r["N"], r["y_min"], r["G"]
        # total height (blue curve): y_min (1 − G^x) / (1 − G), 0 ≤ x ≤ N
        xs = np.linspace(0, n, 400)
        ys = ymin * xs if abs(g - 1) < 1e-12 else ymin * (1 - g ** xs) / (1 - g)
        path = QPainterPath(self._px(xs[0], ys[0]))
        for x, y in zip(xs[1:], ys[1:]):
            path.lineTo(self._px(x, y))
        p.setPen(QPen(QColor(BLUE), 2.2))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
        # cell height (red steps): y_min G^floor(x − ½), ½ ≤ x < N + ½
        p.setPen(QPen(QColor(RED), 2))
        for i, h in enumerate(r["heights"], start=1):
            p.drawLine(self._px(i - 0.5, h), self._px(i + 0.5, h))
        # inflation look: each layer's top as a short line at layer 1
        for i, t in enumerate(r["total"][1:], start=1):
            c = QColor(PURPLE if i % 2 else text.name())
            c.setAlphaF(0.9)
            p.setPen(QPen(c, 1.2))
            p.drawLine(self._px(0.5, t), self._px(1.5, t))
        # boundary layer δ99 (green) and desired cell size (red, dotted)
        mid = n / 2
        for y, color, style, label in (
                (r["d99"], GREEN, Qt.SolidLine, f"Boundary layer: δ99 = {show_length(r['d99'])}"),
                (r["y_des"], RED, Qt.DotLine,
                 f"Desired surface cell size = {show_length(r['y_des'])}")):
            pen = QPen(QColor(color), 1.6)
            pen.setStyle(style)
            p.setPen(pen)
            p.drawLine(self._px(x0, y), self._px(x1, y))
            pos = self._px(mid, y)
            p.setPen(QColor(color))
            p.drawText(QRectF(pos.x() - 160, pos.y() - 18, 320, 14), Qt.AlignCenter, label)
        p.setPen(Qt.NoPen)
        halo = QColor(RED)
        halo.setAlphaF(0.25)
        p.setBrush(halo)
        p.drawEllipse(self._px(mid, r["y_des"]), 8, 8)
        p.setBrush(QColor(RED))
        p.drawEllipse(self._px(mid, r["y_des"]), 3.5, 3.5)
        # legend
        lx, ly = self.PAD_L + 12, self.PAD_T + 10
        for color, label in ((BLUE, "Total height"), (RED, "Cell height"),
                             (PURPLE, "Layers (to scale)")):
            p.setPen(QPen(QColor(color), 2.4))
            p.drawLine(QPointF(lx, ly + 6), QPointF(lx + 16, ly + 6))
            p.setPen(pal.color(QPalette.WindowText))
            p.drawText(QRectF(lx + 22, ly, 150, 14), Qt.AlignVCenter, label)
            ly += 17

    def mouseMoveEvent(self, e):
        if self.r is None:
            return
        (x0, x1), _ = self._ranges()
        w = self.width() - self.PAD_L - self.PAD_R
        x = x0 + (e.position().x() - self.PAD_L) / max(w, 1) * (x1 - x0)
        i = int(round(x))
        if 1 <= i <= self.r["N"]:
            QToolTip.showText(e.globalPosition().toPoint(),
                              f"Layer {i}\ncell height {show_length(self.r['heights'][i - 1])}"
                              f"\ntotal height {show_length(self.r['total'][i])}", self)
        else:
            QToolTip.hideText()


# ---- near-wall cells, to scale -------------------------------------------------------------
class LayerStack(QWidget):
    """The inflation layers drawn as cells on a wall, with the first ordinary
    cell (y_des) on top and the boundary-layer edge."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.r = None
        self.setMinimumWidth(190)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

    def set_result(self, r):
        self.r = r if r and r.get("ok") else None
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pal = self.palette()
        text = pal.color(QPalette.WindowText)
        frame = QColor(text)
        frame.setAlphaF(0.04)
        p.setPen(Qt.NoPen)
        p.setBrush(frame)
        p.drawRoundedRect(QRectF(0, 0, self.width(), self.height()), 10, 10)
        font = QFont(p.font())
        font.setPixelSize(11)
        p.setFont(font)
        p.setPen(text)
        p.drawText(QRectF(12, 8, self.width() - 24, 16), Qt.AlignLeft, "Near the wall (to scale)")
        if self.r is None:
            return
        r = self.r
        left, right = 16.0, self.width() - 16.0
        bottom, top = self.height() - 30.0, 34.0
        y_top = max(r["y_tot"] + r["y_des"], r["d99"]) * 1.08
        to_px = lambda y: bottom - y / y_top * (bottom - top)       # noqa: E731
        cols = 7
        cw = (right - left) / cols
        line = QColor(text)
        line.setAlphaF(0.55)
        fill = QColor(BLUE)
        fill.setAlphaF(0.10 if not _dark(self) else 0.18)
        # inflation cells; the ones thinner than a pixel merge into one solid band
        tops = r["total"]
        k = 0
        while k < r["N"] and to_px(tops[k]) - to_px(tops[k + 1]) < 0.8:
            k += 1
        p.setPen(QPen(line, 0.8))
        if k:
            band = QColor(BLUE)
            band.setAlphaF(0.55)
            p.setBrush(band)
            p.drawRect(QRectF(left, to_px(tops[k]), right - left, to_px(0) - to_px(tops[k])))
        p.setBrush(fill)
        for i in range(k, r["N"]):
            y_a, y_b = to_px(tops[i]), to_px(tops[i + 1])
            for c in range(cols):
                p.drawRect(QRectF(left + c * cw, y_b, cw, y_a - y_b))
        # first ordinary cell (y_des) on top, dotted red
        pen = QPen(QColor(RED), 1.4)
        pen.setStyle(Qt.DotLine)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        y_a, y_b = to_px(r["y_tot"]), to_px(r["y_tot"] + r["y_des"])
        for c in range(0, cols, 2):
            p.drawRect(QRectF(left + c * cw, y_b, 2 * cw, y_a - y_b))
        # boundary layer edge
        pen = QPen(QColor(GREEN), 1.6)
        pen.setStyle(Qt.DashLine)
        p.setPen(pen)
        y = to_px(r["d99"])
        p.drawLine(QPointF(left, y), QPointF(right, y))
        p.setPen(QColor(GREEN))
        p.drawText(QRectF(left, y - 16, right - left, 14), Qt.AlignRight, "δ99")
        # wall
        p.setPen(QPen(text, 2))
        p.drawLine(QPointF(left - 4, bottom), QPointF(right + 4, bottom))
        hatch = QColor(text)
        hatch.setAlphaF(0.35)
        p.setPen(QPen(hatch, 1))
        x = left
        while x < right:
            p.drawLine(QPointF(x, bottom + 8), QPointF(x + 8, bottom))
            x += 8
        p.setPen(pal.color(QPalette.PlaceholderText))
        p.drawText(QRectF(left, bottom + 10, right - left, 14), Qt.AlignCenter, "wall")


# ---- the page --------------------------------------------------------------------------------
class InflationView(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("InflationView")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        page = QWidget()
        page.setObjectName("InflationPage")
        self.setWidget(page)
        lay = QVBoxLayout(page)
        lay.setContentsMargins(22, 18, 22, 18)
        lay.setSpacing(12)

        head = QHBoxLayout()
        title = QLabel("Inflation layers")
        title.setObjectName("PageTitle")
        head.addWidget(title)
        head.addStretch(1)
        self.regime = QLabel("")
        self.regime.setObjectName("Tag")
        head.addWidget(self.regime)
        lay.addLayout(head)

        tiles = QGridLayout()
        tiles.setHorizontalSpacing(10)
        tiles.setVerticalSpacing(10)
        self.tiles = {}
        for i, (key, caption, tip) in enumerate((
                ("re", "Reynolds number", "Re = ρ U L / μ  (laminar below 5·10⁵)"),
                ("y_calc", "First cell for target y+", "y_min = y+ μ / (ρ u*)"),
                ("yplus", "Estimated y+", "y+ = y_min u* ρ / μ  (tends to be a bit high)"),
                ("d99", "Boundary layer δ99", "Flat plate: 0.38 L / Re^⅕ (turbulent) or "
                                              "4.91 L / √Re (laminar); supersonic ÷ rc^⅑"),
                ("y_tot", "Total inflation height", "Σ y_min Gⁿ, n = 0 … N − 1  (should be > δ99)"),
                ("y_max", "Largest layer", "y_max = y_min G^(N−1)  (aim for y_des ≈ 2 y_max)"))):
            t = _Tile(caption, tip)
            tiles.addWidget(t, i // 3, i % 3)
            self.tiles[key] = t
        lay.addLayout(tiles)

        row = QHBoxLayout()
        row.setSpacing(10)
        self.plot = InflationPlot()
        row.addWidget(self.plot, 1)
        self.stack = LayerStack()
        row.addWidget(self.stack)
        lay.addLayout(row, 1)

        self.checks = QLabel("")
        self.checks.setObjectName("ValueLabel")
        self.checks.setWordWrap(True)
        self.checks.setTextFormat(Qt.RichText)
        lay.addWidget(self.checks)
        self.numbers = QLabel("")
        self.numbers.setObjectName("InfoLine")
        self.numbers.setWordWrap(True)
        self.numbers.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(self.numbers)

    def set_result(self, r):
        self.plot.set_result(r)
        self.stack.set_result(r)
        if not r or not r.get("ok"):
            for t in self.tiles.values():
                t.set("—")
            self.regime.setText("")
            self.checks.setText("Fill in the inputs in the sidebar (CFD mode).")
            self.numbers.setText("")
            return
        self.regime.setText(("Turbulent" if r["turbulent"] else "Laminar") + " · " +
                            ("Supersonic" if r["supersonic"] else "Subsonic"))
        self.tiles["re"].set(f"{r['Re']:.3g}", "turbulent" if r["turbulent"] else "laminar")
        self.tiles["y_calc"].set(show_length(r["y_calc"]), f"{r['y_calc']:.3g} m")
        off = abs(r["yplus_est"] - r["target"]) / max(r["target"], 1e-12)
        self.tiles["yplus"].set(f"{r['yplus_est']:.3g}", f"target {r['target']:g}",
                                "ok" if off < 0.2 else "warn")
        self.tiles["d99"].set(show_length(r["d99"]), f"{r['d99']:.3g} m")
        self.tiles["y_tot"].set(show_length(r["y_tot"]), f"{r['N']} layers × G {r['G']:g}",
                                "ok" if r["covers_bl"] else "bad")
        self.tiles["y_max"].set(show_length(r["y_max"]),
                                f"desired cell {show_length(r['y_des'])}",
                                "ok" if r["smooth"] else "warn")
        ok, warn = f"<span style='color:{GREEN}'>✓</span>", "<span style='color:#ff9f0a'>⚠</span>"
        covers = "covers" if r["covers_bl"] else "is thinner than"
        lines = [
            f"{ok if r['covers_bl'] else warn} Inflation {covers}"
            f" the boundary layer: total {show_length(r['y_tot'])} vs δ99 {show_length(r['d99'])}",
            f"{ok if r['smooth'] else warn} Transition to the mesh: desired cell "
            f"{show_length(r['y_des'])} = {r['y_des'] / r['y_max']:.2g} × the largest layer "
            f"(about 2× is smooth)",
            f"{ok if off < 0.2 else warn} Estimated y+ {r['yplus_est']:.3g} for a target of "
            f"{r['target']:g}",
        ]
        self.checks.setText("<br>".join(lines))
        self.numbers.setText(
            f"U {r['U']:.4g} m/s · T {r['T']:.4g} K · p {r['p']:.5g} Pa · ρ {r['rho']:.4g} kg/m³"
            f" · μ {r['mu']:.4g} Pa·s · k {r['k']:.3g} W/(m·K) · Cf {r['Cf']:.3g}"
            f" · τw {r['tau']:.4g} Pa · u* {r['u_star']:.4g} m/s · rc {r['rc']:.3g}")
