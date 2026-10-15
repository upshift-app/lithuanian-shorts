-- =============================================================================
-- Fees and settings.
--
-- app_settings: small key/value store edited on the Settings page (company
--   details printed on the PDFs, and the agency fees).
-- screenings.revenue_eur: when set, it is the revenue of the row as it stands,
--   with no multiplication by the screening count. Used for programmes, whose
--   amount is agreed for the whole booking.
-- screenings.kind: commercial or non-commercial.
--
-- Idempotent: safe to re-run.
-- =============================================================================

create table if not exists public.app_settings (
    key        text primary key,
    value      jsonb not null default '{}'::jsonb,
    updated_at timestamptz not null default now(),
    updated_by uuid
);
alter table public.app_settings enable row level security;
grant all on public.app_settings to service_role;

alter table public.screenings add column if not exists revenue_eur numeric(12, 2);
alter table public.screenings add column if not exists kind text
    check (kind in ('commercial', 'non_commercial'));
