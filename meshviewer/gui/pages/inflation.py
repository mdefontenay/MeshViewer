"""The "Inflation" page of CFD mode (CAD files) — plots and visuals
of the inflation layer calculator. Inputs are in the sidebar (CFD mode).

    Inflation layers                          Turbulent · Supersonic
    [Reynolds] [First layer for y+] [Estimated y+] [Boundary layer] [Total] [Max layer]
    ┌ [ Layer size plot | Cross section ]         ■ Layer height  — Total so far ┐
    │ bars: each layer's height · line: total thickness so far                  │
    │ dashed: boundary layer · dotted: next cell size (labels on the right)     │
    └───────────────────────────────────────────────────────────────────────────┘
    ✓ / ⚠ checks            (every number is in the sidebar's Values pop-ups)

The plot takes the full width, under tabs; drawn like the rest of the app. Second tab
"Cross section" (section_cut.py): the section plane's cut, in 2D, with the inflation
layers estimated on the walls. The tab, Flip side, the flow arrow and the cross-section
zoom are remembered per file (get_state / set_state).
Everything is drawn with QPainter in the app's colours (light and dark).
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QAction, QActionGroup, QColor, QFont, QPainter, QPainterPath, QPalette, QPen,
)
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea, QSizePolicy,
    QStackedWidget, QToolTip, QVBoxLayout, QWidget,
)

from meshviewer.gui.pages.section_cut import SectionLegend, SectionView
from meshviewer.gui.widgets import Capsule
from meshviewer.core.units import length_unit, show_length, nice_step

RED, GREEN = "#ff453a", "#30b350"                  # status colours (tiles, checks)
VISCOUS = 5.0                                      # y+ where the viscous sublayer ends


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
        self.caption = QLabel(caption)
        self.caption.setObjectName("Caption")
        lay.addWidget(self.caption)
        row = QHBoxLayout()                    # big value, small note beside it
        row.setSpacing(8)
        self.value = QLabel("—")
        self.value.setObjectName("TileValue")
        self.value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        row.addWidget(self.value, 0, Qt.AlignBottom)
        self.side = QLabel("")
        self.side.setObjectName("SmallNote")
        row.addWidget(self.side, 0, Qt.AlignBottom)
        row.addStretch(1)
        lay.addLayout(row)
        self.note = QLabel("")
        self.note.setObjectName("InfoLine")
        lay.addWidget(self.note)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set(self, value, note="", state=None, side=""):
        self.value.setText(value)
        self.note.setText(note)
        self.side.setText(side)
        color = {"ok": GREEN, "warn": "#ff9f0a", "bad": RED}.get(state, state)
        self.value.setStyleSheet(f"color: {color};" if color else "")


# ---- the plot (drawn like the rest of the app) ----------------------------------
# Series colours: the reference palette's first two slots (light / dark), validated
# for colour-blind separation; labels stay in the text colours.
SERIES = {"total": ("#2a78d6", "#3987e5"), "layer": ("#eb6834", "#d95926")}


def series_color(widget, key):
    return QColor(SERIES[key][1 if _dark(widget) else 0])


class _Plot(QWidget):
    """what the two plots share, so they look and read the same — horizontal
    grid, y ticks, a y-axis title along the axis, an x-axis title, reference lines
    labelled at the right (name, then value), an end label, hover crosshair."""
    PAD_L, PAD_R, PAD_T, PAD_B = 76, 132, 14, 40
    EMPTY = "Fill in the CFD mode inputs in the sidebar"

    def __init__(self, parent=None):
        super().__init__(parent)
        self.r = None
        self.hover = None
        self.setMinimumHeight(320)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMouseTracking(True)

    def _ranges(self):                          # ((x0, x1), (y0, y1))
        raise NotImplementedError

    def _px(self, x, y):
        (x0, x1), (y0, y1) = self._ranges()
        w = self.width() - self.PAD_L - self.PAD_R
        h = self.height() - self.PAD_T - self.PAD_B
        return QPointF(self.PAD_L + (x - x0) / (x1 - x0) * w,
                       self.PAD_T + (1 - (y - y0) / (y1 - y0)) * h)

    def _begin(self):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pal = self.palette()
        self._text = pal.color(QPalette.WindowText)
        self._muted = pal.color(QPalette.PlaceholderText)
        self._grid = QColor(self._text)
        self._grid.setAlphaF(0.07)
        font = QFont(p.font())
        font.setPixelSize(11)
        p.setFont(font)
        self._labels = []                       # y of the reference labels drawn
        return p

    def _frame(self, p, y_title, x_title, y_label, x_ticks):
        """Grid, ticks and the two axis titles. y_label(v) / x_ticks [(x, text)]."""
        (x0, x1), (y0, y1) = self._ranges()
        left, right = self.PAD_L, self.width() - self.PAD_R
        base = self._px(x0, y0).y()
        top = self._px(x0, y1).y()
        step = nice_step(y1 - y0, 5)
        gy = y0
        while gy <= y1 + 1e-12:
            y = self._px(x0, gy).y()
            p.setPen(QPen(self._grid, 1))
            p.drawLine(QPointF(left, y), QPointF(right, y))
            p.setPen(self._muted)
            p.drawText(QRectF(24, y - 7, left - 34, 14), Qt.AlignRight | Qt.AlignVCenter,
                       y_label(gy))
            gy += step
        for x, text in x_ticks:
            q = self._px(x, y0).x()
            p.drawText(QRectF(q - 30, base + 6, 60, 14), Qt.AlignHCenter, text)
        p.setPen(self._text)                    # axis titles, text colour
        p.drawText(QRectF(left, self.height() - 16, right - left, 14), Qt.AlignHCenter, x_title)
        p.save()
        p.translate(12, (top + base) / 2)
        p.rotate(-90)
        p.drawText(QRectF(-(base - top) / 2, -7, base - top, 14), Qt.AlignCenter, y_title)
        p.restore()

    def _ref(self, p, y, style, title, sub):
        """A reference line across the plot, labelled at the right."""
        left, right = self.PAD_L, self.width() - self.PAD_R
        yy = self._px(self._ranges()[0][0], y).y()
        self._labels.append(yy)
        pen = QPen(self._muted, 1.2)
        pen.setStyle(style)
        p.setPen(pen)
        p.drawLine(QPointF(left, yy), QPointF(right, yy))
        p.setPen(self._text)
        p.drawText(QRectF(right + 8, yy - 15, self.PAD_R - 8, 14), Qt.AlignLeft | Qt.AlignBottom,
                   title)
        p.setPen(self._muted)
        p.drawText(QRectF(right + 8, yy - 1, self.PAD_R - 8, 14), Qt.AlignLeft | Qt.AlignTop, sub)

    def _line(self, p, pts, c):
        """The series line with a soft area under it."""
        base = self._px(self._ranges()[0][0], self._ranges()[1][0]).y()
        line = QPainterPath(pts[0])
        for q in pts[1:]:
            line.lineTo(q)
        area = QPainterPath(line)
        area.lineTo(pts[-1].x(), base)
        area.lineTo(pts[0].x(), base)
        area.closeSubpath()
        fill = QColor(c)
        fill.setAlphaF(0.10)
        p.fillPath(area, fill)
        p.setPen(QPen(c, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        p.drawPath(line)

    def _end_label(self, p, q, text):
        """Label at the end of the line, moved up or down off the reference labels
        (each takes 30 px: name above its line, value below)."""
        y = q.y()
        for _ in range(4):
            near = [ly for ly in self._labels if ly - 24 < y < ly + 24]
            if not near:
                break
            y = near[0] - 24 if y <= near[0] else near[0] + 24
        p.setPen(self._text)
        p.drawText(QRectF(self.width() - self.PAD_R + 8, y - 7, self.PAD_R - 8, 14),
                   Qt.AlignLeft | Qt.AlignVCenter, text)

    def _hover_at(self, p, x, q, c):
        cross = QColor(self._text)
        cross.setAlphaF(0.25)
        p.setPen(QPen(cross, 1))
        (x0, _), (y0, y1) = self._ranges()
        p.drawLine(QPointF(x, self._px(x0, y1).y()), QPointF(x, self._px(x0, y0).y()))
        p.setPen(QPen(self.palette().color(QPalette.Window), 2))
        p.setBrush(c)
        p.drawEllipse(q, 4.5, 4.5)

    def _empty(self, p, text=None):
        p.setPen(self._muted)
        p.drawText(self.rect(), Qt.AlignCenter, text or self.EMPTY)

    def leaveEvent(self, _):
        self.hover = None
        QToolTip.hideText()
        self.update()


class InflationPlot(_Plot):
    """Layer size plot: one bar per layer (its height), a line for the total
    thickness of the layers so far, and two reference lines — the boundary
    layer thickness and the next cell size. Hover a layer for its numbers."""

    def set_result(self, r):
        self.r = r if r and r.get("ok") else None
        self.update()

    def _ranges(self):
        r = self.r
        top = max(r["y_tot"], r["d99"], r["y_des"]) * 1.08
        return (0.0, r["N"] + 0.5), (0.0, top)

    def paintEvent(self, _):
        p = self._begin()
        if self.r is None:
            return self._empty(p)
        r = self.r
        (_, _), (_, y1) = self._ranges()
        f, unit = length_unit(y1)
        n = r["N"]
        xstep = max(1, int(nice_step(n, 10)))
        ticks = [(k, str(k)) for k in [1] + list(range(xstep, n + 1, xstep))]
        self._frame(p, f"Height ({unit})", "Layer number (1 = at the wall)",
                    lambda v: f"{v * f:.3g}", ticks)
        base = self._px(0, 0).y()
        # one bar per layer: its height (4 px rounded top, 2 px gap)
        slot = (self._px(1, 0).x() - self._px(0, 0).x())
        bw = max(1.0, slot - 2.0)
        layer_c = series_color(self, "layer")
        for i, h in enumerate(r["heights"], start=1):
            c = QColor(layer_c)
            if self.hover is not None and i != self.hover:
                c.setAlphaF(0.45)
            top = self._px(i, h).y()
            rect = QRectF(self._px(i, 0).x() - bw / 2, top, bw, max(base - top, 0.5))
            path = QPainterPath()
            rad = min(4.0, bw / 2, rect.height())
            path.addRoundedRect(rect.adjusted(0, 0, 0, rad), rad, rad)   # flat at the base
            p.save()
            p.setClipRect(QRectF(rect.left() - 1, rect.top() - 1, rect.width() + 2,
                                 rect.height() + 1))
            p.fillPath(path, c)
            p.restore()
        total_c = series_color(self, "total")
        pts = [self._px(i, t) for i, t in enumerate(r["total"])]
        self._line(p, pts, total_c)
        self._ref(p, r["d99"], Qt.DashLine, "Pipe radius" if r.get("internal") else
                  "Boundary layer", show_length(r["d99"]))
        self._ref(p, r["y_des"], Qt.DotLine, "Next cell size", show_length(r["y_des"]))
        self._end_label(p, pts[-1], f"Total {show_length(r['y_tot'])}")
        if self.hover is not None:
            self._hover_at(p, self._px(self.hover, 0).x(), pts[self.hover], total_c)

    def _layer_at(self, e):
        if self.r is None:
            return None
        (x0, x1), _ = self._ranges()
        w = self.width() - self.PAD_L - self.PAD_R
        x = x0 + (e.position().x() - self.PAD_L) / max(w, 1) * (x1 - x0)
        i = int(round(x))
        return i if 1 <= i <= self.r["N"] else None

    def mouseMoveEvent(self, e):
        i = self._layer_at(e)
        if i != self.hover:
            self.hover = i
            self.update()
        if i is None:
            QToolTip.hideText()
            return
        r = self.r
        QToolTip.showText(e.globalPosition().toPoint(),
                          f"Layer {i}\nLayer height {show_length(r['heights'][i - 1])}\n"
                          f"Total so far {show_length(r['total'][i])}", self)


class _Legend(QWidget):
    """Two series: a swatch + name each, in the text colour."""

    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.items = items                     # [(series key, "bar" | "line", label)]
        self.setFixedHeight(20)
        fm = self.fontMetrics()
        self.setMinimumWidth(sum(fm.horizontalAdvance(t) + 40 for *_, t in items))

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        x = 0.0
        fm = p.fontMetrics()
        for key, kind, label in self.items:
            c = series_color(self, key)
            if kind == "bar":
                p.setPen(Qt.NoPen)
                p.setBrush(c)
                p.drawRoundedRect(QRectF(x, 5, 10, 10), 2, 2)
            else:
                p.setPen(QPen(c, 2, Qt.SolidLine, Qt.RoundCap))
                p.drawLine(QPointF(x, 10), QPointF(x + 12, 10))
            p.setPen(self.palette().color(QPalette.WindowText))
            p.drawText(QRectF(x + 17, 0, 400, 20), Qt.AlignVCenter | Qt.AlignLeft, label)
            x += 17 + fm.horizontalAdvance(label) + 20


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
                ("y_calc", "First layer height for target y+", "y_min = y+ μ / (ρ u*)"),
                ("yplus", "Estimated y+",
                 "y+ of the first layer, flat-plate estimate over the length L"),
                ("d99", "Boundary layer thickness", "δ99, flat plate: 0.38 L / Re^⅕ (turbulent) "
                                                    "or 4.91 L / √Re (laminar); supersonic ÷ rc^⅑"),
                ("y_tot", "Total thickness of the layers",
                 "Σ y_min Gⁿ, n = 0 … N − 1  (should be more than the boundary layer)"),
                ("y_max", "Max layer height",
                 "y_max = y_min G^(N−1)  (the next cell should be about 2 × this)"))):
            t = _Tile(caption, tip)
            tiles.addWidget(t, i // 3, i % 3)
            self.tiles[key] = t
        lay.addLayout(tiles)

        # a card with tabs; the plot takes the whole width
        card = QFrame()
        card.setObjectName("ResultCard")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(14, 10, 14, 12)
        cl.setSpacing(8)
        bar = QHBoxLayout()
        group = QActionGroup(self)
        group.setExclusive(True)
        self.tabs = {}
        for key, text in (("plot", "Layer size plot"), ("section", "Cross section")):
            a = QAction(text, self)
            a.setCheckable(True)
            a.triggered.connect(lambda _=False, k=key: self.show_tab(k))
            group.addAction(a)
            self.tabs[key] = a
        bar.addWidget(Capsule(list(self.tabs.values()), name="Segmented"))
        bar.addStretch(1)
        self.legend = _Legend([("layer", "bar", "Layer height"),
                               ("total", "line", "Total thickness so far")])
        bar.addWidget(self.legend)
        self.section_legend = SectionLegend()
        bar.addWidget(self.section_legend)
        # Cross section — Flip side + Fit view, capsule buttons like the tabs
        self.section_bar = QWidget()
        sb = QHBoxLayout(self.section_bar)
        sb.setContentsMargins(12, 0, 0, 0)
        sb.setSpacing(8)
        self.flip_action = QAction("Flip side", self)
        self.flip_action.setCheckable(True)
        self.flip_action.setToolTip("Put the layers on the other side of the walls\n"
                                    "(e.g. internal flow in a duct, or a wall facing the wrong way)")
        self.fit_action = QAction("Fit view", self)
        self.fit_action.setToolTip("Show the whole cut again (or double-click the view)")
        sb.addWidget(Capsule([self.flip_action], name="Segmented"))
        sb.addWidget(Capsule([self.fit_action], name="Segmented"))
        bar.addWidget(self.section_bar)
        cl.addLayout(bar)
        self.views = QStackedWidget()
        self.plot = InflationPlot()
        self.views.addWidget(self.plot)
        self.section = SectionView()                   # follows the section plane
        self.views.addWidget(self.section)
        self.flip_action.toggled.connect(self.section.set_flip)
        self.fit_action.triggered.connect(self.section.fit)
        self.section_legend.toggled.connect(self.section.set_show)
        cl.addWidget(self.views, 1)
        lay.addWidget(card, 1)
        self.show_tab("plot")

        self.checks = QLabel("")
        self.checks.setObjectName("ValueLabel")
        self.checks.setWordWrap(True)
        self.checks.setTextFormat(Qt.RichText)
        lay.addWidget(self.checks)

    def show_tab(self, key):
        self.tabs[key].setChecked(True)
        self.views.setCurrentWidget({"plot": self.plot, "section": self.section}[key])
        self.legend.setVisible(key == "plot")
        self.section_legend.setVisible(key == "section")
        self.section_bar.setVisible(key == "section")

    def current_tab(self):
        return next((k for k, a in self.tabs.items() if a.isChecked()), "plot")

    # ---- remembered per file -------------------------------------------------------
    def get_state(self):
        sec = self.section
        return {"tab": self.current_tab(), "flip": self.flip_action.isChecked(),
                "flow": bool(sec.show.get("flow")), "view": sec.view_state()}

    def set_state(self, st):
        st = st or {}
        self.flip_action.setChecked(bool(st.get("flip", False)))
        on = bool(st.get("flow", False))
        self.section_legend.set_on("flow", on)
        self.section.set_show("flow", on)
        self.section.restore_view(st.get("view"))
        self.show_tab(st.get("tab") if st.get("tab") in self.tabs else "plot")

    def set_result(self, r):
        self.plot.set_result(r)
        self.section.set_result(r)
        if not r or not r.get("ok"):
            for t in self.tiles.values():
                t.set("—")
            self.regime.setText("")
            self.checks.setText("Fill in the inputs in the sidebar (CFD mode).")
            return
        self.regime.setText(("Turbulent" if r["turbulent"] else "Laminar") + " · " +
                            ("Supersonic" if r["supersonic"] else "Subsonic"))
        if r.get("walls"):                       # which walls, which length
            self.regime.setText(self.regime.text() + f" · {r['walls']} · "
                                f"{'D' if r.get('internal') else 'L'} {r['L']:.4g} m")
        if r.get("internal"):
            self.regime.setText("Internal · " + self.regime.text())
        self.tiles["re"].set(f"{r['Re']:.3g}", "turbulent" if r["turbulent"] else "laminar")
        self.tiles["y_calc"].set(show_length(r["y_calc"]), f"{r['y_calc']:.3g} m")
        off = abs(r["yplus_est"] - r["target"]) / max(r["target"], 1e-12)
        self.tiles["yplus"].set(f"{r['yplus_est']:.3g}", f"target {r['target']:g}",
                                "ok" if off < 0.2 else "warn")
        self.tiles["d99"].caption.setText("Pipe radius" if r.get("internal")
                                          else "Boundary layer thickness")
        self.tiles["d99"].set(show_length(r["d99"]), "developed flow: the boundary layer fills it"
                              if r.get("internal") else f"{r['d99']:.3g} m")
        self.tiles["y_tot"].set(show_length(r["y_tot"]), f"{r['N']} layers × G {r['G']:g}",
                                "ok" if r["covers_bl"] else "bad")
        self.tiles["y_max"].set(show_length(r["y_max"]),
                                f"next cell {show_length(r['y_des'])}",
                                "ok" if r["smooth"] else "warn")
        ok, warn = f"<span style='color:{GREEN}'>✓</span>", "<span style='color:#ff9f0a'>⚠</span>"
        if r.get("internal"):                    # the layers must fit in the pipe
            first = (f"{ok if r['covers_bl'] else warn} The layers ({show_length(r['y_tot'])} "
                     f"in total) take {r['y_tot'] / r['d99'] * 100:.0f} % of the pipe radius "
                     f"({show_length(r['d99'])})")
        else:
            first = (f"{ok if r['covers_bl'] else warn} The layers ({show_length(r['y_tot'])} "
                     f"in total) {'are thicker than' if r['covers_bl'] else 'are thinner than'} "
                     f"the boundary layer ({show_length(r['d99'])})")
        lines = [
            first,
            f"{ok if r['smooth'] else warn} Step to the mesh: the next cell "
            f"({show_length(r['y_des'])}) is {r['y_des'] / r['y_max']:.2g} × the max layer "
            f"height (about 2 × is smooth)",
        ]
        lines.append(f"{ok if off < 0.2 else warn} Estimated y+ {r['yplus_est']:.3g} for a "
                     f"target of {r['target']:g}")
        self.checks.setText("<br>".join(lines))

