"""Alternative looks for the programme and report PDFs.

The production exporters live in export_pdf.py. This module renders the same
content in several themes, so the team can compare designs side by side before
one of them replaces the current look. Build the samples with
``python scripts/build_design_variants.py``.
"""
from __future__ import annotations

import datetime as _dt
import io
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (Flowable, Image, KeepTogether, PageBreak,
                                Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from .config import ASSETS_DIR
from .export_pdf import (STILL_BUDGET, _cropped, _esc, _film_meta, _fmt_eur,
                         _headline, _still_bytes)
from .fonts import register_fonts, register_serif_fonts
from .i18n import (company_lines, film_genre, film_synopsis, film_title,
                   minutes_label, norm_lang, t)
from .screenings import totals

RED = colors.HexColor("#C8102E")
NAVY = colors.HexColor("#1A1D45")
INK = colors.HexColor("#141414")
MUTED = colors.HexColor("#6B6B6B")
RULE = colors.HexColor("#D8D8D8")
BAND = colors.HexColor("#F2F2F2")
LOGO = ASSETS_DIR / "logo.png"


@dataclass(frozen=True)
class Theme:
    key: str
    serif: bool                 # body text in serif
    header: str                 # "plain" | "rule" | "band"
    film: str                   # "rule" | "card" | "numbered"
    accent: colors.Color
    still_width: float          # points
    film_gap: float             # points between films
    margin: float = 22 * mm
    edge: bool = True           # red strip on the left of cards and tiles


THEMES = {
    "editorial": Theme("editorial", serif=True, header="rule", film="rule",
                       accent=RED, still_width=46 * mm, film_gap=26),
    "cards": Theme("cards", serif=False, header="rule", film="card",
                   accent=RED, still_width=50 * mm, film_gap=14),
    "cards-plain": Theme("cards-plain", serif=False, header="rule", film="card",
                         accent=RED, still_width=50 * mm, film_gap=14,
                         edge=False),
    # The look the agency chose (variant 07): plain cards, navy accent.
    "brand": Theme("brand", serif=False, header="rule", film="card",
                   accent=NAVY, still_width=50 * mm, film_gap=14,
                   edge=False),
    "band": Theme("band", serif=False, header="band", film="numbered",
                  accent=RED, still_width=46 * mm, film_gap=24),
    "minimal": Theme("minimal", serif=False, header="plain", film="numbered",
                     accent=INK, still_width=40 * mm, film_gap=30,
                     margin=26 * mm),
}


# ------------------------------------------------------------------- helpers

def _logo_reader(white: bool = False) -> Optional[ImageReader]:
    if not LOGO.is_file():
        return None
    if not white:
        return ImageReader(str(LOGO))
    from PIL import Image as PILImage
    img = PILImage.open(LOGO).convert("RGBA")
    solid = PILImage.new("RGBA", img.size, (255, 255, 255, 255))
    solid.putalpha(img.getchannel("A"))
    buf = io.BytesIO()
    solid.save(buf, format="PNG")
    buf.seek(0)
    return ImageReader(buf)


def _logo_flowable(width: float) -> Optional[Image]:
    reader = _logo_reader()
    if reader is None:
        return None
    w, h = reader.getSize()
    logo = Image(str(LOGO), width=width, height=width * h / float(w))
    logo.hAlign = "LEFT"
    return logo


class _Rule(Flowable):
    """A horizontal line, optionally with a short heavy accent at the left."""

    def __init__(self, width, color=RULE, thickness=0.6, accent=None,
                 accent_width=22 * mm, accent_thickness=2.4):
        super().__init__()
        self.width, self.color, self.thickness = width, color, thickness
        self.accent, self.accent_width = accent, accent_width
        self.accent_thickness = accent_thickness
        self.height = max(thickness, accent_thickness if accent else 0) + 2

    def wrap(self, *_):
        return self.width, self.height

    def draw(self):
        c = self.canv
        c.setStrokeColor(self.color)
        c.setLineWidth(self.thickness)
        c.line(0, 1, self.width, 1)
        if self.accent is not None:
            c.setStrokeColor(self.accent)
            c.setLineWidth(self.accent_thickness)
            c.line(0, 1, self.accent_width, 1)


def _styles(theme: Theme) -> dict:
    sans, sans_b = register_fonts()
    serif, serif_b = register_serif_fonts()
    body_f, body_b = (serif, serif_b) if theme.serif else (sans, sans_b)
    return {
        "eyebrow": ParagraphStyle("eyebrow", fontName=sans_b, fontSize=7.5,
                                  textColor=theme.accent, leading=10,
                                  spaceAfter=4),
        "title": ParagraphStyle("title", fontName=sans_b, fontSize=24,
                                textColor=INK, leading=28, spaceAfter=8),
        "lead": ParagraphStyle("lead", fontName=body_f, fontSize=10.5,
                               textColor=INK, leading=15, spaceAfter=6),
        "body": ParagraphStyle("body", fontName=body_f, fontSize=9.6,
                               textColor=INK, leading=13.6, spaceAfter=3,
                               alignment=TA_LEFT),
        "meta": ParagraphStyle("meta", fontName=body_f, fontSize=8.8,
                               textColor=MUTED, leading=12, spaceAfter=3),
        "film": ParagraphStyle("film", fontName=body_b, fontSize=11.5,
                               textColor=INK, leading=14.5, spaceAfter=2),
        "company": ParagraphStyle("company", fontName=sans, fontSize=7.8,
                                  textColor=MUTED, leading=11,
                                  alignment=TA_RIGHT),
        "num": ParagraphStyle("num", fontName=sans_b, fontSize=18,
                              textColor=theme.accent, leading=20),
        "small": ParagraphStyle("small", fontName=sans, fontSize=8,
                                textColor=MUTED, leading=11),
        "label": ParagraphStyle("label", fontName=sans_b, fontSize=7.5,
                                textColor=MUTED, leading=10),
        "stat": ParagraphStyle("stat", fontName=sans_b, fontSize=17,
                               textColor=INK, leading=20),
        "cell": ParagraphStyle("cell", fontName=sans, fontSize=8.6,
                               textColor=INK, leading=11.5),
        "cellb": ParagraphStyle("cellb", fontName=sans_b, fontSize=8.6,
                                textColor=INK, leading=11.5),
        "h2": ParagraphStyle("h2", fontName=sans_b, fontSize=13.5,
                             textColor=INK, leading=17, spaceAfter=2),
        "fonts": (sans, sans_b),
    }


def _page_callbacks(theme: Theme, st: dict, label: str):
    """Header band on the first page (band theme) and a footer on every page."""
    sans, sans_b = st["fonts"]
    white = _logo_reader(white=True) if theme.header == "band" else None
    dark = _logo_reader() if theme.header != "band" else None
    margin = theme.margin

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.4)
        canvas.line(margin, 15 * mm, A4[0] - margin, 15 * mm)
        canvas.setFont(sans, 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(margin, 11 * mm, "Lithuanian Shorts")
        canvas.drawRightString(A4[0] - margin, 11 * mm,
                               str(canvas.getPageNumber()))
        canvas.restoreState()

    def later_page(canvas, doc):
        footer(canvas, doc)
        # a small logo keeps every page recognisable, not just the first
        if dark is not None:
            w, h = dark.getSize()
            lw = 22 * mm
            canvas.drawImage(dark, A4[0] - margin - lw,
                             A4[1] - 5 * mm - lw * h / w, width=lw,
                             height=lw * h / w, mask="auto")
        elif white is not None:
            canvas.saveState()
            canvas.setFillColor(INK)
            canvas.rect(0, A4[1] - 9 * mm, A4[0], 9 * mm, stroke=0, fill=1)
            w, h = white.getSize()
            lw = 20 * mm
            canvas.drawImage(white, margin, A4[1] - 9 * mm + (9 * mm - lw * h / w) / 2,
                             width=lw, height=lw * h / w, mask="auto")
            canvas.restoreState()

    def first_page(canvas, doc):
        footer(canvas, doc)
        if white is not None:
            band_h = 46 * mm
            canvas.saveState()
            canvas.setFillColor(INK)
            canvas.rect(0, A4[1] - band_h, A4[0], band_h, stroke=0, fill=1)
            canvas.setFillColor(theme.accent)
            canvas.rect(0, A4[1] - band_h - 1.6 * mm, A4[0], 1.6 * mm,
                        stroke=0, fill=1)
            w, h = white.getSize()
            lw = 62 * mm
            canvas.drawImage(white, margin, A4[1] - band_h + (band_h - lw * h / w) / 2,
                             width=lw, height=lw * h / w, mask="auto")
            canvas.setFillColor(colors.white)
            canvas.setFont(sans_b, 8)
            canvas.drawRightString(A4[0] - margin, A4[1] - band_h / 2 - 3, label)
            canvas.restoreState()

    return first_page, later_page


def _header(theme: Theme, st: dict, width: float, label: str,
            company: Optional[List[str]] = None) -> List:
    """Flowables that open page one. The band theme paints its header on the
    canvas instead, so this only leaves room for it. The agency name sits under
    the logo; the company details (from Settings) sit at the opposite edge."""
    if theme.header == "band":
        return [Spacer(1, 46 * mm - 14 * mm + 10 * mm)]
    out: List = []
    logo = _logo_flowable(54 * mm if theme.header == "rule" else 44 * mm)
    left: List = [logo, Spacer(1, 3 * mm)] if logo is not None else []
    left.append(Paragraph(_esc(label.upper()), st["eyebrow"]))
    right = [Paragraph(_esc(line), st["company"]) for line in (company or [])]
    if right:
        head = Table([[left, right]], colWidths=[width * 0.55, width * 0.45])
        head.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        out.append(head)
    else:
        out += left
    out.append(Spacer(1, 5 * mm))
    if theme.header == "rule":
        out += [_Rule(width, accent=theme.accent), Spacer(1, 7 * mm)]
    return out


def _build(story, path: Path, title: str, theme: Theme, st: dict, label: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    first, later = _page_callbacks(theme, st, label)
    doc = SimpleDocTemplate(
        str(path), pagesize=A4,
        leftMargin=theme.margin, rightMargin=theme.margin,
        topMargin=20 * mm if theme.header != "band" else 18 * mm,
        bottomMargin=22 * mm, title=title, author="Lithuanian Shorts")
    doc.build(story, onFirstPage=first, onLaterPages=later)
    return path


# ------------------------------------------------------------------ programme

def _still_image(film, theme: Theme, deadline: float) -> Optional[Image]:
    url = getattr(film, "image", None)
    if not url or not str(url).startswith(("http://", "https://")):
        return None
    if time.monotonic() > deadline:
        return None
    data = _still_bytes(str(url))
    if not data:
        return None
    ratio = 3 / 2.0
    try:
        return Image(_cropped(data), width=theme.still_width,
                     height=theme.still_width / ratio)
    except Exception:
        return None


def _film_flowable(n: int, film, lang: str, theme: Theme, st: dict,
                   width: float, deadline: float):
    text: List = []
    if theme.film == "numbered":
        text.append(Paragraph(f"{n:02d}", st["num"]))
        text.append(Spacer(1, 2))
    text.append(Paragraph(_esc(_headline(film, lang)), st["film"]))
    meta = _film_meta(film, lang)
    if meta:
        text.append(Paragraph(_esc(meta), st["meta"]))
    synopsis = film_synopsis(film, lang)
    if synopsis:
        text += [Spacer(1, 4), Paragraph(_esc(synopsis), st["body"])]

    still = _still_image(film, theme, deadline)
    gap = 6 * mm
    if theme.film == "card":
        inner = width - 16
        if still is not None:
            row = [[still, text]]
            cols = [theme.still_width + gap, inner - theme.still_width - gap]
        else:
            row, cols = [[text]], [inner]
        card = Table(row, colWidths=cols)
        card.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        outer = Table([[card]], colWidths=[width])
        outer.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.6, RULE),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FAFAFA")),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 9),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ]))
        if theme.edge:
            outer.setStyle(TableStyle(
                [("LINEBEFORE", (0, 0), (0, -1), 2.4, theme.accent)]))
        return KeepTogether([outer])

    if still is None:
        return KeepTogether(text)
    table = Table([[text, still]],
                  colWidths=[width - theme.still_width - gap,
                             gap + theme.still_width])
    table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return KeepTogether([table])


def programme_pdf(programme, path: Path, theme: Theme,
                  lang: Optional[str] = None, company: Optional[dict] = None,
                  alternates: Sequence = (), notes: bool = False,
                  subtitle: Optional[str] = None) -> Path:
    """``programme`` is one programme or a list of variants (a page run each)."""
    progs = list(programme) if isinstance(programme, (list, tuple)) else [programme]
    req = progs[0].request
    lang = norm_lang(lang or req.lang)
    st = _styles(theme)
    width = A4[0] - 2 * theme.margin - 12
    deadline = time.monotonic() + STILL_BUDGET
    heading = req.title or t(lang, "programme_title")

    story: List = _header(theme, st, width, t(lang, "agency"),
                          company_lines(company, lang, split_contact=True))

    for idx, prog in enumerate(progs, 1):
        if idx > 1:
            story.append(PageBreak())
        title_text = heading
        if len(progs) > 1:
            title_text = f"{heading} - {t(lang, 'variant', n=idx)}"
        story.append(Paragraph(_esc(title_text), st["title"]))

        intro = subtitle or req.intro or req.occasion
        if intro:
            for para in str(intro).splitlines():
                if para.strip():
                    story.append(Paragraph(_esc(para.strip()), st["lead"]))
            story.append(Spacer(1, 6))

        facts = [(t(lang, "duration_label").rstrip(":"),
                  f"{int(round(prog.total_minutes))} {t(lang, 'minute')}."),
                 (t(lang, "films_in_programme").rstrip(":"), str(len(prog.films)))]
        if req.rating:
            facts.append(("", req.rating))
        strip = Table([[Paragraph(_esc(k.upper()), st["label"]) if k else ""
                        for k, _ in facts],
                       [Paragraph(_esc(v), st["cellb"]) for _, v in facts]],
                      colWidths=[width / len(facts)] * len(facts))
        strip.setStyle(TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LINEABOVE", (0, 0), (-1, 0), 0.6, RULE),
            ("LINEBELOW", (0, -1), (-1, -1), 0.6, RULE),
        ]))
        story += [strip, Spacer(1, 16)]

        for n, film in enumerate(prog.films, 1):
            if n > 1:
                story.append(Spacer(1, theme.film_gap / 2.0))
                if theme.film == "rule":
                    story.append(_Rule(width))
                story.append(Spacer(1, theme.film_gap / 2.0))
            story.append(_film_flowable(n, film, lang, theme, st, width, deadline))

        warnings = prog.warnings(lang) if notes else []
        if warnings:
            block = [Spacer(1, 18), Paragraph(t(lang, "notes").upper(), st["label"])]
            block += [Paragraph("&bull; " + _esc(w), st["small"]) for w in warnings]
            story.append(KeepTogether(block))

    if alternates:
        block = [Spacer(1, 18), Paragraph(t(lang, "alternates").upper(), st["label"]),
                 Paragraph(t(lang, "alternates_note"), st["small"])]
        for film in alternates:
            bits = [_esc(x) for x in (film.year, film_genre(film, lang),
                                      minutes_label(film.duration_min, lang)) if x]
            block.append(Paragraph(
                "&bull; <b>" + _esc(film_title(film, lang)) + "</b> - "
                + " &middot; ".join(bits), st["small"]))
        story.append(KeepTogether(block))

    return _build(story, path, heading, theme, st, t(lang, "agency"))


