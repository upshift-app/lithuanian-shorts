"""Lithuanian / English strings for the exported documents.

The archive itself is bilingual (every film has an English counterpart page), so
a document can be produced entirely in either language: the chrome comes from
STRINGS below and the film content from the ``*_en`` fields the scraper collects.
"""
from __future__ import annotations

from typing import Optional

LANGUAGES = ("lt", "en")
DEFAULT_LANG = "lt"

LANGUAGE_NAMES = {"lt": "Lietuvių", "en": "English"}

STRINGS = {
    "lt": {
        "brand": "LITHUANIAN SHORTS",
        "programme_title": "Filmų programos pasiūlymas",
        "report_title": "Filmų rodymų ataskaita",
        "prepared": "Parengta",
        "period": "laikotarpis",
        "criteria": "Atrankos kriterijai",
        "crit_keywords": "raktažodžiai",
        "crit_query": "paieška",
        "crit_genre": "žanras",
        "crit_years": "metai",
        "crit_limit": "iki {minutes} min, {min_films}-{max_films} filmai",
        "programme": "PROGRAMA",
        "variant": "{n} PROGRAMOS VARIANTAS",
        "films_runtime": "{n} filmai · bendra trukmė {runtime}",
        "th_no": "Nr.",
        "th_film": "Filmas",
        "th_year_genre": "Metai / žanras",
        "th_duration": "Trukmė",
        "dir_prefix": "rež.",
        "duration_label": "Trukmė:",
        "films_in_programme": "Programos filmai:",
        "director": "Režisierius/ė",
        "keywords": "Raktažodžiai",
        "notes": "Pastabos",
        "alternates": "Taip pat tematiškai tiktų",
        "alternates_note": "Šie filmai atitinka temą, bet netilpo į trukmės limitą.",
        "summary": "Suvestinė",
        "th_films": "Filmai",
        "th_events": "Renginiai",
        "th_screenings": "Seansai",
        "th_revenue": "Pajamos",
        "th_date": "Data",
        "th_event": "Renginys",
        "th_venue": "Vieta",
        "total": "IŠ VISO",
        "n_screenings": "Seansų",
        "n_events": "Renginių",
        "countries": "Šalys",
        "period_label": "Laikotarpis",
        "revenue_total": "Pajamos iš viso",
        "screenings_total": "Iš viso seansų",
        "events_total": "Renginių",
        "notes_prefix": "Pastabos",
        "no_title": "(be pavadinimo)",
        # warnings
        "w_over_time": "Bendra trukmė {runtime} viršija {limit} min ribą.",
        "w_too_few": "Programoje tik {n} filmai (prašyta {wanted}).",
        "w_missed_kw": "Neatliepti raktažodžiai: {keywords}.",
        "hour": "h",
        "minute": "min",
    },
    "en": {
        "brand": "LITHUANIAN SHORTS",
        "programme_title": "Film Programme Proposal",
        "report_title": "Film Screening Report",
        "prepared": "Prepared",
        "period": "period",
        "criteria": "Selection criteria",
        "crit_keywords": "keywords",
        "crit_query": "search",
        "crit_genre": "genre",
        "crit_years": "years",
        "crit_limit": "up to {minutes} min, {min_films}-{max_films} films",
        "programme": "PROGRAMME",
        "variant": "PROGRAMME OPTION {n}",
        "films_runtime": "{n} films · total running time {runtime}",
        "th_no": "No.",
        "th_film": "Film",
        "th_year_genre": "Year / genre",
        "th_duration": "Running time",
        "dir_prefix": "dir.",
        "duration_label": "Duration:",
        "films_in_programme": "Films in the programme:",
        "director": "Director",
        "keywords": "Keywords",
        "notes": "Notes",
        "alternates": "Also a thematic fit",
        "alternates_note": "These films match the theme but did not fit the running-time limit.",
        "summary": "Summary",
        "th_films": "Films",
        "th_events": "Events",
        "th_screenings": "Screenings",
        "th_revenue": "Revenue",
        "th_date": "Date",
        "th_event": "Event",
        "th_venue": "Venue",
        "total": "TOTAL",
        "n_screenings": "Screenings",
        "n_events": "Events",
        "countries": "Countries",
        "period_label": "Period",
        "revenue_total": "Total revenue",
        "screenings_total": "Screenings in total",
        "events_total": "Events",
        "notes_prefix": "Notes",
        "no_title": "(untitled)",
        "w_over_time": "Total running time {runtime} exceeds the {limit} min limit.",
        "w_too_few": "Only {n} films in the programme ({wanted} requested).",
        "w_missed_kw": "Keywords not covered: {keywords}.",
        "hour": "h",
        "minute": "min",
    },
}


def norm_lang(lang: Optional[str]) -> str:
    lang = (lang or DEFAULT_LANG).lower().strip()[:2]
    return lang if lang in LANGUAGES else DEFAULT_LANG


def t(lang: Optional[str], key: str, **kwargs) -> str:
    table = STRINGS[norm_lang(lang)]
    text = table.get(key, STRINGS[DEFAULT_LANG].get(key, key))
    return text.format(**kwargs) if kwargs else text


# ------------------------------------------------------- language-aware film data

def film_title(film, lang: str) -> str:
    """Primary title in the chosen language, with the other title alongside."""
    lang = norm_lang(lang)
    lt = film.title
    en = film.title_en
    if lang == "en":
        if en and en.strip().lower() != (lt or "").strip().lower():
            return f"{en} / {lt}" if lt else en
        return en or lt
    if en and en.strip().lower() != (lt or "").strip().lower():
        return f"{lt} / {en}"
    return lt


def film_synopsis(film, lang: str) -> Optional[str]:
    if norm_lang(lang) == "en":
        return getattr(film, "synopsis_en", None) or film.synopsis
    return film.synopsis


def film_genre(film, lang: str) -> Optional[str]:
    if norm_lang(lang) == "en":
        return getattr(film, "genre_en", None) or film.genre
    return film.genre


def film_country(film, lang: str) -> Optional[str]:
    if norm_lang(lang) == "en":
        return getattr(film, "country_en", None) or film.country
    return film.country


def film_language(film, lang: str) -> Optional[str]:
    if norm_lang(lang) == "en":
        return getattr(film, "language_en", None) or film.language
    return film.language


def film_url(film, lang: str) -> Optional[str]:
    if norm_lang(lang) == "en":
        return getattr(film, "url_en", None) or film.url
    return film.url


def runtime_label(minutes: float, lang: str) -> str:
    hours, mins = divmod(int(round(minutes or 0)), 60)
    if hours:
        return f"{hours} {t(lang, 'hour')} {mins:02d} {t(lang, 'minute')}"
    return f"{mins} {t(lang, 'minute')}"


def minutes_label(minutes: Optional[float], lang: str) -> str:
    if not minutes:
        return "-"
    return f"{int(round(minutes))} {t(lang, 'minute')}"
