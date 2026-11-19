# Changelog

Every version of Mesh Viewer, newest first (version lives in `meshviewer/__init__.py`).

| Stage | Focus |
|---|---|
| **2.0** | Native macOS app bundle (py2app + Qt) replacing the AppleScript/VTK UI |
| **2.1** | Selection, mesh quality, section plane, CAD formats, measurement, appearance |
| **2.2** | Edit (rotate/mirror/move) and Export |
| **2.3** | Cell quality, Info, CFD ($y^+$) and Inflation Layers |
| **2.4** | Simulation results, icon bar sidebar, `.msh`/`.dxf`, section plots |
| **2.5** | macOS polish (menu bar, undo, Settings, inspector), Select ▾, Contours, vector SVG, OpenFOAM |

<details><summary>Version renumbering history (Now · was · before that)</summary>

| Now | Was | Before that |
|---|---|---|
| 2.4.8 | 2.18.4 | 2.20.1 |
| 2.4.7 | 2.18.3 | 2.20 |
| 2.4.6 | 2.18.2 | 2.19.2 |
| 2.4.5 | 2.18.1 | 2.19.1 |
| 2.4.4 | 2.18 | 2.19 |
| 2.4.3 | 2.17 | 2.18 |
| 2.4.2 | 2.16.1 | 2.17 |
| 2.4.1 | 2.16 | |
| 2.4 | 2.15 | |
| 2.3.15 | 2.14.2 | |
| 2.3.14 | 2.14.1 | |
| 2.3.13 | 2.14 | |
| 2.3.12 | 2.13.2 | |
| 2.3.11 | 2.13.1 | |
| 2.3.10 | 2.13 | |
| 2.3.9 | 2.12.2 | |
| 2.3.8 | 2.12.1 | |
| 2.3.7 | 2.12 | |
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
| 2.1 | 2.1 | |
| 2.0 | 2.0 | |

</details>

## 2.5.2 — OpenFOAM cases, time steps & animation, Probe

- **OpenFOAM cases**: **File ▸ Open Case… (⇧⌘O)** and the welcome screen's **Solver** pop-up open a case folder, its `polyMesh`, a `.foam` file or a decomposed case (`core/mesh/openfoam.py`, `gui/welcome.py`). 3D: a part per patch plus the cells for Section and Cell Quality; one-cell-thick cases open as 2D, flat in XY (`core/mesh/openfoam_2d.py`).
- **Results**: the latest time step's fields in Contours and Measure Selected, with units from the file's dimensions and Custom… units per file (`core/mesh/openfoam_files.py`, `core/field_kinds.py`, `core/units.py`). Tensors, means, vorticity, Q, λ2, φ and more; fields a contour can't show and 2D out-of-plane components left out; Field menus grouped in submenus.
- **Time steps & animation**: ▸ Animation on a contour and a playback bar (play, scrub, loop, fps) swap each step's fields in place; Timeline or Current Step color range; Section's cut cells, Plots and Measure Selected follow the step (`render/timesteps.py`, `gui/window_animation.py`, `gui/widgets/animation_bar.py`).
- **Probe** (Analyze tab): points, lines or areas — a field over time in its own tab, or every field at one step, with CSV export; **Select Vertex Point** (`core/probe.py`, `gui/panels/probes.py`).
- **Plots on 2D files**: the zone cut along a line normal to X or Y (`core/plots.py`).
- **Speed**: fields copied into the existing VTK arrays, contours recolored in place, only the fields in use read, steps read ahead in the background (`core/mesh/openfoam_cache.py`, `core/mesh/openfoam_steps.py`). A step 32 → 17 ms; pitzDaily LES (601 steps): open 4.5 → 3.6 s, memory 1,068 → 269 MB.

## 2.5.1 — Multi-tab Contours, draggable color bar, vector SVG screenshots, cleaner feature edges

