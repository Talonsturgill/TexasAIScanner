# WORKLOG — the live progress view

Opened 2026-08-20 on the owner's call: "yeah build the live progress view".

**Read this first.** Resume from the task table at the bottom.

## What the copy promised and what the product does

The homepage scanner section says a research team goes to work when you press it.
It deliberately does NOT say you can watch, because you can't. The owner asked for
the version where you can.

## The finding, measured before any code

The backend for this **already exists and is deployed**. It was built and never
connected.

| piece | state | evidence |
| --- | --- | --- |
| `scanner.scans.progress` jsonb | built | `db/schema.sql`, commented "served by token while the scan runs so the requester can watch" |
| `public_token` | built | 128 bits of `gen_random_bytes`, the credential |
| `scan-request` edge function | DEPLOYED | `OPTIONS` returns 200 |
| `scan-result` edge function | DEPLOYED | `OPTIONS` returns 200 |
| published form calls it | **NO** | posts to `formsubmit.co`, so no row and no token ever exists |
| routine appends progress | **NO** | zero mentions of `progress`, `public_token`, `supabase` in `prompts/` or `scripts/` |
| a page that watches | **NO** | does not exist |

`scan-request` validates the domain, verifies Turnstile, enforces per-IP and daily
caps, serves a cached scan for a recently seen domain, creates the row, and fires
the routine's API trigger with a secret it holds server-side. It returns
`{token, status, cached}`. `scan-result` takes the token and returns status,
headline, the progress feed, and the html once finished.

So the work is wiring, a routine that reports itself, and a page. Not a backend.

## What only the owner can answer

1. **Is `trigger_url` / `trigger_secret` set** in `scanner.config`? Without it
   `scan-request` returns "scanner not fully configured" and the row is marked
   failed. Cannot be checked from here: the config RPC is service-role only.
2. **Is Turnstile configured** (`turnstile_secret`, and a site key for the form)?
   `captcha_required` defaults on.
3. **Switching the form away from FormSubmit changes the delivery story.** Today
   every request lands in the maintainer's mailbox and a person reads it. The DB
   path fires an automated trigger instead. `scanner_sync_check` in the docket repo
   enforces the field names, the hidden `_subject`/`_captcha` values and five
   written promises against a pinned vendored copy; that contract has to move with
   it, deliberately, not by accident.

## The shape

    form -> scan-request -> row + token -> routine trigger
                                             |
                                    routine appends progress per phase
                                             |
    /scan/watch/?t=<token> -> polls scan-result -> renders the feed

## Tasks

| # | task | repo | state |
| --- | --- | --- | --- |
| A | Measure what exists, probe the endpoints | scanner | DONE |
| B | This worklog | scanner | DONE |
| C | Watch page, polling `scan-result`, stub-tested | docket | DONE |
| C2 | The write side: `002_progress.sql` + `scan-progress` function | scanner | DONE, owner must apply + deploy |
| D | `scan_progress.py` helper the routine calls per phase | scanner | DONE |
| E | Routine phases updated to report themselves | scanner | DONE |
| F | Form switched to `scan-request` + Turnstile | docket | TODO, unblocked 2026-08-20 |
| G | `scanner_sync_check` contract updated to match | docket | BLOCKED on F |

The owner answered Q1 and Q2 on 2026-08-20: trigger url, trigger secret and
Turnstile are all set, and the form reuses the site key already on the site. So F
is unblocked and it is the one that changes a written promise.

## What only the owner can do, for C2

Nothing here reaches Supabase: there is no project credential in this session and
no MCP tool for it. The write path ships as source and lands when the owner runs
two commands.

1. Apply `db/migrations/002_progress.sql` to the project. It adds
   `scanner_progress`, `scanner_mark_running` and `scanner_mark_done`.
2. Deploy `supabase/functions/scan-progress`, and set its `PROGRESS_SECRET`.
3. Set `SCAN_PROGRESS_URL` and `SCAN_PROGRESS_SECRET` in the routine's
   environment, or `progress_secret` in `scanner.config`.

Until then `scan_progress.py` declines quietly and the run is exactly what it was.

## Wrap

W1. Delete this file when every task is DONE.
