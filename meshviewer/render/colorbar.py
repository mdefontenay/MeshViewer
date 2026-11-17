"""Contours ▸ the color bar over the 3D view: what the colors on the boundaries mean.

    Pressure p (kPa)        the field and its unit (can be hidden)
    ┌──┐ ─ 1.6              ticks and their values on the right (core/fields.py `ticks`):
    │  │ ─ 1.2              a number that would run into its neighbor is left out, the
    │  │ ─ 0.81             two ends never
    │  │ ─ 0.42             smooth, or in bands between the ticks — the same colors as
    └──┘ ─ 0.02             the boundaries (core/fields.py ramp_table)

Its height and width: percentages (`SIZE_RANGE`) of `BASE`; the text keeps its size. Text
and lines: "auto" (for the background), "white" or "black" (`TEXT_COLORS`).

Text sizes: VTK grows a font by the window's DPI / 72, and the view's DPI is set (144 on a
Retina screen) only once it is first drawn: the view's fonts are given in points, so they
come out right whenever the DPI arrives (a screenshot's window stays at 72: in pixels).

Anchored at the top-left of the view (`offset`, in points from that corner); it can be
dragged elsewhere (gui/viewport.py asks `hit`, then `drag`). Text and lines are light on
a dark background, dark on a light one (`scene._dark`, render/appearance.py). Drawn by
plain VTK 2D actors, again for Save Screenshot at its scale (`add_to`).
"""
from __future__ import annotations

import numpy as np
from vtkmodules.vtkCommonCore import vtkPoints, vtkUnsignedCharArray
from vtkmodules.vtkCommonDataModel import vtkCellArray, vtkPolyData
from vtkmodules.vtkRenderingCore import (
    vtkActor2D, vtkCoordinate, vtkPolyDataMapper2D, vtkTextActor,
)

from meshviewer.core.fields import band_colors, ramp_table
from meshviewer.render.style import rgb

BASE = (190, 14, 11)            # bar height, bar width at 100 %, font size (points)
SIZE_RANGE = (60, 160)          # Height and Width, percent
TEXT_COLORS = ("auto", "white", "black")
MARGIN = 16                     # from the view's top-left corner (points), until dragged
TICK = 4                        # tick mark length (points)
GAP = 5                         # tick mark to its number (points)
TEXT = {True: "#f2f2f7", False: "#1c1c1e"}       # on a dark / light background


def tick_label(v):
    """A tick's number: 3 significant digits, whole numbers from 1000 to 99999 written out
    (1000, not 1e+03), powers of ten outside."""
    a = abs(v)
    if a == 0:
        return "0"
    if a < 1e-3 or a >= 1e5:
        return f"{v:.2e}"
    return f"{v:.3g}" if a < 1e3 else f"{v:.0f}"


def _poly(points, polys=(), lines=(), colors=None):
    pts = vtkPoints()
    for x, y in points:
        pts.InsertNextPoint(float(x), float(y), 0.0)
    out = vtkPolyData()
    out.SetPoints(pts)
    for cells, setter in ((polys, out.SetPolys), (lines, out.SetLines)):
        if cells:
            arr = vtkCellArray()
            for c in cells:
                arr.InsertNextCell(len(c))
                for i in c:
                    arr.InsertCellPoint(int(i))
            setter(arr)
    if colors is not None:
        rgb_arr = vtkUnsignedCharArray()
        rgb_arr.SetNumberOfComponents(3)
        rgb_arr.SetName("rgb")
        for c in np.asarray(colors, dtype=np.uint8):
            rgb_arr.InsertNextTuple3(*map(int, c))
        out.GetPointData().SetScalars(rgb_arr)
    return out


def _place(actor, anchor, x, y):
    """Put a 2D actor `x`, `y` display pixels from the anchor (y up)."""
    c = actor.GetPositionCoordinate()
    c.SetCoordinateSystemToDisplay()
    c.SetReferenceCoordinate(anchor)
    c.SetValue(float(x), float(y))


def _text(text, size_px, color, anchor, x, y, valign="center"):
    t = vtkTextActor()
    t.SetInput(text)
    t.SetTextScaleModeToNone()
    prop = t.GetTextProperty()
    prop.SetFontSize(max(1, int(round(size_px))))
    prop.SetColor(rgb(color))
    prop.SetFontFamilyToArial()
    prop.SetJustificationToLeft()
    {"center": prop.SetVerticalJustificationToCentered,
     "top": prop.SetVerticalJustificationToTop}[valign]()
    t.PickableOff()
    _place(t, anchor, x, y)
    return t


