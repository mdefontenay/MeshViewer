"""The part list: parts that share a base name are grouped under a fold-out row.

"Blue Jay v5", "Blue Jay v5 (2)", … "Blue Jay v5 (14)"  ->  ▸ Blue Jay v5  (15)
"Gear_00" … "Gear_69", "Layer:1" … "Layer:4"            ->  ▸ Gear (70), ▸ Layer (4)
McMaster-Carr parts ("91251A540", "91251A540_Screw:3"…) ->  ▸ McMaster Parts, first of
all, with one sub-group per part number — when Isolate McMaster Parts is on (`mcmaster`;
off by default: they stay in their places). Size / volume limits don't hide them there.

A name is only grouped when at least two parts share its base. A group's
checkbox shows/hides all of it (half-checked when mixed); selecting a group
selects everything in it. Rows are painted by hand (rounded macOS-style
selection, crisp fold-out arrows).

STEP / IGES assemblies come first: the file's own tree (▾ Avbay Assembly ▸ Sub-assembly),
with the groups above made inside each assembly. Rows are sorted by name, size (the
bounding box's diagonal, largest first) or volume (largest first; parts enclosing none
last), `sort_by` / `reverse`. The filter takes a name and size / volume limits
(core/part_filter.py).
"""
from __future__ import annotations

import re
import sys

from PySide6.QtCore import QItemSelectionModel, QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPalette, QPen
from PySide6.QtWidgets import (
    QAbstractItemView, QLineEdit, QStyledItemDelegate, QTreeWidget, QTreeWidgetItem,
)

from meshviewer.core import part_filter
from meshviewer.gui.style import accent
from meshviewer.gui.widgets import color_dot

NAME, MEMBERS = Qt.UserRole, Qt.UserRole + 1
KIND, LABEL = Qt.UserRole + 2, Qt.UserRole + 3   # a group's kind, its name without the count
RENAMABLE = ("group", "assembly")               # not McMaster Parts, not 2D's headings
_SUFFIXES = (re.compile(r"\s*\(\d+\)$"),       # "Part (3)"   — duplicate names
             re.compile(r":\d+$"),             # "Part:3"     — Fusion / Onshape instances
             re.compile(r"\.\d+$"),            # "Part.2"     — solids of one part
             re.compile(r"[\s_\-]+\d+$"))      # "Part_02", "Part 2"
# McMaster-Carr catalogue numbers: digits, one letter, digits — "91251A540", "5536K11".
# At the start of the name (as before), or anywhere in it, as a separate
# word: "Socket Screw 91251A540", "Bracket_8975K12_2". In the middle, the letter
# can't be an x (sizes like "100x200") and at least 2 digits must follow it
# (alloys like "6061T6").
_MCMASTER = re.compile(r"^(\d{3,5}[A-Za-z]\d{1,5})(?=$|[\s_\-:.(,])")
_MCMASTER_ANY = re.compile(r"(?<![A-Za-z0-9])(\d{3,5}[A-WYZa-wyz]\d{2,5})(?![A-Za-z0-9])")
MCMASTER_GROUP = "McMaster Parts"


def group_key(name: str) -> str:
    key = name
    while True:
        new = key
        for pat in _SUFFIXES:
            new = pat.sub("", new)
        if new == key or not new.strip():
            return key.strip() or name
        key = new


def mcmaster_number(name: str):
    """'91251A540' for '91251A540_Socket Head Screw:2' or 'Screw 91251A540 (2)',
    else None."""
    m = _MCMASTER.match(name.strip()) or _MCMASTER_ANY.search(name)
    return m.group(1).upper() if m else None


def is_line_part(poly) -> bool:
    """Lines only (2D boundaries, drawings), no faces."""
    return bool(poly.n_cells) and not poly.GetNumberOfPolys() + poly.GetNumberOfStrips()


