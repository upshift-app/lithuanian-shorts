-- =============================================================================
-- First admin. Run once, with your own email and password.
-- =============================================================================

insert into public.app_users (email, password_hash, full_name, is_admin, must_change_password)
values (
    'admin@example.com',
    crypt('change-this-password', gen_salt('bf', 12)),
    'Admin',
    true,
    false
)
on conflict ((lower(email))) do update
    set password_hash = excluded.password_hash,
        is_admin  = true,
        is_active = true;

-- Adding a colleague straight from the SQL editor (the Users page does this too):
--   insert into public.app_users (email, password_hash, full_name, is_admin)
--   values ('kolega@lithuanianshorts.com',
--           crypt('slaptazodis123', gen_salt('bf', 12)), 'Vardas', false);
--
-- Resetting somebody's password:
--   update public.app_users
--      set password_hash = crypt('naujas-slaptazodis', gen_salt('bf', 12)),
--          must_change_password = true
--    where lower(email) = 'kolega@lithuanianshorts.com';
