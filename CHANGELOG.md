# Changelog

Every version of Mesh Viewer, newest first. Each table lists the files that
changed and what changed in them. (The version number lives in
`meshviewer/__init__.py`.)

**Version numbers:** 2.X for a bigger update (a new feature or section), 2.X.Y for a
smaller one (tweaks, fixes). Versions before 2.11.4 were renumbered to follow this;
the old numbers:

<details><summary>Old → new numbers</summary>

| Old | New |
|---|---|
| 2.2 | 2.1.1 |
| 2.3 | 2.1.2 |
| 2.4 | 2.1.3 |
| 2.5 | 2.2 |
| 2.6 | 2.3 |
| 2.7 | 2.3.1 |
| 2.8 | 2.3.2 |
| 2.9 | 2.4 |
| 2.9.1 | 2.4.1 |
| 2.10 | 2.4.2 |
| 2.11 | 2.4.3 |
| 2.12 | 2.5 |
| 2.12.1 | 2.5.1 |
| 2.13 | 2.5.2 |
| 2.14 | 2.5.3 |
| 2.15 | 2.5.4 |
| 2.16 | 2.5.5 |
| 2.17 | 2.5.6 |
| 2.18 | 2.6 |
| 2.19 | 2.7 |
| 2.20 | 2.7.1 |
| 2.21 | 2.7.2 |
| 2.22 | 2.7.3 |
| 2.23 | 2.8 |
| 2.24 | 2.8.1 |
| 2.25 | 2.8.2 |
| 2.26 | 2.8.3 |
| 2.27 | 2.8.4 |
| 2.28 | 2.8.5 |
| 2.29 | 2.8.6 |
| 2.30 | 2.9 |
| 2.31 | 2.10 |
| 2.32 | 2.11 |
| 2.33 | 2.11.1 |
| 2.34 | 2.11.2 |
| 2.35 | 2.11.3 |
| 2.36 | 2.11.4 |

</details>

## 2.20.1 — Plot tabs scroll; right-click a tab

| File | |
|---|---|
| `gui/window.py`, `gui/style.py` | The tabs under the view scroll sideways when there are too many plots (thin bar; the wheel or trackpad scrolls them; the open tab stays in view) |
| `gui/window.py` | Right-click a plot's tab: **Open**, **Rename…**, **Delete** |

## 2.20 — Units for results, any plane for a cross section, eye on each cut

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

## 2.19.2 — Every section on a card; Section and Plots alike

