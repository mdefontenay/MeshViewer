"""The "About Mesh Viewer" window — small window with the icon, version,
credits and the versions of the main libraries. Check for Updates
(opens the latest release on GitHub).
Check for Updates asks GitHub for the latest release and compares it with
this version: a newer one -> "A new update is available" + Download; the same ->
up to date; older -> this app is a pre-release. (curl, built into macOS, so no
certificate setup is needed; Python's urllib if curl is missing.)"""
from __future__ import annotations

import json
import os
import platform
import re
import sys
from importlib import metadata
from pathlib import Path

from PySide6 import __version__ as PYSIDE_VERSION
from PySide6.QtCore import QProcess, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QDialog, QLabel, QPushButton, QVBoxLayout

from meshviewer import __version__, version_label

AUTHOR = "Matthieu de Fontenay"
BUILT_WITH = "Claude Opus 5.5"
RELEASES = "https://github.com/mdefontenay/MeshViewer/releases/latest"
LATEST_API = "https://api.github.com/repos/mdefontenay/MeshViewer/releases/latest"


def version_tuple(text):
    """'v2.13.2' -> (2, 13, 2); None when there is no number."""
    m = re.search(r"\d+(?:\.\d+)*", text or "")
    return tuple(int(x) for x in m.group(0).split(".")) if m else None


def _beta(text):
    """'2.5b1' / 'v2.5-beta.1' / '2.5 beta 1' -> 1; a release -> None."""
    m = re.search(r"(?:b|beta)[ .-]?(\d+)\s*$", text or "", re.I)
    return int(m[1]) if m else None


def compare_versions(mine, latest):
    """-1: an update is available · 0: up to date · 1: this one is newer (pre-release).
    A beta comes before its release: 2.5b1 < 2.5b2 < 2.5."""
    a, b = version_tuple(mine), version_tuple(latest)
    if a is None or b is None:
        return None
    n = max(len(a), len(b))
    a, b = a + (0,) * (n - len(a)), b + (0,) * (n - len(b))
    if a == b:                                   # same numbers: release > any beta
        ba, bb = _beta(mine), _beta(latest)
        a, b = (ba is None, ba or 0), (bb is None, bb or 0)
    return (a > b) - (a < b)


def _fetch_latest():
    """Fallback without curl: Python's own HTTPS."""
    import urllib.request
    req = urllib.request.Request(LATEST_API, headers={"Accept": "application/vnd.github+json",
                                                      "User-Agent": "MeshViewer"})
    with urllib.request.urlopen(req, timeout=10) as f:
        return f.read().decode()


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
        line(f"Version {version_label()}", obj="InfoLine")
        # the latest release on GitHub, to compare with the version above
        lay.addSpacing(6)
        self.check = check = QPushButton("Check for Updates…")
        check.setCursor(Qt.PointingHandCursor)
        check.setToolTip("Ask GitHub for the latest release and compare it with this version")
        check.setAutoDefault(False)
        check.clicked.connect(self.check_updates)
        lay.addWidget(check, 0, Qt.AlignCenter)
        # the answer, and a Download button when there is a newer release
        self.update_note = QLabel("")
        self.update_note.setAlignment(Qt.AlignCenter)
        self.update_note.setWordWrap(True)
        self.update_note.setTextFormat(Qt.RichText)
        self.update_note.setMaximumWidth(320)
        self.update_note.setVisible(False)
        lay.addWidget(self.update_note)
        self.download = QPushButton("Download")
        self.download.setCursor(Qt.PointingHandCursor)
        self.download.setAutoDefault(False)
        self.download.setVisible(False)
        self.download.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(self._page)))
        lay.addWidget(self.download, 0, Qt.AlignCenter)
        self._page = RELEASES
        self._proc = None
        self._job = None
        lay.addSpacing(10)
        line(f"Made by {AUTHOR}", "font-size: 13px;")
        line(f"using {BUILT_WITH}", "font-size: 13px;")
        lay.addSpacing(10)
        line(library_versions(), "font-size: 11px;", obj="InfoLine")
        line(f"macOS {platform.mac_ver()[0]}" if sys.platform == "darwin"
             else platform.platform(terse=True), "font-size: 11px;", obj="InfoLine")

        QShortcut(QKeySequence.Close, self, self.close)          # ⌘W
        self.layout().setSizeConstraint(QVBoxLayout.SetFixedSize)

    # --- Check for Updates ----------------------------------------------------
    def check_updates(self):
        self.check.setEnabled(False)
        self.download.setVisible(False)
        self._say("Checking…", muted=True)
        self._proc = QProcess(self)
        self._proc.finished.connect(self._curl_done)
        self._proc.errorOccurred.connect(self._curl_error)
        self._proc.start("curl", ["-fsSL", "-m", "10", "-H", "Accept: application/vnd.github+json",
                                  "-A", "MeshViewer", LATEST_API])

    def _curl_done(self, code, _status=None):
        if self._proc is None:
            return
        out = bytes(self._proc.readAllStandardOutput()).decode(errors="replace")
        self._proc = None
        if code == 0 and out.strip():
            self._answer(out)
        else:
            self._failed()

    def _curl_error(self, err):
        if err == QProcess.FailedToStart and self._proc is not None:   # no curl: Python
            self._proc = None
            from meshviewer.gui.jobs import run_job
            self._job = run_job(_fetch_latest, self._answer, self._job_failed)

    def _job_failed(self, _exc):
        self._failed()

    def _answer(self, raw):
        self._job = None
        self.check.setEnabled(True)
        self.download.setVisible(False)
        try:
            data = json.loads(raw)
            tag = data.get("tag_name") or data.get("name") or ""
            self._page = data.get("html_url") or RELEASES
        except (ValueError, AttributeError):
            return self._failed()
        latest = version_label(tag.lstrip("v")) if tag else tag
        cmp = compare_versions(__version__, tag)
        if cmp is None:
            return self._failed()
        if cmp < 0:
            self._say(f"<b>A new update is available: {latest}</b><br>"
                      f"You have {version_label()}.")
            self.download.setText(f"Download {latest}")
            self.download.setVisible(True)
        elif cmp == 0:
            self._say(f"<span style='color:#30b350'>✓</span> You're up to date "
                      f"({version_label()} is the latest release).")
        else:
            self._say(f"This app is a pre-release: {version_label()} is newer than the latest "
                      f"release ({latest}).")

    def _failed(self):
        self._job = None
        self.check.setEnabled(True)
        self._say("Couldn't reach GitHub (no connection?).", muted=True)
        self._page = RELEASES
        self.download.setText("Open the Releases page")
        self.download.setVisible(True)

    def _say(self, text, muted=False):
        self.update_note.setObjectName("InfoLine" if muted else "")
        self.update_note.style().unpolish(self.update_note)
        self.update_note.style().polish(self.update_note)
        self.update_note.setText(text)
        self.update_note.setVisible(True)
