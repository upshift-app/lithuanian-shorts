"""Command line entry point: scrape, build programmes, generate reports."""
from __future__ import annotations

import argparse
import datetime as _dt
import sys
from pathlib import Path

from . import export_docx, export_pdf, licensing, screenings as scr
from .catalog import fold, load_catalog
from .programme import ProgrammeRequest, generate


def _split(value):
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


def _date(value):
    return _dt.datetime.strptime(value, "%Y-%m-%d").date() if value else None


# ---------------------------------------------------------------------- commands

def cmd_scrape(args):
    from .scraper import scrape
    scrape(force=args.force, workers=args.workers)
    return 0


def cmd_keywords(args):
    cat = load_catalog()
    counts = cat.keyword_counts()
    print(f"{len(counts)} raktažodžiai naudojami {sum(counts.values())} kartus:\n")
    for kw, n in counts.items():
        if args.search and fold(args.search) not in fold(kw):
            continue
        print(f"  {n:>4}  {kw}")
    print(f"\nŽanrai: {', '.join(cat.genres)}")
    print(f"Kategorijos: {', '.join(cat.all_categories)}")
    return 0


def cmd_programme(args):
    cat = load_catalog()
    req = ProgrammeRequest(
        title=args.title or "",
        occasion=args.occasion,
        intro=args.intro,
        rating=args.rating,
        keywords=_split(args.keywords),
        query=args.query,
        genres=_split(args.genre),
        categories=_split(args.category),
        year_from=args.year_from,
        year_to=args.year_to,
        min_films=args.min_films,
        max_films=args.max_films,
        max_minutes=args.max_minutes,
        licensed_only=args.licensed_only,
        require_any_keyword=args.strict_keywords,
        exclude_ids=[int(x) for x in _split(args.exclude)],
        pin_ids=[int(x) for x in _split(args.pin)],
        n_proposals=args.proposals,
        seed=args.seed,
        lang=args.lang,
    )
    proposals, alternates, pool = generate(cat, req)
    if not proposals:
        print("Nepavyko sudaryti programos su šiais kriterijais "
              f"(rasta {len(pool)} tinkamų filmų). Pabandykite atlaisvinti filtrus.")
        return 1

    for i, prog in enumerate(proposals, 1):
        print(f"\n=== {i} variantas — {prog.runtime_label}, "
              f"{len(prog.films)} filmai (įvertis {prog.score:.2f}) ===")
        for n, f in enumerate(prog.films, 1):
            print(f"  {n}. {f.display_title} ({f.year}, {f.genre}) "
                  f"— {int(f.duration)} min")
            if f.keywords:
                print(f"      {', '.join(f.keywords)}")
        for w in prog.warnings():
            print(f"  ! {w}")

    if alternates:
        print("\nTaip pat tematiškai tiktų:")
        for f in alternates:
            print(f"  - {f.display_title} ({f.year}, {int(f.duration)} min)")

    outputs = []
    if args.format in ("docx", "both"):
        out = Path(args.out).with_suffix(".docx") if args.out else None
        outputs.append(export_docx.programme_docx(proposals, alternates, path=out,
                                                  lang=args.lang))
    if args.format in ("pdf", "both"):
        out = Path(args.out).with_suffix(".pdf") if args.out else None
        outputs.append(export_pdf.programme_pdf(proposals, alternates, path=out,
                                                lang=args.lang))
    for path in outputs:
        print(f"\nIšsaugota: {path}")
    return 0


