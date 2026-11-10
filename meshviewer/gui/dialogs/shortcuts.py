"""Help ▸ Keyboard Shortcuts: every menu item that has a shortcut, menu by menu, read
from the menu bar itself (so the list is never out of date)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QDialog, QGridLayout, QLabel, QScrollArea, QVBoxLayout, QWidget,
)


def shortcuts(menubar, app_actions=()):
    """[(menu title, [(item, keys)])] for the menus that have any. app_actions: the app
    menu's items (macOS keeps them in a menu bar of their own)."""
    out = []
    first = [(a.text(), a.shortcut().toString(QKeySequence.NativeText)) for a in app_actions
             if not a.shortcut().isEmpty()]
    if first:
        out.append(("Mesh Viewer", first))

    def walk(menu, prefix, rows):
        for a in menu.actions():
            if a.menu() is not None:
                walk(a.menu(), f"{prefix}{a.menu().title()} ▸ ", rows)
            elif not a.isSeparator() and a.isVisible() and not a.shortcut().isEmpty():
                keys = "   ".join(k.toString(QKeySequence.NativeText) for k in a.shortcuts())
                rows.append((prefix + a.text().replace("&", ""), keys))

    for top in menubar.actions():
        if top.menu() is None:
            continue
        rows = []
        walk(top.menu(), "", rows)
        if rows:
            out.append((top.menu().title(), rows))
    return out


class ShortcutsDialog(QDialog):
    def __init__(self, parent, menubar, app_actions=()):
        super().__init__(parent)
        self.setWindowTitle("Keyboard Shortcuts")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        body = QWidget()
        g = QGridLayout(body)
        g.setContentsMargins(22, 16, 22, 18)
        g.setHorizontalSpacing(28)
        g.setVerticalSpacing(5)
        r = 0
        seen = set()
        for title, rows in shortcuts(menubar, app_actions):
            rows = [r for r in rows if r not in seen]          # (Linux: in both lists)
            seen.update(rows)
            if not rows:
                continue
            head = QLabel(title)
            head.setObjectName("GroupTitle")
            g.addWidget(head, r, 0, 1, 2)
            r += 1
            for text, keys in rows:
                g.addWidget(QLabel(text), r, 0)
                k = QLabel(keys)
                k.setObjectName("InfoLine")
                k.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                g.addWidget(k, r, 1)
                r += 1
            g.setRowMinimumHeight(r, 10)
            r += 1
        scroll.setWidget(body)
        lay.addWidget(scroll)
        self.resize(420, 560)
