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

## THERE IS NO DATABASE, AND THAT IS THE DESIGN (owner's call, 2026-08-14)

The Alaska scanner runs on Supabase: a `scanner` schema, four Edge Functions, RLS, unguessable
result tokens, and a shared project with a private `leadflow` machine. Texas keeps none of it.
**The result is EMAILED to the requester and stored nowhere.**

**Why not Supabase.** The owner does not want the dependency, and once the storage question is
asked honestly the rest of it falls away. Most of Alaska's wall exists to fence a public entry
point away from private prospect data in a shared database. Texas has no leadflow and no shared
database, so that entire class of risk is deleted rather than defended.

**Why not GitHub either, which is the more important half.** GitHub Pages is wholly public, so
a scan kept in the repo is published to the world. That is not ours to do. The report describes
a named business's operations, and they asked us to send it to them, not to post it. An
unguessable URL does not change that, because anyone can browse a public repo and read every
scan in it.

If a requester later WANTS their result public, that is a fine thing and it is their call to
make, not a default we take for them.

**So the report is a delivery, not a page.** The requester asks, the scan runs, the report goes
to the address they typed, and nothing about them persists anywhere public.

### What that removes, and what it costs

Removed: the `scanner` schema, all four Edge Functions, RLS, result tokens, the shared-project
fences, the domain cache, and the public API that spends money on demand. The abuse problem
shrinks to almost nothing, because there is no public endpoint firing agents. The privacy
problem is gone because nothing is published.

The cost is honest and worth stating: **there is no instant self-serve result page.** A
requester does not type a domain and watch a page build in ninety seconds. They ask, and the
report arrives. At the volume a consulting front door actually sees, that is the right trade,
and it can be revisited if the volume ever argues otherwise.

### What the wall becomes

Fences 1, 2, 2b, 3 and 8 port unchanged and still govern. Fence 5 (anon sees nothing) and fence
6 (nothing prospecty in git) are now true BY CONSTRUCTION rather than by configuration, which is
strictly stronger: there is no database to misconfigure and no result to leak. Fences 4 and 7
(the `in_pipeline` flag and the cross-schema opt-in) are retired, because there is no other
schema. This paragraph is their record, so a future reader does not go looking for them.

### The intake path

`https://alaskaaihq.com`-style FormSubmit is already how the docket's services form works, so
the scan form uses the same path: the form posts to FormSubmit, the maintainer's mailbox is the
queue, the routine runs the scan, and `scan_draft.py` writes the finished report into a Gmail
draft addressed to the requester. A human presses send. No token, no key, no server.

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

## COST AND ABUSE DISCIPLINE

There is no public endpoint that fires agents, which is most of this problem solved by not
having the thing. A scan costs money and runs research, so the trigger is a request that a
maintainer or a scheduled routine picks up, never a URL a stranger can hammer.

What remains: the form carries a honeypot field and FormSubmit's own abuse handling, the
routine refuses more than one scan per domain per thirty days (`ledger/scanned.json`, which
holds domains and dates and nothing about the business), and a run that cannot fetch the site
degrades honestly rather than retrying forever.

## VOICE

Operator-blunt, specific, receipts first, honest about limits. The docket's house rules hold:

No em dashes or en dashes anywhere. Ranges read "X to Y". No emojis. Straight quotes only.
Never "cannot", always "can't". Never open a sentence with "And" or "But". No first person in
published copy. Dates take the ordinal, month first.

**Colons.** The docket bans them in published prose. The scan PAGE is a labeled document rather
than prose, so a label colon is allowed there, the same carve-out the docket gives a data table.
Never a colon in a hooky sentence, and never a semicolon anywhere.

**If a scan could have been produced for any other business, it failed.**

## LAYOUT

- `prompts/` — `scan_routine.md` (the run contract) + `ROUTINE_PROMPT.txt` (the thin trigger text).
- `config/` — `brand.yaml` (tokens and voice), `scan_contract.md` (the scan.json shape and the
  tagging rules).
- `knowledge/` — `AI_SCOPING_LADDER` (the feasibility ladder), `BOTTLENECK_MAP` (the Texas
  industry map), `PRIVACY_WALL` (the fences).
- `.claude/agents/` — footprint-analyst, industry-scout, feasibility-mapper, scan-critic.
- `scripts/` — `normalize_domain.py` (the exact rule), `build_scan_page.py` (the self-contained
  renderer), `scan_draft.py` (builds the Gmail draft, and it has no send path in it).
- `web/scan.html` — the public form, served from the docket site at `/scan/`. Posts to
  FormSubmit, exactly as the services form does. No key, no token, no server.
- `ledger/scanned.json` — domains and dates only, the thirty day no-repeat. Never a business
  fact, never an email.
- `samples/` — a sample `scan.json` for offline rendering.

## SIBLING REPOS

| Repo | Relationship |
|---|---|
| `TexasAIDocket` | serves the public site, including `/scan/`. Vendors this repo's contract under `vendor/scanner/` for a sync check, and never edits it |
| `TexasAIDispatch` | the video engine. No relationship to this repo |

The Alaska repos are REFERENCE ONLY. Never write to them from a session here.

## MANUAL TEST

```
python3 scripts/build_scan_page.py --scan samples/sample-scan.json --out out/sample.html
python3 scripts/normalize_domain.py --self-test
```

There is nothing to deploy. The form is static and posts to FormSubmit. The report is built
locally by the routine, and `scan_draft.py` puts it in a Gmail draft for a human to send.
