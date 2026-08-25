# Texas AI Scanner (the inbound front door)

Source repo for the Texas AI Bottleneck Scanner: a public tool that reads a business's own
public footprint, on request, and returns an honest map of **where AI would actually help them,
where it would not, and what is already working in their industry.**

It is an OPPORTUNITY map, not an audit and not a critique. The value is that somebody who knows
this state looked at their operation and said something specific and useful, including the
parts where the honest answer is that they are already fine. That honesty is what makes the
opportunities believable, and it is the cheap, generous front door of the inbound funnel.

`prompts/scan_routine.md` is the master run contract. This file is the law above it and never
bends.

## What this repo IS and IS NOT

**IS.** A bounded, request-triggered routine that runs a shallow front slice of the method
(footprint research, published industry evidence, the feasibility ladder, an honesty gate) and
renders one short honest report, which is EMAILED to the requester. Four scan-mode agents. No
database and no server.

**IS NOT.** A deep engagement. It never finds a contact, never models full ROI, never sends
anything to anyone it was not asked to send to. It never writes to the docket repo's ledgers
and never touches the published record.

## THE ONE LAW (authoritative, overrides everything)

**This routine DIAGNOSES, and it NEVER SENDS ANYTHING.** It never emails a pitch, never
cold-messages a business, and never contacts an address it FOUND rather than was GIVEN.

Alaska carved out one sanctioned automated send, the requested delivery of a result to the
address the requester typed, through Buttondown. **Texas does not take that carve-out.** The
report is written into a Gmail DRAFT, addressed to the requester, and a human presses send.

That is better here for a reason beyond consistency with the rest of this project. The report
is the first thing an operator ever sees from us, and it should be good. The draft is where a
person confirms it is worth their attention before it lands, and it costs one click.

So: **draft only, forever, with no exceptions at all.** No Buttondown, no list, no subscriber
record, no send capability anywhere in this repo. The two Gmail artifacts per scan are the
DRAFT to the requester and, if it is worth one, an internal note to the maintainer. Neither is
a send.

## THE PRIVACY WALL

A public entry point that reads real businesses' sites and stores their results. The wall is
absolute. `knowledge/PRIVACY_WALL.md` is the enforced checklist.

- The scanner only ever handles the **requester's own public facts**. Every claim ABOUT THE
  REQUESTER traces to that company's own public information, fetched this run.
- **Published industry evidence** is the one other input and it is a separate lane. The
  industry-scout may read already-published public writing about what AI did in the requester's
  INDUSTRY anywhere in the world. That evidence is always labeled as someone else's published
  result, never blended into the requester's own facts, and never presented as something the
  requester will get.
- The scanner **never exposes another company's data** or any other requester's scan. There is
  nothing to expose: no database, no result page, no public endpoint. A report exists as an
  email to the one address that asked for it and nowhere else.
- **No requester data is ever written to git.** This repo holds the method and the code, never a
  scan result and never a lead. `out/` is gitignored and a scan artifact never leaves it.
- The per-scan lead draft is INTERNAL, addressed only to the maintainer.

## THE STORAGE QUESTION, ANSWERED THREE TIMES (current answer: 2026-08-20)

This section said **THERE IS NO DATABASE, AND THAT IS THE DESIGN** from 2026-08-14 until
2026-08-20, and the code stopped obeying it on the 15th. It is rewritten rather than patched,
because the reasoning is worth keeping and a doctrine the code ignores is worse than no
doctrine: a reader trusts it, and it is a lie.

**14th, no database.** The Alaska scanner runs on Supabase with a shared `leadflow` machine
beside it, and most of its wall exists to fence a public entry point away from private prospect
data in that shared project. Texas has neither, so that class of risk could be deleted rather
than defended. The result would be emailed and stored nowhere.

**15th, a database.** The form got a second path, because a mailbox is a fine queue for a person
and a poor one for a machine, and firing the routine on submit needs something server-side. That
brought a Supabase project with it, and this section was not updated. It stood contradicted for
five days.

