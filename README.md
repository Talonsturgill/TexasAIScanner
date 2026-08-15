# Texas AI Scanner

[![guards](https://github.com/Talonsturgill/texasaiscanner/actions/workflows/guards.yml/badge.svg)](https://github.com/Talonsturgill/texasaiscanner/actions/workflows/guards.yml)

The Bottleneck Scanner behind [alaskaaihq-style Texas AI Docket](https://github.com/Talonsturgill/TexasAIDocket).
A business asks for a look at its own public footprint, and gets back an honest map of where AI
would carry real load, where ordinary software does it cheaper, and where it has no business at
all, plus what operators in the same industry have already published about trying it.

**No database, no server, no send.** The form posts to FormSubmit, the routine runs the scan
locally, and the report goes into a Gmail draft that a human presses send on. `CLAUDE.md` carries
the reasoning for all three.

## Try the renderer offline

```
python3 scripts/build_scan_page.py --scan samples/sample-scan.json --out out/sample.html
```

## The gates

CI runs all of this on every pull request and every merge to main, and reads each one by its
EXIT CODE. A gate that prints advice on failure and one clean line on success looks equally
reassuring under `tail -1`.

```
python3 scripts/normalize_domain.py --self-test
python3 scripts/build_scan_page.py --self-test
python3 scripts/scan_draft.py --self-test
python3 scripts/repo_guards.py --self-test
```

Those four prove the checkers can go red. This one is the half that says anything about the
repo, and it holds the laws that live between files rather than inside one: no send path
anywhere, nothing about a requester in git, a ledger of domains and dates only, everything built
here wired to something, the form and the run contract still agreeing on what was promised, and
the house voice on both published surfaces.

```
python3 scripts/repo_guards.py
```

## Layout

`prompts/scan_routine.md` is the run contract. `knowledge/` holds the method: the feasibility
ladder, the Texas bottleneck map, and the privacy fences. `.claude/agents/` holds the four scan
agents. `config/scan_contract.md` is the shape of a report.
