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

What remains: the form carries a honeypot field and FormSubmit's own abuse handling, the
routine refuses more than one scan per domain per thirty days (`ledger/scanned.json`, which
holds domains and dates and nothing about the business), and a run that can't fetch the site
degrades honestly rather than retrying forever.

**Both of those are mechanisms now, not intentions.** The scan form keeps FormSubmit's captcha
ON, deliberately diverging from the docket's services form, which switches it off. A services
enquiry costs a maintainer the seconds it takes to read. A scan request is an item in a queue
that costs money and runs research when it is picked up, and the honeypot alone stops only a bot
careless enough to fill a field it can't see. The thirty day window is enforced by
`scripts/scanned_ledger.py`, which does the date arithmetic, pins the record shape, and refuses
any key other than `domain` and `date`. **Nothing hand-edits that ledger.** It was a free-form
file that a model appended to in whatever shape it chose, and a second spelling of the keys
makes an earlier entry invisible to the next check, which switches the no-repeat off with
nothing going red.

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

There is nothing to deploy. The form is static and posts to FormSubmit. The report is built
locally by the routine, and `scan_draft.py` puts it in a Gmail draft for a human to send.