def cmd_report(args):
    cat = load_catalog()
    rows = scr.load_screenings()
    if not rows:
        print("Nėra rodymų duomenų. Įveskite juos Įrankiį: "
              "python run.py serve -> Rodymai.")
        return 1

    reports = scr.build_reports(
        rows, cat,
        film_ids=[int(x) for x in _split(args.film_id)],
        director=args.director,
        date_from=_date(args.date_from),
        date_to=_date(args.date_to),
    )
    if not reports:
        print("Pagal šiuos filtrus rodymų nerasta.")
        return 1

    agg = scr.totals(reports)
    print(f"{agg['films']} filmai · {agg['events']} renginiai · "
          f"{agg['screenings']} seansai · {agg['revenue']:.2f} EUR\n")
    for r in reports:
        print(f"  {r.title} — {r.total_screenings} seansai, "
              f"{r.total_revenue:.2f} EUR ({r.period})")

    period = None
    if args.date_from or args.date_to:
        period = f"{args.date_from or '...'} - {args.date_to or '...'}"

    outputs = []
    if args.format in ("pdf", "both"):
        out = Path(args.out).with_suffix(".pdf") if args.out else None
        outputs.append(export_pdf.report_pdf(reports, path=out, title=args.title,
                                             period=period, recipient=args.recipient,
                                             lang=args.lang))
    if args.format in ("docx", "both"):
        out = Path(args.out).with_suffix(".docx") if args.out else None
        outputs.append(export_docx.report_docx(reports, path=out, title=args.title,
                                               period=period, recipient=args.recipient,
                                               lang=args.lang))
    for path in outputs:
        print(f"\nIšsaugota: {path}")
    return 0


def cmd_init_sheets(args):
    cat = load_catalog(with_licensing=False)
    try:
        path = licensing.write_template(cat, overwrite=args.force)
        print(f"Sukurta licencijų lentelė: {path} ({len(cat)} filmai)")
    except FileExistsError as e:
        print(f"Praleista: {e}")
    try:
        path = scr.write_template(overwrite=args.force)
        print(f"Sukurta rodymų lentelė: {path}")
    except FileExistsError as e:
        print(f"Praleista: {e}")
    return 0


def cmd_enrich(args):
    from . import enrich
    cat = load_catalog()

    targets = enrich.untagged_films(cat)
    if not targets:
        print("Visi filmai jau turi raktažodžius.")
        return 0

    if not args.redo:
        already = enrich.load_suggestions()
        targets = [f for f in targets if str(f.id) not in already]
        if not targets:
            print("Visiems filmams be raktažodžių pasiūlymai jau parengti. "
                  "Peržiūrėkite juos įrankyje (/keywords) arba naudokite --redo.")
            return 0

    print(f"Filmų be raktažodžių: {len(enrich.untagged_films(cat))}, "
          f"bus apdorota: {min(len(targets), args.limit or len(targets))}")
    try:
        store = enrich.suggest_all(cat, films=targets,
                                   model=args.model or enrich.DEFAULT_MODEL,
                                   workers=args.workers, limit=args.limit)
    except enrich.EnrichError as e:
        print(f"Klaida: {e}", file=sys.stderr)
        return 2

    print("\nPavyzdžiai:")
    for record in list(store.values())[:8]:
        kws = ", ".join(record.get("keywords") or []) or "(nieko)"
        print(f"  {record['title'][:44]:<44} {kws}")
    print("\nPeržiūrėkite ir patvirtinkite: python run.py serve -> Raktažodžiai")
    return 0


def cmd_serve(args):
    from .webapp import create_app
    app = create_app()
    print("\n  Lithuanian Shorts — vidinis įrankis")
    print(f"  Atidarykite naršyklėje: http://127.0.0.1:{args.port}\n")
    app.run(host=args.host, port=args.port, debug=args.debug)
    return 0


