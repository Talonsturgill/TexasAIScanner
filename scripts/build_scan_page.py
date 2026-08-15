#!/usr/bin/env python3
"""build_scan_page.py — render scan.json into one self-contained HTML report.

WHY THE DATA AND THE RENDER ARE SEPARATE

Because the traceability rule has to be enforced by something that cannot be talked out of it.
**This renderer DROPS any observation whose signal has no source.** Not warns, drops. An
observation that cannot point at a page the footprint-analyst fetched does not appear in the
report, whatever the assembling step believed about it. A shorter true scan beats a padded one,
and the only way to guarantee that is to make the padded version unrenderable.

It also keeps the TWO LANES apart by construction. Observations are claims about the requester
and render in the main column. Industry wins are other operators' published results and render in
their own section with their own treatment. The renderer never puts an industry source under an
observation, because it never reads from that field.

SELF-CONTAINED ON PURPOSE. One file, inline CSS, no fonts to fetch, no scripts, no tracking. It
goes in an email and it may get printed, so it is paper-coloured with dark ink and it survives
being saved to disk with no network.

  build_scan_page.py --scan samples/sample-scan.json --out out/sample.html
  build_scan_page.py --self-test

Exit 0 ok, 1 a check failed, 2 could not run.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import labor_math  # noqa: E402  (sibling module, path fixed on the line above)

# The Texas palette, from the docket's theme. Red (#BF0A30) is deliberately ABSENT: the brand
# reserves it for genuine urgency such as an open comment deadline, and a report about somebody's
# quoting process is not urgent. Borrowing the urgent colour for emphasis is how it stops meaning
# anything.
INK = "#141020"
PAPER = "#F6F1E4"
RUST = "#9A3B2A"
SLATE = "#3A4A63"
MUTED = "#6B6559"

TAGS = {
    "would_help": ("Worth building", RUST,
                   "AI genuinely earns its place here."),
    "rules_first": ("Rules first", SLATE,
                    "Ordinary software or a sensor does this cheaper and safer."),
    "not_ai": ("Leave it alone", MUTED,
               "This pocket should not have AI in it."),
}

RUNGS = {
    "rules": "Rules, deterministic software",
    "retrieval": "Retrieval, search over their own data",
    "single_llm": "One model call, checked",
    "workflow": "A workflow, model inside fixed steps",
    "agent": "An agent, plans its own steps",
}


def e(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def safe_url(raw) -> str:
    """A FETCHED PAGE HAS AN HTTP URL. Anything else is not a source, and it is not a link.

    `html.escape` makes a url safe to sit inside an attribute. It does nothing at all about what
    the url DOES, so `javascript:alert(1)` escapes cleanly and then runs when the maintainer
    opens out/scan.html to check the report before sending it. The source strings are picked out
    of a stranger's website by an agent, which is exactly the input the escaping gate exists for.
    """
    u = str(raw or "").strip()
    return u if u[:7].lower() == "http://" or u[:8].lower() == "https://" else ""


def industry_sources(scan: dict) -> set[str]:
    """Every url the industry lane cites, for the collision check below."""
    ind = scan.get("industry") or {}
    out = set()
    for item in list(ind.get("wins") or []) + list(ind.get("cautions") or []):
        u = safe_url((item or {}).get("source"))
        if u:
            out.add(u)
    return out


def usable_observations(scan: dict) -> list[dict]:
    """THE TRACEABILITY GATE. An observation with no fetched source is not an observation.

    It also refuses a source that CROSSED THE LANES. The docstring above claims this renderer
    keeps the two lanes apart by construction, and reading them out of separate fields only
    keeps the FIELDS apart: an assembling step that pastes an industry case-study url into
    `signal.source` gets it rendered under "What the scan saw", beneath a paragraph promising
    that nothing there is inferred from anyone else's business. One url can't be both the
    requester's own page and another operator's published result, and lane mixing is one of the
    three things the run contract says ends a run badly, so the collision is dropped here rather
    than left to a model to notice.
    """
    crossed = industry_sources(scan)
    out = []
    for o in scan.get("observations") or []:
        o = o or {}
        src = safe_url((o.get("signal") or {}).get("source"))
        if not src:
            continue
        if src in crossed:
            continue
        if o.get("tag") not in TAGS:
            continue
        out.append(o)
    return out


def usable_wins(scan: dict) -> list[dict]:
    """An industry win with no source is somebody's memory, which is the same failure as an
    invented observation and is dropped the same way."""
    return [w for w in ((scan.get("industry") or {}).get("wins") or [])
            if w and safe_url(w.get("source"))]


def labor_line(o: dict) -> tuple[str, list[str], str]:
    """The labor framing, COMPUTED. See scripts/labor_math.py for why it is not a free string."""
    return labor_math.render((o or {}).get("labor_framing"))


# ---------------------------------------------------------------- the numeral gate
#
# THE LAW, from CLAUDE.md: "Every numeral this scanner publishes is produced by code from data
# and can be recomputed. A model that writes 'about 40 hours a week' is guessing at a formatting
# problem it does not know it has."
#
# WHAT THIS GATE COVERS, AND WHAT IT DOES NOT. Stating the boundary is the point, because a gate
# believed to cover more than it does is worse than no gate.
#
#   COVERED: the copy that makes a claim ABOUT THE REQUESTER, in the scanner's own voice. The
#   headline, the operation names, the human checks, the where-not-to-use-AI line, the limits and
#   the next step. This is where an invented number does the damage the law describes, because it
#   is delivered straight to the operator it is about, who knows what the real figure is.
#
#   NOT COVERED, on purpose: a verbatim quote from a page fetched this run, and the whole
#   industry lane. A quote is evidence with its source rendered beside it, and the contract
#   requires an industry `published_result` to be EXACT AS PUBLISHED. Neither is the scanner
#   asserting a figure, and rewriting somebody's published number to satisfy a gate would be the
#   actual dishonesty.
#
# WHAT AUTHORISES A NUMERAL: a labor range this build computed, the date this build formatted, or
# a numeral that appears verbatim in one of the scan's own cited quotes. That last one is the
# scanner's version of "from data", since a quote is a string off a page the analyst fetched.
#
# THE PATTERN IS IMPORTED RATHER THAN COPIED. This gate and labor_math have to agree exactly
# about where a number starts and stops, or a figure authorised as "3.3" is checked as "3" and
# ".3" and passes on a page that authorises neither. Two identical regexes in one repo is that
# disagreement waiting for one of them to be edited.
NUMERAL = labor_math.NUMERAL


def authorised_numerals(scan: dict) -> set[str]:
    """Every numeral string this build either computed or can point at a fetched page for."""
    ok: set[str] = set()
    for o in usable_observations(scan):
        ok.update(labor_line(o)[1])
        # a numeral standing in the requester's own quoted words traces to a fetched page
        ok.update(m.group(0) for m in NUMERAL.finditer(str((o.get("signal") or {})
                                                           .get("quote") or "")))
    ok.update(m.group(0) for m in NUMERAL.finditer(show_date((scan.get("meta") or {}).get("date"))))
    return ok


def untraceable_numerals(scan: dict) -> list[str]:
    """Numerals in the scanner's OWN copy about the requester that trace to no computation."""
    prose = [str(scan.get(k) or "") for k in ("headline", "where_not_to_use_ai", "limits",
                                              "next_step")]
    for o in usable_observations(scan):
        prose += [str(o.get("operation") or ""), str(o.get("human_check") or ""),
                  labor_line(o)[0]]
    ok = authorised_numerals(scan)
    return sorted({m.group(0) for m in NUMERAL.finditer(" ".join(prose))} - ok)


