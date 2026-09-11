-- =============================================================================
-- Row level security.
--
-- Nothing but the Flask server talks to this database, and it uses the service
-- key. So every table gets RLS with no policies, which denies the anon and
-- authenticated roles everything. Nobody can read the film archive, the
-- screening fees or the user table with a leaked public key.
--
-- The service key bypasses RLS by design. Keep it in Vercel's environment
-- variables and nowhere else - never in client-side code.
-- =============================================================================

alter table public.catalog_meta        enable row level security;
alter table public.films               enable row level security;
alter table public.keyword_suggestions enable row level security;
alter table public.keyword_approvals   enable row level security;
alter table public.licensing           enable row level security;
alter table public.screenings          enable row level security;
alter table public.generated_documents enable row level security;
alter table public.scrape_runs         enable row level security;
alter table public.app_users           enable row level security;
alter table public.app_user_audit      enable row level security;

alter table public.app_users      force row level security;
alter table public.app_user_audit force row level security;

-- No policies on purpose: RLS with zero policies denies everything.

revoke all on all tables in schema public from anon, authenticated;
revoke all on all sequences in schema public from anon, authenticated;
-- Postgres grants EXECUTE to PUBLIC on every new function, so revoking from
-- anon alone would leave the auth functions callable with the public key.
revoke execute on all functions in schema public from public, anon, authenticated;
alter default privileges in schema public revoke execute on functions from public;
