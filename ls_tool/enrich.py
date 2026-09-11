"""AI-assisted keyword suggestions for films the site never tagged.

Only 179 of the 435 archive films carry keywords (the catalogue entries from
2020 on). The rest are invisible to thematic search, which is most of what the
programme builder does. This module reads a film's synopsis and proposes
keywords **from the existing 150-term vocabulary only** - it never invents new
terms, so suggestions stay consistent with what the team curated by hand.

Nothing here writes to the catalogue. Suggestions land in
data/keyword_suggestions.json for review; only what a human approves in the
review page is written to data/films_keywords.json and merged at load time.

The OpenRouter key is reused from SlideSmith and is never copied into this
project: it resolves from OPENROUTER_API_KEY, else ~/.slidesmith/config.json.
"""
from __future__ import annotations

import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import requests

from . import store as db
from .catalog import fold

API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-4o-mini"
TIMEOUT = 60

# Optional attribution headers, same convention SlideSmith uses.
HEADERS = {
    "HTTP-Referer": "https://lithuanianshorts.com",
    "X-Title": "Lithuanian Shorts programme builder",
}

MIN_KEYWORDS = 3
MAX_KEYWORDS = 6


class EnrichError(RuntimeError):
    pass


# --------------------------------------------------------------------- api key

def resolve_api_key(explicit: Optional[str] = None) -> str:
    """Find the OpenRouter key without ever storing it in this project."""
    if explicit:
        return explicit

    from_env = os.environ.get("OPENROUTER_API_KEY")
    if from_env:
        return from_env

    # Reuse the key SlideSmith already holds (see its server/store.js).
    config = Path(os.environ.get("SLIDESMITH_DIR") or
                  (Path.home() / ".slidesmith")) / "config.json"
    if config.is_file():
        try:
            data = json.loads(config.read_text(encoding="utf-8"))
            key = (data.get("keys") or {}).get("openrouter")
            if key:
                return key
        except (ValueError, OSError):
            pass

    raise EnrichError(
        "No OpenRouter API key found. Set OPENROUTER_API_KEY, or add the key in "
        "SlideSmith's Settings (it is read from ~/.slidesmith/config.json)."
    )


# ---------------------------------------------------------------------- prompt

SYSTEM = (
    "You tag short films for a Lithuanian film agency's archive. "
    "You choose keywords ONLY from the controlled vocabulary you are given. "
    "You never invent new keywords. You answer with JSON only."
)


def build_prompt(film, vocabulary: Sequence[str]) -> str:
    bits = [f"Title: {film.title}"]
    if film.title_en:
        bits.append(f"Title (English): {film.title_en}")
    if film.year:
        bits.append(f"Year: {film.year}")
    if film.genre:
        bits.append(f"Genre: {film.genre}"
                    + (f" / {film.genre_en}" if film.genre_en else ""))
    if film.duration_min:
        bits.append(f"Running time: {int(film.duration_min)} min")
    if film.synopsis:
        bits.append(f"Synopsis (Lithuanian): {film.synopsis}")
    if film.synopsis_en:
        bits.append(f"Synopsis (English): {film.synopsis_en}")

    return (
        "Controlled vocabulary (choose only from this list, copy terms exactly):\n"
        + "\n".join(f"- {k}" for k in vocabulary)
        + "\n\nFilm:\n" + "\n".join(bits)
        + f"\n\nChoose the {MIN_KEYWORDS}-{MAX_KEYWORDS} vocabulary terms that best "
          "describe this film's subject, theme, tone and form. Prefer terms "
          "supported by the synopsis; do not guess at plot points that are not "
          "stated. If little can be said, return fewer terms rather than padding.\n"
          'Respond with JSON only: {"keywords": ["term", "term"]}'
    )


def _extract_json(text: str) -> dict:
    """Pull a JSON object out of the reply, tolerating code fences and prose."""
    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    candidate = fenced.group(1) if fenced else text
    start, end = candidate.find("{"), candidate.rfind("}")
    if start == -1 or end <= start:
        raise EnrichError("Model did not return JSON.")
    return json.loads(candidate[start:end + 1])


