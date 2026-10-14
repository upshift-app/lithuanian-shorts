"""Render sample programme and report PDFs in every design into design_variants/.

Real films are fetched from lithuanianshorts.com so the samples show real
stills and a co-directed film. Needs network access, and no database.

    python scripts/build_design_variants.py
"""
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# The exporters import the catalogue, which imports the database client. Nothing
# here touches the database, so a stand-in is enough.
if "supabase" not in sys.modules:
    try:
        import supabase  # noqa: F401
    except Exception:
        stub = types.ModuleType("supabase")
        stub.Client = object
        stub.create_client = lambda *a, **k: None
        sys.modules["supabase"] = stub

import requests  # noqa: E402

from ls_tool import export_pdf, pdf_designs, scraper  # noqa: E402
from ls_tool import screenings as scr  # noqa: E402
from ls_tool.catalog import Film  # noqa: E402
from ls_tool.config import API, FILM_POST_TYPE  # noqa: E402
from ls_tool.programme import Programme, ProgrammeRequest  # noqa: E402

OUT = ROOT / "design_variants"
# slugs picked for variety, including two co-directed films
SLUGS = ["bff-dainuojantis-zverynas", "viskas-ka-girdime-tyliai",
         "kavine-bufetas", "klases-nuotrauka", "lunaticos", "rudnios-cirkas"]
INTRO = ("A programme about growing up and the people around us: friendship, "
         "family and the small absurdities of everyday life, told in six "
         "Lithuanian short films.")


def load_films():
    sess = requests.Session()
    sess.headers.update(scraper.HEADERS)
    films = []
    for slug in SLUGS:
        posts = sess.get(f"{API}/{FILM_POST_TYPE}",
                         params={"slug": slug}, timeout=30).json()
        if not posts:
            continue
        post = posts[0]
        page = scraper.parse_film_page(sess.get(post["link"], timeout=30).text)
        data = scraper.normalise(post, page, {}, {})
        fields = set(Film.__dataclass_fields__)
        films.append(Film(**{k: v for k, v in data.items() if k in fields}))
    return films


def main():
    films = load_films()
    print(len(films), "films loaded;",
          "directors:", [f.director for f in films])
    req = ProgrammeRequest(title="Growing Up", intro=INTRO, rating="N-13",
                           lang="en")
    prog = Programme(films=films, score=0.0, breakdown={}, request=req)

    class Cat:  # build_reports only reads .films
        pass
    cat = Cat()
    cat.films = films
    reports = scr.build_reports(scr.sample_screenings(cat, films=len(films)), cat)

    OUT.mkdir(exist_ok=True)
    for old in OUT.glob("*.pdf"):
        old.unlink()

    def name(num, key, kind):
        return OUT / f"{num}-{key}-{kind}.pdf"

    export_pdf.programme_pdf([prog], path=name("01", "current", "programme"),
                             lang="en", notes=False)
    export_pdf.report_pdf(reports, path=name("01", "current", "report"),
                          title="Screening report", lang="en")
    export_pdf.programme_pdf([prog], path=name("02", "current-wider-gaps", "programme"),
                             lang="en", notes=False, film_gap=40)
    export_pdf.report_pdf(reports, path=name("02", "current-wider-gaps", "report"),
                          title="Screening report", lang="en", film_gap=34)

    for num, key in (("03", "editorial"), ("04", "cards"),
                     ("05", "band"), ("06", "minimal"),
                     ("07", "cards-plain")):
        theme = pdf_designs.THEMES[key]
        pdf_designs.programme_pdf(prog, name(num, key, "programme"), theme, lang="en")
        pdf_designs.report_pdf(reports, name(num, key, "report"), theme,
                               title="Screening report", lang="en")
    for p in sorted(OUT.glob("*.pdf")):
        print(p.name)


if __name__ == "__main__":
    main()
