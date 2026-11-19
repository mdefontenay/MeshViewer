# Lessons Learned

What building Mesh Viewer in Python (PySide6 · VTK · OpenCASCADE) taught: the bugs
that will come back in any rebuild, and the ways of tackling a feature that worked.
It is written to be read without the Python code. Each entry says what went wrong,
why, and what fixed it. A *Swift:* note says how it maps onto a native Swift / Metal
app, where that isn't obvious.

**Keep it up to date.** Every bug fix or optimization, in either app, adds an entry
here or updates one, in the section it belongs to: what happened, the cause, the fix,
and the numbers for a speed change. Plain words, no code paths needed. Tag new entries
with the app and version, e.g. *(Swift 3.0b2)*.

1. [Reading files](#1-reading-files)
2. [Fields and units](#2-fields-and-units)
3. [CAD: STEP, IGES, BREP](#3-cad-step-iges-brep)
4. [Drawing the 3D view](#4-drawing-the-3d-view)
5. [Camera and navigation](#5-camera-and-navigation)
6. [Picking and selection](#6-picking-and-selection)
7. [Feature edges and faces](#7-feature-edges-and-faces)
8. [Section plane and cuts](#8-section-plane-and-cuts)
9. [Contours and color scales](#9-contours-and-color-scales)
10. [Time steps](#10-time-steps)
11. [Inflation Layers and CFD numbers](#11-inflation-layers-and-cfd-numbers)
12. [Plots, probes and numbers on screen](#12-plots-probes-and-numbers-on-screen)
13. [Undo and per-file memory](#13-undo-and-per-file-memory)
14. [macOS behavior](#14-macos-behavior)
15. [Speed: rules that held](#15-speed-rules-that-held)
16. [The project itself](#16-the-project-itself)

---

## 1. Reading files

- **CGNS: broken element offsets.** Some exporters (the ONERA M6 mesh is one) write
  MIXED sections whose `ElementStartOffset` is junk: the element type repeated.
  Trusting it gave no volume cells at all, so no cut cells, no y+, and cell quality
  only on the surface. Fix: check the offsets. They start at 0, keep increasing, end
  at the connectivity's length, and each step matches its element type's node count.
  If any of that fails, rebuild them by walking the connectivity: read a type code,
  skip its node count, repeat. That takes a fraction of a second for 10 M cells.
- **CGNS: node counts per element type.** Quadratic types (QUAD_9, HEXA_20, HEXA_27,
  the quadratic pyramids and prisms) were read with the wrong node count, which
  shifted every element after them. Keep one table of node counts per CGNS type, and
  draw only the corner nodes.
- **CGNS: polyhedra.** Meshes stored as NGON_n / NFACE_n had no volume cells until
  their faces were assembled into cells. Recognize the tetra, pyramids, prisms and
  hexa among them. Keep the wall normals pointing the same way, or first-cell heights
  come out wrong.
- **Cells inside out.** Formats disagree on node order (CGNS prisms against VTK's
  convention). A cell read in the other order has a negative volume and terrible
  quality. Fix: per cell type, if most cells of that type are inside out, flip that
  type's order. A mirror (the Edit tool) must also fix node order, and flip face
  winding so normals stay outward.
- **Float32 files.** A file written in float32 has rounding near 1e-7 (relative).
  Geometry tests with fixed tiny tolerances, like "these points are on a line" or "in
  a plane", failed on it. Scale tolerances to the file's precision.
- **Tecplot ASCII.** Handle FEBLOCK and POINT packing, triangles and quads, and
  cell-centered variables. A boundary written several times (time steps) keeps the
  last one. Zone titles like "boundary 1 WING" become the part "WING". Binary
  `.plt` / `.szplt` were never read: say so clearly.
- **Fluent and Gmsh `.msh`.** Find 2D or 3D from the file itself. Fluent mixes text
  and binary sections in one file. Gmsh's physical groups are the parts.
- **UGRID.** Four byte-order and precision variants, told apart by the extension
  (`.lb8` `.b8` `.lb4` `.b4`). Boundary names come from the `.mapbc` beside it.
- **OpenFOAM: what the user picks.** It may be the case folder, `constant/`,
  `polyMesh/`, a `.foam` file, or a decomposed case (`processor*`). Find the mesh from
  any of these and never write into the user's folder (the Python app read through a
  temporary case made of links). Leave processor patches out. Give clear errors for
  "no constant/polyMesh" and for a missing mesh file.
- **OpenFOAM: 2D cases.** A case one cell thick between `empty` patches is 2D. Take
  the cells on one plane, the other patches as lines, and turn it flat into XY. Each
  face gets its cell's values through the owner list. Detect this automatically.
- **OpenFOAM: polyhedra.** Split them into pyramids and tetra to the cell center,
  carrying the cell's values to every piece, for every time step, not just the first.
- **Only floats are fields.** An internal integer id array showed up as a "result" on
  STEP files. Only floating-point arrays count as solution fields.
- **DXF: layers in blocks.** Inside a block, entities on layer 0 take the layer of
  the block reference (DXF's rule). Dimension lines sat on layer 0 until this was
  applied. Leave the `Defpoints` layer out.
- **DXF: entities.** SOLID corners are in 0-1-3-2 order, and entities can have their
  own coordinate system (OCS). Explode MTEXT into lines of text. Dimensions saved
  without their block must be generated. Draw text as glyph outlines. *Swift:* Core
  Text gives glyph paths directly.
- **DXF: fonts.** A style's font that isn't installed was swapped for the closest
  name: Noto Sans became Noto Sans Oriya, which has no Latin letters, so every letter
  was a box. Check that the font covers the text's characters, else fall back (Arial
  Unicode, Helvetica…). Decode MTEXT's `\U+XXXX` escapes (a minus sign in a stacked
  tolerance) before splitting the text.
- **Units.** STEP and IGES state theirs, DXF may (`$INSUNITS`), and most mesh formats
  don't. The first time a file opens, ask once with a sensible default (meshes in m,
  triangle CAD in mm), remember the answer, and let it be changed later. Keep model
  units inside the app; convert only for display and for CFD maths (SI).

## 2. Fields and units

- **One catalog of known fields**: title, group in the menus, physical quantity (or
  none), matched by the names solvers write. Some names must match exactly: `Ux` is
  a velocity component, and `Q` is the Q-criterion, not the heat flux `q`. Unknown
  fields stay usable, with any unit.
- **Vectors** are split into components plus magnitude. Speed comes from u, v, w or
  Ux, Uy, Uz.
- **Tensor order.** OpenFOAM writes symmetric tensors as xx, xy, xz, yy, yz, zz; VTK's
  reader reorders them to xx, yy, zz, xy, yz, xz. A mix-up silently swaps
  components. Know which order your reader gives.
- **2D files** hide out-of-plane components: z of vectors and tensors, Position Z.
- **Dead fields.** Leave out of the menus any field that is on no face (a 2D case's
  `phi` lives only on the boundary lines) or that has one value over all faces at
  every step.
- **OpenFOAM units** come from each field's dimensions. Incompressible solvers write
  kinematic pressure (p/ρ, in m²/s²): treat it as that, not as Pa.
- **One unit table.** Every unit name and factor lives in one place. A "Custom…" unit
  typed for one file stays with that file only.

## 3. CAD: STEP, IGES, BREP

- **Use OpenCASCADE's own triangles.** Re-meshing every face for even triangles gave
  nicer meshes, but 2 to 4 times the triangles and the time, for display only. It was
  removed: a 300-part assembly went from 3.3 s to 0.1 s. OpenCASCADE's faster
  triangulator (Delabella) is 1.5 to 2.5 times quicker. Thin triangles and fans on
  some faces are the accepted cost.
- **Mesh repeated parts once.** A bolt used 40 times: mesh it once and place copies
  by their transforms. Opening the assembly went from 10.5 s to 2.7 s, and a quality
  change from 8.5 s to 1.1 s. *Swift:* instanced drawing.
- **Exact areas and volumes** come from the CAD, computed once per shape, not at
  every refresh of a list (unit changes got 5 to 7 times faster).
- **Each triangle remembers its CAD face** (a face id). Picking a face, Hide Face,
  feature edges as face borders and exact face measurements all need it.
- **Assemblies, colors, materials.** Keep each part's path of assemblies. Its color is
  the instance's, else the part's, else its faces' most common. Read materials only
  when the file has them (the Python binding crashed on a material lookup: be
  defensive). Show the file's colors, and save only colors the user chose, so the
  file's colors win otherwise.
- **IGES naming.** Bodies inside an unnamed compound become separate parts, bare
  unnamed surfaces are grouped ("Surfaces"), and type names like "FACE" or "SHELL" are
  not part names.
- **Section of CAD.** While the plane moves, cut the triangles. Once it stops, cut the
  exact CAD curves, which stay smooth at any zoom.

## 4. Drawing the 3D view

- **Draw once per change.** The view drew every frame twice, and many changes each
  asked for a frame: a unit change drew 5 frames, and Select All on 300 parts drew
  300. Fix: mark the view dirty and draw once when the event is handled. Turning got
  about 1.8 times faster, and clicks became instant. *Swift:* draw on demand (a paused
  MTKView that is told when to draw), never in a constant loop.
- **One draw for all parts.** One object per part was slow. Draw all parts in one
  batch, with a per-part table of color and visibility, and the selection outline as
  one object too (Select All went from 20 s to 0.2 s). Hiding or recoloring updates
  the table and never rebuilds geometry.
- **Normals once.** They were computed twice when a file opened.
- **Hide mesh edges while moving**, on every model, and bring them back 0.3 s after
  the last motion. A burst of zoom steps counts as one motion. Feature edges stay.
  Thin lines (1 px) by default.
- **Sizes on screen stay on screen.** Section handles, measured points (13 px dots)
  and axis numbers are sized in screen points, not in model units, or they grow and
  shrink with the zoom. Axis numbers sized by their distance to the camera came out a
  different size on each axis. Short axes get fewer numbers (2 to 5) so they don't
  run into each other.
- **Retina.** The color bar's title came out twice too big the first time, because
  the screen's scale was only known after the first frame. Work in points, and know
  the backing scale before the first draw.
- **Who owns the memory.** Two bugs came from shared memory:
  - Surfaces built from views into another array crashed when that memory was freed
    (moving a section fast).
  - Highlight colors written into a shallow copy never reached the screen, and an
    edit changed the file's original copy.

  *Swift:* with buffers shared between CPU and GPU (no copy), decide who owns each
  buffer, keep it alive while the GPU uses it, and copy on purpose when the original
  must stay untouched.
- **One render path for the view and exports.** Save Screenshot left out the contour
  colors and the color bar, because they were drawn separately. Render screenshots off
  screen at full size, with text and line widths scaled; otherwise the labels came
  out giant.
- **Selected over colored.** A selected boundary under contour colors was invisible.
  Draw it lighter, with its outline on top.
- **Part colors.** No black or very dark colors in the palette.
- **Background picture**: center-crop it (no stretching), and pick the grid and text
  color from its brightness.
- **SVG export.** Project the facets through the camera, sort them back to front
  (painter's algorithm), and split facets where a contour's value changes so the
  gradient shows. GL2PS lost the colors drawn through a texture.

## 5. Camera and navigation

- **Parallel camera clipping.** Zoomed in and turned in parallel view, the camera
  ended up inside the model and everything behind it vanished. Fix: keep a parallel
  camera far behind the whole model, and set the near and far planes from the model's
  bounds before each frame. Switching to perspective keeps the size on screen.
- **Zoom toward the pointer.** The point under the pointer stays put:
  - trackpad scroll is continuous, `exp(pixels × 0.004)` per event, with its glide
  - pinch is `exp(magnification)`
  - a mouse wheel notch is ×1.2, eased over a few frames
  - parallel view changes the scale and slides; perspective moves along the
    pointer's ray
  - limits: 1e-5 to 1000 model diagonals
- **2D files are locked to +Z.** Dragging pans, nothing turns, and the view is always
  parallel. It is squared to Z after every move and when a saved view comes back. Edit
  turns 2D files about Z only.
- **X, Y or Z pressed again** looks from the opposite side.
- **Mouse-up lost after a context menu** left the view stuck in zoom mode. End any
  drag as soon as the mouse moves with no button down.
- **Comparing cameras** (for undo): in parallel view, ignore where the camera stands
  along its line of sight.

## 6. Picking and selection

- **GPU picking** (an ID buffer) ignores hidden parts and respects the section cut.
- **2D picking by distance on screen.** Hitting a 1-pixel line is hopeless. Project
  the points and lines to the screen and take the nearest within 10 points; a node
  within 7 points beats the line through it; otherwise take the cell under the click.
  On 2D files, measuring takes any point inside the axes (on z = 0).
- **Volume cells**: take the cell just behind the clicked surface, found with a
  spatial index built once.
- **Right-click** doesn't select the row (as in Finder). Outline the clicked row.
  Actions apply to the selection when the click is inside it, else to the clicked item
  only. A click on empty space clears the selection.
- **The selection count is always shown** (grayed at 0), so the list doesn't jump.

## 7. Feature edges and faces

The hardest part to get right on meshes; budget time for it.

- **CAD: feature edges are face borders**, as CAD programs draw them, not where
  triangles bend over 30° (which missed tangent edges and drew tessellation noise). A
  border goes when no face beside it is shown.
- **Meshes: sharp edges** bend over 30°, with hysteresis: a line carries on across
  mesh edges bending half that when they go straight on, so a trailing edge
  wavering around 30° stays one line. Drop the noise: crease bits under 15 mesh edges
  that end in the open, and pieces under 3 edges between two junctions.
- **Meshes: smooth edges** (a cylinder meeting a sphere) are 3 or more mesh edges in
  a row, aligned or in one plane (precision-aware tolerance), where the surface
  creases or bends differently on each side.
  - A smooth edge must be anchored: it ends on another feature edge or closes on
    itself.
  - Drop floating ones, the lattices of rows that line up by chance (a lofted wing
    meshed along its sections), and zig-zags that turn back and forth.
  - Not on regular grids: if more than 10% of mesh edges qualify, it's the grid, not
    a feature.
- **Bridge gaps.** Where two feature edges stop facing each other along a line or in
  a plane, join them through up to 8 mesh edges turning less than 30°, always the same
  way round. The M6 tip curves then reach the leading edge, and the wing is 3 faces
  instead of one face leaking through the gaps.
- **Cut only at corners**, meaning a turn over the feature angle, or a kink of 25° or
  more at least twice the turns either side, and where other feature edges meet. A
  helix stays one edge.
- **Feature faces** are the CAD faces, or on a mesh the cells joined across edges
  bending less than 30°, split along the feature edges. Make it vectorized or parallel
  (a 270,000-triangle box in 0.25 s), per part, when first needed.
- **The selection outline** follows the feature edges plus the silhouette, not every
  bend.

## 8. Section plane and cuts

- **Cut only what it touches**: parts whose bounding box touches the plane.
- **Merge points exactly** before filling the cut. A tolerance-based merge was the
  big slowdown.
- **Nudge the cut** 1e-6 off the plane to avoid degenerate cuts through vertices.
- **Clip at once, fill a moment later.** The view clips instantly; the cut faces fill
  in about 0.15 s later.
- **Draw the plane as its own object**, always visible. A drag widget only drew it
  while dragging.
- **Volume meshes**: fill the cut with the cells it crosses, their edges following
  Show ▸ Mesh Edges. On a new time step, recolor those cells; don't re-cut the mesh.
- **Guard degenerate ranges.** A plot plane along a flat boundary gave a slider range
  about 1e-18 wide, which overflowed while the file opened. Clamp every range.

## 9. Contours and color scales

- **Interpolate the position, not the color.** Map each value to its place on the
  scale (0 to 1), interpolate that across triangles, then look up the color per pixel
  (a texture). Banded scales keep sharp borders this way; per-vertex colors smear.
- **Log scale.** The minimum is the smallest value above zero, values at or below
  zero take the lowest color, and the middle is the geometric mean. On a log scale,
  ticks go at round values (1, 2, 5 × 10ⁿ): evenly spaced in log10, they looked
  identical to linear.
- **Ticks.** Give the exact count asked, always label both ends, and drop a label
  that would collide while keeping its tick. Write 1000, not 1e+03.
- **Auto range** comes from the visible parts only, and follows hide and show.
- **Long thin triangles smear interpolated colors** (y+ on CAD tessellations).
  Subdivide them, or color per face.
- **Lighter selected parts** come from the same color table.

## 10. Time steps

- **Swap the values, never rebuild.** A step from memory went from 32 to 17 ms.
- **Read only what's shown.** Cache per (step, field) in float32. Read the next steps
  ahead in a cancellable background task; a newer request cancels the older one. Stop
  reading before the window closes.
- **Sample to judge.** Tell constant fields from varying ones by about 24 steps spread
  over the case, not all of them. On a 601-step LES case, the field list and a probe
  went from 34 to 6.1 s, and memory from 1,068 to 269 MB.
- **Ask for the next frame only once the last one is shown**, so nothing piles up
  during playback.
- **One notification for a new step.** Everything showing the data (plots, probes,
  Measure Selected, the cut) follows the step through it.
- **Hidden things wait.** Folded or hidden cards update when shown, not on every step.

## 11. Inflation Layers and CFD numbers

- **Formulas** that worked and were checked:
  - flat-plate Cf = (2 log10 Re − 0.65)^−2.3, τw = Cf ½ρU², u* = √(τw/ρ), first cell
    y = y+ μ / (ρ u*)
  - total thickness = Σ y₁ Gⁿ
  - δ99 = 0.38 L / Re^0.2 (turbulent) or 4.91 L / √Re (laminar), divided by
    (1 + 0.2 M²)^(1/9) above Mach 1
  - compressibility correction: Cf × (1 + 0.144 M²)^−0.65 (Raymer)
  - internal flow: Re on the hydraulic diameter 2ab / (a + b), Cf = 16 / Re below
    2300, Petukhov above
- **Fluids.** Air follows the U.S. Standard Atmosphere 1976; a typed temperature keeps
  the altitude's pressure. Water uses Thiesen (density), Vogel (viscosity) and Marczak
  (speed of sound; Mackenzie for sea water).
- **Auto length L** is the longest distance along the flow across the walls (a swept
  wing gives its root chord), not the bounding box.
- **First cell height** measured on a volume mesh needs consistent wall normals. A
  surface-only mesh must not crash it.
- **Sizing limits.** Keep the growth rate between 1 and 2. The next cell is about 2
  times the largest layer.
- **Thickness shell in 3D.**
  - Move each point along its angle-weighted normal, far enough that every face at
    it moves out by the thickness (least squares), capped at twice the thickness.
    Without the cap, the trailing edge and the tip grew spikes.
  - Choose the side where the shell folds over itself least; Flip takes the other.
- **Speed U and Mach are linked**: type either one. Properties are locked for air and
  water, editable for Custom.

## 12. Plots, probes and numbers on screen

- **Derived state follows its inputs.** Flip Y did nothing until the next cut, because
  the page read a value computed at the last cut.
- **Wait for the slider to rest** (about 40 ms) before recomputing, instead of on
  every pixel.
- **Hover follows the line**, interpolating between points.
- **Show what was typed.** A typed normal stays as typed (not normalized).
- **Guard the edge cases.** A histogram where every value is equal divided by zero.
- **Number formatting.** Strip trailing zeros only after a decimal point ("10" once
  showed as "1"). Use fixed-width readouts with tabular digits so they don't jitter.
- **The current step on a time plot** is a dashed line with a "t = …" tag. A solid
  line in the curve's color looked like data.
- **Probes**: find the cells once with a spatial index, then do array lookups per step
  (about 4 ms a step).
- **McMaster part numbers** are found anywhere in a name, but not sizes (100x200) or
  alloys (6061T6).

## 13. Undo and per-file memory

- **Everything the user may want back is an undo step**: visibility, colors, renames,
  edits, the selection, the camera.
  - Record a change once it's done; record nothing while redoing.
  - Don't record a command's side effects separately (a hidden part dropping out of
    the selection).
  - Start recording only once the file has opened, so restoring it isn't undoable.
- **Camera undo**: merge moves of the same kind with no pause over 0.8 s. Never split
  one drag or zoom burst. A move that ends where it started records nothing.
- **Edits** are stored as a rotation plus a translation and always recomputed from the
  file's points, so Undo and Reset are exact. Multiples of 90° stay exact.
- **Renames** refuse names already in use. Keep a map back to the original names, so
  memory and re-meshing survive. Export writes the new names.
- **Per-file memory** is keyed by original names. Migrate old saved keys instead of
  dropping them. Revert to Original forgets everything about the file.
- **Tests used the real settings once** and erased what the app remembered. Give tests
  their own store. *Swift:* a separate UserDefaults suite.

## 14. macOS behavior

- **Full screen.** Settings and About opened on the desktop and slid a full-screen
  window away. In Python this was fixed by making them a window of the front window,
  joining the active Space (full-screen auxiliary, move to active Space). *Swift:*
  check the Settings window and every panel over a full-screen window early.
- **Save and open panels** opened as separate windows in full screen. Attach them to
  the window as sheets.
- **App menu items** are made once (Check for Updates… appeared twice). It's called
  "Settings…", not "Preferences…".
- **Scrolling a sidebar** must not change the slider or number box under the pointer.
- **Grayed icons came out blank** when an SF Symbol was tinted with a see-through
  color (fixed by drawing it solid, then fading). *Swift:* `Image(systemName:)` handles
  this; check custom-drawn icons.
- **Hide Toolbar** isn't remembered, as in other Mac apps.
- **VoiceOver** needs a name for every icon-only button and switch.
- **Distribution.** Without notarization, Gatekeeper blocks the first launch. A DMG
  window laid out by asking Finder through AppleScript failed silently without the
  "control Finder" permission; it is now written directly (dmgbuild).

## 15. Speed: rules that held

- **Measure before and after** a change, on the same big files, with a bench tool.
- **Load heavy libraries lazily.** Importing all of VTK cost 1.4 s at launch. Load the
  CAD kernel only when a CAD file opens.
- **Don't parallelize tiny work.** Threads cost about 1 ms a job, so 300 small parts
  were slower in parallel.
- **Update in place**: a color, visibility or time-step change never rebuilds
  geometry.
- **Coalesce redraws**, and draw on demand.
- **Background work** shows a spinner, can be cancelled, and the newest request wins.
- **Compute once and keep** normals, feature edges per part, exact areas, and spatial
  indexes.

## 16. The project itself

- **Stay out of iCloud.** The repo lives in iCloud Documents, and a `git stash pop`
  once left a file renamed without its extension. Keep the Swift project out of
  iCloud-synced folders; Xcode projects and iCloud sync can conflict too.
- **Screen-grab tests flake** when something covers the window. Rerun before
  suspecting the code.
- **One UI test run at a time.** A second app's windows and menus break the checks.
