# Changelog

Every version of Mesh Viewer, newest first. Each table lists the files that
changed and what changed in them. (The version number lives in
`meshviewer/__init__.py`.)

**Version numbers:** 2.X marks a new stage of the app — six so far:

| | Stage |
|---|---|
| 2.0 | from the AppleScript droplet to a real app |
| 2.1 | viewing: selection, mesh quality, section, CAD formats, measure, appearance |
| 2.2 | Edit and Export |
| 2.3 | analysis: cell quality, Info, CFD (y+) and CFD mode (inflation layers) |
| 2.4 | simulation results, the icon bar sidebar, more formats, plots |
| 2.5 | organized the macOS way: menu bar, undo, Settings, one name per thing, inspector |

Everything inside a stage is 2.X.Y — new tools in a section, tweaks and fixes alike.
A stage can start with betas, 2.Xb1, 2.Xb2… (shown "2.X beta 1"), before 2.X.
The versions were renumbered to this (twice before, the last time harder):

<details><summary>Now · was · before that</summary>

| Now | Was | Before that |
|---|---|---|
| 2.4.8 | 2.18.4 | 2.20.1 |
| 2.4.7 | 2.18.3 | 2.20 |
| 2.4.6 | 2.18.2 | 2.19.2 |
| 2.4.5 | 2.18.1 | 2.19.1 |
| 2.4.4 | 2.18 | 2.19 |
| 2.4.3 | 2.17 | 2.18 |
| 2.4.2 | 2.16.1 | 2.17 |
| 2.4.1 | 2.16 |  |
| 2.4 | 2.15 |  |
| 2.3.15 | 2.14.2 |  |
| 2.3.14 | 2.14.1 |  |
| 2.3.13 | 2.14 |  |
| 2.3.12 | 2.13.2 |  |
| 2.3.11 | 2.13.1 |  |
| 2.3.10 | 2.13 |  |
| 2.3.9 | 2.12.2 |  |
| 2.3.8 | 2.12.1 |  |
| 2.3.7 | 2.12 |  |
| 2.3.6 | 2.11.4 | 2.36 |
| 2.3.5 | 2.11.3 | 2.35 |
| 2.3.4 | 2.11.2 | 2.34 |
| 2.3.3 | 2.11.1 | 2.33 |
| 2.3.2 | 2.11 | 2.32 |
| 2.3.1 | 2.10 | 2.31 |
| 2.3 | 2.9 | 2.30 |
| 2.2.6 | 2.8.6 | 2.29 |
| 2.2.5 | 2.8.5 | 2.28 |
| 2.2.4 | 2.8.4 | 2.27 |
| 2.2.3 | 2.8.3 | 2.26 |
| 2.2.2 | 2.8.2 | 2.25 |
| 2.2.1 | 2.8.1 | 2.24 |
| 2.2 | 2.8 | 2.23 |
| 2.1.23 | 2.7.3 | 2.22 |
| 2.1.22 | 2.7.2 | 2.21 |
| 2.1.21 | 2.7.1 | 2.20 |
| 2.1.20 | 2.7 | 2.19 |
| 2.1.19 | 2.6 | 2.18 |
| 2.1.18 | 2.5.6 | 2.17 |
| 2.1.17 | 2.5.5 | 2.16 |
| 2.1.16 | 2.5.4 | 2.15 |
| 2.1.15 | 2.5.3 | 2.14 |
| 2.1.14 | 2.5.2 | 2.13 |
| 2.1.13 | 2.5.1 | 2.12.1 |
| 2.1.12 | 2.5 | 2.12 |
| 2.1.11 | 2.4.3 | 2.11 |
| 2.1.10 | 2.4.2 | 2.10 |
| 2.1.9 | 2.4.1 | 2.9.1 |
| 2.1.8 | 2.4 | 2.9 |
| 2.1.7 | 2.3.2 | 2.8 |
| 2.1.6 | 2.3.1 | 2.7 |
| 2.1.5 | 2.3 | 2.6 |
| 2.1.4 | 2.2 | 2.5 |
| 2.1.3 | 2.1.3 | 2.4 |
| 2.1.2 | 2.1.2 | 2.3 |
| 2.1.1 | 2.1.1 | 2.2 |
| 2.1 | 2.1 |  |
| 2.0 | 2.0 |  |

</details>

## 2.5.1 — Contours (was Results), each in its tab, with a color bar over the 3D view; Swap Axes and ⌘0 on plots; Show ▸ Axis Indicator; mesh feature edges: no floating zig-zags, gaps bridged, smooth curves in one piece

| File | |
|---|---|
| `gui/panels/contours.py`, `gui/panels/contour_editor.py` (new; `gui/panels/results.py` gone) | **Results is now Contours, laid out as Plots**: New Contour, then a fold-out per contour (`ContourEditor`, on a card, Rename… · Delete under it), each with its own field, Unit in file / Shown in, Color by, **Color scale** (was Scale), Min / Max, Show color bar and ▸ Color Bar. The 3D view draws the **active contour** (`ContoursPanel.active`: the one whose tab or fold-out was opened or that was edited last); Color the boundaries stays in the tool's header. A field's units are shared by every contour and by Plots (`set_units`). A results file starts with Contour 1; a file saved by 2.5 gets its one Results setting as Contour 1. Remembered per file (`results` → on, active, units, contours) |
| `gui/window_pages.py`, `gui/window.py`, `gui/sidebar.py`, `gui/inspector.py`, `gui/sections.py` | **A tab per contour** under the view (**3D View** (was 3D Model) · Inflation Layers · contours · plots; right-click: Open, Rename…, Delete): it shows the model colored by that contour; **the 3D View tab shows the model alone** (no contour, no color bar: `ContoursPanel.tab`); editing a contour opens its tab. **Each 3D tab has its own view** (`_view_state`, `_switch_view`, `_apply_view`): its camera and Show ▾ toggles (mesh edges, feature edges, faces, bounding box, origin, axes, grid, axis indicator) — turning or toggling in one never changes another; a contour's tab opened the first time starts as the view it came from. The 3D View's axes, grid and axis indicator are the app's (Settings); a contour's tab keeps its own. The file remembers the 3D View's view as before (also when saved from a contour's tab) and each contour's in its settings (`view`). **Each tab shows and hides parts on its own** — the 3D View, every contour, every plot (`_switch_parts`; a contour's `view["hidden"]`, a plot's `hidden`, the file's `hidden` the 3D View's): hiding a boundary in a plot's or a contour's tab leaves it in the others; a plot is cut, and a contour's auto range taken, with its own tab's parts (`PlotsPanel._visible`, `ContoursPanel._shown`); the parts list keeps its order and filter. **Color the boundaries is gone**: a contour's tab always shows its contour. **What the Measuring Tool measured stays drawn** when another tool or tab is shown (`Measure.paused`, `picking`: a click picks parts meanwhile; back in the tool, measuring goes on where it was). **A tab and its fold-out open together** (contours and plots): choosing a tab opens its fold-out in the right sidebar, folds the others and scrolls to it (`Sidebar.reveal`, `expand_only`, `Inspector.reveal`); opening a fold-out shows its tab. Deleting a contour removes its tab and fold-out. The tool `results` → `contours` (a remembered open "results" tool opens Contours) |
| `render/colorbar.py` | **New: the color bar over the 3D view** (`ColorBar`, `scene.colorbar`): vertical, at the top-left corner, the field's name and unit on top (regular weight, can be hidden), tick marks and their values on the right (`tick_label`: 1000 written out, not 1e+03); a number that would run into its neighbor is left out, its tick mark stays, the two ends always written (`_labeled`); smooth or in bands between the ticks; **Height and Width** apart, 60–160 % of `BASE` (the text keeps its size); **Text color** Auto (for the background) · White · Black. Fonts in points for the view, so the title is the same size when first drawn as after (it came out twice too big on a Retina screen: the view's DPI is set only once it is first drawn). Plain VTK 2D actors anchored to the corner (they stay there when the window is resized); dragged with the mouse (`hit`, `drag`, kept inside the view); drawn again for Save Screenshot at its scale (`add_to`; dark text on a transparent picture) |
| `core/fields.py` | `ramp_t` (where a value sits, 0…1, linear or log), `ramp_table` (the colors 0…1, smooth or in bands, `band_colors`: the map's ends and evenly between), `ramp_rgb` takes `edges`; **`ticks`**, ends included — Tick spacing Linear: exactly 2–15 ticks evenly up the bar, each with the value at its place (geometric on a log color scale); Log, spaced logarithmically across the range (above zero): on a linear color scale the values evenly in log10, each where it falls; **on a log color scale the round values** (1 · 2 · 5 × 10ⁿ…, at most Ticks, `_round_log`) where they fall, as a log axis is marked — evenly in log10 put them exactly where Linear does, so Log looked as if it did nothing |
| `render/overlays.py` | **The boundaries in the bar's bands**: `ResultsView` gives each node its place on the scale ("ResultT") and colors it with a lookup table (`results_lut`) interpolated before mapping, so bands keep sharp borders across the triangles; selected parts lighter through the table's second half (was: an RGB per node) |
| ▸ Color Bar (`contour_editor.py`) | In the forms layout (label · field · unit · ?): Colors; **Height**, **Width** and **Ticks** (2–15) as sliders with their value in the last column; **Tick spacing** Linear / Log (Log off when the range reaches zero or below); **Text color**; Smooth colors; Show title; then **Reset Color Bar**, right-aligned on the last row (no line above): height, width, ticks, tick spacing, text color, smooth colors, title, **its place (the top-left corner)** and the color map back; Show color bar stays |
| `gui/sidebar_layout.py`, `gui/inspector.py` | **No gutter when the right sidebar scrolls**: Qt's own scrollbar took 8 points from the page when it appeared, pushing the cards left; `FitScroll` keeps it off (it still scrolls: the wheel, `ensureWidgetVisible`) and shows an **overlay scrollbar** (`overlay`) floating in the page's right margin, so the cards line up on the right whether the tab scrolls or not |
| `gui/viewport.py` | **Dragging an overlay**: a left press on the color bar moves it instead of the camera (an open hand over it, closed while dragged) |
| `render/screenshot.py` | Save Screenshot draws the color bar, and the colors over the parts (contours, y+, the walls, cell quality), which it left out before; the XYZ indicator only when shown |
| `core/plots.py`, `gui/panels/plots.py`, `gui/pages/plots.py` | **Flip Y works at once**: the page read the flip worked out at the last cut, so the switch changed nothing until the plot was cut again (`y_flipped`: as set, or cp's own). **Swap** (▸ Axes' title row): X ↔ Y — what each axis shows, with its Min / Max, Log and Flip (`m["swap"]`). The Fit button under Axes gone: **View ▸ Fit (⌘0)** fits the plot shown, the 3D view otherwise (`fit_view`; a double-click on the plot still fits). **Data filters** under Values and Along (> min, < max, the unit beside them; `value_min` / `value_max`, `along_min` / `along_max`, in the units shown, empty: open): points outside either are left out of the curve, the reference points and the auto ranges. Axes ▸ Min / Max: **4 significant figures** when the zoom or a drag set them, the auto value in gray when empty, **as typed** when typed (`typed`; `NumberField.typed_text`). **🔒 Lock** (Axes' title row): the wheel, the trackpad, a drag and a double-click no longer zoom or pan the plot (`lock`). **A plot's fold-out reorganized** (`gui/forms.py`): Plane (Normal to · ✎, Position · unit, the slider the whole width), Plot (Values and its filter, Along · Normalize and its filter), ▸ Axes (columns named as the plot's axes — x/c, Y, cp…, `sync_names` — and Swap; Min, Max, Log, Flip), Data (Import… · Export…) |
| `gui/window_bars.py`, `gui/window.py`, `gui/app.py`, `render/appearance.py`, `gui/icons.py` | **Show ▸ Axis Indicator** (Show ▾ and View ▸ Show): the XYZ arrows in the corner on or off, on by default, the same in every window and remembered (`appearance/axis_indicator`, `set_axis_indicator`); its icon the SF Symbol move.3d (a drawn one where it is missing); lock / lock.open for a plot's Lock |
| `render/screenshot.py`, `render/svg.py` (new), `render/colorbar.py`, `gui/pages/plots.py`, `gui/window_export.py`, `gui/sheets.py` | **Save Screenshot as PNG, JPEG or SVG**, by the file's extension (`save_image`, VTK's PNG and JPEG writers; a JPEG gets white where the picture is see-through); the save sheet offers the three, a name without an extension gets the chosen one's (`ask_save`). **SVG is real vector drawing**, no picture inside: the 3D View and contour tabs (`svg_text`) project the visible facets through the camera, lit from it as the view is, in the parts' or the contour's colors (the same lookup table; a contour's facets split where its value changes, `_split`, so its gradients show), cut by the section with its filled cut faces, sorted back to front (painter's algorithm) with the mesh edges, feature edges and a drawing's lines as `<line>`s; then the color bar (`ColorBar.svg`: rects or a gradient, ticks, text) and the XYZ axis indicator; the view's background gradient (or none). Not drawn: the grid and its numbers, y+ / wall / cell-quality colors, measurement marks. **On a plot's tab, Save Screenshot saves the plot** (`PlotPage.save_picture`): PNG / JPEG at the scale asked, SVG painted through a QSvgGenerator (paths, polylines, text). GL2PS was not used: it leaves out the contours' colors, drawn through a texture |
| `render/element_details.py`, `gui/panels/selected.py`, `gui/sidebar.py` | **Measure Selected ▸ Field Values** (files with solution fields): after a line, every field over what Select ▾ picked (`field_values`) — a node its own value (several: their mean), edges the length-weighted mean, mesh triangles, feature faces and parts (Part: the parts selected) the area-weighted mean, a volume cell its value or its corners' mean; titled as in Contours (`Avg. Pressure p` for a mean), in Contours' units (`ContoursPanel.shown_values`), with a line saying how (length- or area-weighted); hidden with no fields or nothing picked. Part now shows the selected parts' field values too |
| `gui/panels/cfd.py` | **Color by y+ grayed** while there is no y+ to paint: no wall picked, no flow (density, viscosity, speed) or no first cells to measure (a surface mesh) |
| `tests/test_results.py`, `tests/test_plots.py`, `tests/test_sidebar.py`, `tests/conftest.py` | Tests: Contour 1 for a results file; New Contour (its tab, its fold-out open, the other folded), independent fields and ranges, tab ↔ fold-out, rename, delete, remembered, a 2.5 file migrated, the tool named Contours (`ContourTool` reads the active contour as the old tool); ticks (exact count, Linear / Log spacing on linear and log colors, at or below zero), tick numbers, crowded numbers; the title the same size first and after, regular; Ticks, Height, Width sliders; Text color; Show title; Reset Color Bar and the layout; Flip Y at once, Swap Axes and back, ⌘0 on a plot, a plot's tab and fold-out together; Axis Indicator; the bar dragged with the mouse; the 3D View without contours, each tab's own camera and Show ▾ (and Settings untouched), the file keeping the 3D View's view, log-on-log round ticks, Reset back to the corner, Include > / <, the plot fold-out's layout and axis names, the overlay scrollbar with no gutter, a tab switch drawing one frame (`test_viewport.py`); each tab's own hidden parts (contours and plots), no Color the boundaries, the marks kept out of the Measuring Tool, the Values and Along filters with their units, 4 significant figures and typed Min / Max, Lock, PNG / JPEG / SVG screenshots — the SVG valid XML with polygons and lines and no picture, a contour's colors and bar, a plot as paths and text (`test_formats.py`); Field Values: a node, one and two edges (length-weighted), two triangles and a part (area-weighted), in Contours' units, hidden with nothing picked or no fields (`test_select.py`); Color by y+ grayed on a surface mesh and available with first cells (`test_cgns_tools.py`) |
| `core/features.py` | **Floating and zig-zag smooth edges go** (`_anchored`): a smooth edge with both ends in the open (meeting no sharp edge, surface end or other smooth edge) is dropped, however long, unless it closes on itself; a smooth edge that **zig-zags** — turning one way then back at half its turns or more, or at three turns or more with half its turning undone (`_zigzag`: rows of mesh diagonals rippling across a face) — is dropped too. A smooth curve (an S turns back once) and a straight line stay |
| `core/features.py` | **Gaps bridged** (`_bridge`): where two feature edges (3 mesh edges at least) stop facing each other, a path of up to 8 mesh edges (`BRIDGE_EDGES`) that stays on their line or in their plane (within 2°), turns less than 30° at each point and always the same way round, and goes on smoothly into the other feature edge, is added: they become one feature edge. Done for sharp edges (after `_tidy`) and for smooth edges (before `_anchored`); the feature faces are split along the bridges. ONERA M6: the tip curves now reach the leading edge, and the wing is 3 faces (upper, lower, tip) instead of one leaking through the gaps |
| `core/features.py` | **Smooth curves stay in one piece** (`_runs`): a mesh's feature edge is no longer cut where it leaves the line or plane of its first mesh edges — only at a corner: a turn over the feature angle (30°) at one point, or a kink over 25° (`CORNER_DEG`) at least twice the turn either side (a coarse mesh's curve turning 27° at each point stays whole). A helix is one feature edge; cuts where another feature edge meets one (`cut_at_junctions`) are as before. Coarse fin: 302 feature edges to 276 |
| `tests/test_select.py` | Tests: a zig-zag between two sharp edges dropped, an arc and an S kept, a floating line dropped, a closed loop kept; a 4-edge gap on a line and in a circle bridged (one feature edge after), a 10-edge gap and two side-by-side edges not; a helix, a coarse circle not cut, a lone 27° kink and 90° cut |
| `tests/run_all.py`, `tests/conftest.py`, `tests/fixtures.py` | **The tests twice as fast** (94 s → about 43 s, the same 556 checks): every file in one app and one process (`conftest.SHARED`; before each file `fresh_start`: no window, a new scratch settings file, the app's settings as at launch), a file that crashes it run again on its own, each file's time shown, `run_all.py plots select` for some, `--isolated` for the old way; the test files made again only when `fixtures.py` changes (`_data/.made-by`); the tests' app drops macOS's FileOpen of the script (the "Unrecognized file type" window and sheet) |
| `tests/test_sidebar.py`, `tests/test_formats.py`, `tests/test_plots.py`, `tests/test_mac.py`, `tests/test_core.py` | Fewer windows opened for one check: "opens on Contours", "no solution fields", the CGNS summary, "Plots: not for 2D" and Hide Face checked on a window already open; the camera-pause check waits 0.4 s (`CAMERA_PAUSE` 0.3 for it) instead of 0.9 s; 200 fast slides instead of 400; Open Sample's folders put back after test_mac |
| `meshviewer/__init__.py` | Version **2.5.1** |

## 2.5 — Organized the macOS way: menu bar, undo, Settings, inspector; STEP assemblies, Select ▾ and Measure Selected, Inflation Layers in 3D, DXF drawings with their text, smooth zoom

The five betas rolled into one release (FEA and transient results wait for a later
version). The last changes first, then each beta as it came out.

### 2.5 — the release

| File | |
|---|---|
| `render/picking.py`, `render/elements.py`, `render/style.py` | **2D files: Select ▾ Node and Edge pick the nearest one on screen**, within 10 points (`PICK_PX`), instead of needing a hit on a line one pixel wide: the points and lines of the parts shown are projected to the screen (`to_display`) and the nearest is taken (`nearest_on_screen`, `Elements.click_2d`). A node within 7 points (`NODE_SNAP_PX`) wins over the line through it. Nothing that close: a click inside a cell picks as before. A part's mesh edges are made once (`mesh_edges`) |
| `render/picking.py`, `render/elements.py`, `render/measure.py`, `gui/panels/measure.py` | **Snap to edges** (the Measuring Tool on 2D files, was Snap to vertices there): a click snaps to the nearest line within 10 points, or to a line's end or a corner (a 2D mesh's nodes) within 7 (`Elements.snap_2d`); also just outside the axes. 3D files keep Snap to vertices |
| `gui/undo.py`, `render/camera.py` | **Camera undo in steps you can follow**: camera moves are one step only while they are the same kind (turning, panning, zooming, the view buttons) with no pause over 0.8 s (`CAMERA_PAUSE`); a drag or a burst of zoom steps is never cut in two (`camera_gesture` = kind and serial, `new_gesture`). Before, a whole session of moves could be one ⌘Z |
| `gui/sidebar.py` | **Measure Selected opens by itself** when Select ▾ picks a node, an edge, a face or a cell (its Measure tab comes forward when the right sidebar is shown) |
| `render/editing.py`, `core/units.py`, `gui/panels/plots.py` | Cleanup: the scene's old edit undo (`apply_edit`, `undo_edit`, `reset_edits`: the window's Undo does it), `field_quantity` and an unused import removed. Saved settings and file memories load as before |
| `meshviewer/__init__.py`, `gui/welcome.py` | Version **2.5** |
| `README.md`, `docs/screenshots/` | **README shorter**: what 2.5 does in a few lines, the formats, download, build and run; five new screenshots (STEP assembly with a section, CGNS volume mesh cut, transonic results with plots, inflation layers in 3D, the layer stack) |
| `CHANGELOG.md`, `docs/release-notes-2.5.md` | The betas rolled into 2.5 |
| `tests/test_select.py`, `tests/test_mac.py` | 2D pick tolerance (a line and a node 6 points away picked, 20 away not; a node beating its line), Snap to edges (a line and a corner), Measure Selected opening on a pick, camera undo split by a pause and by another kind of move |

