"""Scene ▸ what surrounds the model and how lines look: theme colours, background,
grid and axes, origin marker, bounding box, line widths (Appearance, Display ▸ Axes)."""
from __future__ import annotations

import numpy as np
import pyvista as pv
from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper

from meshviewer.render.background import ImageBackground, is_dark_image, load_image
from meshviewer.render.measure import AXIS_COLORS
from meshviewer.render.style import AXES_MODES, EDGE_WIDTHS, is_dark_color, rgb, THEMES


def _label_format(span):
    """printf format for axis numbers: about 3 significant digits over `span`."""
    if not span > 0:
        return "%.2f"
    decimals = int(np.clip(2 - np.floor(np.log10(span)), 0, 6))
    return f"%.{decimals}f"


def _size_labels(grid, made, factor):
    """The grid's text size and its distances to the axes: as made × factor."""
    size, label_off, title_off = made
    grid.SetScreenSize(size * factor)
    grid.SetLabelOffset(label_off * factor)
    grid.SetTitleOffset([v * factor for v in title_off] if len(title_off) > 1
                        else title_off[0] * factor)


def _overlay_actor(poly, color, line_width=1.0, point_size=None):
    """Plain unlit actor for the overlay layer (origin marker)."""
    m = vtkPolyDataMapper()
    m.SetInputData(poly)
    m.ScalarVisibilityOff()
    a = vtkActor()
    a.SetMapper(m)
    prop = a.GetProperty()
    prop.SetColor(rgb(color))
    prop.SetLineWidth(line_width)
    prop.SetLighting(False)
    if point_size:
        prop.SetRepresentationToPoints()
        prop.SetPointSize(point_size)
        prop.SetRenderPointsAsSpheres(True)
    a.PickableOff()
    return a


