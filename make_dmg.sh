#!/bin/bash
# NEW (v2.12): builds "Mesh Viewer <version>.dmg" — open it, drag the app onto
# Applications, done. The app inside is self-contained (its own Python, Qt, VTK,
# OpenCASCADE), so it no longer depends on this folder.
#
#   ./make_dmg.sh            full build (standalone app + checks + .dmg)
#   ./make_dmg.sh --reuse    package an existing dist/Mesh Viewer.app (re-repairs and
#                            re-signs its libraries, no rebuild)
set -euo pipefail
cd "$(dirname "$0")"

step() { printf "\n\033[1m==> %s\033[0m\n" "$1"; }
die()  { printf "\n\033[31mError:\033[0m %s\n" "$1"; exit 1; }
[ "$(uname)" = "Darwin" ] || die "run this on your Mac."

APP="dist/Mesh Viewer.app"
NAME="Mesh Viewer"
VERSION="$(sed -n 's/^__version__ = "\([^"]*\)".*/\1/p' meshviewer/__init__.py)"
DMG="dist/$NAME $VERSION.dmg"

# ---- 1. Self-contained app ---------------------------------------------------------
if [ "${1:-}" != "--reuse" ]; then
    ./build_app.sh --standalone --no-install
else
    [ -d "$APP" ] || die "$APP not found."
    step "Repairing bundled libraries"
    .venv/bin/python fix_bundle.py "$APP" || true
    .venv/bin/python slim_bundle.py "$APP"
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
step "Making the disk image"
STAGE="$(mktemp -d)/$NAME"
mkdir -p "$STAGE/.background"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
# Retina + normal background in one file (Finder picks the right one).
BG="background.tiff"
tiffutil -cathidpicheck resources/dmg_background.png "resources/dmg_background@2x.png" \
    -out "$STAGE/.background/$BG" >/dev/null 2>&1 \
    || { BG="background.png"; cp resources/dmg_background.png "$STAGE/.background/$BG"; }

SIZE_MB=$(( $(du -sm "$STAGE" | cut -f1) * 12 / 10 + 50 ))
RW="$(mktemp -u).dmg"
hdiutil create -quiet -volname "$NAME" -srcfolder "$STAGE" -fs HFS+ -format UDRW \
        -size "${SIZE_MB}m" "$RW"

# Window layout: icons left / right, arrow background. Finder may ask once for
# permission ("Terminal wants to control Finder"); if refused, the .dmg still works,
# just without the arranged window.
for v in "/Volumes/$NAME"*; do [ -d "$v" ] && hdiutil detach -quiet "$v" -force || true; done
MOUNT="$(hdiutil attach -readwrite -noverify -noautoopen "$RW" | sed -n 's|.*\(/Volumes/.*\)$|\1|p' | head -1)"
DISK_NAME="$(basename "$MOUNT")"
osascript <<APPLESCRIPT >/dev/null 2>&1 || echo "(Finder layout skipped — the disk image still works)"
tell application "Finder"
    tell disk "$DISK_NAME"
        open
        set current view of container window to icon view
        set toolbar visible of container window to false
        set statusbar visible of container window to false
        set the bounds of container window to {200, 120, 840, 520}
        set opts to the icon view options of container window
        set arrangement of opts to not arranged
        set icon size of opts to 128
        set text size of opts to 13
        set background picture of opts to file ".background:$BG"
        set position of item "$NAME.app" of container window to {170, 190}
        set position of item "Applications" of container window to {470, 190}
        update without registering applications
        delay 1
        close
    end tell
end tell
APPLESCRIPT
SetFile -a C "$MOUNT" 2>/dev/null || true          # custom volume icon flag (if Xcode tools exist)
cp resources/mesh_icon.icns "$MOUNT/.VolumeIcon.icns" 2>/dev/null && SetFile -c icnC "$MOUNT/.VolumeIcon.icns" 2>/dev/null || true
sync
hdiutil detach -quiet "$MOUNT" || hdiutil detach -quiet -force "$MOUNT"

# Compressed, read-only final image (LZFSE: macOS 10.11+).
rm -f "$DMG"
hdiutil convert -quiet "$RW" -format ULFO -o "$DMG"
rm -f "$RW"
rm -rf "$(dirname "$STAGE")"

step "Done"
cat <<MSG
$(pwd)/$DMG  ($(du -h "$DMG" | cut -f1))

  Open it and drag Mesh Viewer onto Applications.
  On this Mac it opens normally. On another Mac (same chip type) the first
  launch is blocked because the app isn't notarized by Apple: try to open it
  once, then System Settings -> Privacy & Security -> "Open Anyway".
MSG
