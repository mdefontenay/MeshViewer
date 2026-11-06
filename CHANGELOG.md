# Changelog

Every version of Mesh Viewer, newest first. Each table lists the files that
changed and what changed in them. (The version number lives in
`meshviewer/__init__.py`.)

## 2.26 — rename parts, McMaster numbers anywhere in a name, Edit as a table

| File | |
|---|---|
| `gui/part_tree.py`, `gui/sidebar.py` | **Rename** a part (any file type): right-click ▸ Rename…, or select it and press Return; the name is edited in the list. Names already in use are refused. McMaster numbers are now found **anywhere** in a name ("Screw 91251A540", "Bracket_8975K12_2"), not only at the start (sizes like "100x200" and alloys like "6061T6" are ignored) |
| `gui/scene.py` | `rename_part()` — colours, visibility, selection, edits follow; STEP / IGES parts keep their new name when re-meshed |
| `gui/window.py`, `gui/export_dialog.py` | Export writes the new names (STL solids, OBJ groups, VTU part names, UGRID .mapbc); renames count as unsaved changes (dot, question on close, "_edited" file name) |
| `gui/edit_panel.py`, `gui/style.py` | Edit section laid out as a small table: Pivot · rows X / Y / Z with Rotate [−90° \| +90° \| 180°] and Mirror [x → −x] · Move boxes + Move button in the same columns. Move boxes show "X 0" instead of "X 0.000". No line above "Show original edges" |

## 2.25 — tidier Edit section, shading switch, .dmg background fixed

| File | |
|---|---|
| `gui/edit_panel.py` | **re-laid out**: one row per action, every button the same shape and width — Pivot [Origin \| Centre] · Rotate X / Y / Z [−90° \| +90° \| 180°] (one click turns) · Mirror [X \| Y \| Z] · Move X / Y / Z boxes + a full-width Move button · "Show original edges" · "Last: …" with Undo \| Reset |
| `gui/widgets.py`, `gui/style.py`, `gui/export_dialog.py`, `gui/screenshot_dialog.py` | drop-down lists are now a button that opens a normal menu (`MenuSelect`): no more huge padding or drawing glitches above / below the list (replaces `roomy_combo`) |
| `gui/sidebar.py` | Display ▸ **Shading** switch (off = flat part colours, no light or shadow); a line under Display links to Appearance; switching the Section **off** now folds it |
| `gui/scene.py`, `gui/section.py` | `set_shading()` — parts and filled cut faces; kept when the mesh is rebuilt |
| `gui/appearance_dialog.py`, `gui/window.py` | Appearance says what it is for ("how things look, saved for every window"; Display = what is shown) and is grouped by what it styles: Window · Background · Axes (label size) · Edges (line thickness, while moving) |
| `make_dmg.sh` | the disk image window (background picture, icon places) is written by **dmgbuild** (installed in the build venv the first time) instead of asking Finder by AppleScript, which failed silently without the "control Finder" permission — the background now shows |

## 2.24 — friendlier Edit section, Move, compare with the original

| File | |
|---|---|
| `gui/edit_panel.py` | **redesigned** — always in the sidebar (no Edit button): Rotate (axis + −90° / +90° / 180°) · Mirror X / Y / Z · **Move** by X / Y / Z · turn **about** the origin or the model's centre · **Original** switch · "Last: …" line with **Undo** (one step) and **Reset**, styled like Measure ▸ Clear. STEP / IGES / BREP: a grey note instead of the tools |
| `transform.py` | edits are (R, t); geometry is always recomputed from the file's points, so Undo / Reset are exact and surfaces + volume cells keep identical node coordinates |
| `gui/scene.py`, `gui/section.py` | `apply_edit()`, `undo_edit()`, `reset_edits()`; the camera no longer resets after an edit; `set_show_original()` draws the file's feature edges in grey to compare. **Fix:** moving the volume cells no longer changed the file's copy (shallow-copy bug) |
| `gui/window.py` | Edit button / ⌘E removed; Export stays |
| `gui/widgets.py`, `gui/style.py`, `gui/export_dialog.py`, `gui/screenshot_dialog.py` | `roomy_combo()`: drop-down lists with menu-like spacing and rounded rows, wide enough for their text (Export format, screenshot resolution) |
| `export.py` | shorter format names |