def natural(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


# row spacing, chosen in Appearance
DENSITY = {"compact": 0, "comfortable": 6}       # extra pixels per row


class _RowDelegate(QStyledItemDelegate):
    extra = 0

    def createEditor(self, parent, option, index):
        """an opaque rename field (style.py #RenameField), so the old name
        doesn't show through in dark mode."""
        ed = QLineEdit(parent)
        ed.setObjectName("RenameField")
        ed.setFrame(False)
        return ed

    def setEditorData(self, editor, index):
        label = index.data(LABEL)                   # a group: its name, not "(27)"
        editor.setText(label if label is not None else index.data(Qt.DisplayRole))

    def sizeHint(self, option, index):
        s = super().sizeHint(option, index)
        return QSize(s.width(), s.height() + self.extra)


class PartTree(QTreeWidget):
    visibility_changed = Signal(list, bool)     # names, shown?
    selection_changed = Signal(list)            # names
    zoom_requested = Signal(list)
    isolate_requested = Signal(list)
    context_requested = Signal(list, list, object)   # names, clicked row's names, position
    rename_requested = Signal(str, str)              # old name, new name
    group_rename_requested = Signal(str, str, str, list)   # kind, old, new, its parts

    ROW_RADIUS = 6.0

    def sizeHint(self):
        """Small: the sidebar's sections get their height first, the list the rest."""
        return QSize(super().sizeHint().width(), 150)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("PartList")
        self.setHeaderHidden(True)
        self.setColumnCount(1)
        self.setFrameShape(QTreeWidget.NoFrame)
        self.setIconSize(QSize(12, 12))
        self.setIndentation(13)                     # compact: deep assemblies fit
        self._delegate = _RowDelegate(self)
        self.setItemDelegate(self._delegate)
        self.setUniformRowHeights(True)
        self.setRootIsDecorated(True)
        self.setMouseTracking(True)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)     # ⌘/⇧-click
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)   # rename: menu / Return
        self.customContextMenuRequested.connect(self._context_menu)
        self.itemChanged.connect(self._item_changed)
        self.itemSelectionChanged.connect(
            lambda: self.selection_changed.emit(self.selected_names()))
        self.itemDoubleClicked.connect(lambda it, _c: self.zoom_requested.emit(self._names(it)))
        self._parts = {}                            # name -> item
        self.sort_by, self.reverse = "name", False  # name / size / volume
        self.mcmaster = False                       # Isolate McMaster Parts
        self._scene = None
        self._hover = None
        self._arrow_click = False                  # press handled by the arrow code
        self._context_row = None                   # row right-clicked (menu open)
        self.context_group = None                  # …when it is a group that can be renamed
        self._hide_native_selection()

    # ---- row spacing ------------------------------------------------
    def set_density(self, density):
        extra = DENSITY.get(density, 0)
        if extra != self._delegate.extra:
            self._delegate.extra = extra
            self.doItemsLayout()                    # rows have uniform height: re-measure

    # ---- building ---------------------------------------------------------------
    def populate(self, scene):
        self._scene = scene
        self.blockSignals(True)
        self.clear()
        self._parts = {}
        if scene.model.file_type == "mesh2d":       # 2D: areas and lines, apart
            self._fill_2d(scene)
            self.blockSignals(False)
            return
        names = list(scene.names)
        if self.mcmaster:                           # Isolate McMaster Parts: on top
            mcm = [n for n in names if mcmaster_number(n)]
            if mcm:
                top = self._group_item(MCMASTER_GROUP, mcm,
                                       f"{len(mcm)} McMaster-Carr parts (by part number)",
                                       kind="mcmaster")
                self.addTopLevelItem(top)
                self._fill(scene, top, mcm, key=mcmaster_number)
            names = [n for n in names if not mcmaster_number(n)]
        paths = {n: tuple(scene.part_meta(n).get("path", ())) for n in names}
        if any(paths.values()):                     # STEP / IGES: the file's assemblies
            self._fill_tree(scene, None, names, paths, 0)
        else:
            self._fill_auto(scene, None, names)
        for g in self.groups():                    # children first, then their parents
            self._update_group(g)
        self.blockSignals(False)

    def _fill_auto(self, scene, parent, names):
        """The parts grouped by their base name."""
        self._fill(scene, parent, names, key=group_key)

    def _fill_tree(self, scene, parent, names, paths, depth):
        """The file's assemblies (a row each, holding all below it), then the parts
        right in this one, grouped as usual."""
        subs, here = {}, []
        for n in names:
            p = paths[n]
            (subs.setdefault(p[depth], []) if len(p) > depth else here).append(n)
        for label, members in self._sorted(scene, list(subs.items())):
            shown = scene.group_names.get(label, label)       # renamed in the list
            item = self._group_item(shown, members, "Assembly", kind="assembly")
            item.setData(0, Qt.UserRole + 4, label)           # the file's name for it
            parent.addChild(item) if parent is not None else self.addTopLevelItem(item)
            self._fill_tree(scene, item, members, paths, depth + 1)
            if depth == 0:
                item.setExpanded(True)              # the top assembly opens
        if here:
            self._fill_auto(scene, parent, here)

    # ---- order: name, size or volume -------------------------------------------------
    def _value(self, scene, names):
        """What a row is sorted by (None: no volume)."""
        if self.sort_by == "size":
            return max(scene.part_size(n) for n in names)
        vols = [scene.part_volume(n) for n in names]
        vols = [v for v in vols if v is not None]
        return sum(vols) if vols else None

    def _sorted(self, scene, rows):
        """rows: [(label, names)] in the order chosen. Numbers: largest first (Reverse:
        smallest), rows without a volume last either way."""
        if self.sort_by == "name" or scene is None:
            return sorted(rows, key=lambda r: natural(r[0]), reverse=self.reverse)
        val = {r[0]: self._value(scene, r[1]) for r in rows}
        sign = 1.0 if self.reverse else -1.0
        return sorted(rows, key=lambda r: (val[r[0]] is None,
                                           sign * val[r[0]] if val[r[0]] is not None else 0.0,
                                           natural(r[0])))

    def _fill_2d(self, scene):
        """2D meshes: Faces (the cells: areas) and Boundaries (the lines), each a group."""
        kinds = (("Faces", "The mesh cells (areas)", False),
                 ("Boundaries", "The boundary lines", True))
        for title, tip, lines in kinds:
            names = [n for n in scene.names if is_line_part(scene.model.parts[n]) == lines]
            if not names:
                continue
            top = self._group_item(title, names, tip, kind="heading")
            self.addTopLevelItem(top)
            self._fill(scene, top, names, key=group_key)
            top.setExpanded(True)
        for g in self.groups():
            self._update_group(g)

    def _fill(self, scene, parent, names, key):
        buckets = {}
        for n in names:
            buckets.setdefault(key(n), []).append(n)
        for k, members in self._sorted(scene, list(buckets.items())):
            members[:] = [n for n, _ in self._sorted(scene, [(n, [n]) for n in members])]
            if len(members) == 1:
                item = self._part_item(scene, members[0])
            else:
                item = self._group_item(k, members, f"{len(members)} parts named “{k}…”",
                                        kind="group" if key is group_key else "mcmaster")
                for n in members:
                    item.addChild(self._part_item(scene, n))
            parent.addChild(item) if parent is not None else self.addTopLevelItem(item)

    @staticmethod
    def _group_item(label, members, tip, kind="group"):
        g = QTreeWidgetItem([f"{label}   ({len(members)})"])
        g.setData(0, MEMBERS, list(members))
        g.setData(0, KIND, kind)
        g.setData(0, LABEL, label)
        flags = g.flags() | Qt.ItemIsUserCheckable
        if kind in RENAMABLE:
            flags |= Qt.ItemIsEditable                    # Rename Group…, Return
        g.setFlags(flags)
        g.setToolTip(0, tip)
        return g

    def _part_item(self, scene, name):
        it = QTreeWidgetItem([name])
        it.setIcon(0, color_dot(scene.colors[name]))
        it.setData(0, NAME, name)
        it.setFlags(it.flags() | Qt.ItemIsUserCheckable | Qt.ItemIsEditable)
        it.setCheckState(0, Qt.Checked if scene.visible[name] else Qt.Unchecked)
        it.setToolTip(0, f"{name}\n{scene.info(name)}")
        self._parts[name] = it
        return it

    # ---- helpers --------------------------------------------------------------------
    @staticmethod
    def _names(item):
        return list(item.data(0, MEMBERS) or [item.data(0, NAME)])

    def set_color(self, name, hex_color):
        """new colour dot for a part."""
        if name in self._parts:
            self._parts[name].setIcon(0, color_dot(hex_color))

    def groups(self):
        """Every group row, deepest first (so parents are updated after children)."""
        out = []

        def walk(item):
            for i in range(item.childCount()):
                walk(item.child(i))
            if item.data(0, MEMBERS):
                out.append(item)
        for i in range(self.topLevelItemCount()):
            walk(self.topLevelItem(i))
        return out

    def selected_names(self):
        out = []
        for it in self.selectedItems():
            out += [n for n in self._names(it) if n not in out]
        return out

    @staticmethod
    def _update_group(g):
        states = {g.child(i).checkState(0) for i in range(g.childCount())}
        g.setCheckState(0, states.pop() if len(states) == 1 else Qt.PartiallyChecked)

    def _update_ancestors(self, item):
        p = item.parent()
        while p is not None:
            self._update_group(p)
            p = p.parent()

    # --- rename in place (right-click ▸ Rename…, or Return) ---------------
    def start_rename(self, name):
        it = self._parts.get(name)
        if it is None or it.isHidden():
            return False
        p = it.parent()
        while p is not None:
            p.setExpanded(True)
            p = p.parent()
        self.scrollToItem(it)
        self.setCurrentItem(it)
        self.editItem(it, 0)
        return True

    def keyPressEvent(self, e):
        names = self.selected_names()
        if e.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_F2) \
                and self.state() != QAbstractItemView.EditingState:
            items = self.selectedItems()
            if len(items) == 1 and items[0].data(0, KIND) in RENAMABLE:
                self.start_group_rename(items[0])          # a group row: its name
                e.accept()
                return
            if len(names) == 1 and self.start_rename(names[0]):
                e.accept()
                return
        super().keyPressEvent(e)

    def start_group_rename(self, item):
        """Edit a group's name in place (its parts are renamed, or the assembly)."""
        if item is None or item.data(0, KIND) not in RENAMABLE:
            return False
        self.scrollToItem(item)
        self.setCurrentItem(item)
        self.editItem(item, 0)
        return True

    # ---- checkboxes ----------------------------------------------------------------
    def _item_changed(self, it, _col):
        kind = it.data(0, KIND)
        label = it.data(0, LABEL)
        shown = f"{label}   ({len(it.data(0, MEMBERS) or [])})"
        if kind in RENAMABLE and label is not None and it.text(0) != shown:   # typed a name
            new = re.sub(r"\s*\(\d+\)\s*$", "", it.text(0)).strip()
            self.blockSignals(True)
            it.setText(0, shown)                     # the scene decides; the list refills
            self.blockSignals(False)
            old = it.data(0, Qt.UserRole + 4) if kind == "assembly" else label
            members = list(it.data(0, MEMBERS) or [])
            if new and new != label:
                QTimer.singleShot(0, lambda: self.group_rename_requested.emit(
                    kind, old, new, members))
            return
        name = it.data(0, NAME)
        if name is not None and it.text(0) != name:  # typed a new name
            new = it.text(0).strip()
            self.blockSignals(True)
            it.setText(0, name)                      # the scene decides; the list refills
            self.blockSignals(False)
            if new:                                  # after the editor has closed
                QTimer.singleShot(0, lambda: self.rename_requested.emit(name, new))
            return
        on = it.checkState(0) == Qt.Checked
        self.blockSignals(True)
        if it.data(0, MEMBERS):                      # a group: apply to everything in it
            if it.checkState(0) == Qt.PartiallyChecked:
                it.setCheckState(0, Qt.Checked)
                on = True

            def apply(item):
                for i in range(item.childCount()):
                    c = item.child(i)
                    c.setCheckState(0, Qt.Checked if on else Qt.Unchecked)
                    apply(c)
            apply(it)
        self._update_ancestors(it)
        self.blockSignals(False)
        self.visibility_changed.emit(self._names(it), on)

    def sync_checks(self, visible):
        self.blockSignals(True)
        for n, it in self._parts.items():
            it.setCheckState(0, Qt.Checked if visible.get(n) else Qt.Unchecked)
        for g in self.groups():
            self._update_group(g)
        self.blockSignals(False)

    # ---- selection from outside (click in 3D) -----------------------------------------
    def set_selected(self, names):
        self.blockSignals(True)
        self.clearSelection()
        last = None
        for n in names:
            it = self._parts.get(n)
            if it is None:
                continue
            p = it.parent()
            while p is not None:
                p.setExpanded(True)
                p = p.parent()
            it.setSelected(True)
            last = it
        if last is not None:
            self.setCurrentItem(last, 0, QItemSelectionModel.NoUpdate)
            self.scrollToItem(last)
        self.blockSignals(False)
        return any(self._parts[n].isHidden() for n in names if n in self._parts)

    # ---- filter -------------------------------------------------------------------
    def apply_filter(self, text, scale=1.0):
        """A name (in a row's name, or a group's) and size / volume limits, in the
        toolbar's unit (`scale`: model units -> it)."""
        t, limits = part_filter.parse(text)
        sc = self._scene

        def fits(name):
            if not limits or sc is None or name not in sc.model.parts:
                return True
            vals = {"size": sc.part_size(name) * scale}
            if any(p == "volume" for p, *_ in limits):
                v = sc.part_volume(name)
                vals["volume"] = None if v is None else v * scale ** 3
            return part_filter.passes(vals, limits)

        def walk(item, parent_hit, mcm=False):
            hit = parent_hit or not t or t in item.text(0).lower()
            mcm = mcm or item.data(0, Qt.UserRole + 2) == "mcmaster"
            if not item.data(0, MEMBERS):
                hit = hit and (mcm or fits(item.data(0, NAME)))   # McMaster: no limits
                item.setHidden(not hit)
                return hit
            shown = sum(walk(item.child(j), hit, mcm) for j in range(item.childCount()))
            item.setHidden(shown == 0)
            if (t or limits) and shown:
                item.setExpanded(True)
            return shown > 0
        for i in range(self.topLevelItemCount()):
            walk(self.topLevelItem(i), False)

    # ---- context menu (built by the sidebar, shared with the 3D view) ---------------
    def _context_menu(self, pos):
        it = self.itemAt(pos)
        if it is None:
            return
        clicked = self._names(it)
        sel = self.selected_names()
        # Right-click inside a multi-selection acts on the selection (like Finder);
        # elsewhere only on the row clicked. The selection itself never changes.
        names = sel if it.isSelected() and len(sel) > 1 else clicked
        self._context_row = self.indexFromItem(it)    # outline while the menu is open
        self.context_group = it if it.data(0, KIND) in RENAMABLE else None
        self.viewport().update()
        try:
            self.context_requested.emit(names, clicked, self.viewport().mapToGlobal(pos))
        finally:                                      # (the menu runs inside this call)
            self._context_row = None
            self.context_group = None
            self.viewport().update()

    # ---- painting: rounded selection, crisp arrows --------------------------------------
    def _hide_native_selection(self):
        pal = self.palette()
        for group in (QPalette.Active, QPalette.Inactive):
            pal.setColor(group, QPalette.Highlight, QColor(0, 0, 0, 0))
            pal.setColor(group, QPalette.HighlightedText, QColor("white"))
        self.setPalette(pal)

    def changeEvent(self, e):
        super().changeEvent(e)
        if e.type() in (e.Type.ApplicationPaletteChange, e.Type.StyleChange):
            self._hide_native_selection()

    # ---- bigger target for the fold-out arrow ---------------------------------------
    def _arrow_hit(self, e):
        """A group row clicked anywhere left of its checkbox (the whole indent,
        not just the 20 px arrow cell) -> that click opens / closes the group."""
        if e.button() != Qt.LeftButton or e.modifiers() & (Qt.ShiftModifier | Qt.ControlModifier
                                                           | Qt.MetaModifier):
            return None
        pos = e.position().toPoint()
        idx = self.indexAt(pos)
        item = self.itemFromIndex(idx) if idx.isValid() else None
        if item is None or item.childCount() == 0:
            return None
        return item if pos.x() < self.visualRect(idx).left() + 2 else None

    @staticmethod
    def _is_context_click(e):
        """Right button, or Control-click on a Mac (Qt reports it as Meta + left)."""
        return e.button() == Qt.RightButton or (
            sys.platform == "darwin" and e.button() == Qt.LeftButton
            and e.modifiers() & Qt.MetaModifier)

    def mousePressEvent(self, e):
        if self._is_context_click(e):                # right-click doesn't select
            e.accept()
            return
        item = self._arrow_hit(e)
        if item is None:
            super().mousePressEvent(e)
            return
        item.setExpanded(not item.isExpanded())
        self._arrow_click = True
        e.accept()

    def mouseDoubleClickEvent(self, e):
        item = self._arrow_hit(e)
        if item is None:
            super().mouseDoubleClickEvent(e)
            return
        item.setExpanded(not item.isExpanded())     # quick second click = toggle again
        self._arrow_click = True
        e.accept()

    def mouseReleaseEvent(self, e):
        if self._is_context_click(e):
            e.accept()
            return
        # FIX: on macOS Qt toggles a group on *release* of an arrow click,
        # which closed the group we had just opened on press. Swallow that release.
        if self._arrow_click:
            self._arrow_click = False
            e.accept()
            return
        super().mouseReleaseEvent(e)

    def mouseMoveEvent(self, e):
        idx = self.indexAt(e.position().toPoint())
        if idx != self._hover:
            self._hover = idx if idx.isValid() else None
            self.viewport().update()
        super().mouseMoveEvent(e)

    def leaveEvent(self, e):
        self._hover = None
        self.viewport().update()
        super().leaveEvent(e)

    def drawRow(self, painter, option, index):
        sm = self.selectionModel()
        selected = sm.isSelected(index)
        if selected or index == self._hover:
            r = QRectF(option.rect).adjusted(0, 0.5, 0, -0.5)
            r.setLeft(2)
            r.setRight(self.viewport().width() - 2)
            painter.save()
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(Qt.NoPen)
            if selected:
                color = QColor(accent())                  # vivid in light mode
                above, below = self.indexAbove(index), self.indexBelow(index)
                join_up = above.isValid() and sm.isSelected(above)
                join_down = below.isValid() and sm.isSelected(below)
            else:
                dark = self.palette().color(QPalette.Window).lightness() < 128
                color = QColor(255, 255, 255, 22) if dark else QColor(0, 0, 0, 14)
                join_up = join_down = False
            painter.setBrush(color)
            painter.drawRoundedRect(r, self.ROW_RADIUS, self.ROW_RADIUS)
            # Consecutive selected rows merge into one block (like Finder).
            if join_up:
                painter.drawRect(QRectF(r.left(), r.top() - 0.5, r.width(), r.height() / 2 + 0.5))
            if join_down:
                painter.drawRect(QRectF(r.left(), r.center().y(), r.width(), r.height() / 2 + 0.5))
            painter.restore()
        if self._context_row is not None and index == self._context_row:
            # Finder-style: the right-clicked row gets an accent outline, not a selection.
            r = QRectF(option.rect).adjusted(0, 1, 0, -1)
            r.setLeft(3)
            r.setRight(self.viewport().width() - 3)
            painter.save()
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setPen(QPen(QColor("white") if selected else QColor(accent()), 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(r, self.ROW_RADIUS - 1, self.ROW_RADIUS - 1)
            painter.restore()
        super().drawRow(painter, option, index)

    def drawBranches(self, painter, rect, index):
        item = self.itemFromIndex(index)
        if item is None or item.childCount() == 0:
            return                                   # no lines, no native decorations
        selected = self.selectionModel().isSelected(index)
        color = QColor("white") if selected else self.palette().color(QPalette.PlaceholderText)
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(color, 1.6)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)
        cx = rect.right() - self.indentation() / 2 + 1
        cy = rect.center().y() + 0.5
        painter.translate(cx, cy)
        painter.rotate(90 if item.isExpanded() else 0)
        path = QPainterPath(QPointF(-1.5, -3.5))
        path.lineTo(QPointF(2.0, 0.0))
        path.lineTo(QPointF(-1.5, 3.5))
        painter.drawPath(path)
        painter.restore()