# ------------------------------------------------------------------------ parser

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="lithuanian-shorts",
        description="Lithuanian Shorts: filmų programų sudarymas ir rodymų ataskaitos.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    s = sub.add_parser("scrape", help="atnaujinti filmų archyvą iš svetainės")
    s.add_argument("--force", action="store_true", help="perkrauti visus filmus")
    s.add_argument("--workers", type=int, default=8)
    s.set_defaults(func=cmd_scrape)

    s = sub.add_parser("keywords", help="parodyti raktažodžius, žanrus, kategorijas")
    s.add_argument("--search", help="filtruoti raktažodžius")
    s.set_defaults(func=cmd_keywords)

    s = sub.add_parser("programme", help="sudaryti filmų programos pasiūlymą")
    s.add_argument("--title", help="programos pavadinimas")
    s.add_argument("--occasion", help="renginys / kontekstas")
    s.add_argument("--intro", help="programos aprašymas dokumento pradžioje")
    s.add_argument("--rating", help="amžiaus cenzas, pvz. N-16")
    s.add_argument("-k", "--keywords", help="raktažodžiai, atskirti kableliais")
    s.add_argument("-q", "--query", help="laisvo teksto paieška")
    s.add_argument("--genre", help="žanrai, atskirti kableliais")
    s.add_argument("--category", help="kategorijos, atskirtos kableliais")
    s.add_argument("--year-from", type=int)
    s.add_argument("--year-to", type=int)
    s.add_argument("--min-films", type=int, default=5)
    s.add_argument("--max-films", type=int, default=6)
    s.add_argument("--max-minutes", type=float, default=90)
    s.add_argument("--licensed-only", action="store_true",
                   help="tik filmai su pasirašyta licencine sutartimi")
    s.add_argument("--strict-keywords", action="store_true",
                   help="įtraukti tik filmus, turinčius bent vieną iš raktažodžių")
    s.add_argument("--exclude", help="filmų ID, kurių neįtraukti")
    s.add_argument("--pin", help="filmų ID, kuriuos būtinai įtraukti")
    s.add_argument("-n", "--proposals", type=int, default=2)
    s.add_argument("--seed", type=int)
    s.add_argument("--lang", choices=["lt", "en"], default="lt",
                   help="dokumento kalba")
    s.add_argument("--format", choices=["docx", "pdf", "both"], default="both")
    s.add_argument("--out", help="išvesties failas")
    s.set_defaults(func=cmd_programme)

    s = sub.add_parser("report", help="parengti filmų rodymų ataskaitą")
    s.add_argument("--film-id", help="filmų ID, atskirti kableliais")
    s.add_argument("--director", help="filtruoti pagal režisierių")
    s.add_argument("--date-from", help="YYYY-MM-DD")
    s.add_argument("--date-to", help="YYYY-MM-DD")
    s.add_argument("--title", help="ataskaitos pavadinimas")
    s.add_argument("--recipient", help="kam skirta ataskaita")
    s.add_argument("--lang", choices=["lt", "en"], default="lt",
                   help="dokumento kalba")
    s.add_argument("--format", choices=["docx", "pdf", "both"], default="both")
    s.add_argument("--out", help="išvesties failas")
    s.set_defaults(func=cmd_report)

    s = sub.add_parser("init-sheets", help="sukurti licencijų ir rodymų Excel lenteles")
    s.add_argument("--force", action="store_true", help="perrašyti esamas")
    s.set_defaults(func=cmd_init_sheets)

    s = sub.add_parser("enrich",
                       help="AI pasiūlymai raktažodžiams filmams, kurie jų neturi")
    from .enrich import DEFAULT_MODEL as _DEFAULT_MODEL
    s.add_argument("--model", default=None,
                   help="OpenRouter modelis (numatytas: %s)" % _DEFAULT_MODEL)
    s.add_argument("--limit", type=int, help="apdoroti tik tiek filmų (bandymui)")
    s.add_argument("--workers", type=int, default=4)
    s.add_argument("--redo", action="store_true",
                   help="perdaryti ir tuos, kuriems pasiūlymai jau parengti")
    s.set_defaults(func=cmd_enrich)

    s = sub.add_parser("serve", help="paleisti vidinį web įrankį")
    s.add_argument("--port", type=int, default=5000)
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--debug", action="store_true")
    s.set_defaults(func=cmd_serve)

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except FileNotFoundError as e:
        print(f"Klaida: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
