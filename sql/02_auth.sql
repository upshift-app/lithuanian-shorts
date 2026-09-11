-- =============================================================================
-- Login for the internal tool. No Supabase Auth - a simple users table.
--
-- The Flask app runs server-side with the service key, so it is the only thing
-- that ever touches these tables. The browser gets nothing but a signed Flask
-- session cookie holding the user id, so there is no session table to keep.
--
-- Passwords are bcrypt, hashed and verified inside Postgres (pgcrypto), so a
-- plaintext password never exists anywhere but the one request that carries it.
--
-- Trade-off worth knowing: this is hand-rolled auth. It gives you hashing and
-- an admin-only account list, not email verification, rate limiting or MFA.
-- Fine for a handful of colleagues on an internal tool.
-- =============================================================================

create extension if not exists pgcrypto;

create table if not exists public.app_users (
    id            uuid primary key default gen_random_uuid(),
    email         text not null,
    password_hash text not null,
    full_name     text,
    is_admin      boolean not null default false,
    is_active     boolean not null default true,
    must_change_password boolean not null default false,
    last_login_at timestamptz,
    created_at    timestamptz not null default now(),
    updated_at    timestamptz not null default now()
);
create unique index if not exists ux_app_users_email on public.app_users(lower(email));

drop trigger if exists trg_app_users_touch on public.app_users;
create trigger trg_app_users_touch before update on public.app_users
    for each row execute function public.touch_updated_at();

-- Who changed what, so an internal tool still has a paper trail.
create table if not exists public.app_user_audit (
    id        bigserial primary key,
    actor_id  uuid,
    target_id uuid,
    action    text not null,
    detail    text,
    at        timestamptz not null default now()
);
create index if not exists ix_app_user_audit_at on public.app_user_audit(at desc);

create or replace function public.app_check_password(p_password text)
returns void
language plpgsql
as $fn$
begin
    if p_password is null or length(p_password) < 8 then
        raise exception 'password_too_short';
    end if;
end
$fn$;

-- -----------------------------------------------------------------------------
-- app_verify_password: the login check. Returns no row when the credentials do
-- not match, so the caller cannot tell a wrong password from a missing account.
-- -----------------------------------------------------------------------------
create or replace function public.app_verify_password(p_email text, p_password text)
returns table (
    user_id   uuid,
    email     text,
    full_name text,
    is_admin  boolean,
    must_change_password boolean
)
language plpgsql
security definer
set search_path = public, extensions
as $fn$
declare v_user public.app_users;
begin
    select * into v_user
      from public.app_users u
     where lower(u.email) = lower(trim(p_email))
       and u.is_active;

    if v_user.id is null
       or v_user.password_hash <> crypt(p_password, v_user.password_hash) then
        return;
    end if;

    update public.app_users set last_login_at = now() where id = v_user.id;
    insert into public.app_user_audit (actor_id, target_id, action)
    values (v_user.id, v_user.id, 'login');

    return query select v_user.id, v_user.email, v_user.full_name,
                        v_user.is_admin, v_user.must_change_password;
end
$fn$;

-- -----------------------------------------------------------------------------
-- app_create_user: admin adds a colleague. Email and password, nothing else.
-- -----------------------------------------------------------------------------
create or replace function public.app_create_user(
    p_actor uuid,
    p_email text,
    p_password text,
    p_full_name text default null,
    p_is_admin boolean default false,
    p_must_change_password boolean default true
)
returns uuid
language plpgsql
security definer
set search_path = public, extensions
as $fn$
declare v_new uuid;
begin
    perform public.app_check_password(p_password);
    if p_email is null or position('@' in p_email) = 0 then
        raise exception 'invalid_email';
    end if;

    insert into public.app_users (email, password_hash, full_name, is_admin,
                                  must_change_password)
    values (lower(trim(p_email)), crypt(p_password, gen_salt('bf', 12)),
            nullif(trim(coalesce(p_full_name, '')), ''), p_is_admin,
            p_must_change_password)
    returning id into v_new;

    insert into public.app_user_audit (actor_id, target_id, action, detail)
    values (p_actor, v_new, 'create_user', lower(trim(p_email)));
    return v_new;
