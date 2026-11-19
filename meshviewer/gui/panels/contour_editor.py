"""One contour of the Contours tool (gui/panels/contours.py): its fold-out, on a card.

    ▾ Contour 1                              (opening it shows its tab)
      ┌─────────────────────────────────────────────┐
      │ Field          [ Velocity u             ▾ ]  │   by subject (core/field_kinds)
      │ Unit in file   [ —  As written          ▾ ]  │   what the file's numbers are in
      │ Shown in       [ km/h                   ▾ ]  │   once the file's unit is known
      │ (a line saying what applies)                 │
      │ ──────────────────────────────────────────── │
      │ Color by       [ Value | Gradient ]          │
      │ Color scale    [ Linear | Log ]              │   how values map onto colors
      │ Colors         [ ▬▬▬▬ (the color map) ▾ ]    │
      │ Min [ auto: 0.02 ] kPa                       │   (Timeline: over every step)
      │ Max [ auto: 1.6 ]  kPa                       │
      │ ─ ▸ Color Bar ──────────────────── (switch)  │   the bar over the 3D view; on:
      │     Height       [━━━━●━━━━━━━]       100%   │   unfolds (off: "Off — …")
      │     Width        [━━━━●━━━━━━━]       100%   │
      │     Ticks        [━━●━━━━━━━━━]          5   │   2 – 15, ends included
      │     Tick spacing [ Linear | Log ]            │   evenly up the bar / in log10
      │     Text color   [ Auto | White | Black ]    │   Auto: for the background
      │     Smooth colors                  (switch)  │   off: bands between the ticks
      │     Show title                     (switch)  │
      │                        [ Reset Color Bar ]   │
      │ ─ ▸ Animation ──────────────────── (switch)  │   time steps: gui/panels/
      └─────────────────────────────────────────────┘     contour_animation.py
                                   [ Rename… | Delete ]

The editor writes its contour's dict (`c`) and tells the panel (`contour_changed`), which
computes and draws. Field names and groups (`field_label`, `grouped`) are shared with
Plots; the color bar's settings (`BAR_DEFAULTS`, `bar_settings`) with the panel.
"""
from __future__ import annotations

import json

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from meshviewer.core.field_kinds import GROUP_ORDER, KINDS, field_kind
from meshviewer.core.fields import COLORMAPS, DEFAULT_MAP, TICKS
from meshviewer.core.plots import COORD
from meshviewer.gui.access import name_controls
from meshviewer.gui.forms import (_grid, _label, _row, button, buttons, note, rule, segmented,
                                  switch_row)
from meshviewer.gui.panels.contour_animation import AnimationSection, anim_settings
from meshviewer.gui.panels.field_units import CUSTOM_ITEM, FieldUnits  # noqa: F401 (tests)
from meshviewer.gui.store import settings as _settings
from meshviewer.gui.widgets import (CollapsibleSection, GradientSelect, MenuSelect,
                                    NoWheelSlider, NumberField, Switch)
from meshviewer.render.colorbar import MARGIN, SIZE_RANGE, TEXT_COLORS


def field_label(f):
    """The menu text of a field: its usual name (core/field_kinds), else as written."""
    if f.startswith(COORD):
        return f"Position {f[len(COORD):].upper()}"
    kind = field_kind(f)
    return kind.title if kind is not None else f


def grouped(fields):
    """[(header, [fields])]: the known fields by subject (field_kinds order), then
    Other (unknown), then Position."""
    order = {k.key: i for i, k in enumerate(KINDS)}
    out = {g: [] for g in GROUP_ORDER}
    other, position = [], []
    for f in fields:
        kind = None if f.startswith(COORD) else field_kind(f)
        if f.startswith(COORD):
            position.append(f)
        elif kind is not None:
            out[kind.group].append(f)
        else:
            other.append(f)
    for items in out.values():
        items.sort(key=lambda f: order[field_kind(f).key])
    return [(g, out[g]) for g in GROUP_ORDER if out[g]] + \
        ([("Other", other)] if other else []) + ([("Position", position)] if position else [])


