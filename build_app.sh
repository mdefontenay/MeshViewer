#!/bin/bash
# Builds "Mesh Viewer.app" and installs it in /Applications.
#
#   ./build_app.sh               quick build (default): the app runs the code in
#                                this folder with its own Python — keep this
#                                folder where it is. Re-run after editing code?
#                                Not needed: just reopen the app.
#   ./build_app.sh --standalone  self-contained app (~1 GB) you can move or copy
#                                to another Mac. Slower to build.
#   ./build_app.sh --use-installed   quick build that reuses the packages already
#                                installed for that Python (pyvista, PySide6, …)
#                                instead of downloading its own copy (~1.5 GB).
#   --no-install                 build only (no copy to /Applications); used by make_dmg.sh
#
# NEW (v2.7.1): the heavy files — Python environment (~1.5 GB), build files and
# the finished app / .dmg — go to ~/Downloads/MeshViewer-build, NOT into this
# folder (so a project kept in iCloud-synced Documents stays small). Another place:
#   MESHVIEWER_WORK=/path/to/folder ./build_app.sh
set -euo pipefail
cd "$(dirname "$0")"

MODE="alias"
INSTALL=1
SYSTEM_PKGS=0
for arg in "$@"; do
    case "$arg" in
        --standalone) MODE="standalone" ;;
        --no-install) INSTALL=0 ;;
        --use-installed) SYSTEM_PKGS=1 ;;      # NEW: lightweight install
        *) echo "unknown option: $arg"; exit 2 ;;
    esac
done
step() { printf "\n\033[1m==> %s\033[0m\n" "$1"; }
die()  { printf "\n\033[31mError:\033[0m %s\n" "$1"; exit 1; }

[ "$(uname)" = "Darwin" ] || die "run this on your Mac."

# ---- 0. Where the heavy files go (NEW v2.7.1) --------------------------------------
WORK="${MESHVIEWER_WORK:-$HOME/Downloads/MeshViewer-build}"
VENV="$WORK/venv"
mkdir -p "$WORK"
if [ -d .venv ] && [ ! -L .venv ]; then        # older layout: .venv inside the project
    if [ -e "$VENV" ]; then rm -rf .venv; else mv .venv "$VENV"; fi
    echo "Moved the Python environment out of this folder to $VENV"
fi

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
step "Preparing the Python environment ($VENV)"
WANT="$("$PY" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')"
if [ -x "$VENV/bin/python" ] && [ "$("$VENV/bin/python" -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")')" != "$WANT" ]; then
    echo "Existing environment uses another Python version — recreating it."
    rm -rf "$VENV"
fi
# --use-installed: the environment sees the packages already installed for $PY, so pip
# below only adds what's missing (usually just py2app).
if [ "$SYSTEM_PKGS" = 1 ] && [ "$MODE" = "standalone" ]; then
    die "--use-installed only works for the quick build (not --standalone)."
fi
WANT_SYS="false"; [ "$SYSTEM_PKGS" = 1 ] && WANT_SYS="true"
HAVE_SYS="false"
grep -qs "include-system-site-packages = true" "$VENV/pyvenv.cfg" && HAVE_SYS="true"
if [ -x "$VENV/bin/python" ] && [ "$HAVE_SYS" != "$WANT_SYS" ]; then
    echo "Switching the environment between its own and the installed packages — recreating it."
    rm -rf "$VENV"
fi
if [ ! -x "$VENV/bin/python" ]; then
    if [ "$SYSTEM_PKGS" = 1 ]; then
        "$PY" -m venv --system-site-packages "$VENV"
    else
        "$PY" -m venv "$VENV"
    fi
fi
ln -sfn "$VENV" .venv          # small link: ".venv/bin/python mesh_viewer.py" still works
"$VENV/bin/python" -m pip install --quiet --upgrade pip
"$VENV/bin/python" -m pip install --quiet -r requirements.txt py2app setuptools

step "Checking packages"
"$VENV/bin/python" -c "import numpy, pyvista, pyvistaqt, PySide6, h5py, OCP; print('all packages import fine')" \
    || die "a package failed to import (see above)."

# ---- 3. Build ----------------------------------------------------------------
step "Building ($MODE)"
rm -rf "$WORK/build" "$WORK/dist"
PY2APP_ARGS=(--bdist-base "$WORK/build" --dist-dir "$WORK/dist")   # outside this folder
[ "$MODE" = "alias" ] && PY2APP_ARGS+=(--alias)
"$VENV/bin/python" setup.py py2app "${PY2APP_ARGS[@]}" >/tmp/meshviewer_build.log 2>&1 \
    || { tail -40 /tmp/meshviewer_build.log; die "py2app failed (full log: /tmp/meshviewer_build.log)"; }
rm -rf build ./*.egg-info                       # setuptools scraps, if any
APP="$WORK/dist/Mesh Viewer.app"
[ -d "$APP" ] || die "build finished but $APP is missing (log: /tmp/meshviewer_build.log)"

if [ "$MODE" = "standalone" ]; then
    # FIX (v2.5.1): py2app corrupts Homebrew libraries (liblzma, openssl, ...)
    # when copying them; put back clean copies. See fix_bundle.py.
    step "Repairing bundled libraries"
    "$VENV/bin/python" fix_bundle.py "$APP" || echo "(some libraries could not be repaired — the self-test will tell)"
    # NEW (v2.5.2): drop unused Qt parts (web engine, QML, 3D, tools…) and the Intel
    # half of every universal binary: ~2.2 GB -> ~1 GB. See slim_bundle.py.
    step "Slimming the app"
    "$VENV/bin/python" slim_bundle.py "$APP"
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
    step "Built: $APP"
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
