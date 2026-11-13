"""Toolbar / sidebar icons.

The app's own icons (Select ▾: part, nodes, edges, faces) are SVG files in icons/
(FILES), white on clear, recolored when drawn. On a Mac, the other icons are SF
Symbols asked from macOS itself when they are drawn (SF
below: icon name -> symbol name; browse the names in Apple's SF Symbols app). Nothing
of Apple's is stored in this project. Elsewhere, or if a symbol is missing (older
macOS, no PyObjC), the icon is drawn here as vectors in the same line style.

Both are painted on demand in the current text colour, so they follow light / dark
mode and stay sharp on Retina screens.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QPointF, QRect, QRectF, QSize, Qt
from PySide6.QtGui import (
    QColor, QGuiApplication, QIcon, QIconEngine, QImage, QPainter, QPainterPath, QPalette, QPen,
    QPixmap,
)

GRID = 18.0          # drawn icons use an 18 × 18 grid
_engines = []        # keep Python engines alive while Qt uses them
SF = {   # icon name -> SF Symbol
    "sidebar": "sidebar.left", "inspector": "sidebar.right", "fit": "viewfinder", "iso": "cube",
    "parallel": "perspective", "grid": "rectangle.split.3x3", "camera": "camera",
    "export": "square.and.arrow.up", "appearance": "slider.horizontal.3",
    "section": "square.3.layers.3d", "ruler": "ruler", "measure": "ruler",
    "info": "info.circle", "edit": "move.3d", "cfd": "wind", "cell_quality": "skew",
    "results": "waveform.path.ecg.text.page", "analysis": "wrench.adjustable", "search": "magnifyingglass",
    "mesh_quality": "dial.medium", "mesh_edges": "square.split.diagonal.2x2",
    "faces": "cube.fill", "plus": "plus.circle", "edit_unit": "square.and.pencil",
    "plots": "chart.xyaxis.line", "eye": "eye", "eye_off": "eye.slash",
    "advanced": "gearshape",
    "settings_general": "gearshape", "settings_appearance": "paintpalette",
    "settings_units": "ruler",
    "chevron_down": "chevron.down",        # pull-downs and pop-up menus
    "checkmark": "checkmark",              # what is on, in menus with icons
    "pencil": "pencil",                    # Edit Plane: the origin and normal
}
_sf_cache = {}


def _line(p, *pts):
    path = QPainterPath(QPointF(*pts[0]))
    for pt in pts[1:]:
        path.lineTo(QPointF(*pt))
    p.drawPath(path)


def _draw_sidebar(p):
    p.drawRoundedRect(QRectF(2, 3.5, 14, 11), 2.6, 2.6)
    _line(p, (7, 3.5), (7, 14.5))


def _draw_inspector(p):
    p.drawRoundedRect(QRectF(2, 3.5, 14, 11), 2.6, 2.6)
    _line(p, (11, 3.5), (11, 14.5))


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


def _draw_plots(p):
    """A curve on axes (like "chart.xyaxis.line")."""
    _line(p, (2.5, 2.5), (2.5, 15.5), (15.5, 15.5))
    path = QPainterPath(QPointF(4, 13.5))
    path.cubicTo(QPointF(9, 13.5), QPointF(8, 4), QPointF(15, 4))
    p.drawPath(path)


def _draw_eye(p):
    path = QPainterPath(QPointF(2, 9))
    path.quadTo(QPointF(9, 2), QPointF(16, 9))
    path.quadTo(QPointF(9, 16), QPointF(2, 9))
    p.drawPath(path)
    p.drawEllipse(QPointF(9, 9), 2.4, 2.4)


def _draw_eye_off(p):
    _draw_eye(p)
    _line(p, (3.5, 15), (14.5, 3))


def _draw_advanced(p):
    """A gear: a ring with six teeth."""
    import math
    p.drawEllipse(QPointF(9, 9), 2.3, 2.3)
    p.drawEllipse(QPointF(9, 9), 5.2, 5.2)
    for k in range(6):
        a = k * math.pi / 3
        _line(p, (9 + 5.2 * math.cos(a), 9 + 5.2 * math.sin(a)),
              (9 + 7.2 * math.cos(a), 9 + 7.2 * math.sin(a)))


def _draw_edit_unit(p):
    """A square with a pencil across its top-right corner (like "square.and.pencil")."""
    _line(p, (9, 3.5), (4.5, 3.5), (2.5, 5.5), (2.5, 13.5), (4.5, 15.5), (12.5, 15.5),
          (14.5, 13.5), (14.5, 9))
    _line(p, (7.5, 10.5), (8, 8), (14, 2), (16, 4), (10, 10), (7.5, 10.5))


def _draw_appearance(p):
    """Three sliders (like SF Symbols "slider.horizontal.3"): many settings, not
    just light / dark."""
    r = 1.9
    for y, knob in ((4.5, 11.5), (9.0, 6.0), (13.5, 10.0)):
        _line(p, (2.5, y), (knob - r - 0.6, y))
        _line(p, (knob + r + 0.6, y), (15.5, y))
        p.drawEllipse(QPointF(knob, y), r, r)


def _draw_parallel(p):
    """parallel projection — a box whose edges stay parallel
    (front and back faces the same size)."""
    p.drawRect(QRectF(2.5, 6.0, 9.0, 9.0))
    _line(p, (6.5, 2.5), (15.5, 2.5), (15.5, 11.5))
    for a, b in (((2.5, 6.0), (6.5, 2.5)), ((11.5, 6.0), (15.5, 2.5)), ((11.5, 15.0), (15.5, 11.5))):
        _line(p, a, b)


def _draw_export(p):
    """export — tray with an arrow going out (like macOS Share)."""
    _line(p, (6.0, 7.5), (4.0, 7.5), (4.0, 16.0), (14.0, 16.0), (14.0, 7.5), (12.0, 7.5))
    _line(p, (9.0, 11.0), (9.0, 2.0))
    _line(p, (6.2, 4.8), (9.0, 2.0), (11.8, 4.8))


# --- what-is-shown toggles in the toolbar -----------------------------
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
    """A cube with shaded faces (Faces on / off, was "Edges only")."""
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


def _draw_mesh_quality(p):
    """A dome split into triangles: how finely CAD faces are meshed."""
    path = QPainterPath(QPointF(2, 14.5))
    path.cubicTo(QPointF(2, 6), QPointF(16, 6), QPointF(16, 14.5))
    path.closeSubpath()
    p.drawPath(path)
    for a, b in (((2, 14.5), (6.5, 8.2)), ((6.5, 8.2), (9, 14.5)), ((9, 14.5), (11.5, 8.2)),
                 ((11.5, 8.2), (16, 14.5)), ((6.5, 8.2), (11.5, 8.2))):
        _line(p, a, b)


def _draw_chevron_down(p):
    path = QPainterPath(QPointF(4, 6.5))
    path.lineTo(QPointF(9, 11.5))
    path.lineTo(QPointF(14, 6.5))
    p.drawPath(path)


def _draw_checkmark(p):
    path = QPainterPath(QPointF(3.5, 9.5))
    path.lineTo(QPointF(7.5, 13.5))
    path.lineTo(QPointF(14.5, 4.5))
    p.drawPath(path)


def _draw_pencil(p):
    path = QPainterPath(QPointF(4, 14))
    path.lineTo(QPointF(4.6, 11))
    path.lineTo(QPointF(12, 3.6))
    path.lineTo(QPointF(14.4, 6))
    path.lineTo(QPointF(7, 13.4))
    path.closeSubpath()
    p.drawPath(path)
    _line(p, (10.5, 5.1), (12.9, 7.5))


def _draw_plus(p):
    p.drawEllipse(QPointF(9, 9), 7, 7)
    _line(p, (9, 5.5), (9, 12.5))
    _line(p, (5.5, 9), (12.5, 9))


def _draw_info(p):
    p.drawEllipse(QPointF(9, 9), 7, 7)
    _line(p, (9, 8), (9, 12.5))
    p.drawPoint(QPointF(9, 5.6))


def _draw_edit(p):
    """Three arrows out of a point (move / rotate / mirror)."""
    for a, b, c, d in (((9, 9), (9, 2.5), (7, 4.5), (11, 4.5)),
                       ((9, 9), (3.5, 13), (4, 10.3), (6.3, 13.8)),
                       ((9, 9), (14.5, 13), (14, 10.3), (11.7, 13.8))):
        _line(p, a, b)
        _line(p, c, b, d)


def _draw_cfd(p):
    """Wind: three streamlines."""
    for y, x1 in ((5.5, 13), (9, 15.5), (12.5, 11)):
        path = QPainterPath(QPointF(2, y))
        path.lineTo(QPointF(x1, y))
        path.arcTo(QRectF(x1 - 1.6, y - 3.2, 3.2, 3.2), -90, 270)
        p.drawPath(path)


def _draw_cell_quality(p):
    """A skewed cell with its corners."""
    _line(p, (4, 4), (14, 3), (15, 14), (3, 15), (4, 4))
    for x, y in ((4, 4), (14, 3), (15, 14), (3, 15)):
        p.drawEllipse(QPointF(x, y), 1.2, 1.2)


def _draw_results(p):
    """A page with a pulse line (like "waveform.path.ecg.text.page")."""
    p.drawRoundedRect(QRectF(3.5, 2, 11, 14), 2, 2)
    _line(p, (5, 9), (7, 9), (8, 6), (9.5, 12), (11, 9), (13, 9))


def _draw_analysis(p):
    """A wrench."""
    _line(p, (4, 14), (10, 8))
    p.drawEllipse(QPointF(12, 6), 3.4, 3.4)
    p.drawEllipse(QPointF(3.8, 14.2), 1.3, 1.3)


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


# --- Select ▾: what a click picks ------------------------------------
def _dot(p, x, y, r=1.6):
    p.save()
    p.setBrush(QColor(p.pen().color()))
    p.drawEllipse(QPointF(x, y), r, r)
    p.restore()


def _draw_pick_mesh_node(p):
    for x in (5.5, 12.5):
        for y in (5.5, 12.5):
            _dot(p, x, y, 2.2)


def _draw_pick_mesh_edge(p):
    _line(p, (3.5, 14.5), (14.5, 3.5))


def _draw_pick_mesh_cell(p):
    _line(p, (9, 2.5), (16, 15), (2, 15), (9, 2.5))


def _draw_pick_feature_node(p):
    p.drawEllipse(QPointF(9, 9), 7, 7)
    _dot(p, 9, 9, 2.4)


def _draw_pick_feature_edge(p):
    path = QPainterPath(QPointF(3.5, 4))
    path.cubicTo(QPointF(13, 3), QPointF(5, 15), QPointF(14.5, 14))
    p.drawPath(path)
    _dot(p, 3.5, 4)
    _dot(p, 14.5, 14)


def _draw_pick_feature_face(p):
    p.save()
    pen = QPen(p.pen())
    pen.setDashPattern([2, 1.6])
    p.setPen(pen)
    p.drawRoundedRect(QRectF(2.5, 2.5, 13, 13), 2, 2)
    p.restore()
    c = QColor(p.pen().color())
    p.fillPath(_rounded(QRectF(5.5, 5.5, 7, 7), 1.2), c)


def _rounded(rect, r):
    path = QPainterPath()
    path.addRoundedRect(rect, r, r)
    return path


DRAWINGS = {
    "pick_part": _draw_cube,
    "pick_mesh_node": _draw_pick_mesh_node,
    "pick_mesh_edge": _draw_pick_mesh_edge,
    "pick_mesh_cell": _draw_pick_mesh_cell,
    "pick_feature_node": _draw_pick_feature_node,
    "pick_feature_edge": _draw_pick_feature_edge,
    "pick_feature_face": _draw_pick_feature_face,
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
    "edit_unit": _draw_edit_unit,
    "plots": _draw_plots,
    "eye": _draw_eye,
    "chevron_down": _draw_chevron_down,
    "checkmark": _draw_checkmark,
    "pencil": _draw_pencil,
    "eye_off": _draw_eye_off,
    "advanced": _draw_advanced,
    "ruler": _draw_ruler,
    "sidebar": _draw_sidebar,
    "inspector": _draw_inspector,
    "fit": _draw_fit,
    "iso": _draw_cube,
    "section": _draw_section,
    "camera": _draw_camera,
    "search": _draw_search,
    "mesh_quality": _draw_mesh_quality,
    "info": _draw_info,
    "plus": _draw_plus,
    "edit": _draw_edit,
    "measure": _draw_ruler,
    "cfd": _draw_cfd,
    "cell_quality": _draw_cell_quality,
    "results": _draw_results,
    "analysis": _draw_analysis,
    "settings_general": _draw_advanced,
    "settings_appearance": _draw_appearance,
    "settings_units": _draw_ruler,
}


# The app's own icons (icons/*.svg, white on clear): drawn in the text color like the
# others. Select ▾: what a click picks.
FILES = {
    "pick_part": "part.svg", "pick_mesh_node": "mesh_node.svg",
    "pick_mesh_edge": "mesh_edge.svg", "pick_mesh_cell": "mesh_face.svg",
    "pick_feature_node": "feature_node.svg", "pick_feature_edge": "feature_edge.svg",
    "pick_feature_face": "feature_face.svg",
}
FILE_SCALE = 0.86            # as big as an SF Symbol looks in the same square
_file_cache = {}


def _icon_file(name):
    """Path of an icon file (the source folder's icons/, or inside the app), or None."""
    if name not in FILES:
        return None
    folders = [Path(__file__).resolve().parents[2] / "icons"]
    if os.environ.get("RESOURCEPATH"):                     # the app (py2app)
        folders.insert(0, Path(os.environ["RESOURCEPATH"]) / "icons")
    for folder in folders:
        if (folder / FILES[name]).exists():
            return folder / FILES[name]
    return None


def _file_image(path, px, color):
    """The SVG file drawn px × px (centered, its own proportions) in `color`."""
    key = (str(path), px, color.rgba())
    img = _file_cache.get(key)
    if img is None:
        from PySide6.QtSvg import QSvgRenderer
        r = QSvgRenderer(str(path))
        img = QImage(px, px, QImage.Format_ARGB32_Premultiplied)
        img.fill(Qt.transparent)
        if r.isValid():
            w, h = r.defaultSize().width(), r.defaultSize().height()
            k = px * FILE_SCALE / max(w, h, 1)
            p = QPainter(img)
            p.setRenderHint(QPainter.Antialiasing)
            r.render(p, QRectF((px - w * k) / 2, (px - h * k) / 2, w * k, h * k))
            p.setCompositionMode(QPainter.CompositionMode_SourceIn)  # keep the shape, recolor
            p.fillRect(img.rect(), color)
            p.end()
        _file_cache[key] = img
    return img


class _Engine(QIconEngine):
    def __init__(self, draw, role=QPalette.WindowText, on_accent=False, symbol=None,
                 path=None):
        super().__init__()
        self.draw = draw
        self.role = role
        self.on_accent = on_accent      # checked: accent-coloured (icon bar), else white
        self.symbol = symbol            # SF Symbol name (macOS), else drawn
        self.path = path                # the app's own SVG (icons/), else the above

    def paint(self, p, rect, mode, state):
        pal = QGuiApplication.palette()
        group = QPalette.Disabled if mode == QIcon.Disabled else QPalette.Active
        color = pal.color(group, self.role)
        if state == QIcon.On and mode != QIcon.Disabled:
            # checked toolbar toggles sit on the accent colour; icon bar ones are accent
            color = pal.color(QPalette.Highlight) if self.on_accent else QColor("white")
        if self.path is not None:
            dpr = p.device().devicePixelRatioF() if p.device() is not None else 1.0
            side = min(rect.width(), rect.height())
            img = _file_image(self.path, max(8, round(side * dpr)), color)
            p.drawImage(QRectF(rect.x() + (rect.width() - side) / 2,
                               rect.y() + (rect.height() - side) / 2, side, side), img)
            return
        if self.symbol:
            dpr = p.device().devicePixelRatioF() if p.device() is not None else 1.0
            px = max(8, round(min(rect.width(), rect.height()) * dpr))
            img = _sf_image(self.symbol, px, color)
            if img is not None:
                side = min(rect.width(), rect.height())
                p.drawImage(QRectF(rect.x() + (rect.width() - side) / 2,
                                   rect.y() + (rect.height() - side) / 2, side, side), img)
                return
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
        e = _Engine(self.draw, self.role, self.on_accent, self.symbol, self.path)
        _engines.append(e)
        return e


def _sf_image(symbol, px, color):
    """SF Symbol `symbol` drawn by macOS in `color`, px × px pixels (QImage), or None."""
    key = (symbol, px, color.name(QColor.HexArgb))
    if key in _sf_cache:
        return _sf_cache[key]
    img = None
    if sys.platform == "darwin":
        try:
            solid = QColor(color)
            solid.setAlphaF(1.0)
            img = _sf_render(symbol, px, solid)
            if img is not None and color.alphaF() < 1.0:
                # see-through (a disabled button): fade the solid symbol here. Tinted in
                # macOS with a see-through color, the symbol's own black showed through —
                # invisible on a dark toolbar
                faded = QImage(img.size(), QImage.Format_ARGB32_Premultiplied)
                faded.fill(Qt.transparent)
                p = QPainter(faded)
                p.setOpacity(color.alphaF())
                p.drawImage(0, 0, img)
                p.end()
                img = faded
        except Exception:                                # noqa: BLE001 no PyObjC / symbol
            img = None
    _sf_cache[key] = img
    return img


def _sf_render(symbol, px, color):
    from AppKit import (
        NSBitmapImageFileTypePNG, NSBitmapImageRep, NSColor, NSCompositingOperationSourceAtop,
        NSDeviceRGBColorSpace, NSGraphicsContext, NSImage, NSImageSymbolConfiguration,
        NSRectFillUsingOperation,
    )
    from Foundation import NSMakeRect
    sym = NSImage.imageWithSystemSymbolName_accessibilityDescription_(symbol, None)
    if sym is None:
        return None
    cfg = NSImageSymbolConfiguration.configurationWithPointSize_weight_(px * 0.75, 0.0)
    sym = sym.imageWithSymbolConfiguration_(cfg) or sym
    w, h = sym.size().width, sym.size().height
    k = min(px / w, px / h, 1.0)
    init = getattr(NSBitmapImageRep.alloc(), "initWithBitmapDataPlanes_pixelsWide_pixelsHigh_"
                   "bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_"
                   "bytesPerRow_bitsPerPixel_")
    rep = init(
        None, px, px, 8, 4, True, False, NSDeviceRGBColorSpace, 0, 0)
    ctx = NSGraphicsContext.graphicsContextWithBitmapImageRep_(rep)
    NSGraphicsContext.saveGraphicsState()
    try:
        NSGraphicsContext.setCurrentContext_(ctx)
        sym.drawInRect_(NSMakeRect((px - w * k) / 2, (px - h * k) / 2, w * k, h * k))
        NSColor.colorWithSRGBRed_green_blue_alpha_(color.redF(), color.greenF(), color.blueF(),
                                                    color.alphaF()).set()
        NSRectFillUsingOperation(NSMakeRect(0, 0, px, px), NSCompositingOperationSourceAtop)
        ctx.flushGraphics()
    finally:
        NSGraphicsContext.restoreGraphicsState()
    data = rep.representationUsingType_properties_(NSBitmapImageFileTypePNG, {})
    img = QImage.fromData(bytes(data))
    return None if img.isNull() else img


def icon(name, role=QPalette.WindowText, on_accent=False) -> QIcon:
    e = _Engine(DRAWINGS[name], role, on_accent, SF.get(name), _icon_file(name))
    _engines.append(e)
    return QIcon(e)


_chevrons = {}


def paint_chevron(p, cx, cy, enabled=True, role=QPalette.WindowText, size=10):
    """The pull-down mark (SF Symbol chevron.down) centered on (cx, cy), `size` px,
    grayed when disabled: toolbar pull-downs and pop-up menus."""
    ic = _chevrons.get(role)
    if ic is None:
        ic = _chevrons[role] = icon("chevron_down", role)
    ic.paint(p, QRect(round(cx - size / 2), round(cy - size / 2), size, size), Qt.AlignCenter,
             QIcon.Normal if enabled else QIcon.Disabled)