## 2.23 — Edit (rotate / mirror) and Export

| File | |
|---|---|
| `transform.py` | **new** — exact 90° rotations and mirrors as 3×3 integer matrices; moves surfaces (faces flipped after a mirror so normals stay outward) and volume cells (node order fixed after a mirror) |
| `export.py` | **new** — writers: STL (binary, merged), STL (text, one named solid per part), OBJ (one group per part), PLY, VTU (volume + boundaries, opens in ParaView), UGRID `.lb8.ugrid` + `.mapbc` (volume + named boundaries) |
| `gui/edit_panel.py` | **new** — sidebar Edit section: Axis X / Y / Z · Rotate −90° / +90° / 180° · Mirror · Undo All Edits |
| `gui/export_dialog.py` | **new** — Export sheet: only the formats that fit the open file, "visible parts only", what will be written |
| `model.py` | `transform` (edits so far) and `editable` (not for exact CAD) |
| `gui/scene.py`, `gui/section.py`, `gui/measure.py` | `apply_edit()` / `reset_edits()`: parts, volume cells, section plane, grid and bounding box follow; picked distance points are dropped |
| `gui/window.py`, `gui/icons.py` | **Edit** (⌘E) opens the Edit section — STEP / IGES / BREP show "File type not supported for edits"; **Export…** (⇧⌘E, toolbar and File menu) shows the file in Finder when done; edited windows get the "unsaved" dot and ask before closing |
| `gui/sidebar.py` | Bounding box moved right under Axes |

## 2.22 — toolbar tidy-up

| File | |
|---|---|
| `gui/window.py`, `gui/icons.py` | **Parallel projection** is now a toggle button in the view group of the toolbar (Fit · Iso · X · Y · Z · ▢, also View menu, ⌘5), no longer a sidebar switch; new **Edit** button (pencil, ⌘E) as a placeholder for the editing tools of the next version |
| `gui/sidebar.py` | Display rows evenly spaced (the extra gaps between groups are gone); "Origin (0, 0, 0)" is just "Origin" (the coordinates are in its tooltip) |
| `.gitignore` | ignores the `Claude outputs/` folder |

## 2.21 — cleaner Display section, steadier section handles

| File | |
|---|---|
| `gui/sidebar.py`, `gui/window.py`, `gui/app.py` | Display ▸ **Axes: Off · Axes · Grid · Both** replaces the Grid switch and Appearance's Grid lines / Axis lines switches (old settings carry over); switches grouped: projection · edges · bounding box & origin |
| `gui/appearance_dialog.py` | three groups: Window · 3D view (background, axis label size) · Edges |
| `gui/section.py`, `gui/section_panel.py` | cut volume mesh: edges black like the model's mesh edges and shown only when Display ▸ Mesh edges is on; the switch is "Fill cut faces" again. Plane handles (sphere, arrow tips) keep the same small size on screen at any zoom; shorter arrow |
| `gui/scene.py` | `set_axes_mode()`; Mesh edges switch also drives the cut mesh; unused `set_grid()` removed |

## 2.20

| File | |
|---|---|
| `build_app.sh`, `make_dmg.sh` | heavy files (Python environment, build, app, .dmg) go to `~/Downloads/MeshViewer-build` (or `$MESHVIEWER_WORK`), not the project folder; `.venv` is just a link |
| `.gitignore` | ignores the `.venv` link |

## 2.19

| File | |
|---|---|
| `mesh/volume.py` | **new** — builds one VTK grid from the volume cells |
| `mesh/ugrid.py`, `mesh/cgns.py` | `read_volume()`: tetra / pyramid / prism / hexa cells, read only when needed (CGNS: per-type and MIXED sections; quadratic cells use their corners; polyhedra skipped). **Fix:** CGNS node counts for QUAD_9, HEXA_20, HEXA_27 and quadratic pyramids / prisms |
| `model.py`, `formats.py` | models of mesh files can load their volume cells |
| `gui/section.py`, `gui/section_panel.py` | CGNS / UGRID: the section fills the cut with the volume cells it goes through, with their edges; surface-only files keep the solid fill |
| `gui/scene.py` | cut-mesh colours for light / dark; its edges hide while moving |

