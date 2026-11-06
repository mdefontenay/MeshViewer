"""Toolbar / sidebar icons, drawn as vectors (SF Symbols–like line style).

They are painted on demand with the current text colour, so they follow
light/dark mode automatically and stay sharp on Retina screens.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRect, QRectF, QSize, Qt
from PySide6.QtGui import (
    QColor, QGuiApplication, QIcon, QIconEngine, QPainter, QPainterPath, QPalette, QPen, QPixmap,
)

GRID = 18.0          # icons are drawn on an 18 × 18 grid
_engines = []        # keep Python engines alive while Qt uses them


def _line(p, *pts):
    path = QPainterPath(QPointF(*pts[0]))
    for pt in pts[1:]:
        path.lineTo(QPointF(*pt))
    p.drawPath(path)


def _draw_sidebar(p):
    p.drawRoundedRect(QRectF(2, 3.5, 14, 11), 2.6, 2.6)
    _line(p, (7, 3.5), (7, 14.5))


def _draw_fit(p):
    for a, b, c in (((2.5, 6.5), (2.5, 2.5), (6.5, 2.5)), ((11.5, 2.5), (15.5, 2.5), (15.5, 6.5)),
                    ((15.5, 11.5), (15.5, 15.5), (11.5, 15.5)), ((6.5, 15.5), (2.5, 15.5), (2.5, 11.5))):
        _line(p, a, b, c)


def _draw_cube(p):
    _line(p, (9, 2), (15.2, 5.5), (15.2, 12.5), (9, 16), (2.8, 12.5), (2.8, 5.5), (9, 2))
    _line(p, (2.8, 5.5), (9, 9), (15.2, 5.5))
    _line(p, (9, 9), (9, 16))


def _draw_section(p):
    _draw_cube(p)
    fill = QColor(p.pen().color())
    fill.setAlphaF(0.35)
    path = QPainterPath(QPointF(2.8, 9))
    for pt in ((9, 12.5), (15.2, 9), (9, 5.5)):
        path.lineTo(QPointF(*pt))
    path.closeSubpath()
    p.fillPath(path, fill)
    _line(p, (2.8, 9), (9, 12.5), (15.2, 9))


def _draw_camera(p):
    p.drawRoundedRect(QRectF(2, 5.5, 14, 9.5), 2.2, 2.2)
    _line(p, (6, 5.5), (7.2, 3.5), (10.8, 3.5), (12, 5.5))
    p.drawEllipse(QPointF(9, 10.2), 2.7, 2.7)


def _draw_search(p):
    p.drawEllipse(QPointF(7.5, 7.5), 4.6, 4.6)
    _line(p, (11, 11), (15, 15))


def _draw_ruler(p):
    p.save()
    p.translate(9, 9)
    p.rotate(-45)
    p.drawRoundedRect(QRectF(-8, -3, 16, 6), 1.2, 1.2)
    for i, x in enumerate((-5, -2.5, 0, 2.5, 5)):
        _line(p, (x, -3), (x, -0.5 if i % 2 else 0.6))
    p.restore()


def _draw_nounit(p):
    p.drawEllipse(QPointF(9, 9), 5.6, 5.6)
    _line(p, (5, 13), (13, 5))                 # 45° line through the circle


def _draw_appearance(p):
    """Three sliders (like SF Symbols "slider.horizontal.3"): many settings, not
    just light / dark."""
    r = 1.9
    for y, knob in ((4.5, 11.5), (9.0, 6.0), (13.5, 10.0)):
        _line(p, (2.5, y), (knob - r - 0.6, y))
        _line(p, (knob + r + 0.6, y), (15.5, y))
        p.drawEllipse(QPointF(knob, y), r, r)


def _draw_parallel(p):
    """NEW (v2.22): parallel projection — a box whose edges stay parallel
    (front and back faces the same size)."""
    p.drawRect(QRectF(2.5, 6.0, 9.0, 9.0))
    _line(p, (6.5, 2.5), (15.5, 2.5), (15.5, 11.5))
    for a, b in (((2.5, 6.0), (6.5, 2.5)), ((11.5, 6.0), (15.5, 2.5)), ((11.5, 15.0), (15.5, 11.5))):
        _line(p, a, b)


def _draw_export(p):
    """NEW (v2.23): export — tray with an arrow going out (like macOS Share)."""
    _line(p, (6.0, 7.5), (4.0, 7.5), (4.0, 16.0), (14.0, 16.0), (14.0, 7.5), (12.0, 7.5))
    _line(p, (9.0, 11.0), (9.0, 2.0))
    _line(p, (6.2, 4.8), (9.0, 2.0), (11.8, 4.8))


# ---- NEW (v2.28): what-is-shown toggles in the toolbar -----------------------------
def _draw_mesh_edges(p):
    """A small triangle mesh: square, 2 × 2 cells, one diagonal each."""
    p.drawRect(QRectF(2.5, 2.5, 13, 13))
    _line(p, (9, 2.5), (9, 15.5))
    _line(p, (2.5, 9), (15.5, 9))
    _line(p, (2.5, 9), (9, 2.5))
    _line(p, (9, 9), (15.5, 2.5))
    _line(p, (2.5, 15.5), (9, 9))
    _line(p, (9, 15.5), (15.5, 9))


def _draw_feature_edges(p):
    """Outline of a cylinder: just the sharp edges and the silhouette."""
    p.drawEllipse(QRectF(3, 2.5, 12, 4.4))
    _line(p, (3, 4.7), (3, 13.3))
    _line(p, (15, 4.7), (15, 13.3))
    path = QPainterPath(QPointF(3, 13.3))
    path.arcTo(QRectF(3, 11.1, 12, 4.4), 180, 180)
    p.drawPath(path)


def _draw_faces(p):
    """A cube with shaded faces (v2.29: Faces on / off, was "Edges only")."""
    c = QColor(p.pen().color())
    for alpha, pts in ((0.55, ((9, 2), (15.2, 5.5), (9, 9), (2.8, 5.5))),
                       (0.30, ((2.8, 5.5), (9, 9), (9, 16), (2.8, 12.5))),
                       (0.15, ((9, 9), (15.2, 5.5), (15.2, 12.5), (9, 16)))):
        path = QPainterPath(QPointF(*pts[0]))
        for pt in pts[1:]:
            path.lineTo(QPointF(*pt))
        path.closeSubpath()
        c.setAlphaF(alpha)
        p.fillPath(path, c)
    _draw_cube(p)


def _draw_axes(p):
    """Axis frame with tick marks (the numbers)."""
    _line(p, (3.5, 2), (3.5, 14.5), (16, 14.5))
    for y in (5, 8, 11):
        _line(p, (3.5, y), (5.5, y))
    for x in (7, 10, 13):
        _line(p, (x, 14.5), (x, 12.5))


def _draw_grid(p):
    p.drawRoundedRect(QRectF(2.5, 2.5, 13, 13), 1.5, 1.5)
    for v in (6.8, 11.2):
        _line(p, (v, 2.5), (v, 15.5))
        _line(p, (2.5, v), (15.5, v))


def _draw_bbox(p):
    """Dashed box with solid corner handles."""
    pen = QPen(p.pen())
    pen.setDashPattern([1.4, 1.6])
    p.save()
    p.setPen(pen)
    p.drawRect(QRectF(3.5, 3.5, 11, 11))
    p.restore()
    for x, y in ((3.5, 3.5), (14.5, 3.5), (3.5, 14.5), (14.5, 14.5)):
        p.drawRect(QRectF(x - 1.3, y - 1.3, 2.6, 2.6))


def _draw_origin(p):
    """A dot with X / Y / Z arrows (the origin marker)."""
    o = (6.5, 11.5)
    _line(p, o, (15.5, 11.5))
    _line(p, (13.3, 9.7), (15.5, 11.5), (13.3, 13.3))
    _line(p, o, (6.5, 2.5))
    _line(p, (4.7, 4.7), (6.5, 2.5), (8.3, 4.7))
    _line(p, o, (2.5, 15.5))
    fill = QColor(p.pen().color())
    p.save()
    p.setBrush(fill)
    p.drawEllipse(QPointF(*o), 1.7, 1.7)
    p.restore()


DRAWINGS = {
    "mesh_edges": _draw_mesh_edges,
    "feature_edges": _draw_feature_edges,
    "faces": _draw_faces,
    "axes": _draw_axes,
    "grid": _draw_grid,
    "bbox": _draw_bbox,
    "origin": _draw_origin,
    "export": _draw_export,
    "parallel": _draw_parallel,
    "appearance": _draw_appearance,
    "nounit": _draw_nounit,
    "ruler": _draw_ruler,
    "sidebar": _draw_sidebar,
    "fit": _draw_fit,
    "iso": _draw_cube,
    "section": _draw_section,
    "camera": _draw_camera,
    "search": _draw_search,
}


class _Engine(QIconEngine):
    def __init__(self, draw, role=QPalette.WindowText):
        super().__init__()
        self.draw = draw
        self.role = role

    def paint(self, p, rect, mode, state):
        pal = QGuiApplication.palette()
        group = QPalette.Disabled if mode == QIcon.Disabled else QPalette.Active
        color = pal.color(group, self.role)
        if state == QIcon.On and mode != QIcon.Disabled:
            color = QColor("white")      # v2.28: checked toggles sit on the accent colour
        p.save()
        p.setRenderHint(QPainter.Antialiasing)
        p.translate(rect.x(), rect.y())
        p.scale(rect.width() / GRID, rect.height() / GRID)
        pen = QPen(color, 1.5)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        self.draw(p)
        p.restore()

    def scaledPixmap(self, size, mode, state, scale):
        pm = QPixmap(QSize(round(size.width() * scale), round(size.height() * scale)))
        pm.setDevicePixelRatio(scale)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        self.paint(p, QRect(0, 0, size.width(), size.height()), mode, state)
        p.end()
        return pm

    def pixmap(self, size, mode, state):
        return self.scaledPixmap(size, mode, state, 1.0)

    def clone(self):
        e = _Engine(self.draw, self.role)
        _engines.append(e)
        return e


def icon(name, role=QPalette.WindowText) -> QIcon:
    e = _Engine(DRAWINGS[name], role)
    _engines.append(e)
    return QIcon(e)