MONTHS = ("January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December")


def show_date(raw) -> str:
    """The house rule takes the ordinal, month first, and keeps ISO for a stamp or a ledger
    field. The masthead date is neither, so the ISO the contract stores gets formatted HERE,
    in code, rather than typed into the contract in display form by whatever assembled it."""
    s = str(raw or "").strip()
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
    if not m:
        return s
    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not (1 <= mo <= 12 and 1 <= d <= 31):
        return s
    suffix = "th" if 11 <= d <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(d % 10, "th")
    return f"{MONTHS[mo - 1]} {d}{suffix}, {y}"


CSS = f"""
:root {{ color-scheme: light; }}
* {{ box-sizing: border-box; }}
body {{ margin:0; background:{PAPER}; color:{INK};
  font:16px/1.62 Georgia,'Iowan Old Style',serif; }}
.wrap {{ max-width: 46rem; margin:0 auto; padding: 2.6rem 1.25rem 4rem; }}
h1 {{ font-size:1.85rem; line-height:1.22; margin:.2rem 0 .5rem; letter-spacing:-.01em; }}
h2 {{ font-size:1.12rem; margin:2.4rem 0 .5rem; letter-spacing:.02em;
  text-transform:uppercase; color:{MUTED}; font-weight:700; }}
.meta {{ color:{MUTED}; font-size:.9rem; margin:0 0 1.6rem; }}
.rule {{ border:0; border-top:1px solid rgba(20,16,32,.16); margin:1.6rem 0; }}
.ob {{ border-left:3px solid var(--c); padding:.1rem 0 .1rem 1rem; margin:1.5rem 0 1.9rem; }}
.ob h3 {{ font-size:1.06rem; margin:0 0 .35rem; }}
.tag {{ display:inline-block; font:600 .72rem/1 -apple-system,system-ui,sans-serif;
  letter-spacing:.09em; text-transform:uppercase; color:#fff; background:var(--c);
  padding:.34rem .55rem; border-radius:2px; margin:0 0 .5rem; }}
.q {{ margin:.5rem 0; padding-left:.9rem; border-left:2px solid rgba(20,16,32,.18);
  color:{MUTED}; font-style:italic; }}
.q a {{ color:{MUTED}; }}
.rung {{ font:600 .85rem/1.5 -apple-system,system-ui,sans-serif; color:{SLATE}; margin:.4rem 0 0; }}
.note {{ font-size:.95rem; margin:.35rem 0 0; }}
.win {{ background:rgba(58,74,99,.06); border:1px solid rgba(58,74,99,.18);
  border-radius:3px; padding:1rem 1.1rem; margin:1rem 0; }}
.win h3 {{ font-size:1rem; margin:0 0 .3rem; }}
.win .who {{ font:600 .8rem/1.4 -apple-system,system-ui,sans-serif; color:{SLATE};
  text-transform:uppercase; letter-spacing:.06em; }}
.pub {{ font-weight:700; }}
.lane {{ font-size:.9rem; color:{MUTED}; margin:.2rem 0 1rem; }}
ol.src {{ font-size:.86rem; color:{MUTED}; padding-left:1.2rem; }}
ol.src a {{ color:{MUTED}; word-break:break-all; }}
a {{ color:{RUST}; }}
.foot {{ margin-top:2.6rem; font-size:.9rem; color:{MUTED}; }}
@media print {{ body {{ background:#fff; }} .wrap {{ max-width:none; }} a {{ color:{INK}; }} }}
"""