- **Contours (formerly Results)**: Create multiple contours, each in its own tab under the view alongside **3D View** (`gui/panels/contours.py`, `gui/window_pages.py`). Each tab stores its own camera, visibility toggles, and hidden parts, and syncs automatically with its right-sidebar fold-out.
- **On-canvas color bar**: Vertical color bar anchored top-left over the 3D view (`render/colorbar.py`). Draggable anywhere, included in screenshots, and customizable (smooth or banded colors, 2–15 linear or round logarithmic ticks, height, width, text color, title).
- **Plots**: Reorganized into Plane, Plot, Axes, and Data (`gui/panels/plots.py`). Added instant **Flip Y**, **Swap** axes, min/max data filters, **🔒 Lock** zoom/pan, and **View ▸ Fit (⌘0)**.
- **Vector SVG & selection**: Save Screenshot exports true editable vector SVGs (facets, edges, contour gradients, color bar, and 2D plots) as well as PNG/JPEG (`render/svg.py`, `render/screenshot.py`). **Measure Selected** displays nodal values or length/area-weighted field averages (`render/element_details.py`). Measurement marks stay visible across tools; right sidebar uses a floating overlay scrollbar; added **Show ▸ Axis Indicator**.
- **Cleaner mesh feature edges**: Drops floating or zig-zagging mesh diagonals, bridges collinear/coplanar gaps (connecting ONERA M6 tip curves to the leading edge), and keeps smooth 3D curves intact until sharp corners or junctions (`core/features.py`).

## 2.5 — macOS polish, Select ▾, STEP assemblies, Inflation Layers in 3D, DXF text, smooth zoom

*(Includes 2.5 betas 1–5)*

- **Native macOS architecture**: Full menu bar, **Edit ▸ Undo / Redo** for model edits, visibility, selection, and camera moves (`gui/undo.py`), **Settings… (⌘,)** window, native sheets, welcome screen with built-in samples, **Revert to Original…**, toolbar customization, and VoiceOver support (`gui/window_bars.py`, `gui/dialogs/settings.py`, `gui/welcome.py`).
- **Three-tab Right Sidebar (Inspector)**: Left sidebar dedicated to the parts tree; tools organized into **View**, **Measure**, and **Analyze** tabs on the right (`gui/inspector.py`, `gui/sidebar.py`).
- **Select ▾ & Measure Selected**: Pick parts, mesh nodes/edges/triangles/volume cells, or feature nodes/edges/faces (`render/elements.py`, `core/features.py`). **Measure Selected** reports exact coordinates, lengths, areas, volumes, circle radii, normals, dihedral angles, and cell quality (`core/element_info.py`, `gui/panels/selected.py`). 2D picking and snapping use screen-space tolerance.
- **STEP/IGES assemblies & filtering**: Preserves assembly hierarchies, native part colors, and material metadata (`core/cad/occt.py`). Added sorting (Name, Size, Volume), numeric filter limits (`size > 20`, `volume < 1000`), group renaming, and toggleable McMaster part grouping (`gui/panels/parts.py`, `core/part_filter.py`).
- **Inflation Layers & CFD**: Shows 3D inflation thickness shells over walls with automatic outward/inward side detection (`render/overlays.py`), paired with a scaled wall-layer stack on the Inflation page (`gui/pages/inflation.py`). Grouped CFD/FEA fields with unit conversions, Position X/Y/Z fields, and log color scales (`core/field_kinds.py`).
- **DXF & smooth zoom**: Renders DXF text, MTEXT, dimensions, and arrowheads as vector outlines with font fallback (`core/cad/dxf.py`). Smooth trackpad, pinch, and eased mouse-wheel zoom anchored to the cursor (`gui/viewport.py`, `render/camera.py`).

## 2.4.11 — Native OpenCASCADE triangulation

- Restored OpenCASCADE's direct triangulation (with Delabella) and removed custom face re-meshing (`core/cad/occt.py`), cutting large assembly open times significantly (e.g., 300-part assembly 3.3 s → 0.1 s).

## 2.4.10 — Even STEP meshes, parallel camera clipping & axis label fixes

- Added target-size face remeshing (`core/cad/remesh.py`). Kept parallel cameras far behind the model to prevent close-up clipping and uniformized axis label sizes (`render/camera.py`).

## 2.4.9 — Performance & codebase modularization

- **Speedups**: Single-pass frame rendering (`gui/viewport.py`), single composite selection outline (`render/scene.py`), instanced meshing for repeated CAD assembly parts (`core/cad/occt.py`), and shared VTK array views (`core/polys.py`).
- **Refactor**: Split `Scene`, `ViewerWindow`, `Sidebar`, and widgets into single-responsibility modules and added `tools/bench.py`.

## 2.4.8 — Scrollable plot tabs

