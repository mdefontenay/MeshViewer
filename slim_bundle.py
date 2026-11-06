#!/usr/bin/env python3
"""NEW (v2.5.2): make the standalone app smaller (run by build_app.sh --standalone).

Where the space went (2.2 GB): PySide6 1.2 GB, VTK 0.5 GB, OpenCASCADE 0.2 GB.
PySide6 ships all of Qt — a web browser engine, QML, 3D, multimedia, Designer
and other tools — and, as a "universal" wheel, every binary twice (Apple
Silicon + Intel). Mesh Viewer needs none of that. This script:

  1. keeps the Qt modules the app uses (plus anything they link to) and deletes
     the rest: unused Qt libraries, their plugins, QML files, translations,
     headers and the developer tools;
  2. keeps only this Mac's processor type in every binary (lipo -thin);
  3. replaces duplicated files inside Qt frameworks with links;
  4. re-signs what it changed.

    .venv/bin/python slim_bundle.py "dist/Mesh Viewer.app" [--dry-run]
"""
from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path

# Qt modules Mesh Viewer (PySide6 + pyvistaqt + qtpy) actually imports, plus small
# ones the platform plugin may want. Anything they link to is kept automatically.
KEEP_MODULES = {"QtCore", "QtGui", "QtWidgets", "QtOpenGL", "QtOpenGLWidgets", "QtSvg",
                "QtNetwork", "QtDBus", "QtPrintSupport", "QtXml", "QtConcurrent"}
KEEP_PLUGINS = {"platforms", "imageformats", "styles", "iconengines", "platformthemes",
                "platforminputcontexts", "generic", "tls", "networkinformation"}
DROP_DIRS = ["Qt/qml", "Qt/translations", "Qt/metatypes", "Qt/resources", "Qt/libexec",
             "Qt/include", "include", "typesystems", "glue", "doc", "examples"]
FAT_MAGIC = (b"\xca\xfe\xba\xbe", b"\xca\xfe\xba\xbf")     # universal (fat) Mach-O
FW_RE = re.compile(r"(Qt\w+)\.framework")


