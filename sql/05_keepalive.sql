-- =============================================================================
-- keepalive: one row (id = 1) touched by the daily cron ping.
--
-- A Free plan project is paused after a week without "sufficient user database
-- activity", and Supabase describes that as a few requests to the database each
-- day. A twice-a-week read was not enough - the project was paused on
-- 2026-09-21 - so the ping now runs daily and writes as well as reads.
--
-- The row doubles as the log of that ping: `ok = false` with an error, or a
-- `last_ok` that has stopped moving, says the cron has stopped working without
-- anyone having to open the Vercel logs.
--
-- Idempotent: safe to re-run.
-- =============================================================================

create table if not exists public.keepalive (
    id        smallint primary key default 1 check (id = 1),
    pinged_at timestamptz not null default now(),
    last_ok   timestamptz,
    pings     bigint not null default 0,
    source    text,
    note      text
);
insert into public.keepalive (id) values (1) on conflict (id) do nothing;

alter table public.keepalive enable row level security;
-- No policies on purpose, as everywhere else: only the service key gets in.
grant all on public.keepalive to service_role;