exception
    when unique_violation then
        raise exception 'email_taken';
end
$fn$;

-- -----------------------------------------------------------------------------
-- app_change_password: the user's own change. Needs the current password; the
-- new one is passed twice and both copies are compared here, so a mismatched
-- form can never set a password by accident.
-- -----------------------------------------------------------------------------
create or replace function public.app_change_password(
    p_user_id uuid,
    p_old_password text,
    p_new_password text,
    p_new_password_confirm text
)
returns void
language plpgsql
security definer
set search_path = public, extensions
as $fn$
declare v_hash text;
begin
    if p_new_password is distinct from p_new_password_confirm then
        raise exception 'password_mismatch';
    end if;
    perform public.app_check_password(p_new_password);

    select password_hash into v_hash from public.app_users where id = p_user_id;
    if v_hash is null then
        raise exception 'user_not_found';
    end if;
    if v_hash <> crypt(p_old_password, v_hash) then
        raise exception 'invalid_credentials';
    end if;

    update public.app_users
       set password_hash = crypt(p_new_password, gen_salt('bf', 12)),
           must_change_password = false
     where id = p_user_id;

    insert into public.app_user_audit (actor_id, target_id, action)
    values (p_user_id, p_user_id, 'change_password');
end
$fn$;

-- -----------------------------------------------------------------------------
-- app_admin_set_password: admin resets somebody else's password. No current
-- password needed; still confirmed twice.
-- -----------------------------------------------------------------------------
create or replace function public.app_admin_set_password(
    p_actor uuid,
    p_user_id uuid,
    p_new_password text,
    p_new_password_confirm text,
    p_must_change_password boolean default true
)
returns void
language plpgsql
security definer
set search_path = public, extensions
as $fn$
begin
    if p_new_password is distinct from p_new_password_confirm then
        raise exception 'password_mismatch';
    end if;
    perform public.app_check_password(p_new_password);

    update public.app_users
       set password_hash = crypt(p_new_password, gen_salt('bf', 12)),
           must_change_password = p_must_change_password
     where id = p_user_id;
    if not found then
        raise exception 'user_not_found';
    end if;

    insert into public.app_user_audit (actor_id, target_id, action)
    values (p_actor, p_user_id, 'reset_password');
end
$fn$;

-- -----------------------------------------------------------------------------
-- app_set_user_flags: enable/disable an account, grant/revoke admin.
-- Guard rails: you cannot lock yourself out, and the last admin stays an admin.
-- -----------------------------------------------------------------------------
create or replace function public.app_set_user_flags(
    p_actor uuid,
    p_user_id uuid,
    p_is_active boolean default null,
    p_is_admin boolean default null
)
returns void
language plpgsql
security definer
set search_path = public, extensions
as $fn$
begin
    if p_user_id = p_actor and (p_is_active is false or p_is_admin is false) then
        raise exception 'cannot_demote_self';
    end if;
    if p_is_admin is false and
       (select count(*) from public.app_users where is_admin and is_active) <= 1 then
        raise exception 'last_admin';
    end if;

    update public.app_users
       set is_active = coalesce(p_is_active, is_active),
           is_admin  = coalesce(p_is_admin,  is_admin)
     where id = p_user_id;
    if not found then
        raise exception 'user_not_found';
    end if;

    insert into public.app_user_audit (actor_id, target_id, action, detail)
    values (p_actor, p_user_id, 'set_flags',
            format('is_active=%s is_admin=%s', p_is_active, p_is_admin));
end
$fn$;

create or replace function public.app_delete_user(p_actor uuid, p_user_id uuid)
returns void
language plpgsql
security definer
set search_path = public, extensions
as $fn$
begin
    if p_actor = p_user_id then
        raise exception 'cannot_delete_self';
    end if;
    delete from public.app_users where id = p_user_id;
    insert into public.app_user_audit (actor_id, target_id, action)
    values (p_actor, null, 'delete_user');
end
$fn$;
