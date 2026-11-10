"""What an empty window shows: a way in for someone who has never used the app.

    ┌────────────────────────────────────────────┐
    │            [icon]  Mesh Viewer              │
    │                 2.5 beta 1                  │
    │                 [ Open… ]                   │
    │     or drop a mesh or CAD file here         │
    │                                             │
    │  Recent                Try a Sample         │
    │  wing.cgns  ~/CFD      ONERA M6 Wing        │
    │  …                     Avionics Bay         │
    └────────────────────────────────────────────┘

While a file opens, only "Opening wing.cgns…" stays. The same recent files are in
File ▸ Open Recent, the same samples in File ▸ Open Sample (gui/samples.py).
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from meshviewer import version_label
from meshviewer.gui.samples import available

RECENT_SHOWN = 6


def _row(title, detail, tip):
    """A list row: the name, a gray detail under it; the whole row is a button."""
    b = QPushButton()
    b.setObjectName("WelcomeRow")
    b.setCursor(Qt.PointingHandCursor)
    b.setFlat(True)
    b.setToolTip(tip)
    b.setAccessibleName(title)
    b.setAccessibleDescription(detail)
    lay = QVBoxLayout(b)
    lay.setContentsMargins(10, 6, 10, 6)
    lay.setSpacing(1)
    t = QLabel(title)
    t.setObjectName("WelcomeRowTitle")
    d = QLabel(detail)
    d.setObjectName("InfoLine")
    for lab in (t, d):
        lab.setAttribute(Qt.WA_TransparentForMouseEvents)
        lay.addWidget(lab)
    b.setMinimumHeight(t.sizeHint().height() + d.sizeHint().height() + 14)
    b.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
    return b


def _short(folder):
    home = str(Path.home())
    s = str(folder)
    return "~" + s[len(home):] if s.startswith(home) else s


class Welcome(QWidget):
    open_file = Signal(str)          # a path: a recent file or a sample
    open_dialog = Signal()           # Open…

    def __init__(self, recent, parent=None):
        """recent: a function giving the recent files (newest first)."""
        super().__init__(parent)
        self.setObjectName("Welcome")
        self._recent = recent
        outer = QVBoxLayout(self)
        outer.addStretch(2)
        head = QVBoxLayout()
        head.setSpacing(6)
        self.icon = QLabel()
        self.icon.setAlignment(Qt.AlignCenter)
        ico = QApplication.windowIcon()
        if not ico.isNull():
            self.icon.setPixmap(ico.pixmap(QSize(72, 72)))
        head.addWidget(self.icon)
        title = QLabel("Mesh Viewer")
        title.setObjectName("WelcomeTitle")
        title.setAlignment(Qt.AlignCenter)
        head.addWidget(title)
        version = QLabel(version_label())
        version.setObjectName("InfoLine")
        version.setAlignment(Qt.AlignCenter)
        head.addWidget(version)
        outer.addLayout(head)
        outer.addSpacing(14)
        self.open = QPushButton("Open…")
        self.open.setObjectName("ApplyButton")
        self.open.setCursor(Qt.PointingHandCursor)
        self.open.setMinimumWidth(160)
        self.open.setToolTip("Open a mesh or a CAD file  (⌘O)")
        self.open.clicked.connect(self.open_dialog.emit)
        outer.addWidget(self.open, 0, Qt.AlignCenter)
        self.hint = QLabel("or drop a mesh or CAD file here")
        self.hint.setObjectName("EmptyState")
        self.hint.setAlignment(Qt.AlignCenter)
        outer.addWidget(self.hint)
        outer.addSpacing(22)

        self.lists = QWidget()
        cols = QHBoxLayout(self.lists)
        cols.setContentsMargins(0, 0, 0, 0)
        cols.setSpacing(36)
        cols.addStretch(1)
        self.recent_col = QVBoxLayout()
        self.recent_col.setSpacing(2)
        self.samples_col = QVBoxLayout()
        self.samples_col.setSpacing(2)
        for col in (self.recent_col, self.samples_col):
            box = QWidget()
            box.setFixedWidth(300)
            box.setLayout(col)
            cols.addWidget(box, 0, Qt.AlignTop)
        cols.addStretch(1)
        outer.addWidget(self.lists)
        outer.addStretch(3)
        self.status = QLabel("")                      # "Opening wing.cgns…"
        self.status.setObjectName("EmptyState")
        self.status.setAlignment(Qt.AlignCenter)
        self.status.setVisible(False)
        outer.insertWidget(outer.indexOf(self.lists), self.status)
        self._fill_samples()
        self.idle()

    # ---- states ------------------------------------------------------------------------
    def idle(self):
        """Nothing open: the way in."""
        self.status.setVisible(False)
        for w in (self.open, self.hint, self.lists):
            w.setVisible(True)
        self._fill_recent()

    def opening(self, name):
        self.status.setText(f"Opening {name}…")
        self.status.setVisible(True)
        for w in (self.open, self.hint, self.lists):
            w.setVisible(False)

    # ---- the two lists --------------------------------------------------------------------
    def _clear(self, col):
        while col.count():
            w = col.takeAt(0).widget()
            if w is not None:
                w.hide()
                w.setParent(None)
                w.deleteLater()

    def _heading(self, col, text):
        h = QLabel(text)
        h.setObjectName("GroupTitle")
        col.addWidget(h)

    def _fill_recent(self):
        self._clear(self.recent_col)
        files = [Path(f) for f in self._recent()][:RECENT_SHOWN]
        self._heading(self.recent_col, "Recent")
        if not files:
            none = QLabel("Files you open will be listed here.")
            none.setObjectName("InfoLine")
            self.recent_col.addWidget(none)
        for f in files:
            b = _row(f.name, _short(f.parent), str(f))
            b.clicked.connect(lambda _=False, p=str(f): self.open_file.emit(p))
            self.recent_col.addWidget(b)
        self.recent_col.addStretch(1)

    def _fill_samples(self):
        self._clear(self.samples_col)
        samples = available()
        self._heading(self.samples_col, "Try a Sample")
        if not samples:
            none = QLabel("No samples in this copy of the app.")
            none.setObjectName("InfoLine")
            self.samples_col.addWidget(none)
        for title, what, path in samples:
            b = _row(title, what, f"Open the {title} sample")
            b.clicked.connect(lambda _=False, p=str(path): self.open_file.emit(p))
            self.samples_col.addWidget(b)
        self.samples_col.addStretch(1)


def add_sample_menu(menu, open_path):
    """File ▸ Open Sample ▸ the same samples as the welcome screen."""
    sub = menu.addMenu("Open Sample")
    for title, _what, path in available():
        sub.addAction(title, lambda p=path: open_path(Path(p)))
    sub.setEnabled(bool(available()))
    return sub