### 2.5 beta 5 — Measure Selected, Volume Cell, free points on 2D files; inflation thickness in 3D and the layer stack; STEP assemblies, colors and materials; parts list sorted and filtered by size / volume; DXF for a quick look; Undo / Redo of the selection and the camera, in the toolbar; Left / Right Sidebar; Rotate Camera 90° Left; 2D meshes in Select ▾; the selection outline on the feature edges; Negative up plots −cp; the tools in one layout; DXF text, dimensions and arrowheads; smooth zoom to the cursor; fixes

| File | |
|---|---|
| `render/elements.py`, `gui/window_bars.py` | **Select ▾ on a 2D mesh**: Part, Mesh Node, Mesh Edge, **Mesh Cell** (its triangles and quads; "1 mesh cell selected"), Feature Node, Feature Edge — no Feature Face (a face zone is its part). A click on a boundary line with Mesh Cell picks the cell beside it (`_cell_beside`). The kinds a file offers in one place (`kinds_for`, `title_for`) |
| `core/features.py` | **Fixed**: Feature Edge / Feature Node on a 2D mesh raised an error (its boundaries are lines, with no faces). A part of lines has its lines as feature edges (`_lines_only`); a face zone's outline is cut where one boundary gives way to the next (`cut_at_junctions`: also where another part's feature edge lying on it ends). BluntCone_2D: the outline in 4 (symmetry, wall, outlet, inlet) |
| `gui/sidebar.py`, `gui/widgets/sections.py` | **The Parts / Boundaries list can't be folded**: no chevron, its header doesn't close it (`CollapsibleSection(locked=True)`) |
| `render/appearance.py` | **Fixed**: a bigger axis label size (Settings) moved the XYZ arrows in the bottom-right corner (their viewport grew with it). The corner stays the same; the letters grow (`label_size`) |
| `gui/window_pages.py`, `gui/window.py`, `gui/style.py` | **The tabs under the view, evenly padded**: as much room above the tabs as below (the scrollbar's room was all below), no dividers between tabs (2 px apart), the same padding in each, short names at least 36 px wide |
| `render/scene.py` | **A selected part's outline follows its feature edges** — a mesh's sharp and smooth edges, a CAD part's face borders, as Show ▸ Feature Edges (`_has_feature_lines`) — plus its silhouette; it was every place the triangles bend over 30° (bits of tessellation). 2D zones and drawings as before |
| `gui/pages/plots.py` | **Hovering a plot follows the line**: the point under the cursor anywhere along a segment, the values in between taken linearly (it jumped from mesh crossing to mesh crossing) |
| `gui/pages/plots.py` | **Negative up plots the values' opposite**, and the vertical axis says so (*−cp*), ticks the usual way; reference points too. No more "negative up" tag in the corner |
| `core/plots.py`, `gui/panels/plots.py`, `gui/pages/plots.py` | **A plot's normal stays as typed** (Edit Plane), not rescaled to length 1, as in the Section tool; the plot's subtitle shows it so. Exactly 1 along X, Y or Z is that axis |
| `tests/test_select.py`, `tests/test_plots.py`, `tests/test_sidebar.py` | 2D mesh kinds and picks, boundary lines as feature edges, Mesh Cell beside a line, no Feature Face; the outline with the feature edges; hover between two points, −cp and reference points with Negative up, the normal as typed; the parts list can't fold; the XYZ corner the same for any label size |
| `gui/undo.py`, `render/camera.py`, `render/scene.py`, `gui/window.py` | **Undo / Redo the selection and the camera**: the parts selected (a click, the list, Esc) and the camera (turning, panning, zooming, views, Fit, Perspective) are steps in Edit ▸ Undo (⌘Z / ⇧⌘Z). Recorded once done (`_Done`: pushing doesn't redo it); camera moves one after another with nothing else in between are one step (`mergeWith`, gone if back where it started). The camera is compared before each frame (`_note_camera`, `camera_snapshot`, `same_camera`: in parallel view, wherever it stands along its line of sight); selection changes through `Scene.on_selection`. What a command itself changes (a part hidden drops out of the selection) is not recorded apart (`_applying`). Recording starts once a file has opened (`Changes.watch`) |
| `gui/window_bars.py`, `gui/icons.py`, `gui/dialogs/toolbar.py` | **The toolbar**: Undo · Redo (SF Symbols arrow.uturn.backward / forward; grayed when there is nothing) after the left sidebar; **Export and Screenshot in one pill**; **Rotate Camera 90° Left** (SF Symbol rotate.left, ⌘L, also View menu) in the views' pill — the picture turns a quarter turn counterclockwise about the line of sight; not on 2D files. Customize Toolbar…: Undo, Redo; Export, Screenshot (one group) |
| `gui/window_bars.py` | **View ▸ Hide Toolbar / Show Toolbar** (⌥⌘T): for the window until it closes, never remembered — a new window and every launch start with the toolbar shown |
| `gui/window_bars.py`, `gui/dialogs/toolbar.py`, `gui/pages/section_cut.py`, `gui/window.py` | **Sidebar is now Left Sidebar, Inspector Right Sidebar** (View menu, hover texts, Customize Toolbar…, messages). `inspector` stays the code's name |
| `gui/panels/results.py`, `gui/sidebar.py` | **Color the boundaries**: its switch is in the Results title, right of the name (as Section's) |
| `gui/sections.py`, `core/export.py`, `setup.py` | **No solver named on screen**: the Results note ("a solver's Tecplot .dat of its boundaries"), Export's UGRID format ("UGRID + .mapbc — boundary names"), the Finder kind ("UGRID Mesh File"). README keeps its mentions |
| `tests/test_mac.py`, `tests/test_sidebar.py` | Selection and camera undo (three camera moves one step, toolbar Undo / Redo, nothing new recorded on redo); Left / Right Sidebar; Export · Screenshot pill, Undo · Redo, Rotate in the views' pill, Hide / Show Toolbar, the Results switch in its title |
| `core/cad/occt.py`, `core/model.py`, `core/formats.py` | **STEP / IGES: the file's assemblies, colors and materials**: each part keeps the assemblies above it (`path`), its color (the instance's, the part's, else its faces' most common: `_shape_color`) and its material (name, description, density and unit: `_label_material`, read only when the file has materials — OCP crashes on `FindAttribute` with the material tree's id, so `TDataStd_TreeNode.Set_s` finds it). `CadFile.part_info` → `Model.part_info` (kept up to date when re-meshed). The reader asks for colors and materials (`SetColorMode`, `SetMatMode`) |
| `render/scene.py`, `gui/memory.py` | **Parts in the file's colors** (`default_colors`); the palette for the others. Only colors you chose are saved; a color saved before that is just the palette's gives way to the file's |
| `gui/panels/parts.py` | **The parts list follows the file's tree**: an assembly row per assembly (the top one open), the usual groups (base names, McMaster) inside each (`_fill_tree`, `_fill_auto`) |
| `gui/sidebar_menu.py` | **Material…** in a STEP / IGES / BREP part's right-click menu: a sheet with its material (name, description, density) or "No material metadata embedded" |
| `gui/sidebar.py`, `core/mesh/cgns.py`, `core/mesh/ugrid.py` | **The line under the parts list counts parts for STEP / IGES / BREP** ("STEP CAD · 35 parts") and **cells for CGNS / UGRID** ("CGNS mesh · 10,024,470 cells", from the zone sizes / header: `cell_count`, no cells read); faces otherwise |
| `gui/sidebar.py`, `gui/panels/parts.py`, `core/part_filter.py` (new), `render/scene.py`, `gui/icons.py` | **Sort** (⇅ next to the filter, SF Symbol arrow.up.arrow.down): Name, Size (bounding-box diagonal), Volume (exact for CAD solids, else from closed triangles; none last), Reverse Order; kept for every file. **Filter limits**: `size > 20`, `volume < 1000`, `<=`, `>=`, `=`, with a name or not, in the toolbar's unit (`part_filter.parse`, `passes`) |
| `gui/sidebar.py`, `gui/icons.py` | **The filter's options button** (SF Symbol line.3.horizontal.decrease, was a sort button): Sort By, Reverse Order · **Colors: File Color / Randomized Color** · **Isolate McMaster Parts**; kept for every file (settings `parts/colors`, `parts/mcmaster`) |
| `render/scene.py`, `gui/window.py` | **File Color / Randomized Color** (`Scene.color_mode`, `set_color_mode`): parts still in their default color take the mode's (the file's, or the palette's); colors you chose stay. A file opens in the window's mode |
| `gui/panels/parts.py` | **McMaster Parts only when asked**: off (default), McMaster-Carr parts stay in their places; on, they are all in one section on top of the list, even across assemblies, and size / volume limits don't hide them. **The tree's indent is 13 px** (was 20): deep assemblies stay compact |
| `gui/sidebar_menu.py` | The part menu: **Rename…, Color…, Material…** between two lines |
| `gui/panels/parts.py`, `gui/sidebar_menu.py`, `gui/undo.py`, `gui/memory.py`, `render/scene.py` | **Rename a group** (Rename Group… in its right-click menu, or Return): a group of parts renames its parts (the common start of their names) in one undo step (`Changes.rename_group`); a STEP assembly row is renamed in the list only (`Scene.group_names`, remembered per file, undoable). McMaster Parts and 2D's Faces / Boundaries can't be renamed |
| `gui/style.py`, `gui/sidebar.py` | The filter options button is a **rounded square like the filter field** (`#FilterButton`) |
| `gui/sections.py`, `gui/window_bars.py` | The Measure tool is now the **Measuring Tool** (View ▸ Measuring Tool ⇧⌘M) |
| `render/picking.py` | **2D files: measure between any two points inside the axes** (`flat_point`: the click on z = 0, inside the grid's box), not only on a line or a cell |
| `render/elements.py`, `gui/icons.py` | **Select ▸ Volume Cell** (meshes with volume cells: CGNS, UGRID, .msh; `icons/cell.svg`): the cell a hair behind the click (`vtkStaticCellLocator`, built once), on a boundary or on the section's cut; drawn filled with its rim. Cleared when Edit moves the model |
| `render/element_details.py` (new), `core/element_info.py` (new), `gui/panels/selected.py` (new), `gui/sidebar.py` | **Measure Selected** (Measure tab, below the Measuring Tool): the last pick in numbers. Node: coordinates, distance to the origin, the boundaries it is on. Edge: length, ends, midpoint, ΔX ΔY ΔZ, dihedral angle (the two faces at its middle, found by place across CAD faces), direction if straight, plane normal if planar, and for a circle / arc its radius, diameter, center (`fit_circle`) with *Show diameter* (drawn in the accent color). Face: area, normal, centroid, perimeter. Mesh triangle: area, centroid, type, skewness / aspect ratio / scaled Jacobian (`core/quality.py`), its boundary. Volume cell: volume, type, centroid, quality |
| `gui/pages/inflation.py`, `gui/pages/section_cut.py` (removed), `core/geometry2d.py` (removed), `gui/window.py` | **The Inflation page's Section tab is gone**: the page is the layer sizes, with **the layers stacked on the wall** to the left of the plot, to the plot's scale (alternating shades, the boundary layer dashed across, hover dims the others) |
| `render/overlays.py`, `gui/panels/inflation.py` | **Inflation Layers ▸ Show thickness in 3D**: the walls (or the whole model) moved out by the layers' total thickness, a see-through shell (`thickness_shell`: each point so every face at it moves out by the thickness, least squares — a box grows by exactly that; inward for internal flow) |
| `gui/panels/inflation.py` | **Inflation Layers rearranged** in two groups, each with its Formulas and Values: **Fluid & Freestream** (Fluid; Altitude; ▸ Properties — temperature, density, viscosity, sound speed, folded, their values in its title; Mach / Speed on one row; Direction with the Vectors switch) and **Boundary Layer & Sizing** (Walls with Pick…; Regime (was Flow); Length L; Target y+ with the Compressible switch; First layer; Layers / Rate on one row; Next cell); then "✓ Stack · δ₉₉" and "✓ Next cell · y+". The picking row takes no room when not picking |
| `gui/pages/inflation.py`, `gui/window.py`, `gui/panels/inflation.py` | **Show in 3D and Flip on the Inflation page** (beside "Layer sizes"; they were a switch in the tool), kept per file (`set_3d`); the page follows the tool. **The plot's right margin fits its labels** (as much room after the longest as left of the stack) |
| `render/overlays.py` | **The layers' shell, fixed at sharp edges** (the ONERA M6 trailing edge and tip: spikes): each point moves along its angle-weighted normal, far enough that the faces at it move out by the thickness, at most twice it (`offset_field`). **The side is chosen** where the shell folds over itself least (`auto_side`: the area of triangles turned over; the M6's wing skin: into the air, not into the wing); Flip takes the other. **The walls' feature edges** are drawn on the shell, moved with it (`offset_lines`) |
| `gui/panels/plots.py`, `gui/pages/plots.py`, `core/plots.py`, `gui/window.py` | **Each plot's ▸ Axes** (a subsection, closed at first): X and Y **Min / Max** (empty = auto), **Log**, **Flip**; **Fit**. Only how the plot is drawn (`view_changed`: no new cut). On the plot, **the wheel zooms** around the cursor, **a drag pans**, **a double-click fits** — written back to its Axes (`ranges_changed`, `set_ranges`). Log axes: ticks at 1, 2, 5 × 10ⁿ, values at or below 0 left out (none left: it says so). **Negative up is gone**: cp starts with Y flipped (the true values, negative at the top), as any plot can now |
| `gui/window.py`, `gui/memory.py` | **The meshing level is kept per file** (Meshing Control): a STEP / IGES / BREP opens at its own level, else at Settings' |
| `gui/widgets/sections.py` | **A line above every subsection** (`CollapsibleSection(sub=True)`: Properties in Inflation Layers, each plot and its Axes, CFD's groups) |
| `gui/app.py` | **CAD files open at Medium** (Settings ▸ CAD meshing control: Medium unless changed; it was Same as Last Time) |
| `gui/window_bars.py`, `render/elements.py`, `gui/inspector.py`, `gui/sections.py`, `gui/sidebar.py`, `gui/panels/info.py` | **DXF for a quick look**: no left sidebar (its button grayed), Select ▾ offers **Edge** (a line from corner to corner) and **Node** (an end) — a click picks one and Measure ▸ Info says its length or coordinates (`show_picked`); only the Measure tab (View and Analyze grayed, `enable_tabs`, `tabs_for`; the View / Analyze Tools menu items too); opens on Info, not measuring. The window's Select kind is kept for the next file |
| `tests/test_formats.py`, `tests/test_select.py`, `tests/test_sidebar.py`, `tests/test_round_f.py`, `tests/test_plots.py` | Plot Axes (flip, ranges, the wheel, Fit, log), cp flipped with its true values, the meshing level kept per file; Show in 3D / Flip on the page, the auto side (a box out, a thin plate out), the page following the tool; Measure Selected (an edge at 90°, a face, a node), circle fit, straight, dihedral, Volume Cell, 2D points inside the axes only; group and assembly rename with undo; the Inflation page without tabs, the thickness shell; File / Randomized Color (chosen colors stay), Isolate McMaster Parts (none by default, on top when on, past size limits), the indent, the part menu's lines; STEP material and color read (an assembly made in memory), CGNS / UGRID cell counts and the summary; assemblies in the list, sort, size / volume limits, Material… text, Medium by default, the summary in parts; DXF: no left sidebar, tabs grayed, Edge / Node picks shown in Info |
| `README.md`, `ARCHITECTURE.md` | Measuring Tool, Measure Selected, Volume Cell, group rename, the inflation thickness and stack; Mesh Cell on 2D meshes, Negative up, hover along a line; Left / Right Sidebar, the toolbar, undo of the selection and camera, the Results switch; STEP assemblies, colors, Material…, sort and filter limits, DXF |
| `gui/forms.py`, `gui/widgets/basics.py`, `gui/widgets/numbers.py`, `gui/widgets/sections.py`, `gui/sidebar_layout.py` | **One set of form pieces for every tool**: `column` (a tool's layout, no margins: its card pads it), `switch_row`, `pair`, `xyz_fields` (Origin / Normal), `button` / `buttons` (Flip, Clear, Undo \| Reset), `link` (was `_link`), `group_head` (a group's title and its buttons), `readout_grid` / `readout` (gray key, value on the right), `note`, `set_state` / `status_mark` (✓ / ⚠), `sheet_title`, `PAGE_MARGINS`. `rule` is one line for groups, subsections and tools (`sidebar_layout.divider` gone). `SpinField`: the stepping number box without trailing zeros (was three copies: Edit, Section, Cell Quality) |
| `gui/style.py` | **Status colors in one place** (`STATUS`: ok / warn / bad — CFD's max y+, Cell Quality's inverted cells, the Inflation page and checks); `#InfoLine[state]`, `#SheetTitle`; **a tool that doesn't apply has a lighter name** (`#SectionHeader[unavailable]`, `tertiary`; not with Increase Contrast) |
| `gui/sidebar.py`, `gui/panels/meshing.py` (new) | **Meshing Control is a panel like the others** (`MeshingPanel`: the slider, the triangle count, the level in the header); the sidebar keeps `quality` and `quality_requested`. Unavailable tools: their name lighter (`CollapsibleSection.set_unavailable`); a tool without a card (Plots) gives its gray reason a card |
| `gui/panels/cfd.py`, `gui/panels/fluid.py` | **The CFD tool (meshes) laid out like Inflation Layers**: *Fluid & Freestream* (Fluid; Altitude; ▸ Properties folded, their values in its title — `_props_title` shared; Mach / Speed on one row; Direction with Vectors) and *y+ Estimator* (Boundary; Regime; Length L with Back to Auto Length under it; Target y+ with the Compressible switch), a line between them; then the result card and Color by y+. The groups no longer fold (settings `cfd_flow`, `cfd_yplus` unused) |
| `gui/panels/section.py`, `gui/panels/edit.py`, `gui/panels/measure.py`, `gui/panels/selected.py`, `gui/panels/info.py`, `gui/panels/quality.py`, `gui/panels/results.py`, `gui/panels/plots.py`, `gui/panels/inflation.py` | **Every tool on the shared pieces**, rows in the 4-column grid and labels aligned: Section (X / Y / Z, Flip, Center, Origin / Normal as in a plot's plane), Edit (its own grid gone; *Changes* is a group title with Undo \| Reset; its CAD note gone — the tool's gray reason says it, with "export as STL"), Measuring Tool, Measure Selected, Info (*File unit* a form row; the counts as read-outs: gray names, values right), Cell Quality (*Metric*, was *Measure*: the name of a tab; the inverted-cells line only for volume meshes, red when there are some), Results (Color by, Scale), Plots (Points with Import… \| Export…), Inflation Layers. No layout or behavior changed beyond these |
| `gui/sections.py`, `gui/panels/info.py`, `gui/sidebar.py` | **Drawings open Info and Measure Selected**: Measure Selected says what a click picked; Info's copy of it is gone (`show_picked`) |
| `gui/pages/plots.py`, `gui/pages/inflation.py`, `gui/dialogs/export.py`, `gui/dialogs/screenshot.py`, `gui/dialogs/toolbar.py`, `gui/dialogs/units.py` | A plot page's title is a `#PageTitle` (as the Inflation page's), both pages with the same margins; **Inflation Layers** (was "Inflation layers") on its page; the sheets' titles through `sheet_title` |
| `tests/test_select.py` | Drawings: the picked edge and node in Measure Selected (open for drawings) |
| `core/cad/dxf.py`, `setup.py` | **DXF text, dimensions and arrowheads**, drawn as lines on their layers: TEXT / ATTRIB as the letters' outlines (`text2path`, the system's fonts, matplotlib's DejaVu if none; letters flattened to 1/40 of their height), MTEXT split into TEXT first (`MTextExplode`, in an in-memory block); DIMENSION from its block (one saved without it drawn by ezdxf first, `_render_bare_dimensions`); SOLID / TRACE / 3DFACE as their closed outline (`corners`: SOLID's 0-1-3-2 order, triangles, OCS). Blocks, dimensions, leaders, tables taken apart by `flatten`, which keeps DXF's rule: inside a block, layer 0 goes on the reference's layer (a dimension's lines were on layer 0); `Defpoints` left out. No Qt. `fontTools` packaged |
| `core/cad/dxf.py` | **Letters, not boxes**: a style's font that isn't installed is replaced by ezdxf with the closest name — Onshape's *Noto Sans* became *Noto Sans Oriya* on a Mac, with no Latin letters; a font missing some of the text's characters gives way to Arial Unicode, Arial, Helvetica or DejaVu (`text_font`, `_covers`: the font's character map). MTEXT's `\U+2212` (a minus sign in a stacked tolerance) is decoded before ezdxf splits it (it left "U+2212") |
| `render/appearance.py`, `render/scene.py`, `gui/memory.py`, `gui/window_bars.py` | **Drawings: the bounding box is their frame**, on by default, in the lines' color (white in dark mode, black in light mode; `bbox_color`), not pickable; its toolbar toggle shown for drawings. Remembered per file under its own key (`drawing_bbox`: saves from before had it forced off) |
| `gui/app.py`, `gui/window.py` | **Drawings: grid and axes off by default**, with their own setting (`appearance/drawing_axes`, `_axes_key`): turning the grid on for a drawing leaves 3D files as they are, and the other way round |
| `gui/viewport.py`, `render/camera.py` | **Smooth zoom toward the cursor**, as in a CAD app on the Mac: the viewport takes the wheel, the trackpad's two-finger scroll and its pinch itself (`wheelEvent`, `event`: `NativeGesture`) instead of VTK's fixed steps toward the middle. Trackpad: continuous, `exp(pixels × 0.004)` per event (its glide too); pinch: `exp(magnification)`; mouse wheel: × 1.2 a notch, eased in by a 15 ms timer (35 % of what is left each tick). `Camera.zoom_at`: the point under the cursor stays put — parallel: the scale changes and the view slides (in XY on 2D files, still seen from +Z); perspective: the camera moves along the cursor's line, the focal plane with it — limits 1e-5 to 1000 model diagonals; `_place_camera` still sets the parallel camera FAR_BACK. One frame per step, edges hidden until 0.3 s after the last (`wheel_zoom` → `_zoom_step`), a zoom one Undo step |
| `tests/test_viewport.py` | Zoom: a wheel notch × 1.2 eased in (one frame per step at most), the point under the cursor kept (parallel, perspective), a trackpad scroll at once, wheel back, still along Z from +Z, edges back after, one Undo step |
| `tests/test_formats.py` | DXF: TEXT and MTEXT as segments, a SOLID triangle and a TRACE as closed outlines (lengths), a SOLID in a block on the block's layer, a dimension on its layer, no Defpoints; a missing font replaced by one with the letters, `\U+2212` as a minus sign; a drawing's bounding box on (white / black), grid and axes off, Grid on kept for drawings only |
| `ARCHITECTURE.md`, `README.md`, `CLAUDE.md` | The form pieces and the layout of a tool; Meshing Control's panel; DXF and Measure Selected; DXF text, dimensions, arrowheads; a drawing's bounding box, grid and axes |

### 2.5 beta 4 — Select ▾ (nodes, edges, faces); Results files open again; Results reorganized: usual CFD / FEA fields and their units, log scale, Position X / Y / Z; Plots in Analyze; Edit Plane; Meshing Control

| File | |
|---|---|
| `icons/` (new), `gui/icons.py`, `setup.py` | **The Select ▾ icons are the app's own** (`icons/*.svg`: Part, Mesh Node, Mesh Edge, Mesh Triangle, Feature Node, Feature Edge, Feature Face — a cube showing what is picked), drawn in the text color like the SF Symbols (white when checked, gray when off), at their size (`FILES`, `_file_image`); copied into the app's Resources. The drawn ones stay as fallbacks |
| `gui/window_bars.py`, `gui/window.py`, `gui/dialogs/toolbar.py`, `gui/icons.py` | **Select ▾** in the toolbar (after Show ▾; also Edit ▸ Select, and in Customize Toolbar…): what a click in the 3D view picks — Part · Mesh Node, Mesh Edge, Mesh Triangle (meshes only) · Feature Node, Feature Edge, Feature Face. Its icon is the kind chosen (SF Symbols, drawn fallbacks); a window keeps it from file to file (a mesh kind is Part on CAD); none for drawings |
| `render/elements.py` (new), `render/picking.py`, `render/scene.py`, `render/editing.py` | **Picking nodes, edges and faces**: the node of the clicked cell nearest the click, its nearest edge, the cell itself; the feature face clicked, the feature edge or node of that face nearest the click. ⌘/⇧-click adds or removes one, a click on nothing clears, Esc / Deselect All too. Drawn in the accent color (dots, thick lines, a fill with its rim), cut by the section, follows Edit's moves and hidden parts |
| `core/features.py` (new) | **Feature faces, edges and nodes**: CAD faces (`face_id`) or, on a mesh, cells joined across edges bending less than 30°; feature edges where faces meet or the surface ends, cut at nodes (3+ edges meet, one ends, or the faces either side change). Points at the same place are one, so edges go across CAD faces. Vectorized (a 270,000-triangle box: 0.25 s), made once per part when first needed |
| `core/features.py`, `render/elements.py` | **Feature edges of meshes**: a feature edge stays **straight or in one plane** — its mesh edges are followed while the next stays on the line of the first ones (aligned) or in the plane of the first three (coplanar, within 2°), and it doesn't turn by more than 30°; otherwise a new feature edge starts there (`_runs`; a closed loop starts at its sharpest corner). **Where another feature edge meets one partway, it is cut in two** there, also across a mesh's boundaries (`cut_at_junctions`: all the boundaries are done together; edges lying on each other, a border two boundaries share, cut nothing). The cut points are feature nodes. CAD keeps its faces' edges as they are |
| `core/features.py` | **Smooth edges on meshes**: where the surface bends gently (a cylinder meeting a sphere on top) there was no feature edge. Now three mesh edges in a row, each going on from the last (turning under 30°), that are **aligned** or **coplanar** in a plane crossing the surface, within 0.002° (more for a float32 file's rounding), are a feature edge (`_smooth_edges`), and the feature faces are split along them. A smooth edge must **go somewhere**: from feature edge to feature edge, or closed on itself (`_anchored`) — rows of points that line up by chance on a lofted surface (the ONERA M6 wing, meshed along its sections) stop in the middle of a face and are peeled off; lattices of such rows (pieces under 3 mesh edges between crossings) and smooth edges with a corner where nothing meets them go too. Straight lines on a flat area don't count. Not on a regular grid (over 10% of the mesh edges found). On a mesh, every mesh edge bending over 30° is a feature edge (not only where feature faces meet), so a trailing edge that is sharp in places and slightly less in others is one edge. ONERA M6: the far-field's join (36 mesh edges) found, 3 faces (half cylinder, half sphere, outlet); the wing: its root, its trailing edge in one piece, no chance lines; 0.4 s for the whole file. A 300,000-triangle random sphere: no edge, 0.6 s |
| `render/scene.py`, `render/elements.py` | **Show ▸ Feature Edges on meshes draws the same edges Select picks**: the sharp ones and the smooth ones (`Elements.feature_lines`), so the cylinder-to-sphere join shows |
| `render/scene.py`, `render/elements.py`, `core/features.py` | **Feature edges of STEP / IGES / BREP files are the borders of their faces**, as the CAD program draws them (Onshape…): a wing's leading edge, its tip, both lines of a blunt trailing edge — not where the triangles bend over 30° (which missed tangent edges and drew bits of tessellation). A border goes once no face beside it shows (Hide Face). The 289-part nose cone: 0.12 s |
| `core/features.py` | **Smooth edges on meshes, closer to the CAD**: a smooth edge is kept when the surface **creases** across it (1° or more each mesh edge: a rounded leading edge, a blunt trailing edge's lines, a wing tip) or **bends differently either side** (a cylinder, straight along its length, meeting a sphere; measured one row of mesh edges away), not a row of points that lines up by chance (`_distinct`). The tidying keeps a long edge with one end in the open (rows branching off an edge, or loose at both ends, go). Files written in float32 (read as float64) are allowed their rounding (`_precision`): the M6 leading edge's points were on a line to 1e-7. ONERA M6 wing: root section, leading edge, trailing edge, tip curves and tip cap line, as in Onshape |
| `core/features.py` | **Cleaner mesh feature edges**: a sharp line carries on across mesh edges bending half the feature angle when they go straight on from it (`_hysteresis`: a trailing edge wavering around 30° is one line); crease bits that are mesh noise go — under 15 mesh edges ending in the open, or under 3 between two junctions (a knot where a coarse mesh turns a tight corner) (`_tidy`); a long smooth edge with one end the mesh doesn't show stays (it was dropped, and the edges it met after it: the M6 leading edge stopped short of the tip, the upper tip curve lost its front). Feature faces stay bounded by every edge bending over 30°. ONERA M6: the wing's tip corner from 26 feature edges to 10, its leading edge to the tip, both tip curves whole |
| `gui/sidebar.py` | The line under the parts list says what is picked ("1 feature face selected") and, below, the node's X / Y / Z, the edges' length or the faces' area, in the toolbar's unit; Clear clears it |
| `tests/test_select.py` (new) | Feature faces / edges / nodes of a box, a cylinder, a sphere; a plate's 4 straight sides, a ring's 2 circles, a helix cut into planar pieces, two crossing plates cutting each other's sides, a shared side cutting nothing; a capsule meshed from random points (float64 and float32) giving its 2 smooth circles and 3 faces, a random sphere giving no edge, a structured cylinder (quads and triangles) only its rims; STEP feature edges = face borders, a border going with both faces beside it hidden; a gap in a sharp line filled, short loose creases dropped, a long one kept; every kind picked on the STEP box and a CGNS mesh, the selection line, Deselect All, Part on CAD, no Select for a drawing |
| `README.md`, `ARCHITECTURE.md` | Select ▾ |
| `gui/panels/plots.py` | **Fixed**: a results file whose saved plot cuts across a boundary that is flat along the plot's normal (only a symmetry plane shown, cut along Y) never finished opening: the slider position came out huge (range ~1e-18 wide) and raised an `OverflowError` while the window was set up. The slider now stays within its ends |
| `gui/panels/results.py`, `gui/window.py` | **Results ▸ Field ▸ Position X / Y / Z**: the nodes' coordinates as a field, in the toolbar's unit until one is picked for it (typed Min / Max go back to auto when that unit changes); with *Gradient*, \|∇x\| without a unit |
| `gui/panels/results.py`, `gui/panels/plots.py`, `gui/widgets/select.py` | **The Field list by subject**, a gray header over each: Flow (Mach number, Speed, velocity u / v / w), Pressure (cp, p), Density and Temperature, Wall (y+, cf…), Turbulence, Other, Position. The Plots' *Values* menu the same. `MenuSelect.addSection` |
| `core/field_kinds.py` (new), `core/units.py`, `core/fields.py` | **The usual fields and their units**: CFD (Mach, speed, velocity, cp, pressure, total pressure / temperature, density, temperature, enthalpy, y+, cf, wall shear stress, heat flux, heat transfer coefficient, k, ε, ω, vorticity, μ, μt, νt) and FEA (displacement, von Mises, Tresca, principal and component stresses, safety factor, strains, reaction force), by the names solvers write. Each has a title, a group in the Field menu and a quantity, or none (Mach, y+, cp, cf, safety factor). New unit tables: stress (GPa, ksi with pressure), strain, force, heat flux, heat transfer coefficient, energy per mass, k, ε, rates, kinematic viscosity, µm. `field_quantity` reads the catalog |
| `gui/panels/results.py` | **Results reorganized** in two groups. The field: *Field*, *Unit in file* (only where there is a choice: *As written* or a unit), *Shown in* (only once the file's unit is known), and a line saying what applies ("Mach number has no unit.", "As written in the file…", "Mesh Viewer doesn't know this field…", positions: the file's unit). A known field offers its quantity's units, an unknown one every unit by quantity, a known field with no unit nothing. Then the colors: *Color the boundaries*, *Color by* (was *Show*: Value / Gradient), *Scale*, *Colors*, the scale, Min / Max. Hover texts are the names only |
| `gui/panels/results.py`, `core/fields.py`, `render/overlays.py` | **Scale ▸ Log**: colors by powers of ten (`ramp_rgb(…, log=True)`); Min is the smallest value above zero, values at or below zero take the lowest color, the scale's middle number is the geometric middle; remembered per file |
| `gui/sections.py`, `gui/window_pages.py` | **Plots** moved from the Measure tab to **Analyze**, below Results; their cuts show in 3D while Analyze is shown |
| `gui/sections.py`, `gui/inspector.py`, `gui/window.py`, `gui/dialogs/settings.py` | **Mesh Quality is now Meshing Control**, and Settings ▸ General ▸ *CAD mesh quality* is *CAD meshing control* |
| `gui/window_pages.py` | **Fixed**: the tabs under the view (3D Model · plots) had square corners and more room after the last tab than before the first: the scroll area filled the pill's whole rect, and it was sized before its font was set. Renaming a plot now renames its open page too |
| `gui/pages/plots.py`, `gui/style.py` | **Fixed**: a plot's page was black in light and dark mode; it has the page color now |
| `gui/widgets/basics.py`, `gui/icons.py`, `gui/style.py` | **Check marks in the Show menu** (and any menu of checkable items with icons): a column on the left with the SF Symbol checkmark, as in macOS menus. Qt's styled menus drew the icon in the check's place, so what was on didn't show |
| `gui/panels/section.py`, `gui/panels/plots.py`, `gui/icons.py` | **Edit Plane** (SF Symbol pencil) right of *Normal to* X / Y / Z, in the Section tool and in section plots, replaces the gear: it shows the plane's origin and normal right under *Normal to* |
| `gui/sidebar.py` | **Fixed**: a line above Info and CFD, the first tools of the Measure and Analyze tabs. The lines were set only for the tab shown when a file opened |
| `gui/icons.py`, `gui/window_bars.py`, `gui/widgets/select.py` | Pull-downs (Show, the unit) and pop-up menus (Field, Colors, units…) show the SF Symbol **chevron.down** (`paint_chevron`) instead of ▾ or a drawn mark |
| `tests/fixtures.py`, `tests/test_mac.py`, `tests/test_formats.py`, `tests/test_viewport.py` | The tests pass on a Mac: the STEP box made with OpenCASCADE (no `cadquery`), Settings… looked for in the app menu on macOS, the drawing colors checked from light mode, the window floated above others while the screen is grabbed |
| `tests/test_results.py`, `tests/test_sidebar.py`, `tests/test_plots.py`, `tests/test_mac.py`, `tests/test_formats.py` | Field kinds and groups, the unit rows (known with a unit, known without, unknown, position), Edit Plane, Position X / Y / Z, the log scale, a plot across a flat boundary, no line above the first tool of a tab, Plots in Analyze, Meshing Control |
| `README.md`, `ARCHITECTURE.md` | Plots in the Analyze tab, Position X / Y / Z, grouped fields, units, log scale, Meshing Control |

### 2.5 beta 3 — Parts on the left, tools on the right in three tabs, a lighter toolbar

| File | |
|---|---|
| `gui/icons.py` | **Fixed**: toolbar and menu icons sometimes went missing while a window was empty (on the welcome screen): a grayed SF Symbol was drawn with a see-through color and came out blank. Symbols are drawn solid, then faded |
| `gui/app.py`, `gui/macos.py` | **Fixed**: Settings and About still slid a full-screen window away. They now open as a window of the front window, on its Space |
| `gui/inspector.py` (new), `gui/sidebar.py`, `gui/sections.py`, `gui/window.py`, `gui/style.py` | **The inspector**: the tools moved to a panel right of the 3D view, in three tabs — **View** (Mesh Quality, Section, Edit), **Measure** (Info, Measure, Plots), **Analyze** (CFD, Cell Quality, Results). View ▸ Inspector (⌥⌘I), View ▸ View / Measure / Analyze Tools (⌥⌘1–3). The icon bar and its **+** are gone. A tool works while it is in view (open, in the tab shown): Measure stops measuring on another tab, Plots draw their cuts in 3D while the Measure tab shows. Each file remembers its tab and the tools open; files open on View, results files on Analyze ▸ Results, drawings on Measure |
| `gui/sidebar.py`, `gui/sidebar_layout.py` | **The sidebar is the parts list**, the whole height of the window (no more line to drag between the tools and the list) |
| `gui/window_bars.py`, `gui/dialogs/toolbar.py` (new), `gui/window.py` | **A lighter toolbar**: Sidebar · views · **Show ▾** (edges, faces, axes, grid…) · the **unit ▾** (with File Unit…) · Export · Screenshot · Inspector. **View ▸ Customize Toolbar…** (or a right-click on the toolbar) chooses which groups show, for every window; Settings can be added. Everything stays in the menus |
| `gui/memory.py`, `render/scene.py` | A file remembers the inspector's tab and the tools open (what was shown in the icon bar is no longer read) |
| `gui/widgets/formulas.py` | Formulas open just left of the inspector |
| `tests/test_sidebar.py`, `tests/test_mac.py`, `tests/test_plots.py`, `tests/test_formats.py` | The tabs and their tools, a tool in view or not (measuring, cuts), per-file memory, Customize Toolbar, the View menu |

### 2.5 beta 2 — Fixes; welcome screen, samples, Revert to Original, sheets, VoiceOver

| File | |
|---|---|
| `gui/app.py`, `gui/window_bars.py` | **Fixed**: *Check for Updates…* was twice in the app menu (the window's menu bar and the no-window one both added it), and Settings showed as "Preferences…" with an icon. The three app-menu items are made once and live in one menu bar |
| `gui/macos.py` (new), `gui/app.py` | **Fixed**: Settings and About opened on the desktop, sliding a full-screen window away. They now open on the Space you are in |
| `gui/window.py`, `gui/memory.py` | **File ▸ Revert to Original…**: after a confirmation sheet, everything remembered about the file is forgotten and it opens as the first time |
| `gui/welcome.py`, `gui/samples.py` (new), `setup.py`, `resources/samples/` | **Welcome screen** in an empty window: Open…, recent files, *Try a Sample* — the ONERA M6 wing (its three boundaries from `onera_m6.cgns`, 5 MB instead of 416 MB) and the avionics bay STEP. Also File ▸ Open Sample. Samples save their exports in Documents. The empty window hides its sidebar |
| `gui/feedback.py` (new), `gui/jobs.py`, `gui/window.py`, `gui/panels/cfd.py`, `gui/panels/quality.py` | **Progress**: a small spinner in the toolbar while a file opens, the model is re-meshed, y+ or the cells are measured (hover: what it is doing); no more spinning wait cursor. **Errors** in a sheet that says what failed, why, and what to do next, with *Report a Problem…* |
| `gui/sheets.py` (new), `gui/window_export.py`, `gui/panels/plots.py`, `gui/sidebar_menu.py`, `gui/dialogs/settings.py`, `gui/widgets/basics.py` | **Sheets**: save panels (Export, Screenshot, CFD Settings, plot CSV), Import Points, Rename, Color…, the background image, and "close without exporting?" slide down from their window instead of blocking the app |
| `gui/report.py` (new) | **Help ▸ Report a Problem…**: a GitHub issue filled with the app, macOS and library versions (nothing is sent until you press Submit) |
| `gui/access.py` (new), `gui/style.py`, `gui/widgets/basics.py` | **Accessibility**: VoiceOver reads a name for every icon button and switch; switches show a ring when they have the keyboard focus; *Increase contrast* (System Settings ▸ Accessibility) makes lines, borders and gray text stronger |
| `tests/test_mac.py` | Welcome screen and samples, Revert to Original (and Cancel), spinner, VoiceOver names, the app menu made once |

### 2.5 beta 1 — The Mac way: full menu bar, undo, Settings, one name per thing

| File | |
|---|---|
| `gui/window_bars.py`, `gui/app.py`, `gui/window_pages.py` | **Full menu bar**: **Edit** (Undo ⌘Z, Redo ⇧⌘Z, Select All ⌘A, Deselect All ⌥⌘A, Hide Selection, Isolate Selection, Show All, Find… ⌘F → the parts filter), **Window** (Minimize ⌘M, Zoom, Bring All to Front, the open windows), **Help** (Mesh Viewer Help, Keyboard Shortcuts, Release Notes). View ▸ Units (the toolbar's units + File Unit…), View ▸ Show Next / Previous Tab (⌃⇥ / ⌃⇧⇥). Check for Updates… and Settings… in the app menu, also with no window open. Every toolbar button is in a menu. Sidebar is ⌃⌘S (macOS's own shortcut; was ⌥⌘S) |
| `gui/dialogs/shortcuts.py` (new) | Help ▸ Keyboard Shortcuts: every shortcut, menu by menu, read from the menus |
| `gui/undo.py` (new), `gui/sidebar.py`, `gui/sidebar_menu.py`, `gui/window.py` | **Undo / Redo for every change**: showing / hiding / isolating parts, colors, renames, hidden CAD faces, and the Edit tool's rotations, mirrors, moves, its Undo and Reset buttons. Edit ▸ Undo says what it undoes ("Undo Hide Wing"). Not the camera or the selection (the view, as in other Mac apps) |
| `gui/dialogs/settings.py` (new, replaces `gui/dialogs/appearance.py`) | **Settings… (⌘,)** instead of Appearance…: a window of its own with General · Appearance · Units tabs, every change at once, no OK button. New: *CAD mesh quality* (the level STEP / IGES / BREP open at, or the last one used), *Show lengths in* (the unit for a new file), the unit of meshes and triangle CAD that don't say theirs, and *Ask when a file is opened the first time* |
| `gui/window.py` | The title says "— Edited" while rotations / moves wait to be exported (with the dot in the close button, as before) |
| every file with words on screen | **One name per thing**, in Apple's style: American spelling (color, center, gray, meters); a plot is a *plot* (New Plot…, Rename Plot — "measurement" belonged to Measure); *CFD mode* is now *Inflation Layers*, like the page it opens; *cross section* is *section* (Plots ▸ Section, the page's Section tab); right-click *Hide Face* / *Show Hidden Faces* (were Surface); sidebar panels are *tools* (View ▸ Tools); Title Case for tool names, tabs and buttons (Mesh Quality, Cell Quality, 3D Model, Layer Sizes, Flip Side, Pick Faces…). Saved settings and file memories still load |
| `meshviewer/__init__.py`, `gui/dialogs/about.py`, `setup.py` | Version 2.5b1, shown "2.5 beta 1". The update check knows a beta comes before its release (2.5b1 < 2.5); macOS gets "2.5" as the app's short version |
| `gui/store.py` (new), `tests/conftest.py` | Settings are read and written in one place; the tests now use a scratch file, so running them no longer clears what the app remembers about your files |
| `core/model.py`, `core/cad/occt.py` | The CAD mesh quality names live in one list (Settings shows them without loading OpenCASCADE) |
| `tests/test_mac.py` (new) | Menus, every toolbar button in a menu, undo / redo of each kind of change, Settings tabs and their effect on opening a file, the beta version |

## 2.4.11 — STEP meshes: OpenCASCADE's own triangles again, faster

| File | |
|---|---|
| `core/cad/remesh.py` (removed), `core/cad/occt.py` | Faces are no longer meshed again: the triangles are OpenCASCADE's, as they come (the 2.4.10 even meshes added 2–4× the triangles and time for display only). The duplicate-triangle clean-up it needed goes too. OpenCASCADE's faster triangulator (Delabella) stays. Compared with 2.4.8, at the same Mesh quality: ONERA M6 air domain Medium 2 107 → 1 687 triangles, Very fine 0.55 → 0.18 s; the 300-part test assembly opens in 0.1 s instead of 3.3 s. Thin triangles and fans on some faces are back |
| `tests/test_core.py` | The STEP test checks the surface is closed and gets finer with the quality |

## 2.4.10 — Cleaner STEP meshes, no hole when zoomed in, even axis numbers

| File | |
|---|---|
| `core/cad/remesh.py` (rewritten), `core/cad/occt.py` | **STEP / IGES / BREP meshes are even.** Every face is meshed again to a target size (model size ÷ 20, 32, 50, 80, 130 for the five levels): long outline edges are cut in equal pieces (the same on both faces that share them), points are laid inside on a triangular lattice, then added where a triangle is too big or too thin, so the size grows smoothly away from small details. A cylinder is no longer long strips, a flat face around a small part no longer a fan of needles. On the ONERA M6 air domain at Medium: half of the triangles had an angle under 26°, now half are equilateral (60°); triangles under 15°: 28 % → 8 %. Faces with a pole (a sphere's cap) and very thin ones keep OpenCASCADE's triangles. More triangles than before at the same level (about 2–4×) |
| `core/cad/occt.py` | OpenCASCADE's own mesher runs with its faster triangulator (Delabella: 1.5–2.5×). Two faces meeting along a curve no longer leave a doubled thin triangle. Medium on the test files: 0.05–0.2 s |
| `render/camera.py`, `render/scene.py` | **No more hole in the model when zoomed in** (parallel view): after zooming in on a spot and turning, the camera could stand inside the model, and everything behind it was cut away. The camera is now kept far behind the whole model (the picture is the same). Switching to perspective keeps the size on screen |
| `render/camera.py`, `render/appearance.py` | **Axis numbers the same size on every axis** (parallel view): they were sized by their distance to the camera, so the nearest axis had the smallest numbers, and they grew when zooming in. A short axis gets fewer numbers (2–5 by its length) so they don't run into each other |
| `tests/test_viewport.py`, `tests/test_core.py` | Tests for the camera, the numbers' size and the new mesher (closed, no needles) |

## 2.4.9 — Faster and smoother; the code in smaller files

Nothing new to click: the same app, quicker. Times measured on three test files (300-part
STEP assembly, 1.6 M-triangle STL, CGNS volume mesh), without a graphics card — the
ratios matter, not the seconds.

| File | |
|---|---|
| `gui/viewport.py` (new) | **Each frame is drawn once.** The view drew the whole scene twice per frame shown (once to draw, once to put it on screen) — also on every frame of a turn or a zoom: about 1.8× faster. And several "draw again" during one click now make one frame (a unit change drew 5, *Select All* on 300 parts drew 300) |
| `render/scene.py` | **One outline** for the whole selection instead of one per part: *Select All* on 300 parts 20 s → 0.2 s. The outline of a selection over 300 000 triangles hides while the view moves. A part's colour / visibility settings are kept at hand instead of looked up by name (hide / show all 3×, isolate 5×) |
| `render/scene.py` | Surface normals were computed twice at opening (the app, then PyVista): once now |
| `core/cad/occt.py` | **Repeated parts of an assembly are meshed once** (a bolt used 40 times: one mesh, moved to each place): opening the assembly 10.5 s → 2.7 s, a mesh quality change 8.5 s → 1.1 s. Their triangles are now the same on every copy. Exact face areas are computed once, not at every refresh of the lists (unit change 5–7×) |
| `core/polys.py` | VTK's worker threads only on big parts (they cost more than they save on hundreds of small ones) |
| `render/section.py` | The plane's handle no longer draws a frame at each of its settings (cross section on: 1.6–4×; moving it: 4–7×) |
| `gui/widgets/select.py`, `gui/widgets/basics.py` | Pop-up menus don't measure every item again at each one added; one colour dot per colour (parts list 5× faster to fill) |
| `render/overlays.py` | Result colours no longer rely on a frame having been drawn |

**Code, for readers** (no behaviour change):

| File | |
|---|---|
| `render/scene.py` → + `picking.py`, `camera.py`, `editing.py`, `appearance.py`, `screenshot.py`, `style.py` | The 1 220-line Scene in six files, one subject each (530 lines for the main one) |
| `gui/widgets.py` → `gui/widgets/` | `basics`, `sections`, `select`, `numbers`, `formulas` (imports unchanged: `from meshviewer.gui.widgets import …`) |
| `gui/window.py` → + `window_bars.py`, `window_pages.py`, `window_export.py` | actions / toolbar / menus, pages and tabs, export and screenshot (857 → 440 lines) |
| `gui/sidebar.py` → + `sidebar_layout.py`, `sidebar_menu.py` | layout pieces, a part's right-click menu (863 → 640 lines) |
| `gui/panels/fluid.py` (new) | The fluid / speed / direction inputs that `cfd.py` and `inflation.py` each had a copy of |
| `gui/forms.py` | One `caption()`, `rule()` and `segmented()` instead of a copy in four panels |
| `core/cfd.py`, `gui/pages/section_cut.py`, `gui/panels/results.py` | Unused functions removed; comments about past versions rewritten as what the code does |
| `tools/bench.py` (new) | `python tools/bench.py file`: how long opening, a frame, selecting, hiding, cutting… take on your machine |
| `tests/test_viewport.py` (new) | An action draws one frame, and the screen shows it |
| `ARCHITECTURE.md`, `README.md` | The new files in the map; a *Speed* section with the rules that keep it fast |

## 2.4.8 — Plot tabs scroll; right-click a tab

| File | |
|---|---|
| `gui/window.py`, `gui/style.py` | The tabs under the view scroll sideways when there are too many plots (thin bar; the wheel or trackpad scrolls them; the open tab stays in view) |
| `gui/window.py` | Right-click a plot's tab: **Open**, **Rename…**, **Delete** |

## 2.4.7 — Units for results, any plane for a cross section, eye on each cut

| File | |
|---|---|
| `core/units.py`, `gui/panels/results.py`, `gui/pages/plots.py`, `core/plots.py`, `gui/window.py` | **Results ▸ Values in / Shown in** for fields with a unit (p, ρ, u v w, speed, T, μ): the unit of the file's numbers (— : as they are) and the one shown; the scale, Min / Max (with the unit beside them), the plots and their CSV follow. Remembered per field. cp, Mach, y+: no unit, the rows hide |
| `gui/panels/results.py` | The max · mean · min line and the *Values* button are gone |
| `core/plots.py`, `gui/panels/plots.py` | **Advanced plane** (gear on the *Plane* row): origin and normal in any direction; X / Y / Z light only when the plane is normal to one; Position = along the normal |
| `gui/panels/section.py` | The same gear: Origin / Normal are under it now |
| `gui/panels/plots.py`, `gui/window.py`, `render/overlays.py`, `gui/icons.py`, `gui/widgets.py` (`IconToggle`) | **Eye** next to each measurement's name: its cut in the 3D view or not (several at once), while Plots is in the sidebar |
| `gui/panels/plots.py` | *New Measurement…* without the card or the text under it |
| `gui/sidebar.py` | A grey line above the first analysis tool in the icon bar, like the one above + |
| `gui/style.py` | Every text box and menu 22 px high, 12 px text (they were tall on macOS) |

## 2.4.6 — Every section on a card; Section and Plots alike

| File | |
|---|---|
| `gui/sidebar.py`, `gui/style.py`, `gui/window.py` | **Every sidebar section on a grey card** (the Plots look), with cards and segmented controls inside a shade lighter; the sidebar opens a little wider so CFD fits on its card |
| `gui/panels/section.py` | **Section laid out like a Plots cross section**: *Plane* — Normal to [X Y Z] (lit when the plane is along one) and Flip; Position slider and Center; Origin / Normal; then *Show* — Fill cut faces, Show plane |
| `gui/panels/plots.py` | *Plane* / *Position* as in Section; **Normalize** instead of x/c; Along made of fixed X / Y / Z buttons (the plane's own axis hidden): Y now lights up when chosen (rebuilt buttons stayed unlit on macOS); New Measurement… on its card |
| `gui/icons.py` | Results: `waveform.path.ecg.text.page`; Plots: `chart.xyaxis.line` |

## 2.4.5 — Plots: no more crash when sliding, tidier controls

| File | |
|---|---|
| `core/polys.py` (`bare`), `core/plots.py`, `core/fields.py`, `core/export.py`, `core/cfd.py`, `render/overlays.py`, `render/quality_overlay.py`, `render/scene.py`, `gui/pages/section_cut.py` | **Crash fixed** (moving a cross section quickly): new surfaces were built from NumPy views of a part's points and faces, and VTK could keep pointers into memory NumPy freed. They now share the part's structure inside VTK (`bare`). The same pattern elsewhere (y+ and results colours, cell quality, export, CFD walls) fixed too |
| `gui/panels/plots.py` | The slider plots once it rests (40 ms), not on every pixel |
| `gui/panels/plots.py` | **Tidier measurement controls**: one card per measurement in three groups — *Cut* (normal to, at, slider), *Plot* (values, along + an x/c toggle, negative up), *Points* (Import… · Export…); *Rename… · Delete* under the card instead of the ⋯ button; the point count is gone (only problems are shown) |
| `gui/panels/results.py`, `render/overlays.py`, `core/fields.py` | *Highlight sharp changes* and *Jump over* removed (Gradient stays) |

## 2.4.4 — Plots (cross sections in tabs), gradients and sharp changes

| File | |
|---|---|
| `core/plots.py` (new), `gui/panels/plots.py` (new), `gui/pages/plots.py` (new), `gui/sections.py`, `gui/sidebar.py`, `gui/window.py`, `gui/memory.py`, `gui/icons.py`, `gui/widgets.py` | **Plots** (F13): *New Measurement…* (name + type) adds a sub-section in the sidebar and a tab under the 3D view (3D model · Inflation layers · one per measurement). Built to take more kinds; the first is the **cross section**: the visible boundaries cut by a plane normal to X / Y / Z (position typed or slid; the cut drawn in 3D while Plots is open), a field or the shape plotted along the cut, x/c, negative up (cp by default), hover for the numbers, reference points from a CSV, the points to a CSV. ⋯ menu: Show Plot, Rename…, Delete. Remembered per file, with the open tab. Not for 2D files yet |
| `core/fields.py`, `gui/panels/results.py`, `render/overlays.py` | **Results ▸ Show ▸ Gradient** (F15): |∇f| along the surface. **Highlight sharp changes**: faces where the field changes by more than *Jump over* % of its range, in pink over the colours, with their count |
| `render/scene.py`, `gui/panels/results.py` | Several listeners can follow shown / hidden boundaries (Results, Plots) |

## 2.4.3 — Gmsh / Fluent .msh, DXF drawings, colour maps

| File | |
|---|---|
| `core/mesh/msh.py` (new), `core/formats.py`, `requirements.txt`, `setup.py` | **`.msh` files**: Gmsh (through meshio; physical groups become parts) and Fluent (own reader, text and binary sections), 2D or 3D found from the file. 3D: boundaries + volume cells (Section cut, Cell quality, y+); 2D: the zones as faces and their boundary lines |
| `core/cad/dxf.py` (new), `core/formats.py`, `requirements.txt`, `setup.py` | **DXF drawings** (ezdxf): lines, polylines, arcs, circles, ellipses, splines and blocks, one part per layer, unit from `$INSUNITS`; shown flat, seen from above, measurable |
| `core/model.py`, `gui/sections.py`, `render/scene.py`, `gui/sidebar.py` | **Four kinds of file**: 3D mesh, 3D CAD, 2D mesh, drawing. Every section is listed for each; one that doesn't fit says why (Section and CFD: 3D only; Cell quality: meshes, 2D too). First-open sections: 2D meshes Edit · Measure · Cell quality, drawings Measure. Line-only parts are drawn without shading; 2D boundary lines drawn thick over the zones; "segments" for drawings, "Layers" for their parts |
| `core/fields.py`, `gui/panels/results.py`, `gui/widgets.py`, `render/scene.py` | **Results ▸ Colours**: the menu shows the colour maps themselves, no names: rainbow (new default), blue–white–red, thermal, grey, blue (blue–grey–red removed). The auto min / max is the shown boundaries' and follows when one is hidden or shown. Remembered per file |
| `render/scene.py`, `gui/window.py`, `gui/panels/edit.py`, `gui/memory.py`, `gui/widgets.py` | **2D files locked to +Z**: left / middle drag pans, right drag and the wheel zoom, the trackpad rotate is ignored; the view is squared to Z after every move and when a saved view is restored; no Iso / X / Y / Z or Perspective buttons (always parallel); Edit turns about Z only, mirrors X or Y, moves in X and Y |
| `render/scene.py`, `gui/window.py`, `gui/sidebar.py` | **DXF drawings, lines only**: no mesh edges / feature edges / faces, bounding box or origin buttons; no layer list; every line white on a dark background, black on a light one; black background in dark mode (Appearance can still change it) |
| `gui/widgets.py` | macOS: two menus in a row (Results ▸ Field and Colours) no longer overlap |
| `render/measure.py`, `gui/panels/measure.py` | **Distance ▸ From origin** switch: on, each click is one point (X / Y / Z, from the origin, to the section plane: the old Point tool); off (default), two clicks give the distance, with no origin line in between |
| `render/measure.py` | **Angle on 2D files**: click two lines (or cell edges): the angle between them in XY; the markers lie along the lines |
| `gui/panels/parts.py`, `gui/sidebar.py`, `core/model.py` | **2D list in two groups**: Faces (the cells) and Boundaries (the lines); right-click: Hide / Isolate Face or Boundary |
| `render/scene.py` | 2D files: lines stay while moving (Appearance's "hide lines" doesn't apply); the corner axes show X and Y only |
| `gui/window.py`, `gui/dialogs/units.py`, `gui/icons.py`, `core/model.py` | **✎ File unit** button (square.and.pencil) where the "no unit" button was: opens the file-unit sheet again; it still says what the file itself states |
| `render/scene.py` | 2D meshes: **Feature edges** draws the zones' outline, thick and over the mesh edges, so hidden or unnamed boundaries show. **Right-click** menu and clicks (Measure) work on 2D files: the 2D style held the mouse, so the release never reached them |
| `gui/sidebar.py`, `gui/style.py` | A narrow sidebar scrolls sideways too, with a thin horizontal scrollbar at the bottom |
| `core/quality.py` | Cell quality: no error when every cell has the same value (histogram) |
| `setup.py` | Finder: `.msh` and `.dxf` can open with Mesh Viewer |

## 2.4.2 — File unit, one Distance tool, formula links

| File | |
|---|---|
| `gui/dialogs/units.py` (new), `gui/window.py`, `gui/panels/info.py`, `gui/memory.py`, `render/measure.py` | **File unit**: the first time a file is opened, a sheet asks what unit its numbers are in (STEP / IGES: their own, mm, preselected; meshes: m; other CAD: mm). Remembered per file; **Info ▸ File unit** changes it. The toolbar's "no unit" button is gone: the toolbar unit is the one shown, converted from the file's |
| `render/measure.py`, `gui/panels/measure.py`, `render/section.py` | **Distance and Point are one tool**: click a point — its X / Y / Z, distance from the origin and to the section plane; click a second — the distance and ΔX, ΔY, ΔZ between them |
| `gui/widgets.py`, `gui/panels/cfd.py`, `gui/panels/inflation.py` | Formulas pop-ups open next to the sidebar, by the link that opened them. The y+ formula links to CFD Online, and a CFD Online link closes the y+ formulas (meshes and CFD mode) |
| `gui/panels/inflation.py` | **Next cell**: hover it — about 2 × the largest layer is a smooth step into the volume mesh; use about that size for the surface cells too (low aspect ratio) |
| `gui/pages/inflation.py`, `gui/panels/inflation.py`, `core/cfd.py`, `core/cfd_export.py`, `gui/dialogs/wall_help.py` | **y+ along the flow removed** (tab, curve, Values rows, export line). The y+ tile shows the estimated y+ |

## 2.4.1 — Icon bar sidebar, code reorganised, fixes

| File | |
|---|---|
| `gui/sidebar.py`, `gui/sections.py` (new), `gui/window.py`, `gui/memory.py`, `gui/style.py` | **Icon bar** left of the sidebar: one toggle per section (Info, Mesh quality, Section, Edit, Measure, CFD, Cell quality, Results); a section shows up closed. Every section is listed for every file; one that doesn't apply shows a grey note. Each file remembers which are on; first open: CAD = Mesh quality, Section, Measure · mesh = Section, Edit, Measure (+ Results for results files). CFD is one toggle: the y+ estimate on meshes, CFD mode on CAD. Hiding Section switches the plane off; showing it again puts the plane back as it was. Hiding CFD switches CFD mode (or the flow vectors and y+ colours) off, and back on when shown again; the inputs stay. The parts list is always shown, at the bottom: drag the line above it to make it taller or shorter (remembered); closed, only its header stays at the bottom. The sections scroll only when the window is too short (no scrollbar flashing while sections open), and the sidebar can be made narrow again. **+** under the icons (Analysis Tools): which of CFD, Cell quality and Results have an icon in the bar. The sections reach the sidebar's right edge (scrollbar at the edge). **View ▸ Sidebar Sections** |
| `gui/icons.py`, `gui/window.py`, `requirements.txt`, `setup.py` | **SF Symbols icons**, asked from macOS when the app runs (PyObjC), so none of Apple's files are in the project; drawn icons elsewhere. Hover: just the name and the shortcut. A line under the toolbar; toolbar groups, segmented buttons, fields, cards and the "?" buttons in solid colours (no light dots where they meet); thin sidebar scrollbars (no wide grey track). The y+ estimator's web link moved into the Target y+ "?" card |
| `gui/sidebar.py`, `gui/window.py` | Fix: the sidebar's scrollbar showed when everything fitted. The sections now scroll on their own, only when the window is too short; the parts list keeps the rest |
| `gui/window.py` | The projection toggle is now **Perspective** (on = perspective, off = parallel), ⌘5 |
| `render/overlays.py`, `render/scene.py` | Fix: a boundary selected while Results colours are shown is now visible (lighter, blue outline on top) |
| `gui/window.py` | Fix: in full screen, the Export save panel (UGRID) and the screenshot one opened as a separate window on the desktop; they now wait for the sheet to close, and UGRID uses a one-dot file type |
| `core/cad/remesh.py` (new), `core/cad/occt.py` | Fix: STEP / IGES / BREP faces with fans of thin triangles (a symmetry plane around a wing root) are redone: points added inside, graded from the edges, then Delaunay flips. Edges kept exactly, so faces still join; a face is only changed when its fans clearly drop; big open areas get points too (finer levels); computed once per face, at most 3 s per meshing |
| `core/mesh/polyhedra.py` (new), `core/mesh/cgns.py`, `core/mesh/volume.py`, `core/cfd.py` | Fix: CGNS meshes stored as **polyhedra (NGON_n / NFACE_n)** had no volume cells — no cut cells on the section, no y+, cell quality on the surface only. Their tetra, pyramids, prisms and hexa are now read. First cell height: wall normals made consistent |
| `core/mesh/cgns.py` | Fix: CGNS files whose MIXED sections carry a broken ElementStartOffset (filled with the element type, as some exporters write it — e.g. the ONERA M6 mesh) had no volume cells: no cut cells, no y+, cell quality of the surface. The offsets are now checked and, if wrong, found from the connectivity (10 M cells in a fraction of a second) |
| `core/fields.py`, `gui/panels/results.py` | Fix: STEP files showed a Results section (an internal id array was taken for a field). Only floating-point arrays count |
| whole package | **Code reorganised**: `core/` (no Qt), `render/` (VTK), `gui/` (Qt; `panels/`, `dialogs/`, `pages/`), absolute imports, shared `core/units.py`, `core/fields.py`, `core/geometry2d.py`, `gui/forms.py`; version notes removed from the code. `ARCHITECTURE.md` (new): the map. `tests/` (new): headless tests and test files |

## 2.4 — Simulation results on the boundaries (FUN3D / Tecplot)

| File | |
|---|---|
| `mesh/tecplot.py` (new), `formats.py` | Opens **Tecplot ASCII `.dat`** results as FUN3D writes them (`project_tec_boundary.dat`): one part per boundary ("boundary 1 WING" → WING) with every variable at its nodes. FEBLOCK and POINT packing, triangles and quads, cell-centred variables; a boundary written more than once keeps the last time step. Binary `.plt` / `.szplt` are not read |
| `gui/results_panel.py` (new), `gui/sidebar.py` | **Results** section, shown when the file has results: *Field* (every variable, plus *Speed* \|u, v, w\|), *Colour the boundaries*, the colour scale with its numbers, *Min* / *Max* (empty = auto), max · mean · min on the visible boundaries, and *Values* (every field) |
| `gui/cfd_view.py`, `gui/scene.py` | The colours are drawn over the visible parts: blue scale for fields of one sign, blue–grey–red centred on zero for signed ones (cp, u, v, w). Cut by the section plane, mesh edges follow the toolbar, hiding a part updates the colours and the numbers |
| `gui/memory.py`, `gui/window.py` | The field, range and on / off are remembered per file |

## 2.3.15 — Internal flow, exact CAD cross section; no y+ colours on the walls

| File | |
|---|---|
| `gui/inflation_panel.py`, `gui/cfd_view.py`, `gui/scene.py`, `cfd.py` | **Colour walls by y+ removed** (and the walls' re-splitting and per-point leading edges it needed). The y+ along the flow is now the page's curve only; the max / min / mean of the tile come from it |
| `cfd.py`, `gui/cfd_panel.py`, `gui/inflation_panel.py`, `gui/inflation_view.py`, `cfd_export.py` | **Flow: External / Internal (pipe or duct)**, in the CFD section and CFD mode. Internal: Reynolds number on the hydraulic diameter D (auto: 2ab / (a + b) from the walls' widths across the flow, or typed), skin friction of developed pipe flow (laminar 16 / Re below 2300, Petukhov above), no compressibility correction; the "boundary layer" is the pipe radius and the check is that the layers fit in it; y+ along the pipe: a flat plate from the inlet until the developed value |
| `cad/occt.py`, `gui/section_view.py` | Cross section of STEP / IGES / BREP: the walls are cut from the **CAD curves** themselves (smooth at any zoom), once the plane stops moving — the triangles while it moves |
| `gui/section_view.py` | Flow direction: three thin **inlet arrows** on the upstream edge of the view instead of the boxed arrow; a small dot / cross when the flow goes through the plane |

## 2.3.14 — Even y+ colours on CAD, max y+ tile, plots alike

| File | |
|---|---|
| `gui/inflation_panel.py`, `gui/cfd_view.py`, `cfd.py` | Colour walls by y+ (CAD): the walls are split into small triangles of about the same size (no edge longer than h, about 3 000 of them by area; cached) before the y+ is worked out and drawn, so the long thin triangles of the CAD tessellation no longer smear the colours; the colours are drawn without that mesh's lines. The leading-edge strips are square (a wing gets strips along its span, not cut through its thickness) |
| `gui/inflation_view.py` | the y+ tile is like the mesh's: **max y+ on the walls** big (green / orange / red against the target), *min · mean* beside it, the y+ at the end of the walls below; the check line gives max, min and mean |
| `gui/inflation_view.py` | the two plots share one look: a **y-axis title** along the axis (Height (mm) · y+ of the first layer), the x-axis title under it, reference lines named at the right with their value under the name, an end label moved off them; y+ along the flow **always shows the viscous sublayer** (y+ 5) and notes the first layer it uses |
| `gui/cfd_panel.py`, `gui/inflation_panel.py` | **Temperature** greyed out for *Air — altitude*, like density, viscosity and sound speed (the altitude's standard temperature); typed for water |

## 2.3.13 — CFD export, y+ along the flow, wall functions, temperature, update check

| File | |
|---|---|
| `gui/section_view.py` | Cross section: layers **stop where they would cross** — two walls facing each other meet half-way, a concave curve stops at its centre, another part stops them (each point of the cut gets the largest thickness it can take; the rings are trimmed where they cross). Long faces are split so the layers can stop part-way along them |
| `cfd_export.py` (new), `gui/export_dialog.py`, `gui/window.py`, `gui/inflation_panel.py` | Export (⇧⌘E), CAD files: tabs **3D model / CFD settings**. CFD settings writes the inflation layers for **OpenFOAM** (snappyHexMeshDict addLayersControls), **Fluent Meshing** (Add Boundary Layers), **STAR-CCM+** (Prism Layer Mesher), **Pointwise** (T-Rex), or a **CSV** of every input and computed value plus one row per layer |
| `cfd.py`, `gui/inflation_panel.py`, `gui/inflation_view.py`, `gui/cfd_view.py`, `gui/scene.py` | **y+ along the flow**: each wall point's distance from its own leading edge (strips along the flow, as for the auto length), local Reynolds number and skin friction → the y+ of the first layer. **Colour walls by y+** in CFD mode (same colours as the mesh's), a third tab **y+ along the flow** (curve against the distance from the leading edge, with the target), a check line and Values rows (max / mean / min) |
| `gui/wall_help.py` (new), `gui/cfd_panel.py`, `gui/inflation_panel.py` | **?** next to Target y+ (CFD section and CFD mode): resolve the wall (y+ ≈ 1) or use wall functions (30 – 300), with a plot of the law of the wall (Spalding, u+ = y+, log law, the zones), the buffer layer to avoid, and **Use y+ = 1 / 50** |
| `cfd.py`, `gui/widgets.py`, `gui/cfd_panel.py`, `gui/inflation_panel.py` | **Temperature** input (K / °C / °F; empty = the standard one): air keeps the altitude's pressure, ρ, μ, a follow T; water: density (Thiesen), viscosity (Vogel), speed of sound (Marczak; sea water Mackenzie) |
| `gui/memory.py`, `gui/window.py`, `gui/inflation_view.py`, `gui/section_view.py` | Remembered per file too: the Inflation page (open or not, which tab), Flip side, the flow arrow and the cross-section zoom |
| `gui/about_dialog.py` | **Check for Updates** asks GitHub for the latest release: newer → "A new update is available" + Download; same → up to date; older → this app is a pre-release |
| `cfd.py` | first cell layer: no crash on a mesh without volume cells |

## 2.3.12 — Simpler cross section; every number in Values

| File | |
|---|---|
| `gui/section_view.py`, `gui/inflation_view.py` | Cross section: only the **inflation layers** are drawn (boundary-layer and next-cell lines removed, layers always shown); the legend's only toggle is the **flow direction** arrow. **Flip side** button replaces External / Internal flow: by default the layers go on the outside of each closed cut of the model (tested against the cut itself, so CAD normals facing inward no longer matter; open surfaces follow their normals); Flip side puts them on the other side (internal flow). **Fit view** is a button like the others, in the header row. Smooth curves removed (it made the view lag) |
| `gui/inflation_view.py`, `gui/inflation_panel.py` | the line of small numbers under the page is gone; they're all in the **Values** pop-up (recovery factor added there for supersonic flow) |
| `README.md`, `docs/screenshots/` | new **CFD tools** section with three screenshots (CFD mode in 3D, layer size plot, cross section); features and *Using it* updated for CFD mode (walls, pick faces, cross section, Flip side), Colour by y+, Formulas / Values, right-click ▸ Hide Surface |

## 2.3.11 — Cross section: flow side, toggles, smooth curves, flow arrow

| File | |
|---|---|
| `gui/section_view.py`, `gui/inflation_view.py` | Cross section tab: **External flow / Internal flow** (which side of the walls gets the layers; replaces "Layers on the other side"); the legend sits top right like the plot's and each entry **shows / hides** what it names — inflation layers, boundary layer, top of the next cell, **flow direction** (an arrow of Flow ▸ Direction seen on the plane, or a dot / cross when it goes through the plane); **Smooth curves**: a smooth curve through the cut (centripetal Catmull-Rom through the surface points, points in the middle of flat facets dropped), sharp corners (> 30°) kept; a **Fit view** button |

## 2.3.10 — Cross section of the inflation layers

| File | |
|---|---|
| `gui/section_view.py` (new), `gui/inflation_view.py`, `gui/window.py` | Inflation page ▸ **Cross section** tab (replaces the "Near the wall" placeholder): it follows the section plane (sidebar ▸ Section) and draws its cut in 2D, facing the plane — the model in light grey, the walls in a dark line — with an **estimate of the inflation layers** on the walls: each layer is the wall outline pushed out along the wall's normal by the total thickness so far (mitred corners); layers closer than 2 px merge into a solid band; dashed = boundary layer, dotted = top of the next cell. Scroll to zoom, drag to pan, double-click or *Fit* to fit; *Layers on the other side* for open surfaces facing the other way; scale bar and legend. Messages when Section is off or the plane misses the walls |


## 2.3.9 — Inflation page: tabs, full-width plot, plain names

| File | |
|---|---|
| `gui/inflation_view.py` | the plot sits in a card with tabs — **Layer size plot** and **Near the wall** (a placeholder for the next view) — and takes the full width. Redrawn like the rest of the app: a bar per layer (its height), a line + soft area for the total thickness so far, light horizontal grid, the boundary layer (dashed) and next cell size (dotted) labelled on the right, a legend above, hover crosshair with the layer's numbers. Colour-blind-safe series colours for light and dark. *Near the wall* restyled to match |
| `gui/inflation_panel.py`, `gui/inflation_view.py` | plain names: First layer, Layers, Growth rate, **Next cell (× max layer height)**; tiles and checks say "boundary layer thickness", "total thickness of the layers", "max layer height" |

## 2.3.8 — CFD mode: Flow like the CFD section, growth 1–2, desired cell factor

| File | |
|---|---|
| `gui/inflation_panel.py`, `cfd.py` | CFD mode's **Flow** group is the same as the mesh CFD section: Fluid (air at an altitude, fresh / sea water at a depth, custom), density / viscosity / sound speed locked unless Custom, Mach and speed U, direction. The calculator takes these properties (`inflation(fluid=…)`); the 343 m/s option is gone (type U, or use Custom) |
| `gui/inflation_panel.py`, `gui/widgets.py` | **Growth rate** kept between 1 and 2 (`NumberField.setRange`: typed values snap in) |
| `gui/inflation_panel.py`, `cfd.py` | **Desired cell** is now a factor of the largest layer (× y_max, default 2, 1–10) |
| `gui/inflation_view.py` | plot: the purple "layers" lines removed; the numbers line leaves out T, p, k when they aren't known (water, custom) |

## 2.3.7 — CFD mode: walls, Formulas / Values, units; Hide Surface

| File | |
|---|---|
| `gui/inflation_panel.py`, `gui/inflation_view.py`, `gui/window.py` | **CFD mode** laid out like the mesh CFD section: **Flow** and **Inflation layers** fold, each with **Formulas** and **Values**; unit menus (altitude, speed U, length L, first / desired cell); **Speed U** can be typed (Mach follows); "?" right after *Altitude*; flow **direction** and **Show flow vectors**. **Walls**: the whole model, a part (with its colour dot), or **faces of one part** — *Pick faces…*, click / ⇧-click faces in the 3D view, **Apply**. The walls are tinted in the 3D view and give the **auto length L** (longest distance along the flow) and the wall area; *Back to auto length* after typing L. The Inflation page names the walls and L |
| `gui/scene.py`, `gui/sidebar.py`, `gui/memory.py` | right-click in the 3D view: **Hide Part** and **Hide Surface** (one CAD face); *Show Hidden Surfaces (n)*, and *Show All* brings them back; hidden surfaces are remembered per file |
| `gui/cfd_view.py` | `WallView`: the walls tint |

## 2.3.6 — CFD: unit menus, boundary colours, back to auto length

| File | |
|---|---|
| `gui/widgets.py`, `gui/cfd_panel.py` | **Unit menus** on every input: altitude / depth (m, km, ft), density (kg/m³, g/cm³, lb/ft³, slug/ft³), viscosity (Pa·s, cP, lb/ft·s), sound speed and speed U (m/s, km/h, kt, ft/s, mph), length L (m, cm, mm, in, ft); remembered per file. The "?" sits right after *Altitude*. **Back to auto length** link when L was typed |
| `gui/widgets.py`, `gui/cfd_panel.py`, `gui/sidebar.py` | the Boundary menu shows each part's **colour dot** (follows colour changes) |
| `gui/cfd_view.py`, `gui/scene.py` | Colour by y+ follows the view: its mesh edges hide while moving, and it turns to a coloured wireframe with the faces off |

## 2.3.5 — CFD: colour by y+, compressibility, speed units, Formulas

| File | |
|---|---|
| `gui/cfd_view.py`, `gui/scene.py`, `gui/cfd_panel.py` | **Colour by y+**: the boundary painted by y+ / target at each wall node (blue 0 · green 1 · orange 2 · red ≥ 3, grey where no first cell was found), with a colour scale in the panel. The max y+ is **green / orange / red** (≤ 1.25 ×, ≤ 2.5 ×, above the target) |
| `cfd.py`, `gui/cfd_panel.py`, `gui/inflation_panel.py` | **Compressibility correction** (on by default, in the y+ estimator and CFD mode): Cf × (1 + 0.144 M²)^−0.65 (Raymer, turbulent, adiabatic wall). Off = the plain flat-plate Cf (matches the original inflation calculator) |
| `gui/cfd_panel.py` | **Speed U** in m/s, km/h, kt, ft/s or mph |
| `gui/widgets.py`, `gui/style.py`, `gui/cfd_panel.py` | **Formulas** buttons beside *Values* (Flow, y+ estimator): a window in the middle of the app with every equation, drawn like LaTeX (matplotlib mathtext) |
| `setup.py`, `requirements.txt` | matplotlib bundled (draws the formulas) |

## 2.3.4 — CFD: speed U field, locked air / water values

| File | |
|---|---|
| `gui/cfd_panel.py`, `gui/style.py` | **Speed U** is a field: type U and Mach follows (M = U / a), type Mach and U follows. Density, viscosity and sound speed are greyed out and locked unless the fluid is *Custom*. The y+ card shows *min · mean* beside the max, and the mesh's largest first cell beside the first cell height for the target y+ |

## 2.3.3 — CFD section: folding groups, Values pop-ups, max y+

| File | |
|---|---|
| `gui/cfd_panel.py`, `gui/widgets.py`, `gui/style.py` | **Flow** and **y+ estimator** (was "y+") are groups that fold. Each has a **Values** button: a pop-up with every computed number (Flow: T, p, ρ, μ, ν, a, U, q, T₀, Re, laminar / turbulent; y+: L, Re, Cf, τw, u*, ν/u*, first cell, and from the mesh y+ max / mean / min, first cell max / mean / min, wall nodes). The big y+ is now the **max**, with the min beside it. Direction has X / Y / Z above the fields, which use the full width (no more clipped numbers) |
| `cfd.py` | auto length = the **longest distance along the flow** across the boundary (`streamwise_length`): a swept wing gives its root chord, not root leading edge to tip trailing edge |
| `gui/sidebar.py` | **Info** always starts closed |

## 2.3.2 — CFD mode for CAD files (inflation layer calculator)

| File | |
|---|---|
| `cfd.py`, `gui/inflation_panel.py` (new) | sidebar **CFD mode** (CAD files only, with an on / off switch): the inflation layer calculator. Flow: target y+, Mach, sound speed (at the altitude, or 343 m/s), length L (or *Use the model's length*), altitude (U.S. Standard Atmosphere). Layers: first cell (empty = the one for the target y+), number of layers N, growth rate G, desired cell above the layers (empty = 2 × the largest layer). Re = ρUL/μ, Cf = (2 log10 Re − 0.65)^−2.3, u* = √(τw/ρ), y_min = y+ μ/(ρ u*), y_tot = Σ y_min Gⁿ, δ99 = 0.38 L / Re^0.2 (turbulent) or 4.91 L / √Re (laminar), divided by (1 + 0.2 M²)^(1/9) above Mach 1. Settings are remembered per file |
| `gui/inflation_view.py` (new), `gui/window.py` | with CFD mode on, a bar under the 3D view switches between **3D model** and **Inflation layers**: a page with the key numbers (Reynolds, first cell, estimated y+, δ99, total height, largest layer), the plot (total height and layer height vs layer #, boundary layer, desired cell; hover for values), the layer stack near the wall drawn to scale, and two checks (layers cover the boundary layer · smooth transition) |
| `gui/sidebar.py`, `gui/scene.py`, `gui/memory.py`, `gui/style.py` | CFD mode shows for CAD files, the CFD (y+) section for meshes; page colours for light and dark |

## 2.3.1 — CFD section (y+), clearer Info, Point from the origin

| File | |
|---|---|
| `cfd.py` (new), `gui/cfd_panel.py` (new), `gui/cfd_view.py` (new) | sidebar **CFD**: flow (air at an altitude — U.S. Standard Atmosphere 1976 —, fresh / sea water at a depth, or your own density, viscosity and sound speed; Mach; flow direction X / Y / Z) and a **y+** estimate on a chosen boundary: flat-plate skin friction Cf = (2 log10 Re − 0.65)^−2.3, τw = Cf ½ρU², u* = √(τw/ρ), y+ = y u* ρ / μ. With volume cells, y is the first cell layer measured on the mesh (average, min, max); the first cell height for a target y+ is always given. **Show flow vectors** draws arrows before and after the boundary. "?" buttons open the CFD Online y+ page and the standard-atmosphere table. Settings are remembered per file |
| `gui/info_panel.py`, `gui/sidebar.py` | **Info** is the first section (remembers open / closed) and is easier to read: an Extent table (from / to / size per axis, with the unit or "file units"), then Faces, Points, Edge length, Volume cells, each with a short grey note |
| `gui/measure.py`, `gui/measure_panel.py` | Measure ▸ **Point** works like Distance with the first point at the origin (0, 0, 0): line, ΔX / ΔY / ΔZ and the distance from the origin |
| `gui/section.py`, `gui/section_panel.py`, `gui/memory.py` | the section **normal is kept as typed** (no longer rescaled to length 1) |
| `gui/widgets.py`, `gui/style.py` | `NumberField` (takes 1.8e-5 or 0,3), round "?" help buttons, `MenuSelect.clear()` |

## 2.3 — Cell quality, Info, more measurements, files reopen as you left them

| File | |
|---|---|
| `quality.py` (new), `gui/quality_panel.py` (new), `gui/quality_view.py` (new) | sidebar **Cell quality** (mesh files only): skewness, aspect ratio, scaled Jacobian or volume of every cell (VTK Verdict; computed in the background). Histogram coloured like the 3D view — click or drag it to set the "bad" threshold; bad-cell count, **Zoom** to them, **Show bad cells** (red, model see-through), **Colour by quality** (the section cut for volume meshes, the faces for surface meshes), inverted-cell check |
| `mesh/volume.py`, `transform.py` | volume cells read in the opposite node order (e.g. CGNS prisms vs VTK) are turned the right way out when most of a type is inside out, so volumes and quality are right |
| `gui/info_panel.py` (new), `polys.py` (new) | sidebar **Info**: size, bounds, face and point counts, shortest / longest edge, volume cells by type |
| `gui/measure.py`, `gui/measure_panel.py`, `gui/scene.py`, `gui/section.py` | Measure ▸ **Point** (coordinates, and distance to the section plane) and **Angle** (between two clicked faces, or a face and the cut); "Area & Volume" is now "Area" |
| `gui/memory.py` (new), `gui/window.py`, `gui/app.py` | **File ▸ Open Recent**; each file **reopens the way you left it** (camera, toggles, unit, colours, names, hidden parts, section). Only edits still ask before closing |
| `export.py`, `gui/export_dialog.py` | **OBJ** (with a .mtl) and **PLY** keep the part colours; VTU no longer carries extra arrays |
| `gui/jobs.py` (new) | one helper for background work (loading, re-meshing, cell quality) |

## 2.2.6 — part colours, Faces toggle, cleanup

| File | |
|---|---|
| `gui/sidebar.py`, `gui/scene.py`, `gui/section.py`, `gui/part_tree.py` | right-click a part (or a selection) ▸ **Colour…**: the 3D view, the filled cut faces and the list dot follow |
| `gui/window.py`, `gui/scene.py`, `gui/icons.py` | "Edges only" is now **Faces** (on = faces shown, off = edges only), with a shaded-cube icon |
| cleanup | unused code removed (`n_triangles`, `last_edit`, `volume_cells`, `part_items`, pencil icon); tooltips and comments no longer point to the old Display section |

## 2.2.5 — Display moves to the toolbar, Check for Updates

| File | |
|---|---|
| `gui/window.py`, `gui/icons.py` | two new toolbar pills right of the views (left of the units), each button on / off on its own: **Mesh edges · Feature edges · Edges only**, and **Axes · Grid · Bounding box · Origin** (Axes + Grid are still remembered for every window). Also in View ▸ Show. Checked toolbar icons are now white on the accent colour |
| `gui/sidebar.py` | the **Display** section is removed (it's all in the toolbar now) |
| `gui/about_dialog.py` | **Check for Updates…** opens the latest release on GitHub |

## 2.2.4 — Edit like Onshape, Edges only, shading in Appearance

| File | |
|---|---|
| `gui/edit_panel.py` | **redone like Onshape's Transform**: pick Rotate / Mirror / Move by X, Y, Z in a drop-down, fill in its boxes (axis, **any angle**, pivot; or the three distances), press **Apply** (or Return). Below: the list of changes made so far, with Undo \| Reset, then Show original edges |
| `transform.py`, `model.py`, `gui/scene.py` | rotations by any angle (multiples of 90° stay exact); `edit_labels` lists the changes |
| `gui/sidebar.py`, `gui/scene.py` | Display ▸ **Edges only** (under Feature edges): hides the faces, keeps the edges; feature edges stay visible while the view moves even with "hide edges while moving", mesh edges don't; clicking a hidden face still selects its part. Shading switch removed from Display |
| `gui/appearance_dialog.py`, `gui/app.py`, `gui/window.py` | **Shading** is now in Appearance ▸ Model (remembered, every window) |
| `gui/part_tree.py`, `gui/style.py` | **Fix:** renaming a part in dark mode showed the old name through the new one (the rename field is now opaque) |

## 2.2.3 — rename parts, McMaster numbers anywhere in a name, Edit as a table

| File | |
|---|---|
| `gui/part_tree.py`, `gui/sidebar.py` | **Rename** a part (any file type): right-click ▸ Rename…, or select it and press Return; the name is edited in the list. Names already in use are refused. McMaster numbers are now found **anywhere** in a name ("Screw 91251A540", "Bracket_8975K12_2"), not only at the start (sizes like "100x200" and alloys like "6061T6" are ignored) |
| `gui/scene.py` | `rename_part()` — colours, visibility, selection, edits follow; STEP / IGES parts keep their new name when re-meshed |
| `gui/window.py`, `gui/export_dialog.py` | Export writes the new names (STL solids, OBJ groups, VTU part names, UGRID .mapbc); renames count as unsaved changes (dot, question on close, "_edited" file name) |
| `gui/edit_panel.py`, `gui/style.py` | Edit section laid out as a small table: Pivot · rows X / Y / Z with Rotate [−90° \| +90° \| 180°] and Mirror [x → −x] · Move boxes + Move button in the same columns. Move boxes show "X 0" instead of "X 0.000". No line above "Show original edges" |

## 2.2.2 — tidier Edit section, shading switch, .dmg background fixed

| File | |
|---|---|
| `gui/edit_panel.py` | **re-laid out**: one row per action, every button the same shape and width — Pivot [Origin \| Centre] · Rotate X / Y / Z [−90° \| +90° \| 180°] (one click turns) · Mirror [X \| Y \| Z] · Move X / Y / Z boxes + a full-width Move button · "Show original edges" · "Last: …" with Undo \| Reset |
| `gui/widgets.py`, `gui/style.py`, `gui/export_dialog.py`, `gui/screenshot_dialog.py` | drop-down lists are now a button that opens a normal menu (`MenuSelect`): no more huge padding or drawing glitches above / below the list (replaces `roomy_combo`) |
| `gui/sidebar.py` | Display ▸ **Shading** switch (off = flat part colours, no light or shadow); a line under Display links to Appearance; switching the Section **off** now folds it |
| `gui/scene.py`, `gui/section.py` | `set_shading()` — parts and filled cut faces; kept when the mesh is rebuilt |
| `gui/appearance_dialog.py`, `gui/window.py` | Appearance says what it is for ("how things look, saved for every window"; Display = what is shown) and is grouped by what it styles: Window · Background · Axes (label size) · Edges (line thickness, while moving) |
| `make_dmg.sh` | the disk image window (background picture, icon places) is written by **dmgbuild** (installed in the build venv the first time) instead of asking Finder by AppleScript, which failed silently without the "control Finder" permission — the background now shows |

## 2.2.1 — friendlier Edit section, Move, compare with the original

| File | |
|---|---|
| `gui/edit_panel.py` | **redesigned** — always in the sidebar (no Edit button): Rotate (axis + −90° / +90° / 180°) · Mirror X / Y / Z · **Move** by X / Y / Z · turn **about** the origin or the model's centre · **Original** switch · "Last: …" line with **Undo** (one step) and **Reset**, styled like Measure ▸ Clear. STEP / IGES / BREP: a grey note instead of the tools |
| `transform.py` | edits are (R, t); geometry is always recomputed from the file's points, so Undo / Reset are exact and surfaces + volume cells keep identical node coordinates |
| `gui/scene.py`, `gui/section.py` | `apply_edit()`, `undo_edit()`, `reset_edits()`; the camera no longer resets after an edit; `set_show_original()` draws the file's feature edges in grey to compare. **Fix:** moving the volume cells no longer changed the file's copy (shallow-copy bug) |
| `gui/window.py` | Edit button / ⌘E removed; Export stays |
| `gui/widgets.py`, `gui/style.py`, `gui/export_dialog.py`, `gui/screenshot_dialog.py` | `roomy_combo()`: drop-down lists with menu-like spacing and rounded rows, wide enough for their text (Export format, screenshot resolution) |
| `export.py` | shorter format names |

## 2.2 — Edit (rotate / mirror) and Export

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

## 2.1.23 — toolbar tidy-up

| File | |
|---|---|
| `gui/window.py`, `gui/icons.py` | **Parallel projection** is now a toggle button in the view group of the toolbar (Fit · Iso · X · Y · Z · ▢, also View menu, ⌘5), no longer a sidebar switch; new **Edit** button (pencil, ⌘E) as a placeholder for the editing tools of the next version |
| `gui/sidebar.py` | Display rows evenly spaced (the extra gaps between groups are gone); "Origin (0, 0, 0)" is just "Origin" (the coordinates are in its tooltip) |
| `.gitignore` | ignores the `Claude outputs/` folder |

## 2.1.22 — cleaner Display section, steadier section handles

| File | |
|---|---|
| `gui/sidebar.py`, `gui/window.py`, `gui/app.py` | Display ▸ **Axes: Off · Axes · Grid · Both** replaces the Grid switch and Appearance's Grid lines / Axis lines switches (old settings carry over); switches grouped: projection · edges · bounding box & origin |
| `gui/appearance_dialog.py` | three groups: Window · 3D view (background, axis label size) · Edges |
| `gui/section.py`, `gui/section_panel.py` | cut volume mesh: edges black like the model's mesh edges and shown only when Display ▸ Mesh edges is on; the switch is "Fill cut faces" again. Plane handles (sphere, arrow tips) keep the same small size on screen at any zoom; shorter arrow |
| `gui/scene.py` | `set_axes_mode()`; Mesh edges switch also drives the cut mesh; unused `set_grid()` removed |

## 2.1.21

| File | |
|---|---|
| `build_app.sh`, `make_dmg.sh` | heavy files (Python environment, build, app, .dmg) go to `~/Downloads/MeshViewer-build` (or `$MESHVIEWER_WORK`), not the project folder; `.venv` is just a link |
| `.gitignore` | ignores the `.venv` link |

## 2.1.20

| File | |
|---|---|
| `mesh/volume.py` | **new** — builds one VTK grid from the volume cells |
| `mesh/ugrid.py`, `mesh/cgns.py` | `read_volume()`: tetra / pyramid / prism / hexa cells, read only when needed (CGNS: per-type and MIXED sections; quadratic cells use their corners; polyhedra skipped). **Fix:** CGNS node counts for QUAD_9, HEXA_20, HEXA_27 and quadratic pyramids / prisms |
| `model.py`, `formats.py` | models of mesh files can load their volume cells |
| `gui/section.py`, `gui/section_panel.py` | CGNS / UGRID: the section fills the cut with the volume cells it goes through, with their edges; surface-only files keep the solid fill |
| `gui/scene.py` | cut-mesh colours for light / dark; its edges hide while moving |

## 2.1.19

| File | |
|---|---|
| `gui/scene.py`, `gui/sidebar.py` | **Origin (0, 0, 0)** switch in Display: a dot with short red / green / blue X / Y / Z arrows, drawn on top so it shows inside parts; also in screenshots |
| `gui/scene.py` | pressing X, Y or Z again without moving the view looks from the opposite side (X → −X → X); Iso stays as is |
| `gui/measure.py` | screenshots include the origin marker |
| `.gitignore` | **new** — keeps `.venv`, `build/`, `dist/`, `.dmg` and `__pycache__` out of git |
| `README.md`, `CHANGELOG.md`, `LICENSE`, `docs/` | **new layout for GitHub**: README with screenshots, features, download and build steps; the version history moved to CHANGELOG.md; MIT licence; screenshots and a release-notes template in `docs/` |

## 2.1.18

| File | |
|---|---|
| `gui/widgets.py` | **fix:** the Section switch shows the hand cursor like the other switches (the section header was forcing an arrow) |
| `gui/scene.py` | **Axis lines** off now hides the numbers and axis titles too (grid lines stay); axis numbers follow the unit chosen in the toolbar (mm / cm / m / in / ft) and titles read "X Axis (mm)"; with ⊘ no unit is shown. Grid building moved into `refresh_grid()` / `_add_grid()` (view and screenshots share it) |
| `gui/measure.py` | changing the unit rebuilds the axis labels |

## 2.1.17

| File | |
|---|---|
| `gui/sidebar.py` | switching **Section** on also opens its controls |
| `gui/appearance_dialog.py` | four groups separated by lines: Window · 3D background · Axes & grid · Edges; new **Axis lines** switch next to Grid lines |
| `gui/scene.py` | axis lines (frame + tick marks) can be hidden — numbers and titles stay; screenshots: only "As Shown" or "Transparent" |
| `gui/screenshot_dialog.py` | Light / Dark / Custom backgrounds removed (As Shown follows Appearance) |
| `gui/measure.py` | distance points are fixed-size dots on screen (13 px) instead of spheres that grew when zooming in; X/Y/Z lines 2.5 px (was 1.5) |
| `gui/app.py`, `gui/window.py` | axis-lines setting saved |

## 2.1.16

| File | |
|---|---|
| `gui/scene.py` | edges also hidden while **zooming** (scroll wheel / trackpad): a burst of zoom steps counts as one movement, edges return 0.3 s after the last step; **grid lines** behind the model can be turned off (the axis frame, ticks and labels stay); in CAD-face measuring, **clicking empty space clears** the selected faces |
| `gui/about_dialog.py` | **new** — About Mesh Viewer: icon, version, credits, Python / Qt / VTK / PyVista / OpenCASCADE / NumPy versions |
| `gui/app.py`, `gui/window.py` | "About Mesh Viewer" (macOS puts it in the app menu, left of File); grid-lines setting saved |
| `gui/appearance_dialog.py` | "Grid lines" switch; "While moving" switch now says rotate, pan, zoom |
| `meshviewer/__init__.py`, `setup.py`, `make_dmg.sh` | the version number lives in one place (`__version__`) |

## 2.1.15 — smoother edges, more Appearance options

| File | |
|---|---|
| `gui/scene.py` | edges are hidden while the view moves on **any** model (was only above 1.5 M triangles) and come back when you let go; feature edge thickness Thin 1 / Medium 1.5 / Thick 2 px (default Thin — one drawing pass on macOS) |
| `gui/appearance_dialog.py` | sheet grouped into **Window** and **3D view**; new: axis label size slider (10–28 pt, 10 = the original size, default 16), Edge lines Thin / Medium / Thick, "While rotating: hide edges" switch |
| `gui/app.py` | saves the new options; old Small / Medium / Large axis setting carries over |
| `gui/icons.py` | Appearance icon is now three sliders (it holds more than light / dark) |
| `gui/style.py` | group titles in the sheet |

## 2.1.14 — smaller app

| File | |
|---|---|
| `slim_bundle.py` | **new** — after a standalone build: removes the Qt parts the app never uses (web engine, QML, 3D, multimedia, Designer and other tools, translations, headers), keeps only this Mac's processor type in universal binaries, de-duplicates framework files, re-signs. PySide6 goes from ~1.2 GB to ~0.15 GB |
| `build_app.sh`, `make_dmg.sh` | run it (also with `make_dmg.sh --reuse`) |
| `mesh_viewer.py` | self-test also opens Qt and a 3D view, so a missing Qt piece is caught before packing |
| `setup.py` | leaves out tkinter / pip / wheel |

## 2.1.13 — fix

| File | |
|---|---|
| `fix_bundle.py` | **new** — the standalone app failed its self-test (`liblzma.5.dylib … unknown imports_format`): py2app corrupts Homebrew libraries when it copies them. This puts back clean copies and relinks them with Apple's `install_name_tool` |
| `build_app.sh` | standalone builds run `fix_bundle.py` and sign every library; signing errors are shown |
| `make_dmg.sh` | `--reuse` re-repairs an existing build (no rebuild) |
| `mesh_viewer.py` | self-test also checks lzma, bz2, zlib, ssl, hashlib, decimal, ctypes (not sqlite3: the app doesn't use it, so py2app leaves it out) |

## 2.1.12

| File | |
|---|---|
| `make_dmg.sh` | **new** — builds a self-contained app and packs it in `dist/Mesh Viewer <version>.dmg` (drag-to-Applications window with an arrow background) |
| `build_app.sh` | `--no-install` option (build only), used by `make_dmg.sh` |
| `mesh_viewer.py` | `--selftest`: checks a bundled app has every package and can draw (run by `make_dmg.sh` before packing) |
| `resources/dmg_background*.png` | **new** — background of the disk-image window |
| `gui/scene.py` | axis labels bigger: Small 16 / Medium 20 / Large 24 pt (old Large is the new Small); XYZ corner widget a bit larger |

## 2.1.11

| File | |
|---|---|
| `gui/part_tree.py` | right-click no longer selects the row (also ⌃-click on a Mac); the clicked row gets an accent outline while the menu is open, like Finder |
| `gui/sidebar.py`, `gui/scene.py`, `gui/window.py` | "Search in McMaster" uses only the row / part you right-clicked, never the whole selection (Hide / Isolate still act on the selection when you right-click inside it) |
| `gui/scene.py`, `gui/appearance_dialog.py`, `gui/app.py` | **new:** Axis labels Small (default) / Medium / Large in Appearance; also used for screenshots; the XYZ corner widget grows a little with it |

## 2.1.10

| File | |
|---|---|
| `gui/part_tree.py` | **fix:** groups no longer close right after opening (macOS opens/closes tree rows on mouse *release*; our press handler already had, so it toggled twice) |
| `gui/sidebar.py`, `gui/style.py` | "N parts selected · Clear" is always shown (greyed at 0), so selecting no longer shifts the list |
| `gui/scene.py`, `gui/screenshot_dialog.py` | **new:** "Transparent" screenshot background (PNG with alpha; grid/labels drawn dark, for white pages) |
| clean-up | screenshot sheet reuses the shared `ColorField` instead of its own copy; removed an unused `Scene.set_all_visible` and unused imports; old "NEW" markers removed (each version's changes are tagged `NEW (vX)` / `FIX (vX)`) |

## 2.1.9 — fixes

| File | |
|---|---|
| `gui/scene.py` | after a right-click menu, the 3D view no longer stays in "zoom" mode (any lost drag is ended as soon as the mouse moves with no button held) |
| `gui/sidebar.py` | same clean-up when the menu closes |
| `gui/part_tree.py` | **new:** row spacing Compact / Comfortable; group arrow is easier to hit — clicking anywhere left of a group's checkbox opens / closes it without selecting |
| `gui/appearance_dialog.py`, `gui/app.py`, `gui/window.py` | "Parts list" spacing option in Appearance, remembered |
| `gui/style.py`, `gui/widgets.py` | light mode: the system accent is made vivid and dark enough to read (macOS gives Qt a pale version); dark mode unchanged |

## 2.1.8 — appearance, McMaster, roomier menus

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

## 2.1.7

| File | |
|---|---|
| `gui/scene.py` | no black / very dark part colours; right-click hook (`on_context`) |
| `gui/measure.py` | marker lines no longer tinted by a hidden scalar array (now truly grey / red / green / blue); display units + conversion; 5 significant digits |
| `gui/window.py` | units capsule in the toolbar; right-click menu in the 3D view |
| `gui/sidebar.py`, `gui/part_tree.py` | "N parts selected · Clear" bar; right-click Hide / Isolate / Zoom To (selection-aware) |
| `gui/style.py` | part list: flat full-row selection + own fold-out arrows (no odd shapes) |
| `gui/widgets.py` | closing a section always gives its space back |
| `gui/icons.py` | ⊘ "no units" icon |

## 2.1.6 — fixes

| File | |
|---|---|
| `gui/part_tree.py` | **new** — grouped part list (replaces the flat list) |
| `gui/scene.py` | screenshots render in a separate full-size off-screen window with text and lines scaled (fixes giant axis labels); `isolate` / `zoom_to` take groups |
| `gui/measure.py` | distance line grey, X/Y/Z legs red/green/blue; labels on top; near-zero noise shown as 0 |
| `gui/measure_panel.py` | **rewritten** — result card, no hints, no Copy, units note |
| `gui/sidebar.py`, `gui/window.py` | Measure is a sidebar section (no toolbar button); sections start closed |
| `gui/widgets.py` | sliders / number boxes ignore the scroll wheel; sections can start closed |
| `gui/screenshot_dialog.py` | sheet shrinks back after leaving "Custom" |

## 2.1.5 — measure, screenshot options, multi-select

| File | |
|---|---|
| `gui/measure.py`, `gui/measure_panel.py`, `gui/screenshot_dialog.py` | **new** |
| `gui/scene.py` | **new:** multi-selection (parts) + CAD face selection, `click()` routes clicks to measuring, `pick_full()` returns the 3D point, `screenshot()` with background choice |
| `gui/sidebar.py` | list allows ⌘/⇧ multi-select; Measure section (shown while measuring) |
| `gui/window.py` | Measure + Screenshot buttons back at the top right; Measure in View menu |
| `cad/occt.py` | triangles remember which CAD face they came from (`face_id`); exact area / volume from OpenCASCADE |
| `model.py`, `formats.py` | model keeps the CAD source and units |

## 2.1.4 — more CAD formats

| File | |
|---|---|
| `cad/occt.py` | **new** — the OpenCASCADE code from `step.py`, shared by STEP/IGES/BREP. Bodies inside an unnamed IGES compound become separate parts; bare unnamed surfaces are grouped as "Surfaces"; IGES type names ("FACE", "SHELL") are ignored as part names |
| `cad/step.py` | now a thin wrapper around `occt.py` (same behaviour) |
| `cad/iges.py`, `cad/brep.py`, `cad/tessellated.py` | **new** readers |
| `formats.py`, `setup.py`, `build_app.sh` | register the new extensions (Finder "Open with") |

## 2.1.3 — plane always visible, smoother view

| File | |
|---|---|
| `gui/section.py` | **new:** the plane is drawn as its own actor (translucent + outline), updated on every change — VTK's widget only drew it while dragging. "Show plane handle" → "Show plane" |
| `gui/scene.py` | **rewritten drawing:** all parts in ONE composite actor (per-part colour/visibility), all feature edges in another, instead of 1–2 actors per part; hardware picking (ignores hidden parts, respects the cut); on models over 1.5 M triangles, edge lines are hidden while the view moves |
| `gui/window.py` | 4× instead of 8× anti-aliasing (cheaper on Retina) |

## 2.1.2 — faster section

| File | |
|---|---|
| `gui/section.py` | only parts whose bounding box touches the plane are cut; `vtkPolyDataPlaneCutter` instead of `slice`; exact point merge before filling (the tolerance merge was the big slowdown); all caps in one actor, all outlines in another; cut nudged 1e-6 off the plane to avoid degenerate cuts |
| `gui/section_panel.py` | switching on clips instantly; caps fill in ~0.15 s later with a busy cursor |
| `gui/scene.py` | VTK filters use all CPU cores; picking a cap uses the merged caps actor |
| `gui/window.py` | Section + Screenshot buttons removed from the toolbar (still in the menus) |

## 2.1.1 — UI polish

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
