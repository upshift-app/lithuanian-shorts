"""PDF output via ReportLab, using a font that carries Lithuanian diacritics.

Documents can be produced in Lithuanian or English (``lang="lt"|"en"``).
"""
from __future__ import annotations

import datetime as _dt
import io
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

from .config import ASSETS_DIR, OUTPUT_DIR
from .fonts import register_fonts, register_serif_fonts
from .i18n import (DEFAULT_LANG, film_country, film_genre, film_language,
                   film_synopsis, film_title, film_url, minutes_label,
                   norm_lang, t)
from .programme import Programme
from .screenings import FilmReport, totals

INK = colors.HexColor("#141414")
MUTED = colors.HexColor("#6B6B6B")
RULE = colors.HexColor("#D8D8D8")
BAND = colors.HexColor("#F2F2F2")

MARGIN = 18 * mm


def _styles():
    regular, bold = register_fonts()
    base = dict(fontName=regular, textColor=INK, alignment=TA_LEFT)
    return {
        "eyebrow": ParagraphStyle("eyebrow", fontName=bold, fontSize=7.5,
                                  textColor=MUTED, spaceAfter=3, leading=10),
        "title": ParagraphStyle("title", fontName=bold, fontSize=21,
                                textColor=INK, spaceAfter=4, leading=25),
        "subtitle": ParagraphStyle("subtitle", fontName=regular, fontSize=11,
                                   textColor=MUTED, spaceAfter=3, leading=15),
        "meta": ParagraphStyle("meta", fontName=regular, fontSize=8,
                               textColor=MUTED, spaceAfter=10, leading=11),
        "h2": ParagraphStyle("h2", fontName=bold, fontSize=13.5,
                             textColor=INK, spaceBefore=8, spaceAfter=5, leading=17),
        "h3": ParagraphStyle("h3", fontName=bold, fontSize=11,
                             textColor=INK, spaceBefore=6, spaceAfter=2, leading=14),
        "body": ParagraphStyle("body", fontSize=9.5, leading=13.5,
                               spaceAfter=4, **base),
        "small": ParagraphStyle("small", fontName=regular, fontSize=8.2,
                                textColor=MUTED, leading=11.5, spaceAfter=3),
        "cell": ParagraphStyle("cell", fontName=regular, fontSize=8.6,
                               textColor=INK, leading=11.5),
        "cellb": ParagraphStyle("cellb", fontName=bold, fontSize=8.6,
                                textColor=INK, leading=11.5),
        "cellm": ParagraphStyle("cellm", fontName=regular, fontSize=7.8,
                                textColor=MUTED, leading=10),
        "_fonts": (regular, bold),
    }


def _programme_styles():
    """The programme document is set in serif, like the hand-made original."""
    regular, bold = register_serif_fonts()
    return {
        "title": ParagraphStyle("p_title", fontName=bold, fontSize=12,
                                textColor=INK, leading=15, spaceAfter=13),
        "body": ParagraphStyle("p_body", fontName=regular, fontSize=10,
                               textColor=INK, leading=13, alignment=TA_LEFT),
        "film_title": ParagraphStyle("p_film_title", fontName=bold, fontSize=10,
                                     textColor=INK, leading=13),
        "note": ParagraphStyle("p_note", fontName=regular, fontSize=9,
                               textColor=MUTED, leading=12),
        "_fonts": (regular, bold),
    }


LOGO = ASSETS_DIR / "logo.png"
LOGO_WIDTH = 48 * mm
STILL_WIDTH = 46 * mm
STILL_MAX_BYTES = 4 * 1024 * 1024
# A programme can carry a dozen stills and the whole export has to fit inside a
# serverless request, so downloading gives up once the budget is spent.
STILL_TIMEOUT = 4
STILL_BUDGET = 20
_STILL_CACHE: Dict[str, Optional[bytes]] = {}


def _logo():
    if not LOGO.is_file():
        return None
    try:
        from reportlab.lib.utils import ImageReader
        width, height = ImageReader(str(LOGO)).getSize()
        logo = Image(str(LOGO), width=LOGO_WIDTH,
                     height=LOGO_WIDTH * height / float(width))
        logo.hAlign = "LEFT"
        return logo
    except Exception:
        return None


