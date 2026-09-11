-- =============================================================================
-- DESTRUCTIVE RESET. Wipes the whole `public` schema of this project.
--
-- Every table, view, function, trigger and sequence in `public` is dropped,
-- along with all the data in them. There is no undo. Run this only on a project
-- you mean to rebuild from scratch, and only right before re-running
-- 01_schema.sql / 02_auth.sql / 03_rls.sql / 04_seed_admin.sql.
--
-- What it does NOT touch: the `auth` schema (Supabase Auth users), `storage`
-- (uploaded files), `extensions`, and anything you created in another schema.
-- =============================================================================

drop schema public cascade;
create schema public;

-- Supabase expects these grants on a fresh public schema; without them the API
-- roles cannot see the schema at all and every request fails with a permission
-- error, even for tables you create afterwards.
grant usage on schema public to postgres, anon, authenticated, service_role;
grant all privileges on schema public to postgres, service_role;

comment on schema public is 'standard public schema';

-- Now run, in order:
--   01_schema.sql
--   02_auth.sql
--   03_rls.sql
--   04_seed_admin.sql   (with your own email and password)
