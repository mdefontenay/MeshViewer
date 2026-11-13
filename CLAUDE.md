# Mesh Viewer — notes for Claude Code

A macOS app (PySide6 · PyVista/VTK · OpenCASCADE via cadquery-ocp) for CFD meshes and
CAD files. Read README.md (what it does), ARCHITECTURE.md (where things are, the
conventions) and CHANGELOG.md (history) before changing code.

## How I want you to work

- **Never push to GitHub, never commit or release on your own.** I build, commit,
  push and release myself.
- **Replies: short, plain language.** Say what is new and what was already there.
- **Don't overwrite my edits.** Check a file hasn't changed since you read it before
  writing it. Leave no temporary files in this folder.
- **After changing files for a prompt, build once yourself** (not after every small
  fix; no build when nothing changed). It takes ~20 s and installs into /Applications:
  ```
  cd ~/Documents/"App Dev/Mesh Viewer/MeshViewer"
  ./build_app.sh
  ```
- **Every reply that changed files ends with two command blocks** (none when nothing
  changed):
  1. Build and push to GitHub:
     ```
     cd ~/Documents/"App Dev/Mesh Viewer/MeshViewer"
     ./build_app.sh
     git add -A
     git commit -m "Mesh Viewer X: …"
     git push
     ```
  2. Then, in a separate paragraph, make the DMG and publish the release:
     ```
     ./make_dmg.sh
     gh release create vX ~/Downloads/MeshViewer-build/dist/"Mesh Viewer X.dmg" --title "Mesh Viewer X" --notes-file docs/release-notes-X.md
     ```
     add `--prerelease` for a beta.

## Versions

- 2.X only for a new stage (few, on purpose); everything else is 2.X.Y.
- 2.5 = "organized the macOS way", in beta: `__version__ = "2.5bN"` in
  `meshviewer/__init__.py`, shown "2.5 beta N", tag `v2.5bN`, `--prerelease`.
- Each release: a CHANGELOG entry (table of files → what changed) and
  `docs/release-notes-<version>.md` (renamed from the previous one, new section on top).

## Rules for the app

- Layers: core (no Qt) → render (VTK) → gui (Qt). Settings only through
  `gui/store.settings()`.
- Icons: SF Symbols asked from macOS at run time (PyObjC, `gui/icons.py`); never ship
  SF Symbols exports or SVGs of them. Drawn fallbacks are in `gui/icons.py`.
- Hover texts: the name and the shortcut, nothing more.
- Words on screen: American spelling, Title Case for menus/buttons/tabs/tools,
  sentence case for labels. One name per thing: tool, plot, section, Inflation Layers.
- A change the user may want back goes through `window.changes` (undo).
- Questions are sheets (`gui/sheets.py`), errors `feedback.show_error`, background
  work `run_job(..., busy=(window, "…"))`.
- STEP meshes are for display: speed and few triangles over pretty meshes.

## Tests

```
.venv/bin/python tests/run_all.py          # all 11 test files
.venv/bin/python mesh_viewer.py --selftest
```
The tests use a scratch settings file (`MESHVIEWER_SETTINGS`), never the real one.

- They pass on this Mac (macOS, dark mode). `tests/fixtures.py` makes its STEP box
  with OCP, no `cadquery` needed. The "Unrecognized file type: test_x.py" lines in
  the output are noise: the app also reads the script's own path as a file to open.
- `test_viewport.py` compares screen grabs: now and then a check fails because
  something covered the window. Run it again before suspecting the code.
- To see the app, run a small script with `conftest.run` and save `w.grab()` (widget
  grabs show see-through areas as white: not a bug). A window Claude starts can't take
  the focus, so native full screen can't be tested from here: the user checks it.
- **Don't use `git stash` here**: the folder is in iCloud Documents, and a stash pop
  once left `panels/plots.py` renamed to `plots` (no extension).

## Where things stand (2.5 beta 4, not yet committed or released)

- Released: 2.5 beta 3 (`v2.5b3`). 2.5 beta 4 is in the working tree: `__version__`
  is "2.5b4", its CHANGELOG entry and `docs/release-notes-2.5b4.md` list everything.
  More changes before the user releases it go into the same entry and notes.
- Layout: parts list on the left, the inspector on the right with View (Meshing
  Control, Section, Edit) · Measure (Info, Measure) · Analyze (CFD, Cell Quality,
  Results, Plots) tabs (`gui/inspector.py`, `gui/sidebar.py`, `gui/sections.py`);
  light toolbar with View ▸ Customize Toolbar… (`gui/window_bars.py`).
- Results (`gui/panels/results.py`): the field (Field, Unit in file, Shown in, a note
  line), then the colors (Color the boundaries, Color by, Scale linear / log, Colors,
  Min / Max). What a field is and its units: `core/field_kinds.py` (usual CFD and FEA
  fields) and `core/units.py` (`QUANTITIES`: every unit name in one table only).
- Section tool and section plots: ✎ Edit Plane right of X / Y / Z
  (`panels/section.py` `edit_plane_action`) shows Origin / Normal under Normal to.
- Menus: `widgets/basics.Menu` draws check marks for checkable items with icons
  (Show); `MenuSelect.addSection` for headers; pull-downs use `icons.paint_chevron`.
- Checked on this Mac: the grayed toolbar icons fix works. Settings / About over a
  full-screen window: set up right (a dialog of the front window, on its Space), but
  the real full-screen slide is still for the user to check by hand.
