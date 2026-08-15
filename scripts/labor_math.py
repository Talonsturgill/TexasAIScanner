#!/usr/bin/env python3
"""labor_math.py — the labor range is COMPUTED here, so no model ever types one.

THE LAW THIS ENFORCES, from CLAUDE.md:

    Every numeral this scanner publishes is produced by code from data and can be recomputed.
    A model that writes "about 40 hours a week" is guessing at a formatting problem it does not
    know it has. Ranges are computed from a stated assumption, and the assumption is printed
    beside the range.

That was a paragraph with no mechanism under it. `labor_framing` was a free string, the
feasibility-mapper wrote the sentence AND the arithmetic inside it, and the renderer printed
whatever arrived. The sample shipped "60 to 120 tickets a week at 3 to 5 minutes each, that is
roughly 3 to 10 hours a week", which is four multiplications and two divisions done by a
language model and typed into a quoted string. Nothing checked it. A model told the volume is
120 and the minutes are 5 and writing "12 hours" would have reached the operator it was about.

HOW THE SHAPE CHANGED, AND WHY IT IS TWO FORMS RATHER THAN ONE

A labor framing is either QUALITATIVE or COMPUTED, and the two are told apart by type.

  QUALITATIVE is a plain string and it MUST CARRY NO NUMERAL. "The tally already exists as a
  written record, so the count is a data-entry problem rather than a perception problem" is a
  real and useful framing that needs no arithmetic. Most `rules_first` and `not_ai` pockets want
  this form. A numeral appearing in this form is the exact defect the law names, so it is
  refused rather than printed.

  COMPUTED is an object carrying the OBSERVED quantities and the assumption. This file does the
  arithmetic and writes the sentence. The model's job is to decide what to measure and to state
  the assumption honestly, which is the job it is good at. It is never the calculator.

WHY THE SENTENCE IS BUILT HERE TOO, AND NOT UPSTREAM

Because a number computed in one place and a sentence written in another is the drift the docket
learned the hard way. If the model wrote the prose around a number this file returned, it could
still round it, restate it, or put a stray "about" in front of a figure that is exact. The value
and the words that carry it come out of the same call, so they can't disagree.

ROUNDING IS A COMPUTATION WITH A STATED RULE, not a choice made at writing time. See
`round_hours`. The rule is written down because a reader is entitled to know how 3.33 became
3.3, and because a rule nobody wrote down gets applied differently by the next caller.

  labor_math.py --self-test

Exit 0 ok, 1 a check failed, 2 could not run.
"""
from __future__ import annotations

import re
import sys
from decimal import Decimal, ROUND_HALF_UP

# What a numeral looks like to the gate. Kept identical in shape to the docket's numeral_lint so
# the two agree about where a number starts and stops: a token ENDS ON A DIGIT, so the comma in
# "In 2026, the office" belongs to the sentence and not to the figure.
NUMERAL = re.compile(r"\d(?:[\d,]*\d)?(?:\.\d+)?")

# Numerals are one way to write a quantity. Written-out quantities are another, and a framing
# that says "roughly forty hours a week" is the same guess wearing letters. The qualitative form
# refuses both. `a third` and `half` survive, deliberately: they are proportions of an observed
# thing rather than derived totals, and the sample's honest "if a third of callouts land outside
# office hours" is exactly the framing this form exists to allow.
_SPELLED = re.compile(
    r"\b(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|twenty|thirty|forty|"
    r"fifty|sixty|seventy|eighty|ninety|hundred|thousand)\b", re.I)


class LaborError(ValueError):
    """A framing that can't be computed or can't be trusted. The caller drops the framing."""