- Added horizontal scrolling and right-click context menus (Open, Rename, Delete) to view tabs (`gui/window.py`).

## 2.4.7 — Result units, arbitrary section planes & cut visibility toggles

- Added input/display unit conversion for solution fields (`core/units.py`, `gui/panels/results.py`), arbitrary plane origin/normal controls in Section and Plots, and per-cut visibility toggles (`Eye` icon).

## 2.4.6 — Card-based sidebar styling

- Styled all sidebar sections on uniform rounded cards and aligned Section and Plots layouts (`gui/sidebar.py`, `gui/style.py`).

## 2.4.5 — Section slider stability & plot controls

- Fixed a memory lifetime crash during rapid section sliding via `core/polys.bare()`, debounced plot slider updates, and streamlined plot cards (`gui/panels/plots.py`).

## 2.4.4 — Section Plots & surface gradients

- Added **Plots** (`core/plots.py`, `gui/pages/plots.py`) to slice visible boundaries along X/Y/Z planes, plot fields (such as $c_p$ vs $x/c$), and import/export CSV data. Added surface gradient magnitude ($|\nabla f|$) and jump highlighting to Results.

## 2.4.3 — Gmsh/Fluent `.msh` & DXF support

- Added readers for 2D/3D Gmsh and Fluent `.msh` files (`core/mesh/msh.py`) and 2D DXF drawings (`core/cad/dxf.py`). Added +Z locked 2D navigation, visual colormap swatches, and **Distance ▸ From origin**.

## 2.4.2 — File unit prompt & unified Distance tool

- Added first-open file unit detection/prompting (`gui/dialogs/units.py`), merged Point and Distance into a single tool, and added inline formula popups (`render/measure.py`, `gui/panels/cfd.py`).

## 2.4.1 — Icon bar sidebar, SF Symbols & polyhedral CGNS

- Added an icon bar sidebar (`gui/sections.py`), native macOS SF Symbols (`gui/icons.py`), polyhedral CGNS (`NGON_n`/`NFACE_n`) volume support (`core/mesh/polyhedra.py`), and reorganized the codebase into `core/`, `render/`, and `gui/`.

## 2.4 — FUN3D / Tecplot simulation results

- Added Tecplot ASCII `.dat` reader (`mesh/tecplot.py`) and **Results** panel to contour boundary variables (`gui/results_panel.py`).

## 2.3.15 — Internal pipe/duct flow & exact CAD section curves

- Added internal flow mode (hydraulic diameter Reynolds number and Petukhov/laminar friction) and exact OpenCASCADE curve slicing for CAD cross sections (`cfd.py`, `cad/occt.py`).

## 2.3.14 — Uniform CAD $y^+$ wall coloring

- Subdivided CAD wall triangles for smooth $y^+$ contours and standardized plot axis styling (`gui/inflation_view.py`).

## 2.3.13 — CFD mesher export, streamwise $y^+$ & law-of-the-wall guide

- Added inflation layer export for OpenFOAM, Fluent, STAR-CCM+, Pointwise, and CSV (`cfd_export.py`), streamwise $y^+$ curves, temperature-dependent fluid properties, and an interactive law-of-the-wall ($u^+$ vs $y^+$) guide (`gui/wall_help.py`).

## 2.3.12 — Simplified inflation cross section

- Streamlined the 2D inflation cross section with automatic outward side detection and **Flip side** (`gui/section_view.py`).

## 2.3.11 — Flow arrows & smooth cross-section curves

- Added flow direction arrows, legend toggles, and Catmull-Rom curve smoothing to the inflation cross section (`gui/section_view.py`).

## 2.3.10 — 2D inflation layer cross section

- Added the 2D **Cross section** tab on the Inflation page to visualize offset boundary layers along the active section plane (`gui/section_view.py`).

## 2.3.9 — Full-width inflation layer plot

- Redesigned the Inflation page with full-width layer height and cumulative thickness plots and hover readouts (`gui/inflation_view.py`).

## 2.3.8 — Unified Flow inputs in CFD mode

- Shared the standard atmosphere/water/custom fluid model between mesh CFD and CAD CFD mode (`gui/inflation_panel.py`, `cfd.py`).

## 2.3.7 — Wall face picking & Hide Surface

