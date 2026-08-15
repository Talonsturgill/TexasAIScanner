# The scan.json contract

The object the scan routine assembles and `scripts/build_scan_page.py` renders. Keeping the DATA
and the RENDER separate is what makes every claim traceable: the builder drops any observation
without a fetched source, so a shorter true scan beats a padded invented one.

## What the report is FOR

An opportunity map. Two things carry the value and both are headline sections, not appendices:

1. **Where AI would actually help this operation**, named in operator terms, on the lowest rung
   that clears the bar, with the honest "you don't need it here" calls included, because those
   are what make the rest believable.
2. **What is already working in their industry**, as published by other operators. This is often
   the most useful part of the whole report. An owner who has never seen what a shop like theirs
   actually did with this gets more from three real published examples than from any amount of
   advice.

It is deliberately shallow. The depth is `The Field Study`, and that is what the report points
at when it points anywhere.

```
{
  "meta": {
    "company": "",        // display name as seen on their site
    "domain": "",         // normalised
    "place": "",          // the Texas city, metro or region, if stated on their site
    "date": ""            // America/Chicago YYYY-MM-DD
  },

  "headline": "",         // ONE honest line, THEIR outcome and not our product.
                          //   no colon in the sentence, no dash, no promise.

  "observations": [       // 3 to 6. each MUST cite a page fetched THIS RUN or be dropped.
    {
      "operation": "",    // the specific pocket, in operator words (phones, intake, quoting,
                          //   ticketing, counting, permits, dispatch)
      "signal": {
        "quote": "",      // what was actually seen, ideally in their own words
        "source": ""      // the fetched URL it came from
      },
      "tag": "would_help|rules_first|not_ai",
      "lowest_tier": "rules|retrieval|single_llm|workflow|agent",

      // LABOR FRAMING TAKES ONE OF TWO FORMS, and they are told apart by TYPE.
      // See "Labor framing is computed" below. Never a dollar hero number, never a promise.
      //
      //   A STRING, carrying NO quantity at all, in numerals or in letters:
      "labor_framing": "The tally already exists as a written record, so the count is a
                        data-entry problem rather than a perception problem.",
      //
      //   ...or an OBJECT of what was OBSERVED, which scripts/labor_math.py turns into the
      //   sentence. The arithmetic and the wording both happen there.
      "labor_framing": {
        "actor": "the office keys",         // operator words, no quantity
        "volume": { "low": 60, "high": 120, "unit": "tickets", "per": "a week" },
        "minutes_each": { "low": 3, "high": 5 },
        "of_what": "retyping",              // optional
        "assumption": "a ticket takes one pass"   // REQUIRED. printed beside the range.
      },

      "human_check": ""   // who catches a wrong answer before it lands. required on would_help.
    }
  ],

  "where_not_to_use_ai": "",   // at least one honest line. this is the brand working.

  // THE SECOND LANE, from the industry-scout. A HEADLINE SECTION of the report.
  // Never blended into observations: these are OTHER operators' published results,
  // rendered separately, never a claim about the requester and never a promise.
  "industry": {
    "label": "",               // the industry in plain operator words
    "wins": [
      {
        "pattern": "",         // which operation pattern this speaks to
        "who": "",             // as published. a named company, or "a regional carrier"
        "where": "",           // country or region if stated
        "what_they_did": "",
        "rung": "rules|retrieval|single_llm|workflow|agent",
        "published_result": "",// EXACT as published, with units and timeframe. null if none.
        "quote": "",
        "source": "",          // a URL the industry-scout fetched THIS RUN
        "relevance": ""        // which observed pocket it speaks to, WITH the scale caveat
      }
    ],
    "cautions": [ { "note": "", "quote": "", "source": "" } ]  // published failures and limits
  },

  "limits": "",                // what a public footprint read can and can't see
  "next_step": "",             // the Field Study, in one plain line. no pressure.
  "sources": [ { "n": 1, "url": "" } ],  // every page cited above
  "status": "ok|degraded"
}
```

## The two lanes never mix

`observations` are claims about THE REQUESTER, and every source must be a page the
footprint-analyst fetched from the requester's own domain. `industry.wins` are claims about
OTHER, ALREADY-PUBLISHED operators, and every source must be a page the industry-scout fetched.

An industry source appearing under an observation is a hard reject, and so is the reverse. The
renderer keeps them in separate sections with different visual treatment for exactly this
reason.

A published result from another operator is never restated as what this requester will get.
"They published forty percent fewer intake minutes" is allowed. "You will cut intake forty
percent" is the never-promise violation and the scan-critic kills it.

## Labor framing is computed, and this is the mechanism

CLAUDE.md: "Every numeral this scanner publishes is produced by code from data and can be
recomputed. A model that writes 'about 40 hours a week' is guessing at a formatting problem it
does not know it has."

That was a paragraph with nothing under it. `labor_framing` was a free string, so the arithmetic
lived inside a quoted sentence a model wrote. The sample shipped "60 to 120 tickets a week at 3
to 5 minutes each, that is roughly 3 to 10 hours a week", which is a multiplication and a
division carried out by a language model and typed into JSON. A model told the volume is 120 and
the minutes are 5 and writing "12 hours" would have reached the operator it was about.

**Supply what was OBSERVED. Never supply the answer.** `scripts/labor_math.py` multiplies,
divides, rounds by a written rule, and writes the sentence, so the figure and the words carrying
it come out of the same call and can't drift apart.

- **The assumption is required on the computed form.** A range with no stated assumption is a
  hero number wearing a range's clothes, and `labor_math` refuses it.
- **A plain-string framing carries no quantity**, in numerals or written out. "Roughly forty
  hours" is the same guess wearing letters. Both are refused.
- A framing that can't be computed is **dropped from the report**, and `build_scan_page.py`
  prints which observation lost it and why. It is never printed with a number in it.
- **`build_scan_page.py` will not write a page at all** if a numeral in the scanner's own copy
  about the requester traces to no computation and to no quoted source. That gate covers the
  headline, the operation names, the human checks, the where-not-to-use-AI line, the limits and
  the next step. It deliberately does NOT cover a verbatim quote or the industry lane, because
  those are somebody else's numbers with a source rendered beside them, and rewriting a
  published figure to satisfy a gate would be the actual dishonesty.

## Tagging rules (the honesty spine)

- **would_help.** AI genuinely earns its place on this pocket. `lowest_tier` is usually
  `workflow`, sometimes `single_llm` or `retrieval`. Name the human check.
- **rules_first.** A scale, a scan, a barcode, a rule, or software they already own does this or
  could. `lowest_tier` is `rules` or `retrieval`. Say plainly that they likely don't need AI here
  yet.
- **not_ai.** AI shouldn't touch this pocket, because a person clears it in minutes, or it is
  safety or compliance critical with no human check, or the data doesn't exist. Say why.

**A scan that tags everything would_help is a failure and the scan-critic rejects it.** A real
business almost always has at least one `rules_first` or `not_ai` pocket, and naming it is what
earns the trust that makes the `would_help` calls land.

## Degrade honestly

If the public footprint is too thin to produce three grounded observations, the routine sets
`status: degraded` and renders a short honest report: what could be seen, what couldn't, and the
human path. Never a padded or invented scan. A degraded report is a finished, shippable result
and it still carries the industry lane, which is often the part the requester values most anyway.
