## What's new (since 2.20)

- **Edit** (sidebar, like Onshape's Transform): Rotate by any angle, Mirror, or
  Move by X, Y, Z, then Apply; the changes are listed with Undo / Reset, and *Show
  original edges* compares. Meshes and triangle CAD (not STEP / IGES / BREP).
- **Export…** (⇧⌘E): STL (binary or one named solid per part), OBJ, PLY, VTU
  (ParaView) and, for meshes, UGRID + .mapbc with the volume cells. Edits included.
- **Rename parts** (right-click ▸ Rename…, or Return), for any file type; Export
  writes the new names (e.g. the UGRID .mapbc).
- McMaster part numbers are found anywhere in a part's name.
- **Show** toggles in the toolbar: mesh edges, feature edges, faces (off: only the
  edges, which stay while moving) · axes, grid, bounding box, origin.
- Right-click a part ▸ **Colour…** to change its colour.
- **Shading** switch in Appearance: flat part colours, no light or shadow.
- Parallel projection button in the toolbar.
- About ▸ **Check for Updates…** opens the latest release here.
- Section: the cut mesh follows *Mesh edges*; smaller handles that keep their
  size on screen; switching the section off folds it.
- Appearance is grouped by what it styles and says what it's for; Display links to it.
- Cleaner drop-down lists; the .dmg opens with its background and arranged icons.

## Install

1. Download **Mesh Viewer 2.29.dmg** below.
2. Open it and drag **Mesh Viewer** onto **Applications**.
3. **First launch:** the app isn't notarized by Apple, so macOS blocks it the first
   time. Try to open it once, then go to **System Settings → Privacy & Security**
   and click **Open Anyway**. Only needed once.

Requires a Mac with Apple Silicon and macOS 13 or later. Intel Macs: build from
source (see the README).
