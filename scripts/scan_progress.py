#!/usr/bin/env python3
"""scan_progress.py — how a run tells the requester what it is doing, while it does it.

The scan page hands somebody a link and that page watches this feed. Nothing else writes it,
so a phase that does not call this is a phase the requester watches in silence.

WHAT A LINE IS FOR. The owner's call is to SHOW THE DEPTH OF THE SEARCH: not four milestones,
but the actual reach of the run. A page fetched is a line. A published result found is a line.
A candidate ruled out is a line, and the ruling out is often the most convincing thing in the
whole report, because it is the part a sales pitch never contains.

WHAT A LINE MAY SAY, and this is a rule and not a preference:

  IT IS ABOUT THEIR OWN SCAN. Never another requester, never a count of other scans, never
  anything about the machine's own health. The feed is served to a stranger's browser by a
  token and it carries exactly what that stranger's run is doing.

  IT NEVER QUOTES THEIR FREE TEXT BACK. That box arrived from a stranger through a public form.
  It is context for a person, it is never passed to an agent as instruction, and it is never
  echoed into a page. Same rule as the report.

  IT CLAIMS NOTHING IT HAS NOT DONE. "Reading the careers page" before the fetch has returned
  is a small lie that costs the whole feed its credibility, and this is the one surface where
  a reader is watching for exactly that.

FAILING HERE NEVER FAILS THE RUN. A feed is a courtesy and the report is the product. Every
call returns a bool and swallows its own errors, because a scan that dies because it could not
narrate itself has traded the thing for the description of the thing.

    from scan_progress import line, running, done
    running(scan_id)
    line(scan_id, "footprint", "Read the services page.")
    done(scan_id, headline="...", html=..., scan=..., degraded=False)

    python3 scripts/scan_progress.py --self-test
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

# Set by the routine's environment. Absent, every call is a no-op that says so once.
ENDPOINT = os.environ.get("SCAN_PROGRESS_URL", "")
SECRET = os.environ.get("SCAN_PROGRESS_SECRET", "")

NOTE_MAX = 300

# CLOUDFLARE REFUSES A CLIENT THAT WILL NOT NAME ITSELF, and urllib names itself
# "Python-urllib/3.x". The worker sits behind Cloudflare, which answered every feed call with a
# 403 and error 1010, a browser-signature block, so a live run narrated itself to nobody while
# the helper reported the outage to stderr and carried on exactly as designed. The report was
# never at risk and the feed was never delivered, which is the failure mode the swallowing makes
# quiet. One honest header fixes it.
USER_AGENT = "texas-ai-scanner-routine/1.0"

_warned = False


def _post(payload: dict, timeout: float = 6.0) -> bool:
    """One call. Returns whether it landed, and never raises."""
    global _warned
    if not ENDPOINT or not SECRET:
        if not _warned:
            print("scan_progress: SCAN_PROGRESS_URL or SCAN_PROGRESS_SECRET unset, "
                  "the requester sees no feed", file=sys.stderr)
            _warned = True
        return False
    req = urllib.request.Request(
        ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={"content-type": "application/json",
                 "authorization": f"Bearer {SECRET}",
                 "user-agent": USER_AGENT},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = json.loads(r.read().decode("utf-8") or "{}")
        return bool(body.get("ok"))
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as e:
        print(f"scan_progress: {type(e).__name__}, the run carries on", file=sys.stderr)
        return False


def line(scan_id: str, phase: str, note: str) -> bool:
    """One line of the feed. Trimmed here as well as in SQL, so the caller sees the limit."""
    note = " ".join(str(note or "").split())[:NOTE_MAX]
    if not note:
        return False
    return _post({"scan_id": scan_id, "kind": "line", "phase": phase, "note": note})


def running(scan_id: str) -> bool:
    """Picked up. Says the difference between queued and started, which a watcher can see."""
    return _post({"scan_id": scan_id, "kind": "running"})


def done(scan_id: str, headline: str = "", html: str | None = None,
         scan: dict | None = None, degraded: bool = False) -> bool:
    """Finished, with the result on its own row so the link keeps working."""
    return _post({"scan_id": scan_id, "kind": "done", "headline": headline,
                  "html": html, "scan": scan, "degraded": degraded})


def self_test() -> int:
    failures = 0

    def check(label, cond, extra=""):
        nonlocal failures
        print(f"  {'ok  ' if cond else 'FAIL'}  {label}{'' if cond else '  ' + extra}")
        if not cond:
            failures += 1

    global ENDPOINT, SECRET, _warned
    sent: list = []

    def fake(payload, timeout=6.0):
        sent.append(payload)
        return True

    real, ENDPOINT, SECRET = _post, "set-for-the-test", "s"
    globals()["_post"] = fake
    try:
        line("id-1", "footprint", "  Read   the services page.  ")
        check("a line is sent with its phase", sent and sent[-1]["phase"] == "footprint")
        check("...and its whitespace is collapsed",
              sent[-1]["note"] == "Read the services page.", repr(sent[-1]["note"]))

        sent.clear()
        check("an empty note is not sent at all", line("id-1", "x", "   ") is False and not sent)

        long = "x" * 900
        line("id-1", "industry", long)
        check("a runaway line is trimmed", len(sent[-1]["note"]) == NOTE_MAX,
              str(len(sent[-1]["note"])))

        sent.clear()
        running("id-1")
        check("running is its own kind", sent[-1]["kind"] == "running")
        done("id-1", headline="Two places worth a look.", degraded=True)
        check("done carries the verdict", sent[-1]["kind"] == "done"
              and sent[-1]["degraded"] is True)
    finally:
        globals()["_post"] = real

    # THE REQUEST ITSELF, which the fake above never sees. A helper that swallows its own errors
    # cannot tell you it has been refused at the door for six months, so the one call that
    # actually reaches the network is checked here rather than trusted.
    class _Resp:
        status = 200

        def read(self):
            return b'{"ok": true}'

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    caught: list = []

    def fake_urlopen(req, timeout=6.0):
        caught.append(req)
        return _Resp()

    real_urlopen = urllib.request.urlopen
    urllib.request.urlopen = fake_urlopen
    # THE TEST ENDPOINT CARRIES NO http SCHEME ON PURPOSE. `repo_guards` GUARD 3 fails this file
    # on any url literal in it, and it is right to: this file is exempt from the send-path ban
    # only because its endpoint comes from the environment, so a host typed in here is a host
    # nobody configured. Splitting the string to slip past that check would be evading the guard
    # rather than satisfying it. `Request` only needs a scheme, and urlopen is stubbed anyway.
    ENDPOINT, SECRET = "x-scan-test://feed/progress", "s3cret"
    try:
        landed = line("id-1", "footprint", "Read the services page.")
    finally:
        urllib.request.urlopen = real_urlopen
    check("a configured call reaches the network and reports that it landed", landed)
    sent_req = caught[-1] if caught else None
    ua = sent_req.get_header("User-agent") if sent_req else ""
    # THE DEFECT THIS REPLAYS. urllib names itself "Python-urllib/3.x", Cloudflare answers a
    # client with that signature 403 error 1010, and the feed went dark with nothing going red.
    check("the call NAMES ITSELF, because Cloudflare blocks a client that does not",
          bool(ua) and "urllib" not in ua.lower(), repr(ua))
    check("...and it still carries the bearer token and its json",
          bool(sent_req) and sent_req.get_header("Authorization") == "Bearer s3cret"
          and sent_req.get_header("Content-type") == "application/json")

    # UNCONFIGURED IS A NO-OP, NOT A CRASH. The routine must survive a missing secret, because
    # the alternative is a scan that dies for want of narration.
    ENDPOINT, SECRET, _warned = "", "", False
    check("with no endpoint it declines quietly", line("id", "p", "n") is False)
    check("...and running and done decline too",
          running("id") is False and done("id") is False)

    print("\nscan_progress self-test " + ("clean" if not failures else f"{failures} FAILED"))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(self_test() if "--self-test" in sys.argv else 0)
