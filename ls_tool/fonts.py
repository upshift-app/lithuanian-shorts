"""Resolves a PDF font that actually carries Lithuanian diacritics.

ReportLab's built-in Type1 fonts are Latin-1 only, which mangles ą č ę ė į š ų ū ž.
This picks the first installed TrueType family that covers the full Lithuanian
alphabet and registers it with ReportLab.
"""
from __future__ import annotations

import os
from typing import Optional, Tuple

from reportlab.lib.fonts import addMapping
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from .config import ASSETS_DIR

LITHUANIAN = "ąčęėįšųūžĄČĘĖĮŠŲŪŽ„“"

# (family, regular, bold, italic, bold-italic) - searched in order
CANDIDATES = [
    ("Calibri", "calibri.ttf", "calibrib.ttf", "calibrii.ttf", "calibriz.ttf"),
    ("Arial", "arial.ttf", "arialbd.ttf", "ariali.ttf", "arialbi.ttf"),
    ("SegoeUI", "segoeui.ttf", "segoeuib.ttf", "segoeuii.ttf", "segoeuiz.ttf"),
    ("DejaVuSans", "DejaVuSans.ttf", "DejaVuSans-Bold.ttf",
     "DejaVuSans-Oblique.ttf", "DejaVuSans-BoldOblique.ttf"),
]

SEARCH_DIRS = [
    # Shipped with the project, so a Linux host (Vercel) renders ą č ę ė į š ų ū ž
    # correctly even though it has no system fonts installed at all.
    str(ASSETS_DIR / "fonts"),
    os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts"),
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Fonts"),
    "/usr/share/fonts/truetype/dejavu",
    "/usr/share/fonts/truetype",
    "/Library/Fonts",
    "/System/Library/Fonts/Supplemental",
]

_resolved: Optional[Tuple[str, str]] = None


def _find(filename: str) -> Optional[str]:
    for directory in SEARCH_DIRS:
        if not directory or not os.path.isdir(directory):
            continue
        path = os.path.join(directory, filename)
        if os.path.isfile(path):
            return path
        # case-insensitive fallback (Linux filesystems)
        try:
            for entry in os.listdir(directory):
                if entry.lower() == filename.lower():
                    return os.path.join(directory, entry)
        except OSError:
            continue
    return None


def _covers_lithuanian(path: str) -> bool:
    try:
        face = TTFont("probe", path).face
        cmap = getattr(face, "charToGlyph", None)
        if not cmap:
            return True  # cannot introspect; assume fine
        return all(ord(ch) in cmap for ch in "ąčęėįšųūž")
    except Exception:
        return False


def register_fonts() -> Tuple[str, str]:
    """Register the best available family. Returns (regular_name, bold_name)."""
    global _resolved
    if _resolved:
        return _resolved

    for family, reg, bold, ital, bi in CANDIDATES:
        reg_path = _find(reg)
        if not reg_path or not _covers_lithuanian(reg_path):
            continue

        bold_path = _find(bold) or reg_path
        ital_path = _find(ital) or reg_path
        bi_path = _find(bi) or bold_path

        try:
            pdfmetrics.registerFont(TTFont(family, reg_path))
            pdfmetrics.registerFont(TTFont(family + "-Bold", bold_path))
            pdfmetrics.registerFont(TTFont(family + "-Italic", ital_path))
            pdfmetrics.registerFont(TTFont(family + "-BoldItalic", bi_path))
        except Exception:
            continue

        # so <b>/<i> markup inside Paragraphs resolves to the right face
        addMapping(family, 0, 0, family)
        addMapping(family, 1, 0, family + "-Bold")
        addMapping(family, 0, 1, family + "-Italic")
        addMapping(family, 1, 1, family + "-BoldItalic")

        _resolved = (family, family + "-Bold")
        return _resolved

    # Last resort: ReportLab ships Bitstream Vera.
    import reportlab
    vera_dir = os.path.join(os.path.dirname(reportlab.__file__), "fonts")
    try:
        pdfmetrics.registerFont(TTFont("Vera", os.path.join(vera_dir, "Vera.ttf")))
        pdfmetrics.registerFont(TTFont("Vera-Bold", os.path.join(vera_dir, "VeraBd.ttf")))
        addMapping("Vera", 0, 0, "Vera")
        addMapping("Vera", 1, 0, "Vera-Bold")
        _resolved = ("Vera", "Vera-Bold")
    except Exception:
        _resolved = ("Helvetica", "Helvetica-Bold")
    return _resolved
