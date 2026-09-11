"""Films added by hand, for titles that are not on the website.

They live in the same `films` table as the scraped archive, marked
source = 'manual'. The scraper only ever upserts the ids it found on the site,
so a re-scrape cannot touch them. Manual entries are the only films the web UI
may edit; everything else is owned by the website.

This module is a thin, stable façade over ls_tool.store so the callers (the web
app and the CLI) do not need to know where the rows actually live.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from . import store

FIRST_ID = store.FIRST_MANUAL_ID
EDITABLE = store.MANUAL_EDITABLE


def load() -> List[dict]:
    return store.manual_films()


def next_id() -> int:
    return store.manual_next_id()


def get(film_id: int) -> Optional[dict]:
    return store.manual_get(film_id)


def add(data: Dict) -> dict:
    return store.manual_add(data)


def update(film_id: int, data: Dict) -> Optional[dict]:
    return store.manual_update(film_id, data)


def delete(film_id: int) -> bool:
    return store.manual_delete(film_id)
