"""DXF drawings (2D profiles), read with ezdxf and drawn as lines, one part per layer:

    curves       LINE, LWPOLYLINE, POLYLINE, ARC, CIRCLE, ELLIPSE, SPLINE
    text         TEXT, ATTRIB, MTEXT — the letters' outlines (ezdxf's text2path, with the
                 system's fonts, else matplotlib's: no Qt here); MTEXT split into TEXT first;
                 a font missing some of the letters (not installed) -> FALLBACK_FONTS
    dimensions   DIMENSION — its block (lines, arrows, the value as text); one without a
                 block is drawn by ezdxf first
    filled       SOLID, TRACE, 3DFACE (arrowheads…) — their 3 or 4 corners, as a closed outline

Blocks (INSERT, dimensions, leaders…) are taken apart into the same kinds, wherever
they are; what is on layer 0 inside a block goes on the reference's layer (DXF's rule).
The drawing's unit ($INSUNITS) is passed on when it has one.
read_dxf returns (parts, {"dim": 2, "units": "mm" | … | ""}).
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pyvista as pv

from meshviewer.core.model import MissingDependency

INSUNITS = {1: "in", 2: "ft", 4: "mm", 5: "cm", 6: "m"}
CURVES = ("LINE", "LWPOLYLINE", "POLYLINE", "ARC", "CIRCLE", "ELLIPSE", "SPLINE")
TEXTS = ("TEXT", "ATTRIB")
FILLED = ("SOLID", "TRACE", "3DFACE")


def _fonts_ready():
    """ezdxf finds the system's fonts; with none (a bare machine), matplotlib's DejaVu."""
    try:
        from ezdxf.fonts import fonts
        fm = fonts.font_manager
        if not fm.has_font(fm.fallback_font_name()):
            import matplotlib
            fm.scan_folder(Path(matplotlib.get_data_path()) / "fonts" / "ttf")
    except Exception:                                        # noqa: BLE001 text stays as it can
        pass


def corners(e):
    """The outline of a SOLID / TRACE / 3DFACE: its corners in drawing order, closed.
    SOLID and TRACE store them as 0, 1, 3, 2 (a "Z"); 3DFACE in order. Three corners
    when the last two are the same (a triangle: most arrowheads)."""
    flat = e.dxftype() in ("SOLID", "TRACE")
    pts = [np.array(e.dxf.get(n, e.dxf.get("vtx2")), dtype=float)   # no vtx3: a triangle
           for n in ("vtx0", "vtx1", "vtx2", "vtx3")]
    if flat:
        pts = [pts[0], pts[1], pts[3], pts[2]]
    out = [pts[0]]
    for p in pts[1:]:                                        # a triangle: a corner repeated
        if not np.allclose(p, out[-1]):
            out.append(p)
    if len(out) > 1 and np.allclose(out[-1], out[0]):
        out.pop()
    pts = np.array(out)
    if flat:                                                 # in the entity's plane (OCS)
        ocs = e.ocs()
        if ocs.transform:
            pts = np.array([tuple(ocs.to_wcs(p)) for p in pts])
    return np.vstack([pts, pts[:1]]) if len(pts) >= 3 else pts


# a font with the Latin letters, digits, ± and °, when the drawing's font isn't installed
# (macOS fonts first, then matplotlib's DejaVu: _fonts_ready)
FALLBACK_FONTS = ("Arial Unicode.ttf", "Arial.ttf", "Helvetica.ttc", "DejaVuSans.ttf")
_CMAPS = {}                        # font file -> the characters it has (None: unreadable)
_UNICODE = re.compile(r"(?<!\\)\\U\+([0-9A-Fa-f]{4})")      # MTEXT's \U+2212


def _covers(filename, text):
    """Does this font file have a glyph for every character of the text?"""
    from ezdxf.fonts import fonts
    if filename not in _CMAPS:
        try:
            _CMAPS[filename] = set(fonts.font_manager.get_ttf_font(filename).getBestCmap())
        except Exception:                                    # noqa: BLE001 not a TrueType font
            _CMAPS[filename] = None
    cmap = _CMAPS[filename]
    return cmap is None or all(ord(c) in cmap for c in text if not c.isspace())


def text_font(e, text):
    """The font for a TEXT: its style's, unless that one lacks some of its letters —
    a font that isn't installed is replaced by the closest name, which can be another
    script entirely (Onshape's "Noto Sans" -> Noto Sans Oriya: boxes for letters)."""
    from ezdxf.fonts import fonts
    face = fonts.get_font_face(e.font_name())
    if _covers(face.filename, text):
        return face
    fm = fonts.font_manager
    for name in FALLBACK_FONTS:
        if fm.has_font(name):
            other = fonts.get_font_face(name)
            if _covers(other.filename, text):
                return other
    return face


def _text_polylines(e, tol):
    """The letters of a TEXT / ATTRIB as closed polylines (each contour of each glyph)."""
    from ezdxf.addons import text2path
    if e.dxf.get("invisible", 0):
        return []
    h = float(e.dxf.get("height", 1.0) or 1.0)
    t = min(tol, max(h, 1e-9) / 40)                          # letters stay round
    text = e.plain_text()
    if not text.strip():
        return []
    path = text2path.make_path_from_str(text, text_font(e, text), size=h,
                                        align=e.get_align_enum(), length=e.fit_length())
    path = path.transform(e.wcs_transformation_matrix())
    out = []
    for sub in path.sub_paths():
        v = np.array([(p.x, p.y, p.z) for p in sub.flattening(t)], dtype=float)
        if len(v) >= 2:
            if not np.allclose(v[0], v[-1]):
                v = np.vstack([v, v[:1]])
            out.append(v)
    return out


def _mtext_parts(e, scratch):
    """MTEXT as plain TEXT entities (one per word run, placed as ezdxf lays it out)."""
    from ezdxf.addons import MTextExplode
    # \U+XXXX (a character by its code): ezdxf leaves it as "U+XXXX" inside a stacked
    # tolerance (\S+.000^ \U+2212.010;, Onshape) — decoded first (in memory only)
    e.text = _UNICODE.sub(lambda m: chr(int(m.group(1), 16)), e.text)
    scratch.delete_all_entities()
    with MTextExplode(scratch) as x:
        x.explode(e, destroy=False)
    return [t for t in scratch if t.dxftype() == "TEXT"]


def flatten(entities, parent_layer=None, depth=0):
    """(entity, layer) for every drawable entity, blocks taken apart wherever they are
    (INSERT and its attributes, DIMENSION, LEADER, MLEADER, tables…). DXF's rule: inside
    a block, what is on layer 0 takes the layer of the block's reference."""
    wanted = (*CURVES, *TEXTS, "MTEXT", *FILLED)
    for e in entities:
        kind = e.dxftype()
        layer = e.dxf.get("layer", "0") or "0"
        if parent_layer is not None and layer == "0":
            layer = parent_layer
        if layer.lower() == "defpoints":                     # never shown or printed in CAD
            continue
        if kind in wanted:
            yield e, layer
        elif hasattr(e, "virtual_entities") and depth < 32:
            try:
                yield from flatten(e.virtual_entities(), layer, depth + 1)
                if kind == "INSERT":
                    yield from flatten(e.attribs, layer, depth + 1)
            except Exception:                                # noqa: BLE001 left out
                continue


def _render_bare_dimensions(doc):
    """Dimensions saved without their block (some exporters): let ezdxf draw them."""
    for layout in [doc.modelspace(), *doc.blocks]:
        for d in layout.query("DIMENSION"):
            try:
                if d.get_geometry_block() is None:
                    d.override().render()
            except Exception:                                # noqa: BLE001 left out
                pass


def read_dxf(path, debug=True):
    try:
        import ezdxf
        from ezdxf import path as dxf_path
    except ImportError as exc:
        raise MissingDependency("ezdxf", "DXF drawings") from exc
    doc = ezdxf.readfile(str(path))
    msp = doc.modelspace()
    _render_bare_dimensions(doc)
    ext = list(flatten(msp))
    # chord tolerance: 1/2000 of the drawing's size
    pts_all = []
    for e, _layer in ext[:2000]:
        try:
            kind = e.dxftype()
            if kind in CURVES:
                pts_all.extend((v.x, v.y) for v in dxf_path.make_path(e).control_vertices())
            elif kind in FILLED:
                pts_all.extend(corners(e)[:, :2])
            else:
                pts_all.append(tuple(e.dxf.insert)[:2])
        except Exception:                                    # noqa: BLE001
            pass
    size = float(np.ptp(np.array(pts_all, dtype=float), axis=0).max()) if pts_all else 1.0
    tol = max(size, 1e-9) / 2000
    if any(e.dxftype() in (*TEXTS, "MTEXT") for e, _layer in ext):
        _fonts_ready()
    scratch = None
    layers, counts = {}, {"text": 0, "filled": 0}

    def add(layer, verts):
        if len(verts) >= 2:
            layers.setdefault(layer or "0", []).append(np.asarray(verts, dtype=float))

    for e, layer in ext:
        kind = e.dxftype()
        try:
            if kind in CURVES:
                add(layer, [(v.x, v.y, v.z) for v in dxf_path.make_path(e).flattening(tol)])
            elif kind in FILLED:
                add(layer, corners(e))
                counts["filled"] += 1
            elif kind in TEXTS:
                for v in _text_polylines(e, tol):
                    add(layer, v)
                counts["text"] += 1
            elif kind == "MTEXT":
                if scratch is None:
                    scratch = doc.blocks.new("*MESHVIEWER_MTEXT")   # in memory only
                for t in _mtext_parts(e, scratch):
                    for v in _text_polylines(t, tol):
                        add(layer, v)
                counts["text"] += 1
        except Exception:                                    # noqa: BLE001 skip what can't be drawn
            continue
    parts = {}
    for layer, polys in layers.items():
        pts = np.vstack(polys)
        lines, start = [], 0
        for p in polys:
            n = len(p)
            idx = np.arange(start, start + n)
            lines.append(np.column_stack([np.full(n - 1, 2), idx[:-1], idx[1:]]))
            start += n
        parts[layer] = pv.PolyData(pts, lines=np.vstack(lines).ravel()).clean()
    if not parts:
        raise ValueError("no lines, arcs, circles, curves or text in this DXF")
    units = INSUNITS.get(int(doc.header.get("$INSUNITS", 0) or 0), "")
    if debug:
        extra = [f"{counts['text']:,} texts" if counts["text"] else "",
                 f"{counts['filled']:,} filled shapes" if counts["filled"] else ""]
        print(f"  {len(parts)} layers · {sum(p.n_cells for p in parts.values()):,} segments"
              + "".join(f" · {x}" for x in extra if x) + (f" · {units}" if units else ""))
    return parts, {"dim": 2, "units": units}