**20th, still storage, different vendor.** The owner asked for a live progress view, which
cannot exist without somewhere to put the feed, and then said plainly of Supabase: "I hate the
dependency its flaky, lets get this done without supabase". Both are satisfied by moving to a
**Cloudflare Worker and a D1 database**, which is `workers/scan/` and `db/d1_schema.sql`.

**Why Cloudflare rather than another Postgres.** It already serves the domain, Turnstile and the
ask box's worker, so this is one vendor instead of two, and the ask worker had already written
the argument: it "adds a file rather than a vendor". Not KV, which needs no schema but takes up
to sixty seconds to propagate a write, and the watch page polls every three: eventually
consistent storage turns a live view into a view that lies. Not Durable Objects, which fit best
on the merits but need wrangler, and this project deploys a worker by pasting one bundled file
into the dashboard.

**What did not change is the half that matters.** The report is still a DELIVERY and not a page.

**Not GitHub, and this half never wavered.** GitHub Pages is wholly public, so a scan kept in
the repo is published to the world. That is not ours to do. The report describes a named
business's operations and they asked us to send it to them, not to post it. An unguessable URL
would not fix it, because anyone can browse a public repo and read every scan in it. No scan
result and no requester detail is ever written to git, and that is why the record lives in a
database the site cannot serve rather than in a file the site publishes.

If a requester later WANTS their result public, that is a fine thing and it is their call to
make, not a default we take for them.

**So the report is a delivery, not a page.** The requester asks, the scan runs, the report goes
to the address they typed, and nothing about them persists anywhere public.

### What that removes, and what it costs

Removed: the `scanner` schema, all four Edge Functions, RLS, result tokens, the shared-project
fences, the domain cache, and the public API that spends money on demand. The abuse problem
shrinks to almost nothing, because there is no public endpoint firing agents. The privacy
problem is gone because nothing is published.

That last paragraph used to end "there is no instant self-serve result page", and that is the
line the 20th revisited exactly as it invited. There is now a page that watches the run, at
`/scan/watch/?t=<token>` in the docket repo, and what it shows is the run reporting itself. What
it still does NOT show is the report: the html lands on the row and the delivery is a human
gated draft, same as it ever was.

### What the wall becomes

Fences 1, 2, 2b, 3 and 8 port unchanged and still govern. Fences 4 and 7 (the `in_pipeline`
flag and the cross-schema opt-in) are retired, because there is no other schema. This paragraph
is their record, so a future reader does not go looking for them.

Fence 5 (anon sees nothing) held in Postgres through RLS with no policies, which is a
CONFIGURATION and could be turned off by one migration. On D1 it holds by construction: nothing
but the worker has a binding, there is no anon key and no query endpoint, and `workers/scan/db.js`
is the complete list of questions anybody can ask the record. Every one is a literal statement
with bound parameters, and `getByToken` names the four fields that may leave a row, so the free
text, the address and the request ip stay on it. That is checked, in `workers/scan/test.js`,
against a real SQLite loaded from the real schema.

### The intake path

**REVISED 2026-08-15. The first version used FormSubmit and no server at all**: the form
posted to FormSubmit, the maintainer's mailbox was the queue, and a human pasted the request
into the routine by hand. That was a real design and it is written down here because the reason
it changed matters more than the change.

A mailbox is a fine queue for a person and a poor one for a machine. Firing the routine the
moment somebody submits needs something that can hold an Anthropic API key and call the routines
fire endpoint, and a key cannot live in a static page. So the form posts to a gatekeeper, which
is the only thing the public talks to. **REVISED AGAIN 2026-08-20**: that gatekeeper is now
`POST /request` on the scan Worker rather than a Supabase Edge Function. Same job, same order,
same refusals; a different machine holds the secret.

