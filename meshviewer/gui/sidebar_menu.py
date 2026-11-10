"""Sidebar ▸ what a right-click on a part offers (in the list and in the 3D view): hide,
isolate, zoom, color, rename, McMaster search. Changes go through Edit ▸ Undo."""
from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox

from meshviewer.gui.panels.parts import is_line_part, mcmaster_number
from meshviewer.gui.sheets import ask_color, ask_text
from meshviewer.gui.widgets import Menu


class PartMenu:
    def part_menu(self, names, clicked, global_pos):
        """names: what Hide / Isolate / Zoom act on (the selection when right-clicking
        inside it); clicked: the row / part under the cursor (McMaster search)."""
        if not self.scene:
            return
        names = [n for n in names if n in self.scene.visible]
        clicked = [n for n in clicked if n in self.scene.visible]
        menu = Menu(self)
        if names:
            title = names[0] if len(names) == 1 else f"{len(names)} parts"
            head = menu.addAction(title)
            head.setEnabled(False)
            what = self._menu_word(names)
            menu.addAction(f"Hide{what}", lambda: self._visibility_changed(names, False))
            hit = self.scene.context_hit                 # the CAD face under the cursor
            if hit and hit[1] is not None and hit[0] in names:
                menu.addAction("Hide Face", lambda h=hit: self._hide_face(*h))
            menu.addAction(f"Isolate{what}", lambda: self._isolate(names))
            menu.addAction("Zoom To", lambda: self.scene.zoom_to(names))
            if len(names) == 1 and clicked == names:
                menu.addAction("Rename…", lambda: self.rename(names[0]))
            menu.addAction("Color…", lambda: self.choose_color(names))
            # McMaster-Carr parts -> open their catalogue page
            # only the part / group that was right-clicked, not the selection
            numbers = sorted({mcmaster_number(n) for n in clicked} - {None})
            if len(numbers) == 1:
                menu.addSeparator()
                menu.addAction(f"Search in McMaster  ({numbers[0]})",
                               lambda pn=numbers[0]: open_mcmaster(pn))
            elif numbers:
                menu.addSeparator()
                sub = Menu(menu)
                sub.setTitle("Search in McMaster")
                for pn in numbers[:15]:
                    sub.addAction(pn, lambda pn=pn: open_mcmaster(pn))
                menu.addMenu(sub)
            menu.addSeparator()
        menu.addAction("Show All", lambda: self._set_all(True))
        k = self.scene.n_hidden_faces
        if k:
            menu.addAction(f"Show Hidden Faces ({k})", self._show_faces)
        menu.addAction("Fit View", self.scene.fit)
        menu.exec(global_pos)
        self.scene.context_hit = None
        self.scene.end_stuck_drag()            # no zoom mode left behind

    def _menu_word(self, names):
        """" Part", " 3 Parts"; 2D meshes: " Face" (the cells) / " Boundary" (a line)."""
        word, words = "Part", "Parts"
        if self.scene.model.file_type == "mesh2d":
            lines = {is_line_part(self.scene.model.parts[n]) for n in names}
            if lines == {True}:
                word, words = "Boundary", "Boundaries"
            elif lines == {False}:
                word, words = "Face", "Faces"
        return f" {word}" if len(names) == 1 else f" {len(names)} {words}"

    def _section_for_colors(self):
        """Colour by quality on a volume mesh: the colours show on the cut."""
        sp = self.section_panel
        self.show_section("section")
        if not sp.enable.isChecked():
            sp.enable.setChecked(True)
        if not sp.fill.isChecked():
            sp.fill.setChecked(True)

    def choose_color(self, names):
        if not self.scene or not names:
            return
        title = names[0] if len(names) == 1 else f"{len(names)} parts"
        self.scene.end_stuck_drag()
        ask_color(self.window(), self.scene.colors[names[0]], f"Color of {title}",
                  lambda c: self._set_color(names, c))

    def _set_color(self, names, c):
        if not self.scene:
            return
        if self.changes is not None:
            self.changes.color(names, c)                # Edit ▸ Undo Color
            return
        self.scene.set_color(names, c)
        for n in names:
            self.list.set_color(n, self.scene.colors[n])
        self.cfd_panel.refresh_colors()                # Boundary menu dots
        self.inflation_panel.refresh_colors()          # Walls menu dots

    def rename(self, name):
        """Edit the name in the list (or, with the sidebar hidden, in a small dialog)."""
        if not self.scene:
            return
        if self.isVisible():
            self.parts_section.set_expanded(True)
            if self.list.start_rename(name):
                return
            self.filter.clear()                       # filtered out: show it, try again
            if self.list.start_rename(name):
                return
        ask_text(self.window(), "Rename", "New name:", name, lambda new: self._rename(name, new))

    def _rename(self, old, new):
        new = new.strip()
        if not self.scene or not new or new == old:
            return
        if new in self.scene.model.parts:
            QMessageBox.warning(self.window(), "Rename",
                                f"There is already a {self._one_part()} named “{new}”.")
            return
        if self.changes is not None:
            self.changes.rename(old, new)              # Edit ▸ Undo Rename
        elif self.scene.rename_part(old, new):
            self.refresh_parts()
            self.renamed.emit()

    def _hide_face(self, name, face_id):
        hidden = {k: set(v) for k, v in self.scene.hidden_faces.items()}
        hidden.setdefault(name, set()).add(int(face_id))
        if self.changes is not None:
            self.changes.faces(hidden, "Hide Face")
        else:
            self.scene.hide_face(name, face_id)

    def _show_faces(self):
        if self.changes is not None:
            self.changes.faces({}, "Show Hidden Faces")
        else:
            self.scene.show_faces()

    def _one_part(self):
        return self.scene.model.item_words[0]


def open_mcmaster(part_number):
    QDesktopServices.openUrl(QUrl(f"https://www.mcmaster.com/{part_number}"))
