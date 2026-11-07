# Mesh Viewer

A fast, native-feeling macOS viewer for **CAD files** (STEP, IGES, BREP, STL, …)
and **CFD meshes** (CGNS, UGRID). Double-click a file and inspect it: show or
hide parts, cut it with a section plane, measure distances, areas and volumes,
estimate y+ and inflation layers for CFD, and export clean screenshots.

![Mesh Viewer: a STEP assembly with its parts list](docs/screenshots/main_dark.png)

<p align="center">
  <img src="docs/screenshots/measure_dark.png" width="49%" alt="Distance measurement in dark mode">
  <img src="docs/screenshots/section_light.png" width="49%" alt="Section plane">
</p>

## Small AI Disclamer

I just wanted to make it clear here: I am a mechanical engineer. I have studied
physics and mechanical engineering, not software engineering. Therefore yes, this
program has entirely been made using Claude Opus 5.5. I was tired of not having
a quick and simple way to preview my CAD/mesh files on my MacBook, so I 'made' this
program. I chose each functionalities it should have, but I didn't implement them
myself. I am sharing this work as I liked how it ended up looking and felt like
others could benefit from it.

## Features

- **Meshes and CAD in one app**: CGNS and FUN3D/AFLR3 UGRID meshes with their
  named boundaries, and CAD files read with OpenCASCADE, with an adjustable mesh
  quality for STEP/IGES/BREP.
- **McMaster Parts list**: groups similar names into fold-out rows, has a filter, and
  checkboxes to show or hide parts. McMaster-Carr parts are collected at the top,
  and right-clicking one gives **Search in McMaster**.
- **Section plane**: set its origin and normal, slide it, flip it, or drag it in
  3D. The cut faces are filled in.
- **CFD** (meshes): y+ estimate on a boundary from the flow (air at an altitude,
  water at a depth, or your own values) and the mesh's first cell layer; the
  boundary **coloured by y+**; first cell height for a target y+; compressibility
  correction; a unit menu on every input; flow direction arrows.