def render(scan: dict) -> str:
    meta = scan.get("meta") or {}
    obs = usable_observations(scan)
    wins = usable_wins(scan)
    ind = scan.get("industry") or {}
    cautions = [c for c in (ind.get("cautions") or []) if c and safe_url(c.get("source"))]
    degraded = scan.get("status") == "degraded" or len(obs) < 3

    P = []
    P.append("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">")
    P.append("<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">")
    P.append("<meta name=\"robots\" content=\"noindex,nofollow\">")
    P.append(f"<title>{e(meta.get('company') or 'Scan')} · Texas AI Docket</title>")
    P.append(f"<style>{CSS}</style></head><body><div class=\"wrap\">")

    # Built from the parts that are actually there. Joining a fixed template instead printed
    # "Bottleneck scan for  · " on a meta that was missing a field, which is a masthead with a
    # hole in it on the first thing an operator ever sees.
    who = e(str(meta.get("company") or "").strip()) or "your operation"
    if str(meta.get("place") or "").strip():
        who += f", {e(str(meta.get('place')).strip())}"
    bits = [f"Bottleneck scan for {who}"]
    if show_date(meta.get("date")):
        bits.append(e(show_date(meta.get("date"))))
    P.append(f"<p class=\"meta\">{' · '.join(bits)}</p>")

    if scan.get("headline"):
        P.append(f"<h1>{e(scan['headline'])}</h1>")

    if degraded:
        P.append("<p>This one is short, and honestly so. There was not enough on the public site "
                 "to say something specific about how the work actually runs, and a padded scan "
                 "would be worth less than a short true one.</p>")
        if obs:
            P.append("<p>What could be seen from the outside:</p>")

    # ------------------------------------------------------ lane 1, the requester
    if obs:
        P.append("<h2>What the scan saw</h2>")
        P.append("<p class=\"lane\">Every line below comes from a page on the site, linked at "
                 "the end. Nothing here is inferred from anyone else's business.</p>")
    for o in obs:
        label, colour, gloss = TAGS[o["tag"]]
        sig = o.get("signal") or {}
        src = safe_url(sig.get("source"))
        P.append(f"<div class=\"ob\" style=\"--c:{colour}\">")
        P.append(f"<span class=\"tag\">{e(label)}</span>")
        P.append(f"<h3>{e(o.get('operation'))}</h3>")
        if sig.get("quote"):
            P.append(f"<p class=\"q\">{e(sig['quote'])}<br>"
                     f"<a href=\"{e(src)}\">{e(src)}</a></p>")
        # An unknown rung prints NOTHING rather than printing itself. A typo in the tier used to
        # reach the operator as "Lowest thing that would work: agentic", and a missing one left
        # the label hanging over a blank. main() counts these so the run hears about it.
        rung = RUNGS.get(o.get("lowest_tier"))
        if rung:
            P.append(f"<p class=\"rung\">Lowest thing that would work: {e(rung)}</p>")
        P.append(f"<p class=\"note\">{e(gloss)}</p>")
        # The labor line is COMPUTED, and a framing that can't be computed prints nothing rather
        # than printing a number a model typed. main() names every one that was dropped.
        labor = labor_line(o)[0]
        if labor:
            P.append(f"<p class=\"note\">{e(labor)}</p>")
        # The human check belongs to a build. On a rules_first or not_ai pocket there is no
        # model to check, and printing "not applicable" there reads as a form with a blank in it.
        if o.get("human_check") and o["tag"] == "would_help":
            P.append(f"<p class=\"note\">Who catches a wrong answer: {e(o['human_check'])}</p>")
        P.append("</div>")

    if scan.get("where_not_to_use_ai"):
        P.append("<h2>Where AI does not belong</h2>")
        P.append(f"<p>{e(scan['where_not_to_use_ai'])}</p>")

    # ------------------------------------------------------ lane 2, published elsewhere
    # The heading is gated on WINS, not on wins-or-cautions. The scout is told to hunt failures
    # hardest, so a run that returns only cautions is a normal outcome, and it used to print
    # "What is working in this industry", promise other operators' published results, and then
    # show nothing at all under it.
    if wins:
        P.append("<h2>What is working in this industry</h2>")
        P.append("<p class=\"lane\">These are OTHER operators' published results"
                 + (f" in {e(ind.get('label'))}" if ind.get("label") else "")
                 + ". They are not predictions about this business and the scale is rarely the "
                   "same. They are here because seeing what actually shipped beats being told "
                   "what is possible.</p>")
    for w in wins:
        P.append("<div class=\"win\">")
        who = w.get("who") or "An operator"
        where = f" · {e(w['where'])}" if w.get("where") else ""
        P.append(f"<p class=\"who\">{e(who)}{where}</p>")
        P.append(f"<h3>{e(w.get('what_they_did'))}</h3>")
        if w.get("published_result"):
            P.append(f"<p class=\"note\"><span class=\"pub\">They published:</span> "
                     f"{e(w['published_result'])}</p>")
        if w.get("quote"):
            P.append(f"<p class=\"q\">{e(w['quote'])}</p>")
        if w.get("relevance"):
            P.append(f"<p class=\"note\">{e(w['relevance'])}</p>")
        wsrc = safe_url(w.get("source"))
        P.append(f"<p class=\"note\"><a href=\"{e(wsrc)}\">{e(wsrc)}</a></p>")
        P.append("</div>")

    if cautions:
        P.append("<h2>Where it did not work</h2>")
        # THE SENTENCE DEPENDS ON THERE BEING A SECTION ABOVE IT. A cautions-only return
        # renders this heading with no wins block, and the static wording then points a reader
        # at something that is not on the page.
        P.append("<p class=\"lane\">Published failures and limits"
                 + (". This section is the reason to believe the one above it.</p>" if wins
                    else " from operators in this industry.</p>"))
        for c in cautions:
            csrc = safe_url(c.get("source"))
            P.append(f"<p class=\"note\">{e(c.get('note'))}<br>"
                     f"<a href=\"{e(csrc)}\">{e(csrc)}</a></p>")

    # ------------------------------------------------------ close
    P.append("<hr class=\"rule\">")
    if scan.get("limits"):
        P.append(f"<p class=\"foot\">{e(scan['limits'])}</p>")
    if scan.get("next_step"):
        P.append(f"<p class=\"foot\">{e(scan['next_step'])}</p>")

    srcs = [u for u in (safe_url((s or {}).get("url")) for s in (scan.get("sources") or [])) if u]
    if srcs:
        P.append("<h2>Everything above, sourced</h2><ol class=\"src\">")
        for u in srcs:
            P.append(f"<li><a href=\"{e(u)}\">{e(u)}</a></li>")
        P.append("</ol>")

    P.append("</div></body></html>")
    return "\n".join(P)


# ---------------------------------------------------------------- self-test
def self_test() -> int:
    fails = 0

    def ok(label, cond, extra=""):
        """`extra` prints ONLY on a failure, and it carries what was actually found. A red line
        that names the expectation and not the reality sends the next reader back to the
        debugger to learn what the test already knew."""
        nonlocal fails
        print(f"  {'ok  ' if cond else 'FAIL'}  {label}{'' if cond else '  ' + str(extra)}")
        if not cond:
            fails += 1

    good_ob = {"operation": "Phone quoting", "tag": "would_help", "lowest_tier": "workflow",
               "signal": {"quote": "Call for a quote", "source": "https://x.com/quotes"},
               "labor_framing": "if the desk fields 20 to 40 calls a day",
               "human_check": "the estimator signs every quote"}
    unsourced = {"operation": "Invented", "tag": "would_help", "lowest_tier": "agent",
                 "signal": {"quote": "nothing", "source": ""}}
    scan = {"meta": {"company": "X Fluid", "place": "Midland", "date": "2026-08-14"},
            "headline": "Two pockets worth building and one to leave alone",
            "observations": [good_ob, unsourced,
                             dict(good_ob, operation="Counting", tag="rules_first",
                                  lowest_tier="rules"),
                             dict(good_ob, operation="Safety sign-off", tag="not_ai")],
            "where_not_to_use_ai": "The safety sign-off stays with a person.",
            "industry": {"label": "oilfield services",
                         "wins": [{"who": "A regional operator", "what_they_did": "extracted tickets",
                                   "published_result": "40 percent fewer keying minutes",
                                   "source": "https://pub.example/case"},
                                  {"who": "No source", "what_they_did": "x", "source": ""}],
                         "cautions": [{"note": "rolled back", "source": "https://pub.example/fail"}]},
            "limits": "This is a public footprint read.",
            "next_step": "The Field Study goes deeper.",
            "sources": [{"n": 1, "url": "https://x.com/quotes"}]}

    # THE TRACEABILITY GATE, which is the whole reason this file renders rather than the model
    ok("an unsourced observation is DROPPED, not warned about", len(usable_observations(scan)) == 3)
    ok("an unsourced industry win is dropped too", len(usable_wins(scan)) == 1)
    ok("an unknown tag is dropped",
       len(usable_observations({"observations": [dict(good_ob, tag="magic")]})) == 0)

    h = render(scan)
    ok("the dropped observation is nowhere in the html", "Invented" not in h)
    ok("the kept observations render", "Phone quoting" in h and "Counting" in h)
    ok("the industry section is labeled as somebody else's result",
       "OTHER operators" in h and "not predictions about this business" in h)
    ok("the published result is attributed, never promised",
       "They published:" in h and "you will" not in h.lower())
    ok("the reserved urgency red is not used", "#BF0A30" not in h)
    ok("it is noindex, because it is not ours to publish", 'content="noindex,nofollow"' in h)
    ok("it is self-contained: no external fetch",
       "http-equiv" not in h and "<script" not in h and "@import" not in h
       and "fonts.googleapis" not in h)
    ok("html in a quote is escaped, since the site's copy is untrusted input",
       "&lt;script&gt;" in render({"observations": [
           dict(good_ob, signal={"quote": "<script>x</script>", "source": "https://x/y"})]}))

    # DEGRADE. Fewer than three sourced observations cannot honestly stand.
    thin = dict(scan, observations=[good_ob])
    ht = render(thin)
    ok("a thin scan degrades honestly rather than padding", "honestly so" in ht)
    ok("...and still carries the industry lane, often the useful half",
       "What is working in this industry" in ht)

    # an empty industry section is legitimate and must not crash or render an empty heading
    he = render({"meta": {}, "observations": [good_ob, good_ob, good_ob]})
    ok("no industry section renders when there is none",
       "What is working in this industry" not in he)

    # A SOURCE IS AN HTTP URL. Escaping makes a url safe to sit in an attribute and does nothing
    # about what it does when the maintainer clicks it.
    ok("a javascript: source is not a source, so the observation is dropped",
       len(usable_observations({"observations": [
           dict(good_ob, signal={"quote": "q", "source": "javascript:alert(1)"})]})) == 0)
    hj = render({"meta": {}, "observations": [good_ob], "industry": {"wins": [], "cautions": []},
                 "sources": [{"n": 1, "url": "javascript:alert(1)"}]})
    ok("...and no javascript url survives anywhere in the page", "javascript:" not in hj)

    # THE LANES DO NOT MIX, and this is the half of it that is mechanically checkable
    crossed = {"observations": [dict(good_ob, signal={"quote": "q",
                                                     "source": "https://pub.example/case"})],
               "industry": {"wins": [{"who": "Someone", "what_they_did": "x",
                                      "source": "https://pub.example/case"}]}}
    ok("an industry url used as evidence about the requester is dropped",
       len(usable_observations(crossed)) == 0)
    ok("...and the win it really belongs to is untouched", len(usable_wins(crossed)) == 1)

    # An unknown rung is not printed AT the operator
    hr_ = render({"meta": {}, "observations": [dict(good_ob, lowest_tier="agentic"),
                                               dict(good_ob, lowest_tier=None)]})
    ok("an unknown or missing rung prints nothing rather than printing itself",
       "agentic" not in hr_ and "Lowest thing that would work: <" not in hr_
       and "Lowest thing that would work: </p>" not in hr_)

    # CAUTIONS WITHOUT WINS. The scout is told to hunt failures hardest, so this is normal.
    hc = render({"meta": {}, "observations": [good_ob, good_ob, good_ob],
                 "industry": {"label": "trucking", "wins": [],
                              "cautions": [{"note": "rolled back",
                                            "source": "https://pub.example/fail"}]}})
    ok("cautions alone never raise an empty what-is-working heading",
       "What is working in this industry" not in hc and "Where it did not work" in hc)
    ok("...and the caution copy stops pointing at a section that is not there",
       "the one above it" not in hc)

    # THE MASTHEAD, which is the first line an operator reads
    # A NULL IN THE JSON IS NOT A CRASH. The scan object is assembled by a model, so a stray
    # null in any list has to render a shorter report rather than a traceback.
    nulls = {"meta": {"company": None, "place": None, "date": None},
             "observations": [None, good_ob],
             "industry": {"wins": [None], "cautions": [None]},
             "sources": [None, {"url": None}]}
    ok("a stray null anywhere in the scan renders a shorter report, never a traceback",
       "Bottleneck scan for your operation" in render(nulls))

    ok("a partly filled meta leaves no orphan separator",
       "for  ·" not in h and " · </p>" not in render({"meta": {"company": "X Fluid"}}))
    ok("the date takes the ordinal, month first, computed here and not typed upstream",
       "August 14th, 2026" in h and "2026-08-14" not in h)
    ok("a date that is not ISO is passed through rather than mangled",
       show_date("August 14th, 2026") == "August 14th, 2026" and show_date("") == "")
    ok("the ordinal is computed for the awkward ones too",
       show_date("2026-08-11") == "August 11th, 2026"
       and show_date("2026-08-01") == "August 1st, 2026"
       and show_date("2026-08-22") == "August 22nd, 2026"
       and show_date("2026-08-03") == "August 3rd, 2026")

    # NO FIRST PERSON, on the renderer's OWN chrome. Measured with every content field set to a
    # letterless placeholder, so a requester quoting themselves ("we call back within the hour")
    # can never trip a rule that is about the words THIS FILE writes.
    blank_ob = {"operation": ".", "tag": "would_help", "lowest_tier": "workflow",
                "signal": {"quote": ".", "source": "https://p/1"},
                "labor_framing": ".", "human_check": "."}
    chrome_scan = {"meta": {"company": ".", "place": ".", "date": "2026-08-14"},
                   "headline": ".", "observations": [blank_ob, blank_ob, blank_ob],
                   "where_not_to_use_ai": ".",
                   "industry": {"label": ".",
                                "wins": [{"who": ".", "where": ".", "what_they_did": ".",
                                          "published_result": ".", "quote": ".", "relevance": ".",
                                          "source": "https://p/2"}],
                                "cautions": [{"note": ".", "source": "https://p/3"}]},
                   "limits": ".", "next_step": ".", "sources": [{"n": 1, "url": "https://p/1"}]}
    chrome = (re.sub(r"<[^>]+>", " ", render(chrome_scan))
              + re.sub(r"<[^>]+>", " ", render(dict(chrome_scan, status="degraded"))))
    person = sorted(set(re.findall(r"\b(?:we|we're|our|ours|us|I|I'm|my|mine)\b", chrome,
                                   flags=re.I)))
    ok(f"no first person in the page's own copy, per the house rule (found {person or 'none'})",
       not person)
    ok("...and no sentence in it opens with And or But",
       not re.search(r"(?:^|[.!?]\s|\s{2,})(?:And|But)\s", chrome))

    # ---------------------------------------------------------- the numeral gate
    # A COMPUTED framing renders, and it renders the figure code produced.
    computed = dict(good_ob, labor_framing={
        "actor": "the office keys",
        "volume": {"low": 60, "high": 120, "unit": "tickets", "per": "a week"},
        "minutes_each": {"low": 3, "high": 5},
        "of_what": "retyping", "assumption": "a ticket takes one pass"})
    hcomp = render({"meta": {}, "observations": [computed]})
    ok("a computed labor framing renders the figure code produced",
       "roughly 3 to 10 hours a week of retyping" in hcomp)
    ok("...and nothing in it is untraceable",
       not untraceable_numerals({"observations": [computed]}))

    # A TYPED figure never reaches the page at all.
    typed = dict(good_ob, labor_framing="That is roughly 40 hours a week of retyping.")
    ok("a labor framing with a typed figure is dropped rather than printed",
       "40 hours" not in render({"meta": {}, "observations": [typed]}))
    ok("...and the drop is explained rather than silent",
       "typed rather than measured" in labor_line(typed)[2])

    # THE GATE FIRES on the scanner's own copy about the requester...
    ok("a figure nobody computed, in the scanner's own copy, is caught",
       untraceable_numerals({"observations": [good_ob],
                             "headline": "Retyping eats 40 minutes a week"}) == ["40"],
       str(untraceable_numerals({"observations": [good_ob],
                                 "headline": "Retyping eats 40 minutes a week"})))
    ok("...and it is caught in an operation name and a human check too",
       untraceable_numerals({"observations": [dict(good_ob, operation="Keying 900 tickets",
                                                   human_check="A manager checks all 12")]})
       == ["12", "900"])

    # ...and NOT on quoted evidence or on the industry lane, which are somebody else's numbers
    quoted = dict(good_ob, signal={"quote": "The office keys 900 tickets a week.",
                                   "source": "https://p/1"},
                  operation="Keying 900 tickets")
    ok("a figure standing in the requester's own quoted words is traceable, so it passes",
       not untraceable_numerals({"observations": [quoted]}),
       str(untraceable_numerals({"observations": [quoted]})))
    ok("another operator's published result is never rewritten to satisfy this gate",
       not untraceable_numerals({"observations": [good_ob], "industry": {
           "wins": [{"who": "A carrier", "published_result": "40 percent fewer intake minutes",
                     "source": "https://pub/1"}]}}))
    ok("the computed masthead date does not trip the gate it was computed for",
       not untraceable_numerals({"meta": {"date": "2026-08-14"}, "observations": [good_ob]}),
       str(untraceable_numerals({"meta": {"date": "2026-08-14"}, "observations": [good_ob]})))

    # A GATE THAT CANNOT FAIL PROVES NOTHING, and the sample is the thing that actually ships.
    real = json.loads((Path(__file__).resolve().parents[1]
                       / "samples" / "sample-scan.json").read_text(encoding="utf-8"))
    ok("the shipped sample passes the gate", not untraceable_numerals(real),
       str(untraceable_numerals(real)))
    ok("...and it goes red when a typed figure is planted in it",
       untraceable_numerals(dict(real, limits="Roughly 40 hours a week are invisible")) == ["40"],
       str(untraceable_numerals(dict(real, limits="Roughly 40 hours a week are invisible"))))
    ok("...and every labor framing in it still renders, so it did not pass by emptiness",
       all(labor_line(o)[0] for o in usable_observations(real)),
       str([labor_line(o)[2] for o in usable_observations(real)]))

    print(f"\nbuild_scan_page self-test: {'all passed' if not fails else f'{fails} FAILED'}")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--scan")
    ap.add_argument("--out")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if not a.scan or not a.out:
        print("build_scan_page: pass --scan FILE --out FILE, or --self-test", file=sys.stderr)
        return 2
    try:
        scan = json.loads(Path(a.scan).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"build_scan_page: can't read scan: {exc}", file=sys.stderr)
        return 2
    if not isinstance(scan, dict):
        print(f"build_scan_page: {a.scan} is not a scan object", file=sys.stderr)
        return 2

    kept = usable_observations(scan)
    # Phase 6 says to READ WHAT THIS PRINTS, so it names the actual reason. Reporting every drop
    # as "no source" sent the next reader looking for a missing url when the fault was a tag.
    raw = scan.get("observations") or []
    crossed = industry_sources(scan)
    why = {"no fetched source": 0, "a source that crossed the lanes": 0, "an unknown tag": 0}
    for o in raw:
        src = safe_url(((o or {}).get("signal") or {}).get("source"))
        if not src:
            why["no fetched source"] += 1
        elif src in crossed:
            why["a source that crossed the lanes"] += 1
        elif (o or {}).get("tag") not in TAGS:
            why["an unknown tag"] += 1
    unrung = sum(1 for o in kept if o.get("lowest_tier") not in RUNGS)
    dropped_labor = [(o.get("operation") or "?", labor_line(o)[2]) for o in kept if labor_line(o)[2]]

    # THE NUMERAL GATE IS A HARD FAIL, the way the docket's is. A number nobody computed reaching
    # the operator it is about is the failure this whole file exists to make impossible, and a
    # warning printed into a log is not a mechanism. The page is not written.
    stray = untraceable_numerals(scan)
    if stray:
        print(f"build_scan_page: {a.scan} publishes {len(stray)} numeral(s) that trace to no "
              f"computation and to no quoted source. Nothing was written.", file=sys.stderr)
        for n in stray:
            print(f"  {n}", file=sys.stderr)
        print("A figure in this scanner's own copy is computed from observed quantities or it "
              "is not published. Move it into a computed labor framing, or quote the page it "
              "came from so it carries its source.", file=sys.stderr)
        return 1

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(scan), encoding="utf-8")
    notes = [f"{n} dropped for {reason}" for reason, n in why.items() if n]
    if unrung:
        notes.append(f"{unrung} kept with no honest rung, so the ladder line is missing")
    for op, reason in dropped_labor:
        notes.append(f"the labor framing on {op!r} was dropped, {reason}")
    print(f"build_scan_page: wrote {out} ({len(kept)} observation(s))"
          + (". " + ". ".join(notes) if notes else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
