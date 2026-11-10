## What's new in 2.5 beta 3

- **Tools on the right**: the tools moved to an inspector right of the 3D view, in
  three tabs — **View** (Mesh Quality, Section, Edit), **Measure** (Info, Measure,
  Plots) and **Analyze** (CFD, Cell Quality, Results). ⌥⌘I shows or hides it, ⌥⌘1–3
  pick a tab. Measure measures while its tab is shown.
- **Parts on the left**: the sidebar is the parts list, the whole height of the window.
- **A lighter toolbar**: views, **Show ▾**, the **unit ▾**, Export, Screenshot.
  View ▸ **Customize Toolbar…** (or right-click the toolbar) picks what it shows.
- **Fixed**: toolbar icons sometimes missing on the welcome screen.
- **Fixed**: Settings and About no longer slide a full-screen window away.

## In 2.5 beta 2

- **Fixed**: *Check for Updates…* was twice in the app menu, and Settings was called
  Preferences.
- **Fixed**: Settings and About no longer slide a full-screen window away.
- **Welcome screen**: an empty window offers Open…, your recent files and two samples
  to try — the ONERA M6 wing (CGNS) and an avionics bay (STEP).
- **File ▸ Revert to Original…** opens a file as the first time, after asking.
- A small **spinner** in the toolbar while a file opens or is re-meshed; **errors** say
  what to do next and offer **Report a Problem…** (also in the Help menu).
- Save panels, Rename and Color… **slide down from the window** as sheets.
- **VoiceOver** names every button and switch; **Increase contrast** is followed.

## In 2.5 beta 1

A first beta of 2.5: the app organized the way Mac apps are.

- **Full menu bar**: Edit (Undo, Redo, Select All, Find…), Window, and Help with a
  list of every keyboard shortcut. Everything in the toolbar is also in a menu.
- **Undo anything** with ⌘Z: hiding and showing parts, colors, renames, hidden faces,
  rotations and moves. ⇧⌘Z redoes.
- **Settings… (⌘,)** replaces Appearance…: General, Appearance and Units tabs. New:
  the mesh quality CAD files open at, the unit new files are shown in, and the unit
  assumed for files that don't say theirs.
- **Clearer names**: plots are *plots* (New Plot…), CFD mode is *Inflation Layers*,
  *Hide Face* on CAD parts, American spelling everywhere.
- The window title says **Edited** while rotations or moves aren't exported yet.
- The sidebar's shortcut is now ⌃⌘S, as in other Mac apps.

This is a beta: tell me what feels off.

## In 2.4.11

- **Faster STEP / IGES / BREP meshing, fewer triangles**: OpenCASCADE's own triangles
  again (the even meshes of 2.4.10 are gone). Changing the Mesh quality is near
  instant on most files.

## In 2.4.10

- **No more hole in the model** when zoomed in close and turning (parallel view).
- **Axis numbers** are the same size on every axis and keep their size when zooming.

## In 2.4.9

Faster and smoother — nothing new to learn.

- **Turning and zooming**: each frame is drawn once (it was drawn twice).
- **Assemblies**: a part used many times is meshed once — opening and changing the mesh
  quality are several times faster; *Select All* is instant (it took seconds).
- **Everyday clicks** — hide, show, isolate, a unit change, moving a cross section —
  draw one frame instead of several.

## In 2.4.8

- Many plots: the tabs under the view scroll sideways.
- Right-click a plot's tab to open, rename or delete it.

## In 2.4.7

- **Results ▸ Values in / Shown in**: units for pressure, density, velocity,
  temperature… — the scale, Min / Max and the plots follow.
- **Plots**: an eye shows or hides each cut in 3D; the gear opens the plane's origin and
  normal (any direction). Section has the same gear.
- Smaller text boxes and menus; a line above the analysis tools in the icon bar.

## In 2.4.6

- Every sidebar section sits on a card; Section and Plots cross sections are laid out
  the same way (Plane · Position · …).
- Plots: *Normalize* (x/c), and the Along buttons light up properly.
- New icons for Results and Plots.

## In 2.4.5

- Fixed a crash when moving a cross section quickly.
- Tidier measurement controls: Cut · Plot · Points, with Rename and Delete under them.
- *Highlight sharp changes* is gone; *Show ▸ Gradient* stays.

## In 2.4.4

- **Plots**: *New Measurement…* adds a named plot with its own tab under the 3D view.
  First kind: the **cross section** — cut the boundaries with a plane and plot cp, Mach…
  or the shape along the cut (x/c, negative up), with reference points from a CSV and
  export to CSV.
