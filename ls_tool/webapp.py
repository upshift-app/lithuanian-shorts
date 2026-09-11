"""The Flask app the team clicks through.

Runs locally with `python run.py serve` and on Vercel as a serverless function
(see api/index.py). Data lives in Supabase, so both talk to the same archive.
Access is behind a login; accounts are created by an admin on the Users page.
"""
from __future__ import annotations

import dataclasses
import datetime as _dt
import os
import re
import uuid
from typing import Dict, Optional
from urllib.parse import urlparse

from flask import (Flask, abort, g, jsonify, make_response, redirect,
                   render_template, request, send_file, session, url_for)
from werkzeug.datastructures import MultiDict

from . import auth, enrich, export_docx, export_pdf, manual_films
from . import screenings as scr
from . import store
from .catalog import fold, load_catalog
from .config import OUTPUT_DIR
from .i18n import film_title, minutes_label, norm_lang
from .ui_strings import ui as ui_string
from .programme import MAX_PROPOSALS, Programme, ProgrammeRequest, generate

# How long a generated proposal stays downloadable. The handover between the
# "generate" and "download" clicks goes through the database, because on Vercel
# the two requests can be served by different instances.
SESSION_DAYS = 14


def _split(value):
    if not value:
        return []
    return [v.strip() for v in str(value).split(",") if v.strip()]