# ---- the color bar's settings ----------------------------------------------------------------
# until one is chosen; then a new contour starts with the last chosen ("results/color_bar")
BAR_DEFAULTS = {"on": True, "height": 100, "width": 100, "ticks": 5, "tick_log": False,
                "text": "auto", "smooth": True, "title": True, "pos": [MARGIN, MARGIN]}
RESET = ("height", "width", "ticks", "tick_log", "text", "smooth", "title",   # Reset
         "pos")                                                                # Color Bar


def bar_settings(saved):
    """The color bar's settings from what was saved (any missing or odd: the default)."""
    out = dict(BAR_DEFAULTS)
    out["pos"] = list(out["pos"])
    if isinstance(saved, dict):
        for k, v in saved.items():
            if k in ("on", "smooth", "tick_log", "title"):
                out[k] = bool(v)
            elif k in ("height", "width") and isinstance(v, (int, float)):
                out[k] = int(np.clip(round(v), *SIZE_RANGE))
            elif k == "ticks" and isinstance(v, (int, float)):
                out[k] = int(np.clip(round(v), *TICKS))
            elif k == "text" and v in TEXT_COLORS:
                out[k] = v
            elif k == "pos" and isinstance(v, (list, tuple)) and len(v) == 2:
                try:
                    out[k] = [max(0.0, float(v[0])), max(0.0, float(v[1]))]
                except (TypeError, ValueError):
                    pass
    return out


def last_bar_settings():
    try:
        return bar_settings(json.loads(_settings().value("results/color_bar") or "null"))
    except (TypeError, ValueError):
        return bar_settings(None)


def save_bar_defaults(bar):
    _settings().setValue("results/color_bar", json.dumps(bar))


def new_contour(ident, name, field, bar=None):
    """A contour's settings (remembered per file): its field, range, scale, colors, bar."""
    return {"id": int(ident), "name": name, "field": field, "lo": None, "hi": None,
            "show": "value", "log": False, "cmap": DEFAULT_MAP,
            "bar": bar_settings(bar if bar is not None else last_bar_settings()),
            "anim": anim_settings(None), "view": None}


def clean_contour(c, ident):
    """A remembered contour, checked (None when it isn't one)."""
    if not isinstance(c, dict):
        return None
    out = new_contour(c.get("id", ident), str(c.get("name") or f"Contour {ident}"),
                      c.get("field"), bar=c.get("bar") if isinstance(c.get("bar"), dict)
                      else None)
    for k in ("lo", "hi"):
        out[k] = float(c[k]) if isinstance(c.get(k), (int, float)) else None
    out["show"] = "gradient" if c.get("show") == "gradient" else "value"
    out["log"] = bool(c.get("log"))
    out["cmap"] = c.get("cmap") if c.get("cmap") in COLORMAPS else DEFAULT_MAP
    out["view"] = clean_view(c.get("view"))
    out["anim"] = anim_settings(c.get("anim"))
    return out


def clean_view(v):
    """A tab's own view (its camera, Show ▾ toggles and hidden parts,
    gui/window_pages.py), checked; None: none yet (it starts as the view it came from)."""
    if not isinstance(v, dict):
        return None
    cam = v.get("camera")
    try:
        cam = [[float(x) for x in cam[i]] for i in range(3)] + [float(cam[3]), bool(cam[4]),
                                                               float(cam[5])]
    except (TypeError, ValueError, IndexError):
        cam = None
    show = {k: bool(x) for k, x in (v.get("show") or {}).items() if isinstance(k, str)}
    hidden = v.get("hidden")
    hidden = [str(n) for n in hidden] if isinstance(hidden, (list, tuple)) else None
    return {"camera": cam, "show": show, "hidden": hidden}