def _still_bytes(url: str) -> Optional[bytes]:
    """Download a film still. Any failure just means the film prints without one."""
    if url in _STILL_CACHE:
        return _STILL_CACHE[url]
    data = None
    try:
        import requests
        from .scraper import HEADERS  # the site's WAF rejects the default UA
        response = requests.get(url, timeout=STILL_TIMEOUT, stream=True,
                                headers=HEADERS)
        response.raise_for_status()
        if response.headers.get("content-type", "").startswith("image/"):
            payload = response.raw.read(STILL_MAX_BYTES + 1, decode_content=True)
            if len(payload) <= STILL_MAX_BYTES:
                data = payload
    except Exception:
        data = None
    _STILL_CACHE[url] = data
    return data


def _still(film, deadline: Optional[float] = None) -> Optional[Image]:
    url = getattr(film, "image", None)
    if not url or not str(url).startswith(("http://", "https://")):
        return None
    if deadline is not None and time.monotonic() > deadline and str(url) not in _STILL_CACHE:
        return None
    data = _still_bytes(str(url))
    if not data:
        return None
    try:
        from reportlab.lib.utils import ImageReader
        width, height = ImageReader(io.BytesIO(data)).getSize()
        still = Image(io.BytesIO(data), width=STILL_WIDTH,
                      height=STILL_WIDTH * height / float(width))
        still.hAlign = "RIGHT"
        return still
    except Exception:
        return None


def _headline(film, lang: str) -> str:
    """'English title // Lithuanian title', primary title first."""
    return film_title(film, lang).replace(" / ", " // ")


def _film_meta(film, lang: str) -> str:
    """'dir. Name, genre, year, 25 min.'"""
    bits = []
    if film.director:
        bits.append(f"{t(lang, 'dir_prefix')} {film.director}")
    genre = film_genre(film, lang)
    if genre:
        bits.append(str(genre).lower())
    if film.year:
        bits.append(str(film.year))
    if film.duration_min:
        bits.append(f"{int(round(film.duration_min))} {t(lang, 'minute')}.")
    return ", ".join(bits)


def _fmt_eur(amount: float) -> str:
    return f"{amount:,.2f} EUR".replace(",", " ")


def _esc(text) -> str:
    """Escape user/site text before it goes into a ReportLab Paragraph."""
    if text is None:
        return ""
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def _table_style(bold_font: str, header: bool = True) -> TableStyle:
    cmds = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]
    if header:
        cmds += [
            ("BACKGROUND", (0, 0), (-1, 0), BAND),
            ("FONTNAME", (0, 0), (-1, 0), bold_font),
            ("LINEBELOW", (0, 0), (-1, 0), 0.7, colors.HexColor("#9A9A9A")),
        ]
    return TableStyle(cmds)