- **Results ▸ Show ▸ Gradient**: colour by how fast the field changes (|∇f|) — shocks
  and leading edges stand out.

## In 2.4.3

- **Gmsh and Fluent `.msh` files**, 2D or 3D (found from the file): the boundaries,
  and for 3D the volume cells (section cut, cell quality, y+).
- **DXF drawings**: shown flat, one part per layer, and measurable.
- Four kinds of file — 3D mesh, 3D CAD, 2D mesh, drawing — each opens with the
  sections that fit; the others say why they don't.
- **Results ▸ Colours**: pick the colour map by its colours (rainbow by default). The
  auto range follows the boundaries you show.
- 2D files are always seen from above: drag to pan, nothing turns.
- DXF drawings: white lines on black in dark mode, black lines in light mode.
- ✎ next to the units changes the file's unit.
- Measure ▸ Distance: two points by default; *From origin* gives one point's
  coordinates and distance from (0, 0, 0). Angle works on 2D lines.
- 2D meshes: the list is split into Faces and Boundaries.
- A narrow sidebar gets a horizontal scrollbar.

## In 2.4.2

- **File unit**: the first time you open a file, pick the unit its numbers are in
  (STEP / IGES preselect theirs). Change it any time in Info.
- **Distance** does both: one click gives the point (X / Y / Z, from the origin),
  a second click the distance between the two.
- Formulas open next to the sidebar; the y+ formula links to CFD Online.
- Hover *Next cell* in CFD mode for what it means.
- "y+ along the flow" is gone; the y+ tile shows the estimate.

## In 2.4.1

- **New sidebar**: an icon bar on the left shows or hides each section. Every file
  remembers its sections; the + under the icons chooses which analysis tools
  have an icon.
- New icons: Apple's SF Symbols, drawn by macOS.
- CGNS meshes with MIXED sections (like the ONERA M6 mesh) or polyhedra (NGON / NFACE):
  cut cells, y+ and cell quality work.
- STEP / IGES / BREP: no more fans of thin triangles on flat or gently curved faces.
- The projection button is now Perspective (on / off).
- Fixes: sidebar scrollbar when everything fits, selection hidden under Results
  colours, Export save panel leaving full screen, Results shown for STEP files.

## In 2.4

- **Simulation results**: open the Tecplot `.dat` that FUN3D writes
  (`project_tec_boundary.dat`, File ▸ Open) and colour the boundaries by any of its
  variables — cp, Mach, pressure, y+, speed… — in the new **Results** section, with
  the scale, your own min / max, and max · mean · min.

## In 2.3.15

- **Internal flow** (pipe or duct): Reynolds number on the hydraulic diameter, developed
  pipe-flow friction, y+ along the pipe from the inlet.
- Cross section of CAD files cut from the exact CAD curves: smooth at any zoom.
- Cleaner flow arrows in the cross section.
- The y+ colours on the walls are gone (the y+ along the flow tab stays).

## In 2.3.14

- The y+ tile shows the **max** on the walls, with min and mean beside it.
- Layer size and y+ plots now look alike, with y-axis titles; the y+ plot always shows
  where the viscous sublayer ends.
- Temperature is greyed out for air at an altitude (standard atmosphere).

## In 2.3.13

- **Export ▸ CFD settings** (CAD files): the inflation layers for OpenFOAM
  (snappyHexMesh), Fluent Meshing, STAR-CCM+ or Pointwise, or a CSV of every input
  and value.
- **y+ along the flow**: a new tab with the y+ of the first layer from the leading edge.
- **?** next to Target y+: resolve the wall or use wall functions, with the law of the wall.
- **Temperature** input for water (air: from the altitude).
- Cross section: layers **stop where they would cross** (narrow gaps, other parts).
- Every file also remembers its Inflation page, Flip side and zoom.
- **Check for Updates** tells you whether a newer version is out.

## In 2.3.12

- Cross section, simpler: only the inflation layers, a **Flip side** button (layers
  outside the model by default, inside for internal flow) and a **Fit view** button.
  No more lag from smoothing.
- All the computed numbers are in the **Values** pop-up.

## In 2.3.11

- Cross section: choose **external or internal flow**, show or hide each element from
  the legend, and a **flow direction** arrow.

## In 2.3.10

- **Cross section** tab on the Inflation page: turn on the section plane and it shows
  the cut in 2D, with an estimate of the inflation layers on the walls (scroll to zoom
  in on the wall, drag to pan). Follows the plane as you move it.

