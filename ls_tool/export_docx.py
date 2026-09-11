"""Word (.docx) output - the editable format the team asked for.

Every document can be produced in Lithuanian or English (``lang="lt"|"en"``):
the chrome comes from ls_tool.i18n, the film content from the English
counterpart pages the scraper collects.
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Optional, Sequence

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.shared import Pt, RGBColor

from .config import OUTPUT_DIR
from .i18n import (DEFAULT_LANG, film_country, film_genre, film_language,
                   film_synopsis, film_title, film_url, minutes_label,
                   norm_lang, t)
from .programme import Programme
from .screenings import FilmReport, totals

ACCENT = RGBColor(0x1A, 0x1A, 0x1A)
MUTED = RGBColor(0x6B, 0x6B, 0x6B)
BODY_FONT = "Calibri"


def _setup(doc: Document) -> None:
    style = doc.styles["Normal"]
    style.font.name = BODY_FONT
    style.font.size = Pt(10.5)


def _para(doc, text="", size=10.5, bold=False, italic=False, color=None,
          space_after=4):
    p = doc.add_paragraph()
    run = p.add_run(text)
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    if color is not None:
        run.font.color.rgb = color
    p.paragraph_format.space_after = Pt(space_after)
    return p


def _kv_line(doc, label: str, value: str, size=9.5):
    p = doc.add_paragraph()
    r1 = p.add_run(f"{label}: ")
    r1.bold = True
    r1.font.size = Pt(size)
    r2 = p.add_run(value)
    r2.font.size = Pt(size)
    p.paragraph_format.space_after = Pt(2)
    return p


def _header_row(table, labels):
    for cell, text in zip(table.rows[0].cells, labels):
        cell.text = ""
        run = cell.paragraphs[0].add_run(text)
        run.bold = True
        run.font.size = Pt(9)


def _fmt_eur(amount: float) -> str:
    return f"{amount:,.2f} EUR".replace(",", " ")


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


# ---------------------------------------------------------------- programme doc

def programme_docx(proposals: Sequence[Programme], alternates=(),
                   path: Optional[Path] = None, subtitle: Optional[str] = None,
                   lang: Optional[str] = None) -> Path:
    req = proposals[0].request if proposals else None
    lang = norm_lang(lang or (req.lang if req else DEFAULT_LANG))

    doc = Document()
    _setup(doc)

    heading = (req.title if req and req.title else None) or t(lang, "programme_title")

    _para(doc, t(lang, "brand"), size=8.5, bold=True, color=MUTED, space_after=2)
    _para(doc, heading, size=22, bold=True, color=ACCENT, space_after=2)
    if subtitle or (req and req.occasion):
        _para(doc, subtitle or req.occasion, size=11.5, italic=True, color=MUTED,
              space_after=6)
    _para(doc, f"{t(lang, 'prepared')} {_dt.date.today():%Y-%m-%d}",
          size=8.5, color=MUTED, space_after=10)

    if req:
        _para(doc, _criteria(req, lang), size=9, color=MUTED, space_after=12)

    for idx, prog in enumerate(proposals, 1):
        if idx > 1:
            doc.add_page_break()

        label = t(lang, "variant", n=idx) if len(proposals) > 1 else t(lang, "programme")
        _para(doc, label, size=9, bold=True, color=MUTED, space_after=2)
        _para(doc, t(lang, "films_runtime", n=len(prog.films),
                     runtime=prog.runtime(lang)),
              size=13, bold=True, color=ACCENT, space_after=8)

        table = doc.add_table(rows=1, cols=4)
        table.style = "Light Grid Accent 1"
        table.alignment = WD_TABLE_ALIGNMENT.LEFT
        _header_row(table, [t(lang, "th_no"), t(lang, "th_film"),
                            t(lang, "th_year_genre"), t(lang, "th_duration")])

        for n, film in enumerate(prog.films, 1):
            row = table.add_row().cells
            row[0].text = str(n)
            cell = row[1]
            cell.text = ""
            title_run = cell.paragraphs[0].add_run(film_title(film, lang))
            title_run.bold = True
            title_run.font.size = Pt(10)
            if film.director:
                sub = cell.add_paragraph()
                sub_run = sub.add_run(f"{t(lang, 'dir_prefix')} {film.director}")
                sub_run.font.size = Pt(8.5)
                sub_run.italic = True
                sub.paragraph_format.space_after = Pt(0)
            row[2].text = ", ".join(str(x) for x in
                                    (film.year, film_genre(film, lang)) if x)
            row[3].text = minutes_label(film.duration_min, lang)
            for c in row:
                for p in c.paragraphs:
                    for r in p.runs:
                        if not r.font.size:
                            r.font.size = Pt(9.5)

        doc.add_paragraph()

        for n, film in enumerate(prog.films, 1):
            _para(doc, f"{n}. {film_title(film, lang)}", size=12, bold=True,
                  color=ACCENT, space_after=2)
            meta = " · ".join(str(x) for x in (
                film.year, film_genre(film, lang),
                minutes_label(film.duration_min, lang),
                film_country(film, lang), film_language(film, lang)) if x)
            _para(doc, meta, size=9, color=MUTED, space_after=4)
            if film.director:
                _kv_line(doc, t(lang, "director"), film.director)
            synopsis = film_synopsis(film, lang)
            if synopsis:
                _para(doc, synopsis, size=10, space_after=4)
            if film.keywords:
                _kv_line(doc, t(lang, "keywords"), ", ".join(film.keywords), size=9)
            if film.licence_signed is not None:
                _kv_line(doc, t(lang, "licence"),
                         t(lang, "licence_yes" if film.licence_signed else "licence_no"),
                         size=9)
            url = film_url(film, lang)
            if url:
                _para(doc, url, size=8.5, color=MUTED, space_after=10)
            else:
                doc.add_paragraph()

        warnings = prog.warnings(lang)
        if warnings:
            _para(doc, t(lang, "notes"), size=11, bold=True, color=ACCENT, space_after=3)
            for w in warnings:
                p = doc.add_paragraph(w, style="List Bullet")
                for r in p.runs:
                    r.font.size = Pt(9)
                    r.font.color.rgb = MUTED

    if alternates:
        doc.add_page_break()
        _para(doc, t(lang, "alternates"), size=13, bold=True,
              color=ACCENT, space_after=3)
        _para(doc, t(lang, "alternates_note"), size=9, italic=True,
              color=MUTED, space_after=8)
        for film in alternates:
            p = doc.add_paragraph(style="List Bullet")
            r = p.add_run(film_title(film, lang))
            r.bold = True
            r.font.size = Pt(10)
            meta = " — " + " · ".join(str(x) for x in (
                film.year, film_genre(film, lang),
                minutes_label(film.duration_min, lang)) if x)
            if film.keywords:
                meta += " · " + ", ".join(film.keywords[:5])
            r2 = p.add_run(meta)
            r2.font.size = Pt(9)
            r2.font.color.rgb = MUTED

    path = Path(path) if path else OUTPUT_DIR / _default_name(heading, "docx", lang)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))
    return path


# ------------------------------------------------------------------- report doc

def report_docx(reports: Sequence[FilmReport], path: Optional[Path] = None,
                title: Optional[str] = None, period: Optional[str] = None,
                recipient: Optional[str] = None,
                lang: Optional[str] = None) -> Path:
    lang = norm_lang(lang)
    title = title or t(lang, "report_title")

    doc = Document()
    _setup(doc)

    _para(doc, t(lang, "brand"), size=8.5, bold=True, color=MUTED, space_after=2)
    _para(doc, title, size=22, bold=True, color=ACCENT, space_after=2)
    if recipient:
        _para(doc, recipient, size=11.5, italic=True, color=MUTED, space_after=4)
    line = f"{t(lang, 'prepared')} {_dt.date.today():%Y-%m-%d}"
    if period:
        line += f" · {t(lang, 'period')} {period}"
    _para(doc, line, size=8.5, color=MUTED, space_after=12)

    agg = totals(reports)
    _para(doc, t(lang, "summary"), size=13, bold=True, color=ACCENT, space_after=4)
    summary = doc.add_table(rows=2, cols=4)
    summary.style = "Light Grid Accent 1"
    _header_row(summary, [t(lang, "th_films"), t(lang, "th_events"),
                          t(lang, "th_screenings"), t(lang, "th_revenue")])
    values = [str(agg["films"]), str(agg["events"]), str(agg["screenings"]),
              _fmt_eur(agg["revenue"])]
    for cell, text in zip(summary.rows[1].cells, values):
        cell.text = ""
        r = cell.paragraphs[0].add_run(text)
        r.font.size = Pt(11)
        r.bold = True
    doc.add_paragraph()

    for report in reports:
        _para(doc, report.display_title(lang), size=14, bold=True, color=ACCENT,
              space_after=2)
        meta = " · ".join(str(x) for x in (
            (f"{t(lang, 'dir_prefix')} {report.director}") if report.director else None,
            report.year,
            minutes_label(report.duration_min, lang)) if x)
        if meta:
            _para(doc, meta, size=9, color=MUTED, space_after=6)

        _kv_line(doc, t(lang, "screenings_total"), str(report.total_screenings))
        _kv_line(doc, t(lang, "events_total"), str(report.total_events))
        if report.countries:
            _kv_line(doc, t(lang, "countries"), ", ".join(report.countries))
        if report.period:
            _kv_line(doc, t(lang, "period_label"), report.period)
        _kv_line(doc, t(lang, "revenue_total"), _fmt_eur(report.total_revenue))
        doc.add_paragraph()

        table = doc.add_table(rows=1, cols=5)
        table.style = "Light Grid Accent 1"
        _header_row(table, [t(lang, "th_date"), t(lang, "th_event"),
                            t(lang, "th_venue"), t(lang, "th_screenings"),
                            t(lang, "th_revenue")])

        for s in report.screenings:
            row = table.add_row().cells
            row[0].text = s.date_label or "-"
            row[1].text = s.event or "-"
            row[2].text = s.place or "-"
            row[3].text = str(s.screenings)
            row[4].text = _fmt_eur(s.revenue)
            for c in row:
                for p in c.paragraphs:
                    for r in p.runs:
                        r.font.size = Pt(9)

        total_row = table.add_row().cells
        total_row[0].text = ""
        total_row[1].text = ""
        total_row[2].text = t(lang, "total")
        total_row[3].text = str(report.total_screenings)
        total_row[4].text = _fmt_eur(report.total_revenue)
        for c in total_row:
            for p in c.paragraphs:
                for r in p.runs:
                    r.bold = True
                    r.font.size = Pt(9)

        notes = [s.notes for s in report.screenings if s.notes]
        if notes:
            _para(doc, f"{t(lang, 'notes_prefix')}: " + "; ".join(notes), size=8.5,
                  italic=True, color=MUTED, space_after=6)
        doc.add_paragraph()

    path = Path(path) if path else OUTPUT_DIR / _default_name(title, "docx", lang)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))
    return path


def _default_name(title: str, ext: str, lang: str = DEFAULT_LANG) -> str:
    import re
    from .catalog import fold
    slug = re.sub(r"[^a-z0-9]+", "-", fold(title)).strip("-") or "dokumentas"
    return f"{_dt.date.today():%Y%m%d}-{slug[:60]}-{lang}.{ext}"
