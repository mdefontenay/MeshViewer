"""What an OpenFOAM case says in its own files, read without VTK: the patches
(polyMesh/boundary), the time folders and the fields in them (their class and
dimensions, from each file's header), and the owner list (which cell owns each face).

    read_boundary(poly)    {patch: {"type", "nFaces", "startFace"}}
    time_folders(case)     ["0", "0.5", "1"]: the folders with fields, by time
    fields_in(folder)      {"p": ("scalar", "m²/s²"), "U": ("vector", "m/s"), "R":
                           ("symmTensor", "m²/s²"), "phi": ("surface", "m³/s")}
    read_labels(path)      owner / neighbour as a NumPy array (ASCII or binary)
    patch_values(path, patches)   a face field's values on each patch (phi)
"""
from __future__ import annotations

import gzip
import re
from pathlib import Path

import numpy as np

_NUMBER = re.compile(r"[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?")
FIELD_CLASSES = {"volScalarField": "scalar", "volVectorField": "vector",
                 "volSymmTensorField": "symmTensor", "volTensorField": "tensor",
                 "surfaceScalarField": "surface"}         # surface: on the faces (phi)

# dimensions [kg m s K …] -> the unit (a name in core/units.QUANTITIES); others: none
DIMENSIONS = {(0, 1, -1, 0): "m/s", (1, -1, -2, 0): "Pa", (0, 2, -2, 0): "m²/s²",
              (0, 2, -3, 0): "m²/s³", (0, 0, -1, 0): "1/s", (0, 2, -1, 0): "m²/s",
              (1, -1, -1, 0): "Pa·s", (1, -3, 0, 0): "kg/m³", (0, 0, 0, 1): "K",
              (1, 0, -3, 0): "W/m²", (0, 1, 0, 0): "m", (0, 3, -1, 0): "m³/s",
              (1, 0, -1, 0): "kg/s", (0, 0, -2, 0): "1/s²", (2, -2, -4, 0): "Pa²",
              (0, 4, -4, 0): "m⁴/s⁴"}


def _file(path):
    """`path`, or `path`.gz when only that one is there."""
    path = Path(path)
    return path if path.is_file() else path.with_name(path.name + ".gz")


def read_bytes(path, size=None):
    p = _file(path)
    opener = gzip.open if p.suffix == ".gz" else open
    with opener(p, "rb") as f:
        return f.read(size) if size else f.read()


def _text(path, size=None):
    return read_bytes(path, size).decode("latin-1")


def _strip_comments(s):
    return re.sub(r"//[^\n]*|/\*.*?\*/", "", s, flags=re.S)


def _header(path):
    """The FoamFile entries of a file ({"class": …, "format": …, "arch": …}), {} if none."""
    try:
        s = _strip_comments(_text(path, 4096))
    except OSError:
        return {}
    m = re.search(r"FoamFile\s*\{([^}]*)\}", s)
    return dict((k, v.strip().strip('"')) for k, v in re.findall(r"(\w+)\s+([^;]*);",
                                                                   m.group(1))) if m else {}


def read_boundary(poly) -> dict:
    """{patch: {"type": …, "nFaces": int, "startFace": int}} from polyMesh/boundary
    (always a text dictionary)."""
    s = _strip_comments(_text(Path(poly) / "boundary"))
    out = {}
    for name, body in re.findall(r'([^\s{}();"]+)\s*\{([^{}]*)\}', s):
        if name == "FoamFile":
            continue
        e = dict(re.findall(r"(\w+)\s+([^;]*);", body))
        out[name] = {"type": e.get("type", "patch").strip(),
                     "nFaces": int(e.get("nFaces", "0").strip() or 0),
                     "startFace": int(e.get("startFace", "0").strip() or 0)}
    return out


def cells_in_note(poly):
    """nCells from the owner file's note, or None."""
    m = re.search(r"nCells:\s*(\d+)", _text(Path(poly) / "owner", 4096))
    return int(m.group(1)) if m else None


