-- =============================================================================
-- saved_programmes: programmes the team kept as favourites.
--
-- Only the film ids are stored (plus the title and the description text), so a
-- saved programme always shows the current archive data. Picking one in the
-- screening log expands it into its films.
--
-- Idempotent: safe to re-run.
-- =============================================================================

create table if not exists public.saved_programmes (
    id         bigserial primary key,
    title      text not null,
    film_ids   bigint[] not null default '{}',
    intro      text,
    lang       text not null default 'lt',
    created_by uuid,
    created_at timestamptz not null default now()
);

alter table public.saved_programmes enable row level security;
-- No policies on purpose, as everywhere else: only the service key gets in.
grant all on public.saved_programmes to service_role;
grant all on sequence public.saved_programmes_id_seq to service_role;