def round_hours(x: float) -> str:
    """THE STATED RULE, so a reader knows how the figure was made.

    Ten hours or more rounds to a whole hour, because a half hour inside a working week is
    precision the input never had. Under ten hours keeps one decimal, and a trailing zero is
    dropped so a computed 3.0 prints as 3 rather than implying a measurement to the tenth.
    A HALF ALWAYS GOES UP.

    That last sentence is the reason this uses Decimal rather than `round`. Python's `round` is
    banker's rounding, so `round(12.5)` is 12 and `round(13.5)` is 14, which is a defensible rule
    and is NOT the rule stated above. A stated rule that the code quietly does not follow is
    worse than no stated rule, because a reader who recomputes gets a different answer and has
    no way to know which of them is the mistake. Binary float makes it worse again: 2.675 is not
    really 2.675, so `round(2.675, 2)` is 2.67. Decimal off the string form has neither problem.
    """
    d = Decimal(repr(float(x)))
    if d >= 10:
        return str(d.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    r = d.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
    return str(r.quantize(Decimal("1")) if r == r.to_integral_value() else r)


def _num(v, field: str) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise LaborError(f"{field} is not a number, so no range can be computed from it")
    if v < 0:
        raise LaborError(f"{field} is negative, which is not a quantity of work")
    return float(v)


def _pair(d, field: str) -> tuple[float, float]:
    if not isinstance(d, dict):
        raise LaborError(f"{field} must carry a low and a high")
    lo = _num(d.get("low"), f"{field}.low")
    hi = _num(d.get("high", d.get("low")), f"{field}.high")
    if hi < lo:
        raise LaborError(f"{field} has a high below its low, so the range reads backwards")
    return lo, hi


def _show(lo: float, hi: float) -> str:
    """A range reads "X to Y", per the house rule, and a single value reads as itself."""
    f = (lambda v: str(int(v)) if v == int(v) else str(v))
    return f(lo) if lo == hi else f"{f(lo)} to {f(hi)}"


def compute(framing: dict) -> dict:
    """Turn the observed quantities into the hours range AND the sentence that carries it.

    Returns the rendered sentence plus `numerals`, which is every numeral string the sentence
    actually contains. The page gate authorises from that set, so a figure on the page and a
    figure this computed can't drift apart: they are the same string.
    """
    if not isinstance(framing, dict):
        raise LaborError("a computed framing must be an object")

    vol = framing.get("volume")
    if not isinstance(vol, dict):
        raise LaborError("volume must carry low, high, unit and per")
    v_lo, v_hi = _pair(vol, "volume")
    m_lo, m_hi = _pair(framing.get("minutes_each"), "minutes_each")

    unit = str(vol.get("unit") or "").strip()
    per = str(vol.get("per") or "").strip()
    actor = str(framing.get("actor") or "").strip()
    assumption = str(framing.get("assumption") or "").strip()
    of_what = str(framing.get("of_what") or "").strip()

    if not unit or not per:
        raise LaborError("volume needs a unit and a period, or the range means nothing")
    if not actor:
        raise LaborError("a framing needs an actor, or the hours belong to nobody")

    # THE ASSUMPTION IS REQUIRED, because a range without one is a hero number wearing a range's
    # clothes. CLAUDE.md: "Ranges are computed from a stated assumption, and the assumption is
    # printed beside the range." Printed beside it, which means it can't be optional.
    if not assumption:
        raise LaborError("a computed range with no stated assumption is a hero number")

    # The one piece of arithmetic in the whole scanner, and it lives here rather than in a string.
    lo_h = v_lo * m_lo / 60.0
    hi_h = v_hi * m_hi / 60.0

    hours = round_hours(lo_h) if round_hours(lo_h) == round_hours(hi_h) \
        else f"{round_hours(lo_h)} to {round_hours(hi_h)}"

    sentence = (f"If {actor} {_show(v_lo, v_hi)} {unit} {per} at {_show(m_lo, m_hi)} minutes "
                f"each, that is roughly {hours} hours {per}"
                + (f" of {of_what}" if of_what else "")
                + f", on the stated assumption that {assumption}.")

    # Every numeral the sentence prints, taken OUT OF THE SENTENCE rather than rebuilt from the
    # inputs. Rebuilding is how an authorised set and a rendered figure drift.
    return {
        "sentence": sentence,
        "hours_low": lo_h,
        "hours_high": hi_h,
        "numerals": sorted({m.group(0) for m in NUMERAL.finditer(sentence)}),
    }


def qualitative_ok(text: str) -> list[str]:
    """What disqualifies a plain-string framing. Empty list means it is fine as it stands."""
    found = [m.group(0) for m in NUMERAL.finditer(text or "")]
    found += [m.group(0) for m in _SPELLED.finditer(text or "")]
    return sorted(set(found))


def render(framing) -> tuple[str, list[str], str]:
    """The one entry point the renderer calls.

    Returns (text, authorised numerals, reason it was dropped). A dropped framing returns an
    empty text and a reason the run is told about, because a silent drop is how a defect in the
    assembling step survives to the next scan.
    """
    if framing is None or framing == "":
        return "", [], ""
    if isinstance(framing, dict):
        try:
            out = compute(framing)
        except LaborError as exc:
            return "", [], str(exc)
        return out["sentence"], out["numerals"], ""
    text = str(framing).strip()
    if not text:
        return "", [], ""
    bad = qualitative_ok(text)
    if bad:
        return "", [], (f"a written-out labor framing carries a quantity ({', '.join(bad)}) that "
                        f"no computation produced, so it was typed rather than measured")
    return text, [], ""


def self_test() -> int:
    fails = 0

    def ok(label, cond, extra=""):
        nonlocal fails
        print(f"  {'ok  ' if cond else 'FAIL'}  {label}{'' if cond else '  ' + extra}")
        if not cond:
            fails += 1

    # THE SAMPLE'S OWN SENTENCE, which used to be typed, now computed from what was observed.
    sample = {
        "actor": "the office keys",
        "volume": {"low": 60, "high": 120, "unit": "tickets", "per": "a week"},
        "minutes_each": {"low": 3, "high": 5},
        "of_what": "retyping",
        "assumption": "a ticket takes one pass",
    }
    out = compute(sample)
    ok("the arithmetic is done in code, and it is right",
       out["hours_low"] == 3.0 and out["hours_high"] == 10.0, str(out))
    ok("...and the sentence reads the way an operator would say it",
       out["sentence"] == ("If the office keys 60 to 120 tickets a week at 3 to 5 minutes each, "
                           "that is roughly 3 to 10 hours a week of retyping, on the stated "
                           "assumption that a ticket takes one pass."), out["sentence"])
    ok("...and every numeral in it is authorised from the sentence itself",
       out["numerals"] == ["10", "120", "3", "5", "60"], str(out["numerals"]))

    # THE DEFECT THE LAW NAMES. A model told the inputs and writing the answer gets it wrong,
    # and nothing downstream would have caught it. Now the inputs are all it gets to supply.
    ok("a model can no longer state the hours at all, so it cannot state them wrong",
       "hours" not in sample and compute(sample)["hours_high"] == 10.0)

    # ROUNDING IS A RULE, not a choice made while writing
    ok("under ten hours keeps one decimal", round_hours(3.33) == "3.3")
    ok("...and a computed whole number does not grow a false tenth", round_hours(3.0) == "3")
    ok("ten hours and over rounds to the whole hour",
       round_hours(10.4) == "10" and round_hours(12.4) == "12")
    # THE STATED RULE SAYS A HALF GOES UP, and `round` would have made that sentence a lie on
    # exactly the even-numbered halves. It is checked on both sides of the parity because that
    # is where banker's rounding and the stated rule disagree.
    ok("...and a half goes up, on an even hour as well as an odd one",
       round_hours(12.5) == "13" and round_hours(13.5) == "14",
       f"{round_hours(12.5)} {round_hours(13.5)}")
    ok("...and the same holds at the tenth, where binary float bites too",
       round_hours(3.25) == "3.3" and round_hours(2.35) == "2.4",
       f"{round_hours(3.25)} {round_hours(2.35)}")
    ok("a rounding that collapses the range prints one figure rather than X to X",
       "roughly 1 hours" in compute({**sample, "volume": {"low": 20, "high": 20,
                                                          "unit": "tickets", "per": "a week"},
                                     "minutes_each": {"low": 3, "high": 3}})["sentence"])
    ok("a single observed value reads as itself and not as a range", _show(4, 4) == "4")

    # THE ASSUMPTION IS PRINTED BESIDE THE RANGE, so it can't be dropped
    try:
        compute({k: v for k, v in sample.items() if k != "assumption"})
        ok("a range with no stated assumption is refused", False)
    except LaborError as exc:
        ok(f"a range with no stated assumption is refused ({exc})", True)

    # BAD INPUT DEGRADES, it does not crash and it does not print nonsense
    for bad, why in [
        ({**sample, "minutes_each": {"low": 5, "high": 3}}, "a backwards range"),
        ({**sample, "minutes_each": {"low": "three", "high": 5}}, "a spelled-out input"),
        ({**sample, "volume": {"low": 60, "high": 120, "unit": "", "per": "a week"}}, "no unit"),
        ({**sample, "actor": ""}, "no actor"),
        ({**sample, "minutes_each": None}, "no minutes at all"),
        ({**sample, "volume": {"low": -1, "high": 5, "unit": "t", "per": "a week"}}, "a negative"),
    ]:
        text, nums, reason = render(bad)
        ok(f"{why} drops the framing and names why ({reason[:44]}...)",
           text == "" and nums == [] and bool(reason))

    # THE QUALITATIVE FORM. Numeral-free framings are real and they stay.
    keep = "The tally already exists as a written record, so the count is a data-entry problem."
    ok("a numeral-free framing renders untouched", render(keep)[0] == keep)
    ok("...and a proportion of an observed thing is not a derived total",
       render("If a third of callouts land outside office hours, a structured intake would "
              "cover that share.")[0].startswith("If a third"))

    # ...and the typed number, in both spellings, is refused
    typed = render("That is roughly 40 hours a week of retyping.")
    ok(f"a typed figure in a plain framing is refused ({typed[2][:40]}...)",
       typed[0] == "" and "40" in typed[2])
    spelled = render("That is roughly forty hours a week of retyping.")
    ok("...and so is the same guess written out in letters",
       spelled[0] == "" and "forty" in spelled[2])

    ok("nothing at all is not an error, it is just no framing",
       render(None) == ("", [], "") and render("") == ("", [], ""))

    print(f"\nlabor_math self-test: {'all passed' if not fails else f'{fails} FAILED'}")
    return 1 if fails else 0


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] == "--self-test":
        return self_test()
    print("usage: labor_math.py --self-test", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
