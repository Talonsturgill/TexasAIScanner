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
import sys
from pathlib import Path

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


def usable_observations(scan: dict) -> list[dict]:
    """THE TRACEABILITY GATE. An observation with no fetched source is not an observation."""
    out = []
    for o in scan.get("observations") or []:
        src = ((o.get("signal") or {}).get("source") or "").strip()
        if not src:
            continue
        if o.get("tag") not in TAGS:
            continue
        out.append(o)
    return out


def usable_wins(scan: dict) -> list[dict]:
    """An industry win with no source is somebody's memory, which is the same failure as an
    invented observation and is dropped the same way."""
    return [w for w in ((scan.get("industry") or {}).get("wins") or [])
            if (w.get("source") or "").strip()]


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
    cautions = [c for c in (ind.get("cautions") or []) if (c.get("source") or "").strip()]
    degraded = scan.get("status") == "degraded" or len(obs) < 3

    P = []
    P.append("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">")
    P.append("<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">")
    P.append("<meta name=\"robots\" content=\"noindex,nofollow\">")
    P.append(f"<title>{e(meta.get('company') or 'Scan')} · Texas AI Docket</title>")
    P.append(f"<style>{CSS}</style></head><body><div class=\"wrap\">")

    P.append(f"<p class=\"meta\">Bottleneck scan for {e(meta.get('company'))}"
             + (f", {e(meta.get('place'))}" if meta.get("place") else "")
             + f" · {e(meta.get('date'))}</p>")

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
        P.append("<h2>What we saw</h2>")
        P.append("<p class=\"lane\">Every line below comes from a page on the site, linked at "
                 "the end. Nothing here is inferred from anyone else's business.</p>")
    for o in obs:
        label, colour, gloss = TAGS[o["tag"]]
        sig = o.get("signal") or {}
        P.append(f"<div class=\"ob\" style=\"--c:{colour}\">")
        P.append(f"<span class=\"tag\">{e(label)}</span>")
        P.append(f"<h3>{e(o.get('operation'))}</h3>")
        if sig.get("quote"):
            P.append(f"<p class=\"q\">{e(sig['quote'])}<br>"
                     f"<a href=\"{e(sig.get('source'))}\">{e(sig.get('source'))}</a></p>")
        rung = RUNGS.get(o.get("lowest_tier"), o.get("lowest_tier"))
        P.append(f"<p class=\"rung\">Lowest thing that would work: {e(rung)}</p>")
        P.append(f"<p class=\"note\">{e(gloss)}</p>")
        if o.get("labor_framing"):
            P.append(f"<p class=\"note\">{e(o['labor_framing'])}</p>")
        # The human check belongs to a build. On a rules_first or not_ai pocket there is no
        # model to check, and printing "not applicable" there reads as a form with a blank in it.
        if o.get("human_check") and o["tag"] == "would_help":
            P.append(f"<p class=\"note\">Who catches a wrong answer: {e(o['human_check'])}</p>")
        P.append("</div>")

    if scan.get("where_not_to_use_ai"):
        P.append("<h2>Where we would not put AI</h2>")
        P.append(f"<p>{e(scan['where_not_to_use_ai'])}</p>")

    # ------------------------------------------------------ lane 2, published elsewhere
    if wins or cautions:
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
        P.append(f"<p class=\"note\"><a href=\"{e(w.get('source'))}\">{e(w.get('source'))}</a></p>")
        P.append("</div>")

    if cautions:
        P.append("<h2>And where it did not work</h2>")
        P.append("<p class=\"lane\">Published failures and limits. This section is the reason to "
                 "believe the one above it.</p>")
        for c in cautions:
            P.append(f"<p class=\"note\">{e(c.get('note'))}<br>"
                     f"<a href=\"{e(c.get('source'))}\">{e(c.get('source'))}</a></p>")

    # ------------------------------------------------------ close
    P.append("<hr class=\"rule\">")
    if scan.get("limits"):
        P.append(f"<p class=\"foot\">{e(scan['limits'])}</p>")
    if scan.get("next_step"):
        P.append(f"<p class=\"foot\">{e(scan['next_step'])}</p>")

    srcs = scan.get("sources") or []
    if srcs:
        P.append("<h2>Everything above, sourced</h2><ol class=\"src\">")
        for s in srcs:
            u = e(s.get("url"))
            P.append(f"<li><a href=\"{u}\">{u}</a></li>")
        P.append("</ol>")

    P.append("</div></body></html>")
    return "\n".join(P)


# ---------------------------------------------------------------- self-test
def self_test() -> int:
    fails = 0

    def ok(label, cond):
        nonlocal fails
        print(f"  {'ok  ' if cond else 'FAIL'}  {label}")
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
        print(f"build_scan_page: cannot read scan: {exc}", file=sys.stderr)
        return 2
    kept = usable_observations(scan)
    dropped = len(scan.get("observations") or []) - len(kept)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(scan), encoding="utf-8")
    print(f"build_scan_page: wrote {out} ({len(kept)} observation(s)"
          + (f", {dropped} dropped for having no source" if dropped else "") + ")")
    return 0


if __name__ == "__main__":
    sys.exit(main())