**IT FIRES A ROUTINE, NOT THE API.** Worth stating plainly because the gatekeeper holds an
Anthropic credential and that is easy to misread. The call is the routines fire endpoint,
`POST .../routines/<id>/fire` with the `experimental-cc-routine` beta header, which runs the
scan as a routine on the owner's subscription. Nothing in this repo bills per token. Do not
"simplify" this into a Messages API call: it would work, and it would move the cost of every
public form submission onto a meter.

**BOTH PATHS ARE LIVE, and the old one is the fallback rather than the ex-path.** With
JavaScript the form posts to the Edge Function and the scan starts on submit. Without it, or if
that request never reaches the network, the plain FormSubmit POST still happens and the
maintainer still gets the email. A migration that can take the form down is a migration that
will, so this one cannot.

A REFUSAL IS NOT A FAILURE and is never retried down the old path. Falling through to
FormSubmit on a 429 would post around the daily cap, which is the one thing standing between a
public form and a bill. Only a network error falls back.

What the gatekeeper does, in order: verifies the Turnstile captcha, enforces a global daily cap
and a per-IP cap, serves a cached scan for a domain seen in the last week, writes a `scans` row,
and fires the routine with a Bearer token it holds server-side. `POST /result` hands one scan
back by its unguessable token and nothing else, and `POST /progress` is the routine's only way
to write.

What did NOT change, and is the part that matters: **nothing sends.** The routine still writes
the finished report into a Gmail draft addressed to the requester and a human presses send.

WHAT THE CHANGE COSTS, stated plainly rather than buried. There is now a database holding a
domain, an IP and a user agent per request, where before there was an email in one mailbox. The
privacy wall is what keeps that honest: RLS is on with no policies, so the anon key reads
nothing, every access goes through eight named service-role-only RPCs, and the only shape the
browser can ever get back is one scan by its own token.

CAPS ARE THE THING THAT REPLACED THE HUMAN. When a person pasted each request in, they were the
ceiling on spend. Auto-firing removes that, so the ceiling is now `daily_cap` and `ip_cap` in
`scanner.config`, and the captcha FAILS CLOSED: a missing Turnstile secret refuses every request
rather than waving them through, because the alternative is a failure you notice on a bill.

## HONESTY (the gate and the brand)

Every observation traces to a page fetched THIS RUN. Never invent a fact, a number, or a
signal. Labor framing is a range with a stated assumption, never a lone hero number. The honest
"you do not need AI for this" is a FEATURE, not a failure, and it is the whole reason a
national tool can't fake this. The scan-critic defaults to reject. If a site is too thin to say
anything true, the scan degrades to an honest "we could not see enough of your public
footprint" result rather than fabricate one.

**A fabricated observation is the single unforgivable failure.** On a public surface it is
delivered straight to the operator it is about, in a market where everyone talks.

## NUMBERS ARE COMPUTED, NEVER GENERATED

Inherited from the docket and it holds here. Every numeral this scanner publishes is produced
by code from data and can be recomputed. A model that writes "about 40 hours a week" is
guessing at a formatting problem it does not know it has. Ranges are computed from a stated
assumption, and the assumption is printed beside the range.

**The mechanism, because a law with no mechanism is a habit.** `scripts/labor_math.py` owns the
one piece of arithmetic in the scanner. The feasibility-mapper supplies what it OBSERVED and
never the answer, and a `labor_framing` written as a plain string may carry no quantity at all,
in digits or spelled out. `build_scan_page.py` then **refuses to write the page** when a numeral
in the scanner's own copy about the requester traces to no computation and to no quoted source.

That gate covers the headline, the operation names, the human checks, the where-not-to-use-AI
line, the limits and the next step. It deliberately does NOT cover a verbatim quote or the
industry lane, and the boundary is stated in the code rather than implied: those are somebody
else's numbers with a source rendered beside them, the contract requires a published result to
be exact as published, and rewriting one to satisfy a gate would be the real dishonesty.