class Appearance:
    def set_origin(self, on, render=True):
        """A dot at (0, 0, 0) with short X / Y / Z arrows (red / green / blue),
        drawn on top of the model so it shows even inside a part."""
        on = on and not self.is_drawing             # drawings: lines only
        self.state["origin"] = bool(on)
        self._build_origin()
        if render:
            self.p.render()

    def origin_actors(self):
        return list(self._origin_actors)

    def _build_origin(self):
        layer = self.measure._layer()             # the overlay the measure markers use
        for a in self._origin_actors:
            layer.RemoveActor(a)
        self._origin_actors = []
        if not self.state.get("origin"):
            return
        length = 0.06 * self._diag()
        for axis, color in zip(np.eye(3), AXIS_COLORS):
            self._origin_actors.append(_overlay_actor(
                pv.Line((0.0, 0.0, 0.0), axis * length), color, line_width=2.5))
        dot = _overlay_actor(pv.PolyData(np.zeros((1, 3))),
                             "#f2f2f7" if self._dark else "#1c1c1e", point_size=10)
        self._origin_actors.append(dot)
        for a in self._origin_actors:
            layer.AddActor(a)

    def set_bbox(self, on, render=True):
        on = on and not self.is_drawing             # drawings: lines only
        self.state["bbox"] = bool(on)
        if on and self._bbox_actor is None:
            self._bbox_actor = self.p.add_bounding_box(color=THEMES[self._dark]["grid"],
                                                       line_width=1, reset_camera=False)
        if self._bbox_actor is not None:
            self._bbox_actor.SetVisibility(bool(on))
        if render:
            self.p.render()

    # ---- theme ---------------------------------------------------------
    @property
    def edge_color(self):
        return THEMES[self._dark]["edge"]

    def theme_colors(self):
        """Colours for the background actually shown (light or dark set)."""
        return THEMES[self._dark]

    # ---- Appearance: axis labels, edge lines, grid lines ----------------------------
    def set_axis_font(self, size, rebuild=True):
        size = int(size)                              # points
        if size != self.axis_font:
            self.axis_font = size
            if rebuild:
                self.set_theme(self._ui_dark)         # rebuilds the grid + axes

    def set_edge_options(self, width=None, hide_while_moving=None, render=True):
        """feature edge thickness ("thin" / "medium" / "thick" or px)
        and whether lines are hidden while the view moves."""
        if hide_while_moving is not None:              # 2D files: cheap to draw, never hidden
            self.hide_edges_moving = bool(hide_while_moving) and self.model.dim != 2
        if width is not None:
            self.edge_width = float(EDGE_WIDTHS.get(width, width))
            if self._edges is not None:
                w = self.edge_width
                if self.model.file_type == "mesh2d":
                    w = max(2.5, 2 * w)                  # 2D outline: over the mesh edges
                self._edges.GetProperty().SetLineWidth(w)
            if render:
                self.p.render()

    def set_axes_mode(self, mode, rebuild=True, render=True):
        """, one control instead of three (Display ▸ Grid + Appearance
        ▸ Grid lines / Axis lines):
            "off"   nothing
            "axes"  axis frame, ticks, numbers and titles
            "grid"  grid lines on the walls behind the model only
            "both"  axes + grid lines (default)"""
        mode = mode if mode in AXES_MODES else "both"
        lines, axes = mode in ("grid", "both"), mode in ("axes", "both")
        changed = (lines, axes) != (self.grid_lines, self.axis_lines)
        self.grid_lines, self.axis_lines = lines, axes
        self.state["grid"] = mode != "off"
        if changed and rebuild:
            self.refresh_grid(render=False)
        elif self._grid_actor is not None:
            self._grid_actor.SetVisibility(self.state["grid"])
        if render:
            self.p.render()

    # ---- the grid / axes box -----------------------------------------------------------
    def refresh_grid(self, render=True):
        """Rebuild the grid (it can't be recoloured or relabelled in place).
        Called on theme / Appearance changes and when the display unit changes."""
        self.p.remove_bounds_axes()
        self._grid_actor = self._add_grid(self.p, THEMES[self._dark]["grid"])
        self._grid_actor.SetVisibility(self.state["grid"])
        if render:
            self.p.render()

    def _add_grid(self, plotter, color, k=1):
        """Grid + axes on `plotter` (the view, or an off-screen screenshot at k×).
        Fixed to the model's bounds, so the section handle can't stretch it.
        Numbers in the unit chosen in the toolbar and titles like
        "X Axis (mm)"; with Axis lines off, numbers and titles go too."""
        b = np.asarray(self.model_bounds(), dtype=float)
        s, unit = self.measure.unit_scale()
        kw = dict(color=color, font_size=self.axis_font * k, grid=self._grid_mode(),
                  location="outer", ticks="both", bounds=list(b))
        spans = np.ptp(b.reshape(3, 2), axis=1)           # a short axis: fewer numbers,
        for axis, span in zip("xyz", spans):              # so they don't run into each other
            kw[f"n_{axis}labels"] = int(np.clip(round(5 * span / (spans.max() or 1.0)), 2, 5))
        if not self.axis_lines:
            kw.update(xtitle=" ", ytitle=" ", ztitle=" ")
            # (not show_*labels=False: PyVista then drops the ticks the grid lines use)
        else:
            suffix = f" ({unit})" if unit else ""
            kw.update(xtitle=f"X Axis{suffix}", ytitle=f"Y Axis{suffix}", ztitle=f"Z Axis{suffix}")
            if s != 1.0:                                  # converted: label the real values
                span = np.ptp(b.reshape(3, 2), axis=1).max() * s
                kw.update(axes_ranges=list(b * s), fmt=_label_format(span))
        g = plotter.show_grid(**kw)
        made = (g.GetScreenSize(), g.GetLabelOffset(), tuple(np.atleast_1d(g.GetTitleOffset())))
        if plotter is self.p:
            self._label_made = made                   # _place_camera scales from these
        _size_labels(g, made, self.label_factor())
        if not self.axis_lines:                   # numbers, frame lines and tick marks
            for i, ax in enumerate("XYZ"):
                g.GetLabelTextProperty(i).SetOpacity(0.0)
                getattr(g, f"Get{ax}AxesLinesProperty")().SetOpacity(0.0)
                getattr(g, f"Set{ax}AxisTickVisibility")(False)
                getattr(g, f"Set{ax}AxisMinorTickVisibility")(False)
        return g

    def _grid_mode(self):
        return "back" if self.grid_lines else False

    def _corner_axes(self, plotter, **kw):
        """The X / Y / Z arrows in the corner; 2D files: X and Y only (Z points at you)."""
        ax = plotter.add_axes(viewport=self._axes_viewport(), **kw)
        if self.model.dim == 2 and ax is not None:
            ax.SetZAxisLabelText("")
            for prop in (ax.GetZAxisShaftProperty(), ax.GetZAxisTipProperty()):
                prop.SetOpacity(0.0)
        return ax

    def _axes_viewport(self):
        """XYZ corner widget grows a little with the label size."""
        side = min(0.16 * (self.axis_font / 10) ** 0.5, 0.26)     # 10 pt = original 0.16
        return (1.0 - side * 0.875, 0.0, 1.0, side)

    # ---- 3D background chosen in Appearance -----------------------------------
    def set_background(self, mode="default", value=None, render=True):
        """mode: "default" (theme gradient) | "color" ("#RRGGBB") | "image" (path)."""
        if mode == "image" and not value:
            mode = "default"
        self.bg_mode = (mode, value)
        self.set_theme(self._ui_dark, render=render)

    def set_theme(self, dark, render=True, accent=None):
        self._ui_dark = bool(dark)                    # the app's light / dark mode
        mode, value = self.bg_mode
        img = self._background_image(value) if mode == "image" else None
        # Grid, axes and edges follow the background actually shown.
        if mode == "color":
            self._dark = is_dark_color(value)
        elif img is not None:
            self._dark = is_dark_image(img)
        else:
            self._dark = self._ui_dark
        if accent and accent != self.accent:
            self.accent = accent
            if self._outline is not None:
                self._outline.GetProperty().SetColor(rgb(accent))
            self.section.set_accent(accent)
        t = THEMES[self._dark]
        if mode == "color":
            self.p.set_background(value)
        elif self.is_drawing and self._dark and img is None:
            self.p.set_background("#000000")           # drawings: black, like a CAD screen
        else:
            self.p.set_background(t["bg"], top=t["bg_top"])
        if self.is_drawing and self._surf_map is not None:
            self._apply_blocks()                       # lines follow the background
        self._apply_background_image(img)
        if self._edges is not None:
            self._edges.GetProperty().SetColor(rgb(t["edge"]))
        self.refresh_grid(render=False)
        self.p.hide_axes()
        self._corner_axes(self.p, line_width=3, color=t["grid"])
        if self._bbox_actor is not None:
            self._bbox_actor.GetProperty().SetColor(rgb(t["grid"]))
        if self.state.get("origin"):
            self._build_origin()                   # dot colour follows the background
        self.section.restyle()                     # cut mesh + outline colours
        if self._original_actor is not None:       # grey "original" edges
            self._original_actor.GetProperty().SetColor(rgb(t["grid"]))
        if render:
            self.p.render()

    def _background_image(self, path):
        """Pixels of the chosen picture (cached); None if it can't be read."""
        cache = getattr(self, "_bg_cache", (None, None))
        if cache[0] != path:
            try:
                cache = (path, load_image(path))
            except Exception as exc:                  # unreadable: keep the gradient
                print(f"background image failed: {exc}")
                cache = (path, None)
            self._bg_cache = cache
        return cache[1]

    def _apply_background_image(self, arr):
        old = getattr(self, "_bg_image", None)
        if old is not None and old.arr is arr:
            return
        if old is not None:
            old.detach()
        self._bg_image = ImageBackground(self.p.renderer, arr) if arr is not None else None
