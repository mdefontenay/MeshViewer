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
| change how STEP / IGES / BREP are meshed | `core/cad/occt.py` (`QUALITY_LEVELS`, `tessellate`), `core/cad/remesh.py` (no sliver fans) |
| Gmsh / Fluent `.msh`, DXF | `core/mesh/msh.py` (meshio for Gmsh, own Fluent parser, text and binary), `core/cad/dxf.py` (ezdxf). Readers may return `(parts, {"dim": 2, "units": …})`; `Model.dim` / `file_type` (cad, mesh, mesh2d, drawing) pick the sections |
| volume cells (CGNS, UGRID, .msh) | `core/mesh/cgns.py` `read_volume`, `core/mesh/polyhedra.py` (NGON/NFACE), `core/mesh/volume.py` |
| CFD numbers (y+, atmosphere, layers) | `core/cfd.py`; exports for meshers `core/cfd_export.py` |
| units, number formatting | `core/units.py` (unit tables, `fmt`, `show_length`, `nice_length`, `nice_num`) |
| solution fields, colour scales | `core/fields.py` (`solution_fields`, `ramp_rgb`, `COLORMAPS`, `DEFAULT_MAP`; F15 `gradient_magnitude`, `cell_jumps`) |
| Plots (measurements → tabs) | `core/plots.py` (`KINDS`: defaults + compute per kind; CSV), `gui/panels/plots.py` (`PlotsPanel`, `EDITORS` per kind), `gui/pages/plots.py` (`PlotPage`), tabs in `gui/window.py` (`_rebuild_view_bar`, `_show_page("plot:<id>")`), the 3D cut `render/overlays.py` `CutLineView`. A new kind: an entry in `KINDS` + an editor in `EDITORS` |
| 2D cut geometry (inflation layers) | `core/geometry2d.py` |
| the 3D view: parts, edges, picking, views | `render/scene.py` (`Scene`) |
| overlays (flow arrows, y+, walls, results) | `render/overlays.py`; cell quality colours `render/quality_overlay.py` |
| section plane, measurements | `render/section.py`, `render/measure.py` |
| a sidebar section | `gui/sections.py` (the list) + `gui/panels/<name>.py` + `Sidebar._build_sections` |
| shared form rows (label · field · unit · ?) | `gui/forms.py` |
| switches, menus, number fields | `gui/widgets.py` |
| icons | `gui/icons.py`: `SF` maps icon names to SF Symbols (drawn by macOS at run time, via PyObjC); `DRAWINGS` are the fallbacks |
| colours / stylesheet | `gui/style.py` |
| per-file memory | `gui/memory.py` (`capture` / `restore`, one key per setting) |
| window, toolbar, menus, export / screenshot flow | `gui/window.py` |
| pages under the 3D view (Inflation layers) | `gui/pages/inflation.py`, `gui/pages/section_cut.py` |

## Conventions

- **Sidebar sections**: every section exists for every file; `SectionSpec.unavailable(scene)`
  returns the grey reason when it doesn't apply. Panels expose `bind(scene)` and, when
  needed, `activate(on)` (open / closed), `model_changed()`, `refresh_names()`,
  `refresh_colors()`, `settings()`. Settings that a file remembers live on the scene
  (`scene.<name>_settings`) and are saved by `gui/memory.py`.
- **Background work**: `gui/jobs.run_job(work, done, failed)`; `work` must not touch Qt.
- **Naming**: modules are nouns (`sections.py`, `units.py`); panels are `<Name>Panel`,
  3D overlays `<Name>View`. Private helpers start with `_`.
- **No version notes in code**: history goes in CHANGELOG.md, not in comments.
- **Units**: lengths inside the app are model units; CFD maths is in metres
  (`core/units.UNITS` converts).

## Tests

```
python tests/run_all.py          every test file (xvfb-run is used on Linux)
python tests/test_sidebar.py     one of them
```

`tests/fixtures.py` writes small test files into `tests/_data/` (git-ignored): a STEP
box, a hex CGNS mesh, the same mesh as NGON/NFACE polyhedra, a UGRID and a Tecplot
results file. `tests/conftest.py` has `check()`, `open_file()` and `run()`.