## COST AND ABUSE DISCIPLINE

There is no public endpoint that fires agents, which is most of this problem solved by not
having the thing. A scan costs money and runs research, so the trigger is a request that a
maintainer or a scheduled routine picks up, never a URL a stranger can hammer.

What remains, and **the order matters because only the first one prevents a spend**:

1. **The worker's domain window, thirty days, in D1.** It runs on the request, before the
   routine is fired, and hands back the earlier report rather than paying for a new one. This is
   the ceiling that actually holds.
2. **The routine's own no-repeat**, `ledger/scanned.json`, domains and dates and nothing about
   the business. It covers a run fired by hand rather than through the form, which the worker
   never sees. It runs after the container is already up, so it saves the research and not the
   startup.
3. The honeypot field and FormSubmit's own abuse handling, and a run that can't fetch the site
   degrades honestly rather than retrying forever.

**BOTH WINDOWS WERE WRONG UNTIL 2026-08-25, in different ways, and the record of it belongs
here.** The worker's was set to 168 hours while every document promised thirty days, so a paid
rescan on day eight was allowed by the only thing that could have refused it. The routine's was
worse: Phase 7 wrote the ledger into a container that is reclaimed when the run ends and no
phase ever committed it, so on `main` that file has never held a single entry and Phase 0 has
answered "clear to scan" to every domain that ever asked. **A guard reading a file nothing
persists is not a weak guard, it is a green light with a guard's name on it.** `repo_guards`
GUARD 7 now pins the record step to the push step so they cannot be separated again.

**These are mechanisms now, not intentions**, and that claim was false for the no-repeat half
from the day it was written until 2026-08-25. It is worth saying twice because it is the exact
shape of every fault this repo has had. A rule written down, a checker built for it, and no
mechanism carrying the checker's answer to the next run.

The scan form keeps FormSubmit's captcha ON, deliberately diverging from the docket's services
form, which switches it off. A services enquiry costs a maintainer the seconds it takes to read.
A scan request is an item in a queue that costs money and runs research when it is picked up,
and the honeypot alone stops only a bot careless enough to fill a field it can't see.

**The thirty day window is enforced in two places and they are not interchangeable.** The
worker's `CACHE_HOURS` is the one that stops the spend, because it answers before the routine is
fired. `scripts/scanned_ledger.py` is the routine's own, for a run that never went through the
worker: it does the date arithmetic, pins the record shape, and refuses any key other than
`domain` and `date`. **Nothing hand-edits that ledger.** It was a free-form file that a model
appended to in whatever shape it chose, and a second spelling of the keys makes an earlier entry
invisible to the next check, which switches the no-repeat off with nothing going red. A record
that is never pushed does the same thing by a different route, which is GUARD 7.

## VOICE

Operator-blunt, specific, receipts first, honest about limits. The docket's house rules hold:

No em dashes or en dashes anywhere. Ranges read "X to Y". No emojis. Straight quotes only.
Never "cannot", always "can't". Never open a sentence with "And" or "But". Dates take the
ordinal, month first.

**Colons.** The docket bans them in published prose. The scan PAGE is a labeled document rather
than prose, so a label colon is allowed there, the same carve-out the docket gives a data table.
Never a colon in a hooky sentence, and never a semicolon anywhere.

**First person, split by surface**, for the same structural reason as the colon. The FORM is
public marketing copy served on the docket's own site and takes the docket's rule, no first
person, because a page about somebody else's operation that keeps saying "we" is talking about
itself. The REPORT is a letter to one operator who asked for it, and correspondence written in
the third person reads like a machine produced it, which is the opposite of what this product is
selling. `repo_guards.py` enforces exactly that split, so neither half drifts by accident.

Every rule here is CHECKED against the RENDERED surfaces rather than the source, because the
report a reader sees is assembled from f-strings and ledger fields and exists as a whole
sentence nowhere in the code. A quotation is stripped before the check and never rewritten to
fit a house rule, because editing a quote to suit our punctuation is falsifying it.

