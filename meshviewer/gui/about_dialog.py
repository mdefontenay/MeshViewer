"""NEW (v2.15): "About Mesh Viewer" — small window with the icon, version,
credits and the versions of the main libraries."""
from __future__ import annotations

import os
import platform
import sys
from importlib import metadata
from pathlib import Path

from PySide6 import __version__ as PYSIDE_VERSION
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QVBoxLayout

from .. import __version__

AUTHOR = "Matthieu de Fontenay"
BUILT_WITH = "Claude Opus 5.5"


def _app_icon() -> QIcon:
    """The .icns from the source folder, or from the app bundle's Resources."""
    here = Path(__file__).resolve()
    candidates = [here.parents[2] / "resources" / "mesh_icon.icns"]
    if os.environ.get("RESOURCEPATH"):                       # set by py2app
        candidates.append(Path(os.environ["RESOURCEPATH"]) / "mesh_icon.icns")
    for c in candidates:
        if c.exists():
            return QIcon(str(c))
    return QApplication.windowIcon()


def _version(dist, module=None) -> str:
    try:
        return metadata.version(dist)
    except metadata.PackageNotFoundError:
        try:
            return getattr(__import__(module or dist), "__version__", "?")
        except ImportError:
            return "?"


def library_versions() -> str:
    py = platform.python_version()
    try:
        from vtkmodules.vtkCommonCore import vtkVersion
        vtk = vtkVersion.GetVTKVersion()
    except ImportError:
        vtk = "?"
    occt = ".".join(_version("cadquery-ocp", "OCP").split(".")[:3])
    return (f"Python {py}  ·  Qt {PYSIDE_VERSION}  ·  VTK {vtk}\n"
            f"PyVista {_version('pyvista')}  ·  OpenCASCADE {occt}  ·  NumPy {_version('numpy')}")


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("About Mesh Viewer")
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(36, 26, 36, 22)
        lay.setSpacing(4)

        icon = QLabel()
        icon.setPixmap(_app_icon().pixmap(96, 96))
        icon.setAlignment(Qt.AlignCenter)
        lay.addWidget(icon)
        lay.addSpacing(8)

        def line(text, style="", obj=None):
            lab = QLabel(text)
            lab.setAlignment(Qt.AlignCenter)
            if style:
                lab.setStyleSheet(style)
            if obj:
                lab.setObjectName(obj)
            lab.setTextInteractionFlags(Qt.TextSelectableByMouse)
            lay.addWidget(lab)
            return lab

        line("Mesh Viewer", "font-size: 17px; font-weight: 700;")
        line(f"Version {__version__}", obj="InfoLine")
        lay.addSpacing(10)
        line(f"Made by {AUTHOR}", "font-size: 13px;")
        line(f"using {BUILT_WITH}", "font-size: 13px;")
        lay.addSpacing(10)
        line(library_versions(), "font-size: 11px;", obj="InfoLine")
        line(f"macOS {platform.mac_ver()[0]}" if sys.platform == "darwin"
             else platform.platform(terse=True), "font-size: 11px;", obj="InfoLine")

        QShortcut(QKeySequence.Close, self, self.close)          # ⌘W
        self.setFixedSize(self.sizeHint())
