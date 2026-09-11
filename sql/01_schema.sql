-- =============================================================================
-- Lithuanian Shorts internal tool - Supabase (Postgres) schema.
--
-- Replaces the local files the tool used to keep:
--   data/films.json             -> films + catalog_meta
--   data/films_manual.json      -> films where source = 'manual'
--   data/films_keywords.json    -> keyword_approvals
--   data/keyword_suggestions.json -> keyword_suggestions
--   data/licensing.xlsx         -> licensing
--   data/screenings.xlsx        -> screenings
--
-- Idempotent: safe to re-run.
-- =============================================================================

create extension if not exists pgcrypto;
create extension if not exists pg_trgm;

-- -----------------------------------------------------------------------------
-- catalog_meta: one row (id = 1) holding what films.json carried alongside the
-- film list - the vocabulary and the lt->en name maps.
-- -----------------------------------------------------------------------------
create table if not exists public.catalog_meta (
    id           smallint primary key default 1 check (id = 1),
    scraped_at   timestamptz,
    keywords     text[] not null default '{}',
    categories   text[] not null default '{}',
    keyword_map  jsonb  not null default '{}',   -- lt -> en
    category_map jsonb  not null default '{}',   -- lt -> en
    updated_at   timestamptz not null default now()
);
insert into public.catalog_meta (id) values (1) on conflict (id) do nothing;

-- -----------------------------------------------------------------------------
-- films: one row per film, scraped or hand-entered.
-- The id is the WordPress post id for scraped films; hand-entered films get ids
-- from 1000000 up, which WordPress ids never reach.
-- -----------------------------------------------------------------------------
create table if not exists public.films (
    id                 bigint primary key,
    title              text not null,
    title_en           text,
    year               integer,
    genre              text,
    genre_en           text,
    duration_min       real,
    duration_raw       text,
    country            text,
    country_en         text,
    language           text,
    language_en        text,
    director           text,
    producer           text,
    production_company text,
    distributor        text,
    synopsis           text,
    synopsis_en        text,
    director_bio_en    text,
    keywords           text[] not null default '{}',
    keywords_en        text[] not null default '{}',
    categories         text[] not null default '{}',
    categories_en      text[] not null default '{}',
    contacts           text[] not null default '{}',
    url                text,
    url_en             text,
    image              text,
    -- 'site' for scraped films, 'manual' for hand-entered ones. Only manual
    -- films may be edited in the UI; the rest are owned by the website.
    source             text not null default 'site' check (source in ('site', 'manual')),
    -- WordPress' own "modified" timestamp; the scraper re-fetches a film only
    -- when this changed, which is what keeps a refresh to a couple of minutes
    wp_modified        text,
    -- 'site' when the website tagged the film, 'ai' when an approved
    -- suggestion filled the gap
    keywords_source    text not null default 'site' check (keywords_source in ('site', 'ai')),
    scraped_at         timestamptz,
    created_at         timestamptz not null default now(),
    updated_at         timestamptz not null default now()
);
create index if not exists ix_films_source   on public.films(source);
create index if not exists ix_films_year     on public.films(year);
create index if not exists ix_films_director on public.films(director);
create index if not exists ix_films_keywords on public.films using gin (keywords);
create index if not exists ix_films_title_trgm
    on public.films using gin (title gin_trgm_ops);

-- -----------------------------------------------------------------------------
-- AI keyword suggestions, and the human decisions on them.
-- Kept apart so a re-scrape can never overwrite approved work, exactly as the
-- two JSON files did.
-- -----------------------------------------------------------------------------
create table if not exists public.keyword_suggestions (
    film_id     bigint primary key references public.films(id) on delete cascade,
    keywords    text[] not null default '{}',
    keywords_en text[] not null default '{}',
    model       text,
    error       text,           -- the suggestion run failed for this film
    created_at  timestamptz not null default now()
);