def _footer(canvas, doc):
    canvas.saveState()
    regular, _ = register_fonts()
    canvas.setFont(regular, 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(MARGIN, 12 * mm, "Lithuanian Shorts")
    canvas.drawRightString(A4[0] - MARGIN, 12 * mm, str(canvas.getPageNumber()))
    canvas.setStrokeColor(RULE)
    canvas.setLineWidth(0.4)
    canvas.line(MARGIN, 15 * mm, A4[0] - MARGIN, 15 * mm)
    canvas.restoreState()


def _build(story, path: Path, title: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(path), pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=16 * mm, bottomMargin=22 * mm,
        title=title, author="Lithuanian Shorts",
    )
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return path


def _criteria(req, lang) -> str:
    bits = []
    if req.keywords:
        bits.append(f"{t(lang, 'crit_keywords')}: " + ", ".join(req.keywords))
    if req.query:
        bits.append(f"{t(lang, 'crit_query')}: {req.query}")
    if req.genres:
        bits.append(f"{t(lang, 'crit_genre')}: " + ", ".join(req.genres))
    if req.year_from or req.year_to:
        bits.append(f"{t(lang, 'crit_years')}: "
                    f"{req.year_from or '...'}-{req.year_to or '...'}")
    bits.append(t(lang, "crit_limit", minutes=int(req.max_minutes),
                  min_films=req.min_films, max_films=req.max_films))
    if req.licensed_only:
        bits.append(t(lang, "crit_licensed"))
    return f"{t(lang, 'criteria')}: " + " | ".join(bits)


# ---------------------------------------------------------------- programme pdf

PROG_MARGIN = 25 * mm


def _build_programme(story, path: Path, title: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(path), pagesize=A4,
        leftMargin=PROG_MARGIN, rightMargin=PROG_MARGIN,
        topMargin=14 * mm, bottomMargin=18 * mm,
        title=title, author="Lithuanian Shorts",
    )
    doc.build(story)
    return path


def _film_block(film, lang: str, st, text_width: float, still_width: float,
                gap: float, deadline: Optional[float] = None):
    """Title, credits and synopsis on the left, the film still on the right."""
    text = [Paragraph(_esc(_headline(film, lang)), st["film_title"])]
    meta = _film_meta(film, lang)
    if meta:
        text.append(Paragraph(_esc(meta), st["body"]))
    synopsis = film_synopsis(film, lang)
    if synopsis:
        text.append(Spacer(1, 9))
        text.append(Paragraph(_esc(synopsis), st["body"]))

    still = _still(film, deadline)
    if still is None:
        return KeepTogether(text)

    table = Table([[text, still]], colWidths=[text_width, gap + still_width])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return KeepTogether([table])


def programme_pdf(proposals: Sequence[Programme], alternates=(),
                  path: Optional[Path] = None, subtitle: Optional[str] = None,
                  lang: Optional[str] = None, notes: bool = True) -> Path:
    """One PDF per programme. ``notes=False`` leaves out the curatorial
    apparatus - licence warnings and the like - for a document that goes out to
    a venue rather than around the office."""
    req = proposals[0].request if proposals else None
    lang = norm_lang(lang or (req.lang if req else DEFAULT_LANG))

    st = _programme_styles()
    # SimpleDocTemplate pads the frame by 6pt on each side; tables have to stay
    # inside that or they hang past the text column.
    content_width = A4[0] - 2 * PROG_MARGIN - 12
    gap = 6 * mm
    text_width = content_width - STILL_WIDTH - gap

    heading = (req.title if req and req.title else None) or t(lang, "programme_title")

    deadline = time.monotonic() + STILL_BUDGET

    story: List = []
    logo = _logo()
    if logo is not None:
        story += [logo, Spacer(1, 14 * mm)]

    for idx, prog in enumerate(proposals, 1):
        if idx > 1:
            story.append(PageBreak())

        title_text = heading
        if len(proposals) > 1:
            title_text = f"{heading} — {t(lang, 'variant', n=idx)}"
        story.append(Paragraph(_esc(title_text), st["title"]))

        intro = subtitle or (req.intro if req else None) or (req.occasion if req else None)
        if intro:
            for para in str(intro).splitlines():
                if para.strip():
                    story.append(Paragraph(_esc(para.strip()), st["body"]))
            story.append(Spacer(1, 13))

        story.append(Paragraph(
            f"<b>{t(lang, 'duration_label')}</b> "
            f"{int(round(prog.total_minutes))} {t(lang, 'minute')}.",
            st["body"]))
        if req and req.rating:
            story.append(Paragraph(_esc(req.rating), st["body"]))
        story.append(Spacer(1, 13))

        story.append(Paragraph(f"<b>{t(lang, 'films_in_programme')}</b>", st["body"]))
        story.append(Spacer(1, 16))

        for n, film in enumerate(prog.films, 1):
            if n > 1:
                story.append(Spacer(1, 18))
            story.append(_film_block(film, lang, st, text_width, STILL_WIDTH,
                                     gap, deadline))

        warnings = prog.warnings(lang) if notes else []
        if warnings:
            block = [Spacer(1, 18),
                     Paragraph(f"<b>{t(lang, 'notes')}</b>", st["note"])]
            for w in warnings:
                block.append(Paragraph("&bull; " + _esc(w), st["note"]))
            story.append(KeepTogether(block))

    if alternates:
        block = [Spacer(1, 18),
                 Paragraph(f"<b>{t(lang, 'alternates')}</b>", st["note"]),
                 Paragraph(t(lang, "alternates_note"), st["note"])]
        for film in alternates:
            bits = [_esc(x) for x in (film.year, film_genre(film, lang),
                                      minutes_label(film.duration_min, lang)) if x]
            block.append(Paragraph(
                "&bull; <b>" + _esc(film_title(film, lang)) + "</b> — "
                + " &middot; ".join(bits), st["note"]))
        story.append(KeepTogether(block))

    path = Path(path) if path else OUTPUT_DIR / _default_name(heading, "pdf", lang)
    return _build_programme(story, path, heading)


# ------------------------------------------------------------------- report pdf

def report_pdf(reports: Sequence[FilmReport], path: Optional[Path] = None,
               title: Optional[str] = None, period: Optional[str] = None,
               recipient: Optional[str] = None,
               lang: Optional[str] = None) -> Path:
    lang = norm_lang(lang)
    title = title or t(lang, "report_title")

    st = _styles()
    _regular, bold = st["_fonts"]
    content_width = A4[0] - 2 * MARGIN

    story: List = [
        Paragraph(t(lang, "brand"), st["eyebrow"]),
        Paragraph(_esc(title), st["title"]),
    ]
    if recipient:
        story.append(Paragraph(_esc(recipient), st["subtitle"]))
    line = f"{t(lang, 'prepared')} {_dt.date.today():%Y-%m-%d}"
    if period:
        line += f" &middot; {t(lang, 'period')} {_esc(period)}"
    story.append(Paragraph(line, st["meta"]))

    agg = totals(reports)
    summary = Table(
        [[Paragraph(h, st["cellb"]) for h in
          (t(lang, "th_films"), t(lang, "th_events"),
           t(lang, "th_screenings"), t(lang, "th_revenue"))],
         [Paragraph(v, st["cell"]) for v in
          (str(agg["films"]), str(agg["events"]), str(agg["screenings"]),
           _fmt_eur(agg["revenue"]))]],
        colWidths=[content_width / 4.0] * 4)
    summary.setStyle(_table_style(bold))
    story += [summary, Spacer(1, 14)]

    for report in reports:
        block = [Paragraph(_esc(report.display_title(lang)), st["h2"])]
        meta_bits = [_esc(x) for x in (
            (f"{t(lang, 'dir_prefix')} {report.director}") if report.director else None,
            str(report.year) if report.year else None,
            minutes_label(report.duration_min, lang) if report.duration_min else None,
        ) if x]
        if meta_bits:
            block.append(Paragraph(" &middot; ".join(meta_bits), st["small"]))
        facts = [f"{t(lang, 'n_screenings')}: <b>{report.total_screenings}</b>",
                 f"{t(lang, 'n_events')}: <b>{report.total_events}</b>",
                 f"{t(lang, 'th_revenue')}: <b>{_fmt_eur(report.total_revenue)}</b>"]
        if report.countries:
            facts.append(f"{t(lang, 'countries')}: " + _esc(", ".join(report.countries)))
        if report.period:
            facts.append(f"{t(lang, 'period_label')}: {report.period}")
        block.append(Paragraph(" &middot; ".join(facts), st["body"]))
        block.append(Spacer(1, 4))

        rows = [[Paragraph(h, st["cellb"]) for h in
                 (t(lang, "th_date"), t(lang, "th_event"), t(lang, "th_venue"),
                  t(lang, "th_screenings"), t(lang, "th_revenue"))]]
        for s in report.screenings:
            rows.append([
                Paragraph(s.date_label or "-", st["cell"]),
                Paragraph(_esc(s.event) or "-", st["cell"]),
                Paragraph(_esc(s.place) or "-", st["cell"]),
                Paragraph(str(s.screenings), st["cell"]),
                Paragraph(_fmt_eur(s.revenue), st["cell"]),
            ])
        rows.append([
            Paragraph("", st["cell"]), Paragraph("", st["cell"]),
            Paragraph(t(lang, "total"), st["cellb"]),
            Paragraph(str(report.total_screenings), st["cellb"]),
            Paragraph(_fmt_eur(report.total_revenue), st["cellb"]),
        ])
        widths = [content_width * w for w in (0.13, 0.32, 0.29, 0.11, 0.15)]
        table = Table(rows, colWidths=widths, repeatRows=1)
        table.setStyle(_table_style(bold))
        block += [table, Spacer(1, 14)]

        if len(report.screenings) <= 8:
            story.append(KeepTogether(block))
        else:
            story.extend(block)

    path = Path(path) if path else OUTPUT_DIR / _default_name(title, "pdf", lang)
    return _build(story, path, title)


def _default_name(title: str, ext: str, lang: str = DEFAULT_LANG) -> str:
    import re
    from .catalog import fold
    slug = re.sub(r"[^a-z0-9]+", "-", fold(title)).strip("-") or "dokumentas"
    return f"{_dt.date.today():%Y%m%d}-{slug[:60]}-{lang}.{ext}"