def fields_in(folder) -> dict:
    """{field: (kind "scalar" | "vector", unit or "")} of the volume fields in a time folder."""
    out = {}
    folder = Path(folder)
    if not folder.is_dir():
        return out
    for f in sorted(folder.iterdir()):
        if not f.is_file():
            continue
        name = f.name[:-3] if f.name.endswith(".gz") else f.name
        kind = FIELD_CLASSES.get(_header(f).get("class", ""))
        if kind is not None and name not in out:
            out[name] = (kind, _unit(f))
    return out


def _unit(path):
    m = re.search(r"dimensions\s*\[([^\]]*)\]", _strip_comments(_text(path, 8192)))
    if not m:
        return ""
    try:
        d = [int(round(float(x))) for x in m.group(1).split()]
    except ValueError:
        return ""
    if len(d) < 4 or any(d[4:]):
        return ""
    return DIMENSIONS.get(tuple(d[:4]), "")


def time_folders(case) -> list:
    """The time folders of a case that hold fields, earliest first ("0", "0.5", "1e-3")."""
    case = Path(case) if case is not None else None
    if case is None or not case.is_dir():
        return []
    times = [d.name for d in case.iterdir()
             if d.is_dir() and _NUMBER.fullmatch(d.name) and fields_in(d)]
    return sorted(times, key=float)


def patch_values(path, patches):
    """{patch: values (n,)} of a face field (surfaceScalarField: phi) on the patches,
    from each patch's `value` entry (uniform or a list, ASCII or binary). patches:
    [(name, number of faces)], in the boundary file's order."""
    raw = read_bytes(path)
    head = _header(path)
    binary = head.get("format", "ascii") == "binary"
    m = re.search(r"scalar=(\d+)", head.get("arch", ""))
    size = int(m.group(1)) // 8 if m else 8
    endian = ">" if "MSB" in head.get("arch", "") else "<"
    at = raw.find(b"boundaryField")
    out = {}
    if at < 0:
        return out
    for name, n in patches:
        m = re.compile(rb"\b" + re.escape(name.encode()) + rb"\s*\{").search(raw, at)
        if not m:
            continue
        at = m.end()
        stop = raw.find(b"}", at)
        v = raw.find(b"value", at)
        if v < 0 or (stop >= 0 and stop < v):        # no value: (empty, zeroGradient…)
            continue
        m = re.compile(rb"value\s+(uniform\s+([^;\s]+)|nonuniform\s+List<scalar>\s*(\d+)"
                       rb"\s*\()").match(raw, v)
        if not m:
            continue
        if m.group(2) is not None:
            out[name] = np.full(n, float(m.group(2)))
            at = m.end()
            continue
        count, start = int(m.group(3)), m.end()
        if binary:
            out[name] = np.frombuffer(raw, dtype=f"{endian}f{size}", count=count,
                                      offset=start).astype(np.float64)
            at = start + count * size
        else:
            stop = raw.find(b")", start)
            out[name] = np.array(raw[start:stop].split(), dtype=np.float64)
            at = stop
    return out


def read_labels(path):
    """A labelList (owner, neighbour) as int64, written ASCII or binary, gzipped or not."""
    raw = read_bytes(path)
    head = _header(path)
    end = raw.find(b"}", raw.find(b"FoamFile")) + 1 if b"FoamFile" in raw[:4096] else 0
    body = re.sub(rb"//[^\n]*", b"", raw[end:end + 4096]) if end else raw[:4096]
    m = re.search(rb"(\d+)\s*\(", body)
    if not m:
        raise ValueError(f"Can't read {Path(path).name}: no list in it.")
    count = int(m.group(1))
    start = raw.find(b"(", raw.find(m.group(0), end)) + 1
    if head.get("format", "ascii") == "binary":
        size = int(re.search(r"label=(\d+)", head.get("arch", "label=32"))
                   .group(1)) // 8 if "label=" in head.get("arch", "") else 4
        endian = ">" if "MSB" in head.get("arch", "") else "<"
        return np.frombuffer(raw, dtype=f"{endian}i{size}", count=count,
                             offset=start).astype(np.int64)
    stop = raw.find(b")", start)
    return np.array(raw[start:stop].split(), dtype=np.int64)
