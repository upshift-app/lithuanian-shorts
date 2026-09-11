"""One-off import: the local files -> Supabase.

    pip install -r requirements.txt
    cp .env.example .env      # fill in SUPABASE_URL and SUPABASE_SERVICE_KEY
    python migrate_to_supabase.py

Reads whatever is present in ./data and writes it into the tables created by
supabase/01_schema.sql:

    films.json              -> films (source = 'site') + catalog_meta
    films_manual.json       -> films (source = 'manual')
    keyword_suggestions.json-> keyword_suggestions
    films_keywords.json     -> keyword_approvals
    screenings.xlsx         -> screenings

Safe to re-run: every table is upserted by its key, except screenings, which
have no natural key - those are skipped if the table already has rows, so a
second run cannot duplicate the log.
"""
from __future__ import annotations

import json
import sys

from dotenv import load_dotenv

load_dotenv()

from ls_tool import screenings as scr, store  # noqa: E402
from ls_tool.config import (APPROVED_JSON, DATA_DIR, FILMS_JSON,  # noqa: E402
                            MANUAL_JSON, SUGGESTIONS_JSON)


def _json(path, key, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8")).get(key, default)
    except ValueError:
        return default


def films() -> int:
    if not FILMS_JSON.exists():
        print("  films.json not found, skipped")
        return 0
    payload = json.loads(FILMS_JSON.read_text(encoding="utf-8"))
    n = store.save_catalog(payload.get("films", []), payload)
    print("  films: %d (+ vocabulary: %d keywords, %d categories)"
          % (n, len(payload.get("keywords") or []),
             len(payload.get("categories") or [])))
    return n


def manual() -> int:
    rows = _json(MANUAL_JSON, "films", [])
    if not rows:
        print("  manual films: none")
        return 0
    payload = []
    for raw in rows:
        row = {k: raw.get(k) for k in store.FILM_COLUMNS if k in raw}
        row["id"] = int(raw["id"])
        row["source"] = "manual"
        for key in ("keywords", "keywords_en", "categories", "categories_en",
                    "contacts"):
            row[key] = list(raw.get(key) or [])
        payload.append(row)
    store.client().table("films").upsert(payload).execute()
    print("  manual films: %d" % len(payload))
    return len(payload)


def suggestions() -> int:
    rows = _json(SUGGESTIONS_JSON, "suggestions", {})
    for film_id, record in rows.items():
        store.save_suggestion(int(film_id), record.get("keywords") or [],
                              record.get("keywords_en") or [],
                              model=record.get("model"),
                              error=record.get("error"))
    print("  keyword suggestions: %d" % len(rows))
    return len(rows)


def approvals() -> int:
    rows = _json(APPROVED_JSON, "films", {})
    for film_id, record in rows.items():
        store.approve(int(film_id), record.get("keywords") or [],
                      record.get("keywords_en") or [])
    print("  approved keywords: %d" % len(rows))
    return len(rows)


def screenings() -> int:
    existing = store.screening_rows()
    if existing:
        print("  screenings: %d already in the database, skipped" % len(existing))
        return 0
    rows = scr.load_from_xlsx(DATA_DIR / "screenings.xlsx")
    for row in rows:
        store.screening_add({
            "film_id": row.film_id,
            "film_title": row.film_title,
            "event": row.event,
            "venue": row.venue,
            "city": row.city,
            "country": row.country,
            "date": row.date,
            "screenings": row.screenings,
            "fee_eur": row.fee_eur,
            "programme": row.programme,
            "notes": row.notes,
        })
    print("  screenings: %d" % len(rows))
    return len(rows)


def main() -> int:
    print("importing ./data into Supabase ...")
    films()
    manual()
    suggestions()
    approvals()
    screenings()
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
