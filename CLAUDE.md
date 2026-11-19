# Mesh Viewer — notes for Claude Code

The Python app (PySide6 · PyVista/VTK · OpenCASCADE via cadquery-ocp) for CFD meshes,
CAD files and simulation results. Before changing code, read:

- README.md: what it does
- ARCHITECTURE.md: where things are, the conventions, the speed rules
- CHANGELOG.md: the short history (every detail in FULL CHANGELOG.md)
- LESSONS LEARNED.md: the bugs and approaches worth knowing

## The Swift rebuild

- A native SwiftUI version is being built from scratch, as its own project (Claude in
  Xcode). I describe each of its steps myself; it doesn't copy this code or its
  structure. This app stays the one people download until the Swift one replaces it.
- What carries over is **LESSONS LEARNED.md**: what went wrong, why, and how it was
  solved, in plain words, without code paths.
- **Every bug fix or optimization adds an entry there, or updates one,** in the
  section it belongs to: what happened, the cause, the fix, and the numbers for a speed
  change, tagged with the app and version, e.g. *(Python 2.5.3)*. Python-only quirks
  (Qt, VTK, NumPy, py2app) go in only when the idea behind them applies to a native
  app. Say in the reply what was added.

## How I want you to work

- **Never push, commit or release on your own.** I build, commit, push and release.
- **Replies: short, plain language.** Say what is new and what was already there.
- **Speed is a top priority.** Measure before and after a change to a hot path
  (`tools/bench.py <file>`, `tools/bench_timeline.py`), keep work off the UI thread,
  update in place rather than rebuild (ARCHITECTURE.md ▸ Speed), and give the numbers
  in the reply.
- **Restructure on your own initiative** when adding options or optimizing: split a
  file past ~600 lines or holding two subjects, move code where it belongs, merge
  duplicated paths, rename for clarity, without asking first. Keep ARCHITECTURE.md's
  layers and "Where things are" table up to date, and say in the reply what moved.
- **Don't overwrite my edits.** Check a file hasn't changed since you read it before
  writing it. Leave no temporary files in this folder.
- **After changing files for a prompt, build once yourself** (not after every small
  fix, and not when nothing changed). It takes ~20 s and installs into /Applications:
  ```
  cd ~/Documents/Dev/"Mesh Viewer"/MeshViewer
  ./build_app.sh
  ```
- **End every reply that changed files with the commands to run** (none when nothing
  changed):
  - A small change with no new version: only commit and push.
    ```
    cd ~/Documents/Dev/"Mesh Viewer"/MeshViewer
    git add -A
    git commit -m "Short line saying what changed"
    git push
    ```
  - A new version: first build and push,
    ```
    cd ~/Documents/Dev/"Mesh Viewer"/MeshViewer
    ./build_app.sh
    git add -A
    git commit -m "Mesh Viewer X: …"
    git push
    ```
    then, in a separate paragraph, make the DMG and publish the release (add
    `--prerelease` for a beta):
    ```
    ./make_dmg.sh
    gh release create vX ~/Downloads/MeshViewer-build/dist/"Mesh Viewer X.dmg" --title "Mesh Viewer X" --notes-file docs/release-notes-X.md
    ```

## Versions

- 2.X only for a new stage (few, on purpose); everything else is 2.X.Y. A new stage
  can start with betas (`"2.Xb1"`, shown "2.X beta 1", released with `--prerelease`).
- Each release has four entries:
  - `FULL CHANGELOG.md`: everything that changed, file by file, as detailed as needed.
  - `CHANGELOG.md`: the same version condensed, with a short title and 3–6 one- or
    two-line bullets (main features, main files in parentheses, a key timing), no
    tests or restructuring. Update its Stage table when a stage gains something big.
  - `docs/release-notes-<version>.md`, for users (renamed from the previous one, new
    section on top).
  - `LESSONS LEARNED.md`: the version's bug fixes and optimizations, if not already
    added along the way.

## Rules for the app

- Layers: core (no Qt) → render (VTK) → gui (Qt). Settings only through
  `gui/store.settings()`.
- Icons: SF Symbols asked from macOS at run time (PyObjC, `gui/icons.py`); never ship
  SF Symbols exports or SVGs of them. Drawn fallbacks are in `gui/icons.py`.
- Hover texts: the name and the shortcut, nothing more.
- Words on screen: American spelling, Title Case for menus, buttons, tabs and tools,
  sentence case for labels. One name per thing: tool, plot, section, Inflation Layers.
- A change the user may want back goes through `window.changes` (undo).
- Questions are sheets (`gui/sheets.py`), errors `feedback.show_error`, background
  work `run_job(..., busy=(window, "…"))`.
- STEP meshes are for display: speed and few triangles over pretty meshes.
- Tools are built from `gui/forms.py` (`column`, `_row`, `switch_row`, `group_head`,
  `readout`, `note`…), laid out as ARCHITECTURE.md ▸ Conventions ▸ A tool's layout.

## Tests

```
.venv/bin/python tests/run_all.py          # all 12 test files in one app, ~70 s
.venv/bin/python tests/run_all.py plots    # only some (--isolated: a process each)
.venv/bin/python mesh_viewer.py --selftest
```

- **Settings.** The tests use a scratch settings file (`MESHVIEWER_SETTINGS`), never
  the real one; `run_all.py` makes a new one per file.
- **Test files.** `tests/fixtures.py` writes the test files (a STEP box made with OCP,
  no `cadquery`) into `tests/_data/`, and makes them again when it changes. The tests'
  app ignores macOS's FileOpen of the script.
- **One run at a time.** In parallel, a second app's windows and menus break the
  screen grabs and the tab-menu checks.
- **`test_viewport.py` compares screen grabs.** A check fails now and then when
  something covers the window: rerun it before suspecting the code.
- **To see the app**, run a small script with `conftest.run` and save `w.grab()`
  (see-through areas come out white: not a bug).
- **Full screen** can't be tested from here, because a window Claude starts can't take
  the focus: I check it by hand.
- **Don't use `git stash` here.** The folder is in iCloud Documents, and a stash pop
  once left `panels/plots.py` renamed to `plots`, with no extension.

## Where things stand

- **2.5.2** is in the working tree, not yet committed or released (`__version__`
  "2.5.2", CHANGELOG and FULL CHANGELOG ▸ 2.5.2, `docs/release-notes-2.5.2.md`). It
  adds OpenFOAM cases with time steps and animation, Probe, Open Case… (⇧⌘O), and
  plots on 2D files. Released: 2.5.1.
- **Long test case:** the pitzDaily LES (601 steps), in ~/Downloads/Mesh Viewer Test
  Cases.
- **Left for later:** FEA and transient results.
- **Still to check by hand:** Settings / About over a full-screen window (set up
  right, but the slide itself is only visible to me).