- Added individual CAD face picking for inflation walls and right-click **Hide Surface** (`gui/inflation_panel.py`, `gui/scene.py`).

## 2.3.6 — CFD unit menus & part color dots

- Added per-field unit selectors across CFD inputs and live color dots in the Boundary dropdown (`gui/cfd_panel.py`, `gui/widgets.py`).

## 2.3.5 — Color by $y^+$, compressibility & LaTeX formulas

- Added 3D wall coloring by $y^+ / y^+_{\text{target}}$, Raymer compressibility correction, and rendered LaTeX formula popups (`gui/cfd_view.py`, `cfd.py`).

## 2.3.4 — Coupled Mach / Speed $U$ inputs

- Linked Mach number and speed $U$ bidirectionally and locked standard fluid properties unless Custom is selected (`gui/cfd_panel.py`).

## 2.3.3 — Streamwise auto-length & CFD Values popup

- Computed characteristic length $L$ along the flow vector (`streamwise_length`) and added a full computed-values popup (`cfd.py`, `gui/cfd_panel.py`).

## 2.3.2 — CAD Inflation Layer calculator

- Added **CFD mode** for CAD files with a dedicated **Inflation layers** page showing boundary-layer thickness ($\delta_{99}$), layer stack, and transition checks (`gui/inflation_panel.py`, `gui/inflation_view.py`).

## 2.3.1 — Mesh CFD ($y^+$) estimator & U.S. Standard Atmosphere

- Added the **CFD** tool with 1976 U.S. Standard Atmosphere / water models, flat-plate skin friction $y^+$ estimation, first-cell height measurement, and 3D flow vectors (`cfd.py`, `gui/cfd_panel.py`).

## 2.3 — Cell quality, Info, Angle measurement & per-file memory

- Added VTK Verdict **Cell quality** histograms (`quality.py`), **Info** geometry summary (`gui/info_panel.py`), face-to-face **Angle** measurement, OBJ/PLY color export, and per-file state restoration (`gui/memory.py`).

## 2.2.6 — Custom part colors & Faces toggle

- Added right-click **Colour…** picker for parts and replaced "Edges only" with the **Faces** toolbar toggle (`gui/scene.py`, `gui/part_tree.py`).

## 2.2.5 — Display toggles moved to toolbar

- Moved edge, face, axis, grid, bounding box, and origin toggles into toolbar pills (`gui/window.py`).

## 2.2.4 — Arbitrary-angle rotations & Edges only

- Redesigned **Edit** to support arbitrary rotation angles, added **Edges only** mode, and moved shading to Appearance (`gui/edit_panel.py`, `transform.py`).

## 2.2.3 — Part renaming & McMaster detection

- Added inline part renaming (preserved on export) and automatic McMaster-Carr part number detection anywhere in filenames (`gui/part_tree.py`, `export.py`).

## 2.2.2 — Uniform Edit layout, shading toggle & `dmgbuild`

- Standardized Edit buttons, added flat-shading toggle, and switched `.dmg` packaging to `dmgbuild` (`gui/edit_panel.py`, `make_dmg.sh`).

## 2.2.1 — Translation moves & original wireframe comparison

- Added X/Y/Z translation, origin/center pivot selection, single-step Undo/Reset, and **Show original edges** overlay (`gui/edit_panel.py`, `transform.py`).

## 2.2 — Edit (rotate/mirror) & multi-format Export

- Added exact 90° rotations/mirrors (`transform.py`) and export to STL, OBJ, PLY, VTU, and UGRID + `.mapbc` (`export.py`, `gui/export_dialog.py`).

## 2.1.23 — Toolbar parallel projection toggle

- Moved parallel projection toggle into the camera toolbar pill (`gui/window.py`).

## 2.1.22 — Unified Axes/Grid modes & fixed-size section handles

- Consolidated axes/grid switches into **Off · Axes · Grid · Both** and kept section plane handles constant in screen size (`gui/section.py`).

## 2.1.21 — Out-of-tree build directory

- Moved `.venv`, `build/`, `dist/`, and `.dmg` artifacts to `~/Downloads/MeshViewer-build` (`build_app.sh`, `make_dmg.sh`).

## 2.1.20 — Volume mesh reading & section cell slicing

- Added CGNS/UGRID volume cell readers (`mesh/volume.py`) and volumetric cell slicing in the Section tool (`gui/section.py`).

