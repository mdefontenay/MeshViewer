#!/usr/bin/env python3
"""NEW (v2.5.1): repair libraries py2app damaged in a standalone app.

Why: Homebrew builds its libraries (xz, openssl, sqlite, ...) for your macOS
version, which stores them in a newer format ("chained fixups"). When py2app
copies them into the app it rewrites their headers with an old tool (macholib)
that corrupts that format, so macOS refuses to load them:

    Library not loaded: .../Frameworks/liblzma.5.dylib
    (chained fixups, unknown imports_format (49))

Fix: put back an untouched copy of each such library (and of Python's own
extension modules that use them), redo the path changes with Apple's
install_name_tool (which understands the format), and re-sign.

    .venv/bin/python fix_bundle.py "dist/Mesh Viewer.app"
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

LINK = "@executable_path/../Frameworks/"


def run(*cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def deps(path: Path) -> list[str]:
    """Libraries a Mach-O file loads (otool -L, without the file's own id)."""
    out = run("otool", "-L", str(path)).stdout.splitlines()[1:]
    own = run("otool", "-D", str(path)).stdout.splitlines()[1:]
    return [line.split(" (compatibility")[0].strip() for line in out
            if line.strip() and line.split(" (compatibility")[0].strip() not in own]


def homebrew_prefixes() -> list[str]:
    found = run("brew", "--prefix").stdout.strip()
    return [p for p in dict.fromkeys([found, "/opt/homebrew", "/usr/local"]) if p]


def pristine_dylib(name: str, prefixes) -> Path | None:
    for pre in prefixes:
        for cand in [Path(pre, "lib", name), *Path(pre, "opt").glob(f"*/lib/{name}")]:
            if cand.exists():
                return cand.resolve()
    return None


def main(app: Path) -> int:
    fw = app / "Contents" / "Frameworks"
    prefixes = homebrew_prefixes()
    base = Path(sys.base_prefix)                    # the Python the app was built from
    ver = f"python{sys.version_info[0]}.{sys.version_info[1]}"
    dynload_src = base / "lib" / ver / "lib-dynload"
    dynload_app = app / "Contents" / "Resources" / "lib" / ver / "lib-dynload"
    local = (*prefixes, str(base))                  # paths that only exist on this Mac

    todo: list[Path] = []
    # 1. Untouched copies of Homebrew libraries in Contents/Frameworks.
    for lib in sorted(fw.glob("*.dylib")):
        if lib.is_symlink():
            continue
        src = pristine_dylib(lib.name, prefixes)
        if src:
            shutil.copyfile(src, lib)
            lib.chmod(0o755)
            todo.append(lib)
    # 2. Untouched copies of Python's extension modules that link to them.
    if dynload_src.is_dir() and dynload_app.is_dir():
        for so in sorted(dynload_app.glob("*.so")):
            src = dynload_src / so.name
            if src.exists() and any(d.startswith(local) for d in deps(src)):
                shutil.copyfile(src, so)
                so.chmod(0o755)
                todo.append(so)

    # 3. Point every reference at the copy inside the app (pulling in any
    #    library that's still missing), with Apple's tool.
    done, fixed, errors = set(), 0, 0
    while todo:
        f = todo.pop()
        if f in done:
            continue
        done.add(f)
        if f.suffix == ".dylib":
            run("install_name_tool", "-id", LINK + f.name, str(f))
        for d in deps(f):
            if not d.startswith(local):
                continue                            # system library or already relative
            name = Path(d).name
            target = fw / name
            if not target.exists():
                src = Path(d).resolve()
                if not src.exists():
                    print(f"  ! {f.name}: {d} not found")
                    errors += 1
                    continue
                shutil.copyfile(src, target)
                target.chmod(0o755)
                todo.append(target)
            r = run("install_name_tool", "-change", d, LINK + name, str(f))
            if r.returncode:
                print(f"  ! {f.name}: {r.stderr.strip()}")
                errors += 1
        r = run("codesign", "--force", "--sign", "-", str(f))
        if r.returncode:
            print(f"  ! sign {f.name}: {r.stderr.strip()}")
            errors += 1
        fixed += 1
    print(f"repaired {fixed} librar{'y' if fixed == 1 else 'ies'}"
          + (f", {errors} problem(s)" if errors else ""))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1] if len(sys.argv) > 1 else "dist/Mesh Viewer.app")))
