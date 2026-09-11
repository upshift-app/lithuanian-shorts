"""Login, session and access control for the web tool.

The session is a signed Flask cookie holding nothing but the user id; the user
record itself is read back from Supabase on each request. So revoking somebody
(disabling the account in the Users page) takes effect on their very next click,
without a session table to clean up.

FLASK_SECRET_KEY signs that cookie. Changing it signs everybody out, which is
also the emergency answer if a laptop goes missing.
"""
from __future__ import annotations

import functools
import os
from typing import Optional

from flask import abort, g, redirect, request, session, url_for

from . import store

SESSION_KEY = "uid"

# Endpoints reachable without being signed in.
PUBLIC_ENDPOINTS = {"login", "static"}


def secret_key() -> str:
    key = os.environ.get("FLASK_SECRET_KEY") or os.environ.get("SECRET_KEY")
    if key:
        return key
    if os.environ.get("VERCEL"):
        # A random key per instance would sign every user out on each cold
        # start, which looks like the app is broken. Fail loudly instead.
        raise RuntimeError(
            "FLASK_SECRET_KEY is not set. Add it in Vercel -> Settings -> "
            "Environment Variables (any long random string)."
        )
    return "dev-only-not-for-production"


def current_user() -> Optional[dict]:
    """The signed-in user, or None. Cached per request."""
    if "user" in g:
        return g.user
    uid = session.get(SESSION_KEY)
    g.user = store.user_by_id(uid) if uid else None
    if uid and g.user is None:
        # account deleted or disabled since the cookie was issued
        session.clear()
    return g.user


def sign_in(user: dict) -> None:
    session.clear()
    session[SESSION_KEY] = str(user["user_id"] if "user_id" in user else user["id"])
    session.permanent = True


def sign_out() -> None:
    session.clear()


def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if current_user() is None:
            return redirect(url_for("login", next=request.full_path))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        user = current_user()
        if user is None:
            return redirect(url_for("login", next=request.full_path))
        if not user.get("is_admin"):
            abort(403)
        return view(*args, **kwargs)
    return wrapped


# Postgres raises bare error codes; these are the ones a user can act on.
ERRORS = {
    "invalid_credentials": ("Neteisingas slaptažodis.", "Wrong password."),
    "password_mismatch": ("Slaptažodžiai nesutampa.", "The two passwords do not match."),
    "password_too_short": ("Slaptažodis turi būti bent 8 simbolių.",
                           "Password must be at least 8 characters."),
    "email_taken": ("Toks el. paštas jau užregistruotas.",
                    "That email already has an account."),
    "invalid_email": ("Neteisingas el. pašto adresas.", "Invalid email address."),
    "user_not_found": ("Vartotojas nerastas.", "No such user."),
    "last_admin": ("Negalima pašalinti paskutinio administratoriaus.",
                   "You cannot remove the last admin."),
    "cannot_demote_self": ("Negalite atimti teisių sau.", "You cannot lock yourself out."),
    "cannot_delete_self": ("Negalite ištrinti savo paskyros.",
                           "You cannot delete your own account."),
}


def readable_error(exc: Exception, lang: str = "lt") -> str:
    text = str(exc)
    for code, (lt, en) in ERRORS.items():
        if code in text:
            return lt if lang == "lt" else en
    return text
