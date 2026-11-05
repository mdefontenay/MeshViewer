"""py2app build description for Mesh Viewer.app — run through build_app.sh."""
import re
from pathlib import Path

from setuptools import setup

# Version lives in meshviewer/__init__.py (also shown in About Mesh Viewer).
VERSION = re.search(r'__version__ = "([^"]+)"',
                    Path(__file__).with_name("meshviewer").joinpath("__init__.py").read_text())[1]

DOC_TYPES = [
    # extensions, name, rank, UTIs
    (["cgns"],         "CGNS Mesh File",        "Owner",     ["local.cgns"]),
    (["ugrid"],        "FUN3D UGRID Mesh File", "Owner",     ["local.ugrid"]),
    (["step", "stp"],  "STEP CAD File",         "Default",   ["local.step"]),
    (["iges", "igs"],  "IGES CAD File",         "Default",   ["local.iges"]),
    (["brep", "brp"],  "BREP CAD File",         "Default",   ["local.brep"]),
    # Triangulated formats other apps (Preview, …) also open: "Alternate" keeps
    # their default until you pick Mesh Viewer in Get Info -> Open with -> Change All.
    (["stl"],          "STL Model",             "Alternate", ["public.standard-tesselated-geometry-format"]),
    (["obj"],          "OBJ Model",             "Alternate", ["public.geometry-definition-format", "local.obj"]),
    (["ply"],          "PLY Model",             "Alternate", ["public.polygon-file-format", "local.ply"]),
    (["gltf", "glb"],  "glTF Model",            "Alternate", ["local.gltf"]),
    (["wrl", "vrml"],  "VRML Model",            "Alternate", ["local.vrml"]),
]


def _uti(uti, name, exts):
    return {"UTTypeIdentifier": uti, "UTTypeDescription": name,
            "UTTypeConformsTo": ["public.data"],
            "UTTypeTagSpecification": {"public.filename-extension": exts}}


PLIST = {
    "CFBundleName": "Mesh Viewer",
    "CFBundleDisplayName": "Mesh Viewer",
    "CFBundleIdentifier": "local.meshviewer",          # same id as the old app
    "CFBundleShortVersionString": VERSION,
    "CFBundleVersion": VERSION,
    "LSMinimumSystemVersion": "13.0",
    "LSApplicationCategoryType": "public.app-category.developer-tools",
    "NSHighResolutionCapable": True,
    "NSRequiresAquaSystemAppearance": False,            # follow light / dark mode
    "CFBundleDocumentTypes": [
        {"CFBundleTypeExtensions": exts, "CFBundleTypeName": name,
         "CFBundleTypeRole": "Viewer", "LSHandlerRank": rank, "LSItemContentTypes": utis}
        for exts, name, rank, utis in DOC_TYPES
    ],
    "UTExportedTypeDeclarations": [
        _uti("local.cgns", "CGNS Mesh File", ["cgns"]),
        _uti("local.ugrid", "FUN3D UGRID Mesh File",
             ["ugrid", "lb8.ugrid", "b8.ugrid", "lb4.ugrid", "b4.ugrid"]),
    ],
    # Types we don't own: "imported" (used only if no other app defines them).
    "UTImportedTypeDeclarations": [
        _uti("local.step", "STEP CAD File", ["step", "stp"]),
        _uti("local.iges", "IGES CAD File", ["iges", "igs"]),
        _uti("local.brep", "BREP CAD File", ["brep", "brp"]),
        _uti("local.obj", "OBJ Model", ["obj"]),
        _uti("local.ply", "PLY Model", ["ply"]),
        _uti("local.gltf", "glTF Model", ["gltf", "glb"]),
        _uti("local.vrml", "VRML Model", ["wrl", "vrml"]),
    ],
}

OPTIONS = {
    "iconfile": "resources/mesh_icon.icns",
    "plist": PLIST,
    "argv_emulation": False,        # Qt receives macOS file-open events itself
    # Standalone builds only: copy these packages whole (VTK and PyVista load
    # many modules lazily, which py2app's import scanner would otherwise miss).
    "packages": ["meshviewer", "pyvista", "pyvistaqt", "vtkmodules", "qtpy",
                 "numpy", "h5py", "OCP", "scooby", "pooch"],
    "includes": ["vtk"],
    # Not used by the app (py2app would otherwise pull them in from the venv).
    "excludes": ["tkinter", "pip", "wheel"],
}

setup(
    app=["mesh_viewer.py"],
    name="Mesh Viewer",
    options={"py2app": OPTIONS},
)
