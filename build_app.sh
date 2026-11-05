#!/bin/bash
# Builds "Mesh Viewer.app" and installs it in /Applications.
#
#   ./build_app.sh               quick build (default): the app runs the code in
#                                this folder with the Python in .venv — keep this
#                                folder where it is. Re-run after editing code?
#                                Not needed: just reopen the app.
#   ./build_app.sh --standalone  self-contained app (~1 GB) you can move or copy
#                                to another Mac. Slower to build.
#   --no-install                 build only (dist/Mesh Viewer.app); used by make_dmg.sh
set -euo pipefail
cd "$(dirname "$0")"

MODE="alias"
INSTALL=1
for arg in "$@"; do
    case "$arg" in
        --standalone) MODE="standalone" ;;
        --no-install) INSTALL=0 ;;
        *) echo "unknown option: $arg"; exit 2 ;;
    esac
done
step() { printf "\n\033[1m==> %s\033[0m\n" "$1"; }
die()  { printf "\n\033[31mError:\033[0m %s\n" "$1"; exit 1; }

[ "$(uname)" = "Darwin" ] || die "run this on your Mac."

# ---- 1. Python -------------------------------------------------------------
# py2app supports Python 3.10–3.13 and needs a "framework" build
# (Homebrew or python.org — not pyenv/conda).
step "Finding Python 3.13 / 3.12"
PY=""
for cand in \
    /opt/homebrew/bin/python3.13 /opt/homebrew/bin/python3.12 \
    /usr/local/bin/python3.13 /usr/local/bin/python3.12 \
    /Library/Frameworks/Python.framework/Versions/3.13/bin/python3.13 \
    /Library/Frameworks/Python.framework/Versions/3.12/bin/python3.12
do
    if [ -x "$cand" ] && [ -n "$("$cand" -c 'import sysconfig; print(sysconfig.get_config_var("PYTHONFRAMEWORK") or "")')" ]; then
        PY="$cand"; break
    fi
done
[ -n "$PY" ] || die "no framework Python 3.12/3.13 found. Install one with:  brew install python@3.13"
echo "Using $PY ($("$PY" --version))"

# ---- 2. Virtual environment ------------------------------------------------
step "Preparing .venv"
WANT="$("$PY" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')"
if [ -x .venv/bin/python ] && [ "$(.venv/bin/python -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')" != "$WANT" ]; then
    echo "Existing .venv uses another Python version — recreating it."
    rm -rf .venv
fi
[ -x .venv/bin/python ] || "$PY" -m venv .venv
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet -r requirements.txt py2app setuptools

step "Checking packages"
.venv/bin/python -c "import numpy, pyvista, pyvistaqt, PySide6, h5py, OCP; print('all packages import fine')" \
    || die "a package failed to import (see above)."

# ---- 3. Build ----------------------------------------------------------------
step "Building ($MODE)"
rm -rf build dist
if [ "$MODE" = "alias" ]; then
    .venv/bin/python setup.py py2app --alias >/tmp/meshviewer_build.log 2>&1 \
        || { tail -40 /tmp/meshviewer_build.log; die "py2app failed (full log: /tmp/meshviewer_build.log)"; }
else
    .venv/bin/python setup.py py2app >/tmp/meshviewer_build.log 2>&1 \
        || { tail -40 /tmp/meshviewer_build.log; die "py2app failed (full log: /tmp/meshviewer_build.log)"; }
fi
APP="dist/Mesh Viewer.app"
[ -d "$APP" ] || die "build finished but $APP is missing (log: /tmp/meshviewer_build.log)"

if [ "$MODE" = "standalone" ]; then
    # FIX (v2.12.1): py2app corrupts Homebrew libraries (liblzma, openssl, ...)
    # when copying them; put back clean copies. See fix_bundle.py.
    step "Repairing bundled libraries"
    .venv/bin/python fix_bundle.py "$APP" || echo "(some libraries could not be repaired — the self-test will tell)"
    # NEW (v2.13): drop unused Qt parts (web engine, QML, 3D, tools…) and the Intel
    # half of every universal binary: ~2.2 GB -> ~1 GB. See slim_bundle.py.
    step "Slimming the app"
    .venv/bin/python slim_bundle.py "$APP"
    # Every library inside must carry a valid signature on Apple Silicon.
    find "$APP/Contents" -type f \( -name "*.so" -o -name "*.dylib" \) -print0 \
        | xargs -0 codesign --force --sign - >/dev/null 2>&1 || true
fi

# Apple Silicon refuses to run unsigned code: sign it locally ("ad hoc").
if ! codesign --force --deep --sign - "$APP" >/tmp/meshviewer_sign.log 2>&1; then
    echo "(codesign warning — usually harmless:)"
    tail -3 /tmp/meshviewer_sign.log
fi

if [ "$INSTALL" = 0 ]; then
    step "Built: $(pwd)/$APP"
    exit 0
fi

# ---- 4. Install --------------------------------------------------------------
step "Installing in /Applications"
DEST="/Applications/Mesh Viewer.app"
osascript -e 'tell application "Mesh Viewer" to quit' >/dev/null 2>&1 || true
if [ -e "$DEST" ]; then
    # Old version goes to the Trash (recoverable), not deleted.
    osascript -e "tell application \"Finder\" to delete POSIX file \"$DEST\"" >/dev/null 2>&1 \
        || mv "$DEST" "$HOME/.Trash/Mesh Viewer (old $(date +%H%M%S)).app"
    echo "Previous version moved to the Trash."
fi
cp -R "$APP" "$DEST"
xattr -cr "$DEST" 2>/dev/null || true
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f "$DEST"

step "Done"
cat <<MSG
Mesh Viewer is in /Applications.

  • Double-click a .cgns / .ugrid / .step / .iges / .brep file to open it.
  • For .stl / .obj / .ply / .glb / .wrl (other apps own them by default):
    Get Info -> Open with -> Mesh Viewer -> Change All.
  • Logs: run from Terminal to see them:  "$DEST/Contents/MacOS/Mesh Viewer"
MSG
[ "$MODE" = "alias" ] && echo "  • Quick build: keep this folder ($(pwd)) where it is — the app uses it."