**If a scan could have been produced for any other business, it failed.**

## LAYOUT

- `prompts/` — `scan_routine.md` (the run contract) + `ROUTINE_PROMPT.txt` (the thin trigger text).
- `config/` — `scan_contract.md` (the scan.json shape, the labor framing forms, the tagging
  rules). There is no `brand.yaml` here. The palette is a handful of constants at the top of
  `build_scan_page.py`, beside the note on why the urgent red is absent, and the voice is the
  VOICE section above. A separate token file would be a second place for both to drift.
- `knowledge/` — `AI_SCOPING_LADDER` (the feasibility ladder), `BOTTLENECK_MAP` (the Texas
  industry map), `PRIVACY_WALL` (the fences).
- `.claude/agents/` — footprint-analyst, industry-scout, feasibility-mapper, scan-critic.
- `scripts/` — every one carries a `--self-test` that replays the defect it exists for, and they
  are run BY EXIT CODE and never by reading the last line.
  - `normalize_domain.py` — the exact rule. Fails loud rather than empty, because everything
    downstream keys on its output.
  - `labor_math.py` — the only arithmetic in the scanner. See NUMBERS ARE COMPUTED above.
  - `build_scan_page.py` — the self-contained renderer, and the numeral gate. Drops what it
    can't trace and refuses to write a page carrying a figure nobody computed.
  - `scanned_ledger.py` — the thirty day no-repeat. Owns `ledger/scanned.json` outright.
  - `scan_draft.py` — builds the Gmail draft, and it has no send path in it. Its self-test
    proves that by reading its own source, `main()` included.
  - `repo_guards.py` — the laws that live BETWEEN files, which no single script's self-test can
    see. Each of the above proves one FILE; every law in this document is about the REPO, and a
    second file importing `smtplib` passes all five suites because none of them is looking.
- `.github/workflows/guards.yml` — runs every gate above on each pull request and each merge to
  main, by EXIT CODE. Both halves: the self-tests, which prove the checkers can go red, and then
  the checks against the committed files, which is the half that says anything about this repo.
- `web/scan.html` — the public form, served from the docket site at `/scan/`. **A template, not
  a page.** `{FORM_ACTION}` is a required substitution, and served verbatim the form posts to
  that literal path, 404s, and loses every request with nobody told. Posts to FormSubmit, with
  the captcha ON, which is the one place it diverges from the services form. No key, no token,
  no server.
- `ledger/scanned.json` — domains and dates only, the thirty day no-repeat. Never a business
  fact, never an email. Written by `scanned_ledger.py` and never by hand.
- `samples/` — a sample `scan.json` for offline rendering. It is also a fixture: the renderer's
  self-test asserts the shipped sample passes the numeral gate and goes red when a typed figure
  is planted in it, so the gate can't pass by having nothing to check.

## SIBLING REPOS

| Repo | Relationship |
|---|---|
| `TexasAIDocket` | serves the public site, INCLUDING `/scan/`, which is live. It does not read this repo's `web/scan.html`, it re-authors the same form in Python, so there are two copies of one page and no sync check. See below |
| `TexasAIDispatch` | the video engine. No relationship to this repo |

**The front door is up.** The docket's site build renders its scan page from a `scan_page()`
function in its own site builder, wired into its page list, and its `FORM_ACTION` constant is a
live FormSubmit alias interpolated at build time, so no placeholder reaches the published page. A
request typed into that form lands in the docket mailbox. Verified against that repo's `main` on
2026-08-15th.

Paths over there are described rather than written as paths, deliberately. `repo_guards` GUARD 4
requires every path this file names to exist in THIS repo, which is the correct rule and caught
an earlier draft of this very paragraph citing the docket's builder by path.

