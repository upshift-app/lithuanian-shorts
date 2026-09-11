"""Scrapes the Lithuanian Shorts film archive into data/films.json.

Strategy:
  1. The site is WordPress and exposes a public REST API. The film archive is the
     custom post type ``filmas``. The API gives us ids, titles, permalinks and the
     two taxonomies (``post_tag`` = curatorial keywords, ``kategorija`` = category).
  2. The production metadata (year, genre, running time, country, crew) lives in
     ACF fields that are NOT exposed over REST, so each film page is fetched and the
     ``.row > .key/.value`` pairs are parsed out of the HTML.

The scrape is incremental: films whose WordPress ``modified`` timestamp has not
changed since the last run are reused from the existing films.json.
"""
from __future__ import annotations

import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional

import requests
from bs4 import BeautifulSoup

from . import store
from .config import API, FILM_POST_TYPE, SITE

HEADERS = {"User-Agent": "LithuanianShorts-InternalTool/1.0 (+programme builder)"}
TIMEOUT = 30


# --------------------------------------------------------------------------- API

def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def _paged(sess: requests.Session, url: str, per_page: int = 100) -> List[dict]:
    """Fetch every page of a WP REST collection."""
    out, page = [], 1
    while True:
        r = sess.get(url, params={"per_page": per_page, "page": page}, timeout=TIMEOUT)
        if r.status_code == 400 and page > 1:
            break  # WP returns 400 for "page beyond the last one"
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        out.extend(batch)
        total_pages = int(r.headers.get("X-WP-TotalPages", 1))
        if page >= total_pages:
            break
        page += 1
    return out


def fetch_taxonomy(sess: requests.Session, rest_base: str) -> Dict[int, str]:
    return {t["id"]: t["name"] for t in _paged(sess, f"{API}/{rest_base}")}


def fetch_taxonomy_translated(sess: requests.Session, rest_base: str,
                              term_ids, lang: str = "en",
                              workers: int = 8) -> Dict[int, str]:
    """Translated name for each term id.

    WPML keeps translated terms under their own ids, so the language-filtered
    collection cannot be joined back to the Lithuanian one. Asking for a single
    term *by its Lithuanian id* with ``wpml_language`` set does return that
    term's translation, which gives an exact 1:1 pairing.
    """
    def one(term_id: int):
        try:
            r = sess.get(f"{API}/{rest_base}/{term_id}",
                         params={"wpml_language": lang}, timeout=TIMEOUT)
            r.raise_for_status()
            return term_id, r.json().get("name")
        except (requests.RequestException, ValueError):
            return term_id, None

    out: Dict[int, str] = {}
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for term_id, name in pool.map(one, list(term_ids)):
            if name:
                out[term_id] = name
    return out


# ----------------------------------------------------------------------- parsing

_DUR_MIN_SEC = re.compile("(\\d+)\\s*['’]\\s*(\\d+)\\s*(?:''|\"|”)")
_DUR_HOURS = re.compile(r"(\d+)\s*(?:h|val\.?)\s*(\d+)", re.I)
_DUR_PLAIN = re.compile(r"(\d+(?:[.,]\d+)?)")


def parse_duration(text: Optional[str]) -> Optional[float]:
    """Turn the site's free-text running time into minutes (float).

    Handles ``17'``, ``17 min``, ``17'30''`` and ``1 val. 05``.
    """
    if not text:
        return None
    t = text.strip()

    m = _DUR_MIN_SEC.search(t)
    if m:
        val = int(m.group(1)) + int(m.group(2)) / 60.0
        return round(val, 2) if val > 0 else None

    m = _DUR_HOURS.search(t)
    if m:
        val = int(m.group(1)) * 60 + int(m.group(2))
        return float(val) if val > 0 else None

    m = _DUR_PLAIN.search(t)
    if m:
        val = float(m.group(1).replace(",", "."))
        return round(val, 2) if val > 0 else None
    return None


def parse_year(text: Optional[str]) -> Optional[int]:
    if not text:
        return None
    m = re.search(r"(?:19|20)\d{2}", str(text))
    return int(m.group(0)) if m else None


def _clean(node) -> str:
    return re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()


