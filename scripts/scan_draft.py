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
  here is escaped, and the company name is CLEANED before it reaches the subject as well as the
  body, because a subject line is a header and a scraped name can carry a newline. Free text from
  the form is NEVER echoed into the body at all: it is for the maintainer to read in the queue,
  not for the machine to reflect back.

  ONE ADDRESS. The draft is addressed to the address that asked, and to nothing else. No cc, no
  bcc, no list, no second recipient, ever.

  A FRAGMENT, NOT A DOCUMENT. Phase 6 renders a complete standalone page and Phase 7 hands it
  here, so the report arrives as `<!doctype html><html><head>...`. Dropping that into a div
  nests a whole document inside an email body, which is not html any client agrees on: the
  wrapper tags and the title get stripped or, worse, surface as a stray line above the report.
  The report is unwrapped to its body and its stylesheet is carried across with it.

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

If any of it is worth a closer look, say so. The next step is a conversation about what a Field
Study would cover.
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


def clean_name(raw) -> str:
    """The company name off a stranger's website, made fit for a HEADER.

    `valid_email` refuses a CR or an LF in the address and says why: a permissive pattern there
    is how a header injection or a second recipient gets in. The subject was taking the same
    class of string from a LESS trusted place, since the requester typed the address and an agent
    read the company name off a page, and it was interpolated raw.
    """
    s = "".join(" " if c in "\r\n\t" else c for c in str(raw or ""))
    s = "".join(c for c in s if c.isprintable())
    s = " ".join(s.split())
    return s[:120].strip()


def report_fragment(scan_html: str) -> str:
    """Unwrap a rendered report page down to what belongs inside an email body.

    Keeps the stylesheet, drops the doctype, the html/head/body wrapper and the title. A string
    that is already a fragment comes back untouched, so a caller passing a snippet still works.
    """
    doc = scan_html or ""
    body = re.search(r"<body[^>]*>(.*)</body\s*>", doc, flags=re.S | re.I)
    if not body:
        return doc
    # only from the head, so a style block already inside the body is not carried twice
    head = doc[:body.start()]
    css = "".join(m.group(0) for m in re.finditer(r"<style[^>]*>.*?</style\s*>", head,
                                                  flags=re.S | re.I))
    return css + body.group(1)


def build_draft(scan: dict, scan_html: str, to: str) -> dict:
    """The draft payload. `to` is the ONE address that asked for this."""
    if not valid_email(to):
        raise ValueError(
            f"scan_draft: {to!r} is not an address this will draft to. It came from a public "
            f"form, so it is checked strictly rather than trusted.")

    meta = scan.get("meta") or {}
    company = clean_name(meta.get("company")) or clean_name(meta.get("domain")) or "your operation"

    body = (
        "<div style=\"font:16px/1.6 Georgia,serif;color:#141020\">"
        # Escape ONCE, on the assembled paragraph. Escaping `company` here as well produced
        # &amp;lt;script&amp;gt; in the body, which is a different bug wearing the same fix.
        + "".join(f"<p>{html.escape(p)}</p>"
                  for p in NOTE.format(company=company).split("\n\n") if p.strip())
        + "<hr style=\"border:0;border-top:1px solid #ccc;margin:1.4rem 0\">"
        + report_fragment(scan_html)
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

    # THE SUBJECT IS A HEADER, and the name in it came off a page rather than out of the form
    d3 = build_draft({"meta": {"company": "Acme\r\nBcc: harvest@evil.co"}}, "<p>x</p>",
                     "owner@example.com")
    ok("a newline in a scraped company name never reaches the subject",
       "\r" not in d3["subject"] and "\n" not in d3["subject"])
    ok("...and the name still reads as itself", "Acme Bcc: harvest@evil.co" in d3["subject"])
    ok("an absurd scraped name is capped rather than carried",
       len(build_draft({"meta": {"company": "A" * 400}}, "<p>x</p>",
                       "owner@example.com")["subject"]) < 200)
    ok("a name that is only whitespace falls through to the honest default",
       "your operation" in build_draft({"meta": {"company": "   "}}, "<p>x</p>",
                                       "owner@example.com")["subject"])

    # THE REAL INPUT. Phase 6 renders a whole page and Phase 7 hands it straight to this file,
    # so the fixture is a whole page. Testing a fragment here is what hid the defect.
    page = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<title>Llano Fluid · Texas AI Docket</title>'
            '<style>\n.ob { border-left:3px solid var(--c); }\n</style></head>'
            '<body><div class="wrap"><h2>What the scan saw</h2><p>the report</p></div>'
            '</body></html>')
    d4 = build_draft(scan, page, "owner@example.com")["body_html"]
    ok("a rendered page is unwrapped, never nested whole inside the email body",
       all(t not in d4.lower() for t in ["<!doctype", "<html", "<head", "<title", "<body"]))
    ok("...and the title text does not leak in as a stray line", "Texas AI Docket" not in d4)
    ok("...while the report itself survives intact",
       "the report" in d4 and "What the scan saw" in d4)
    ok("...and so does its stylesheet, which carries the whole look",
       "border-left:3px solid var(--c)" in d4)
    ok("a caller passing a plain fragment still gets it through untouched",
       "<p>the report</p>" in build_draft(scan, "<p>the report</p>",
                                          "owner@example.com")["body_html"])

    # NO FIRST PERSON in the note this file writes, per the house rule
    person = sorted(set(re.findall(r"\b(?:we|we're|our|ours|us|I|I'm|my|mine)\b",
                                   NOTE + SUBJECT, flags=re.I)))
    ok(f"the cover note carries no first person (found {person or 'none'})", not person)

    # THE ABSENCE OF A SEND PATH, proved by reading this file with the prose removed.
    #
    # IT MUST READ THE WHOLE FILE EXCEPT THIS FUNCTION. The banned tokens are named right here,
    # so the scan has to skip the checklist or it reports the guard as the violation. Cutting at
    # `def self_test` did that and threw away everything after it too, which is `main()`: the one
    # function in the file that opens files, takes an address and would be where a send got
    # wired. A planted `smtplib.SMTP(...).send_message(...)` in main() passed this gate green.
    src = Path(__file__).read_text(encoding="utf-8")
    # Cut out exactly THIS function, from its def to the next top-level statement, and scan
    # everything else. Cutting at `def self_test` and stopping there was the bug.
    scanned = re.sub(r"^def self_test\b.*?(?=^\S|\Z)", "", src, flags=re.S | re.M)
    code = re.sub(r'""".*?"""', "", scanned, flags=re.S)       # docstrings
    code = re.sub(r"#.*", "", code)                            # comments

    banned = ["smtplib", "sendmail", "send_message", "requests.post", "urlopen",
              "http.client", "def send", "SMTP"]

    def send_paths(text: str) -> list[str]:
        return [b for b in banned if b in text]

    ok("the scan reaches main(), which is where a send would actually be wired",
       "def main" in code and "out.write_text" in code)
    ok("...and it still skips this function's own checklist", "banned = [" not in code)
    hits = send_paths(code)
    ok(f"there is NO send path in this file (found {hits or 'none'})", not hits)
    # A GATE THAT CANNOT FAIL PROVES NOTHING about what it guards.
    ok("...and the check goes red when a send path is planted",
       send_paths("x = smtplib.SMTP('h').send_message(p)") == ["smtplib", "send_message", "SMTP"])

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
        if not isinstance(scan, dict):
            raise ValueError(f"{a.scan} is not a scan object")
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