| File | |
|---|---|
| `gui/sidebar.py`, `gui/style.py`, `gui/window.py` | **Every sidebar section on a grey card** (the Plots look), with cards and segmented controls inside a shade lighter; the sidebar opens a little wider so CFD fits on its card |
| `gui/panels/section.py` | **Section laid out like a Plots cross section**: *Plane* — Normal to [X Y Z] (lit when the plane is along one) and Flip; Position slider and Center; Origin / Normal; then *Show* — Fill cut faces, Show plane |
| `gui/panels/plots.py` | *Plane* / *Position* as in Section; **Normalize** instead of x/c; Along made of fixed X / Y / Z buttons (the plane's own axis hidden): Y now lights up when chosen (rebuilt buttons stayed unlit on macOS); New Measurement… on its card |
| `gui/icons.py` | Results: `waveform.path.ecg.text.page`; Plots: `chart.xyaxis.line` |

## 2.19.1 — Plots: no more crash when sliding, tidier controls

| File | |
|---|---|
| `core/polys.py` (`bare`), `core/plots.py`, `core/fields.py`, `core/export.py`, `core/cfd.py`, `render/overlays.py`, `render/quality_overlay.py`, `render/scene.py`, `gui/pages/section_cut.py` | **Crash fixed** (moving a cross section quickly): new surfaces were built from NumPy views of a part's points and faces, and VTK could keep pointers into memory NumPy freed. They now share the part's structure inside VTK (`bare`). The same pattern elsewhere (y+ and results colours, cell quality, export, CFD walls) fixed too |
| `gui/panels/plots.py` | The slider plots once it rests (40 ms), not on every pixel |
| `gui/panels/plots.py` | **Tidier measurement controls**: one card per measurement in three groups — *Cut* (normal to, at, slider), *Plot* (values, along + an x/c toggle, negative up), *Points* (Import… · Export…); *Rename… · Delete* under the card instead of the ⋯ button; the point count is gone (only problems are shown) |
| `gui/panels/results.py`, `render/overlays.py`, `core/fields.py` | *Highlight sharp changes* and *Jump over* removed (Gradient stays) |

## 2.19 — Plots (cross sections in tabs), gradients and sharp changes

| File | |
|---|---|
| `core/plots.py` (new), `gui/panels/plots.py` (new), `gui/pages/plots.py` (new), `gui/sections.py`, `gui/sidebar.py`, `gui/window.py`, `gui/memory.py`, `gui/icons.py`, `gui/widgets.py` | **Plots** (F13): *New Measurement…* (name + type) adds a sub-section in the sidebar and a tab under the 3D view (3D model · Inflation layers · one per measurement). Built to take more kinds; the first is the **cross section**: the visible boundaries cut by a plane normal to X / Y / Z (position typed or slid; the cut drawn in 3D while Plots is open), a field or the shape plotted along the cut, x/c, negative up (cp by default), hover for the numbers, reference points from a CSV, the points to a CSV. ⋯ menu: Show Plot, Rename…, Delete. Remembered per file, with the open tab. Not for 2D files yet |
| `core/fields.py`, `gui/panels/results.py`, `render/overlays.py` | **Results ▸ Show ▸ Gradient** (F15): |∇f| along the surface. **Highlight sharp changes**: faces where the field changes by more than *Jump over* % of its range, in pink over the colours, with their count |
| `render/scene.py`, `gui/panels/results.py` | Several listeners can follow shown / hidden boundaries (Results, Plots) |

## 2.18 — Gmsh / Fluent .msh, DXF drawings, colour maps

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

## 2.17 — File unit, one Distance tool, formula links

| File | |
|---|---|
| `gui/dialogs/units.py` (new), `gui/window.py`, `gui/panels/info.py`, `gui/memory.py`, `render/measure.py` | **File unit**: the first time a file is opened, a sheet asks what unit its numbers are in (STEP / IGES: their own, mm, preselected; meshes: m; other CAD: mm). Remembered per file; **Info ▸ File unit** changes it. The toolbar's "no unit" button is gone: the toolbar unit is the one shown, converted from the file's |
| `render/measure.py`, `gui/panels/measure.py`, `render/section.py` | **Distance and Point are one tool**: click a point — its X / Y / Z, distance from the origin and to the section plane; click a second — the distance and ΔX, ΔY, ΔZ between them |
| `gui/widgets.py`, `gui/panels/cfd.py`, `gui/panels/inflation.py` | Formulas pop-ups open next to the sidebar, by the link that opened them. The y+ formula links to CFD Online, and a CFD Online link closes the y+ formulas (meshes and CFD mode) |
| `gui/panels/inflation.py` | **Next cell**: hover it — about 2 × the largest layer is a smooth step into the volume mesh; use about that size for the surface cells too (low aspect ratio) |
| `gui/pages/inflation.py`, `gui/panels/inflation.py`, `core/cfd.py`, `core/cfd_export.py`, `gui/dialogs/wall_help.py` | **y+ along the flow removed** (tab, curve, Values rows, export line). The y+ tile shows the estimated y+ |

## 2.16 — Icon bar sidebar, code reorganised, fixes

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

## 2.15 — Simulation results on the boundaries (FUN3D / Tecplot)

| File | |
|---|---|
| `mesh/tecplot.py` (new), `formats.py` | Opens **Tecplot ASCII `.dat`** results as FUN3D writes them (`project_tec_boundary.dat`): one part per boundary ("boundary 1 WING" → WING) with every variable at its nodes. FEBLOCK and POINT packing, triangles and quads, cell-centred variables; a boundary written more than once keeps the last time step. Binary `.plt` / `.szplt` are not read |
| `gui/results_panel.py` (new), `gui/sidebar.py` | **Results** section, shown when the file has results: *Field* (every variable, plus *Speed* \|u, v, w\|), *Colour the boundaries*, the colour scale with its numbers, *Min* / *Max* (empty = auto), max · mean · min on the visible boundaries, and *Values* (every field) |
| `gui/cfd_view.py`, `gui/scene.py` | The colours are drawn over the visible parts: blue scale for fields of one sign, blue–grey–red centred on zero for signed ones (cp, u, v, w). Cut by the section plane, mesh edges follow the toolbar, hiding a part updates the colours and the numbers |
| `gui/memory.py`, `gui/window.py` | The field, range and on / off are remembered per file |

## 2.14.2 — Internal flow, exact CAD cross section; no y+ colours on the walls

| File | |
|---|---|
| `gui/inflation_panel.py`, `gui/cfd_view.py`, `gui/scene.py`, `cfd.py` | **Colour walls by y+ removed** (and the walls' re-splitting and per-point leading edges it needed). The y+ along the flow is now the page's curve only; the max / min / mean of the tile come from it |
| `cfd.py`, `gui/cfd_panel.py`, `gui/inflation_panel.py`, `gui/inflation_view.py`, `cfd_export.py` | **Flow: External / Internal (pipe or duct)**, in the CFD section and CFD mode. Internal: Reynolds number on the hydraulic diameter D (auto: 2ab / (a + b) from the walls' widths across the flow, or typed), skin friction of developed pipe flow (laminar 16 / Re below 2300, Petukhov above), no compressibility correction; the "boundary layer" is the pipe radius and the check is that the layers fit in it; y+ along the pipe: a flat plate from the inlet until the developed value |
| `cad/occt.py`, `gui/section_view.py` | Cross section of STEP / IGES / BREP: the walls are cut from the **CAD curves** themselves (smooth at any zoom), once the plane stops moving — the triangles while it moves |
| `gui/section_view.py` | Flow direction: three thin **inlet arrows** on the upstream edge of the view instead of the boxed arrow; a small dot / cross when the flow goes through the plane |

## 2.14.1 — Even y+ colours on CAD, max y+ tile, plots alike

| File | |
|---|---|
| `gui/inflation_panel.py`, `gui/cfd_view.py`, `cfd.py` | Colour walls by y+ (CAD): the walls are split into small triangles of about the same size (no edge longer than h, about 3 000 of them by area; cached) before the y+ is worked out and drawn, so the long thin triangles of the CAD tessellation no longer smear the colours; the colours are drawn without that mesh's lines. The leading-edge strips are square (a wing gets strips along its span, not cut through its thickness) |
| `gui/inflation_view.py` | the y+ tile is like the mesh's: **max y+ on the walls** big (green / orange / red against the target), *min · mean* beside it, the y+ at the end of the walls below; the check line gives max, min and mean |
| `gui/inflation_view.py` | the two plots share one look: a **y-axis title** along the axis (Height (mm) · y+ of the first layer), the x-axis title under it, reference lines named at the right with their value under the name, an end label moved off them; y+ along the flow **always shows the viscous sublayer** (y+ 5) and notes the first layer it uses |
| `gui/cfd_panel.py`, `gui/inflation_panel.py` | **Temperature** greyed out for *Air — altitude*, like density, viscosity and sound speed (the altitude's standard temperature); typed for water |

## 2.14 — CFD export, y+ along the flow, wall functions, temperature, update check

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

## 2.13.2 — Simpler cross section; every number in Values

| File | |
|---|---|
| `gui/section_view.py`, `gui/inflation_view.py` | Cross section: only the **inflation layers** are drawn (boundary-layer and next-cell lines removed, layers always shown); the legend's only toggle is the **flow direction** arrow. **Flip side** button replaces External / Internal flow: by default the layers go on the outside of each closed cut of the model (tested against the cut itself, so CAD normals facing inward no longer matter; open surfaces follow their normals); Flip side puts them on the other side (internal flow). **Fit view** is a button like the others, in the header row. Smooth curves removed (it made the view lag) |
| `gui/inflation_view.py`, `gui/inflation_panel.py` | the line of small numbers under the page is gone; they're all in the **Values** pop-up (recovery factor added there for supersonic flow) |
| `README.md`, `docs/screenshots/` | new **CFD tools** section with three screenshots (CFD mode in 3D, layer size plot, cross section); features and *Using it* updated for CFD mode (walls, pick faces, cross section, Flip side), Colour by y+, Formulas / Values, right-click ▸ Hide Surface |

## 2.13.1 — Cross section: flow side, toggles, smooth curves, flow arrow

| File | |
|---|---|
| `gui/section_view.py`, `gui/inflation_view.py` | Cross section tab: **External flow / Internal flow** (which side of the walls gets the layers; replaces "Layers on the other side"); the legend sits top right like the plot's and each entry **shows / hides** what it names — inflation layers, boundary layer, top of the next cell, **flow direction** (an arrow of Flow ▸ Direction seen on the plane, or a dot / cross when it goes through the plane); **Smooth curves**: a smooth curve through the cut (centripetal Catmull-Rom through the surface points, points in the middle of flat facets dropped), sharp corners (> 30°) kept; a **Fit view** button |

## 2.13 — Cross section of the inflation layers

| File | |
|---|---|
| `gui/section_view.py` (new), `gui/inflation_view.py`, `gui/window.py` | Inflation page ▸ **Cross section** tab (replaces the "Near the wall" placeholder): it follows the section plane (sidebar ▸ Section) and draws its cut in 2D, facing the plane — the model in light grey, the walls in a dark line — with an **estimate of the inflation layers** on the walls: each layer is the wall outline pushed out along the wall's normal by the total thickness so far (mitred corners); layers closer than 2 px merge into a solid band; dashed = boundary layer, dotted = top of the next cell. Scroll to zoom, drag to pan, double-click or *Fit* to fit; *Layers on the other side* for open surfaces facing the other way; scale bar and legend. Messages when Section is off or the plane misses the walls |


## 2.12.2 — Inflation page: tabs, full-width plot, plain names

| File | |
|---|---|
| `gui/inflation_view.py` | the plot sits in a card with tabs — **Layer size plot** and **Near the wall** (a placeholder for the next view) — and takes the full width. Redrawn like the rest of the app: a bar per layer (its height), a line + soft area for the total thickness so far, light horizontal grid, the boundary layer (dashed) and next cell size (dotted) labelled on the right, a legend above, hover crosshair with the layer's numbers. Colour-blind-safe series colours for light and dark. *Near the wall* restyled to match |
| `gui/inflation_panel.py`, `gui/inflation_view.py` | plain names: First layer, Layers, Growth rate, **Next cell (× max layer height)**; tiles and checks say "boundary layer thickness", "total thickness of the layers", "max layer height" |

## 2.12.1 — CFD mode: Flow like the CFD section, growth 1–2, desired cell factor

| File | |
|---|---|
| `gui/inflation_panel.py`, `cfd.py` | CFD mode's **Flow** group is the same as the mesh CFD section: Fluid (air at an altitude, fresh / sea water at a depth, custom), density / viscosity / sound speed locked unless Custom, Mach and speed U, direction. The calculator takes these properties (`inflation(fluid=…)`); the 343 m/s option is gone (type U, or use Custom) |
| `gui/inflation_panel.py`, `gui/widgets.py` | **Growth rate** kept between 1 and 2 (`NumberField.setRange`: typed values snap in) |
| `gui/inflation_panel.py`, `cfd.py` | **Desired cell** is now a factor of the largest layer (× y_max, default 2, 1–10) |
| `gui/inflation_view.py` | plot: the purple "layers" lines removed; the numbers line leaves out T, p, k when they aren't known (water, custom) |

## 2.12 — CFD mode: walls, Formulas / Values, units; Hide Surface

| File | |
|---|---|
| `gui/inflation_panel.py`, `gui/inflation_view.py`, `gui/window.py` | **CFD mode** laid out like the mesh CFD section: **Flow** and **Inflation layers** fold, each with **Formulas** and **Values**; unit menus (altitude, speed U, length L, first / desired cell); **Speed U** can be typed (Mach follows); "?" right after *Altitude*; flow **direction** and **Show flow vectors**. **Walls**: the whole model, a part (with its colour dot), or **faces of one part** — *Pick faces…*, click / ⇧-click faces in the 3D view, **Apply**. The walls are tinted in the 3D view and give the **auto length L** (longest distance along the flow) and the wall area; *Back to auto length* after typing L. The Inflation page names the walls and L |
| `gui/scene.py`, `gui/sidebar.py`, `gui/memory.py` | right-click in the 3D view: **Hide Part** and **Hide Surface** (one CAD face); *Show Hidden Surfaces (n)*, and *Show All* brings them back; hidden surfaces are remembered per file |
| `gui/cfd_view.py` | `WallView`: the walls tint |

## 2.11.4 — CFD: unit menus, boundary colours, back to auto length

| File | |
|---|---|
| `gui/widgets.py`, `gui/cfd_panel.py` | **Unit menus** on every input: altitude / depth (m, km, ft), density (kg/m³, g/cm³, lb/ft³, slug/ft³), viscosity (Pa·s, cP, lb/ft·s), sound speed and speed U (m/s, km/h, kt, ft/s, mph), length L (m, cm, mm, in, ft); remembered per file. The "?" sits right after *Altitude*. **Back to auto length** link when L was typed |
| `gui/widgets.py`, `gui/cfd_panel.py`, `gui/sidebar.py` | the Boundary menu shows each part's **colour dot** (follows colour changes) |
| `gui/cfd_view.py`, `gui/scene.py` | Colour by y+ follows the view: its mesh edges hide while moving, and it turns to a coloured wireframe with the faces off |

## 2.11.3 — CFD: colour by y+, compressibility, speed units, Formulas

| File | |
|---|---|
| `gui/cfd_view.py`, `gui/scene.py`, `gui/cfd_panel.py` | **Colour by y+**: the boundary painted by y+ / target at each wall node (blue 0 · green 1 · orange 2 · red ≥ 3, grey where no first cell was found), with a colour scale in the panel. The max y+ is **green / orange / red** (≤ 1.25 ×, ≤ 2.5 ×, above the target) |
| `cfd.py`, `gui/cfd_panel.py`, `gui/inflation_panel.py` | **Compressibility correction** (on by default, in the y+ estimator and CFD mode): Cf × (1 + 0.144 M²)^−0.65 (Raymer, turbulent, adiabatic wall). Off = the plain flat-plate Cf (matches the original inflation calculator) |
| `gui/cfd_panel.py` | **Speed U** in m/s, km/h, kt, ft/s or mph |
| `gui/widgets.py`, `gui/style.py`, `gui/cfd_panel.py` | **Formulas** buttons beside *Values* (Flow, y+ estimator): a window in the middle of the app with every equation, drawn like LaTeX (matplotlib mathtext) |
| `setup.py`, `requirements.txt` | matplotlib bundled (draws the formulas) |

## 2.11.2 — CFD: speed U field, locked air / water values

| File | |
|---|---|
| `gui/cfd_panel.py`, `gui/style.py` | **Speed U** is a field: type U and Mach follows (M = U / a), type Mach and U follows. Density, viscosity and sound speed are greyed out and locked unless the fluid is *Custom*. The y+ card shows *min · mean* beside the max, and the mesh's largest first cell beside the first cell height for the target y+ |

## 2.11.1 — CFD section: folding groups, Values pop-ups, max y+

| File | |
|---|---|
| `gui/cfd_panel.py`, `gui/widgets.py`, `gui/style.py` | **Flow** and **y+ estimator** (was "y+") are groups that fold. Each has a **Values** button: a pop-up with every computed number (Flow: T, p, ρ, μ, ν, a, U, q, T₀, Re, laminar / turbulent; y+: L, Re, Cf, τw, u*, ν/u*, first cell, and from the mesh y+ max / mean / min, first cell max / mean / min, wall nodes). The big y+ is now the **max**, with the min beside it. Direction has X / Y / Z above the fields, which use the full width (no more clipped numbers) |
| `cfd.py` | auto length = the **longest distance along the flow** across the boundary (`streamwise_length`): a swept wing gives its root chord, not root leading edge to tip trailing edge |
| `gui/sidebar.py` | **Info** always starts closed |

## 2.11 — CFD mode for CAD files (inflation layer calculator)

| File | |
|---|---|
| `cfd.py`, `gui/inflation_panel.py` (new) | sidebar **CFD mode** (CAD files only, with an on / off switch): the inflation layer calculator. Flow: target y+, Mach, sound speed (at the altitude, or 343 m/s), length L (or *Use the model's length*), altitude (U.S. Standard Atmosphere). Layers: first cell (empty = the one for the target y+), number of layers N, growth rate G, desired cell above the layers (empty = 2 × the largest layer). Re = ρUL/μ, Cf = (2 log10 Re − 0.65)^−2.3, u* = √(τw/ρ), y_min = y+ μ/(ρ u*), y_tot = Σ y_min Gⁿ, δ99 = 0.38 L / Re^0.2 (turbulent) or 4.91 L / √Re (laminar), divided by (1 + 0.2 M²)^(1/9) above Mach 1. Settings are remembered per file |
| `gui/inflation_view.py` (new), `gui/window.py` | with CFD mode on, a bar under the 3D view switches between **3D model** and **Inflation layers**: a page with the key numbers (Reynolds, first cell, estimated y+, δ99, total height, largest layer), the plot (total height and layer height vs layer #, boundary layer, desired cell; hover for values), the layer stack near the wall drawn to scale, and two checks (layers cover the boundary layer · smooth transition) |
| `gui/sidebar.py`, `gui/scene.py`, `gui/memory.py`, `gui/style.py` | CFD mode shows for CAD files, the CFD (y+) section for meshes; page colours for light and dark |

## 2.10 — CFD section (y+), clearer Info, Point from the origin

| File | |
|---|---|
| `cfd.py` (new), `gui/cfd_panel.py` (new), `gui/cfd_view.py` (new) | sidebar **CFD**: flow (air at an altitude — U.S. Standard Atmosphere 1976 —, fresh / sea water at a depth, or your own density, viscosity and sound speed; Mach; flow direction X / Y / Z) and a **y+** estimate on a chosen boundary: flat-plate skin friction Cf = (2 log10 Re − 0.65)^−2.3, τw = Cf ½ρU², u* = √(τw/ρ), y+ = y u* ρ / μ. With volume cells, y is the first cell layer measured on the mesh (average, min, max); the first cell height for a target y+ is always given. **Show flow vectors** draws arrows before and after the boundary. "?" buttons open the CFD Online y+ page and the standard-atmosphere table. Settings are remembered per file |
| `gui/info_panel.py`, `gui/sidebar.py` | **Info** is the first section (remembers open / closed) and is easier to read: an Extent table (from / to / size per axis, with the unit or "file units"), then Faces, Points, Edge length, Volume cells, each with a short grey note |
| `gui/measure.py`, `gui/measure_panel.py` | Measure ▸ **Point** works like Distance with the first point at the origin (0, 0, 0): line, ΔX / ΔY / ΔZ and the distance from the origin |
| `gui/section.py`, `gui/section_panel.py`, `gui/memory.py` | the section **normal is kept as typed** (no longer rescaled to length 1) |
| `gui/widgets.py`, `gui/style.py` | `NumberField` (takes 1.8e-5 or 0,3), round "?" help buttons, `MenuSelect.clear()` |

## 2.9 — Cell quality, Info, more measurements, files reopen as you left them

| File | |
|---|---|
| `quality.py` (new), `gui/quality_panel.py` (new), `gui/quality_view.py` (new) | sidebar **Cell quality** (mesh files only): skewness, aspect ratio, scaled Jacobian or volume of every cell (VTK Verdict; computed in the background). Histogram coloured like the 3D view — click or drag it to set the "bad" threshold; bad-cell count, **Zoom** to them, **Show bad cells** (red, model see-through), **Colour by quality** (the section cut for volume meshes, the faces for surface meshes), inverted-cell check |
| `mesh/volume.py`, `transform.py` | volume cells read in the opposite node order (e.g. CGNS prisms vs VTK) are turned the right way out when most of a type is inside out, so volumes and quality are right |
| `gui/info_panel.py` (new), `polys.py` (new) | sidebar **Info**: size, bounds, face and point counts, shortest / longest edge, volume cells by type |
| `gui/measure.py`, `gui/measure_panel.py`, `gui/scene.py`, `gui/section.py` | Measure ▸ **Point** (coordinates, and distance to the section plane) and **Angle** (between two clicked faces, or a face and the cut); "Area & Volume" is now "Area" |
| `gui/memory.py` (new), `gui/window.py`, `gui/app.py` | **File ▸ Open Recent**; each file **reopens the way you left it** (camera, toggles, unit, colours, names, hidden parts, section). Only edits still ask before closing |
| `export.py`, `gui/export_dialog.py` | **OBJ** (with a .mtl) and **PLY** keep the part colours; VTU no longer carries extra arrays |
| `gui/jobs.py` (new) | one helper for background work (loading, re-meshing, cell quality) |

## 2.8.6 — part colours, Faces toggle, cleanup

| File | |
|---|---|
| `gui/sidebar.py`, `gui/scene.py`, `gui/section.py`, `gui/part_tree.py` | right-click a part (or a selection) ▸ **Colour…**: the 3D view, the filled cut faces and the list dot follow |
| `gui/window.py`, `gui/scene.py`, `gui/icons.py` | "Edges only" is now **Faces** (on = faces shown, off = edges only), with a shaded-cube icon |
| cleanup | unused code removed (`n_triangles`, `last_edit`, `volume_cells`, `part_items`, pencil icon); tooltips and comments no longer point to the old Display section |

## 2.8.5 — Display moves to the toolbar, Check for Updates

| File | |
|---|---|
| `gui/window.py`, `gui/icons.py` | two new toolbar pills right of the views (left of the units), each button on / off on its own: **Mesh edges · Feature edges · Edges only**, and **Axes · Grid · Bounding box · Origin** (Axes + Grid are still remembered for every window). Also in View ▸ Show. Checked toolbar icons are now white on the accent colour |
| `gui/sidebar.py` | the **Display** section is removed (it's all in the toolbar now) |
| `gui/about_dialog.py` | **Check for Updates…** opens the latest release on GitHub |

## 2.8.4 — Edit like Onshape, Edges only, shading in Appearance

| File | |
|---|---|
| `gui/edit_panel.py` | **redone like Onshape's Transform**: pick Rotate / Mirror / Move by X, Y, Z in a drop-down, fill in its boxes (axis, **any angle**, pivot; or the three distances), press **Apply** (or Return). Below: the list of changes made so far, with Undo \| Reset, then Show original edges |
| `transform.py`, `model.py`, `gui/scene.py` | rotations by any angle (multiples of 90° stay exact); `edit_labels` lists the changes |
| `gui/sidebar.py`, `gui/scene.py` | Display ▸ **Edges only** (under Feature edges): hides the faces, keeps the edges; feature edges stay visible while the view moves even with "hide edges while moving", mesh edges don't; clicking a hidden face still selects its part. Shading switch removed from Display |
| `gui/appearance_dialog.py`, `gui/app.py`, `gui/window.py` | **Shading** is now in Appearance ▸ Model (remembered, every window) |
| `gui/part_tree.py`, `gui/style.py` | **Fix:** renaming a part in dark mode showed the old name through the new one (the rename field is now opaque) |

## 2.8.3 — rename parts, McMaster numbers anywhere in a name, Edit as a table

| File | |
|---|---|
| `gui/part_tree.py`, `gui/sidebar.py` | **Rename** a part (any file type): right-click ▸ Rename…, or select it and press Return; the name is edited in the list. Names already in use are refused. McMaster numbers are now found **anywhere** in a name ("Screw 91251A540", "Bracket_8975K12_2"), not only at the start (sizes like "100x200" and alloys like "6061T6" are ignored) |
| `gui/scene.py` | `rename_part()` — colours, visibility, selection, edits follow; STEP / IGES parts keep their new name when re-meshed |
| `gui/window.py`, `gui/export_dialog.py` | Export writes the new names (STL solids, OBJ groups, VTU part names, UGRID .mapbc); renames count as unsaved changes (dot, question on close, "_edited" file name) |
| `gui/edit_panel.py`, `gui/style.py` | Edit section laid out as a small table: Pivot · rows X / Y / Z with Rotate [−90° \| +90° \| 180°] and Mirror [x → −x] · Move boxes + Move button in the same columns. Move boxes show "X 0" instead of "X 0.000". No line above "Show original edges" |

## 2.8.2 — tidier Edit section, shading switch, .dmg background fixed

| File | |
|---|---|
| `gui/edit_panel.py` | **re-laid out**: one row per action, every button the same shape and width — Pivot [Origin \| Centre] · Rotate X / Y / Z [−90° \| +90° \| 180°] (one click turns) · Mirror [X \| Y \| Z] · Move X / Y / Z boxes + a full-width Move button · "Show original edges" · "Last: …" with Undo \| Reset |
| `gui/widgets.py`, `gui/style.py`, `gui/export_dialog.py`, `gui/screenshot_dialog.py` | drop-down lists are now a button that opens a normal menu (`MenuSelect`): no more huge padding or drawing glitches above / below the list (replaces `roomy_combo`) |
| `gui/sidebar.py` | Display ▸ **Shading** switch (off = flat part colours, no light or shadow); a line under Display links to Appearance; switching the Section **off** now folds it |
| `gui/scene.py`, `gui/section.py` | `set_shading()` — parts and filled cut faces; kept when the mesh is rebuilt |
| `gui/appearance_dialog.py`, `gui/window.py` | Appearance says what it is for ("how things look, saved for every window"; Display = what is shown) and is grouped by what it styles: Window · Background · Axes (label size) · Edges (line thickness, while moving) |
| `make_dmg.sh` | the disk image window (background picture, icon places) is written by **dmgbuild** (installed in the build venv the first time) instead of asking Finder by AppleScript, which failed silently without the "control Finder" permission — the background now shows |

## 2.8.1 — friendlier Edit section, Move, compare with the original

| File | |
|---|---|
| `gui/edit_panel.py` | **redesigned** — always in the sidebar (no Edit button): Rotate (axis + −90° / +90° / 180°) · Mirror X / Y / Z · **Move** by X / Y / Z · turn **about** the origin or the model's centre · **Original** switch · "Last: …" line with **Undo** (one step) and **Reset**, styled like Measure ▸ Clear. STEP / IGES / BREP: a grey note instead of the tools |
| `transform.py` | edits are (R, t); geometry is always recomputed from the file's points, so Undo / Reset are exact and surfaces + volume cells keep identical node coordinates |
| `gui/scene.py`, `gui/section.py` | `apply_edit()`, `undo_edit()`, `reset_edits()`; the camera no longer resets after an edit; `set_show_original()` draws the file's feature edges in grey to compare. **Fix:** moving the volume cells no longer changed the file's copy (shallow-copy bug) |
| `gui/window.py` | Edit button / ⌘E removed; Export stays |
| `gui/widgets.py`, `gui/style.py`, `gui/export_dialog.py`, `gui/screenshot_dialog.py` | `roomy_combo()`: drop-down lists with menu-like spacing and rounded rows, wide enough for their text (Export format, screenshot resolution) |
| `export.py` | shorter format names |

## 2.8 — Edit (rotate / mirror) and Export

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

## 2.7.3 — toolbar tidy-up

| File | |
|---|---|
| `gui/window.py`, `gui/icons.py` | **Parallel projection** is now a toggle button in the view group of the toolbar (Fit · Iso · X · Y · Z · ▢, also View menu, ⌘5), no longer a sidebar switch; new **Edit** button (pencil, ⌘E) as a placeholder for the editing tools of the next version |
| `gui/sidebar.py` | Display rows evenly spaced (the extra gaps between groups are gone); "Origin (0, 0, 0)" is just "Origin" (the coordinates are in its tooltip) |
| `.gitignore` | ignores the `Claude outputs/` folder |

## 2.7.2 — cleaner Display section, steadier section handles

| File | |
|---|---|
| `gui/sidebar.py`, `gui/window.py`, `gui/app.py` | Display ▸ **Axes: Off · Axes · Grid · Both** replaces the Grid switch and Appearance's Grid lines / Axis lines switches (old settings carry over); switches grouped: projection · edges · bounding box & origin |
| `gui/appearance_dialog.py` | three groups: Window · 3D view (background, axis label size) · Edges |
| `gui/section.py`, `gui/section_panel.py` | cut volume mesh: edges black like the model's mesh edges and shown only when Display ▸ Mesh edges is on; the switch is "Fill cut faces" again. Plane handles (sphere, arrow tips) keep the same small size on screen at any zoom; shorter arrow |
| `gui/scene.py` | `set_axes_mode()`; Mesh edges switch also drives the cut mesh; unused `set_grid()` removed |

## 2.7.1

| File | |
|---|---|
| `build_app.sh`, `make_dmg.sh` | heavy files (Python environment, build, app, .dmg) go to `~/Downloads/MeshViewer-build` (or `$MESHVIEWER_WORK`), not the project folder; `.venv` is just a link |
| `.gitignore` | ignores the `.venv` link |

## 2.7

| File | |
|---|---|
| `mesh/volume.py` | **new** — builds one VTK grid from the volume cells |
| `mesh/ugrid.py`, `mesh/cgns.py` | `read_volume()`: tetra / pyramid / prism / hexa cells, read only when needed (CGNS: per-type and MIXED sections; quadratic cells use their corners; polyhedra skipped). **Fix:** CGNS node counts for QUAD_9, HEXA_20, HEXA_27 and quadratic pyramids / prisms |
| `model.py`, `formats.py` | models of mesh files can load their volume cells |
| `gui/section.py`, `gui/section_panel.py` | CGNS / UGRID: the section fills the cut with the volume cells it goes through, with their edges; surface-only files keep the solid fill |
| `gui/scene.py` | cut-mesh colours for light / dark; its edges hide while moving |

## 2.6

| File | |
|---|---|
| `gui/scene.py`, `gui/sidebar.py` | **Origin (0, 0, 0)** switch in Display: a dot with short red / green / blue X / Y / Z arrows, drawn on top so it shows inside parts; also in screenshots |
| `gui/scene.py` | pressing X, Y or Z again without moving the view looks from the opposite side (X → −X → X); Iso stays as is |
| `gui/measure.py` | screenshots include the origin marker |
| `.gitignore` | **new** — keeps `.venv`, `build/`, `dist/`, `.dmg` and `__pycache__` out of git |
| `README.md`, `CHANGELOG.md`, `LICENSE`, `docs/` | **new layout for GitHub**: README with screenshots, features, download and build steps; the version history moved to CHANGELOG.md; MIT licence; screenshots and a release-notes template in `docs/` |

## 2.5.6

| File | |
|---|---|
| `gui/widgets.py` | **fix:** the Section switch shows the hand cursor like the other switches (the section header was forcing an arrow) |
| `gui/scene.py` | **Axis lines** off now hides the numbers and axis titles too (grid lines stay); axis numbers follow the unit chosen in the toolbar (mm / cm / m / in / ft) and titles read "X Axis (mm)"; with ⊘ no unit is shown. Grid building moved into `refresh_grid()` / `_add_grid()` (view and screenshots share it) |
| `gui/measure.py` | changing the unit rebuilds the axis labels |

## 2.5.5

| File | |
|---|---|
| `gui/sidebar.py` | switching **Section** on also opens its controls |
| `gui/appearance_dialog.py` | four groups separated by lines: Window · 3D background · Axes & grid · Edges; new **Axis lines** switch next to Grid lines |
| `gui/scene.py` | axis lines (frame + tick marks) can be hidden — numbers and titles stay; screenshots: only "As Shown" or "Transparent" |
| `gui/screenshot_dialog.py` | Light / Dark / Custom backgrounds removed (As Shown follows Appearance) |
| `gui/measure.py` | distance points are fixed-size dots on screen (13 px) instead of spheres that grew when zooming in; X/Y/Z lines 2.5 px (was 1.5) |
| `gui/app.py`, `gui/window.py` | axis-lines setting saved |

## 2.5.4

| File | |
|---|---|
| `gui/scene.py` | edges also hidden while **zooming** (scroll wheel / trackpad): a burst of zoom steps counts as one movement, edges return 0.3 s after the last step; **grid lines** behind the model can be turned off (the axis frame, ticks and labels stay); in CAD-face measuring, **clicking empty space clears** the selected faces |
| `gui/about_dialog.py` | **new** — About Mesh Viewer: icon, version, credits, Python / Qt / VTK / PyVista / OpenCASCADE / NumPy versions |
| `gui/app.py`, `gui/window.py` | "About Mesh Viewer" (macOS puts it in the app menu, left of File); grid-lines setting saved |
| `gui/appearance_dialog.py` | "Grid lines" switch; "While moving" switch now says rotate, pan, zoom |
| `meshviewer/__init__.py`, `setup.py`, `make_dmg.sh` | the version number lives in one place (`__version__`) |

## 2.5.3 — smoother edges, more Appearance options

| File | |
|---|---|
| `gui/scene.py` | edges are hidden while the view moves on **any** model (was only above 1.5 M triangles) and come back when you let go; feature edge thickness Thin 1 / Medium 1.5 / Thick 2 px (default Thin — one drawing pass on macOS) |
| `gui/appearance_dialog.py` | sheet grouped into **Window** and **3D view**; new: axis label size slider (10–28 pt, 10 = the original size, default 16), Edge lines Thin / Medium / Thick, "While rotating: hide edges" switch |
| `gui/app.py` | saves the new options; old Small / Medium / Large axis setting carries over |
| `gui/icons.py` | Appearance icon is now three sliders (it holds more than light / dark) |
| `gui/style.py` | group titles in the sheet |

## 2.5.2 — smaller app

| File | |
|---|---|
| `slim_bundle.py` | **new** — after a standalone build: removes the Qt parts the app never uses (web engine, QML, 3D, multimedia, Designer and other tools, translations, headers), keeps only this Mac's processor type in universal binaries, de-duplicates framework files, re-signs. PySide6 goes from ~1.2 GB to ~0.15 GB |
| `build_app.sh`, `make_dmg.sh` | run it (also with `make_dmg.sh --reuse`) |
| `mesh_viewer.py` | self-test also opens Qt and a 3D view, so a missing Qt piece is caught before packing |
| `setup.py` | leaves out tkinter / pip / wheel |

## 2.5.1 — fix

| File | |
|---|---|
| `fix_bundle.py` | **new** — the standalone app failed its self-test (`liblzma.5.dylib … unknown imports_format`): py2app corrupts Homebrew libraries when it copies them. This puts back clean copies and relinks them with Apple's `install_name_tool` |
| `build_app.sh` | standalone builds run `fix_bundle.py` and sign every library; signing errors are shown |
| `make_dmg.sh` | `--reuse` re-repairs an existing build (no rebuild) |
| `mesh_viewer.py` | self-test also checks lzma, bz2, zlib, ssl, hashlib, decimal, ctypes (not sqlite3: the app doesn't use it, so py2app leaves it out) |

## 2.5

| File | |
|---|---|
| `make_dmg.sh` | **new** — builds a self-contained app and packs it in `dist/Mesh Viewer <version>.dmg` (drag-to-Applications window with an arrow background) |
| `build_app.sh` | `--no-install` option (build only), used by `make_dmg.sh` |
| `mesh_viewer.py` | `--selftest`: checks a bundled app has every package and can draw (run by `make_dmg.sh` before packing) |
| `resources/dmg_background*.png` | **new** — background of the disk-image window |
| `gui/scene.py` | axis labels bigger: Small 16 / Medium 20 / Large 24 pt (old Large is the new Small); XYZ corner widget a bit larger |

## 2.4.3

| File | |
|---|---|
| `gui/part_tree.py` | right-click no longer selects the row (also ⌃-click on a Mac); the clicked row gets an accent outline while the menu is open, like Finder |
| `gui/sidebar.py`, `gui/scene.py`, `gui/window.py` | "Search in McMaster" uses only the row / part you right-clicked, never the whole selection (Hide / Isolate still act on the selection when you right-click inside it) |
| `gui/scene.py`, `gui/appearance_dialog.py`, `gui/app.py` | **new:** Axis labels Small (default) / Medium / Large in Appearance; also used for screenshots; the XYZ corner widget grows a little with it |

## 2.4.2

| File | |
|---|---|
| `gui/part_tree.py` | **fix:** groups no longer close right after opening (macOS opens/closes tree rows on mouse *release*; our press handler already had, so it toggled twice) |
| `gui/sidebar.py`, `gui/style.py` | "N parts selected · Clear" is always shown (greyed at 0), so selecting no longer shifts the list |
| `gui/scene.py`, `gui/screenshot_dialog.py` | **new:** "Transparent" screenshot background (PNG with alpha; grid/labels drawn dark, for white pages) |
| clean-up | screenshot sheet reuses the shared `ColorField` instead of its own copy; removed an unused `Scene.set_all_visible` and unused imports; old "NEW" markers removed (each version's changes are tagged `NEW (vX)` / `FIX (vX)`) |

## 2.4.1 — fixes

| File | |
|---|---|
| `gui/scene.py` | after a right-click menu, the 3D view no longer stays in "zoom" mode (any lost drag is ended as soon as the mouse moves with no button held) |
| `gui/sidebar.py` | same clean-up when the menu closes |
| `gui/part_tree.py` | **new:** row spacing Compact / Comfortable; group arrow is easier to hit — clicking anywhere left of a group's checkbox opens / closes it without selecting |
| `gui/appearance_dialog.py`, `gui/app.py`, `gui/window.py` | "Parts list" spacing option in Appearance, remembered |
| `gui/style.py`, `gui/widgets.py` | light mode: the system accent is made vivid and dark enough to read (macOS gives Qt a pale version); dark mode unchanged |

## 2.4 — appearance, McMaster, roomier menus

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

## 2.3.2

| File | |
|---|---|
| `gui/scene.py` | no black / very dark part colours; right-click hook (`on_context`) |
| `gui/measure.py` | marker lines no longer tinted by a hidden scalar array (now truly grey / red / green / blue); display units + conversion; 5 significant digits |
| `gui/window.py` | units capsule in the toolbar; right-click menu in the 3D view |
| `gui/sidebar.py`, `gui/part_tree.py` | "N parts selected · Clear" bar; right-click Hide / Isolate / Zoom To (selection-aware) |
| `gui/style.py` | part list: flat full-row selection + own fold-out arrows (no odd shapes) |
| `gui/widgets.py` | closing a section always gives its space back |
| `gui/icons.py` | ⊘ "no units" icon |

## 2.3.1 — fixes

| File | |
|---|---|
| `gui/part_tree.py` | **new** — grouped part list (replaces the flat list) |
| `gui/scene.py` | screenshots render in a separate full-size off-screen window with text and lines scaled (fixes giant axis labels); `isolate` / `zoom_to` take groups |
| `gui/measure.py` | distance line grey, X/Y/Z legs red/green/blue; labels on top; near-zero noise shown as 0 |
| `gui/measure_panel.py` | **rewritten** — result card, no hints, no Copy, units note |
| `gui/sidebar.py`, `gui/window.py` | Measure is a sidebar section (no toolbar button); sections start closed |
| `gui/widgets.py` | sliders / number boxes ignore the scroll wheel; sections can start closed |
| `gui/screenshot_dialog.py` | sheet shrinks back after leaving "Custom" |

## 2.3 — measure, screenshot options, multi-select

| File | |
|---|---|
| `gui/measure.py`, `gui/measure_panel.py`, `gui/screenshot_dialog.py` | **new** |
| `gui/scene.py` | **new:** multi-selection (parts) + CAD face selection, `click()` routes clicks to measuring, `pick_full()` returns the 3D point, `screenshot()` with background choice |
| `gui/sidebar.py` | list allows ⌘/⇧ multi-select; Measure section (shown while measuring) |
| `gui/window.py` | Measure + Screenshot buttons back at the top right; Measure in View menu |
| `cad/occt.py` | triangles remember which CAD face they came from (`face_id`); exact area / volume from OpenCASCADE |
| `model.py`, `formats.py` | model keeps the CAD source and units |

## 2.2 — more CAD formats

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