**What is actually missing is narrower, and it is a drift risk rather than a dead end.** The
docket does not read `web/scan.html`. It writes the same copy again, in Python, in its own file.
Two copies of one page with nothing comparing them is how they end up promising different things
to the same reader, and they had already drifted once: this repo's copy still said "Give us your
website. We read what is public" after the published page had been rewritten out of the first
person. `repo_guards` GUARD 5 pins the PROMISES in this repo's copy against the run contract,
which is the half that matters most, and nothing yet compares either against what the docket
actually serves. The `vendor/scanner/` sync check named in the port manifest is the intended
answer and does not exist yet. Standing it up is the docket's `site` actor's work, not this
repo's.

An earlier version of this section said `/scan/` was not live at all and that requests could not
arrive. That was written against a docket state that was already stale when it was written, and
it was wrong. The lesson is the one this repo keeps relearning in other forms: **a claim about
another repo has to be checked against that repo, not remembered.**

The Alaska repos are REFERENCE ONLY. Never write to them from a session here.

## MANUAL TEST

```
python3 scripts/build_scan_page.py --scan samples/sample-scan.json --out out/sample.html

python3 scripts/normalize_domain.py --self-test
python3 scripts/labor_math.py       --self-test
python3 scripts/build_scan_page.py  --self-test
python3 scripts/scanned_ledger.py   --self-test
python3 scripts/scan_draft.py       --self-test
python3 scripts/repo_guards.py      --self-test
```

**Run them by exit code.** Each prints advice on a failure and one clean line on success, which
looks reassuring either way under `tail -1`. Everything CI runs, in one line:

```
for g in normalize_domain labor_math build_scan_page scanned_ledger scan_draft repo_guards; do
  python3 scripts/$g.py --self-test >/dev/null || echo "RED: $g"; done
python3 scripts/repo_guards.py || echo "RED: the repo itself"
```

The six self-tests prove the checkers can go red. The last line is the half that says anything
about THIS repo, and it is the one that catches what no single file can see.

DEPLOYING. The page is static. The backend is one Cloudflare Worker and one D1 database, both
made in the dashboard, because a terminal and a local checkout is a fine ask for a laptop and a
poor one for a Chromebook. The report is still built locally by the routine, and `scan_draft.py`
still puts it in a Gmail draft for a human to send.

1. ~~Create a D1 database, paste `db/d1_schema.sql` into its console.~~ DONE 2026-08-20:
   `texas-scan`, `3f20a8f7-6cf8-4de7-a514-fc739dae27e3`, in ENAM with read replication
   off. The id is pinned in `workers/scan/wrangler.toml`, so nothing needs creating and
   a second database is the wrong answer if something looks unbound. The schema is
   idempotent, so re-running it is safe.
2. Create a Worker from `workers/scan/bundled.js`, which is generated and never hand edited:
   run `node workers/scan/bundle.mjs`, and `workers/scan/test.js` fails if it is stale.
3. Bind the database to the Worker as **`SCAN_DB`**.
4. Set four secrets. None of them belongs in this repo:

       TRIGGER_URL        https://.../routines/<routine id>/fire
       TRIGGER_SECRET     the credential that fires the ROUTINE, see above
       TURNSTILE_SECRET   the Cloudflare Turnstile secret
       PROGRESS_SECRET    the append-only secret the routine holds

5. Optional vars, which are plain and not secret: `DAILY_CAP` (25), `IP_CAP` (2),
   `CACHE_HOURS` (720, which is the thirty days the rest of this file promises),
   `CAPTCHA_REQUIRED` (true), `SCAN_ORIGIN`. **If this worker was deployed with `CACHE_HOURS`
   set in the dashboard, the variable wins over the new default and has to be changed there
   too.**

`PROGRESS_SECRET` is the one the routine carries, and it is deliberately the weakest thing here:
it appends a line to a scan whose uuid the caller already holds, and reads nothing. The routine
fetches pages a stranger named, so what it carries is chosen on the assumption that it leaks.