## 2.1.19 — Origin marker, axis flipping & GitHub docs layout

- Added `(0, 0, 0)` RGB origin marker, opposite-axis camera toggling (X → −X), and structured `README.md`, `CHANGELOG.md`, and `LICENSE`.

## 2.1.18 — Toolbar-unit axis labels

- Linked grid axis labels and titles to the active toolbar display unit (`gui/scene.py`).

## 2.1.17 — Screen-space measurement markers & transparent screenshots

- Made distance points fixed-size screen dots, added transparent PNG screenshots, and auto-expanded Section on toggle (`gui/measure.py`).

## 2.1.16 — Zoom edge hiding & About dialog

- Hid edges during scroll/pinch zoom bursts and added **About Mesh Viewer** (`gui/about_dialog.py`).

## 2.1.15 — Smooth edge hiding & line thickness

- Hid edges during camera movement on all models and added Thin/Medium/Thick edge options (`gui/appearance_dialog.py`).

## 2.1.14 — Standalone bundle slimming

- Added `slim_bundle.py` to strip unused Qt modules and universal slices, shrinking PySide6 from ~1.2 GB to ~0.15 GB.

## 2.1.13 — Homebrew dylib repair in standalone builds

- Added `fix_bundle.py` to restore and relink Homebrew dynamic libraries corrupted by `py2app`.

## 2.1.12 — `.dmg` installer & self-test

- Added `make_dmg.sh` and `--selftest` bundle verification (`mesh_viewer.py`).

## 2.1.11 — Non-selecting right-click & axis label sizing

- Prevented right-click from altering selection, added "Search in McMaster", and added Small/Medium/Large axis labels (`gui/part_tree.py`).

## 2.1.10 — Group toggle fix & transparent background option

- Fixed double-toggle on tree group clicks and added transparent background export (`gui/part_tree.py`, `gui/screenshot_dialog.py`).

## 2.1.9 — List density & light-mode accent contrast

- Added Compact/Comfortable part list spacing and adjusted system accent contrast in light mode (`gui/part_tree.py`, `gui/style.py`).

## 2.1.8 — Appearance sheet, custom backgrounds & McMaster grouping

- Added **Appearance** (System/Light/Dark themes, solid color or cropped image backgrounds) and top-level **McMaster Parts** grouping (`gui/appearance_dialog.py`, `gui/background.py`).

## 2.1.7 — Display units, context menus & multi-part selection bar

- Added toolbar unit conversion, 3D right-click menus, and selection count bar (`gui/window.py`, `gui/measure.py`).

## 2.1.6 — Hierarchical part tree & off-screen screenshots

- Replaced flat part list with collapsible prefix groups (`gui/part_tree.py`) and rendered screenshots off-screen at full resolution (`gui/scene.py`).

## 2.1.5 — Distance/Area measurement & multi-select

- Added 3D point-to-point **Distance** and CAD face **Area** measurement, ⌘/⇧ multi-select, and screenshot dialog (`gui/measure.py`, `cad/occt.py`).

## 2.1.4 — IGES, BREP & triangulated CAD formats

- Shared OpenCASCADE pipeline across STEP, IGES, and BREP, and added STL, OBJ, PLY, glTF, and VRML readers (`cad/occt.py`, `cad/tessellated.py`).

## 2.1.3 — Composite VTK actors & persistent section plane

- Batched all parts and feature edges into single composite VTK actors for fast rendering and added translucent section plane visualization (`gui/scene.py`, `gui/section.py`).

## 2.1.2 — Bounding-box culled section cutting

- Sped up section slicing with bounding-box culling and `vtkPolyDataPlaneCutter` (`gui/section.py`).

## 2.1.1 — Collapsible sections & system accent styling

- Added light/dark palettes, system accent highlights, and collapsible sidebar sections (`gui/style.py`, `gui/widgets.py`).

## 2.1 — 3D picking, adaptive STEP tessellation & section tool

- Added click picking, 5-level background STEP re-tessellation (`cad/step.py`), and interactive **Section** slicing (`gui/section.py`).

## 2.0 — Native macOS Qt application

- Replaced the AppleScript droplet and VTK-drawn UI with a standalone `py2app` + PySide6 application supporting native menus, dark mode, searchable part lists, and multi-window file opening (`gui/`).