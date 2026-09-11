"""Supabase access layer - everything that used to be a file on disk.

The tool used to keep its state in data/*.json and data/*.xlsx. On Vercel the
filesystem is read-only and every request may land on a different instance, so
all of it lives in Postgres now. This module is the only place that knows that.

Auth: the Flask server holds the **service key**, which bypasses RLS. That is
deliberate - RLS denies every table to the public keys (see supabase/03_rls.sql),
and the server is the only client. The key must never reach the browser.
"""
from __future__ import annotations

import datetime as _dt
import functools
import os
from typing import Dict, List, Optional

from supabase import Client, create_client

PAGE = 1000          # Supabase returns at most 1000 rows per request


class StoreError(RuntimeError):
    pass


@functools.lru_cache(maxsize=1)
def client() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = (os.environ.get("SUPABASE_SERVICE_KEY")
           or os.environ.get("SUPABASE_SECRET_KEY"))
    if not url or not key:
        raise StoreError(
            "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set. Locally put them "
            "in .env; on Vercel add them under Settings -> Environment Variables."
        )
    return create_client(url, key)


def _all(table: str, columns: str = "*", order: Optional[str] = None) -> List[dict]:
    """Read a whole table, paging past the 1000-row response cap."""
    out: List[dict] = []
    start = 0
    while True:
        q = client().table(table).select(columns)
        if order:
            q = q.order(order)
        rows = q.range(start, start + PAGE - 1).execute().data or []
        out.extend(rows)
        if len(rows) < PAGE:
            return out
        start += PAGE


def _rpc(name: str, params: dict):
    return client().rpc(name, params).execute().data


# --------------------------------------------------------------------- catalogue

# The columns the Film dataclass understands, in the order the table declares.
FILM_COLUMNS = [
    "id", "title", "title_en", "year", "genre", "genre_en", "duration_min",
    "duration_raw", "country", "country_en", "language", "language_en",
    "director", "producer", "production_company", "distributor", "synopsis",
    "synopsis_en", "director_bio_en", "keywords", "keywords_en", "categories",
    "categories_en", "contacts", "url", "url_en", "image", "source",
    "keywords_source", "wp_modified",
]


def load_catalog_payload() -> dict:
    """The shape films.json used to have, read straight from Postgres."""
    meta_rows = client().table("catalog_meta").select("*").eq("id", 1).execute().data
    meta = meta_rows[0] if meta_rows else {}
    return {
        "films": _all("films", ",".join(FILM_COLUMNS), order="id"),
        "scraped_at": meta.get("scraped_at"),
        "keywords": meta.get("keywords") or [],
        "categories": meta.get("categories") or [],
        "keyword_map": meta.get("keyword_map") or {},
        "category_map": meta.get("category_map") or {},
    }


def save_catalog(films: List[dict], meta: dict) -> int:
    """Write a scrape result: upsert every film, then the vocabulary.

    Films are upserted rather than replaced, so hand-entered films (source =
    'manual') and any film the site has since taken down both survive. The
    scraper is the only caller.
    """
    rows = []
    now = _dt.datetime.now(_dt.timezone.utc).isoformat()
    for raw in films:
        row = {k: raw.get(k) for k in FILM_COLUMNS if k in raw}
        row["id"] = int(raw["id"])
        row["source"] = "site"
        row["scraped_at"] = now
        for key in ("keywords", "keywords_en", "categories", "categories_en",
                    "contacts"):
            row[key] = list(raw.get(key) or [])
        rows.append(row)

    for i in range(0, len(rows), 200):
        client().table("films").upsert(rows[i:i + 200]).execute()

    client().table("catalog_meta").update({
        "scraped_at": now,
        "keywords": meta.get("keywords") or [],
        "categories": meta.get("categories") or [],
        "keyword_map": meta.get("keyword_map") or {},
        "category_map": meta.get("category_map") or {},
    }).eq("id", 1).execute()
    return len(rows)


def record_scrape(films: int, ok: bool = True, note: Optional[str] = None) -> None:
    client().table("scrape_runs").insert({
        "finished_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "ok": ok, "films": films, "note": note,
    }).execute()


def last_scrape() -> Optional[dict]:
    rows = (client().table("scrape_runs").select("*")
            .order("started_at", desc=True).limit(1).execute().data)
    return rows[0] if rows else None


# ----------------------------------------------------------------- manual films

# WordPress post ids are five figures; start well clear of them.
FIRST_MANUAL_ID = 1_000_000

MANUAL_EDITABLE = [
    "title", "title_en", "year", "genre", "genre_en", "duration_min",
    "country", "country_en", "language", "language_en", "director",
    "producer", "production_company", "distributor", "synopsis", "synopsis_en",
    "keywords", "keywords_en", "url", "url_en",
]


def manual_films() -> List[dict]:
    return (client().table("films").select(",".join(FILM_COLUMNS))
            .eq("source", "manual").order("id").execute().data or [])


def manual_get(film_id: int) -> Optional[dict]:
    rows = (client().table("films").select(",".join(FILM_COLUMNS))
            .eq("id", int(film_id)).eq("source", "manual").execute().data)
    return rows[0] if rows else None


def manual_next_id() -> int:
    rows = (client().table("films").select("id").eq("source", "manual")
            .order("id", desc=True).limit(1).execute().data)
    return int(rows[0]["id"]) + 1 if rows else FIRST_MANUAL_ID


def manual_add(data: Dict) -> dict:
    row = {k: data.get(k) for k in MANUAL_EDITABLE}
    row["keywords"] = list(data.get("keywords") or [])
    row["keywords_en"] = list(data.get("keywords_en") or [])
    row["id"] = manual_next_id()
    row["source"] = "manual"
    return client().table("films").insert(row).execute().data[0]