def _int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _date(value):
    try:
        return _dt.datetime.strptime(value, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- doc handover
# A generated proposal has to survive the trip from the "generate" click to the
# "download" click, which on Vercel can be two different instances. Only the
# inputs travel: film ids, scores and the request. Everything else is rebuilt
# from the catalogue, so a document can never disagree with the archive.

def _request_json(req: ProgrammeRequest) -> dict:
    return dataclasses.asdict(req)


def _request_from_json(raw: dict) -> ProgrammeRequest:
    fields = set(ProgrammeRequest.__dataclass_fields__)
    return ProgrammeRequest(**{k: v for k, v in raw.items() if k in fields})


def _rating(form) -> Optional[str]:
    """The rating is a short list of the usual indexes plus a free-text 'other'."""
    picked = (form.get("rating") or "").strip()
    if picked == "custom":
        picked = (form.get("rating_custom") or "").strip()
    return picked or None


def _download_name(title: str, option: Optional[int], fmt: str, lang: str) -> str:
    """A file name the curator can tell apart in their downloads folder."""
    slug = re.sub(r"[^a-z0-9]+", "-", fold(title)).strip("-") or "programme"
    part = f"-{option}" if option else ""
    return f"{_dt.date.today():%Y%m%d}-{slug[:60]}{part}-{lang}.{fmt}"


def _programme_json(prog: Programme) -> dict:
    return {"ids": [f.id for f in prog.films], "score": prog.score,
            "breakdown": prog.breakdown}


def _programme_from_json(raw: dict, cat, req: ProgrammeRequest) -> Programme:
    films = [f for f in (cat.by_id(i) for i in raw.get("ids") or []) if f]
    return Programme(films=films, score=raw.get("score") or 0.0,
                     breakdown=raw.get("breakdown") or {}, request=req)


def _missing_config() -> list:
    """Environment variables the app cannot run without."""
    return [name for name in ("SUPABASE_URL", "FLASK_SECRET_KEY")
            if not os.environ.get(name)] + (
        [] if (os.environ.get("SUPABASE_SERVICE_KEY")
               or os.environ.get("SUPABASE_SECRET_KEY"))
        else ["SUPABASE_SERVICE_KEY"])


def _config_error_app(missing: list) -> Flask:
    """A one-page app that says what is missing.

    Raising at import time gives an opaque "Internal Server Error" with the
    reason buried in the platform log, which is the worst possible way to learn
    that an environment variable was not set.
    """
    app = Flask(__name__)

    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def config_error(path):
        return (
            "<h1>Configuration incomplete</h1>"
            "<p>These environment variables are not set:</p><ul>"
            + "".join(f"<li><code>{name}</code></li>" for name in missing)
            + "</ul><p>Add them in Vercel under Settings &rarr; Environment "
              "Variables (Production and Preview), then redeploy. Locally they "
              "go in <code>.env</code>.</p>",
            503,
        )

    return app


def create_app() -> Flask:
    missing = _missing_config()
    if missing:
        return _config_error_app(missing)

    app = Flask(__name__)
    app.config["catalog"] = None
    app.secret_key = auth.secret_key()
    app.permanent_session_lifetime = _dt.timedelta(days=SESSION_DAYS)
    app.config.update(
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        # Vercel serves over HTTPS; locally http://127.0.0.1 must still work.
        SESSION_COOKIE_SECURE=bool(os.environ.get("VERCEL")),
    )

    UI_COOKIE = "ui_lang"

    @app.before_request
    def require_login():
        """Everything except the login page needs a signed-in user."""
        endpoint = request.endpoint or ""
        if endpoint in auth.PUBLIC_ENDPOINTS:
            return None
        if request.endpoint is None:
            # Unknown path: let Flask answer 404. Redirecting here would loop
            # forever if the host ever rewrote the path out from under us.
            return None
        user = auth.current_user()
        if user is None:
            return redirect(url_for("login", next=request.full_path))
        # A new account must set its own password before doing anything else.
        if user.get("must_change_password") and endpoint not in (
                "password", "logout"):
            return redirect(url_for("password"))
        return None

    @app.context_processor
    def inject_user():
        return {"user": auth.current_user()}

    def ui_lang() -> str:
        """Interface language: ?ui= wins, then the cookie, then Lithuanian."""
        return norm_lang(request.args.get("ui") or request.cookies.get(UI_COOKIE))

    @app.context_processor
    def inject_ui():
        lang = ui_lang()
        return {
            "ui_lang": lang,
            "other_lang": "en" if lang == "lt" else "lt",
            "ui": lambda key, **kw: ui_string(lang, key, **kw),
            "ftitle": lambda film: film_title(film, lang),
            "fkeywords": lambda film: film.keywords_in(lang),
            "fgenre": lambda film: (film.genre_en or film.genre) if lang == "en"
                                   else film.genre,
        }

    @app.route("/lang/<code>")
    def set_lang(code):
        # Return to the page the switch was clicked on, but never follow a
        # referrer pointing somewhere else - that would be an open redirect.
        target = url_for("index")
        referrer = request.referrer
        if referrer:
            ref = urlparse(referrer)
            if not ref.netloc or ref.netloc == urlparse(request.host_url).netloc:
                target = ref.path + (f"?{ref.query}" if ref.query else "")

        resp = make_response(redirect(target))
        resp.set_cookie(UI_COOKIE, norm_lang(code), max_age=60 * 60 * 24 * 365,
                        samesite="Lax")
        return resp

    def catalog(refresh: bool = False):
        if refresh or app.config["catalog"] is None:
            app.config["catalog"] = load_catalog()
        return app.config["catalog"]

    # ------------------------------------------------------------------ access
    @app.route("/login", methods=["GET", "POST"])
    def login():
        if auth.current_user() is not None:
            return redirect(url_for("index"))

        error = None
        email = ""
        if request.method == "POST":
            email = (request.form.get("email") or "").strip()
            password = request.form.get("password") or ""
            user = store.verify_password(email, password)
            if user is None:
                error = ui_string(ui_lang(), "login_failed")
            else:
                auth.sign_in(user)
                # Only ever redirect inside this site.
                target = request.form.get("next") or url_for("index")
                if urlparse(target).netloc:
                    target = url_for("index")
                return redirect(target)

        return render_template("login.html", error=error, email=email,
                               next=request.args.get("next") or "")

    @app.route("/logout", methods=["GET", "POST"])
    def logout():
        auth.sign_out()
        return redirect(url_for("login"))

    @app.route("/password", methods=["GET", "POST"])
    def password():
        user = auth.current_user()
        error = saved = None
        if request.method == "POST":
            try:
                store.change_password(
                    user["id"],
                    request.form.get("old_password") or "",
                    request.form.get("new_password") or "",
                    request.form.get("new_password_confirm") or "",
                )
                g.pop("user", None)      # must_change_password just cleared
                saved = True
            except Exception as e:      # the RPC raises a bare error code
                error = auth.readable_error(e, ui_lang())
        return render_template("password.html", error=error, saved=saved)

    @app.route("/users", methods=["GET", "POST"])
    @auth.admin_required
    def users():
        me = auth.current_user()
        error = notice = None

        if request.method == "POST":
            action = request.form.get("action")
            target = request.form.get("user_id")
            try:
                if action == "create":
                    store.create_user(
                        me["id"],
                        (request.form.get("email") or "").strip(),
                        request.form.get("password") or "",
                        full_name=(request.form.get("full_name") or "").strip() or None,
                        is_admin=bool(request.form.get("is_admin")),
                    )
                    notice = "created"
                elif action == "set_password":
                    store.admin_set_password(
                        me["id"], target,
                        request.form.get("password") or "",
                        request.form.get("password_confirm") or "")
                    notice = "password_set"
                elif action == "toggle_active":
                    store.set_user_flags(
                        me["id"], target,
                        is_active=request.form.get("value") == "1")
                    notice = "updated"
                elif action == "toggle_admin":
                    store.set_user_flags(
                        me["id"], target,
                        is_admin=request.form.get("value") == "1")
                    notice = "updated"
                elif action == "delete":
                    store.delete_user(me["id"], target)
                    notice = "deleted"
            except Exception as e:
                error = auth.readable_error(e, ui_lang())

        return render_template("users.html", users=store.list_users(),
                               error=error, notice=notice, me=me)

    # ------------------------------------------------------------- programme
    @app.route("/", methods=["GET", "POST"])
    def index():
        cat = catalog()
        ctx = {
            "catalog": cat,
            "keyword_counts": cat.keyword_counts(ui_lang()),
            "genres": cat.genres,
            "genre_map": cat.genre_map(),
            "categories": cat.all_categories,
            "years": cat.years,
            # year inputs are bounded by what the archive actually contains
            "year_min": cat.years[0] if cat.years else None,
            "year_max": cat.years[-1] if cat.years else None,
            "max_proposals": MAX_PROPOSALS,
            "form": request.form if request.method == "POST" else MultiDict(),
        }

        if request.method != "POST":
            return render_template("index.html", **ctx)

        selected = request.form.getlist("keywords") + _split(
            request.form.get("keywords_extra"))
        req = ProgrammeRequest(
            title=request.form.get("title") or "",
            occasion=request.form.get("occasion") or None,
            intro=request.form.get("intro") or None,
            rating=_rating(request.form),
            keywords=selected,
            query=request.form.get("query") or None,
            genres=request.form.getlist("genres"),
            categories=request.form.getlist("categories"),
            year_from=_int(request.form.get("year_from")),
            year_to=_int(request.form.get("year_to")),
            min_films=_int(request.form.get("min_films"), 5),
            max_films=_int(request.form.get("max_films"), 6),
            max_minutes=_float(request.form.get("max_minutes"), 90.0),
            licensed_only=bool(request.form.get("licensed_only")),
            require_any_keyword=bool(request.form.get("strict_keywords")),
            exclude_ids=[int(x) for x in _split(request.form.get("exclude_ids"))
                         if x.isdigit()],
            pin_ids=[int(x) for x in _split(request.form.get("pin_ids"))
                     if x.isdigit()],
            n_proposals=_int(request.form.get("n_proposals"), 2) or 2,
            all_proposals=(request.form.get("n_proposals") == "all"),
            seed=_int(request.form.get("seed")),
            lang=norm_lang(request.form.get("lang") or ui_lang()),
        )

        proposals, alternates, pool = generate(cat, req)
        token = uuid.uuid4().hex[:12]
        # Only the inputs are stored - film ids, scores and the request. The
        # document itself is rebuilt on download, from the same catalogue.
        store.document_put(token, "programme", {
            "request": _request_json(req),
            "proposals": [_programme_json(p) for p in proposals],
            # alternates are individual films, not programmes
            "alternates": [f.id for f in alternates],
        }, actor=auth.current_user()["id"])

        ctx.update({
            "proposals": proposals,
            "alternates": alternates,
            "pool_size": len(pool),
            "found_total": req.found_total,
            "token": token,
            "req": req,
            "submitted": True,
        })
        return render_template("index.html", **ctx)

    def _stored_programme(token):
        """The films behind a generated proposal, rebuilt from the catalogue."""
        entry = store.document_get(token)
        if not entry or entry["kind"] != "programme":
            abort(404)
        payload = entry["payload"]
        req = _request_from_json(payload["request"])
        cat = catalog()
        proposals = [_programme_from_json(p, cat, req) for p in payload["proposals"]]
        alternates = [f for f in (cat.by_id(i)
                                  for i in payload.get("alternates") or [])
                      if f is not None]
        if not proposals:
            abort(404)
        return req, proposals, alternates

    @app.route("/api/keepalive")
    def keepalive():
        """Touched by a Vercel cron job twice a week.

        A free Supabase project is paused after a week without traffic, which
        would take the archive offline until someone restored it by hand. One
        cheap read is enough to count as activity. Public on purpose: cron
        invocations carry no session and do not follow redirects, so a login
        redirect here would silently do nothing.
        """
        secret = os.environ.get("CRON_SECRET")
        if secret and request.headers.get("Authorization") != f"Bearer {secret}":
            return jsonify({"error": "unauthorized"}), 401
        try:
            rows = (store.client().table("films").select("id")
                    .limit(1).execute().data)
        except Exception as e:  # the point is to report it, not to crash
            return jsonify({"ok": False, "error": str(e)[:200]}), 502
        return jsonify({"ok": True, "films_reachable": bool(rows),
                        "at": _dt.datetime.utcnow().isoformat(timespec="seconds")})

    @app.route("/describe/<token>", methods=["POST"])
    def describe(token):
        """Draft the programme's introductory paragraph. The team edits it."""
        req, proposals, _alternates = _stored_programme(token)
        option = _int(request.form.get("option")) or 1
        if not 1 <= option <= len(proposals):
            abort(404)
        try:
            text = enrich.describe_programme(
                proposals[option - 1].films, req.title or None, req.lang)
        except enrich.EnrichError as e:
            return jsonify({"error": str(e)}), 502
        return jsonify({"text": text})

    @app.route("/download/<token>.<fmt>", methods=["GET", "POST"])
    def download(token, fmt):
        if fmt not in ("docx", "pdf"):
            abort(404)
        req, proposals, alternates = _stored_programme(token)

        # The description can be written, drafted or edited right before the
        # download, so what the form posts wins over what was stored.
        if request.method == "POST" and "intro" in request.form:
            req.intro = (request.form.get("intro") or "").strip() or None

        # The curator picks one option and gets a document containing only that
        # programme - the alternatives are a working aid, not something a venue
        # should ever read.
        option = _int(request.args.get("option"))
        if option is not None:
            if not 1 <= option <= len(proposals):
                abort(404)
            proposals = [proposals[option - 1]]

        lang = req.lang
        title = req.title or ""
        name = _download_name(title or "programme", option, fmt, lang)
        path = OUTPUT_DIR / name
        if option is not None:
            alternates = []
        if fmt == "docx":
            path = export_docx.programme_docx(proposals, alternates, path=path,
                                              lang=lang)
        else:
            path = export_pdf.programme_pdf(proposals, alternates, path=path,
                                            lang=lang, notes=option is None)
        return send_file(str(path), as_attachment=True, download_name=name)

    # --------------------------------------------------------- screening log
    @app.route("/screenings", methods=["GET", "POST"])
    def screening_log():
        cat = catalog()
        errors, notice = [], request.args.get("msg")
        form = MultiDict()

        if request.method == "POST":
            form = request.form
            lang = ui_lang()
            film = cat.by_id(_int(form.get("film_id"))) if form.get("film_id") else None
            title = (form.get("film_title") or "").strip()
            if film is None and not title:
                errors.append(ui_string(lang, "s_err_film"))

            count = _int(form.get("screenings"), 1)
            if count is None or count < 1:
                errors.append(ui_string(lang, "s_err_count"))
            fee = _float(form.get("fee_eur"), 0.0)
            if fee is None or fee < 0:
                errors.append(ui_string(lang, "s_err_fee"))
            raw_date = (form.get("date") or "").strip()
            date = _date(raw_date) if raw_date else None
            if raw_date and date is None:
                errors.append(ui_string(lang, "s_err_date"))

            if not errors:
                scr.append_screening({
                    "film_id": film.id if film else "",
                    # the plain title is stored too, so a row stays readable
                    # on its own; the film_id is what the report matches on
                    "film_title": film.title if film else title,
                    "event": (form.get("event") or "").strip(),
                    "venue": (form.get("venue") or "").strip(),
                    "city": (form.get("city") or "").strip(),
                    "country": (form.get("country") or "").strip(),
                    "date": date or "",
                    "screenings": count,
                    "fee_eur": fee,
                    "programme": (form.get("programme") or "").strip(),
                    "notes": (form.get("notes") or "").strip(),
                }, actor=auth.current_user()["id"])
                return redirect(url_for("screening_log", msg="added"))

        try:
            rows = scr.load_screenings()
            error = None
        except ValueError as e:
            rows, error = [], str(e)

        # newest first: the row just added is the one the user wants to see
        entries = []
        for row in sorted(rows, key=lambda r: (r.date or _dt.date.min, r.row or 0),
                          reverse=True):
            film = cat.by_id(row.film_id) if row.film_id else None
            entries.append({"row": row, "film": film})

        return render_template(
            "screenings.html", catalog=cat,
            films=sorted(cat.films, key=lambda f: (f.title or "").lower()),
            entries=entries, error=error, errors=errors, form=form,
            notice={"added": "s_added", "deleted": "s_deleted"}.get(notice),
            totals={"n": len(rows),
                    "s": sum(int(r.screenings or 1) for r in rows),
                    "v": round(sum(r.revenue for r in rows), 2)},
        )

    @app.route("/screenings/<int:screening_id>/delete", methods=["POST"])
    def screening_delete(screening_id):
        if not scr.delete_screening(screening_id):
            abort(404)
        return redirect(url_for("screening_log", msg="deleted"))

    # --------------------------------------------------------------- reports
    @app.route("/reports", methods=["GET", "POST"])
    def reports():
        cat = catalog()
        try:
            rows = scr.load_screenings()
            error = None
        except ValueError as e:
            rows, error = [], str(e)

        sheet_films = scr.films_in_sheet(rows, cat)
        ctx = {
            "catalog": cat,
            "has_rows": bool(rows),
            "error": error,
            "form": request.form if request.method == "POST" else MultiDict(),
            # Only films that actually appear in the sheet can be reported on.
            "sheet_films": sheet_films,
            "directors": scr.director_options(sheet_films),
        }

        if request.method != "POST" or not rows:
            return render_template("reports.html", **ctx)

        film_ids = [int(x) for x in request.form.getlist("film_ids") if str(x).isdigit()]
        built = scr.build_reports(
            rows, cat,
            film_ids=film_ids,
            director=request.form.get("director") or None,
            date_from=_date(request.form.get("date_from")),
            date_to=_date(request.form.get("date_to")),
        )
        token = uuid.uuid4().hex[:12]
        period = None
        if request.form.get("date_from") or request.form.get("date_to"):
            period = (f"{request.form.get('date_from') or '...'} - "
                      f"{request.form.get('date_to') or '...'}")
        # As with programmes, only the filters are stored; the report is
        # rebuilt from the screening log when the document is downloaded.
        store.document_put(token, "report", {
            "film_ids": film_ids,
            "director": request.form.get("director") or None,
            "date_from": request.form.get("date_from") or None,
            "date_to": request.form.get("date_to") or None,
            "title": request.form.get("title") or None,
            "recipient": request.form.get("recipient") or None,
            "period": period,
            "lang": norm_lang(request.form.get("lang") or ui_lang()),
        }, actor=auth.current_user()["id"])

        ctx.update({
            "reports": built,
            "totals": scr.totals(built),
            "token": token,
            "submitted": True,
        })
        return render_template("reports.html", **ctx)

    @app.route("/reports/download/<token>.<fmt>")
    def download_report(token, fmt):
        entry = store.document_get(token)
        if not entry or entry["kind"] != "report" or fmt not in ("docx", "pdf"):
            abort(404)
        payload = entry["payload"]
        built = scr.build_reports(
            scr.load_screenings(), catalog(),
            film_ids=payload.get("film_ids") or (),
            director=payload.get("director"),
            date_from=_date(payload.get("date_from")),
            date_to=_date(payload.get("date_to")),
        )
        kwargs = dict(title=payload.get("title"), period=payload.get("period"),
                      recipient=payload.get("recipient"), lang=payload.get("lang"))
        if fmt == "docx":
            path = export_docx.report_docx(built, **kwargs)
        else:
            path = export_pdf.report_pdf(built, **kwargs)
        return send_file(str(path), as_attachment=True, download_name=path.name)

    # --------------------------------------------------------------- archive
    @app.route("/films")
    def films():
        cat = catalog()
        q = request.args.get("q") or None
        results = cat.filter(query=q) if q else cat.films
        # Hand-added films first: they are the ones the team manages here, and
        # the listing is capped, so a new entry must never be pushed off the page.
        results = sorted(results, key=lambda f: (f.source != "manual",
                                                 -(f.year or 0), f.title or ""))
        msg = request.args.get("msg")
        notice = {"added": "nf_added", "updated": "nf_updated",
                  "deleted": "nf_deleted"}.get(msg)
        return render_template("films.html", catalog=cat, films=results[:300],
                               q=q or "", total=len(results),
                               shown=min(300, len(results)), notice=notice)

    # ------------------------------------------- AI keyword review
    PER_PAGE = 20
    PAGE_SIZES = (20, 50, 100)

    @app.route("/keywords", methods=["GET", "POST"])
    def keywords():
        from . import enrich

        cat = catalog()
        vocabulary = cat.all_keywords
        canonical = {fold(k): k for k in vocabulary}

        saved = 0
        if request.method == "POST":
            # Only films rendered on this page are touched, so paging through
            # the list never clears approvals made on another page.
            for raw_id in request.form.getlist("film_ids"):
                if not raw_id.isdigit():
                    continue
                picked = request.form.getlist(f"kw_{raw_id}")
                picked += _split(request.form.get(f"extra_{raw_id}"))
                # keep only real vocabulary terms, in canonical spelling
                clean, seen = [], set()
                for term in picked:
                    match = canonical.get(fold(term))
                    if match and match not in seen:
                        seen.add(match)
                        clean.append(match)
                enrich.approve(int(raw_id), clean, cat.keyword_map,
                               actor=auth.current_user()["id"])
                saved += 1
            catalog(refresh=True)
            cat = catalog()

        suggestions = enrich.load_suggestions()
        approved = enrich.load_approved()

        # A film needs review while the site has not tagged it itself.
        site_untagged = [f for f in cat.films
                         if f.keywords_source != "site" or not f.keywords]

        which = request.args.get("filter", "pending")
        if which == "pending":      # suggested, not yet approved
            rows = [f for f in site_untagged
                    if str(f.id) in suggestions and str(f.id) not in approved]
        elif which == "approved":
            rows = [f for f in site_untagged if str(f.id) in approved]
        elif which == "missing":    # no suggestions generated yet
            rows = [f for f in site_untagged if str(f.id) not in suggestions]
        else:                       # all films still lacking site keywords
            rows = list(site_untagged)

        query = (request.args.get("q") or "").strip()
        if query:
            needle = fold(query)
            rows = [f for f in rows if needle in f.haystack()]

        # NB: named page_num, not page - templates already use `page` for the
        # active nav item, and the two silently collide in Jinja.
        page_num = max(_int(request.args.get("page"), 1) or 1, 1)
        per_page = _int(request.args.get("per_page"), PER_PAGE)
        if per_page not in PAGE_SIZES:
            per_page = PER_PAGE
        pages = max((len(rows) + per_page - 1) // per_page, 1)
        page_num = min(page_num, pages)
        visible = rows[(page_num - 1) * per_page: page_num * per_page]

        entries = []
        for film in visible:
            record = suggestions.get(str(film.id), {})
            done = approved.get(str(film.id))
            entries.append({
                "film": film,
                "suggested": record.get("keywords") or [],
                "error": record.get("error"),
                "chosen": (done or {}).get("keywords") or record.get("keywords") or [],
                "approved": bool(done),
            })

        return render_template(
            "keywords.html", catalog=cat, entries=entries,
            vocabulary=vocabulary, filter=which, page_num=page_num, pages=pages,
            per_page=per_page, page_sizes=PAGE_SIZES,
            # every film still waiting for a suggestion, not just this page
            missing_ids=[f.id for f in site_untagged if str(f.id) not in suggestions],
            query=query, n_missing=len([f for f in site_untagged
                                        if str(f.id) not in suggestions]),
            matched=len(rows),
            saved=saved,
            n_untagged=len([f for f in cat.films if not f.keywords]),
            n_suggested=len(suggestions), n_approved=len(approved),
        )

    @app.route("/keywords/suggest", methods=["POST"])
    def keywords_suggest():
        """Generate suggestions on demand for the films named in the form."""
        from . import enrich

        cat = catalog()
        ids = [int(x) for x in request.form.getlist("film_ids") if x.isdigit()]
        films = [f for f in (cat.by_id(i) for i in ids) if f is not None]

        back = url_for("keywords", filter=request.form.get("filter") or "missing",
                       q=request.form.get("q") or None,
                       per_page=_int(request.form.get("per_page")) or None,
                       page=_int(request.form.get("page")) or None)
        if not films:
            return redirect(back)

        try:
            enrich.suggest_all(cat, films=films, progress=lambda *_a, **_k: None)
        except enrich.EnrichError as e:
            return redirect(url_for("keywords", filter="missing", error=str(e)))
        return redirect(back)

    # ------------------------------------------------- hand-entered films
    TEXT_FIELDS = ["title", "title_en", "genre", "genre_en", "country",
                   "country_en", "language", "language_en", "director",
                   "producer", "production_company", "distributor",
                   "synopsis", "synopsis_en", "url", "url_en"]

    def _film_form_ctx(form, editing=False, errors=(), film_id=None):
        cat = catalog()
        return {"catalog": cat, "form": form, "editing": editing,
                "errors": errors, "film_id": film_id,
                "genres": cat.genres, "all_keywords": cat.all_keywords}

    def _parse_film_form():
        """Turn the posted form into a manual-film dict plus any errors."""
        lang = ui_lang()
        form, errors = request.form, []

        data = {k: (form.get(k) or "").strip() or None for k in TEXT_FIELDS}
        data["year"] = _int(form.get("year"))
        data["keywords"] = _split(form.get("keywords"))
        data["keywords_en"] = _split(form.get("keywords_en"))

        if not data["title"]:
            errors.append(ui_string(lang, "nf_err_title"))

        raw_duration = (form.get("duration_min") or "").strip()
        duration = _float(raw_duration) if raw_duration else None
        if raw_duration and (duration is None or duration <= 0):
            errors.append(ui_string(lang, "nf_err_duration"))
        data["duration_min"] = duration
        return data, errors

    @app.route("/films/new", methods=["GET", "POST"])
    def film_new():
        if request.method == "POST":
            data, errors = _parse_film_form()
            if errors:
                return render_template("film_form.html",
                                       **_film_form_ctx(request.form, False, errors))
            manual_films.add(data)
            catalog(refresh=True)
            return redirect(url_for("films", msg="added"))
        return render_template("film_form.html", **_film_form_ctx(MultiDict()))

    @app.route("/films/<int:film_id>/edit", methods=["GET", "POST"])
    def film_edit(film_id):
        film = manual_films.get(film_id)
        if film is None:
            abort(404)  # scraped films are owned by the website, not editable here

        if request.method == "POST":
            data, errors = _parse_film_form()
            if errors:
                return render_template(
                    "film_form.html",
                    **_film_form_ctx(request.form, True, errors, film_id))
            manual_films.update(film_id, data)
            catalog(refresh=True)
            return redirect(url_for("films", msg="updated"))

        prefill = MultiDict({k: ("" if v is None else v)
                             for k, v in film.items()
                             if k not in ("keywords", "keywords_en")})
        prefill["keywords"] = ", ".join(film.get("keywords") or [])
        prefill["keywords_en"] = ", ".join(film.get("keywords_en") or [])
        return render_template("film_form.html",
                               **_film_form_ctx(prefill, True, (), film_id))

    @app.route("/films/<int:film_id>/delete", methods=["POST"])
    def film_delete(film_id):
        if not manual_films.delete(film_id):
            abort(404)
        catalog(refresh=True)
        return redirect(url_for("films", msg="deleted"))

    @app.route("/refresh", methods=["POST"])
    def refresh():
        """Re-read the archive from the database.

        The scrape itself is not run here on purpose: pulling 435 films takes
        minutes and a serverless request is killed long before that. Run
        `python run.py scrape` on a machine (or a scheduled job) - it writes to
        the same database, and this button picks the result up.
        """
        catalog(refresh=True)
        return redirect(url_for("index"))

    @app.template_filter("minutes")
    def _minutes(value):
        return minutes_label(value, ui_lang())

    @app.template_filter("eur")
    def _eur(value):
        return f"{float(value or 0):,.2f} EUR".replace(",", " ")

    return app


app = create_app() if __name__ != "__main__" else None
