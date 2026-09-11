"""Shared paths and constants."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = Path(__file__).resolve().parent / "assets"

SITE = "https://lithuanianshorts.com"
API = SITE + "/wp-json/wp/v2"
FILM_POST_TYPE = "filmas"

# Programme defaults (from the brief)
DEFAULT_MIN_FILMS = 5
DEFAULT_MAX_FILMS = 6
DEFAULT_MAX_MINUTES = 90

# True on Vercel, where the bundle is read-only and only /tmp accepts writes.
SERVERLESS = bool(os.environ.get("VERCEL")
                  or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))


def _writable_dir(preferred: Path) -> Path:
    """A directory we can actually write to, whichever host this is."""
    if SERVERLESS:
        return Path(tempfile.gettempdir())
    try:
        preferred.mkdir(parents=True, exist_ok=True)
        return preferred
    except OSError:
        return Path(tempfile.gettempdir())


DATA_DIR = ROOT / "data"
# Only the CLI writes documents to disk; the web app streams them from memory
# and never touches this directory.
OUTPUT_DIR = _writable_dir(ROOT / "output")

# Legacy file locations. The tool reads everything from Supabase now - these are
# only what migrate_to_supabase.py imports from, once.
FILMS_JSON = DATA_DIR / "films.json"
MANUAL_JSON = DATA_DIR / "films_manual.json"
SUGGESTIONS_JSON = DATA_DIR / "keyword_suggestions.json"
APPROVED_JSON = DATA_DIR / "films_keywords.json"
SCREENINGS_XLSX = DATA_DIR / "screenings.xlsx"
