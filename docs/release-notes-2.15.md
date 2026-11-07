## What's new in 2.15

- **Simulation results**: open the Tecplot `.dat` that FUN3D writes
  (`project_tec_boundary.dat`, File ▸ Open) and colour the boundaries by any of its
  variables — cp, Mach, pressure, y+, speed… — in the new **Results** section, with
  the scale, your own min / max, and max · mean · min.

## In 2.14.2

- **Internal flow** (pipe or duct): Reynolds number on the hydraulic diameter, developed
  pipe-flow friction, y+ along the pipe from the inlet.
- Cross section of CAD files cut from the exact CAD curves: smooth at any zoom.
- Cleaner flow arrows in the cross section.
- The y+ colours on the walls are gone (the y+ along the flow tab stays).

## In 2.14.1

- The y+ tile shows the **max** on the walls, with min and mean beside it.
- Layer size and y+ plots now look alike, with y-axis titles; the y+ plot always shows
  where the viscous sublayer ends.
- Temperature is greyed out for air at an altitude (standard atmosphere).

## In 2.14

- **Export ▸ CFD settings** (CAD files): the inflation layers for OpenFOAM
  (snappyHexMesh), Fluent Meshing, STAR-CCM+ or Pointwise, or a CSV of every input
  and value.
- **y+ along the flow**: a new tab with the y+ of the first layer from the leading edge.
- **?** next to Target y+: resolve the wall or use wall functions, with the law of the wall.
- **Temperature** input for water (air: from the altitude).
- Cross section: layers **stop where they would cross** (narrow gaps, other parts).
- Every file also remembers its Inflation page, Flip side and zoom.
- **Check for Updates** tells you whether a newer version is out.

## In 2.13.2

- Cross section, simpler: only the inflation layers, a **Flip side** button (layers
  outside the model by default, inside for internal flow) and a **Fit view** button.
  No more lag from smoothing.
- All the computed numbers are in the **Values** pop-up.

## In 2.13.1

- Cross section: choose **external or internal flow**, show or hide each element from
  the legend, and a **flow direction** arrow.

## In 2.13

- **Cross section** tab on the Inflation page: turn on the section plane and it shows
  the cut in 2D, with an estimate of the inflation layers on the walls (scroll to zoom
  in on the wall, drag to pan). Follows the plane as you move it.

## In 2.12.2

- Inflation page: the layer size plot takes the full width under tabs, redrawn to
  match the app (bars per layer, total-thickness line, labelled reference lines, hover).
- Plain names in CFD mode: First layer, Layers, Growth rate, Next cell (× max layer height).

## In 2.12.1

- CFD mode's **Flow** inputs now match the mesh CFD section (fluid, altitude or depth,
  locked properties unless Custom, Mach / speed U, direction).
- Growth rate limited to 1–2; **Desired cell** is a factor of the largest layer.
- Cleaner inflation plot.

## In 2.12

- **CFD mode** (CAD) reworked like the mesh CFD section: folding Flow / Inflation
  layers groups with **Formulas** and **Values**, unit menus, a typed speed U, flow
  direction and arrows.
- **Walls**: give the inflation layers to the whole model, a part, or **faces of one
  part** picked in the 3D view (⇧-click, then Apply). They're tinted in 3D and set
  the auto length L.
- Right-click a surface: **Hide Part** or **Hide Surface**; *Show All* brings them back.

## In 2.11.4

- CFD: a **unit menu** on every input (altitude, density, viscosity, speeds, length).
- Boundary menu with each part's colour; **Back to auto length** after typing L.
- Colour by y+ hides its mesh edges while the view moves, like the model.

## In 2.11.3

- **Colour by y+**: the boundary painted by its y+ at each wall node, relative to
  the target. The max y+ turns green, orange or red.
- **Compressibility correction** for the skin friction (Raymer), in the y+
  estimator and CFD mode — matters above about Mach 0.8.
- Speed U in m/s, km/h, kt, ft/s or mph.
- **Formulas** buttons: every equation used, shown like LaTeX.

## In 2.11.2

- CFD: type the **speed U** or the Mach number, the other follows.
- Density, viscosity and sound speed are locked for air and water (editable with *Custom*).
- y+ card: max with *min · mean* beside it; the mesh's largest first cell next to
  the first cell height for the target y+.

## In 2.11.1

- CFD section: **Flow** and **y+ estimator** fold, and each has a **Values** pop-up
  with every computed number (Re, T, p, ν, q… / Cf, τw, u*, y+ max / mean / min…).
- The big y+ number is the **max** on the boundary, with the min beside it.
- The auto length is the longest distance along the flow (root chord of a swept wing).
- Flow direction: X / Y / Z labels, no more clipped numbers. Info starts closed.

## In 2.11

- **CFD mode** for CAD files: an inflation layer calculator in the sidebar (target
  y+, Mach, length, altitude; first cell, number of layers, growth rate, desired
  cell). Switch it on and a bar under the 3D view opens the **Inflation layers**
  page: Reynolds number, first cell height, estimated y+, boundary-layer thickness
  δ99, total and largest layer, a plot of the layers against δ99 and the desired
  cell, the layer stack drawn to scale, and two checks (covers the boundary layer ·
  smooth transition to the mesh).

## In 2.10

- **CFD** section: y+ estimate on a boundary — air at an altitude (U.S. Standard
  Atmosphere), fresh or sea water at a depth, or your own density / viscosity;
  Mach and flow direction. For volume meshes the first cell layer is measured on
  the mesh; the first cell height for a target y+ is always shown. Flow arrows.
- **Info** is the first section and easier to read.
- Measure ▸ **Point** is measured from the origin, like a distance.
- The section normal keeps the numbers you type.

## In 2.9

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

1. Download **Mesh Viewer 2.15.dmg** below.
2. Open it and drag **Mesh Viewer** onto **Applications**.
3. **First launch:** the app isn't notarized by Apple, so macOS blocks it the first
   time. Try to open it once, then go to **System Settings → Privacy & Security**
   and click **Open Anyway**. Only needed once.

Requires a Mac with Apple Silicon and macOS 13 or later. Intel Macs: build from
source (see the README).