- **CFD mode** (CAD): an inflation layer calculator — choose the walls (a part, or
  faces you pick), get the first layer height for a target y+, the layer heights
  for N layers and a growth rate, and compare them to the boundary layer. A page
  under the 3D view shows a **layer size plot** and a **cross section** of the
  walls with the layers drawn on them (see [CFD tools](#cfd-tools)).
- **Formulas** and **Values**: every equation used, shown like LaTeX, and every
  computed number (Re, Cf, δ99, u*…) in a pop-up.
- **Cell quality** (meshes): skewness, aspect ratio, scaled Jacobian and volume of
  every cell, as a histogram; show the bad cells, colour the cut by quality, find
  inverted cells.
- **Measure**:
  - point-to-point distance, with ΔX / ΔY / ΔZ drawn in 3D
  - point coordinates (and distance to the section plane), angle between faces
  - area, and volume when the selection is closed
  - **exact** values for STEP/IGES/BREP, straight from the CAD
  - results in mm, cm, m, in or ft; the axis labels follow the same unit
- **Screenshots** at up to 4× the window size, with the background as shown or
  transparent.
- **Looks like a Mac app**: light and dark mode, your accent colour, a sidebar
  with sections that fold, one window per file. A second file opens instantly,
  without starting the app again.
- **Appearance** settings: theme, 3D background (gradient, colour or a picture),
  axis label size, edge thickness, and hiding edges while rotating for smoother
  handling of large models.

| Kind | Formats |
|------|---------|
| Mesh | CGNS `.cgns`, UGRID `.lb8/.b8/.lb4/.b4.ugrid` (boundary names from `.mapbc`) |
| CAD, exact geometry | STEP `.step/.stp`, IGES `.iges/.igs`, BREP `.brep/.brp` |
| CAD, triangulated | STL `.stl`, OBJ `.obj`, PLY `.ply`, glTF `.gltf/.glb`, VRML `.wrl/.vrml` |

Native SolidWorks, CATIA, NX, Creo, Inventor, Parasolid (`.x_t`), ACIS (`.sat`)
and JT files are closed formats: export STEP (best) or IGES from those programs.

## CFD tools

Two sections help set up a CFD mesh:

- **CFD** (for meshes, CGNS / UGRID): checks the y+ of a mesh you already have,
  from its first cell layer, and can paint the boundary by y+.
- **CFD mode** (for CAD files): plans the inflation layers before you mesh. Pick
  the walls, set the flow and the layers, and switch to the **Inflation layers**
  page under the 3D view.

![CFD mode: the flow and inflation layer inputs, with the walls tinted in 3D](docs/screenshots/cfd_mode_dark.png)

<p align="center">
  <img src="docs/screenshots/inflation_plot_light.png" width="49%" alt="Layer size plot: each layer's height and the total thickness against the boundary layer">
  <img src="docs/screenshots/cross_section_dark.png" width="49%" alt="Cross section: the inflation layers estimated around a wing section">
</p>

The page shows the Reynolds number, the first layer height, the estimated y+,
the boundary-layer thickness and the size of the layers, then two tabs:

- **Layer size plot**: a bar per layer and the total thickness so far, against
  the boundary layer and the size of the next cell of the mesh.
- **Cross section**: turn on the section plane (sidebar ▸ Section) and the cut
  of the walls is drawn in 2D, with the layers on it. It follows the plane as you
  move it. Scroll to zoom, drag to pan.

Below, simple checks say whether the layers cover the boundary layer and step
smoothly into the mesh.

## Download

Get the latest **`Mesh Viewer <version>.dmg`** from the
[Releases page](../../releases/latest), open it and drag **Mesh Viewer** onto
**Applications**.

> **First launch:** the app isn't notarized by Apple (that needs a paid developer
> account), so macOS blocks it the first time. Try to open it once, then go to
> **System Settings → Privacy & Security** and click **Open Anyway**. You only
> need to do this once.

The app in the .dmg is built for **Apple Silicon** Macs running macOS 13 or later.
On an Intel Mac, build it from source (below).

## Build from source

You need Python 3.12 or 3.13 from Homebrew or python.org. py2app doesn't support
pyenv or conda Pythons, or Python 3.14 yet.

```bash
brew install python@3.13
git clone https://github.com/mdefontenay/MeshViewer.git
cd MeshViewer
./build_app.sh            # quick build, installed in /Applications
```

- `./build_app.sh` creates `.venv`, installs `requirements.txt`, builds the app
  and installs it. This quick build runs the code in this folder, so keep the
  folder where it is. After editing the code, just reopen the app.
- `./build_app.sh --standalone` builds a self-contained app (~1 GB) that can be
  copied to another Mac.
- `./make_dmg.sh` builds the self-contained app, checks it (`--selftest`) and
  packs `~/Downloads/MeshViewer-build/dist/Mesh Viewer <version>.dmg` (its window
  layout is written by `dmgbuild`, installed in the build environment the first time).
- Heavy files (Python environment, app, .dmg) go to `~/Downloads/MeshViewer-build`,
  not the project folder; choose another place with `MESHVIEWER_WORK=/path`.
- Run without building: `.venv/bin/python mesh_viewer.py file.step`

## Already have Python? Run it without the 1 GB app

The self-contained app is big because it carries its own copy of Python, Qt,
VTK and OpenCASCADE (I liked the self-contained aspect). If you already have Python with these packages, you don't
need any of that.

**1. Install what's missing:**

```bash
pip install numpy pyvista pyvistaqt PySide6 h5py cadquery-ocp
```

`cadquery-ocp` is only needed for STEP / IGES / BREP files, and `h5py` only
for CGNS files.

**2. Run it:**

```bash
git clone https://github.com/mdefontenay/MeshViewer.git
cd MeshViewer
python mesh_viewer.py path/to/file.step
```

**Optional: a small app in /Applications that uses your Python.** It gives
you the Dock icon and double-click-to-open, but only weighs a few MB because it
uses your installed packages. This needs Python 3.12 or 3.13 from Homebrew or
python.org:

```bash
python3.13 -m venv --system-site-packages .venv   # reuse your packages
./build_app.sh                                    # quick build, no re-download
```

Keep the MeshViewer folder where it is: this app runs the code from it.

## Using it

- **Open** files by double-clicking them, dropping them on a window or the Dock
  icon, or with ⌘O. Each file gets its own window.
- **Views**: Fit ⌘0 · Iso ⌘1 · X ⌘2 · Y ⌘3 · Z ⌘4 · parallel projection on/off ⌘5.
  Press X, Y or Z again to look from the opposite side.
- **Select**: click a part, or ⌘/⇧-click to add parts. Click empty space or press
  Esc to clear.
- **Right-click** a part (in 3D or in the list):
  - Hide Part, Isolate, Zoom To, Colour…, Show All
  - Hide Surface (STEP / IGES / BREP): hides only the face under the cursor;
    *Show All* brings it back
  - Rename… (also: select a part and press Return) — Export uses the new names
  - Search in McMaster (when a McMaster part number is anywhere in the name)
  - Right-clicking inside a multi-selection acts on the whole selection.
- **Sidebar**:
  - **Info** (first): extent per axis, faces, points, edge lengths, volume cells.
  - **Mesh quality** (STEP/IGES/BREP): five levels; the part is re-meshed in the
    background.
  - **Section**: the plane controls. Switching it on opens them, off folds them. For CGNS /
    UGRID meshes, *Fill cut faces* shows the volume cells the plane cuts.
  - **Measure**: measuring is on while this section is open.
    - *Distance*: click two points.
    - *Point*: click a point — measured from the origin (0, 0, 0) like a distance,
      with its coordinates and its distance to the section plane.
    - *Angle*: click two faces (or a face and the cut) — the angle between them.
    - *Area*: click parts, or switch to *CAD faces* to pick single faces; volume
      too when they close up. Clicking empty space clears the faces.
  - **Cell quality** (meshes): pick a measure, set the "bad" threshold on the
    histogram (click / drag), then Zoom, Show bad cells or Colour by quality.
  - **CFD**: fluid (air at an altitude, fresh / sea water at a depth, or custom),
    Mach or speed U, and flow direction; y+ on a boundary (measured from the first
    cell layer of volume meshes), *Colour by y+*, and the first cell height for a
    target y+; flow vectors. *Formulas* and *Values* next to each group.
  - **CFD mode** (CAD files): switch it on, fill in the **Flow** (same inputs as
    the CFD section) and the **Inflation layers**:
    - *Walls*: the whole model, one part, or *Pick faces…* — ⇧-click faces of one
      part in 3D, then *Apply*. The walls are tinted in 3D.
    - *Length L* (auto: the longest distance along the flow), *Target y+*,
      *Compressibility correction*.
    - *First layer* (auto from y+, or typed), *Layers*, *Growth rate* (1 to 2),
      *Next cell* (a multiple of the largest layer).

    The bar under the 3D view switches between the model and the *Inflation
    layers* page. In its *Cross section* tab, *Flip side* puts the layers on the
    other side of the walls (for internal flow), *Fit view* fits the cut, and the
    legend shows or hides the flow direction arrow.
  - **Parts**: list, filter, Show All / Hide All.
- **Show** (toolbar, also View ▸ Show): mesh edges, feature edges, faces (off =
  edges only) · axes, grid, bounding box, origin marker — each on / off.
- **Units** (toolbar): ⊘ · mm · cm · m · in · ft. Used for measurements and axis
  labels. STEP/IGES files are in mm and get converted.
- **Appearance** (⌘, or the sliders button) — how things look, the same in every
  window: theme, parts list spacing, 3D background, shading, axis label size, edge
  line thickness, and hide edges while moving.
- **Screenshot** (⇧⌘S): 1×–4× resolution, background *As Shown* or *Transparent*.
- **Edit** (sidebar section, like Onshape's Transform): choose Rotate (any angle
  about X, Y or Z), Mirror or Move by X, Y, Z, fill it in and press Apply — turning
  about the origin or the model's centre. The changes are listed below. *Show original edges* shows
  the file's edges in grey to compare; *Undo* steps back, *Reset* returns to the
  file. Works on meshes (CGNS, UGRID) and triangle CAD (STL, OBJ, PLY, glTF, VRML),
  not on STEP / IGES / BREP. Edits and renamed parts stay in memory until you
  export them.
- **File ▸ Open Recent**; every file reopens the way you left it (camera, display
  toggles, unit, colours, names, hidden parts, section).
- **Export…** (⇧⌘E): STL (binary or one named solid per part), OBJ and PLY (with
  the part colours), VTU
  (ParaView) and, for meshes, UGRID + .mapbc with the volume cells. Includes your
  edits; hidden parts can be left out. STEP / IGES / BREP export their current
  triangle mesh (STL, OBJ, PLY).
- **About Mesh Viewer** is in the app menu, with *Check for Updates…* (opens the
  latest GitHub release).

## Project layout

```
mesh_viewer.py          entry point (+ --selftest)
meshviewer/
  __init__.py           version number
  formats.py            file extension -> reader
  model.py              what readers return: {part name: surface} + kind / format / units
  transform.py          Edit: rotations, mirrors, moves
  export.py             Export: STL, OBJ, PLY, VTU, UGRID writers
  quality.py            cell quality measures (skewness, aspect ratio, Jacobian, volume)
  cfd.py                y+ estimate, standard atmosphere, water, first cell layer, inflation layers
  polys.py              small surface helpers (faces by size, edge lengths)
  mesh/  cgns.py ugrid.py volume.py mesh readers, volume cells
  cad/   occt.py                    OpenCASCADE core: read, name, tessellate, exact area/volume
         step.py iges.py brep.py    exact-geometry CAD readers
         stl.py tessellated.py      triangulated CAD formats
  gui/
    app.py              application: windows, file-open events, Appearance settings, About
    window.py           window: toolbar, menus, loading, drag & drop, screenshots
    scene.py            3D view: parts, edges, grid, views, picking, screenshots
    sidebar.py          side panel; part_tree.py = parts list
    section.py, section_panel.py    section plane and its controls
    measure.py, measure_panel.py    measurements and their panel
    appearance_dialog.py, screenshot_dialog.py, about_dialog.py
    edit_panel.py, export_dialog.py   Edit section, Export sheet
    quality_panel.py, quality_view.py Cell quality section and its 3D overlays
    info_panel.py       Info section
    cfd_panel.py, cfd_view.py         CFD section and its flow arrows
    inflation_panel.py, inflation_view.py  CFD mode (CAD): inflation layer inputs and page
    section_view.py     CFD mode: the section plane's cut with the layers estimated
    memory.py           files reopen the way you left them
    jobs.py             background work
    background.py       picture behind the 3D view
    widgets.py, icons.py, style.py  switches, menus, icons, light/dark styling
setup.py                py2app settings: icon, file types
build_app.sh            build (+ install)
make_dmg.sh             self-contained app -> .dmg
fix_bundle.py           repairs Homebrew libraries py2app damages when copying
slim_bundle.py          removes unused Qt parts from the self-contained app
resources/              app icon, .dmg window background
docs/                   screenshots, release notes template
```

The history of every version is in [CHANGELOG.md](CHANGELOG.md).

## Credits

Made by **Matthieu de Fontenay**, built with Claude Opus 5.5.

Built on [PyVista](https://pyvista.org) / [VTK](https://vtk.org),
[Qt for Python (PySide6)](https://doc.qt.io/qtforpython/),
[OpenCASCADE](https://dev.opencascade.org) (via
[cadquery-ocp](https://github.com/CadQuery/OCP)), [h5py](https://www.h5py.org)
and [NumPy](https://numpy.org).

## License

[MIT](LICENSE) © 2026 Matthieu de Fontenay
