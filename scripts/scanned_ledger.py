#!/usr/bin/env python3
"""scanned_ledger.py — the thirty day no-repeat, in code rather than in a paragraph.

WHAT IT GUARDS

CLAUDE.md, COST AND ABUSE DISCIPLINE: "the routine refuses more than one scan per domain per
thirty days (`ledger/scanned.json`, which holds domains and dates and nothing about the
business)". That was two rules with nothing enforcing either.

  THE SHAPE WAS DEFINED NOWHERE. The file shipped as `{"scanned": []}` and the run contract told
  a model to record "the domain and today's date". A model writing `{"domain": ..., "date": ...}`
  on Monday and `{"site": ..., "scanned_at": ...}` on Tuesday produces a ledger where Monday's
  entry is invisible to Tuesday's reader, and the no-repeat silently stops working. Nothing goes
  red. The next request for that domain just quietly bills a second scan.

  THE THIRTY DAY COMPARISON WAS DATE ARITHMETIC DONE BY A MODEL, which the compute-not-generate
  law assigns to Python for exactly the reason it assigns everything else.

  THE PRIVACY WALL HAD NO ENFORCEMENT EITHER. "Never a business fact, never an email" was prose
  above a free-form JSON file that anything could append anything to, in a repo whose whole
  design is that no requester data is ever written to git. A ledger is the one file in this repo
  that a run DOES write, so it is the one place that rule can be broken.

So the shape is pinned here, the arithmetic happens here, and a record carrying any key other
than `domain` and `date` is refused rather than written.

  scanned_ledger.py --check <domain>     is this domain clear to scan
  scanned_ledger.py --record <domain>    write it, after the scan is delivered
  scanned_ledger.py --self-test

`--check` exits 0 when the domain is clear and 1 when the no-repeat blocks it, printing the
earlier date. The run contract reads the EXIT CODE. Exit 2 could not run.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from normalize_domain import normalize_domain  # noqa: E402

WINDOW_DAYS = 30

LEDGER = Path(__file__).resolve().parents[1] / "ledger" / "scanned.json"

# THE WHOLE RECORD. Two keys, both required, nothing else permitted. This tuple is the schema,
# and `clean_record` refuses anything wider rather than trimming it quietly, because a run that
# tried to write a company name has a defect worth hearing about.
FIELDS = ("domain", "date")

ISO = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class LedgerError(ValueError):
    """A record or a file this module refuses to work with."""


def today_chicago() -> str:
    """The contract stamps America/Chicago, so the ledger agrees with the report's masthead."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/Chicago")).date().isoformat()
    except Exception:
        # A missing tzdata is not a reason to fail a scan. UTC is at worst a few hours out on a
        # thirty day window, and the fallback is stated rather than silent.
        print("scanned_ledger: no America/Chicago tzdata, stamping UTC instead", file=sys.stderr)
        return datetime.now(timezone.utc).date().isoformat()


def parse_iso(s: str) -> date:
    if not ISO.match(str(s or "")):
        raise LedgerError(f"{s!r} is not an ISO date, so no window can be measured from it")
    try:
        return date.fromisoformat(str(s))
    except ValueError as exc:
        raise LedgerError(f"{s!r} is not a real date ({exc})") from exc


def clean_record(rec) -> dict:
    """One record, or an explanation of why it is not one.

    The domain is put through `normalize_domain` on the way IN as well as on the way out, so a
    ledger written by an older run that stored `www.X.com/` still answers a check for `x.com`.
    """
    if not isinstance(rec, dict):
        raise LedgerError("a ledger entry must be an object")
    extra = sorted(set(rec) - set(FIELDS))
    if extra:
        raise LedgerError(
            f"a ledger entry carries {extra}, and this ledger holds domains and dates and "
            f"nothing about the business. See THE PRIVACY WALL in CLAUDE.md.")
    dom = normalize_domain(rec.get("domain"))
    if not dom:
        raise LedgerError(f"{rec.get('domain')!r} is not a domain this ledger can key on")
    return {"domain": dom, "date": parse_iso(rec.get("date")).isoformat()}