def parse_film_page(html: str) -> dict:
    """Pull the metadata blocks out of a single film page."""
    soup = BeautifulSoup(html, "lxml")
    root = soup.select_one("div.single-movie") or soup

    data: dict = {"info": {}, "crew": {}, "contacts": []}

    h1 = root.select_one("h1.page-title")
    data["page_title"] = _clean(h1) if h1 else None

    # On an LT page .lang-title holds the English title (and vice versa).
    other = root.select_one(".lang-title")
    data["other_title"] = _clean(other) if other else None

    alt = soup.select_one('link[rel="alternate"][hreflang="en"]')
    data["url_en"] = alt.get("href") if alt else None

    syn = root.select_one(".left .text")
    data["synopsis"] = _clean(syn) if syn else None

    img = root.select_one("img.main-img")
    if img and img.get("src"):
        data["image"] = img["src"]

    # Each ".single" block is headed by an <h2>: Informacija / Komanda / Kontaktai
    for block in root.select("div.single"):
        head = block.find(["h2", "h3"])
        section = _clean(head).lower() if head else ""
        for row in block.select("div.row"):
            key_el = row.select_one(".key")
            val_el = row.select_one(".value")
            if not key_el:
                continue
            key = _clean(key_el)
            value = _clean(val_el) if val_el else ""
            if section.startswith("informacija") or section.startswith("information"):
                data["info"][key] = value
            elif section.startswith("komanda") or section.startswith("team"):
                data["crew"][key] = value
            elif section.startswith("kontakt") or section.startswith("contact"):
                joined = " ".join(x for x in (key, value) if x)
                if joined:
                    data["contacts"].append(joined)

    bio = soup.select_one(".director-block .text")
    data["director_bio"] = _clean(bio) if bio else None
    return data


# Lithuanian labels used on the film pages -> normalised field names
INFO_MAP = {
    "metai": "year",
    "žanras": "genre",
    "trukmė": "duration",
    "gamybos šalis": "country",
    "dialogai": "language",
    "subtitrai": "subtitles",
    "formatas": "format",
}
INFO_MAP_EN = {
    "year": "year",
    "genre": "genre",
    "duration": "duration",
    "production country": "country",
    "dialogues": "language",
    "subtitles": "subtitles",
    "format": "format",
}
CREW_MAP_EN = {
    "director": "director",
    "producer": "producer",
    "script": "writer",
    "screenwriter": "writer",
    "cinematographer": "cinematographer",
    "editor": "editor",
    "sound": "sound",
    "composer": "composer",
    "production company": "production_company",
    "distributor": "distributor",
    "cast": "cast",
    "production designer": "production_designer",
}
CREW_MAP = {
    "režisierius/ė": "director",
    "režisierius": "director",
    "prodiuseris/ė": "producer",
    "scenarijaus autorius/ė": "writer",
    "operatorius/ė": "cinematographer",
    "montažo režisierius/ė": "editor",
    "garso režisierius/ė": "sound",
    "kompozitorius/ė": "composer",
    "prodiuserinė kompanija": "production_company",
    "platintojas": "distributor",
    "pagrindiniai aktoriai": "cast",
    "dailininkas/-ė": "production_designer",
}


def normalise(post: dict, page: dict, tag_names: Dict[int, str],
              cat_names: Dict[int, str], page_en: Optional[dict] = None,
              tag_names_en: Optional[Dict[int, str]] = None,
              cat_names_en: Optional[Dict[int, str]] = None) -> dict:
    tag_names_en = tag_names_en or {}
    cat_names_en = cat_names_en or {}
    info = {k.lower().rstrip(":"): v for k, v in page["info"].items()}
    crew = {k.lower().rstrip(":"): v for k, v in page["crew"].items()}

    film = {
        "id": post["id"],
        "slug": post["slug"],
        "url": post["link"],
        "title": BeautifulSoup(post["title"]["rendered"], "lxml").get_text().strip(),
        "title_en": page.get("other_title"),
        "synopsis": page.get("synopsis"),
        "image": page.get("image"),
        "keywords": sorted(tag_names.get(t, str(t)) for t in post.get("tags", [])),
        "categories": sorted(cat_names.get(c, str(c)) for c in post.get("kategorija", [])),
        "keywords_en": sorted(tag_names_en[t] for t in post.get("tags", [])
                              if t in tag_names_en),
        "categories_en": sorted(cat_names_en[c] for c in post.get("kategorija", [])
                                if c in cat_names_en),
        "contacts": page.get("contacts", []),
        "director_bio": page.get("director_bio"),
        "url_en": page.get("url_en"),
        "wp_modified": post.get("modified"),
        "wp_date": post.get("date"),
    }
    for lt, field in INFO_MAP.items():
        if not film.get(field):
            film[field] = info.get(lt)
    for lt, field in CREW_MAP.items():
        if not film.get(field):
            film[field] = crew.get(lt)

    # English counterpart page: title, synopsis and the translated info labels.
    if page_en:
        info_en = {k.lower().rstrip(":"): v for k, v in page_en["info"].items()}
        crew_en = {k.lower().rstrip(":"): v for k, v in page_en["crew"].items()}
        film["title_en"] = page_en.get("page_title") or film.get("title_en")
        film["synopsis_en"] = page_en.get("synopsis")
        film["director_bio_en"] = page_en.get("director_bio")
        for en, field in INFO_MAP_EN.items():
            value = info_en.get(en)
            if value:
                film[field + "_en"] = value
        for en, field in CREW_MAP_EN.items():
            if not film.get(field):
                film[field] = crew_en.get(en)

    film["duration_raw"] = film.get("duration")
    film["duration_min"] = parse_duration(film.get("duration_raw"))
    film.pop("duration", None)
    film.pop("duration_en", None)
    film["year"] = parse_year(film.get("year")) or parse_year(film.get("wp_date"))
    film.pop("year_en", None)
    return film