## 2.18

| File | |
|---|---|
| `gui/scene.py`, `gui/sidebar.py` | **Origin (0, 0, 0)** switch in Display: a dot with short red / green / blue X / Y / Z arrows, drawn on top so it shows inside parts; also in screenshots |
| `gui/scene.py` | pressing X, Y or Z again without moving the view looks from the opposite side (X → −X → X); Iso stays as is |
| `gui/measure.py` | screenshots include the origin marker |
| `.gitignore` | **new** — keeps `.venv`, `build/`, `dist/`, `.dmg` and `__pycache__` out of git |
| `README.md`, `CHANGELOG.md`, `LICENSE`, `docs/` | **new layout for GitHub**: README with screenshots, features, download and build steps; the version history moved to CHANGELOG.md; MIT licence; screenshots and a release-notes template in `docs/` |

## 2.17

| File | |
|---|---|
| `gui/widgets.py` | **fix:** the Section switch shows the hand cursor like the other switches (the section header was forcing an arrow) |
| `gui/scene.py` | **Axis lines** off now hides the numbers and axis titles too (grid lines stay); axis numbers follow the unit chosen in the toolbar (mm / cm / m / in / ft) and titles read "X Axis (mm)"; with ⊘ no unit is shown. Grid building moved into `refresh_grid()` / `_add_grid()` (view and screenshots share it) |
| `gui/measure.py` | changing the unit rebuilds the axis labels |

## 2.16

| File | |
|---|---|
| `gui/sidebar.py` | switching **Section** on also opens its controls |
| `gui/appearance_dialog.py` | four groups separated by lines: Window · 3D background · Axes & grid · Edges; new **Axis lines** switch next to Grid lines |
| `gui/scene.py` | axis lines (frame + tick marks) can be hidden — numbers and titles stay; screenshots: only "As Shown" or "Transparent" |
| `gui/screenshot_dialog.py` | Light / Dark / Custom backgrounds removed (As Shown follows Appearance) |
| `gui/measure.py` | distance points are fixed-size dots on screen (13 px) instead of spheres that grew when zooming in; X/Y/Z lines 2.5 px (was 1.5) |
| `gui/app.py`, `gui/window.py` | axis-lines setting saved |

## 2.15

| File | |
|---|---|
| `gui/scene.py` | edges also hidden while **zooming** (scroll wheel / trackpad): a burst of zoom steps counts as one movement, edges return 0.3 s after the last step; **grid lines** behind the model can be turned off (the axis frame, ticks and labels stay); in CAD-face measuring, **clicking empty space clears** the selected faces |
| `gui/about_dialog.py` | **new** — About Mesh Viewer: icon, version, credits, Python / Qt / VTK / PyVista / OpenCASCADE / NumPy versions |
| `gui/app.py`, `gui/window.py` | "About Mesh Viewer" (macOS puts it in the app menu, left of File); grid-lines setting saved |
| `gui/appearance_dialog.py` | "Grid lines" switch; "While moving" switch now says rotate, pan, zoom |
| `meshviewer/__init__.py`, `setup.py`, `make_dmg.sh` | the version number lives in one place (`__version__`) |

## 2.14 — smoother edges, more Appearance options

| File | |
|---|---|
| `gui/scene.py` | edges are hidden while the view moves on **any** model (was only above 1.5 M triangles) and come back when you let go; feature edge thickness Thin 1 / Medium 1.5 / Thick 2 px (default Thin — one drawing pass on macOS) |
| `gui/appearance_dialog.py` | sheet grouped into **Window** and **3D view**; new: axis label size slider (10–28 pt, 10 = the original size, default 16), Edge lines Thin / Medium / Thick, "While rotating: hide edges" switch |
| `gui/app.py` | saves the new options; old Small / Medium / Large axis setting carries over |
| `gui/icons.py` | Appearance icon is now three sliders (it holds more than light / dark) |
| `gui/style.py` | group titles in the sheet |

