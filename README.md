# Texas AI Scanner

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

```
python3 scripts/normalize_domain.py --self-test
python3 scripts/build_scan_page.py --self-test
python3 scripts/scan_draft.py --self-test
```

## Layout

`prompts/scan_routine.md` is the run contract. `knowledge/` holds the method: the feasibility
ladder, the Texas bottleneck map, and the privacy fences. `.claude/agents/` holds the four scan
agents. `config/scan_contract.md` is the shape of a report.