def load(path: Path = LEDGER) -> list[dict]:
    """Every usable record. A malformed one raises rather than being skipped, because a ledger
    that silently drops what it can't read is a no-repeat that silently switches off."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except json.JSONDecodeError as exc:
        raise LedgerError(f"{path} is not readable JSON ({exc})") from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("scanned"), list):
        raise LedgerError(f"{path} must be an object with a 'scanned' list")
    return [clean_record(r) for r in raw["scanned"]]


def last_scan(domain: str, records: list[dict]) -> str:
    """The most recent date this domain was scanned, or "" if it never was."""
    key = normalize_domain(domain)
    dates = [r["date"] for r in records if r["domain"] == key]
    return max(dates) if dates else ""


def days_since(earlier: str, today: str) -> int:
    """The arithmetic, done here. A run counting days by eye is the defect this replaces."""
    return (parse_iso(today) - parse_iso(earlier)).days


def check(domain: str, today: str, records: list[dict]) -> tuple[bool, str]:
    """(clear to scan, why not). A future-dated record blocks, since it is a clock problem and
    scanning through it would bill the second scan the window exists to prevent."""
    key = normalize_domain(domain)
    if not key:
        raise LedgerError(f"{domain!r} is not a domain this rule can use")
    earlier = last_scan(key, records)
    if not earlier:
        return True, ""
    n = days_since(earlier, today)
    if n >= WINDOW_DAYS:
        return True, ""
    if n < 0:
        return False, (f"{key} carries a scan dated {earlier}, which is after today ({today}). "
                       f"That is a clock problem rather than a no-repeat, so it stops here.")
    return False, (f"{key} was scanned on {earlier}, {n} day(s) ago. The window is "
                   f"{WINDOW_DAYS} days, so this request is a repeat and the scan does not run. "
                   f"A second scan of the same site inside a month costs money and says the "
                   f"same thing.")


def record(domain: str, today: str, path: Path = LEDGER) -> dict:
    """Append one record. Rewrites the whole file, normalised and sorted, so it stays diffable."""
    rows = load(path)
    rec = clean_record({"domain": domain, "date": today})
    rows.append(rec)
    rows.sort(key=lambda r: (r["date"], r["domain"]))
    path.write_text(json.dumps({"scanned": rows}, indent=2) + "\n", encoding="utf-8")
    return rec


def self_test() -> int:
    fails = 0

    def ok(label, cond, extra=""):
        nonlocal fails
        print(f"  {'ok  ' if cond else 'FAIL'}  {label}{'' if cond else '  ' + str(extra)}")
        if not cond:
            fails += 1

    rows = [{"domain": "permian-fluid.com", "date": "2026-07-20"}]

    # THE ARITHMETIC, which used to be a model counting days by eye
    ok("a scan inside the window blocks the repeat",
       not check("permian-fluid.com", "2026-08-14", rows)[0])
    ok("...and says how long ago, so the maintainer can answer the requester",
       "25 day(s) ago" in check("permian-fluid.com", "2026-08-14", rows)[1],
       check("permian-fluid.com", "2026-08-14", rows)[1])
    ok("a scan outside the window is clear again",
       check("permian-fluid.com", "2026-08-19", rows)[0])
    ok("the boundary is the thirtieth day, not the thirty-first",
       days_since("2026-07-20", "2026-08-19") == 30
       and check("permian-fluid.com", "2026-08-19", rows)[0]
       and not check("permian-fluid.com", "2026-08-18", rows)[0])
    ok("a domain never scanned is clear", check("new-shop.com", "2026-08-14", rows)[0])
    ok("the arithmetic crosses a month and a leap day without help",
       days_since("2024-02-27", "2024-03-01") == 3 and days_since("2026-12-20", "2027-01-10") == 21)
    ok("a future-dated record is a clock problem and it blocks rather than passing",
       not check("permian-fluid.com", "2026-07-01", rows)[0]
       and "clock problem" in check("permian-fluid.com", "2026-07-01", rows)[1])

    # THE KEY IS THE NORMALISED DOMAIN, so a second spelling is still the same business
    ok("every spelling of the domain hits the same record",
       all(not check(s, "2026-08-14", rows)[0]
           for s in ["https://www.Permian-Fluid.com/about", "PERMIAN-FLUID.COM",
                     "permian-fluid.com/quotes?utm=x"]))
    ok("...including a ledger written in an older run's spelling",
       not check("permian-fluid.com", "2026-08-14",
                 load_rows := [clean_record({"domain": "https://www.Permian-Fluid.com/",
                                             "date": "2026-07-20"})])[0]
       and load_rows[0]["domain"] == "permian-fluid.com")

    # THE SHAPE IS PINNED. This is the defect that silently switched the no-repeat off.
    for bad, why in [
        ({"site": "x.com", "scanned_at": "2026-08-14"}, "a second spelling of the keys"),
        ({"domain": "x.com", "date": "2026-08-14", "company": "X Fluid"}, "a business fact"),
        ({"domain": "x.com", "date": "2026-08-14", "email": "a@b.co"}, "an email address"),
        ({"domain": "x.com", "date": "August 14th, 2026"}, "a display date"),
        ({"domain": "hello world", "date": "2026-08-14"}, "an unusable domain"),
        ({"domain": "x.com", "date": "2026-02-30"}, "a date that does not exist"),
        ("permian-fluid.com", "a bare string"),
    ]:
        try:
            clean_record(bad)
            ok(f"{why} is refused", False, f"{bad!r} was accepted")
        except LedgerError as exc:
            ok(f"{why} is refused ({str(exc)[:46]}...)", True)

    # THE PRIVACY WALL, stated as the property rather than as a list of rejected keys
    ok("a written record can only ever hold a domain and a date",
       set(clean_record({"domain": "x.com", "date": "2026-08-14"})) == {"domain", "date"})

    # ...and the file round-trips
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "scanned.json"
        ok("a missing ledger is an empty one, not a crash", load(p) == [])
        record("https://www.Permian-Fluid.com/about", "2026-08-14", p)
        record("new-shop.com", "2026-07-01", p)
        back = load(p)
        ok("what was written comes back normalised", back[1]["domain"] == "permian-fluid.com",
           str(back))
        ok("...and sorted by date, so the file stays diffable",
           [r["date"] for r in back] == ["2026-07-01", "2026-08-14"], str(back))
        ok("...and a round trip blocks the repeat it was written for",
           not check("permian-fluid.com", "2026-08-15", back)[0])
        p.write_text('{"scanned": [{"site": "x.com"}]}', encoding="utf-8")
        try:
            load(p)
            ok("a ledger written in the wrong shape is refused, never skipped", False)
        except LedgerError:
            ok("a ledger written in the wrong shape is refused, never skipped", True)

    # THE REAL FILE. A committed ledger that this module can't read is a no-repeat that is
    # already off, and it would go unnoticed until the second scan of somebody's site.
    try:
        load()
        ok(f"the committed ledger at {LEDGER.name} loads", True)
    except LedgerError as exc:
        ok(f"the committed ledger at {LEDGER.name} loads", False, str(exc))

    print(f"\nscanned_ledger self-test: {'all passed' if not fails else f'{fails} FAILED'}")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", metavar="DOMAIN")
    ap.add_argument("--record", metavar="DOMAIN")
    ap.add_argument("--today", metavar="YYYY-MM-DD", help="defaults to today in America/Chicago")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()

    if a.self_test:
        return self_test()
    if bool(a.check) == bool(a.record):
        print("usage: scanned_ledger.py --check DOMAIN | --record DOMAIN | --self-test",
              file=sys.stderr)
        return 2

    try:
        today = a.today or today_chicago()
        parse_iso(today)
        rows = load()
        if a.check:
            clear, why = check(a.check, today, rows)
            if not clear:
                print(f"scanned_ledger: {why}", file=sys.stderr)
                return 1
            earlier = last_scan(a.check, rows)
            print("clear to scan"
                  + (f" (last scanned {earlier}, "
                     f"{days_since(earlier, today)} days ago)" if earlier else " (never scanned)"))
            return 0
        # RECORDING IS GUARDED BY THE SAME CHECK. A run that records twice on one domain writes a
        # second row that says nothing new and makes the file lie about how often it is scanned.
        clear, why = check(a.record, today, rows)
        if not clear:
            print(f"scanned_ledger: not recording. {why}", file=sys.stderr)
            return 1
        rec = record(a.record, today)
        print(f"recorded {rec['domain']} on {rec['date']}")
        return 0
    except (LedgerError, OSError) as exc:
        print(f"scanned_ledger: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