create table if not exists public.keyword_approvals (
    film_id     bigint primary key references public.films(id) on delete cascade,
    keywords    text[] not null default '{}',
    keywords_en text[] not null default '{}',
    approved_by uuid,
    approved_at timestamptz not null default now()
);

-- -----------------------------------------------------------------------------
-- licensing: was data/licensing.xlsx. A row matches a film by id when known,
-- otherwise by title, which is what the spreadsheet loader did.
-- -----------------------------------------------------------------------------
create table if not exists public.licensing (
    id             bigserial primary key,
    film_id        bigint references public.films(id) on delete cascade,
    film_title     text,
    licence_signed boolean,
    licence_until  text,          -- free text in the sheet; kept verbatim
    rights_holder  text,
    notes          text,
    updated_by     uuid,
    updated_at     timestamptz not null default now(),
    check (film_id is not null or film_title is not null)
);
create unique index if not exists ux_licensing_film on public.licensing(film_id)
    where film_id is not null;
create index if not exists ix_licensing_title on public.licensing(lower(film_title));

-- -----------------------------------------------------------------------------
-- screenings: was data/screenings.xlsx, one row per screening event.
-- Rates are not formulaic, so fee_eur is simply the number the team types in.
-- -----------------------------------------------------------------------------
create table if not exists public.screenings (
    id         bigserial primary key,
    film_id    bigint references public.films(id) on delete set null,
    film_title text not null default '',
    event      text,
    venue      text,
    city       text,
    country    text,
    date       date,
    screenings integer not null default 1 check (screenings >= 0),
    fee_eur    numeric(12, 2) not null default 0,
    programme  text,
    notes      text,
    created_by uuid,
    created_at timestamptz not null default now()
);
create index if not exists ix_screenings_film on public.screenings(film_id);
create index if not exists ix_screenings_date on public.screenings(date);

-- -----------------------------------------------------------------------------
-- generated_documents: what used to be the in-process _CACHE between the
-- "generate" and "download" clicks.
--
-- On Vercel the download can land on a different instance than the generate, so
-- the handover has to go through the database. Only the inputs are stored -
-- film ids, scores, and the request - and the document is rebuilt on download.
-- -----------------------------------------------------------------------------
create table if not exists public.generated_documents (
    token      text primary key,
    kind       text not null check (kind in ('programme', 'report')),
    payload    jsonb not null,
    created_by uuid,
    created_at timestamptz not null default now(),
    expires_at timestamptz not null default now() + interval '2 days'
);
create index if not exists ix_generated_documents_exp
    on public.generated_documents(expires_at);

-- -----------------------------------------------------------------------------
-- scrape_runs: so the team can see when the archive was last refreshed and
-- whether it worked. The scrape itself runs from a laptop or a cron job, never
-- inside a request - it takes minutes.
-- -----------------------------------------------------------------------------
create table if not exists public.scrape_runs (
    id          bigserial primary key,
    started_at  timestamptz not null default now(),
    finished_at timestamptz,
    ok          boolean,
    films       integer,
    note        text
);
create index if not exists ix_scrape_runs_started on public.scrape_runs(started_at desc);

-- -----------------------------------------------------------------------------
-- updated_at trigger
-- -----------------------------------------------------------------------------
create or replace function public.touch_updated_at()
returns trigger
language plpgsql
as $fn$
begin
    new.updated_at := now();
    return new;
end
$fn$;

drop trigger if exists trg_films_touch on public.films;
create trigger trg_films_touch before update on public.films
    for each row execute function public.touch_updated_at();

drop trigger if exists trg_licensing_touch on public.licensing;
create trigger trg_licensing_touch before update on public.licensing
    for each row execute function public.touch_updated_at();

drop trigger if exists trg_catalog_meta_touch on public.catalog_meta;
create trigger trg_catalog_meta_touch before update on public.catalog_meta
    for each row execute function public.touch_updated_at();