class ColorBar:
    def __init__(self, scene):
        self.scene = scene
        self.p = scene.p
        self.spec = None            # what is shown (`show`'s arguments) or None
        self.offset = (MARGIN, MARGIN)
        self.on_moved = None        # called once a drag ends (the panel saves the place)
        self.labeled = []           # the tick values written (a crowded one is left out)
        self._actors = []
        self._anchor = None         # the top-left corner of the bar's box, in the view
        self._box = (0.0, 0.0)      # its width and height (pixels)
        self.p.overlay = self       # gui/viewport.py: dragged with the mouse

    # ---- what the Contours tool sets ---------------------------------------------------------
    def show(self, stops, lo, hi, ticks, title="", smooth=True, height=100, width=100,
             text="auto"):
        """ticks: [(position 0…1 up the bar, value)] (core/fields.py `ticks`); smooth
        False: bands between them; title "": none; height, width: percent of BASE;
        text: "auto" | "white" | "black"."""
        clip = lambda v: float(min(max(v, SIZE_RANGE[0]), SIZE_RANGE[1]))   # noqa: E731
        self.spec = dict(stops=tuple(stops), lo=float(lo), hi=float(hi),
                         ticks=[(float(a), float(b)) for a, b in ticks], title=title,
                         smooth=bool(smooth), height=clip(height), width=clip(width),
                         text=text if text in TEXT_COLORS else "auto")
        self._rebuild()

    def hide(self):
        if self.spec is None and not self._actors:
            return
        self.spec = None
        self._rebuild()

    @property
    def shown(self):
        return self.spec is not None

    @property
    def edges(self):
        """The band borders (0…1) when stepped, else None: the boundaries use the same."""
        if self.spec is None or self.spec["smooth"]:
            return None
        return [pos for pos, _ in self.spec["ticks"]]

    def restyle(self):
        """The background changed (light ↔ dark): text and lines follow."""
        if self.spec is not None:
            self._rebuild()

    # ---- drawn in the view ---------------------------------------------------------------
    def _ratio(self):
        try:
            return float(self.p.devicePixelRatioF())          # Retina: 2 pixels per point
        except AttributeError:
            return 1.0

    def _rebuild(self):
        ren = self.p.renderer
        for a in self._actors:
            ren.RemoveViewProp(a)
        self._actors = []
        if self.spec is not None:
            self._actors, self._anchor, self._box = self._build(
                ren, self._ratio(), text_k=1.0)          # fonts in points (DPI follows)
            self._dpi = self._win_dpi(ren)
            for a in self._actors:
                ren.AddViewProp(a)
        self.p.render()

    @staticmethod
    def _win_dpi(ren):
        win = ren.GetRenderWindow()
        return float(win.GetDPI()) if win is not None else 72.0

    def ink(self, dark=None):
        """The text and lines' color: chosen, or for the background (`dark`, default
        the view's)."""
        choice = self.spec["text"] if self.spec else "auto"
        if choice == "white":
            return TEXT[True]
        if choice == "black":
            return TEXT[False]
        return TEXT[bool(getattr(self.scene, "_dark", False)) if dark is None else dark]

    def _build(self, ren, s, dark=None, text_k=None):
        """The actors for renderer `ren` at `s` pixels per point -> (actors, the anchor,
        (width, height) of the whole, pixels). dark: the background (default the view's);
        text_k: VTK font size per point of text (default: s, a window at 72 DPI)."""
        sp = self.spec
        bar_h = BASE[0] * s * sp["height"] / 100
        bar_w = BASE[1] * s * sp["width"] / 100
        font = BASE[2] * s                              # text: pixels
        tf = (s if text_k is None else text_k) / s      # pixels -> VTK font size
        ink = self.ink(dark)
        corner = vtkCoordinate()                            # the view's top-left
        corner.SetCoordinateSystemToNormalizedViewport()
        corner.SetValue(0.0, 1.0)
        anchor = vtkCoordinate()                            # the bar's: dragged
        anchor.SetCoordinateSystemToDisplay()
        anchor.SetReferenceCoordinate(corner)
        anchor.SetValue(self.offset[0] * s, -self.offset[1] * s)
        actors = []
        title_h = 0.0
        if sp["title"]:
            t = _text(sp["title"], font * 1.1 * tf, ink, anchor, 0, 0, valign="top")
            actors.append(t)
            title_h = font * 1.1 * 1.25 + 6 * s
        top, bottom = -title_h, -title_h - bar_h
        # the colors, bottom (lo) to top (hi)
        pts, cells, cols = [], [], []
        if sp["smooth"]:
            n = 96
            table = ramp_table(sp["stops"], None, n + 1)
            for i in range(n + 1):
                y = bottom + bar_h * i / n
                pts += [(0, y), (bar_w, y)]
                cols += [table[i], table[i]]
            cells = [(2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2) for i in range(n)]
        else:
            edges = [pos for pos, _ in sp["ticks"]]
            bands = band_colors(sp["stops"], len(edges) - 1).round()
            for i, (a, b) in enumerate(zip(edges[:-1], edges[1:])):
                y0, y1 = bottom + bar_h * a, bottom + bar_h * b
                k = len(pts)
                pts += [(0, y0), (bar_w, y0), (bar_w, y1), (0, y1)]
                cols += [bands[i]] * 4
                cells.append((k, k + 1, k + 2, k + 3))
        m = vtkPolyDataMapper2D()
        m.SetInputData(_poly(pts, polys=cells, colors=cols))
        m.SetColorModeToDirectScalars()
        m.ScalarVisibilityOn()
        bar = vtkActor2D()
        bar.SetMapper(m)
        bar.PickableOff()
        _place(bar, anchor, 0, 0)
        actors.append(bar)
        # the frame and the ticks, with their numbers
        pts = [(0, bottom), (bar_w, bottom), (bar_w, top), (0, top)]
        lines = [(0, 1, 2, 3, 0)]
        label_w = 0.0
        self.labeled = []                               # the values written (tests)
        for pos, value in self._labeled(sp["ticks"], bar_h, font):
            y = bottom + bar_h * pos
            t = _text(tick_label(value), font * tf, ink, anchor, bar_w + (TICK + GAP) * s, y)
            actors.append(t)
            self.labeled.append(value)
            label_w = max(label_w, self._width(t, ren, font))
        for pos, _ in sp["ticks"]:                     # every tick has its mark
            y = bottom + bar_h * pos
            k = len(pts)
            pts += [(bar_w, y), (bar_w + TICK * s, y)]
            lines.append((k, k + 1))
        m = vtkPolyDataMapper2D()
        m.SetInputData(_poly(pts, lines=lines))
        frame = vtkActor2D()
        frame.SetMapper(m)
        prop = frame.GetProperty()
        prop.SetColor(rgb(ink))
        prop.SetOpacity(0.7)
        prop.SetLineWidth(max(1.0, s))
        frame.PickableOff()
        _place(frame, anchor, 0, 0)
        actors.append(frame)
        width = bar_w + (TICK + GAP) * s + label_w
        if sp["title"]:
            width = max(width, self._width(actors[0], ren, font * 1.1))
        height = title_h + bar_h + font * 0.6           # half a number below the bar
        self._geom = (bar_w + (TICK + GAP) * s, title_h + bar_h + font * 0.6,
                      [a for a in actors if isinstance(a, vtkTextActor)], font)
        return actors, anchor, (width, height)

    def _box_now(self):
        """Its size in pixels, measured again once the view's DPI has changed (the text's
        width follows it)."""
        ren = self.p.renderer
        dpi = self._win_dpi(ren)
        if getattr(self, "_geom", None) is not None and dpi != getattr(self, "_dpi", dpi):
            left, height, texts, font = self._geom
            width = left
            for t in texts:
                bb = self._width(t, ren, font)
                width = max(width, (bb if t.GetInput() == (self.spec or {}).get("title")
                                    else left + bb))
            self._box, self._dpi = (width, height), dpi
        return self._box

    @staticmethod
    def _labeled(marks, bar_h, font):
        """The ticks whose number is written: both ends, then from the bottom up each one
        at least a line of text clear of the last written and of the top end."""
        if len(marks) < 2:
            return list(marks)
        gap = 1.15 * font / max(bar_h, 1e-9)            # a line of text, as a share of the bar
        top = marks[-1][0]
        out = [marks[0]]
        for m in marks[1:-1]:
            if m[0] - out[-1][0] >= gap and top - m[0] >= gap:
                out.append(m)
        return out + [marks[-1]]

    @staticmethod
    def _width(text_actor, ren, font):
        bb = [0.0] * 4
        try:
            text_actor.GetBoundingBox(ren, bb)
            return float(bb[1] - bb[0])
        except (TypeError, AttributeError):
            return 0.6 * font * len(text_actor.GetInput() or "")

    # ---- dragged (gui/viewport.py) -----------------------------------------------------
    def hit(self, x, y, pad=6):
        """Is display pixel (x, y) (from the bottom-left) on the bar or its text?"""
        if self.spec is None or self._anchor is None:
            return False
        ax, ay = self._anchor.GetComputedDoubleDisplayValue(self.p.renderer)[:2]
        w, h = self._box_now()
        pad *= self._ratio()
        return ax - pad <= x <= ax + w + pad and ay - h - pad <= y <= ay + pad

    def drag(self, dx, dy):
        """Move it by (dx, dy) display pixels (y up), kept inside the view."""
        s = self._ratio()
        width, height = self.p.renderer.GetSize()
        w, h = self._box_now()
        ox = min(max(self.offset[0] + dx / s, 0.0), max((width - w) / s, 0.0))
        oy = min(max(self.offset[1] - dy / s, 0.0), max((height - h) / s, 0.0))
        self.offset = (ox, oy)
        if self._anchor is not None:
            self._anchor.SetValue(ox * s, -oy * s)
            for a in self._actors:
                a.Modified()
        self.p.render()

    def drag_done(self):
        if self.on_moved is not None:
            self.on_moved()

    def set_offset(self, offset):
        """A remembered place (points from the top-left corner)."""
        try:
            ox, oy = (max(0.0, float(v)) for v in offset)
        except (TypeError, ValueError):
            ox, oy = MARGIN, MARGIN
        if (ox, oy) != tuple(self.offset):
            self.offset = (ox, oy)
            if self.spec is not None:
                self._rebuild()

    # ---- Save Screenshot as SVG ----------------------------------------------------------
    def svg(self, W, H, k, dark=None):
        """The bar as SVG shapes (rects, lines, text) for a picture W × H pixels at k ×
        the view's size — as the view draws it."""
        sp = self.spec
        if sp is None:
            return ""
        s = self._ratio() * k
        bar_h = BASE[0] * s * sp["height"] / 100
        bar_w = BASE[1] * s * sp["width"] / 100
        font = BASE[2] * s
        ink = self.ink(dark)
        x0, y0 = self.offset[0] * s, self.offset[1] * s
        out = []
        title_h = 0.0
        txt = 'font-family="Helvetica, Arial, sans-serif"'
        if sp["title"]:
            title = (sp["title"].replace("&", "&amp;").replace("<", "&lt;")
                     .replace(">", "&gt;"))
            out.append(f'<text x="{x0:.1f}" y="{y0 + font * 1.1:.1f}" {txt} '
                       f'font-size="{font * 1.1:.1f}" fill="{ink}">{title}</text>')
            title_h = font * 1.1 * 1.25 + 6 * s
        top = y0 + title_h                             # SVG: y down
        bottom = top + bar_h

        def at(pos):
            return bottom - bar_h * pos

        if sp["smooth"]:
            table = ramp_table(sp["stops"], None, 33)       # lo (bottom) to hi (top)
            stops = "".join('<stop offset="%.4f" stop-color="#%02x%02x%02x"/>'
                            % (i / 32, *(int(v) for v in c)) for i, c in enumerate(table))
            out.append('<defs><linearGradient id="colorbar" x1="0" y1="1" x2="0" y2="0">'
                       f'{stops}</linearGradient></defs>')
            out.append(f'<rect x="{x0:.1f}" y="{top:.1f}" width="{bar_w:.1f}" '
                       f'height="{bar_h:.1f}" fill="url(#colorbar)"/>')
        else:
            edges = [pos for pos, _ in sp["ticks"]]
            bands = band_colors(sp["stops"], len(edges) - 1).round()
            for c, (a, b) in zip(bands, zip(edges[:-1], edges[1:])):
                out.append(f'<rect x="{x0:.1f}" y="{at(b):.1f}" width="{bar_w:.1f}" '
                           f'height="{at(a) - at(b):.2f}" fill="#%02x%02x%02x"/>'
                           % tuple(int(v) for v in c))
        out.append(f'<rect x="{x0:.1f}" y="{top:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" '
                   f'fill="none" stroke="{ink}" stroke-opacity="0.7" '
                   f'stroke-width="{max(1.0, s):.1f}"/>')
        for pos, _ in sp["ticks"]:
            y = at(pos)
            out.append(f'<line x1="{x0 + bar_w:.1f}" y1="{y:.1f}" '
                       f'x2="{x0 + bar_w + TICK * s:.1f}" y2="{y:.1f}" stroke="{ink}" '
                       f'stroke-opacity="0.7" stroke-width="{max(1.0, s):.1f}"/>')
        for pos, value in self._labeled(sp["ticks"], bar_h, font):
            out.append(f'<text x="{x0 + bar_w + (TICK + GAP) * s:.1f}" y="{at(pos):.1f}" '
                       f'{txt} font-size="{font:.1f}" fill="{ink}" '
                       f'dominant-baseline="middle">{tick_label(value)}</text>')
        return "\n".join(out)

    # ---- Save Screenshot ---------------------------------------------------------------
    def add_to(self, ren, k, dark=None):
        """Drawn again on another renderer (the screenshot's), k × the view's size;
        dark: its background (a transparent picture is for a white page: False)."""
        if self.spec is None:
            return []
        actors, _, _ = self._build(ren, self._ratio() * k, dark)   # its window: 72 DPI
        for a in actors:
            ren.AddViewProp(a)
        return actors
