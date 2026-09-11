"""In-memory catalogue: loads the films from Supabase, merges licensing, filters."""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence

from . import store


def fold(text: Optional[str]) -> str:
    """Lowercase + strip Lithuanian diacritics, so 'Šokio' matches 'sokio'."""
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFKD", str(text))
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return stripped.lower().strip()


@dataclass
class Film:
    id: int
    title: str
    # everything below is optional: a hand-entered film may only carry a few of
    # these, while a scraped one normally carries them all
    title_en: Optional[str] = None
    year: Optional[int] = None
    genre: Optional[str] = None
    duration_min: Optional[float] = None
    duration_raw: Optional[str] = None
    country: Optional[str] = None
    language: Optional[str] = None
    director: Optional[str] = None
    producer: Optional[str] = None
    production_company: Optional[str] = None
    distributor: Optional[str] = None
    synopsis: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    contacts: List[str] = field(default_factory=list)
    url: Optional[str] = None
    image: Optional[str] = None
    # English counterpart page (WPML translation of the same film)
    synopsis_en: Optional[str] = None
    genre_en: Optional[str] = None
    country_en: Optional[str] = None
    language_en: Optional[str] = None
    url_en: Optional[str] = None
    director_bio_en: Optional[str] = None
    keywords_en: List[str] = field(default_factory=list)
    categories_en: List[str] = field(default_factory=list)
    # "site" for scraped films, "manual" for hand-entered ones
    source: str = "site"
    # "site" when the website tagged the film, "ai" when the keywords were
    # AI-suggested and approved in the review page
    keywords_source: str = "site"
    # filled in from the licensing spreadsheet
    licence_signed: Optional[bool] = None
    licence_until: Optional[str] = None
    rights_holder: Optional[str] = None
    licence_notes: Optional[str] = None

    @property
    def display_title(self) -> str:
        if self.title_en and fold(self.title_en) != fold(self.title):
            return f"{self.title} / {self.title_en}"
        return self.title

    @property
    def duration(self) -> float:
        return float(self.duration_min or 0.0)

    @property
    def kw_folded(self) -> set:
        """Keyword names in both languages.

        The site's tag list contains a handful of concepts entered twice, once
        with a Lithuanian name and once with an English one ("šeima" / "family").
        Matching on the union means a keyword chosen in either interface
        language finds every film tagged with either variant.
        """
        cached = self.__dict__.get("_kw_folded")
        if cached is None:
            cached = {fold(k) for k in self.keywords}
            cached |= {fold(k) for k in self.keywords_en}
            self.__dict__["_kw_folded"] = cached
        return cached

    @property
    def director_folded(self) -> str:
        cached = self.__dict__.get("_director_folded")
        if cached is None:
            cached = fold(self.director)
            self.__dict__["_director_folded"] = cached
        return cached

    @property
    def genre_folded(self) -> str:
        cached = self.__dict__.get("_genre_folded")
        if cached is None:
            cached = fold(self.genre)
            self.__dict__["_genre_folded"] = cached
        return cached

    def keywords_in(self, lang: str = "lt") -> List[str]:
        if lang == "en" and self.keywords_en:
            return self.keywords_en
        return self.keywords

    def categories_in(self, lang: str = "lt") -> List[str]:
        if lang == "en" and self.categories_en:
            return self.categories_en
        return self.categories

    def haystack(self) -> str:
        """All free text a search query may match against."""
        cached = self.__dict__.get("_haystack")
        if cached is not None:
            return cached
        parts = [self.title, self.title_en, self.synopsis, self.synopsis_en,
                 self.genre, self.genre_en, self.director, self.country,
                 " ".join(self.keywords), " ".join(self.keywords_en),
                 " ".join(self.categories)]
        cached = fold(" ".join(p for p in parts if p))
        self.__dict__["_haystack"] = cached
        return cached

    def to_dict(self) -> dict:
        d = {k: v for k, v in self.__dict__.items() if not k.startswith("_")}
        d["display_title"] = self.display_title
        return d