## In 2.3.9

- Inflation page: the layer size plot takes the full width under tabs, redrawn to
  match the app (bars per layer, total-thickness line, labelled reference lines, hover).
- Plain names in CFD mode: First layer, Layers, Growth rate, Next cell (× max layer height).

## In 2.3.8

- CFD mode's **Flow** inputs now match the mesh CFD section (fluid, altitude or depth,
  locked properties unless Custom, Mach / speed U, direction).
- Growth rate limited to 1–2; **Desired cell** is a factor of the largest layer.
- Cleaner inflation plot.

## In 2.3.7

- **CFD mode** (CAD) reworked like the mesh CFD section: folding Flow / Inflation
  layers groups with **Formulas** and **Values**, unit menus, a typed speed U, flow
  direction and arrows.
- **Walls**: give the inflation layers to the whole model, a part, or **faces of one
  part** picked in the 3D view (⇧-click, then Apply). They're tinted in 3D and set
  the auto length L.
- Right-click a surface: **Hide Part** or **Hide Surface**; *Show All* brings them back.

## In 2.3.6

- CFD: a **unit menu** on every input (altitude, density, viscosity, speeds, length).
- Boundary menu with each part's colour; **Back to auto length** after typing L.
- Colour by y+ hides its mesh edges while the view moves, like the model.

## In 2.3.5

- **Colour by y+**: the boundary painted by its y+ at each wall node, relative to
  the target. The max y+ turns green, orange or red.
- **Compressibility correction** for the skin friction (Raymer), in the y+
  estimator and CFD mode — matters above about Mach 0.8.
- Speed U in m/s, km/h, kt, ft/s or mph.
- **Formulas** buttons: every equation used, shown like LaTeX.

## In 2.3.4

- CFD: type the **speed U** or the Mach number, the other follows.
- Density, viscosity and sound speed are locked for air and water (editable with *Custom*).
- y+ card: max with *min · mean* beside it; the mesh's largest first cell next to
  the first cell height for the target y+.

## In 2.3.3

- CFD section: **Flow** and **y+ estimator** fold, and each has a **Values** pop-up
  with every computed number (Re, T, p, ν, q… / Cf, τw, u*, y+ max / mean / min…).
- The big y+ number is the **max** on the boundary, with the min beside it.
- The auto length is the longest distance along the flow (root chord of a swept wing).
- Flow direction: X / Y / Z labels, no more clipped numbers. Info starts closed.

## In 2.3.2

- **CFD mode** for CAD files: an inflation layer calculator in the sidebar (target
  y+, Mach, length, altitude; first cell, number of layers, growth rate, desired
  cell). Switch it on and a bar under the 3D view opens the **Inflation layers**
  page: Reynolds number, first cell height, estimated y+, boundary-layer thickness
  δ99, total and largest layer, a plot of the layers against δ99 and the desired
  cell, the layer stack drawn to scale, and two checks (covers the boundary layer ·
  smooth transition to the mesh).

## In 2.3.1

- **CFD** section: y+ estimate on a boundary — air at an altitude (U.S. Standard
  Atmosphere), fresh or sea water at a depth, or your own density / viscosity;
  Mach and flow direction. For volume meshes the first cell layer is measured on
  the mesh; the first cell height for a target y+ is always shown. Flow arrows.
- **Info** is the first section and easier to read.
- Measure ▸ **Point** is measured from the origin, like a distance.
- The section normal keeps the numbers you type.

## In 2.3

- **Cell quality** for meshes: skewness, aspect ratio, scaled Jacobian and volume
  of every cell as a histogram. Set the "bad" threshold, zoom to the bad cells,
  show them in red, colour the section cut by quality, spot inverted cells.
- **Info** section: size, bounds, faces, points, edge lengths, volume cells.
- Measure ▸ **Point** (coordinates, distance to the section plane) and **Angle**.
- **File ▸ Open Recent**, and every file reopens the way you left it.
- OBJ and PLY exports keep the part colours.
- CGNS prisms (and other cells stored in the opposite node order) now have the
  right orientation.

## Since 2.7.1

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

1. Download **Mesh Viewer 2.17.dmg** below.
2. Open it and drag **Mesh Viewer** onto **Applications**.
3. **First launch:** the app isn't notarized by Apple, so macOS blocks it the first
   time. Try to open it once, then go to **System Settings → Privacy & Security**
   and click **Open Anyway**. Only needed once.

Requires a Mac with Apple Silicon and macOS 13 or later. Intel Macs: build from
source (see the README).