## 2.13 — smaller app

| File | |
|---|---|
| `slim_bundle.py` | **new** — after a standalone build: removes the Qt parts the app never uses (web engine, QML, 3D, multimedia, Designer and other tools, translations, headers), keeps only this Mac's processor type in universal binaries, de-duplicates framework files, re-signs. PySide6 goes from ~1.2 GB to ~0.15 GB |
| `build_app.sh`, `make_dmg.sh` | run it (also with `make_dmg.sh --reuse`) |
| `mesh_viewer.py` | self-test also opens Qt and a 3D view, so a missing Qt piece is caught before packing |
| `setup.py` | leaves out tkinter / pip / wheel |

## 2.12.1 — fix

| File | |
|---|---|
| `fix_bundle.py` | **new** — the standalone app failed its self-test (`liblzma.5.dylib … unknown imports_format`): py2app corrupts Homebrew libraries when it copies them. This puts back clean copies and relinks them with Apple's `install_name_tool` |
| `build_app.sh` | standalone builds run `fix_bundle.py` and sign every library; signing errors are shown |
| `make_dmg.sh` | `--reuse` re-repairs an existing build (no rebuild) |
| `mesh_viewer.py` | self-test also checks lzma, bz2, zlib, ssl, hashlib, decimal, ctypes (not sqlite3: the app doesn't use it, so py2app leaves it out) |

## 2.12

| File | |
|---|---|
| `make_dmg.sh` | **new** — builds a self-contained app and packs it in `dist/Mesh Viewer <version>.dmg` (drag-to-Applications window with an arrow background) |
| `build_app.sh` | `--no-install` option (build only), used by `make_dmg.sh` |
| `mesh_viewer.py` | `--selftest`: checks a bundled app has every package and can draw (run by `make_dmg.sh` before packing) |
| `resources/dmg_background*.png` | **new** — background of the disk-image window |
| `gui/scene.py` | axis labels bigger: Small 16 / Medium 20 / Large 24 pt (old Large is the new Small); XYZ corner widget a bit larger |

## 2.11

| File | |
|---|---|
| `gui/part_tree.py` | right-click no longer selects the row (also ⌃-click on a Mac); the clicked row gets an accent outline while the menu is open, like Finder |
| `gui/sidebar.py`, `gui/scene.py`, `gui/window.py` | "Search in McMaster" uses only the row / part you right-clicked, never the whole selection (Hide / Isolate still act on the selection when you right-click inside it) |
| `gui/scene.py`, `gui/appearance_dialog.py`, `gui/app.py` | **new:** Axis labels Small (default) / Medium / Large in Appearance; also used for screenshots; the XYZ corner widget grows a little with it |

## 2.10

| File | |
|---|---|
| `gui/part_tree.py` | **fix:** groups no longer close right after opening (macOS opens/closes tree rows on mouse *release*; our press handler already had, so it toggled twice) |
| `gui/sidebar.py`, `gui/style.py` | "N parts selected · Clear" is always shown (greyed at 0), so selecting no longer shifts the list |
| `gui/scene.py`, `gui/screenshot_dialog.py` | **new:** "Transparent" screenshot background (PNG with alpha; grid/labels drawn dark, for white pages) |
| clean-up | screenshot sheet reuses the shared `ColorField` instead of its own copy; removed an unused `Scene.set_all_visible` and unused imports; old "NEW" markers removed (each version's changes are tagged `NEW (vX)` / `FIX (vX)`) |

## 2.9.1 — fixes

| File | |
|---|---|
| `gui/scene.py` | after a right-click menu, the 3D view no longer stays in "zoom" mode (any lost drag is ended as soon as the mouse moves with no button held) |
| `gui/sidebar.py` | same clean-up when the menu closes |
| `gui/part_tree.py` | **new:** row spacing Compact / Comfortable; group arrow is easier to hit — clicking anywhere left of a group's checkbox opens / closes it without selecting |
| `gui/appearance_dialog.py`, `gui/app.py`, `gui/window.py` | "Parts list" spacing option in Appearance, remembered |
| `gui/style.py`, `gui/widgets.py` | light mode: the system accent is made vivid and dark enough to read (macOS gives Qt a pale version); dark mode unchanged |

## 2.9 — appearance, McMaster, roomier menus

| File | |
|---|---|
| `gui/appearance_dialog.py` | **new** — Appearance sheet: theme System / Light / Dark; 3D background Default / Colour (hex) / Image |
| `gui/background.py` | **new** — picture behind the 3D view, centre-cropped to the window (no stretching), grid/axes colour picked from the picture's brightness |
| `gui/app.py` | appearance saved between launches and applied to every window |
| `gui/scene.py` | `set_background()`; screenshots "As Shown" keep the colour / picture |
| `gui/window.py` | Appearance button next to the camera (also View ▸ Appearance…, ⌘,) |
| `gui/part_tree.py` | **McMaster Parts** group always at the top (names starting with a McMaster number, e.g. `91251A540`); rounded selection painted by hand (merged across rows); crisp vector fold-out arrows |
| `gui/sidebar.py` | right-click "Search in McMaster" opens `mcmaster.com/<part number>` (from the list or the 3D view) |
| `gui/widgets.py` | `Menu` (rounded, roomier macOS-style right-click menu); `ColorField` (hex + swatch) |
| `gui/style.py` | menu styling; old arrow images removed |
| `gui/screenshot_dialog.py` | background choice adds "As Shown" |
| `gui/icons.py` | Appearance icon |

## 2.8

| File | |
|---|---|
| `gui/scene.py` | no black / very dark part colours; right-click hook (`on_context`) |
| `gui/measure.py` | marker lines no longer tinted by a hidden scalar array (now truly grey / red / green / blue); display units + conversion; 5 significant digits |
| `gui/window.py` | units capsule in the toolbar; right-click menu in the 3D view |
| `gui/sidebar.py`, `gui/part_tree.py` | "N parts selected · Clear" bar; right-click Hide / Isolate / Zoom To (selection-aware) |
| `gui/style.py` | part list: flat full-row selection + own fold-out arrows (no odd shapes) |
| `gui/widgets.py` | closing a section always gives its space back |
| `gui/icons.py` | ⊘ "no units" icon |

## 2.7 — fixes

| File | |
|---|---|
| `gui/part_tree.py` | **new** — grouped part list (replaces the flat list) |
| `gui/scene.py` | screenshots render in a separate full-size off-screen window with text and lines scaled (fixes giant axis labels); `isolate` / `zoom_to` take groups |
| `gui/measure.py` | distance line grey, X/Y/Z legs red/green/blue; labels on top; near-zero noise shown as 0 |
| `gui/measure_panel.py` | **rewritten** — result card, no hints, no Copy, units note |
| `gui/sidebar.py`, `gui/window.py` | Measure is a sidebar section (no toolbar button); sections start closed |
| `gui/widgets.py` | sliders / number boxes ignore the scroll wheel; sections can start closed |
| `gui/screenshot_dialog.py` | sheet shrinks back after leaving "Custom" |

## 2.6 — measure, screenshot options, multi-select

| File | |
|---|---|
| `gui/measure.py`, `gui/measure_panel.py`, `gui/screenshot_dialog.py` | **new** |
| `gui/scene.py` | **new:** multi-selection (parts) + CAD face selection, `click()` routes clicks to measuring, `pick_full()` returns the 3D point, `screenshot()` with background choice |
| `gui/sidebar.py` | list allows ⌘/⇧ multi-select; Measure section (shown while measuring) |
| `gui/window.py` | Measure + Screenshot buttons back at the top right; Measure in View menu |
| `cad/occt.py` | triangles remember which CAD face they came from (`face_id`); exact area / volume from OpenCASCADE |
| `model.py`, `formats.py` | model keeps the CAD source and units |

## 2.5 — more CAD formats

| File | |
|---|---|
| `cad/occt.py` | **new** — the OpenCASCADE code from `step.py`, shared by STEP/IGES/BREP. Bodies inside an unnamed IGES compound become separate parts; bare unnamed surfaces are grouped as "Surfaces"; IGES type names ("FACE", "SHELL") are ignored as part names |
| `cad/step.py` | now a thin wrapper around `occt.py` (same behaviour) |
| `cad/iges.py`, `cad/brep.py`, `cad/tessellated.py` | **new** readers |
| `formats.py`, `setup.py`, `build_app.sh` | register the new extensions (Finder "Open with") |

## 2.4 — plane always visible, smoother view

| File | |
|---|---|
| `gui/section.py` | **new:** the plane is drawn as its own actor (translucent + outline), updated on every change — VTK's widget only drew it while dragging. "Show plane handle" → "Show plane" |
| `gui/scene.py` | **rewritten drawing:** all parts in ONE composite actor (per-part colour/visibility), all feature edges in another, instead of 1–2 actors per part; hardware picking (ignores hidden parts, respects the cut); on models over 1.5 M triangles, edge lines are hidden while the view moves |
| `gui/window.py` | 4× instead of 8× anti-aliasing (cheaper on Retina) |

## 2.3 — faster section

| File | |
|---|---|
| `gui/section.py` | only parts whose bounding box touches the plane are cut; `vtkPolyDataPlaneCutter` instead of `slice`; exact point merge before filling (the tolerance merge was the big slowdown); all caps in one actor, all outlines in another; cut nudged 1e-6 off the plane to avoid degenerate cuts |
| `gui/section_panel.py` | switching on clips instantly; caps fill in ~0.15 s later with a busy cursor |
| `gui/scene.py` | VTK filters use all CPU cores; picking a cap uses the merged caps actor |
| `gui/window.py` | Section + Screenshot buttons removed from the toolbar (still in the menus) |

## 2.2 — UI polish

| File | |
|---|---|
| `gui/icons.py` | **new** — drawn icons |
| `gui/style.py` | **rewritten** — separate light/dark colours, system accent colour, rounded fields, capsule groups |
| `gui/widgets.py` | **new:** `CollapsibleSection`, `Capsule` |
| `gui/sidebar.py` | sections are collapsible; Mesh quality shows its level in the header, no tick marks (was looking disabled) |
| `gui/section_panel.py` | X/Y/Z and Flip/Center as segmented controls; short hint when off |
| `gui/window.py` | icon toolbar in capsules, Section toggle (⌥⌘X) synced with the sidebar; re-mesh results handled on the UI thread |
| `gui/scene.py`, `gui/section.py` | selection outline and plane use the system accent colour |

## 2.1 — selection, mesh quality, section

| File | |
|---|---|
| `gui/section.py`, `gui/section_panel.py`, `gui/widgets.py` | **new** |
| `gui/scene.py` | **new:** click picking + highlight, `replace_parts()` for re-meshing, section hooks; grid and Fit now use the model's bounds |
| `gui/sidebar.py` | **new:** Mesh quality and Section blocks, list ↔ 3D selection. Switch moved to `widgets.py` |
| `gui/window.py` | **new:** background re-meshing, remembered quality, Esc to deselect, sidebar scrolls on short windows |
| `cad/step.py` | `read_step()` unchanged in behaviour; **new** `StepFile` keeps the CAD in memory and re-tessellates at 5 levels |
| `formats.py`, `model.py` | **new:** optional `retessellate` / `quality` on the model |
| `mesh/`, `cad/stl.py` | unchanged |

## 2.0 — from the AppleScript droplet to a real app

| | Before | Now |
|---|---|---|
| App | AppleScript droplet → `launch.sh` → Python (Python icon in Dock) | py2app bundle: own icon and name, one process |
| UI | VTK buttons drawn inside the 3D view | Qt window: native menus, toolbar, side panel |
| Long part lists | paged buttons | scrolling list + filter |
| Opening a 2nd file | new Python process (~2 s) | new window in the running app |
| Light/dark | white only | follows macOS |
| Readers (`mesh/`, `cad/`, `formats.py`, `model.py`) | — | **unchanged** |
| `ui.py` | VTK-button UI | replaced by `gui/` (`scene.py` keeps its drawing logic) |
