"""Curated programme generator.

A programme is a set of short films that must satisfy hard constraints
(count, total running time, licensing, year/genre filters) while maximising a
curatorial score built from:

  relevance  - how well each film matches the requested keywords / free text
  coverage   - how many of the requested keywords the programme touches at all
  fit        - how well the total running time uses the available slot
  flow       - diversity of directors, genres and years, plus a sane run of lengths

Search is a randomised greedy build followed by local swap improvement, repeated
from many restarts. That reliably finds near-optimal sets over a few hundred
candidates and, unlike exhaustive search, is fast enough to run interactively.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

from .catalog import Catalog, Film, fold
from .i18n import runtime_label, t
from .config import DEFAULT_MAX_FILMS, DEFAULT_MAX_MINUTES, DEFAULT_MIN_FILMS

# Upper bound on how many distinct programmes we ever return for "All".
MAX_PROPOSALS = 8


@dataclass
class ProgrammeRequest:
    """Everything the team specifies when asking for a programme."""
    title: str = "Filmų programa"
    occasion: Optional[str] = None          # festival / event / team building
    # free text printed under the programme title in the exported document
    intro: Optional[str] = None
    rating: Optional[str] = None            # age rating, e.g. "N-16"
    keywords: List[str] = field(default_factory=list)
    query: Optional[str] = None             # free text over title/synopsis
    genres: List[str] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    min_films: int = DEFAULT_MIN_FILMS
    max_films: int = DEFAULT_MAX_FILMS
    max_minutes: float = DEFAULT_MAX_MINUTES
    min_minutes: float = 0.0
    licensed_only: bool = False
    require_any_keyword: bool = False
    exclude_ids: List[int] = field(default_factory=list)
    pin_ids: List[int] = field(default_factory=list)   # films that must be included
    n_proposals: int = 2
    # when set, return every distinct programme found (up to MAX_PROPOSALS)
    all_proposals: bool = False
    seed: Optional[int] = None
    lang: str = "lt"
    # filled in by generate(): how many distinct programmes actually existed
    found_total: int = 0

    def normalised(self) -> "ProgrammeRequest":
        if self.min_films > self.max_films:
            self.min_films, self.max_films = self.max_films, self.min_films
        self.min_films = max(1, self.min_films)
        self.max_films = max(self.min_films, self.max_films)
        return self


@dataclass
class Programme:
    films: List[Film]
    score: float
    breakdown: Dict[str, float]
    request: ProgrammeRequest

    @property
    def total_minutes(self) -> float:
        return round(sum(f.duration for f in self.films), 2)

    @property
    def runtime_label(self) -> str:
        return self.runtime(self.request.lang)

    def runtime(self, lang: str = "lt") -> str:
        return runtime_label(self.total_minutes, lang)

    @property
    def ids(self) -> Tuple[int, ...]:
        return tuple(sorted(f.id for f in self.films))

    def keyword_coverage(self) -> Dict[str, bool]:
        wanted = [k for k in self.request.keywords if k]
        present = set().union(*[f.kw_folded for f in self.films]) if self.films else set()
        return {k: fold(k) in present for k in wanted}

    def all_keywords(self) -> List[str]:
        seen: Dict[str, None] = {}
        for f in self.films:
            for k in f.keywords:
                seen.setdefault(k, None)
        return list(seen)

    def warnings(self, lang: Optional[str] = None) -> List[str]:
        lang = lang or self.request.lang
        out = []
        req = self.request
        if self.total_minutes > req.max_minutes:
            out.append(t(lang, "w_over_time", runtime=self.runtime(lang),
                         limit=int(req.max_minutes)))
        if len(self.films) < req.min_films:
            out.append(t(lang, "w_too_few", n=len(self.films), wanted=req.min_films))
        unsigned = [f.title for f in self.films if f.licence_signed is False]
        if unsigned:
            out.append(t(lang, "w_unsigned", films=", ".join(unsigned)))
        unknown = [f.title for f in self.films if f.licence_signed is None]
        if unknown and req.licensed_only is False:
            out.append(t(lang, "w_unknown", films=", ".join(unknown)))
        missed = [k for k, ok in self.keyword_coverage().items() if not ok]
        if missed:
            out.append(t(lang, "w_missed_kw", keywords=", ".join(missed)))
        return out


# --------------------------------------------------------------------- relevance

# A film with no keywords at all (the pre-2020 archive) still gets a small base
# score so it can be picked, but never outranks a genuine keyword match.
UNTAGGED_FLOOR = 0.12


def film_relevance(film: Film, wanted_kw: Sequence[str], q_terms: Sequence[str]) -> float:
    score = 0.0
    if wanted_kw:
        hits = film.kw_folded & set(wanted_kw)
        score += len(hits) / float(len(wanted_kw))
        # a partial credit for near matches ("seima" inside "seimynine drama")
        if not hits:
            soft = sum(1 for w in wanted_kw for k in film.kw_folded if w in k or k in w)
            score += 0.25 * min(soft, len(wanted_kw)) / float(len(wanted_kw))
    if q_terms:
        hay = film.haystack()
        score += 0.6 * sum(1 for t in q_terms if t in hay) / float(len(q_terms))
    if not wanted_kw and not q_terms:
        return 1.0
    if not film.keywords:
        score = max(score, UNTAGGED_FLOOR)
    return min(score, 2.0)


WEIGHTS = {
    "relevance": 1.0,
    "coverage": 0.7,
    "fit": 0.5,
    "flow": 0.35,
}


def score_programme(films: Sequence[Film], req: ProgrammeRequest,
                    rel: Dict[int, float]) -> Tuple[float, Dict[str, float]]:
    if not films:
        return -1e9, {}

    total = sum(f.duration for f in films)
    wanted = [fold(k) for k in req.keywords if k]

    relevance = sum(rel.get(f.id, 0.0) for f in films) / float(len(films))

    if wanted:
        present = set().union(*[f.kw_folded for f in films])
        coverage = len([w for w in wanted if w in present]) / float(len(wanted))
    else:
        coverage = 1.0

    # Fit: reward using the slot well, punish overrun hard (it is a hard limit).
    if total > req.max_minutes:
        fit = -5.0
    else:
        fit = total / req.max_minutes
        if req.min_minutes and total < req.min_minutes:
            fit -= 0.5

    # Flow: no director twice, a spread of genres and years, varied lengths.
    directors = [f.director_folded for f in films if f.director]
    dir_div = len(set(directors)) / float(len(directors)) if directors else 1.0
    genres = [f.genre_folded for f in films if f.genre]
    genre_div = len(set(genres)) / float(len(genres)) if genres else 0.0
    years = [f.year for f in films if f.year]
    year_spread = min((max(years) - min(years)) / 12.0, 1.0) if len(years) > 1 else 0.0
    lengths = sorted(f.duration for f in films)
    length_var = min((lengths[-1] - lengths[0]) / 20.0, 1.0) if len(lengths) > 1 else 0.0
    flow = 0.45 * dir_div + 0.25 * genre_div + 0.15 * year_spread + 0.15 * length_var

    # A duplicated director is a real curatorial problem, not just a lost bonus.
    if directors and len(set(directors)) < len(directors):
        flow -= 0.4

    parts = {
        "relevance": relevance,
        "coverage": coverage,
        "fit": fit,
        "flow": flow,
    }
    total_score = sum(WEIGHTS[k] * v for k, v in parts.items())
    parts["total"] = total_score
    return total_score, parts


# ------------------------------------------------------------------------ search

def _build_one(pool: List[Film], req: ProgrammeRequest, rel: Dict[int, float],
               rng: random.Random, pinned: List[Film]) -> List[Film]:
    """Randomised greedy: repeatedly add the best film among a random top-k sample."""
    chosen = list(pinned)
    used = {f.id for f in chosen}
    budget = req.max_minutes - sum(f.duration for f in chosen)
    target = rng.randint(req.min_films, req.max_films)

    while len(chosen) < target:
        options = [f for f in pool if f.id not in used and f.duration <= budget]
        if not options:
            break
        remaining_slots = target - len(chosen)
        # Prefer films that leave room for the slots still to fill.
        avg_needed = budget / max(remaining_slots, 1)

        def desirability(f: Film) -> float:
            d = rel.get(f.id, 0.0)
            d -= 0.25 * abs(f.duration - avg_needed) / max(avg_needed, 1.0)
            fd = f.director_folded
            if fd and any(fd == c.director_folded for c in chosen):
                d -= 0.8
            return d

        options.sort(key=desirability, reverse=True)
        window = options[:max(3, min(8, len(options)))]
        pick = rng.choice(window)
        chosen.append(pick)
        used.add(pick.id)
        budget -= pick.duration

    return chosen


def _improve(chosen: List[Film], pool: List[Film], req: ProgrammeRequest,
             rel: Dict[int, float], pinned_ids: set, rounds: int = 2) -> List[Film]:
    """Local search: try swapping each non-pinned film for a better candidate."""
    best = list(chosen)
    best_score, _ = score_programme(best, req, rel)

    for _ in range(rounds):
        improved = False
        for i, film in enumerate(best):
            if film.id in pinned_ids:
                continue
            current_ids = {f.id for f in best}
            headroom = req.max_minutes - (sum(f.duration for f in best) - film.duration)
            for cand in pool:
                if cand.id in current_ids or cand.duration > headroom:
                    continue
                trial = list(best)
                trial[i] = cand
                s, _ = score_programme(trial, req, rel)
                if s > best_score + 1e-9:
                    best, best_score, improved = trial, s, True
                    break
            if improved:
                break
        if not improved:
            break
    return best


def generate(catalog: Catalog, req: ProgrammeRequest, restarts: int = 800,
             pool_size: int = 120, improve_top: int = 25):
    """Return (proposals, alternates, pool).

    proposals  - up to req.n_proposals distinct Programme objects, best first
    alternates - strong thematic matches that did not fit the running-time slot
    """
    req = req.normalised()
    rng = random.Random(req.seed)

    pinned = [f for f in (catalog.by_id(i) for i in req.pin_ids) if f]
    pinned_ids = {f.id for f in pinned}

    candidates = catalog.filter(
        keywords=req.keywords,
        genres=req.genres,
        categories=req.categories,
        year_from=req.year_from,
        year_to=req.year_to,
        max_duration=req.max_minutes,
        query=req.query,
        licensed_only=req.licensed_only,
        require_any_keyword=req.require_any_keyword,
        exclude_ids=req.exclude_ids,
    )
    # Pinned films bypass the filters - the curator asked for them explicitly.
    by_id = {f.id: f for f in candidates}
    for f in pinned:
        by_id.setdefault(f.id, f)
    candidates = list(by_id.values())

    wanted_kw = [fold(k) for k in req.keywords if k]
    q_terms = [t for t in fold(req.query).split() if t] if req.query else []
    rel = {f.id: film_relevance(f, wanted_kw, q_terms) for f in candidates}

    ranked = sorted(candidates, key=lambda f: (-rel[f.id], -(f.year or 0)))
    pool = [f for f in ranked[:pool_size]]
    for f in pinned:  # never let a pinned film fall outside the working pool
        if f not in pool:
            pool.append(f)

    if not pool:
        return [], [], []

    # Phase 1: many cheap randomised builds.
    built_seen: Dict[Tuple[int, ...], Tuple[float, List[Film]]] = {}
    for _ in range(restarts):
        built = _build_one(pool, req, rel, rng, pinned)
        if len(built) < req.min_films:
            continue
        if sum(f.duration for f in built) > req.max_minutes:
            continue
        s, _parts = score_programme(built, req, rel)
        key = tuple(sorted(f.id for f in built))
        if key not in built_seen or s > built_seen[key][0]:
            built_seen[key] = (s, built)

    # Phase 2: local swap improvement, only on the most promising builds.
    top = sorted(built_seen.values(), key=lambda sv: -sv[0])[:improve_top]
    seen: Dict[Tuple[int, ...], Programme] = {}
    for _s, built in top:
        refined = _improve(built, pool, req, rel, pinned_ids)
        if sum(f.duration for f in refined) > req.max_minutes:
            refined = built
        s, parts = score_programme(refined, req, rel)
        prog = Programme(films=refined, score=s, breakdown=parts, request=req)
        prev = seen.get(prog.ids)
        if prev is None or s > prev.score:
            seen[prog.ids] = prog

    ordered = sorted(seen.values(), key=lambda p: -p.score)
    # How many genuinely different programmes exist for these filters. Drives
    # the "All" choice and the option count offered in the form.
    req.found_total = min(len(ordered), MAX_PROPOSALS)
    wanted = MAX_PROPOSALS if req.all_proposals else req.n_proposals

    # Keep proposals genuinely different from one another.
    proposals: List[Programme] = []
    for prog in ordered:
        if len(proposals) >= wanted:
            break
        if all(len(set(prog.ids) & set(p.ids)) <= max(1, len(prog.ids) // 2)
               for p in proposals):
            proposals.append(prog)
    chosen_ids = {p.ids for p in proposals}
    for prog in ordered:  # relax the distinctness rule if we came up short
        if len(proposals) >= wanted:
            break
        if prog.ids not in chosen_ids:
            proposals.append(prog)
            chosen_ids.add(prog.ids)

    for prog in proposals:
        prog.films.sort(key=lambda f: (f.duration, f.title or ""))

    used = {f.id for p in proposals for f in p.films}
    alternates = [
        f for f in ranked
        if f.id not in used and rel.get(f.id, 0) > 0.2
    ][:8]

    return proposals, alternates, pool
