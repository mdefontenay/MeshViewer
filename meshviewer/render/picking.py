"""Scene ▸ the mouse: a click (not a drag) picks the part, face or point under it and
does what the current mode wants; a right-click opens the part menu."""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from vtkmodules.vtkRenderingCore import vtkCellPicker, vtkHardwarePicker

from meshviewer.render.style import CLICK_TOLERANCE_PX


class Picking:
    def _setup_picking(self):
        # Hardware picking: respects hidden parts and the section cut.
        self._hw_picker = vtkHardwarePicker()
        self._picker = vtkCellPicker()             # fallback
        self._picker.SetTolerance(0.0005)
        self._press = None
        iren = self.p.iren
        # right-click (without dragging) -> context menu for the part under it
        self.on_context = None           # UI hook: (names to act on, part under the cursor)
        self._rpress = None
        # Passive: still called while a style holds the mouse (the 2D style grabs it
        # on press, so the release reached only the style: no click, no right-click menu)
        for ev, fn in (("LeftButtonPressEvent", self._on_press),
                       ("LeftButtonReleaseEvent", self._on_release),
                       ("RightButtonPressEvent", self._on_rpress),
                       ("RightButtonReleaseEvent", self._on_rrelease)):
            tag = iren.interactor.AddObserver(ev, lambda *_, f=fn: f())
            iren.interactor.GetCommand(tag).PassiveObserverOn()
        # a click that closes a pop-up menu reaches the 3D view, but its
        # release goes to the menu, so VTK kept zooming / rotating with no button held.
        # On every mouse move: no button down -> end whatever drag VTK thinks is running.
        tag = iren.interactor.AddObserver("MouseMoveEvent", lambda *_: self.end_stuck_drag(), 10.0)
        iren.interactor.GetCommand(tag).PassiveObserverOn()   # still called while VTK holds focus

    def end_stuck_drag(self):
        style = self.p.iren.interactor.GetInteractorStyle()
        if style is None or style.GetState() == 0:           # 0 = VTKIS_NONE
            return
        if QGuiApplication.mouseButtons() != Qt.NoButton:
            return                                           # a real drag
        for up in (style.OnLeftButtonUp, style.OnMiddleButtonUp, style.OnRightButtonUp):
            up()
        self._press = self._rpress = None

    def _on_rpress(self, *_):
        self._rpress = self.p.iren.get_event_position()

    def _on_rrelease(self, *_):
        if self._rpress is None or self.on_context is None:
            return
        (x0, y0), (x1, y1) = self._rpress, self.p.iren.get_event_position()
        self._rpress = None
        if abs(x1 - x0) > CLICK_TOLERANCE_PX or abs(y1 - y0) > CLICK_TOLERANCE_PX:
            return                          # right-drag zooms; not a click
        name, cell, _ = self.pick_full(x1, y1)
        self.context_hit = (name, self.face_at(name, cell)) if name else None
        if name and name in self.selected_parts and len(self.selected_parts) > 1:
            names = list(self.selected_parts)     # act on the whole selection
        else:
            names = [name] if name else []
        self.on_context(names, [name] if name else [])   # + clicked part

    def _on_press(self, *_):
        self._press = self.p.iren.get_event_position()

    def _on_release(self, *_):
        if self._press is None:
            return
        (x0, y0), (x1, y1) = self._press, self.p.iren.get_event_position()
        self._press = None
        if abs(x1 - x0) > CLICK_TOLERANCE_PX or abs(y1 - y0) > CLICK_TOLERANCE_PX:
            return                          # it was a rotate/drag, not a click
        vi = self.p.iren.interactor
        self.click(x1, y1, additive=bool(vi.GetShiftKey() or vi.GetControlKey()))

    def click(self, x, y, additive=False):
        """What a click at display (x, y) does, depending on the measure mode."""
        name, cell, pos = self.pick_full(x, y)
        if self.face_pick is not None:                # Inflation Layers picks its walls
            self.face_pick(name, self.face_at(name, cell), additive)
            return
        m = self.measure
        if m.mode in ("distance", "point"):
            m.add_point(pos, name, cell)
            return
        if m.mode == "angle":
            m.add_face(pos, name, cell)
            return
        if m.mode == "area" and m.pick_faces and name is None and self.selected_faces:
            self.clear_face_selection()              # click outside -> deselect
            m._changed()
            return
        if m.mode == "area" and m.pick_faces and name and cell is not None \
                and "face_id" in self.model.parts[name].cell_data:
            self.toggle_face(name, int(self.model.parts[name].cell_data["face_id"][cell]),
                             additive)
            m._changed()
            return
        if self.elements.kind != "part":             # Select ▾: a node, an edge, a face…
            self.elements.click(name, cell, pos, additive)
            return
        if additive and name:
            self.toggle_part(name)
        else:
            self.select(name)
        if self.on_pick:
            self.on_pick(list(self.selected_parts))

    def pick(self, x, y):
        """Part name under the display position (x, y), or None."""
        return self.pick_full(x, y)[0]

    def pick_full(self, x, y):
        """(part name, cell id in that part or None, 3D point) under (x, y)."""
        hit = self._hit(self._hw_picker, self._hw_picker.Pick(x, y, 0, self.p.renderer))
        if hit[0] is not None:
            return hit
        # Something else was in front (e.g. the section handle): try a ray pick
        # against parts and cut faces only, ignoring hidden parts.
        self._picker.InitializePickList()
        self._picker.AddPickList(self._surf)
        for a in self.section.cap_actors():
            self._picker.AddPickList(a)
        self._picker.PickFromListOn()
        # Edges only: the faces aren't drawn, but clicking them still selects.
        hidden = not self._surf.GetVisibility() or \
            self._surf.GetProperty().GetRepresentation() != 2
        if hidden:
            self._surf.VisibilityOn()
            self._surf.GetProperty().SetRepresentationToSurface()
        try:
            return self._hit(self._picker, self._picker.Pick(x, y, 0, self.p.renderer))
        finally:
            if hidden:
                self._apply_lines()

    def _hit(self, picker, ok):
        if not ok:
            return None, None, None
        actor, pos = picker.GetActor(), np.array(picker.GetPickPosition())
        if actor is self._surf:
            i = picker.GetFlatBlockIndex() - 1
            if 0 <= i < len(self.names) and self.visible[self.names[i]]:
                n, cell = self.names[i], int(picker.GetCellId())
                shown = self._display.get(n)               # surfaces hidden
                if shown is not None and "orig_id" in shown.cell_data and cell >= 0:
                    cell = int(shown.cell_data["orig_id"][cell])
                return n, cell, pos
            return None, None, None
        name = self.section.cap_owner(actor, picker.GetCellId())
        return (name, None, pos) if name else (None, None, None)