# --------------------------------------------------------------------- report

def report_pdf(reports: Sequence, path: Path, theme: Theme,
               title: Optional[str] = None, recipient: Optional[str] = None,
               lang: Optional[str] = None, company: Optional[dict] = None,
               period: Optional[str] = None) -> Path:
    from .i18n import t as tr
    lang = norm_lang(lang)
    st = _styles(theme)
    width = A4[0] - 2 * theme.margin - 12
    title = title or tr(lang, "report_title")

    story: List = _header(theme, st, width, tr(lang, "brand"),
                          company_lines(company, lang, split_contact=True))
    story.append(Paragraph(_esc(title), st["title"]))
    if recipient:
        story.append(Paragraph(_esc(recipient), st["lead"]))
    line = f"{tr(lang, 'prepared')} {_dt.date.today():%Y-%m-%d}"
    if period:
        line += f" &middot; {tr(lang, 'period')} {_esc(period)}"
    story.append(Paragraph(line, st["meta"]))
    story.append(Spacer(1, 8))

    agg = totals(reports)
    tiles = [(tr(lang, "th_films"), str(agg["films"])),
             (tr(lang, "th_events"), str(agg["events"])),
             (tr(lang, "th_screenings"), str(agg["screenings"])),
             (tr(lang, "th_revenue"), _fmt_eur(agg["revenue"]))]
    stat = Table([[Paragraph(_esc(k.upper()), st["label"]) for k, _ in tiles],
                  [Paragraph(_esc(v), st["stat"]) for _, v in tiles]],
                 colWidths=[width / 4.0] * 4)
    stat.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("BACKGROUND", (0, 0), (-1, -1), BAND),
    ] + ([("LINEBEFORE", (0, 0), (0, -1), 2.4, theme.accent)]
         if theme.edge else [])))
    story += [stat, Spacer(1, theme.film_gap)]

    for n, report in enumerate(reports, 1):
        head = report.display_title(lang)
        if theme.film == "numbered":
            head_row = Table(
                [[Paragraph(f"{n:02d}", st["num"]),
                  Paragraph(_esc(head), st["h2"])]],
                colWidths=[14 * mm, width - 14 * mm])
            head_row.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
            block: List = [head_row]
        else:
            block = [Paragraph(_esc(head), st["h2"])]
        bits = [_esc(x) for x in (
            f"{tr(lang, 'dir_prefix')} {report.director}" if report.director else None,
            str(report.year) if report.year else None,
            minutes_label(report.duration_min, lang) if report.duration_min else None,
        ) if x]
        if bits:
            block.append(Paragraph(" &middot; ".join(bits), st["meta"]))
        facts = [f"{tr(lang, 'n_screenings')}: <b>{report.total_screenings}</b>",
                 f"{tr(lang, 'n_events')}: <b>{report.total_events}</b>",
                 f"{tr(lang, 'th_revenue')}: <b>{_fmt_eur(report.total_revenue)}</b>"]
        if report.countries:
            facts.append(f"{tr(lang, 'countries')}: " + _esc(", ".join(report.countries)))
        block += [Paragraph(" &middot; ".join(facts), st["body"]), Spacer(1, 4)]

        rows = [[Paragraph(h, st["cellb"]) for h in
                 (tr(lang, "th_date"), tr(lang, "th_event"), tr(lang, "th_venue"),
                  tr(lang, "th_screenings"), tr(lang, "th_revenue"))]]
        for s in report.screenings:
            rows.append([Paragraph(s.date_label or "-", st["cell"]),
                         Paragraph(_esc(s.event) or "-", st["cell"]),
                         Paragraph(_esc(s.place) or "-", st["cell"]),
                         Paragraph(str(s.screenings), st["cell"]),
                         Paragraph(_fmt_eur(s.revenue), st["cell"])])
        rows.append(["", "", Paragraph(tr(lang, "total"), st["cellb"]),
                     Paragraph(str(report.total_screenings), st["cellb"]),
                     Paragraph(_fmt_eur(report.total_revenue), st["cellb"])])
        table = Table(rows, repeatRows=1,
                      colWidths=[width * w for w in (0.12, 0.30, 0.28, 0.15, 0.15)])
        cmds = [("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
                ("LINEABOVE", (0, -1), (-1, -1), 0.6, INK)]
        if theme.film == "card":
            cmds += [("ROWBACKGROUNDS", (0, 1), (-1, -2),
                      [colors.white, colors.HexColor("#F7F7F7")]),
                     ("BOX", (0, 0), (-1, -1), 0.6, RULE)]
        else:
            cmds.append(("LINEBELOW", (0, 1), (-1, -2), 0.3, RULE))
        table.setStyle(TableStyle(cmds))
        block += [table, Spacer(1, theme.film_gap / 2.0)]
        if theme.film == "rule":
            block.append(_Rule(width))
        block.append(Spacer(1, theme.film_gap / 2.0))
        story.append(KeepTogether(block) if len(report.screenings) <= 8
                     else block[0])
        if len(report.screenings) > 8:
            story.extend(block[1:])

    return _build(story, path, title, theme, st, tr(lang, "brand"))