def _validate(raw_keywords, vocabulary: Sequence[str]) -> List[str]:
    """Keep only real vocabulary terms, restoring their canonical spelling."""
    canonical = {fold(k): k for k in vocabulary}
    out: List[str] = []
    for item in raw_keywords or []:
        match = canonical.get(fold(str(item)))
        if match and match not in out:
            out.append(match)
    return out[:MAX_KEYWORDS]


# ------------------------------------------------------------------ suggesting

def suggest_for_film(film, vocabulary: Sequence[str], api_key: str,
                     model: str = DEFAULT_MODEL,
                     session: Optional[requests.Session] = None) -> dict:
    """Ask the model for keywords for one film. Returns a suggestion record."""
    sess = session or requests.Session()
    payload = {
        "model": model,
        "temperature": 0,
        "max_tokens": 300,
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": build_prompt(film, vocabulary)},
        ],
    }
    headers = dict(HEADERS)
    headers["Authorization"] = f"Bearer {api_key}"

    last_error = None
    for attempt in range(3):
        try:
            r = sess.post(API_URL, json=payload, headers=headers, timeout=TIMEOUT)
            if r.status_code == 401:
                raise EnrichError("OpenRouter rejected the API key (401).")
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(2 * (attempt + 1))
                last_error = f"HTTP {r.status_code}"
                continue
            r.raise_for_status()
            body = r.json()
            text = body["choices"][0]["message"]["content"]
            keywords = _validate(_extract_json(text).get("keywords"), vocabulary)
            return {
                "film_id": film.id,
                "title": film.title,
                "year": film.year,
                "keywords": keywords,
                "model": model,
                "suggested_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }
        except EnrichError:
            raise
        except (requests.RequestException, ValueError, KeyError, IndexError) as e:
            last_error = str(e)
            time.sleep(1.5 * (attempt + 1))

    return {"film_id": film.id, "title": film.title, "year": film.year,
            "keywords": [], "model": model, "error": last_error or "failed"}


def untagged_films(catalog) -> List:
    """Films with no keywords at all - the ones worth suggesting for."""
    return [f for f in catalog.films if not f.keywords]


def suggest_all(catalog, films=None, model: str = DEFAULT_MODEL,
                api_key: Optional[str] = None, workers: int = 4,
                limit: Optional[int] = None, progress=print) -> Dict[str, dict]:
    """Run suggestions for many films and merge them into the suggestions file."""
    api_key = resolve_api_key(api_key)
    vocabulary = catalog.all_keywords
    if not vocabulary:
        raise EnrichError("The keyword vocabulary is empty; run a scrape first.")

    targets = list(films if films is not None else untagged_films(catalog))
    if limit:
        targets = targets[:limit]
    if not targets:
        progress("Nothing to do: every film already has keywords.")
        return load_suggestions()

    progress(f"Suggesting keywords for {len(targets)} film(s) using {model} ...")
    sess = requests.Session()
    done = [0]

    def work(film):
        record = suggest_for_film(film, vocabulary, api_key, model, sess)
        done[0] += 1
        if done[0] % 10 == 0 or done[0] == len(targets):
            progress(f"  ... {done[0]}/{len(targets)}")
        return record

    records = load_suggestions()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for record in pool.map(work, targets):
            records[str(record["film_id"])] = record
            save_suggestions_one(record, keyword_map=catalog.keyword_map)

    failed = [r for r in records.values() if r.get("error")]
    empty = [r for r in records.values()
             if not r.get("keywords") and not r.get("error")]
    progress(f"Saved {len(records)} suggestion(s)")
    if failed:
        progress(f"  {len(failed)} failed (re-run to retry)")
    if empty:
        progress(f"  {len(empty)} returned no usable keywords")
    return records


# ------------------------------------------------------------------- stores
# Suggestions and approvals are two tables, for the same reason they used to be
# two files: a re-scrape must never be able to undo approved human work.

def load_suggestions() -> Dict[str, dict]:
    return db.suggestions()


def save_suggestions_one(record: dict, keyword_map: Optional[Dict[str, str]] = None
                         ) -> None:
    keywords = list(record.get("keywords") or [])
    mapped = keyword_map or {}
    db.save_suggestion(
        record["film_id"], keywords, [mapped.get(k, k) for k in keywords],
        model=record.get("model"), error=record.get("error"),
    )


def load_approved() -> Dict[str, dict]:
    return db.approvals()


def approve(film_id: int, keywords: Sequence[str], keyword_map: Dict[str, str],
            actor: Optional[str] = None) -> dict:
    """Record human-approved keywords for one film (English mirrored via the map)."""
    keywords = [k for k in keywords if k]
    record = {
        "keywords": list(keywords),
        "keywords_en": [keyword_map.get(k, k) for k in keywords],
    }
    db.approve(film_id, record["keywords"], record["keywords_en"], actor=actor)
    return record


# ------------------------------------------------------- programme description

# Keyword tagging is a cheap classification job; a programme note is prose the
# team will sign their name under, so it gets the stronger model.
DESCRIBE_MODEL = "anthropic/claude-sonnet-5"

DESCRIBE_SYSTEM = (
    "You write programme notes for a Lithuanian short film agency. "
    "You write for the audience of a cinema or festival: plain, concrete, "
    "unhurried. Short declarative sentences. Name real things from the films - "
    "the sea, a summer garden, a night shift - rather than abstractions about "
    "the human condition. Never use the vocabulary of a press release: no "
    "tapestry, journey, exploration, delve, resonate, evoke, poignant, "
    "meditative, curated selection, invites viewers, lingers long after. "
    "You only use what the synopses actually say - you never invent plot "
    "points, awards or intentions. You answer with prose only, no headings, no "
    "lists, no quotation marks around the text."
)

DESCRIBE_LANGUAGE = {
    "lt": "Write in Lithuanian.",
    "en": "Write in English.",
}


def build_description_prompt(films: Sequence, title: Optional[str],
                             lang: str) -> str:
    """Everything the model is allowed to know about the programme."""
    blocks = []
    for n, film in enumerate(films, 1):
        bits = [f"{n}. {film.title}"]
        if film.title_en and film.title_en != film.title:
            bits.append(f"   English title: {film.title_en}")
        if film.director:
            bits.append(f"   Director: {film.director}")
        for label, value in (("Genre", film.genre), ("Year", film.year),
                             ("Running time", film.duration_min)):
            if value:
                bits.append(f"   {label}: {value}")
        synopsis = film.synopsis_en or film.synopsis
        if synopsis:
            bits.append(f"   Synopsis: {synopsis}")
        if film.keywords:
            bits.append(f"   Keywords: {', '.join(film.keywords)}")
        blocks.append("\n".join(bits))

    named = f' The programme is called "{title}".' if title else ""
    return (
        "Films in the programme:\n\n" + "\n\n".join(blocks)
        + f"\n\nWrite one paragraph introducing this programme as a whole.{named}"
        " Say what these films have in common - the places, the moods, the"
        " questions they share - and what a viewer is in for across the whole"
        " screening. Name the number of films. Do not summarise them one by one"
        " and do not list titles; the film descriptions follow underneath."
        " Four to seven sentences.\n"
        + DESCRIBE_LANGUAGE.get(lang, DESCRIBE_LANGUAGE["en"])
    )


def describe_programme(films: Sequence, title: Optional[str] = None,
                       lang: str = "lt", api_key: Optional[str] = None,
                       model: str = DESCRIBE_MODEL) -> str:
    """Draft the introductory paragraph for a programme. Editorial, not final."""
    if not films:
        raise EnrichError("The programme has no films to describe.")
    api_key = resolve_api_key(api_key)

    payload = {
        "model": model,
        "temperature": 0.6,
        "max_tokens": 600,
        "messages": [
            {"role": "system", "content": DESCRIBE_SYSTEM},
            {"role": "user",
             "content": build_description_prompt(films, title, lang)},
        ],
    }
    headers = dict(HEADERS)
    headers["Authorization"] = f"Bearer {api_key}"

    try:
        r = requests.post(API_URL, json=payload, headers=headers, timeout=TIMEOUT)
    except requests.RequestException as e:
        raise EnrichError(f"OpenRouter is not reachable: {e}")
    if r.status_code == 401:
        raise EnrichError("OpenRouter rejected the API key (401).")
    if not r.ok:
        raise EnrichError(f"OpenRouter returned HTTP {r.status_code}.")

    try:
        text = r.json()["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError):
        raise EnrichError("OpenRouter returned an unexpected response.")

    text = re.sub(r"```[a-z]*\s*|\s*```", "", text).strip()
    return text.strip('"').strip()