def _slider_row(g, r, text, lo, hi, step):
    """Label · slider (field and unit columns) · its value (the last column)."""
    s = NoWheelSlider(Qt.Horizontal)
    s.setRange(lo, hi)
    s.setSingleStep(step)
    s.setPageStep(step * 2)
    s.setToolTip(text)
    s.setAccessibleName(text)
    val = _label("", "AxisLabel")
    val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    val.setMinimumWidth(QLabel("160%").sizeHint().width())
    g.addWidget(QLabel(text), r, 0)
    g.addWidget(s, r, 1, 1, 2)
    g.addWidget(val, r, 3)
    return s, val


class ContourEditor(QWidget):
    """The settings of one contour; edits its dict in place."""

    def __init__(self, panel, c):
        super().__init__()
        self.panel, self.c = panel, c
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 2, 0, 2)
        lay.setSpacing(6)
        card = QFrame()
        card.setObjectName("ResultCard")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(8, 9, 8, 10)
        cl.setSpacing(6)
        lay.addWidget(card)

        # -- which field, and its unit
        g = _grid()
        self.field = MenuSelect()
        self.field.cascade = True                      # a submenu per group (Flow ▸ …)
        self.field.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.field.setToolTip("Field")
        self.field.currentIndexChanged.connect(self._field_changed)
        _row(g, 0, "Field", self.field, wide=True)
        self.units = FieldUnits(self, lambda: self.panel, lambda: self.c["field"], g, 1)
        self.file_unit, self.shown_unit = self.units.file_unit, self.units.shown_unit
        cl.addLayout(g)
        self.unit_note = self.units.note               # what applies to this field's unit
        cl.addWidget(self.unit_note)
        cl.addWidget(rule())

        # -- how the boundaries are colored
        g = _grid()
        self.show_acts, cap = segmented(           # gradient: |∇f| along the surface
            self, (("value", "Value", "Value"), ("gradient", "Gradient", "Gradient")),
            self._show_changed)
        _row(g, 0, "Color by", cap, wide=True, align=Qt.AlignLeft)
        self.scale_acts, cap = segmented(          # log: by powers of ten
            self, (("linear", "Linear", "Linear"), ("log", "Log", "Log")),
            self._scale_changed)
        _row(g, 1, "Color scale", cap, wide=True, align=Qt.AlignLeft)
        self.cmap = GradientSelect()
        self.cmap.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        for key, stops in COLORMAPS.items():
            self.cmap.addItem(stops, key)
        self.cmap.setToolTip("Colors")
        self.cmap.currentIndexChanged.connect(lambda *_: self._set(cmap=self.cmap.currentData()))
        _row(g, 2, "Colors", self.cmap, wide=True)
        self.lo = NumberField()
        self.lo.setToolTip("Min")
        self.hi = NumberField()
        self.hi.setToolTip("Max")
        self.lo.valueChanged.connect(lambda v: self._set(lo=v))
        self.hi.valueChanged.connect(lambda v: self._set(hi=v))
        _, self.lo_unit = _row(g, 3, "Min", self.lo, unit=" ")
        _, self.hi_unit = _row(g, 4, "Max", self.hi, unit=" ")
        cl.addLayout(g)
        self.stats = note()                            # only when there is nothing to show
        self.stats.setVisible(False)
        cl.addWidget(self.stats)
        cl.addWidget(self._build_bar_section())
        self.anim = AnimationSection(self)                 # time steps (OpenFOAM)
        cl.addWidget(self.anim.section)

        # -- rename / delete, under the card (as a plot's)
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        ren = button(self, "Rename…", lambda: self.panel.rename(self.c["id"]))
        dele = button(self, "Delete", lambda: self.panel.remove(self.c["id"]),
                      "Delete this contour and its tab")
        bottom.addWidget(buttons(ren, dele))
        lay.addLayout(bottom)
        self.sync()
        name_controls(self)

    def _build_bar_section(self):
        """▸ Color Bar, its switch in the header (Show color bar), in the forms layout:
        label · field · unit · ? (sliders take the field and unit columns, their value
        the last). Off: one note instead of the controls."""
        outer = QWidget()
        oc = QVBoxLayout(outer)
        oc.setContentsMargins(0, 0, 0, 0)
        oc.setSpacing(6)
        self.bar_note = note("Off — switch on to show the color bar.")
        oc.addWidget(self.bar_note)
        w = QWidget()
        self.bar_details = w
        oc.addWidget(w)
        col = QVBoxLayout(w)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(6)
        g = _grid()
        self.height_slider, self.height_label = _slider_row(g, 1, "Height", *SIZE_RANGE, 5)
        self.width_slider, self.width_label = _slider_row(g, 2, "Width", *SIZE_RANGE, 5)
        self.ticks_slider, self.ticks_label = _slider_row(g, 3, "Ticks", *TICKS, 1)
        self.height_slider.valueChanged.connect(lambda v: self._set_bar(height=int(v)))
        self.width_slider.valueChanged.connect(lambda v: self._set_bar(width=int(v)))
        self.ticks_slider.valueChanged.connect(lambda v: self._set_bar(ticks=int(v)))
        self.tick_acts, cap = segmented(           # evenly up the bar / in log10
            self, (("linear", "Linear", "Linear"), ("log", "Log", "Log")),
            lambda k: self._set_bar(tick_log=k == "log"))
        _row(g, 4, "Tick spacing", cap, wide=True, align=Qt.AlignLeft)
        self.text_acts, cap = segmented(
            self, tuple((k, k.title(), k.title()) for k in TEXT_COLORS),
            lambda k: self._set_bar(text=k))
        _row(g, 5, "Text color", cap, wide=True, align=Qt.AlignLeft)
        col.addLayout(g)
        self.smooth = Switch()                         # off: bands between the ticks
        self.smooth.toggled.connect(lambda on: self._set_bar(smooth=bool(on)))
        col.addWidget(switch_row("Smooth colors", self.smooth))
        self.show_title = Switch()                     # the field's name over the bar
        self.show_title.toggled.connect(lambda on: self._set_bar(title=bool(on)))
        col.addWidget(switch_row("Show title", self.show_title))
        g = _grid()
        self.reset_bar = button(self, "Reset Color Bar", self.reset_color_bar)
        self.reset_cap = buttons(self.reset_bar)
        g.addWidget(self.reset_cap, 0, 1, 1, 3, Qt.AlignRight)
        col.addLayout(g)
        self.bar_on = Switch()                         # Show color bar
        self.bar_on.setToolTip("Show Color Bar")
        self.bar_on.setAccessibleName("Show Color Bar")
        self.bar_on.toggled.connect(self._bar_switched)
        self.bar_section = CollapsibleSection("Color Bar", outer, f"contour_bar{self.c['id']}",
                                              trailing=self.bar_on, sub=True, remember=False,
                                              start_open=False)
        return self.bar_section

    def _bar_switched(self, on):
        if on:
            self.bar_section.set_expanded(True)
        self._set_bar(on=bool(on))

    # ---- from the contour's dict to the widgets -----------------------------------------
    def sync(self):
        c, b = self.c, self.c["bar"]
        self.field.blockSignals(True)
        self.field.clear()
        for title, group in grouped(self.panel.fields):    # by subject, under headers
            self.field.addSection(title)
            for f in group:
                self.field.addItem(field_label(f), f)
        i = self.field.findData(c["field"])
        self.field.setCurrentIndex(i if i >= 0 else 0)
        c["field"] = self.field.currentData()
        self.field.blockSignals(False)
        for box, v in ((self.lo, c["lo"]), (self.hi, c["hi"])):
            box.blockSignals(True)
            box.setValue(v)
            box.blockSignals(False)
        self.show_acts[c["show"]].setChecked(True)
        self.scale_acts["log" if c["log"] else "linear"].setChecked(True)
        self.cmap.blockSignals(True)
        self.cmap.setCurrentIndex(max(0, self.cmap.findData(c["cmap"])))
        self.cmap.blockSignals(False)
        self.sync_bar()
        self.sync_units()
        self.anim.sync()

    def sync_bar(self):
        b = self.c["bar"]
        Switch.set_silently(self.bar_on, b["on"])
        self.bar_note.setVisible(not b["on"])
        self.bar_details.setVisible(b["on"])
        Switch.set_silently(self.smooth, b["smooth"])
        Switch.set_silently(self.show_title, b["title"])
        self.tick_acts["log" if b["tick_log"] else "linear"].setChecked(True)
        self.text_acts[b["text"]].setChecked(True)
        for s, key in ((self.height_slider, "height"), (self.width_slider, "width"),
                       (self.ticks_slider, "ticks")):
            s.blockSignals(True)
            s.setValue(b[key])
            s.blockSignals(False)
        self.height_label.setText(f"{b['height']}%")
        self.width_label.setText(f"{b['width']}%")
        self.ticks_label.setText(str(b["ticks"]))

    def sync_units(self):
        self.units.sync()

    def show_info(self, info):
        """What the panel worked out for it: the auto range, the unit, or why nothing
        shows."""
        for lab in (self.lo_unit, self.hi_unit):
            lab.setText(info.get("unit", ""))
        why = info.get("why")
        self.stats.setText(why or "")
        self.stats.setVisible(bool(why))
        if "a_lo" in info:
            self.lo.setPlaceholderText(f"auto: {info['a_lo_text']}")
            self.hi.setPlaceholderText(f"auto: {info['a_hi_text']}")
        else:                                          # nothing shows: no old numbers
            self.lo.setPlaceholderText("auto")
            self.hi.setPlaceholderText("auto")
        self.tick_acts["log"].setEnabled(bool(info.get("lo_positive", True)))
        self.anim.sync_range()

    # ---- handlers ------------------------------------------------------------------------
    def commit(self):
        """Min / Max as in their boxes (a box set without typing sends nothing)."""
        self.c["lo"], self.c["hi"] = self.lo.value(), self.hi.value()

    def _set(self, **kw):
        self.commit()
        self.c.update(kw)
        self.panel.contour_changed(self.c["id"])

    def _set_bar(self, **kw):
        self.commit()
        self.c["bar"].update(kw)
        self.sync_bar()
        self.panel.bar_changed(self.c["id"])

    def _field_changed(self, *_):
        self.c.update(field=self.field.currentData(), lo=None, hi=None)  # its own range
        self.sync()
        self.panel.contour_changed(self.c["id"])

    def _show_changed(self, k):
        self.c.update(show=k, lo=None, hi=None)                # the gradient: its own range
        self.sync()
        self.panel.contour_changed(self.c["id"])

    def _scale_changed(self, k):
        """Linear ↔ log: a typed Min at or below zero means nothing on a log scale."""
        self.commit()
        self.c["log"] = k == "log"
        if self.c["log"] and self.c["lo"] is not None and self.c["lo"] <= 0:
            self.c["lo"] = None
            self.sync()
        self.panel.contour_changed(self.c["id"])

    def set_custom_unit(self, which, text):
        self.units.set_custom(which, text)

    def reset_color_bar(self):
        """Reset Color Bar: its height, width, ticks, tick spacing, text color, smooth
        colors, title, place (the top-left corner) and the color map as they first were
        (Show color bar stays)."""
        self.c["bar"].update({k: list(BAR_DEFAULTS[k]) if k == "pos" else BAR_DEFAULTS[k]
                              for k in RESET})
        self.c["cmap"] = DEFAULT_MAP
        self.sync()
        self.panel.bar_changed(self.c["id"])
