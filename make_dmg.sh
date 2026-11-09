#!/bin/bash
# NEW (v2.1.12): builds "Mesh Viewer <version>.dmg" — open it, drag the app onto
# Applications, done. The app inside is self-contained (its own Python, Qt, VTK,
# OpenCASCADE), so it no longer depends on this folder.
#
#   ./make_dmg.sh            full build (standalone app + checks + .dmg)
#   ./make_dmg.sh --reuse    package the app already built (re-repairs and
#                            re-signs its libraries, no rebuild)
#
# NEW (v2.1.21): the app and the .dmg are made in ~/Downloads/MeshViewer-build/dist
# (or $MESHVIEWER_WORK/dist), not in this folder.
# v2.2.2: the disk image window (background, icon places) is written by dmgbuild
# (installed in the build venv the first time), no longer arranged by Finder.
set -euo pipefail
cd "$(dirname "$0")"

step() { printf "\n\033[1m==> %s\033[0m\n" "$1"; }
die()  { printf "\n\033[31mError:\033[0m %s\n" "$1"; exit 1; }
[ "$(uname)" = "Darwin" ] || die "run this on your Mac."

WORK="${MESHVIEWER_WORK:-$HOME/Downloads/MeshViewer-build}"
VENV="$WORK/venv"
APP="$WORK/dist/Mesh Viewer.app"
NAME="Mesh Viewer"
VERSION="$(sed -n 's/^__version__ = "\([^"]*\)".*/\1/p' meshviewer/__init__.py)"
DMG="$WORK/dist/$NAME $VERSION.dmg"

# ---- 1. Self-contained app ---------------------------------------------------------
if [ "${1:-}" != "--reuse" ]; then
    ./build_app.sh --standalone --no-install
else
    [ -d "$APP" ] || die "$APP not found."
    step "Repairing bundled libraries"
    "$VENV/bin/python" fix_bundle.py "$APP" || true
    "$VENV/bin/python" slim_bundle.py "$APP"
    find "$APP/Contents" -type f \( -name "*.so" -o -name "*.dylib" \) -print0 \
        | xargs -0 codesign --force --sign - >/dev/null 2>&1 || true
    codesign --force --deep --sign - "$APP" >/dev/null 2>&1 || true
fi
[ -d "$APP" ] || die "$APP not found."
# A standalone app carries its own Python library; a quick (alias) build doesn't.
ls -d "$APP"/Contents/Resources/lib/python3* >/dev/null 2>&1 \
    || die "$APP is a quick build that only works from this folder — run without --reuse."

# ---- 2. Does the bundled app have everything? ----------------------------------------
step "Checking the app (self-test)"
"$APP/Contents/MacOS/$NAME" --selftest || die "self-test failed: a package is missing from the app (see above)."

# ---- 3. Disk image -------------------------------------------------------------------
# v2.2.2: made with dmgbuild, which writes the window layout (background picture,
# icon positions) straight into the image. The old way asked Finder to arrange
# the window by AppleScript; when macOS refused Terminal the "control Finder"
# permission, or Finder hadn't saved its settings before the disk was ejected,
# the .dmg opened without the background. No Finder, no permission prompt now.
step "Making the disk image"
"$VENV/bin/python" -c "import dmgbuild" 2>/dev/null \
    || "$VENV/bin/python" -m pip install -q dmgbuild \
    || die "could not install dmgbuild (pip install dmgbuild in $VENV)."
for v in "/Volumes/$NAME"*; do [ -d "$v" ] && hdiutil detach -quiet "$v" -force || true; done
rm -f "$DMG"
# dmg_background.png (640 × 400) + dmg_background@2x.png (Retina) are combined
# automatically; the window is the same size as the picture.
"$VENV/bin/python" - "$DMG" "$NAME" "$APP" <<'PY'
import sys
from dmgbuild import build_dmg

dmg, name, app = sys.argv[1:4]
build_dmg(dmg, name, settings={
    "format": "ULFO",                       # LZFSE compressed, macOS 10.11+
    "filesystem": "HFS+",
    "files": [app],
    "symlinks": {"Applications": "/Applications"},
    "icon": "resources/mesh_icon.icns",     # icon of the mounted disk
    "background": "resources/dmg_background.png",
    "window_rect": ((200, 120), (640, 400)),
    "default_view": "icon-view",
    "show_toolbar": False, "show_status_bar": False, "show_pathbar": False,
    "show_sidebar": False, "show_tab_view": False,
    "icon_size": 128, "text_size": 13,
    "icon_locations": {f"{name}.app": (170, 190), "Applications": (470, 190)},
})
PY
[ -f "$DMG" ] || die "the disk image was not made (see above)."

step "Done"
cat <<MSG
$DMG  ($(du -h "$DMG" | cut -f1))

  Open it and drag Mesh Viewer onto Applications.
  On this Mac it opens normally. On another Mac (same chip type) the first
  launch is blocked because the app isn't notarized by Apple: try to open it
  once, then System Settings -> Privacy & Security -> "Open Anyway".
MSG
