"""Questions asked in a sheet: it slides down from the window it is about (macOS), and
the rest of the app keeps working. Qt's one-line helpers (QFileDialog.getSaveFileName…)
open a separate window that blocks the whole app instead.

Each function returns at once; `done(answer)` is called when the sheet is closed with
OK / Save (not on Cancel).

    ask_save(window, "Export", "/path/name.stl", "STL (*.stl)", done)     done(path)
    ask_open(window, "Import Points", folder, "CSV (*.csv)", done)        done(path)
    ask_text(window, "Rename Plot", "Name", "Root", done)                 done(text)
    ask_color(window, "#ff0000", "Color of Wing", done)                   done("#rrggbb")
    save_folder(path)       where to save next to a file (Documents for the bundled samples)
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QStandardPaths, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QColorDialog, QFileDialog, QInputDialog

from meshviewer.gui.samples import is_sample


def _sheet(window, dialog):
    dialog.setWindowModality(Qt.WindowModal)
    window._sheet = dialog                    # kept alive while it shows
    dialog.open()
    return dialog


def save_folder(path):
    """The folder of `path`, or Documents for a sample (inside the app: read-only)."""
    if path is None or is_sample(path):
        return Path(QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation))
    return Path(path).parent


def ask_save(window, title, default, filters, done):
    d = QFileDialog(window, title, str(default), filters)
    d.setAcceptMode(QFileDialog.AcceptSave)
    d.setFileMode(QFileDialog.AnyFile)
    d.fileSelected.connect(lambda fn: fn and done(fn))
    return _sheet(window, d)


def ask_open(window, title, folder, filters, done):
    d = QFileDialog(window, title, str(folder or ""), filters)
    d.setAcceptMode(QFileDialog.AcceptOpen)
    d.setFileMode(QFileDialog.ExistingFile)
    d.fileSelected.connect(lambda fn: fn and done(fn))
    return _sheet(window, d)


def ask_text(window, title, label, text, done):
    d = QInputDialog(window)
    d.setWindowTitle(title)
    d.setLabelText(label)
    d.setTextValue(text)
    d.textValueSelected.connect(done)
    return _sheet(window, d)


def ask_color(window, initial, title, done):
    d = QColorDialog(QColor(initial), window)
    d.setWindowTitle(title)
    d.colorSelected.connect(lambda c: c.isValid() and done(c.name()))
    return _sheet(window, d)
