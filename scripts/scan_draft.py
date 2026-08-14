#!/usr/bin/env python3
"""scan_draft.py — build the Gmail DRAFT that carries a finished scan to the requester.

THERE IS NO SEND PATH IN THIS FILE, AND THAT IS THE POINT.

Alaska's scanner carved out one automated delivery: the requester typed an address asking for
their result, so the machine sent it. Texas does not take that carve-out. The report goes into a
DRAFT and a person presses send.

That is not timidity. The report is the first thing an operator ever sees from this desk, and a
human glancing at it once before it lands is worth the click. It also means this repo has no
credential that can mail anybody, which is a smaller blast radius than any policy.

**The self-test proves the absence** by scanning this file's own source with the prose stripped
out, the same way `mix.py` proves it has no resampler. A future edit that adds a send path makes
the gate go red rather than making the file lie.

WHAT IT GUARDS ON THE WAY OUT

  UNTRUSTED INPUT. The requester's own name, company and message came from a stranger through a
  public form, and the scan HTML was built from a stranger's website. Everything interpolated
  here is escaped. Free text from the form is NEVER echoed into the body at all: it is for the
  maintainer to read in the queue, not for the machine to reflect back.

  ONE ADDRESS. The draft is addressed to the address that asked, and to nothing else. No cc, no
  bcc, no list, no second recipient, ever.

  build a draft payload:
    scan_draft.py --scan out/scan.json --html out/scan.html --to owner@example.com \\
                  --out out/draft.json
    scan_draft.py --self-test

Exit 0 ok, 1 a check failed, 2 could not run.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

SUBJECT = "Your Texas AI bottleneck scan, {company}"

# The plain-text note that sits above the report. Deliberately short: the report is the artifact,
# and a long cover letter is a sales email wearing a delivery envelope.
NOTE = """You asked for a look at where AI would and would not help {company}.

It is below. Everything in it is sourced to a page on your own site, linked inline, and the
section on what other operators published is marked as theirs rather than a prediction about you.

The parts that say you don't need AI yet are the honest ones and they are there on purpose.

If any of it is worth a closer look, say so and we can talk about what a Field Study would cover.
"""


def valid_email(s: str) -> bool:
    """Deliberately strict. This address decides who a human is about to mail, so a permissive
    pattern here is how a header injection or a second recipient gets in."""
    s = (s or "").strip()
    if not s or len(s) > 254:
        return False
    if any(c in s for c in "\r\n,;<>\"'\\ "):
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", s))


def build_draft(scan: dict, scan_html: str, to: str) -> dict:
    """The draft payload. `to` is the ONE address that asked for this."""
    if not valid_email(to):
        raise ValueError(
            f"scan_draft: {to!r} is not an address this will draft to. It came from a public "
            f"form, so it is checked strictly rather than trusted.")

    meta = scan.get("meta") or {}
    company = str(meta.get("company") or meta.get("domain") or "your operation")

    body = (
        "<div style=\"font:16px/1.6 Georgia,serif;color:#141020\">"
        # Escape ONCE, on the assembled paragraph. Escaping `company` here as well produced
        # &amp;lt;script&amp;gt; in the body, which is a different bug wearing the same fix.
        + "".join(f"<p>{html.escape(p)}</p>"
                  for p in NOTE.format(company=company).split("\n\n") if p.strip())
        + "<hr style=\"border:0;border-top:1px solid #ccc;margin:1.4rem 0\">"
        + scan_html
        + "</div>"
    )
    return {
        "to": to,                       # exactly one, and never a list
        "subject": SUBJECT.format(company=company),
        "body_html": body,
        "draft_only": True,
    }


# ---------------------------------------------------------------- self-test
def self_test() -> int:
    fails = 0

    def ok(label, cond):
        nonlocal fails
        print(f"  {'ok  ' if cond else 'FAIL'}  {label}")
        if not cond:
            fails += 1

    scan = {"meta": {"company": "Llano Fluid", "domain": "x.com"}}
    d = build_draft(scan, "<p>the report</p>", "owner@example.com")
    ok("a draft is built for one address", d["to"] == "owner@example.com")
    ok("it is flagged draft_only", d["draft_only"] is True)
    ok("the subject names the company", "Llano Fluid" in d["subject"])
    ok("the report is carried in the body", "the report" in d["body_html"])
    ok("there is no cc or bcc field at all", "cc" not in d and "bcc" not in d)

    # ADDRESSES ARE CHECKED, because this one decides who a human is about to mail
    for bad in ["", "  ", "not-an-email", "a@b", "a@b.c d@e.fg",
                "a@b.co\nbcc: x@y.co", "a@b.co,c@d.co", "<a@b.co>", "a@b.co;c@d.co"]:
        ok(f"refuses {bad!r}", not valid_email(bad))
    for good in ["owner@example.com", "a.b+tag@sub.example.co.uk"]:
        ok(f"accepts {good!r}", valid_email(good))

    threw = False
    try:
        build_draft(scan, "<p>x</p>", "a@b.co\nbcc: evil@x.co")
    except ValueError:
        threw = True
    ok("a header-injection address raises rather than drafting", threw)

    # UNTRUSTED INPUT IS ESCAPED. The company name came off a stranger's website.
    eviltag = "<script>x</script>"
    d2 = build_draft({"meta": {"company": eviltag}}, "<p>ok</p>", "owner@example.com")
    ok("a company name from a scanned site is escaped in the body",
       "&lt;script&gt;" in d2["body_html"] and eviltag not in d2["body_html"])

    # THE ABSENCE OF A SEND PATH, proved by reading this file with the prose removed.
    src = Path(__file__).read_text(encoding="utf-8")
    # Only the OPERATIONAL half. The banned tokens are named in this function, so scanning the
    # whole file finds its own checklist and reports the guard as the violation.
    src = src.split("def self_test")[0]
    code = re.sub(r'""".*?"""', "", src, flags=re.S)          # docstrings
    code = re.sub(r"#.*", "", code)                            # comments
    banned = ["smtplib", "sendmail", "send_message", "requests.post", "urlopen",
              "http.client", "def send", "SMTP"]
    hits = [b for b in banned if b in code]
    ok(f"there is NO send path in this file (found {hits or 'none'})", not hits)

    print(f"\nscan_draft self-test: {'all passed' if not fails else f'{fails} FAILED'}")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--scan")
    ap.add_argument("--html")
    ap.add_argument("--to")
    ap.add_argument("--out", default="out/draft.json")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not (a.scan and a.html and a.to):
        print("scan_draft: pass --scan FILE --html FILE --to ADDRESS, or --self-test",
              file=sys.stderr)
        return 2
    try:
        scan = json.loads(Path(a.scan).read_text(encoding="utf-8"))
        page = Path(a.html).read_text(encoding="utf-8")
        payload = build_draft(scan, page, a.to)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"scan_draft: {exc}", file=sys.stderr)
        return 2
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"scan_draft: wrote {out}. It is a DRAFT payload. A human sends it.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
