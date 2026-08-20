# WORKLOG — off Supabase, onto the Worker that already runs

Opened 2026-08-20 on the owner's call: "I hate the supabase dependency its flaky,
lets get this done without supabase, like the whole thing".

**Read this first.** Resume from the task table at the bottom.

## What Supabase is actually doing

Seven things, and every one of them has to keep working:

| # | what | where it lives today |
| --- | --- | --- |
| 1 | hold a scan row for days, so a shared link still opens | `scanner.scans` |
| 2 | rate limit: a global daily cap and a per IP 24 hour cap | `scanner_today_count`, `scanner_ip_count` |
| 3 | serve a cached scan for a domain seen recently | `scanner_cached` |
| 4 | hold config: trigger url, trigger secret, turnstile secret, caps | `scanner.config` |
| 5 | serve ONE scan by its unguessable token | `scanner_get_by_token` |
| 6 | append the progress feed, mark running, mark done | `002_progress.sql` |
| 7 | set the notify address once, never overwrite | `scanner_set_notify` |

Plus three Deno functions in front of them, and a service role key.

**Nothing has to be migrated.** The published form has never successfully created
a row, `scanner.scans` holds nothing worth keeping, and the token space is
unguessable so no link outside points at one. This is a replacement, not a move.

## The decision, and why it is not really a choice

**One Cloudflare Worker at `workers/scan/`, one D1 database.** Everything above
lands there and Supabase goes away entirely.

The argument was already written in this project, in
`texasaidocket/workers/ask/worker.js`, about the ask box's own backend:

> WHY A WORKER AND NOT A SERVER. It holds two secrets and forwards one call.
> There is no schema to migrate, no project to pause and no row that can go
> stale. Cloudflare already serves the domain and Turnstile, so this adds a file
> rather than a vendor.

That is the same argument. The scan flow is the case it was never applied to.

**Why not KV**, which the ask worker already has bound and which needs no schema
at all: KV takes up to sixty seconds to propagate a write. The watch page polls
every three. A live feed on eventually consistent storage is a feed that lies,
and watching a run while it runs is the whole feature.

**Why not Durable Objects**, which would be the best fit on the merits: they need
a class migration through wrangler, and this project deploys a worker by pasting
ONE bundled file into the Cloudflare dashboard. `workers/ask/bundle.mjs` exists
for exactly that reason and says so: a terminal and a local checkout is "a fine
ask for a laptop and a poor one for a Chromebook". A design the owner cannot
deploy is not a design.

**Why D1**: strongly consistent, created and queried from the dashboard, bound to
a worker from the dashboard, same vendor that already serves the domain and
Turnstile and the ask worker. One vendor instead of two, and the schema is one
paste into a console the owner already uses for exactly this.

What this costs, honestly: it is still a schema. The complaint was flakiness and
a second vendor, not the existence of a table, and a scan token that has to
survive for days needs durable state somewhere. Anything that claims otherwise
is proposing to lose scans.

## The shape after

    form -> POST worker /request -> row + token -> fires the routine trigger
                                                     |
                                        routine POSTs /progress per line
                                                     |
    /scan/watch/?t=<token> -> polls worker /result -> renders the feed

Four routes, one worker, one binding. `scan_progress.py` does not change at all:
it reads its endpoint from the environment and is proved to hold no url of its
own, which is exactly what makes it repointable.

## What only the owner can do

1. Create a D1 database in the Cloudflare dashboard, paste `db/d1_schema.sql`
   into its console.
2. Create the Worker from `workers/scan/bundled.js`, bind the D1 database as
   `SCAN_DB`, set the secrets: `TRIGGER_URL`, `TRIGGER_SECRET`,
   `TURNSTILE_SECRET`, `PROGRESS_SECRET`.
3. Point `SCAN_PROGRESS_URL` and `SCAN_PROGRESS_SECRET` at it in the routine's
   environment.
4. Delete the Supabase project once the new path has run once.

## Tasks

| # | task | repo | state |
| --- | --- | --- | --- |
| A | Measure what Supabase does, decide the replacement | scanner | DONE |
| B | This worklog | scanner | DONE |
| C | `db/d1_schema.sql`, the whole record in one file | scanner | DONE |
| D | `workers/scan/` worker + bundler + tests | scanner | DONE, 79 checks |
| E | Delete `supabase/`, `db/schema.sql`, `db/migrations/` | scanner | DONE |
| F | `repo_guards`, README, `CLAUDE.md`, guards.yml | scanner | DONE |
| G | Docket repoints both constants and hands back the watch link | docket | TODO |
| H | `scanner_sync_check` contract moves with it | docket | TODO |

## Wrap

W1. Delete this file when every task is DONE.

## Found on the way, and worth a reader's time

`CLAUDE.md` carried a section headed **THERE IS NO DATABASE, AND THAT IS THE DESIGN (owner's
call, 2026-08-14)**, and the code stopped obeying it on the 15th when the form got its
gatekeeper. It stood contradicted for five days. Rewritten as a dated three-part record rather
than patched, because a doctrine the code ignores is worse than none: a reader trusts it.

The privacy half of it never wavered and is kept: the report is a DELIVERY and not a page,
nothing about a requester goes in git, and GitHub Pages being wholly public is why.