# -------------------------------------------------------------------------- main

def scrape(force: bool = False, workers: int = 8, limit: Optional[int] = None,
           with_english: bool = True, progress=print) -> List[dict]:
    sess = _session()

    progress("Fetching taxonomies ...")
    tag_names = fetch_taxonomy(sess, "tags")
    cat_names = fetch_taxonomy(sess, "kategorija")
    progress("  %d keywords, %d categories" % (len(tag_names), len(cat_names)))

    tag_names_en: Dict[int, str] = {}
    cat_names_en: Dict[int, str] = {}
    if with_english:
        progress("Fetching English taxonomy names ...")
        tag_names_en = fetch_taxonomy_translated(sess, "tags", tag_names, workers=workers)
        cat_names_en = fetch_taxonomy_translated(sess, "kategorija", cat_names,
                                                 workers=workers)
        progress("  %d/%d keywords and %d/%d categories translated"
                 % (len(tag_names_en), len(tag_names),
                    len(cat_names_en), len(cat_names)))

    progress("Fetching film index ...")
    posts = _paged(sess, f"{API}/{FILM_POST_TYPE}")
    if limit:
        posts = posts[:limit]
    progress("  %d films in the archive" % len(posts))

    # What we already hold, so only films the site actually changed get fetched.
    cached: Dict[int, dict] = {}
    if not force:
        try:
            cached = {f["id"]: f
                      for f in store.load_catalog_payload().get("films", [])
                      if f.get("source") == "site"}
        except Exception as e:      # an empty or unreachable database: full scrape
            progress("  (no cached archive: %s)" % e)
            cached = {}

    todo = [p for p in posts
            if p["id"] not in cached
            or cached[p["id"]].get("wp_modified") != p.get("modified")]
    progress("  %d unchanged (reused), %d to fetch" % (len(posts) - len(todo), len(todo)))

    results: Dict[int, dict] = {p["id"]: cached[p["id"]] for p in posts if p["id"] in cached}
    # keyword/category names may have been renamed since the cache was written
    for p in posts:
        if p["id"] in results:
            results[p["id"]]["keywords"] = sorted(
                tag_names.get(t, str(t)) for t in p.get("tags", []))
            results[p["id"]]["categories"] = sorted(
                cat_names.get(c, str(c)) for c in p.get("kategorija", []))
            if tag_names_en:
                results[p["id"]]["keywords_en"] = sorted(
                    tag_names_en[t] for t in p.get("tags", []) if t in tag_names_en)
            if cat_names_en:
                results[p["id"]]["categories_en"] = sorted(
                    cat_names_en[c] for c in p.get("kategorija", [])
                    if c in cat_names_en)

    done = [0]

    def _get(url: str) -> Optional[str]:
        for attempt in range(3):
            try:
                r = sess.get(url, timeout=TIMEOUT)
                r.raise_for_status()
                if not r.encoding:
                    r.encoding = "utf-8"
                return r.text
            except requests.RequestException:
                time.sleep(1.5 * (attempt + 1))
        return None

    def work(post: dict) -> Optional[dict]:
        html = _get(post["link"])
        if html is None:
            progress("  ! failed: %s" % post["link"])
            return None
        page = parse_film_page(html)

        page_en = None
        if with_english and page.get("url_en"):
            html_en = _get(page["url_en"])
            if html_en:
                page_en = parse_film_page(html_en)

        film = normalise(post, page, tag_names, cat_names, page_en,
                         tag_names_en, cat_names_en)
        done[0] += 1
        if done[0] % 25 == 0:
            progress("  ... %d/%d" % (done[0], len(todo)))
        return film

    if todo:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            for film in pool.map(work, todo):
                if film:
                    results[film["id"]] = film

    films = [results[p["id"]] for p in posts if p["id"] in results]
    meta = {
        "keywords": sorted(tag_names.values()),
        "categories": sorted(cat_names.values()),
        "keyword_map": {tag_names[i]: tag_names_en[i]
                        for i in tag_names if i in tag_names_en},
        "category_map": {cat_names[i]: cat_names_en[i]
                         for i in cat_names if i in cat_names_en},
    }
    store.save_catalog(films, meta)
    store.record_scrape(len(films))
    progress("Saved %d films to Supabase" % len(films))

    no_dur = [f for f in films if not f.get("duration_min")]
    no_year = [f for f in films if not f.get("year")]
    no_kw = [f for f in films if not f.get("keywords")]
    no_en = [f for f in films if not f.get("title_en")]
    progress("  running time missing: %d | year missing: %d | no keywords: %d "
             "| no English title: %d"
             % (len(no_dur), len(no_year), len(no_kw), len(no_en)))
    return films


if __name__ == "__main__":
    scrape(force="--force" in sys.argv)
