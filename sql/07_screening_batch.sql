-- A saved programme logged as one screening is stored as one row per film.
-- batch_id ties those rows together so the log can show them as one entry.
-- Rows logged before this existed (or single films) leave it empty.
-- Idempotent: safe to re-run.
alter table public.screenings add column if not exists batch_id uuid;
create index if not exists ix_screenings_batch on public.screenings(batch_id)
    where batch_id is not null;
