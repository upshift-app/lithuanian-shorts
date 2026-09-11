"""Screening log + per-film / per-director revenue reporting.

The log is the `screenings` table, one row per screening event. Rates are not
formulaic - the team prices each case individually - so the fee is simply a
number typed into the ``fee_eur`` field, exactly as they asked.

The spreadsheet reader is still here, but only so migrate_to_supabase.py can
import the sheet the team kept before this moved into the database.
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from openpyxl import Workbook, load_workbook

from . import store
from .catalog import Catalog, fold
from .config import SCREENINGS_XLSX

COLUMNS = [
    "film_id",
    "film_title",
    "event",
    "venue",
    "city",
    "country",
    "date",
    "screenings",
    "fee_eur",
    "programme",
    "notes",
]

HEADER_LABELS = {
    "film_id": "Filmo ID",
    "film_title": "Filmo pavadinimas",
    "event": "Renginys / festivalis",
    "venue": "Vieta",
    "city": "Miestas",
    "country": "Šalis",
    "date": "Data",
    "screenings": "Seansų sk.",
    "fee_eur": "Įkainis (EUR)",
    "programme": "Programa",
    "notes": "Pastabos",
}


@dataclass
class Screening:
    film_id: Optional[int]
    film_title: str
    event: Optional[str] = None
    venue: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    date: Optional[_dt.date] = None
    screenings: int = 1
    fee_eur: float = 0.0
    programme: Optional[str] = None
    notes: Optional[str] = None
    # The database id, so a row shown in the UI can be deleted again without
    # guessing which one it was. None for rows built in memory. It kept the
    # name `row` from the spreadsheet days because the templates use it.
    row: Optional[int] = None

    @property
    def revenue(self) -> float:
        """Fee is per screening event as entered; multiplied by the count."""
        return round(float(self.fee_eur or 0.0) * int(self.screenings or 1), 2)

    @property
    def date_label(self) -> str:
        return self.date.strftime("%Y-%m-%d") if self.date else ""

    @property
    def place(self) -> str:
        bits = [b for b in (self.venue, self.city, self.country) if b]
        return ", ".join(bits)


@dataclass
class FilmReport:
    film_id: Optional[int]
    title: str
    director: Optional[str]
    year: Optional[int]
    duration_min: Optional[float]
    screenings: List[Screening] = field(default_factory=list)
    # the catalogue entry, when the row could be resolved - lets the exporters
    # render the title in whichever language the document is being produced in
    film: object = None

    def display_title(self, lang: str = "lt") -> str:
        if self.film is None:
            return self.title
        from .i18n import film_title
        return film_title(self.film, lang)

    @property
    def total_events(self) -> int:
        return len(self.screenings)

    @property
    def total_screenings(self) -> int:
        return sum(int(s.screenings or 1) for s in self.screenings)

    @property
    def total_revenue(self) -> float:
        return round(sum(s.revenue for s in self.screenings), 2)

    @property
    def countries(self) -> List[str]:
        return sorted({s.country for s in self.screenings if s.country})

    @property
    def period(self) -> str:
        dates = sorted(s.date for s in self.screenings if s.date)
        if not dates:
            return ""
        if dates[0] == dates[-1]:
            return dates[0].strftime("%Y-%m-%d")
        return f"{dates[0].strftime('%Y-%m-%d')} - {dates[-1].strftime('%Y-%m-%d')}"


# ------------------------------------------------------------------------- io

def _to_date(value) -> Optional[_dt.date]:
    if value is None or value == "":
        return None
    if isinstance(value, _dt.datetime):
        return value.date()
    if isinstance(value, _dt.date):
        return value
    text = str(value).strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%Y.%m.%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return _dt.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _to_float(value) -> float:
    if value is None or value == "":
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace("EUR", "").replace("€", "").replace(",", ".").strip()
    try:
        return float(text)
    except ValueError:
        return 0.0


def _to_int(value, default: int = 1) -> int:
    if value is None or value == "":
        return default
    try:
        return max(int(float(value)), 0)
    except (TypeError, ValueError):
        return default


def _str(value) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def load_screenings() -> List[Screening]:
    """Every screening in the log, newest last."""
    return [Screening(
        film_id=row.get("film_id"),
        film_title=row.get("film_title") or "",
        event=row.get("event"),
        venue=row.get("venue"),
        city=row.get("city"),
        country=row.get("country"),
        date=_to_date(row.get("date")),
        screenings=_to_int(row.get("screenings")),
        fee_eur=_to_float(row.get("fee_eur")),
        programme=row.get("programme"),
        notes=row.get("notes"),
        row=row.get("id"),
    ) for row in store.screening_rows()]


def load_from_xlsx(path=SCREENINGS_XLSX) -> List[Screening]:
    """Read the old spreadsheet. Only the one-off migration calls this."""
    if not path.exists():
        return []
    wb = load_workbook(path, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []

    header = [str(c).strip().lower() if c else "" for c in rows[0]]
    index = {name: header.index(name) for name in COLUMNS if name in header}
    if "film_title" not in index and "film_id" not in index:
        raise ValueError(
            f"{path.name} needs a 'film_id' or 'film_title' column. Found: {header}"
        )

    label_values = {v.lower() for v in HEADER_LABELS.values()}

    out = []
    for row_no, row in enumerate(rows[1:], start=2):
        if row is None or all(c is None or c == "" for c in row):
            continue
        # Row 2 of the template repeats the column names in Lithuanian for the
        # team's benefit; it is documentation, not a screening.
        filled = [str(c).strip().lower() for c in row if c not in (None, "")]
        if filled and all(c in label_values for c in filled):
            continue

        def cell(name):
            i = index.get(name)
            return row[i] if i is not None and i < len(row) else None

        film_id = cell("film_id")
        try:
            film_id = int(film_id) if film_id not in (None, "") else None
        except (TypeError, ValueError):
            film_id = None

        out.append(Screening(
            film_id=film_id,
            film_title=_str(cell("film_title")) or "",
            event=_str(cell("event")),
            venue=_str(cell("venue")),
            city=_str(cell("city")),
            country=_str(cell("country")),
            date=_to_date(cell("date")),
            screenings=_to_int(cell("screenings")),
            fee_eur=_to_float(cell("fee_eur")),
            programme=_str(cell("programme")),
            notes=_str(cell("notes")),
            row=row_no,
        ))
    return out


def write_template(path=SCREENINGS_XLSX, overwrite: bool = False, example_rows=()):
    if path.exists() and not overwrite:
        raise FileExistsError(f"{path} already exists (pass overwrite=True to replace)")

    wb = Workbook()
    ws = wb.active
    ws.title = "Screenings"
    ws.append(COLUMNS)
    ws.append([HEADER_LABELS[c] for c in COLUMNS])
    for cell in ws[1]:
        cell.font = cell.font.copy(bold=True)
    for cell in ws[2]:
        cell.font = cell.font.copy(italic=True)
    # Row 2 is a human-readable label row; the loader skips it because its
    # film_id cell is not numeric and its title will not match a film.
    for row in example_rows:
        ws.append([row.get(c, "") for c in COLUMNS])

    widths = {"A": 10, "B": 34, "C": 30, "D": 24, "E": 16, "F": 14,
              "G": 12, "H": 11, "I": 13, "J": 26, "K": 30}
    for col, width in widths.items():
        ws.column_dimensions[col].width = width
    ws.freeze_panes = "A3"

    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    return path



def append_screening(data: Dict, actor: Optional[str] = None) -> int:
    """Add one screening and return its database id."""
    return int(store.screening_add(data, actor=actor)["id"])


def delete_screening(screening_id: int) -> bool:
    return store.screening_delete(screening_id)


def export_xlsx(rows: Sequence[Screening], path) -> object:
    """Write the log back out as a spreadsheet, for anyone who wants it in Excel."""
    return write_template(path, overwrite=True, example_rows=[{
        "film_id": r.film_id or "",
        "film_title": r.film_title,
        "event": r.event or "",
        "venue": r.venue or "",
        "city": r.city or "",
        "country": r.country or "",
        "date": r.date_label,
        "screenings": r.screenings,
        "fee_eur": r.fee_eur,
        "programme": r.programme or "",
        "notes": r.notes or "",
    } for r in rows])

# -------------------------------------------------------------------- reporting

def build_reports(
    screenings: Sequence[Screening],
    catalog: Optional[Catalog] = None,
    film_ids: Sequence[int] = (),
    director: Optional[str] = None,
    date_from: Optional[_dt.date] = None,
    date_to: Optional[_dt.date] = None,
) -> List[FilmReport]:
    """Group screening rows into one report per film, resolving titles against
    the catalogue so the report carries director / year / running time."""
    by_id = {}
    by_title = {}
    if catalog:
        by_id = {f.id: f for f in catalog.films}
        for f in catalog.films:
            for t in (f.title, f.title_en):
                if t:
                    by_title.setdefault(fold(t), f)

    wanted_ids = {int(i) for i in film_ids}
    wanted_director = fold(director) if director else None

    grouped: Dict[object, FilmReport] = {}
    for s in screenings:
        if date_from and (s.date is None or s.date < date_from):
            continue
        if date_to and (s.date is None or s.date > date_to):
            continue

        film = by_id.get(s.film_id) if s.film_id else None
        if film is None and s.film_title:
            film = by_title.get(fold(s.film_title))

        if wanted_ids and (film.id if film else s.film_id) not in wanted_ids:
            continue
        if wanted_director:
            film_dir = film.director_folded if film else ""
            if wanted_director not in film_dir:
                continue

        key = film.id if film else fold(s.film_title)
        report = grouped.get(key)
        if report is None:
            report = FilmReport(
                film_id=film.id if film else s.film_id,
                title=film.display_title if film else (s.film_title or "(be pavadinimo)"),
                director=film.director if film else None,
                year=film.year if film else None,
                duration_min=film.duration_min if film else None,
                film=film,
            )
            grouped[key] = report
        report.screenings.append(s)

    reports = list(grouped.values())
    for r in reports:
        r.screenings.sort(key=lambda s: (s.date or _dt.date.min, s.event or ""))
    reports.sort(key=lambda r: (-r.total_revenue, r.title.lower()))
    return reports


def films_in_sheet(screenings: Sequence[Screening], catalog: Catalog) -> List:
    """The catalogue films that actually appear in the screening sheet.

    The report picker should offer these and nothing else: listing all 435
    archive films when only a handful have screenings is just noise.
    """
    by_id = {f.id: f for f in catalog.films}
    by_title = {}
    for f in catalog.films:
        for t in (f.title, f.title_en):
            if t:
                by_title.setdefault(fold(t), f)

    found, seen = [], set()
    for s in screenings:
        film = by_id.get(s.film_id) if s.film_id else None
        if film is None and s.film_title:
            film = by_title.get(fold(s.film_title))
        if film is not None and film.id not in seen:
            seen.add(film.id)
            found.append(film)
    found.sort(key=lambda f: (f.title or "").lower())
    return found


def split_directors(value: Optional[str]) -> List[str]:
    """Split a director field into individual names ("A ir B", "A, B")."""
    if not value:
        return []
    parts = value.replace(" ir ", ",").replace(" & ", ",").split(",")
    return [p.strip() for p in parts if p.strip()]


def director_options(films: Sequence) -> List[dict]:
    """Director choices for the report filter.

    Individual names, plus the exact combined credit for co-directed films, so
    a pair that always works together can be picked in one go.
    """
    singles, combos = {}, {}
    for film in films:
        names = split_directors(film.director)
        if not names:
            continue
        for name in names:
            singles.setdefault(name, set()).add(film.id)
        if len(names) > 1:
            combos.setdefault(film.director.strip(), set()).add(film.id)

    out = [{"value": n, "label": n, "film_ids": sorted(ids), "combo": False}
           for n, ids in singles.items()]
    out += [{"value": c, "label": c, "film_ids": sorted(ids), "combo": True}
            for c, ids in combos.items()]
    out.sort(key=lambda d: (d["combo"], d["label"].lower()))
    return out


def totals(reports: Sequence[FilmReport]) -> Dict[str, float]:
    return {
        "films": len(reports),
        "events": sum(r.total_events for r in reports),
        "screenings": sum(r.total_screenings for r in reports),
        "revenue": round(sum(r.total_revenue for r in reports), 2),
    }
