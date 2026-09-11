"""PDF output via ReportLab, using a font that carries Lithuanian diacritics.

Documents can be produced in Lithuanian or English (``lang="lt"|"en"``).
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import List, Optional, Sequence

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

from .config import OUTPUT_DIR
from .fonts import register_fonts
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

def programme_pdf(proposals: Sequence[Programme], alternates=(),
                  path: Optional[Path] = None, subtitle: Optional[str] = None,
                  lang: Optional[str] = None) -> Path:
    req = proposals[0].request if proposals else None
    lang = norm_lang(lang or (req.lang if req else DEFAULT_LANG))

    st = _styles()
    _regular, bold = st["_fonts"]
    content_width = A4[0] - 2 * MARGIN

    heading = (req.title if req and req.title else None) or t(lang, "programme_title")

    story: List = [
        Paragraph(t(lang, "brand"), st["eyebrow"]),
        Paragraph(_esc(heading), st["title"]),
    ]
    if subtitle or (req and req.occasion):
        story.append(Paragraph(_esc(subtitle or req.occasion), st["subtitle"]))

    meta = f"{t(lang, 'prepared')} {_dt.date.today():%Y-%m-%d}"
    if req:
        meta += "<br/>" + _esc(_criteria(req, lang))
    story.append(Paragraph(meta, st["meta"]))

    for idx, prog in enumerate(proposals, 1):
        if idx > 1:
            story.append(PageBreak())

        label = t(lang, "variant", n=idx) if len(proposals) > 1 else t(lang, "programme")
        story.append(Paragraph(label, st["eyebrow"]))
        story.append(Paragraph(
            _esc(t(lang, "films_runtime", n=len(prog.films),
                   runtime=prog.runtime(lang))), st["h2"]))

        rows = [[Paragraph(h, st["cellb"]) for h in
                 (t(lang, "th_no"), t(lang, "th_film"),
                  t(lang, "th_year_genre"), t(lang, "th_duration"))]]
        for n, film in enumerate(prog.films, 1):
            title_cell = [Paragraph(_esc(film_title(film, lang)), st["cellb"])]
            if film.director:
                title_cell.append(Paragraph(
                    f"{t(lang, 'dir_prefix')} {_esc(film.director)}", st["cellm"]))
            rows.append([
                Paragraph(str(n), st["cell"]),
                title_cell,
                Paragraph(_esc(", ".join(str(x) for x in
                                         (film.year, film_genre(film, lang)) if x)),
                          st["cell"]),
                Paragraph(minutes_label(film.duration_min, lang), st["cell"]),
            ])
        widths = [content_width * w for w in (0.07, 0.53, 0.26, 0.14)]
        table = Table(rows, colWidths=widths, repeatRows=1)
        table.setStyle(_table_style(bold))
        story += [table, Spacer(1, 10)]

        for n, film in enumerate(prog.films, 1):
            block = [Paragraph(f"{n}. {_esc(film_title(film, lang))}", st["h3"])]
            info = " &middot; ".join(_esc(x) for x in (
                film.year, film_genre(film, lang),
                minutes_label(film.duration_min, lang),
                film_country(film, lang), film_language(film, lang)) if x)
            block.append(Paragraph(info, st["small"]))
            if film.director:
                block.append(Paragraph(
                    f"<b>{t(lang, 'director')}:</b> {_esc(film.director)}", st["body"]))
            synopsis = film_synopsis(film, lang)
            if synopsis:
                block.append(Paragraph(_esc(synopsis), st["body"]))
            if film.keywords:
                block.append(Paragraph(
                    f"<b>{t(lang, 'keywords')}:</b> " + _esc(", ".join(film.keywords)),
                    st["small"]))
            if film.licence_signed is not None:
                block.append(Paragraph(
                    f"<b>{t(lang, 'licence')}:</b> " +
                    t(lang, "licence_yes" if film.licence_signed else "licence_no"),
                    st["small"]))
            url = film_url(film, lang)
            if url:
                block.append(Paragraph(_esc(url), st["small"]))
            block.append(Spacer(1, 6))
            story.append(KeepTogether(block))

        warnings = prog.warnings(lang)
        if warnings:
            block = [Paragraph(t(lang, "notes"), st["h3"])]
            for w in warnings:
                block.append(Paragraph("&bull; " + _esc(w), st["small"]))
            story.append(KeepTogether(block))

    if alternates:
        story.append(PageBreak())
        story.append(Paragraph(t(lang, "alternates"), st["h2"]))
        story.append(Paragraph(t(lang, "alternates_note"), st["small"]))
        story.append(Spacer(1, 6))
        for film in alternates:
            bits = [_esc(x) for x in (film.year, film_genre(film, lang),
                                      minutes_label(film.duration_min, lang)) if x]
            line = f"<b>{_esc(film_title(film, lang))}</b> — " + " &middot; ".join(bits)
            if film.keywords:
                line += " &middot; " + _esc(", ".join(film.keywords[:5]))
            story.append(Paragraph("&bull; " + line, st["body"]))

    path = Path(path) if path else OUTPUT_DIR / _default_name(heading, "pdf", lang)
    return _build(story, path, heading)


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
