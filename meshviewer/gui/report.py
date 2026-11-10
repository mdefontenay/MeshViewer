"""Help ▸ Report a Problem…: a new GitHub issue, already filled with what helps to find
the cause — the app's version, macOS's, the libraries' — and, from an error sheet, the
error itself. Nothing is sent until you press Submit on GitHub.
"""
from __future__ import annotations

import platform
from urllib.parse import urlencode

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

ISSUES = "https://github.com/mdefontenay/MeshViewer/issues/new"


def system_info():
    from meshviewer import version_label
    from meshviewer.gui.dialogs.about import library_versions
    mac = platform.mac_ver()[0]
    system = f"macOS {mac}" if mac else f"{platform.system()} {platform.release()}"
    return (f"Mesh Viewer {version_label()} · {system} ({platform.machine()})\n"
            + library_versions().replace("\n", " · "))


def report_url(error="", file_name=""):
    title = f"Problem with {file_name}" if file_name else ""
    body = ("**What happened, and what did you expect?**\n\n\n"
            "**Steps to make it happen again**\n1. \n\n")
    if error:
        body += f"**The error**\n```\n{error.strip()[:1500]}\n```\n\n"
    body += f"**System**\n{system_info()}\n"
    return f"{ISSUES}?{urlencode({'title': title, 'body': body})}"


def report_problem(error="", file_name=""):
    QDesktopServices.openUrl(QUrl(report_url(error, file_name)))