@dataclass
class Catalog:
    films: List[Film]
    scraped_at: Optional[str] = None
    all_keywords: List[str] = field(default_factory=list)
    all_categories: List[str] = field(default_factory=list)
    keyword_map: Dict[str, str] = field(default_factory=dict)     # lt -> en
    category_map: Dict[str, str] = field(default_factory=dict)    # lt -> en

    def __len__(self) -> int:
        return len(self.films)

    def __iter__(self):
        return iter(self.films)

    def by_id(self, film_id: int) -> Optional[Film]:
        return next((f for f in self.films if f.id == int(film_id)), None)

    @property
    def genres(self) -> List[str]:
        return sorted({f.genre for f in self.films if f.genre})

    def genre_map(self) -> Dict[str, str]:
        """Lithuanian genre name -> English, taken from the films themselves."""
        out: Dict[str, str] = {}
        for f in self.films:
            if f.genre and f.genre_en:
                out.setdefault(f.genre, f.genre_en)
        return out


    @property
    def years(self) -> List[int]:
        return sorted({f.year for f in self.films if f.year})

    def keyword_counts(self, lang: str = "lt") -> Dict[str, int]:
        """Keyword -> number of films, with names in the interface language."""
        counts: Dict[str, int] = {}
        for f in self.films:
            for k in f.keywords_in(lang):
                counts[k] = counts.get(k, 0) + 1
        return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))

    # ------------------------------------------------------------------ filtering
    def filter(
        self,
        keywords: Sequence[str] = (),
        genres: Sequence[str] = (),
        categories: Sequence[str] = (),
        year_from: Optional[int] = None,
        year_to: Optional[int] = None,
        max_duration: Optional[float] = None,
        query: Optional[str] = None,
        licensed_only: bool = False,
        require_any_keyword: bool = False,
        exclude_ids: Iterable[int] = (),
    ) -> List[Film]:
        wanted_kw = {fold(k) for k in keywords if k}
        wanted_genre = {fold(g) for g in genres if g}
        wanted_cat = {fold(c) for c in categories if c}
        q = fold(query) if query else None
        q_terms = [t for t in q.split() if t] if q else []
        excluded = {int(i) for i in exclude_ids}

        out = []
        for f in self.films:
            if f.id in excluded:
                continue
            if not f.duration:
                continue  # cannot be scheduled without a running time
            if year_from and (f.year or 0) < year_from:
                continue
            if year_to and (f.year or 9999) > year_to:
                continue
            if max_duration and f.duration > max_duration:
                continue
            if wanted_genre and fold(f.genre) not in wanted_genre:
                continue
            if wanted_cat and not ({fold(c) for c in f.categories} & wanted_cat):
                continue
            if licensed_only and f.licence_signed is not True:
                continue
            if require_any_keyword and wanted_kw and not (f.kw_folded & wanted_kw):
                continue
            if q_terms:
                hay = f.haystack()
                if not all(t in hay for t in q_terms):
                    continue
            out.append(f)
        return out


def load_catalog(with_licensing: bool = True) -> Catalog:
    """Read the whole archive from Supabase.

    Hand-entered films are rows in the same table with source = 'manual', so
    they arrive in the same query; the scraper only ever upserts its own ids,
    which is what keeps a re-scrape from wiping them.
    """
    payload = store.load_catalog_payload()

    fields = set(Film.__dataclass_fields__)
    films = []
    for raw in payload.get("films", []):
        films.append(Film(**{k: v for k, v in raw.items() if k in fields}))

    cat = Catalog(
        films=films,
        scraped_at=payload.get("scraped_at"),
        all_keywords=payload.get("keywords", []),
        all_categories=payload.get("categories", []),
        keyword_map=payload.get("keyword_map", {}),
        category_map=payload.get("category_map", {}),
    )
    apply_approved_keywords(cat)
    if with_licensing:
        apply_licensing(cat)
    return cat


def apply_approved_keywords(cat: "Catalog") -> int:
    """Fill in AI-suggested keywords a human approved in the review page.

    Only ever fills gaps: a film the website already tagged keeps its own
    keywords, so a later scrape always wins over an approved suggestion.
    """
    approved = store.approvals()
    if not approved:
        return 0

    applied = 0
    for film in cat.films:
        if film.keywords:
            continue
        record = approved.get(str(film.id))
        if not record or not record.get("keywords"):
            continue
        film.keywords = list(record.get("keywords") or [])
        film.keywords_en = list(record.get("keywords_en") or [])
        film.keywords_source = "ai"
        film.__dict__.pop("_kw_folded", None)   # drop the cached fold
        film.__dict__.pop("_haystack", None)
        applied += 1
    return applied


def apply_licensing(cat: Catalog) -> int:
    """Merge the licensing table onto the catalogue. Returns rows matched."""
    rows = store.licensing_rows()
    if not rows:
        return 0

    by_id = {f.id: f for f in cat.films}
    by_title = {}
    for f in cat.films:
        for t in (f.title, f.title_en):
            if t:
                by_title.setdefault(fold(t), f)

    matched = 0
    for row in rows:
        film = None
        if row.get("film_id"):
            try:
                film = by_id.get(int(row["film_id"]))
            except (TypeError, ValueError):
                film = None
        if film is None and row.get("film_title"):
            film = by_title.get(fold(row["film_title"]))
        if film is None:
            continue
        film.licence_signed = row.get("licence_signed")
        film.licence_until = row.get("licence_until")
        film.rights_holder = row.get("rights_holder")
        film.licence_notes = row.get("notes")
        matched += 1
    return matched