def tree_size(p: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(p):
        for f in files:
            fp = Path(root, f)
            if not fp.is_symlink():
                total += fp.stat().st_size
    return total


def linked_frameworks(path: Path) -> set[str]:
    """Qt frameworks a binary links to (otool -L)."""
    out = subprocess.run(["otool", "-L", str(path)], capture_output=True, text=True).stdout
    return set(FW_RE.findall(out))


class Slimmer:
    def __init__(self, app: Path, dry_run=False, linked=linked_frameworks):
        self.app = app
        self.dry = dry_run
        self.linked = linked                # injectable (tests)
        ver = f"python{sys.version_info[0]}.{sys.version_info[1]}"
        self.pys = app / "Contents" / "Resources" / "lib" / ver / "PySide6"
        self.qt = self.pys / "Qt"
        self.removed = 0
        self.changed: list[Path] = []          # binaries rewritten -> re-sign

    # ---- helpers ---------------------------------------------------------------------
    def rm(self, p: Path):
        if not (p.exists() or p.is_symlink()):
            return
        size = p.stat().st_size if p.is_file() or p.is_symlink() else tree_size(p)
        self.removed += 0 if p.is_symlink() else size
        if self.dry:
            print(f"  would remove {p.relative_to(self.app)}  ({size / 1e6:.1f} MB)")
            return
        shutil.rmtree(p) if p.is_dir() and not p.is_symlink() else p.unlink()

    @staticmethod
    def module_name(f: Path) -> str:
        return f.name.split(".")[0]          # QtWebEngineCore.abi3.so -> QtWebEngineCore

    # ---- 1. unused Qt ------------------------------------------------------------------
    def drop_unused_qt(self):
        if not self.pys.is_dir():
            print("  (no PySide6 in the app — skipped)")
            return
        for f in list(self.pys.glob("Qt*.so")) + list(self.pys.glob("Qt*.pyi")):
            if self.module_name(f) not in KEEP_MODULES:
                self.rm(f)
        for d in DROP_DIRS:
            self.rm(self.pys / d)
        for tool in self.pys.glob("*.app"):                  # Designer, Linguist, Assistant
            self.rm(tool)
        for f in self.pys.iterdir():                          # uic, rcc, lupdate, qmllint, …
            if f.is_file() and not f.suffix and os.access(f, os.X_OK):
                self.rm(f)
        plugins = self.qt / "plugins"
        if plugins.is_dir():
            for d in plugins.iterdir():
                if d.name not in KEEP_PLUGINS:
                    self.rm(d)
        # Frameworks: keep what the remaining modules and plugins link to (transitively).
        lib = self.qt / "lib"
        if not lib.is_dir():
            return
        # (only the pieces that stay — so a --dry-run report is right too)
        roots = [f for f in self.pys.glob("Qt*.so") if self.module_name(f) in KEEP_MODULES]
        roots += list(self.pys.glob("*.dylib"))                       # libpyside6, …
        if plugins.is_dir():
            roots += [f for f in plugins.rglob("*.dylib")
                      if f.relative_to(plugins).parts[0] in KEEP_PLUGINS]
        keep, todo = set(), set()
        for r in roots:
            todo |= self.linked(r)
        todo |= {m for m in KEEP_MODULES if (lib / f"{m}.framework").exists()}
        while todo:
            name = todo.pop()
            if name in keep:
                continue
            keep.add(name)
            binary = lib / f"{name}.framework" / "Versions" / "A" / name
            if not binary.exists():
                binary = lib / f"{name}.framework" / name
            if binary.exists():
                todo |= self.linked(binary) - keep
        for fw in lib.glob("*.framework"):
            if fw.name[:-len(".framework")] not in keep:
                self.rm(fw)
        for fw in lib.glob("*.framework"):                   # headers are for compiling only
            for h in fw.rglob("Headers"):
                self.rm(h)
        print(f"  Qt frameworks kept: {', '.join(sorted(keep))}")

    # ---- 2. one processor type -----------------------------------------------------------
    def thin(self, arch=None):
        arch = arch or platform.machine()                    # "arm64" or "x86_64"
        n = 0
        for root, _dirs, files in os.walk(self.app):
            for f in files:
                p = Path(root, f)
                if p.is_symlink() or p.stat().st_size < 4096:
                    continue
                with open(p, "rb") as fh:
                    if fh.read(4) not in FAT_MAGIC:
                        continue
                before = p.stat().st_size
                if self.dry:
                    n += 1
                    continue
                tmp = p.with_name(p.name + ".thin")
                r = subprocess.run(["lipo", "-thin", arch, str(p), "-output", str(tmp)],
                                   capture_output=True, text=True)
                if r.returncode == 0:
                    os.replace(tmp, p)
                    os.chmod(p, 0o755)
                    self.removed += before - p.stat().st_size
                    self.changed.append(p)
                    n += 1
                elif tmp.exists():
                    tmp.unlink()
        print(f"  {'would thin' if self.dry else 'thinned'} {n} universal binaries to {arch}")

    # ---- 3. duplicated framework files -------------------------------------------------------
    def dedupe_frameworks(self):
        lib = self.qt / "lib"
        if not lib.is_dir():
            return
        for fw in lib.glob("*.framework"):
            a = fw / "Versions" / "A"
            if not a.is_dir():
                continue
            cur = fw / "Versions" / "Current"
            if not cur.is_symlink():                          # copy, or missing
                self.rm(cur)
                if not self.dry:
                    cur.symlink_to("A")
            for entry in list(fw.iterdir()):
                if entry.name == "Versions" or entry.is_symlink():
                    continue
                twin = a / entry.name
                same = twin.exists() and (entry.is_dir() == twin.is_dir()) and (
                    entry.is_dir() or entry.stat().st_size == twin.stat().st_size)
                if same:
                    self.rm(entry)
                    if not self.dry:
                        entry.symlink_to(f"Versions/Current/{entry.name}")

    # ---- 4. signatures (Apple Silicon only runs signed code) ---------------------------------
    def sign(self):
        if self.dry:
            return
        frameworks = {p for p in self.app.rglob("*.framework") if p.is_dir() and not p.is_symlink()}
        for fw in sorted(frameworks):
            subprocess.run(["codesign", "--force", "--sign", "-", str(fw)], capture_output=True)
        for p in self.changed:
            if not any(fw in p.parents for fw in frameworks):
                subprocess.run(["codesign", "--force", "--sign", "-", str(p)], capture_output=True)
        print(f"  re-signed {len(frameworks)} frameworks + {len(self.changed)} binaries")

    def run(self):
        size0 = tree_size(self.app)
        print("  unused Qt parts…")
        self.drop_unused_qt()
        print("  duplicates…")
        self.dedupe_frameworks()
        print("  processor type…")
        self.thin()
        self.sign()
        size1 = tree_size(self.app)
        verb = "would save" if self.dry else "saved"
        print(f"slimmed: {size0 / 1e9:.2f} GB -> "
              f"{(size0 - self.removed if self.dry else size1) / 1e9:.2f} GB "
              f"({verb} {self.removed / 1e9:.2f} GB)")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    Slimmer(Path(args[0] if args else "dist/Mesh Viewer.app"),
            dry_run="--dry-run" in sys.argv).run()