def manual_update(film_id: int, data: Dict) -> Optional[dict]:
    row = {k: data[k] for k in MANUAL_EDITABLE if k in data}
    result = (client().table("films").update(row)
              .eq("id", int(film_id)).eq("source", "manual").execute().data)
    return result[0] if result else None


def manual_delete(film_id: int) -> bool:
    result = (client().table("films").delete()
              .eq("id", int(film_id)).eq("source", "manual").execute().data)
    return bool(result)


# ------------------------------------------------------------------- screenings

def screening_rows() -> List[dict]:
    return _all("screenings", order="id")


def screening_add(data: Dict, actor: Optional[str] = None) -> dict:
    row = {
        "film_id": int(data["film_id"]) if data.get("film_id") else None,
        "film_title": data.get("film_title") or "",
        "event": data.get("event") or None,
        "venue": data.get("venue") or None,
        "city": data.get("city") or None,
        "country": data.get("country") or None,
        "date": data["date"].isoformat() if isinstance(data.get("date"), _dt.date)
                else (data.get("date") or None),
        "screenings": int(data.get("screenings") or 1),
        "fee_eur": float(data.get("fee_eur") or 0),
        "programme": data.get("programme") or None,
        "notes": data.get("notes") or None,
        "created_by": actor,
    }
    return client().table("screenings").insert(row).execute().data[0]


def screening_delete(screening_id: int) -> bool:
    result = (client().table("screenings").delete()
              .eq("id", int(screening_id)).execute().data)
    return bool(result)


# ------------------------------------------------------------- keyword workflow

def suggestions() -> Dict[str, dict]:
    """film id (as a string, as the JSON file keyed them) -> suggestion."""
    return {str(r["film_id"]): r for r in _all("keyword_suggestions")}


def save_suggestion(film_id: int, keywords: List[str], keywords_en: List[str],
                    model: Optional[str] = None,
                    error: Optional[str] = None) -> None:
    client().table("keyword_suggestions").upsert({
        "film_id": int(film_id),
        "keywords": list(keywords or []),
        "keywords_en": list(keywords_en or []),
        "model": model,
        "error": error,
    }).execute()


def approvals() -> Dict[str, dict]:
    return {str(r["film_id"]): r for r in _all("keyword_approvals")}


def approve(film_id: int, keywords: List[str], keywords_en: List[str],
            actor: Optional[str] = None) -> None:
    client().table("keyword_approvals").upsert({
        "film_id": int(film_id),
        "keywords": list(keywords or []),
        "keywords_en": list(keywords_en or []),
        "approved_by": actor,
        "approved_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
    }).execute()


# ---------------------------------------------------------- generated documents

def document_put(token: str, kind: str, payload: dict,
                 actor: Optional[str] = None) -> None:
    client().table("generated_documents").upsert({
        "token": token, "kind": kind, "payload": payload, "created_by": actor,
    }).execute()


def document_get(token: str) -> Optional[dict]:
    rows = (client().table("generated_documents").select("*")
            .eq("token", token).execute().data)
    if not rows:
        return None
    row = rows[0]
    expires = row.get("expires_at")
    if expires and _dt.datetime.fromisoformat(expires.replace("Z", "+00:00")) \
            < _dt.datetime.now(_dt.timezone.utc):
        return None
    return row


# ------------------------------------------------------------------------ users

def verify_password(email: str, password: str) -> Optional[dict]:
    rows = _rpc("app_verify_password", {"p_email": email, "p_password": password})
    if not rows:
        return None
    return rows[0] if isinstance(rows, list) else rows


def user_by_id(user_id: str) -> Optional[dict]:
    rows = (client().table("app_users")
            .select("id, email, full_name, is_admin, is_active, must_change_password")
            .eq("id", user_id).eq("is_active", True).execute().data)
    return rows[0] if rows else None


def list_users() -> List[dict]:
    return (client().table("app_users")
            .select("id, email, full_name, is_admin, is_active, "
                    "must_change_password, last_login_at, created_at")
            .order("created_at").execute().data or [])


def create_user(actor: Optional[str], email: str, password: str,
                full_name: Optional[str] = None, is_admin: bool = False,
                must_change_password: bool = True) -> str:
    return _rpc("app_create_user", {
        "p_actor": actor, "p_email": email, "p_password": password,
        "p_full_name": full_name, "p_is_admin": is_admin,
        "p_must_change_password": must_change_password,
    })


def change_password(user_id: str, old: str, new: str, confirm: str) -> None:
    _rpc("app_change_password", {
        "p_user_id": user_id, "p_old_password": old,
        "p_new_password": new, "p_new_password_confirm": confirm,
    })


def admin_set_password(actor: str, user_id: str, new: str, confirm: str,
                       must_change_password: bool = True) -> None:
    _rpc("app_admin_set_password", {
        "p_actor": actor, "p_user_id": user_id, "p_new_password": new,
        "p_new_password_confirm": confirm,
        "p_must_change_password": must_change_password,
    })


def set_user_flags(actor: str, user_id: str, is_active: Optional[bool] = None,
                   is_admin: Optional[bool] = None) -> None:
    _rpc("app_set_user_flags", {
        "p_actor": actor, "p_user_id": user_id,
        "p_is_active": is_active, "p_is_admin": is_admin,
    })


def delete_user(actor: str, user_id: str) -> None:
    _rpc("app_delete_user", {"p_actor": actor, "p_user_id": user_id})
