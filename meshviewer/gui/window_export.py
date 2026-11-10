"""File ▸ Export and Save Screenshot: their dialogs, then the files."""
from __future__ import annotations

from pathlib import Path
import subprocess
import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QApplication

from meshviewer.core.cfd_export import (
    export as write_cfd, FORMATS as CFD_FORMATS, SUFFIX as CFD_SUFFIX,
)
from meshviewer.core.export import (
    available as available_formats, export as write_export, FORMATS as EXPORT_FORMATS,
)
from meshviewer.gui.dialogs.export import ExportDialog
from meshviewer.gui.dialogs.screenshot import ScreenshotDialog
from meshviewer.gui.feedback import show_error
from meshviewer.gui.sheets import ask_save, save_folder


class Exports:
    def save_screenshot(self):
        """choose resolution + background first (a sheet), then where to save."""
        if not self.scene:
            return
        w, h = self.plotter.window_size
        self._shot_dialog = ScreenshotDialog(self, w, h)
        self._shot_dialog.accepted.connect(                  # after the sheet has gone
            lambda: QTimer.singleShot(300, self._save_screenshot_to_file))
        self._shot_dialog.open()

    def _save_screenshot_to_file(self):
        name = f"{self.path.stem}.png" if self.path else "Screenshot.png"
        ask_save(self, "Save Screenshot", save_folder(self.path) / name, "PNG image (*.png)",
                 self._write_screenshot)

    def _write_screenshot(self, fn):
        d = self._shot_dialog
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self.scene.screenshot(fn, scale=d.scale, background=d.background)
        except Exception as exc:                        # shown, not a crash
            show_error(self, f"“{Path(fn).name}” couldn't be saved.", str(exc),
                       "Check that you can write to that folder and that the disk has room.",
                       self.path.name if self.path else "", warning=True)
        finally:
            QApplication.restoreOverrideCursor()

    def export_model(self):
        if not self.scene:
            return
        sc = self.scene
        keys = available_formats(sc.model.kind, exact_cad=not sc.model.editable)
        ip = self.sidebar.inflation_panel
        cfd = ({"on": ip.enabled and bool((ip.result or {}).get("ok"))}   # CAD files
               if sc.model.is_cad else None)
        self._export_dialog = ExportDialog(
            self, keys, has_hidden=not all(sc.visible.values()),
            has_volume=sc.section.has_volume, edited=sc.model.edited,
            renamed=sc.renamed, cfd=cfd)
        # Ask where to save once the sheet has gone: opened while it is still closing,
        # macOS shows the save panel as a separate window (on another desktop in full
        # screen) instead of attached to this one.
        self._export_dialog.accepted.connect(lambda: QTimer.singleShot(300, self._export_to_file))
        self._export_dialog.open()

    def _export_to_file(self):
        sc, d = self.scene, self._export_dialog
        if d.what == "cfd":                              # CFD settings
            return self._export_cfd(d.cfd_fmt)
        fmt = d.fmt
        label, ext = EXPORT_FORMATS[fmt]
        base = self.path.name.split(".")[0] + ("_edited" if sc.has_changes else "")
        # one-dot pattern: macOS file types can't be ".lb8.ugrid" (the panel then
        # falls back to a detached window); the full suffix is put back below
        pattern = "*." + ext.rsplit(".", 1)[-1]
        ask_save(self, "Export", save_folder(self.path) / (base + ext), f"{label} ({pattern})",
                 lambda fn: self._write_export(fn, fmt, ext))

    def _write_export(self, fn, fmt, ext):
        sc, d = self.scene, self._export_dialog
        if not fn.lower().endswith(ext):
            fn = fn[: -len(".ugrid")] + ext if fn.lower().endswith(".ugrid") else fn + ext
        names = [n for n in sc.names if sc.visible[n] or not d.visible_only.isChecked()]
        parts = {n: sc.model.parts[n] for n in names}
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            volume = sc.section.volume_grid() if fmt in ("vtu", "ugrid") else None
            write_export(fmt, fn, parts, volume=volume,
                         colors={n: sc.colors[n] for n in names})   # OBJ / PLY
        except Exception as exc:                        # shown, not a crash
            QApplication.restoreOverrideCursor()
            show_error(self, f"“{Path(fn).name}” couldn't be exported.", str(exc),
                       "Check that you can write to that folder and that the disk has room.",
                       self.path.name, warning=True)
            return
        QApplication.restoreOverrideCursor()
        if sys.platform == "darwin":                    # show the new file in Finder
            subprocess.run(["open", "-R", fn], check=False)

    def _export_cfd(self, kind):
        """the inflation layers for a mesher, or a CSV of everything."""
        label, ext = CFD_FORMATS[kind]
        base = self.path.name.split(".")[0] + CFD_SUFFIX[kind]
        ask_save(self, "Export CFD Settings", save_folder(self.path) / (base + ext),
                 f"{label.split(' — ')[0]} (*{ext})", lambda fn: self._write_cfd(fn, kind, ext))

    def _write_cfd(self, fn, kind, ext):
        if not fn.lower().endswith(ext):
            fn += ext
        try:
            write_cfd(kind, fn, self.sidebar.inflation_panel.export_info(self.path.name))
        except Exception as exc:                        # shown, not a crash
            show_error(self, f"“{Path(fn).name}” couldn't be exported.", str(exc),
                       "Check that you can write to that folder, and that Inflation Layers "
                       "is filled in.", self.path.name, warning=True)
            return
        if sys.platform == "darwin":
            subprocess.run(["open", "-R", fn], check=False)
