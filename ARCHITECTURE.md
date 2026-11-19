# Architecture

A map of the code for whoever changes it next (people or Claude): read this first,
then only the files the change touches. User-facing docs are in README.md, the
history in CHANGELOG.md.

## Three layers

```
meshviewer/core/     no Qt, no rendering   numbers, files, geometry   (testable on its own)
meshviewer/render/   VTK / PyVista actors  what is drawn in the 3D view (no Qt widgets)
meshviewer/gui/      Qt                    windows, sidebar, panels, dialogs, pages
```

Imports only go down: gui -> render -> core. Imports are absolute
(`from meshviewer.core.units import fmt`).

## Where things are

| Need to… | Look in |
|---|---|
| add a file format | `core/formats.py` (one line) + a reader in `core/mesh/` or `core/cad/` returning `{name: pv.PolyData}` |
| what a STEP / IGES file says about its parts (assemblies, colors, materials) | `core/cad/occt.py` (`_collect_leaves`, `_shape_color`, `_label_material`; `CadFile.part_info` → `Model.part_info`); the native colors in `Scene.default_colors` (saved colors: only the ones chosen, `gui/memory.py`); the tree in `gui/panels/parts.py` `_fill_tree`; Material… `gui/sidebar_menu.py` |
| the parts list's order and filter | `gui/panels/parts.py` (`sort_by`, `_sorted`, `apply_filter`), the ⇅ button `gui/sidebar.py` `_build_sort`; limits `core/part_filter.py`; sizes and volumes `Scene.part_size`, `part_volume` |
| change how STEP / IGES / BREP are meshed | `core/cad/occt.py` (`QUALITY_LEVELS`, `tessellate`, `_occt_mesh`: OpenCASCADE's triangles are used as they are) |
| Gmsh / Fluent `.msh`, DXF | `core/mesh/msh.py` (meshio for Gmsh, own Fluent parser, text and binary), `core/cad/dxf.py` (ezdxf: curves, text and dimensions as outlines via `text2path`, SOLID / TRACE / 3DFACE corners; blocks walked by `flatten` with the layer-0 rule); a missing font replaced by one with the letters (`text_font`); a drawing's frame is its bounding box (`render/appearance.py` `bbox_color`), its grid / axes mode `appearance/drawing_axes` (`gui/window.py` `_axes_key`). Readers may return `(parts, {"dim": 2, "units": …})`; `Model.dim` / `file_type` (cad, mesh, mesh2d, drawing) pick the sections |
| OpenFOAM case folders (File ▸ Open Case… ⇧⌘O, the welcome screen's Solver pop-up) | `core/mesh/openfoam.py` (`_locate`: what was picked → the polyMesh folder(s) and time folders; `FoamCase`: `vtkOpenFOAMReader`s on a temporary case of links, kept as `Model.case` — `patches`, `cells`, `volume`, `set_time`; vectors split `_split_vectors`; `_two_d`: one cell thick between `empty` patches → flat in XY, the cells' values through the owner list), `core/mesh/openfoam_files.py` (boundary, time folders, fields and their units from the dimensions, owner lists); time steps and field units on the model (`Model.times`, `time_index`, `field_units` → Contours' Unit in file); polyhedra `core/mesh/volume.py` `split_polyhedra`; a folder → OpenFOAM in `core/formats.py` `detect`; the dialog `gui/app.py` `open_case_dialog`, `gui/sheets.py` `ask_folder`; `gui/welcome.py` `SOLVERS` |
| time steps, animation (OpenFOAM) | `render/timesteps.py` (`Scene.set_time_index`: only the fields in use swapped in place — `scene.field_users` → `wanted_fields()`, a tool needing more calls `ensure_fields(names)`; `scene.time_listeners`), the steps of a case `core/mesh/openfoam_steps.py` (`Steps`, mixed into `FoamCase`: `step_arrays` / `volume_arrays` read per file field, `prefetch`, `range_steps` (24 spread steps on a long case), `read_ranges`, `known_ranges`, `varies`) in a float32 cache kept while the case is open `core/mesh/openfoam_cache.py`; 2D cases `core/mesh/openfoam_2d.py` (`two_d` → the flat parts and their map, `flat_arrays`: another step's arrays on them without rebuilding); the playback bar `gui/widgets/animation_bar.py`, shown by `gui/window_animation.py` (a contour's tab with ▸ Animation on, a probe's tab); ▸ Animation in the card `gui/panels/contour_animation.py`; Timeline Min / Max `gui/panels/contours.py` `_timeline`; the section's cut cells colored by the contour `render/section.py` `_contour_colors` |
| volume cells (CGNS, UGRID, .msh, OpenFOAM) | `core/mesh/cgns.py` `read_volume`, `core/mesh/polyhedra.py` (NGON/NFACE), `core/mesh/volume.py` |
| CFD numbers (y+, atmosphere, layers) | `core/cfd.py`; exports for meshers `core/cfd_export.py` |
| units, number formatting | `core/units.py` (unit tables, `fmt`, `show_length`, `nice_length`, `nice_num`) |
| solution fields, color scales | `core/fields.py` (`solution_fields`, `ramp_t` (linear or log) → `ramp_table` (smooth, or in bands between `edges`) / `ramp_rgb`, the color bar's `ticks` (Color scale and Tick scale apart), `COLORMAPS`, `DEFAULT_MAP`; F15 `gradient_magnitude`, `cell_jumps`) |
| Contours (each contour → a tab) | `gui/panels/contours.py` (`ContoursPanel`: the list, the fields' units shared with Plots, `info(c)` what a contour shows, `_changed` draws the active one; `scene.results_settings` = on, active, units, contours — a 2.5 file's one Results setting becomes Contour 1), `gui/panels/contour_editor.py` (`ContourEditor`: one contour's fold-out; `field_label`, `grouped`; `BAR_DEFAULTS`, `new_contour`), tabs in `gui/window_pages.py` (`_show_page("contour:<id>")`: the model, that contour drawn; the 3D View tab: never a contour; each 3D tab its own camera and Show ▾: `_view_state`, `_switch_view`, `_apply_view`, a contour's in `c["view"]`; every tab its own hidden parts: `_switch_parts`); a tab opened ↔ its fold-out opened, the others folded (`Sidebar.reveal`, `expand_only`, `Inspector.reveal`; Plots too) |
| the Contours color bar (over the 3D view, top-left, dragged) | `render/colorbar.py` (`ColorBar`, `scene.colorbar`: VTK 2D actors anchored at the view's top-left corner, `offset` in points; Height / Width in percent, the text in points (right whenever the view's DPI arrives), Text color, crowded numbers left out `_labeled`; `hit` / `drag` from `gui/viewport.py` (`overlay`); `add_to` for Save Screenshot); its settings per contour (`c["bar"]`, the last chosen as `results/color_bar`); the boundaries' colors through the same table: `render/overlays.py` `ResultsView`, `results_lut` |
| what a field is (its name, group, unit) | `core/field_kinds.py` (`KINDS`: the usual CFD and FEA fields — title, group in the Field menu, quantity or none; `field_kind(name)`; `EXACT`: names matched as written (Ux, Q); `Z_KEYS` left out on 2D files, `core/fields.planar`); their units `core/units.py` (`QUANTITIES`, `QUANTITY_TITLES`, `unit_quantity`; a unit typed for one file with Custom…: `is_custom`, kept in `scene.results_settings` only) |
| Plots (each plot → a tab) | `core/plots.py` (`KINDS`: defaults + compute per kind; CSV; `y_flipped`: Flip Y as set or cp's own), `gui/panels/plots.py` (`PlotsPanel`, `EDITORS` per kind; Axes ▸ Swap `swap_axes`, its column names `sync_names`; Include), `gui/pages/plots.py` (`PlotPage`; swapped: drawn value across; Include > / <: the rest left out), tabs in `gui/window_pages.py` (`_rebuild_view_bar`, `_show_page("plot:<id>")`; View ▸ Fit ⌘0 fits the plot shown: `fit_view`), the 3D cut `render/overlays.py` `CutLineView`; 2D files: a line across the zone, X / Y only (`plots.axes_of`, `in_plane(axis, flat)`, the editor's `flat`). A new kind: an entry in `KINDS` + an editor in `EDITORS` |
| the 3D view (`Scene`) | `render/scene.py`: parts, colors, visibility, selection, Display toggles. The rest of the class, one subject per file: `render/picking.py` (clicks; Select ▾ in `render/elements.py`; 2D files: Node / Edge and Snap to edges by distance on screen, `to_display`, `nearest_on_screen`, `Elements.click_2d` / `snap_2d`), `render/camera.py` (views, 2D lock, lines hidden while moving), `render/editing.py` (new mesh quality, rename, rotate / mirror / move), `render/appearance.py` (theme, background, grid, axes, origin, bounding box, the XYZ axis indicator: Show ▸ Axis Indicator, `set_axis_indicator`, app-wide `appearance/axis_indicator`), `render/screenshot.py` (PNG / JPEG / SVG: `save_image`); colors and sizes in `render/style.py` |
| what a click picks (Select ▾: part, mesh node / edge / triangle, feature node / edge / face) | `render/elements.py` (`Elements`, `scene.elements`: the kind, the picked items, their accent drawing, the line under the parts list); feature faces, edges and nodes `core/features.py` (`Features`, `components`; on meshes sharp edges `_hysteresis` + `_tidy`, smooth edges `_smooth_edges` kept by `_distinct` (crease or change of bend) and `_anchored` (no floating or zig-zag ones, `_zigzag`), gaps between feature edges `_bridge`, on CAD the face borders, drawn by Show ▸ Feature Edges through `Elements.feature_lines`, cut at corners `_runs`, cut where others meet them `cut_at_junctions`); the menu `gui/window_bars.py` (`a_select`, `set_select_kind`) |
| the 3D view widget (when frames are drawn); wheel, trackpad and pinch zoom; dragging the color bar | `gui/viewport.py` (`wheelEvent`, `event`, the wheel glide → `render/camera.py` `zoom_at`, to the cursor; `mousePressEvent` … on `overlay`) |
| overlays (flow arrows, y+, walls, contours) | `render/overlays.py`; cell quality colors `render/quality_overlay.py`; the contour's color bar `render/colorbar.py` |
| section plane, measurements | `render/section.py`, `render/measure.py` (`paused`: the Measuring Tool out of view, its marks stay, `picking` is "off") |
| a tool (a "section" in the code) | `gui/sections.py` (the list, each with its `tab`) + `gui/panels/<name>.py` + `Sidebar._build_sections` (Meshing Control: `gui/panels/meshing.py`) |
| the menu bar | `gui/window_bars.py` (`_build_actions`, `_build_menus`; the layout is in its first lines); with no window open, `gui/app.py`; Help ▸ Keyboard Shortcuts `gui/dialogs/shortcuts.py` (read from the menus) |
| Undo / Redo | `gui/undo.py` (`Changes`: one `QUndoStack` per window; a command per kind of change; the selection and the camera recorded once done, `_Done`; camera moves merged while of one kind with no pause over `CAMERA_PAUSE` = 0.8 s, never inside one drag or zoom burst: `Scene.camera_gesture`; hooks `Scene.on_selection`, `on_camera` in `render/camera.py`) |
| the empty window, samples | `gui/welcome.py` (welcome screen; File ▸ Open Sample), `gui/samples.py` (the list; `resources/samples/`, copied into the app by `setup.py`) |
| File ▸ Revert to Original… | `ViewerWindow.revert_to_original` (`gui/window.py`): `memory.forget`, then the file in a fresh window |
| progress, errors, Report a Problem | `gui/feedback.py` (`Spinner` in the toolbar, `show_error` sheet), `gui/report.py` (the GitHub issue link) |
| VoiceOver, Increase Contrast, full screen | `gui/access.py` (`name_controls`), `gui/style.py` (`HIGH_CONTRAST`), `gui/macos.py` (`join_active_space`, `increase_contrast`) |
| Settings (⌘,) | `gui/dialogs/settings.py` (the window, a tab per subject); the values in `MeshViewerApp.appearance` / `.prefs` (`gui/app.py`), saved through `gui/store.py` |
| shared form pieces (label · field · unit · ? rows, pairs, X / Y / Z boxes, switch rows, buttons, links, group titles, divider line, read-outs, notes, status colors, sheet titles) | `gui/forms.py` (the list on top); the layout of a tool under **Conventions** |
| switches, menus, number fields | `gui/widgets/` (import from the package): `basics.py`, `sections.py` (folding section), `select.py` (pop-up choices), `numbers.py`, `formulas.py` |
| icons | `gui/icons.py`: `SF` maps icon names to SF Symbols (drawn by macOS at run time, via PyObjC); `FILES` the app's own SVGs in `icons/` (Select ▾; white on clear, recolored when drawn; copied into the app by `setup.py`); `DRAWINGS` are the fallbacks |
| colors / stylesheet | `gui/style.py` |
| per-file memory | `gui/memory.py` (`capture` / `restore`, one key per setting) |
| the window | `gui/window.py` (opening a file, appearance, closing); its units `gui/window_units.py`; its actions, toolbar and menus `gui/window_bars.py`; pages and tabs under the view `gui/window_pages.py` (one tab bar for contours, plots and probes: `_sync_tabs`, `_tab_items`); Export and Save Screenshot `gui/window_export.py` |
| Probe (a point, a line, an area: values, over time) | `core/probe.py` (`sampler`: the target → cells / nodes with weights, found once with VTK static locators, `Locator`; `Sampler.value`, `series` over the steps: array lookups only), `gui/panels/probes.py` (`ProbesPanel`: the list, `target_from_selection` from Select ▾, Follow Select ▾, Select Vertex Point `pick_vertex` / `vertex_picked` (asks the window for Select ▾ through `select_kind`), the reads in the background, `scene.probes`), `gui/panels/probe_editor.py` (a probe's card: X / Y / Z, the readout, Copy Values, Export CSV), its tab `gui/pages/probe.py` (`ProbePage`: the field over time, the step as a dashed line with its time tag, a click picks a step) shown by `gui/window_probes.py`; markers `render/probes.py` |
| marks over the model (always visible) | `render/layers.py` (`scene.overlays`: layer 1 marks, layer 2 labels, copied into Save Screenshot) — the Measuring Tool's marks, the origin, the probes' markers |
| a field's units in a tool (Unit in file · Shown in · Custom…) | `gui/panels/field_units.py` (`FieldUnits`: for a contour and a probe; the choice kept by Contours, `unit_of` / `set_units`) |
| the left sidebar (parts list) and the right sidebar (`inspector` in the code) | `gui/sidebar.py` (the parts list; builds the tools and decides which are in view: `is_active`, `show_section`, `activity_changed`), `gui/inspector.py` (the right sidebar: View · Measure · Analyze tabs); layout pieces `gui/sidebar_layout.py` (`FitScroll`: as tall as its content, an overlay scrollbar in the right margin); the right-click menu of a part (hide, color, rename…) `gui/sidebar_menu.py` |
| the toolbar | `gui/window_bars.py` `_build_toolbar` (groups by key in `_tb_items`), `apply_toolbar`; View ▸ Customize Toolbar… `gui/dialogs/toolbar.py` (settings `toolbar/hidden`) |
| CFD panels | `gui/panels/cfd.py` (meshes), `gui/panels/inflation.py` (CFD mode, CAD); the fluid / speed / direction inputs they share `gui/panels/fluid.py` |
| pages under the 3D view (Inflation layers) | `gui/pages/inflation.py` (the layer sizes and their stack); the layers' thickness in 3D `render/overlays.py` `WallView` |
| Measure Selected (what a picked node / edge / face / cell is) | `render/element_details.py` (`details`; the solution fields over what is picked: `field_values`, length- / area-weighted), geometry `core/element_info.py`, the panel `gui/panels/selected.py` (Field Values in Contours' units: `units`); Volume Cell picking `render/elements.py` `_volume_cell_at` |
| Save Screenshot as SVG (vector) | the 3D view: `render/svg.py` (`svg_text`: facets projected through the camera, painter's algorithm, `_split` for a contour's gradients; the color bar `ColorBar.svg`); a plot's tab: `gui/pages/plots.py` `PlotPage.save_picture` (QSvgGenerator) |

## Speed: what keeps it smooth

- **Draw freely, it happens once.** `plotter.render()` only says a frame is due;
  `gui/viewport.py` draws it once the event is handled, and shows a frame VTK has just
  drawn without drawing it again. So code never needs a `render=False` dance to be fast —
  and must not expect the picture to exist right after `render()` (`flush()` if it does).
- **One actor for many parts.** Parts, feature edges and the selection outline are each
  one actor (`Scene._composite`, `_refresh_highlights`); per-part settings go through
  `Scene._apply_blocks`. Don't add an actor per part.
- **Repeated CAD parts are meshed once.** `core/cad/occt.py` meshes and triangulates each
  distinct shape once (`_PerShape`) and moves the copy to each instance's place; exact
  face areas are remembered the same way.
- **A parallel camera stays far back.** `render/camera.py` `_place_camera` (before each
  frame): otherwise VTK cuts away what is behind the camera and sizes the grid's numbers
  by their distance to it.
- **Small parts on one thread.** VTK's worker threads cost about 1 ms per filter run:
  `core/polys.one_thread()` around filters on small parts.
- **No NumPy views into VTK.** A surface made from another's arrays is made with
  `core/polys.bare()` (random crashes otherwise).
- **A time step swaps values, not objects.** `core/fields.replace_fields` copies a step's
  values into the parts' existing VTK arrays; the contour's actor is recolored in place
  (`ResultsView`: same boundaries → only "ResultT", written into the drawn array — a
  `pv.wrap` of it is a shallow copy); the color bar is left alone when unchanged;
  Section re-cuts only its cells, giving the cutter the contour's field alone
  (`Section._cut_source`); Plots recompute only plots of a field; folded contour cards
  wait until unfolded. Read `vtk` modules by name (`from vtkmodules.vtkIOGeometry …`),
  never `import vtk` (every module: 1.4 s).
- `python tools/bench.py <file>` times opening, drawing, selecting, hiding, cutting…
  on your machine (before / after a change); `python tools/bench_timeline.py` a contour
  playing through time steps (OpenFOAM cases it makes: 3D and 2D, with Section, a plot,
  two contours).

## Conventions

- **Tools**: every tool exists for every file, in its tab; `SectionSpec.unavailable(scene)`
  returns the gray reason when it doesn't apply. Panels expose `bind(scene)` and, when
  needed, `activate(on)` (in view or not: open, in the tab shown, the inspector shown), `model_changed()`, `refresh_names()`,
  `refresh_colors()`, `settings()`. Settings that a file remembers live on the scene
  (`scene.<name>_settings`) and are saved by `gui/memory.py`.
- **A tool's layout** (`gui/forms.py`, as Inflation Layers and Contours): the panel's
  `column(self)` (no margins: its card pads it); inputs in `_grid` / `_row` (label ·
  field · unit · ?), two coupled fields with `pair`, switches with `switch_row`;
  groups under `group_head` (a gray title, its Formulas / Values / buttons on the
  right), a `rule` between groups; what most people leave alone folded in a
  `CollapsibleSection(sub=True, start_open=False)` (▸ Properties, ▸ Axes). Computed
  numbers: `readout` (gray key, value right) or a `#ResultCard` with a big value for
  the tool's main result; a tool that is off, empty or waiting: one `note` ("Off —
  switch on to …"); colors of a state from `style.STATUS` (`set_state`,
  `status_mark`). A tool that doesn't apply shows its `unavailable` reason instead,
  its name lighter.
- **Background work**: `gui/jobs.run_job(work, done, failed)`; `work` must not touch Qt.
- **Naming**: modules are nouns (`sections.py`, `units.py`); panels are `<Name>Panel`,
  3D overlays `<Name>View`. Private helpers start with `_`.
- **Big classes in several files**: `Scene`, `ViewerWindow` and `Sidebar` are each put
  together from small classes, one subject per file (`class Scene(Picking, Camera, …)`).
  A method is found by its subject; every piece uses the same `self`.
- **File size**: a file over ~600 lines is a sign it holds two subjects.
- **No version notes in code**: history goes in CHANGELOG.md, not in comments.
- **Words on screen** (Apple's rules): American spelling (color, center, gray, meters).
  Title Case for menus and their items, buttons, tabs, window titles and tool names
  ("Meshing Control", "Save Screenshot…"); sentence case for labels, switches, notes and
  hover texts ("Fill cut faces"). One name per thing: the **left sidebar** (parts) and the **right sidebar** (tools; `inspector` in
  the code), a panel in the right sidebar is a **tool**, a
  plot under the view is a **plot** (not a measurement: that is the Measure tool), the
  CAD side of CFD is **Inflation Layers**, a cut by a plane is a **section**, a face of a
  CAD part is a **face**. A part is called what the file calls it: `Model.item_words`.
- **A change the user may want back** goes through `window.changes` (`gui/undo.py`), not
  straight to the scene, so Edit ▸ Undo knows it. Memory restore and file loading don't.
- **Questions are sheets**: `gui/sheets.py` (`ask_save`, `ask_open`, `ask_text`,
  `ask_color`) and `QMessageBox` with `Qt.WindowModal` + `open()`, never Qt's
  blocking `getSaveFileName` / `exec()`. Saving next to a file goes to
  `sheets.save_folder(path)` (a sample is inside the app: Documents instead).
- **Errors** go through `feedback.show_error(window, what failed, why, what to do)`.
- **Background work** shows the toolbar spinner: `run_job(..., busy=(window, "Doing x…"))`.
- **The app menu** (About, Check for Updates…, Settings…) is made once,
  `MeshViewerApp.app_menu_actions()`; on macOS it goes only in the no-window menu bar
  (macOS shows those items in every window — added per window they appeared twice).
- **Saved settings** are read and written with `gui/store.settings()`, never
  `QSettings(...)` directly: the tests point it at a scratch file.
- **Units**: lengths inside the app are model units; CFD maths is in metres
  (`core/units.UNITS` converts).

## Tests

```
python tests/run_all.py              every test file, in one app (xvfb-run is used on Linux)
python tests/run_all.py plots select only those; --isolated: each in its own process
python tests/test_sidebar.py         one of them, in its own app
```

`run_all.py` runs the files one after another in one process, so the imports, the app
and VTK's first window are paid once; before each file `conftest.fresh_start` closes
every window, points the settings at a new scratch file and puts the app's settings
back as at launch. A file that crashes that process is run again on its own (and the
ones after it). Windows are not shared between files (a window can't be reset to as
opened); within a file, read-only checks go on a window already open for that file.

`tests/fixtures.py` writes small test files into `tests/_data/` (git-ignored) and keeps
them; they are made again when missing or when `fixtures.py` changes (its hash in
`_data/.made-by`): a STEP box, a hex CGNS mesh, the same mesh as NGON/NFACE polyhedra,
a UGRID and a Tecplot results file. `tests/conftest.py` has `check()`, `open_file()`
and `run()`.
`tests/test_viewport.py` checks that an action draws one frame and that the screen shows it;
`tests/test_mac.py` the menu bar, Undo / Redo, Settings, the names, the welcome screen,
samples, Revert to Original, the spinner and VoiceOver names. The tests save
their settings in a scratch file, so they never change what the app remembers for you.
