"""Where the app saves its settings and the memory of each file.

    settings()        a QSettings: on macOS ~/Library/Preferences/local.Mesh Viewer.plist

The tests set MESHVIEWER_SETTINGS to a scratch file, so running them never touches
what the app remembers for you.
"""
from __future__ import annotations

import os

from PySide6.QtCore import QSettings


def settings() -> QSettings:
    path = os.environ.get("MESHVIEWER_SETTINGS")
    if path:
        return QSettings(path, QSettings.IniFormat)
    return QSettings("local", "Mesh Viewer")
