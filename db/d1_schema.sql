-- Texas AI Scanner, the whole record, in one file.
--
-- Applied to a Cloudflare D1 database bound to the scan Worker as SCAN_DB. Paste it into the
-- D1 console once; it is idempotent, so pasting it again is safe.
--
-- WHY D1 AND NOT POSTGRES. This replaced a Supabase project on 2026-08-20 because that project
-- was a second vendor with its own uptime, its own key, and a console the owner had to keep a
-- separate account for. Cloudflare already serves the domain, Turnstile, and the ask box's
-- worker. This is the same storage the rest of the site already depends on rather than another
-- thing that can be down on its own.
--
-- WHY A DATABASE AT ALL, given the worker could use KV with no schema: a progress feed is read
-- three seconds after it is written and KV takes up to sixty to propagate. Storage that is
-- eventually consistent turns a live view into a view that lies.
--
-- THE SECURITY MODEL MOVED WITH THE DATA AND DID NOT WEAKEN. Postgres held it in RLS with no
-- policies plus service-role-only functions. Here, nothing but the Worker has a binding to this
-- database at all: there is no anon key, no PostgREST, and no url a browser could aim at a
-- table. The Worker is the only reader and the only writer, and it returns one scan by its
-- unguessable token and never a list.
--
-- One deliberate divergence carried over from the Postgres schema: the day boundary is
-- America/Chicago, not UTC, so "today" means the day it is in Texas. SQLite has no timezone
-- database, so the boundary is computed in the Worker and passed in, rather than asserted here
-- in a way that would quietly drift twice a year.

create table if not exists scans (
  id             text primary key,          -- uuid, crypto.randomUUID() in the worker
  created_at     integer not null,          -- unix seconds
  updated_at     integer not null,

  domain         text not null,
  status         text not null default 'queued',   -- queued|running|done|degraded|failed
  public_token   text not null unique,      -- 128 bits of crypto.getRandomValues, hex

  booking_url    text,
  jobs_signal    text,

  headline       text,
  result_html    text,

  -- Appended by the routine as the work happens, served by token while the scan runs so the
  -- requester can watch. A json array of {at, phase, kind, note}, and generic steps about
  -- their own scan only.
  progress       text not null default '[]',

  -- "send it to me when it is ready". NOTHING SENDS AUTOMATICALLY. It feeds a human-gated
  -- draft to the maintainer, same as every other path in this project.
  notify_email   text,

  -- The form's free-text box. Stored so a PERSON can read it, and never put in the trigger
  -- payload, so it cannot reach an agent as instructions. It arrived from a stranger through
  -- a public form: it is context for a human.
  note           text,

  request_ip     text,
  user_agent     text,
  error          text,
  run_ms         integer
);

create unique index if not exists scans_token_idx  on scans (public_token);
create index if not exists        scans_domain_idx on scans (domain, created_at desc);
create index if not exists        scans_ip_idx     on scans (request_ip, created_at desc);
create index if not exists        scans_made_idx   on scans (created_at desc);

-- THE CONFIG TABLE IS DELIBERATELY GONE. In Postgres it existed so the trigger url and secret
-- could be wired with one insert and no redeploy, which was a real convenience when a redeploy
-- meant a Deno function. A Worker takes its secrets from the dashboard, changed in the same
-- number of clicks and stored somewhere that is not a row anybody can select. Caps live as
-- plain vars next to them. A secret in a table you can query is a worse place than a secret in
-- a secret store, and there is now no reason to keep it.
