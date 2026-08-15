-- Texas AI Scanner schema. Applied to the texas-ai-scanner Supabase project
-- (fbcxboktppalytugeqin) as migration `scanner_schema`.
--
-- Ported from alaska-ai-scanner/db/schema.sql, which is REFERENCE ONLY.
--
-- Design law: RLS is ON with NO policies, so the anon/public key sees NOTHING.
-- Only the Edge Functions reach these tables, server-side, through the service
-- role, and only ever return a single scan by its unguessable public_token.
--
-- Two deliberate divergences from Alaska:
--   the day boundary is America/Chicago, not America/Anchorage
--   there is no scanner_optin: that RPC writes into Alaska's leadflow schema
--   and Texas has no lead pipeline to seed. The consent columns are omitted
--   with it rather than left as dead fields nobody writes.

create schema if not exists scanner;

create table if not exists scanner.scans (
  id             uuid primary key default gen_random_uuid(),
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now(),

  domain         text not null,
  status         text not null default 'queued',   -- queued|running|done|degraded|failed
  public_token   text not null unique
                   default encode(gen_random_bytes(16), 'hex'),

  booking_url    text,
  jobs_signal    text,

  headline       text,
  scan_json      jsonb,
  result_html    text,

  -- Appended by the routine as the work happens, served by token while the
  -- scan runs so the requester can watch. Generic steps about their own scan
  -- only: array of {at, phase, kind, note}.
  progress       jsonb not null default '[]'::jsonb,

  -- "send it to me when it is ready". Nothing sends automatically. It feeds a
  -- human-gated draft to the maintainer, same as every other path here.
  notify_email   text,

  -- The form's free-text box. Stored so a person can read it, and NEVER put in
  -- the trigger payload, so it cannot reach an agent as instructions. It arrived
  -- from a stranger through a public form: it is context for a human.
  -- (migration scanner_note)
  note           text,

  request_ip     text,
  user_agent     text,
  error          text,
  run_ms         int
);

create index if not exists scans_domain_idx on scanner.scans (lower(domain), created_at desc);
create index if not exists scans_status_idx on scanner.scans (status);
create index if not exists scans_ip_idx     on scanner.scans (request_ip, created_at desc);

-- search_path pinned empty so the function cannot be hijacked by a mutable path.
create or replace function scanner.touch_updated_at()
  returns trigger language plpgsql
  set search_path = '' as $$
begin
  new.updated_at = now();
  return new;
end $$;

drop trigger if exists scans_touch on scanner.scans;
create trigger scans_touch before update on scanner.scans
  for each row execute function scanner.touch_updated_at();

alter table scanner.scans enable row level security;

-- Server-side config the gatekeeper reads. Wiring the routine trigger is one
-- insert here, no redeploy:
--   insert into scanner.config (key, value) values
--     ('trigger_url', '...'), ('trigger_secret', '...')
--   on conflict (key) do update set value = excluded.value, updated_at = now();
create table if not exists scanner.config (
  key        text primary key,
  value      text not null,
  updated_at timestamptz not null default now()
);
alter table scanner.config enable row level security;

-- ---------------------------------------------------------------------------
-- THE RPC API. PostgREST exposes only the public schema, so the Edge Functions
-- reach the scanner through these narrow named functions rather than
-- addressing the schema. Every one is SECURITY DEFINER with an empty
-- search_path, EXECUTE revoked from PUBLIC/anon/authenticated and granted only
-- to service_role. The public API surface is exactly these and nothing else.
-- ---------------------------------------------------------------------------

create or replace function public.scanner_today_count()
  returns int language sql security definer set search_path = '' as $$
  select count(*)::int from scanner.scans
  where created_at >= ((now() at time zone 'America/Chicago')::date);
$$;

create or replace function public.scanner_ip_count(p_ip text)
  returns int language sql security definer set search_path = '' as $$
  select count(*)::int from scanner.scans
  where request_ip = p_ip and created_at >= now() - interval '24 hours';
$$;

create or replace function public.scanner_cached(p_domain text, p_hours int)
  returns jsonb language sql security definer set search_path = '' as $$
  select jsonb_build_object('token', public_token, 'status', status)
  from scanner.scans
  where lower(domain) = lower(p_domain)
    and status in ('done','degraded')
    and created_at >= now() - make_interval(hours => p_hours)
  order by created_at desc limit 1;
$$;

create or replace function public.scanner_create(
    p_domain text, p_booking text, p_jobs text, p_ip text, p_ua text,
    p_notify text default null, p_note text default null)
  returns jsonb language sql security definer set search_path = '' as $$
  insert into scanner.scans (domain, booking_url, jobs_signal, request_ip, user_agent,
                             notify_email, note, status)
  values (p_domain, p_booking, p_jobs, p_ip, p_ua, left(p_notify, 320),
          left(p_note, 4000), 'queued')
  returning jsonb_build_object('id', id, 'token', public_token);
$$;

create or replace function public.scanner_mark_failed(p_id uuid, p_error text)
  returns void language sql security definer set search_path = '' as $$
  update scanner.scans set status = 'failed', error = left(p_error, 500)
  where id = p_id;
$$;

-- Read ONE scan by its unguessable token, safe fields only. The html comes back
-- only once the scan is finished; the progress feed comes back always so the
-- requester can watch. Internal fields never leave this shape.
create or replace function public.scanner_get_by_token(p_token text)
  returns jsonb language sql security definer set search_path = '' as $$
  select jsonb_build_object(
    'status', status,
    'headline', headline,
    'progress', progress,
    'html', case when status in ('done','degraded') then result_html else null end)
  from scanner.scans where public_token = p_token;
$$;

create or replace function public.scanner_config()
  returns jsonb language sql security definer set search_path = '' as $$
  select coalesce(jsonb_object_agg(key, value), '{}'::jsonb) from scanner.config;
$$;

-- SET ONCE. A scan link is shareable, so an address already on the row is never
-- overwritten: otherwise a shared link could redirect someone else's delivery,
-- or be used to mail a stranger.
create or replace function public.scanner_set_notify(p_token text, p_email text)
  returns jsonb language plpgsql security definer set search_path = '' as $$
declare v record;
begin
  select id, status, notify_email into v
  from scanner.scans where public_token = p_token;
  if not found then
    return jsonb_build_object('found', false);
  end if;
  if v.notify_email is not null and v.notify_email <> '' then
    return jsonb_build_object('found', true, 'already_set', true, 'status', v.status);
  end if;
  update scanner.scans set notify_email = left(p_email, 320) where id = v.id;
  return jsonb_build_object('found', true, 'already_set', false, 'status', v.status);
end $$;

do $lock$
declare f text;
begin
  foreach f in array array[
    'public.scanner_today_count()',
    'public.scanner_ip_count(text)',
    'public.scanner_cached(text, int)',
    'public.scanner_create(text, text, text, text, text, text, text)',
    'public.scanner_mark_failed(uuid, text)',
    'public.scanner_get_by_token(text)',
    'public.scanner_config()',
    'public.scanner_set_notify(text, text)'
  ] loop
    execute format('revoke all on function %s from public', f);
    execute format('revoke all on function %s from anon', f);
    execute format('revoke all on function %s from authenticated', f);
    execute format('grant execute on function %s to service_role', f);
  end loop;
end $lock$;
