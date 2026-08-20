#!/usr/bin/env python3
"""repo_guards.py — the laws that no single script's self-test can see.

Every script here already proves itself. `normalize_domain` proves its rule, `build_scan_page`
proves it drops what it cannot trace, and `scan_draft` proves its own file holds no send path.
Each of those is a statement about ONE FILE, and every law in `CLAUDE.md` is a statement about
the REPO. A second file importing `smtplib` passes all three self-tests, because none of them
is looking.

That gap is the exact defect class the sibling repos keep a written record of: a green self-test
says the checker works, not that the thing it checks is clean. So this file checks the things
that only exist between files.

  GUARD 1  there is no send path ANYWHERE, proved by parsing rather than grepping
  GUARD 2  nothing about a requester is in git
  GUARD 3  the ledger holds domains and dates and nothing else
  GUARD 4  everything built here is wired to something
  GUARD 5  the promise on the form and the run contract still agree
  GUARD 6  the published surfaces keep the house voice

WHY AN AST AND NOT A GREP. `scan_draft.py` proves its own innocence by reading its source with
the prose stripped out, which works, and which forced a carve-out: the banned words are NAMED in
that file, so scanning the whole thing finds its own checklist and reports the guard as the
violation. Grep cannot tell a checklist from a call. A parser can, because it never sees string
literals at all. It is also strictly stronger: `import smtplib as m` followed by `m.sendmail(...)`
defeats a grep for `sendmail` and cannot defeat this.

  repo_guards.py                 check this repo
  repo_guards.py --self-test     prove every guard above can go red

Exit 0 ok, 1 a guard failed, 2 could not run.
"""
from __future__ import annotations

import argparse
import ast
import html
import importlib.util
import json
import re
import subprocess  # noqa: S404  see EXEMPT below, and GUARD 1's own check on it
import sys
import tempfile
from pathlib import Path

# --------------------------------------------------------------------------- GUARD 1

# Import roots that are a send path, or that reach one. Each is banned by MODULE NAME, so an
# alias cannot hide it. `urllib.parse` is deliberately absent: normalize_domain parses urls and
# parsing is not fetching.
BANNED_IMPORTS = {
    "smtplib": "the standard library's mail sender",
    "requests": "an HTTP client, which is a send path wearing a fetch's coat",
    "urllib.request": "the standard library's HTTP opener",
    "http.client": "a raw HTTP connection",
    "httpx": "an HTTP client",
    "aiohttp": "an HTTP client",
    "socket": "a raw socket, which is every protocol at once",
    "ftplib": "a file transfer client",
    "poplib": "a mail reader",
    "imaplib": "a mail reader",
    "subprocess": "a shell, and a shell reaches curl and mail",
}

# Called names that deliver something, whatever the receiver is.
BANNED_CALLS = {"sendmail", "send_message", "urlopen", "popen", "system"}

# THE EXEMPTIONS, deliberately shaped so they cannot grow quietly. Each is keyed by
# (file, module) rather than by file, so the file is still held to every other ban, and GUARD 1
# additionally proves a property of each that makes the exemption safe rather than trusted.
#
# THE SECOND ONE WAS A DECISION, made 2026-08-20 on the owner's call, and it is the harder of
# the two to justify, so here is the justification. The law is that this routine drafts and a
# human sends: there is no credential here that can mail anybody. `scan_progress.py` holds a
# credential, and what that credential can do is append one line to one scan row. It cannot
# mail, it cannot read the table, and it cannot reach anything the operator has not configured.
#
# The reason `urllib.request` is banned at all is that an HTTP opener is general purpose, which
# the ban's own words call "a send path wearing a fetch's coat". That is a fair worry, and the
# compensating check below is the answer to it: the exempted file is proved to hold NO url of
# its own. Its endpoint comes from the environment and nowhere else, so the hosts it can reach
# are the hosts the operator chose, and an edit that types a mail API's address into it fails.
EXEMPT = {
    ("scripts/repo_guards.py", "subprocess"):
        "reads the git index to know what is tracked. Every call is checked to be git.",
    ("scripts/scan_progress.py", "urllib"):
        "appends one line to one scan row so the requester can watch. It holds no url of its "
        "own, which is checked, so it reaches only what the environment configures.",
}

# The one delivery call the one exempted file must make. Same shape and same reasoning as
# EXEMPT: named, not counted, and the file is still held to every other ban.
EXEMPT_CALLS = {("scripts/scan_progress.py", "urlopen")}


def _module_is_banned(mod: str) -> str | None:
    for banned, why in BANNED_IMPORTS.items():
        if mod == banned or mod.startswith(banned + "."):
            return why
    return None


def guard_no_send_path(root: Path) -> list[str]:
    """GUARD 1. This routine drafts and a human sends. There is no credential here that can mail
    anybody, which is a smaller blast radius than any policy, and it stays true only if something
    checks every file rather than one file."""
    bad = []
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        if rel.startswith((".git/", "out/")) or "__pycache__" in rel:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=rel)
        except (OSError, SyntaxError) as exc:
            bad.append(f"{rel}: will not parse, so it cannot be cleared ({exc})")
            continue

        for node in ast.walk(tree):
            mods: list[str] = []
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                # both halves: `import http.client` and `from http import client`
                mods = [node.module] + [f"{node.module}.{a.name}" for a in node.names]

            for mod in mods:
                why = _module_is_banned(mod)
                if not why:
                    continue
                root_mod = mod.split(".")[0]
                if (rel, root_mod) in EXEMPT:
                    continue
                bad.append(f"{rel}:{node.lineno} imports {mod}, {why}")

            if isinstance(node, ast.Call):
                name = (node.func.attr if isinstance(node.func, ast.Attribute)
                        else node.func.id if isinstance(node.func, ast.Name) else "")
                # The exempted appender necessarily calls the opener it is exempted for.
                # Keyed by (file, call), so every other file and every other call in this one
                # is still held to the ban.
                if name in BANNED_CALLS and (rel, name) not in EXEMPT_CALLS:
                    bad.append(f"{rel}:{node.lineno} calls {name}(), which delivers something")

        # THE NAME HEURISTIC IS MODULE LEVEL ONLY, and the mechanism checks above are not.
        #
        # An import or a delivery call is scanned anywhere in the tree, including inside a
        # function, because that is where the CAPABILITY lives. A name is different: it is a
        # hint, not a mechanism, and walking the whole tree with it flagged `send_paths()`, a
        # helper nested inside scan_draft's self-test whose entire job is FINDING send paths.
        # A gate that reports the checker as the violation is how a gate gets switched off,
        # and it is the same "a mention is not a call" lesson GUARD 4 already learned.
        #
        # An operational send path is a module-level function. Scaffolding nested inside a test
        # is not, and it cannot smuggle in capability anyway, since the import ban is tree-wide.
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == "send" or node.name.startswith("send_"):
                    bad.append(f"{rel}:{node.lineno} defines {node.name}(), and nothing here sends")

    # THE EXEMPTIONS ARE NAMED, NOT COUNTED. This asserted a count of one, which is a tripwire
    # against quiet growth and was the right instinct; a number is the wrong way to spell it,
    # because the next person raises the number. Naming them means a new exemption has to be
    # written into this list, in this file, where somebody reads it.
    ALLOWED = {("scripts/repo_guards.py", "subprocess"),
               ("scripts/scan_progress.py", "urllib")}
    for key in sorted(set(EXEMPT) - ALLOWED):
        bad.append(f"EXEMPT holds {key}, which is not one of the exemptions this guard knows "
                   f"about. Growing it quietly is how the one law in this repo stops being one.")

    # AND THE SECOND EXEMPTION IS ONLY SAFE WHILE IT HOLDS NO URL OF ITS OWN. Its endpoint comes
    # from the environment, so the hosts it can reach are the ones the operator configured. A
    # url typed into that file is a host nobody chose, and it fails here.
    prog = root / "scripts" / "scan_progress.py"
    if prog.is_file():
        ptree = ast.parse(prog.read_text(encoding="utf-8"), filename="scripts/scan_progress.py")
        for node in ast.walk(ptree):
            if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                    and re.search(r"https?://", node.value)):
                bad.append(f"scripts/scan_progress.py:{node.lineno} holds a url of its own. Its "
                           f"endpoint comes from the environment, which is what makes its "
                           f"exemption from the send-path ban safe.")
    guard = root / "scripts" / "repo_guards.py"
    if guard.is_file():
        tree = ast.parse(guard.read_text(encoding="utf-8"), filename="scripts/repo_guards.py")
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "subprocess"):
                first = node.args[0] if node.args else None
                argv0 = None
                if isinstance(first, (ast.List, ast.Tuple)) and first.elts:
                    head = first.elts[0]
                    if isinstance(head, ast.Constant):
                        argv0 = head.value
                if argv0 != "git":
                    bad.append(f"scripts/repo_guards.py:{node.lineno} hands a subprocess "
                               f"{argv0!r}. The exemption covers git and nothing else.")
    return bad


# --------------------------------------------------------------------------- GUARD 2

TEXT_EXT = {".py", ".md", ".json", ".txt", ".html", ".yaml", ".yml", ".tsv", ".csv"}
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# The maintainer's own mailbox is the one real address this repo is ever allowed to hold.
OWN_MAILBOXES = {"alaskaaihq.com"}


def _tracked(root: Path) -> list[str]:
    out = subprocess.run(["git", "-C", str(root), "ls-files"],
                         capture_output=True, text=True, check=True)
    return [ln for ln in out.stdout.splitlines() if ln.strip()]


def guard_nothing_about_a_requester_in_git(root: Path) -> list[str]:
    """GUARD 2. The privacy wall's sixth fence. This repo holds the method and the code, never a
    scan result and never a lead. A report exists as an email to the one address that asked for
    it and nowhere else, so a real address appearing in the history is the wall breached."""
    bad = []
    ignore = (root / ".gitignore")
    if not ignore.is_file() or "out/" not in ignore.read_text(encoding="utf-8").split():
        bad.append(".gitignore does not ignore out/, which is where every scan artifact lands")

    for rel in _tracked(root):
        if rel.startswith("out/"):
            bad.append(f"{rel} is tracked. Scan artifacts never enter git.")
        path = root / rel
        if path.suffix not in TEXT_EXT or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if path.suffix == ".py":
            # Test scaffolding names deliberately malformed addresses to prove they are refused.
            # Those are fixtures, not contacts, so the scan reads the operational half. GUARD 1
            # still reads the whole file, and GUARD 1 is the one that matters.
            text = text.split("def self_test")[0]
        for hit in EMAIL_RE.findall(text):
            domain = hit.rsplit("@", 1)[1].lower()
            if "example" in domain.split(".") or domain in OWN_MAILBOXES:
                continue
            bad.append(f"{rel} holds the address {hit}. Only an example address or the "
                       f"maintainer's own mailbox may be committed here.")
    return bad


# --------------------------------------------------------------------------- GUARD 3

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def guard_ledger_is_domains_and_dates(root: Path) -> list[str]:
    """GUARD 3. `ledger/scanned.json` is the only file here that persists anything about a
    request, and the promise is that it holds domains and dates and nothing else. A company name
    or a reply address landing in it would be published to a public repo on the next commit."""
    bad = []
    path = root / "ledger" / "scanned.json"
    if not path.is_file():
        return ["ledger/scanned.json is missing, and the thirty day no-repeat depends on it"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"ledger/scanned.json will not parse: {exc}"]

    if set(data) != {"scanned"}:
        bad.append(f"ledger/scanned.json holds top-level keys {sorted(data)}, expected "
                   f"['scanned'] only")
    spec = importlib.util.spec_from_file_location(
        "normalize_domain", root / "scripts" / "normalize_domain.py")
    nd = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(nd)

    for i, entry in enumerate(data.get("scanned") or []):
        if not isinstance(entry, dict) or set(entry) != {"domain", "date"}:
            bad.append(f"ledger/scanned.json entry {i} carries "
                       f"{sorted(entry) if isinstance(entry, dict) else type(entry).__name__}, "
                       f"and this file is allowed exactly domain and date")
            continue
        if nd.normalize_domain(entry["domain"]) != entry["domain"]:
            bad.append(f"ledger/scanned.json entry {i} stores {entry['domain']!r}, which is not "
                       f"its own normalised form, so the no-repeat will miss it")
        if not ISO_DATE.match(str(entry["date"])):
            bad.append(f"ledger/scanned.json entry {i} has date {entry['date']!r}, "
                       f"which is not ISO")
    return bad


# --------------------------------------------------------------------------- GUARD 4

PATH_RE = re.compile(r"\b((?:scripts|knowledge|config|ledger|web|samples|prompts)/[\w./-]+"
                     r"\.(?:py|md|json|yaml|yml|html|txt))")


def guard_everything_is_wired(root: Path) -> list[str]:
    """GUARD 4. The owner's named failure mode, in one check: things get built and then never
    connected. An unreferenced script does not throw and an agent nobody spawns does not
    complain, so the only symptom is a run that quietly does less than the repo claims."""
    bad = []
    prompt = (root / "prompts" / "scan_routine.md")
    if not prompt.is_file():
        return ["prompts/scan_routine.md is missing, and it is the run contract"]
    prompt_text = prompt.read_text(encoding="utf-8")
    claude = (root / "CLAUDE.md").read_text(encoding="utf-8") if (root / "CLAUDE.md").is_file() \
        else ""
    workflows = "\n".join(p.read_text(encoding="utf-8")
                          for p in sorted((root / ".github" / "workflows").glob("*.yml"))) \
        if (root / ".github" / "workflows").is_dir() else ""
    # forwards: everything on disk is spoken for.
    #
    # Matched on the FULL FILENAME, and against the OPERATIONAL half of every other script. The
    # first draft matched the stem anywhere in any script and could not catch an orphan at all,
    # because this file's own self-test writes the orphan's name into a string and that counted
    # as wiring. It is GUARD 1's lesson again on a different surface: a mention is not a call,
    # and test scaffolding is not wiring.
    for path in sorted((root / "scripts").glob("*.py")):
        name = path.name
        others = "\n".join(p.read_text(encoding="utf-8").split("def self_test")[0]
                           for p in sorted((root / "scripts").glob("*.py")) if p != path)
        if not any(name in text for text in (prompt_text, claude, workflows, others)):
            bad.append(f"scripts/{name} is wired to nothing. No routine phase runs it, no "
                       f"workflow runs it, and no other script reaches for it.")

    for path in sorted((root / ".claude" / "agents").glob("*.md")):
        head = path.read_text(encoding="utf-8")
        m = re.search(r"^name:\s*(\S+)\s*$", head, re.M)
        if not m:
            bad.append(f".claude/agents/{path.name} has no name field in its frontmatter")
            continue
        if m.group(1) != path.stem:
            bad.append(f".claude/agents/{path.name} declares name {m.group(1)!r}, which does not "
                       f"match its filename, so a spawn by filename finds nothing")
        if m.group(1) not in prompt_text:
            bad.append(f"the agent {m.group(1)!r} exists and the run contract never spawns it")

    # backwards: everything the prose names is on disk
    for text, where in ((prompt_text, "prompts/scan_routine.md"), (claude, "CLAUDE.md")):
        for rel in sorted(set(PATH_RE.findall(text))):
            if rel.startswith("out/"):
                continue          # per-run scratch, correctly absent from a clean checkout
            if not (root / rel).exists():
                bad.append(f"{where} names {rel}, which is not on disk")
    return bad


# --------------------------------------------------------------------------- GUARD 5

# Each pair is one promise, pinned in the two places that have to agree about it. The form is
# what the requester actually agreed to, so when this goes red the form is right and the run
# contract is what needs fixing.
CONTRACT = [
    ("one report goes to one address",
     "One report to one address",
     "the address they typed"),
    ("there is no second message, ever",
     "No list, no follow-up sequence, no second email",
     "There is no follow-up sequence"),
    ("nothing is sent, a human presses send",
     "A person reads every report before it goes out",
     "Do not send it"),
    ("every line traces to the requester's own pages",
     "traces to a page on your own site",
     "cites every claim"),
]


def guard_promise_and_routine_agree(root: Path) -> list[str]:
    """GUARD 5. The form page says what this product promises and the run contract says what it
    does. Those are two documents that can drift, and only one of them is what a stranger read
    before typing their address in."""
    form = (root / "web" / "scan.html")
    routine = (root / "prompts" / "scan_routine.md")
    if not form.is_file() or not routine.is_file():
        return ["web/scan.html and prompts/scan_routine.md must both exist to be compared"]
    f, r = form.read_text(encoding="utf-8"), routine.read_text(encoding="utf-8")
    bad = []
    for promise, in_form, in_routine in CONTRACT:
        if in_form not in f:
            bad.append(f"the form no longer promises that {promise}. If that promise is being "
                       f"dropped, the run contract has to drop it in the same commit.")
        if in_routine not in r:
            bad.append(f"the form promises that {promise} and the run contract no longer says "
                       f"so. The form is what the requester agreed to.")
    return bad


# --------------------------------------------------------------------------- GUARD 6

TAGS_RE = re.compile(r"<(script|style)\b.*?</\1>|<!--.*?-->|<[^>]+>", re.S | re.I)
QUOTE_RE = re.compile(r'<p class="q">.*?</p>', re.S)
EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF☀-➿⬀-⯿️]")
OPENER_RE = re.compile(r"(?:^|[.!?]\s+)(And|But)\s")


def _visible(html_text: str) -> str:
    """The words a reader sees. Quoted source text goes first and never comes back: rewriting a
    quotation to fit a house rule would be falsifying it, which is far worse than a stray dash.

    ENTITIES ARE RESOLVED LAST, and that is not cosmetic. The renderer escapes with
    `html.escape(quote=True)`, so every apostrophe in the report ships as `&#x27;` and the first
    version of this guard read the trailing semicolon of the entity as a semicolon in the prose.
    It failed a clean report over punctuation no reader will ever see. A gate that reads markup
    instead of the rendered word is reporting on a document nobody is looking at.
    """
    return html.unescape(TAGS_RE.sub(" ", QUOTE_RE.sub(" ", html_text)))


def _voice(text: str, where: str, first_person: bool) -> list[str]:
    bad = []
    for ch, name in (("—", "an em dash"), ("–", "an en dash"),
                     ("‘", "a curly quote"), ("’", "a curly quote"),
                     ("“", "a curly quote"), ("”", "a curly quote"),
                     (";", "a semicolon")):
        if ch in text:
            bad.append(f"{where} contains {name}")
    if EMOJI_RE.search(text):
        bad.append(f"{where} contains an emoji")
    if re.search(r"\bcannot\b", text, re.I):
        bad.append(f"{where} writes \"cannot\", and the house writes \"can't\"")
    m = OPENER_RE.search(text)
    if m:
        bad.append(f"{where} opens a sentence with {m.group(1)!r}")
    if first_person:
        m = re.search(r"\b(we|us|our|ours)\b", text, re.I)
        if m:
            bad.append(f"{where} uses the first person ({m.group(1)!r}). A page about somebody "
                       f"else's operation that keeps saying we is talking about itself.")
    return bad


def guard_house_voice(root: Path) -> list[str]:
    """GUARD 6. Checked on the RENDERED surfaces rather than the source, because the report a
    reader sees is assembled from f-strings and ledger fields and exists as a whole sentence
    nowhere in the code.

    FIRST PERSON IS SPLIT BY SURFACE, on purpose. The form is public marketing copy on the
    docket's own site and takes the docket's rule, no first person. The report is a letter to one
    operator who asked for it, and correspondence in the third person reads like a machine wrote
    it, which is the opposite of the point. Same reasoning as the colon carve-out in CLAUDE.md.
    """
    bad = []
    form = root / "web" / "scan.html"
    if form.is_file():
        bad += _voice(_visible(form.read_text(encoding="utf-8")), "the form page",
                      first_person=True)

    sample = root / "samples" / "sample-scan.json"
    builder = root / "scripts" / "build_scan_page.py"
    if sample.is_file() and builder.is_file():
        spec = importlib.util.spec_from_file_location("build_scan_page", builder)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        page = mod.render(json.loads(sample.read_text(encoding="utf-8")))
        bad += _voice(_visible(page), "the rendered report", first_person=False)
    return bad


# --------------------------------------------------------------------------- runner

GUARDS = [
    ("no send path anywhere", guard_no_send_path),
    ("nothing about a requester in git", guard_nothing_about_a_requester_in_git),
    ("the ledger is domains and dates", guard_ledger_is_domains_and_dates),
    ("everything is wired", guard_everything_is_wired),
    ("the promise and the routine agree", guard_promise_and_routine_agree),
    ("the published surfaces keep the house voice", guard_house_voice),
]


def run(root: Path) -> int:
    total = 0
    for label, fn in GUARDS:
        fails = fn(root)
        total += len(fails)
        print(f"  {'ok  ' if not fails else 'FAIL'}  {label}")
        for f in fails:
            print(f"          {f}")
    print(f"\nrepo_guards: {'all guards hold' if not total else f'{total} violation(s)'}")
    return 1 if total else 0


# ---------------------------------------------------------------- self-test
def _fixture(tmp: Path) -> Path:
    """A minimum repo that passes every guard, so each check below breaks exactly one thing."""
    root = tmp / "repo"
    for d in ("scripts", "knowledge", "config", "ledger", "web", "samples", "prompts",
              ".claude/agents"):
        (root / d).mkdir(parents=True, exist_ok=True)
    here = Path(__file__).resolve().parent
    for name in ("normalize_domain.py", "build_scan_page.py", "repo_guards.py"):
        (root / "scripts" / name).write_text((here / name).read_text(encoding="utf-8"),
                                             encoding="utf-8")
    (root / ".gitignore").write_text("out/\n", encoding="utf-8")
    (root / "ledger" / "scanned.json").write_text('{"scanned": []}', encoding="utf-8")
    (root / "CLAUDE.md").write_text("law\n", encoding="utf-8")
    (root / "samples" / "sample-scan.json").write_text(
        json.dumps({"meta": {"company": "X"}, "observations": [], "sources": []}),
        encoding="utf-8")
    (root / ".claude" / "agents" / "scan-critic.md").write_text(
        "---\nname: scan-critic\ndescription: d\ntools: Read\n---\n", encoding="utf-8")
    (root / "web" / "scan.html").write_text(
        "<p>One report to one address. No list, no follow-up sequence, no second email. "
        "Every line traces to a page on your own site. "
        "A person reads every report before it goes out.</p>", encoding="utf-8")
    (root / "prompts" / "scan_routine.md").write_text(
        "Draft to the address they typed. There is no follow-up sequence. Do not send it. "
        "It cites every claim. Spawn scan-critic. Run scripts/normalize_domain.py, "
        "scripts/build_scan_page.py and scripts/repo_guards.py.\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    return root


def self_test() -> int:
    fails = 0

    def ok(label, cond):
        nonlocal fails
        print(f"  {'ok  ' if cond else 'FAIL'}  {label}")
        if not cond:
            fails += 1

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        root = _fixture(tmp)

        clean = {label: fn(root) for label, fn in GUARDS}
        ok(f"a clean repo passes every guard ({[k for k, v in clean.items() if v]})",
           not any(clean.values()))

        # GUARD 1, the one law. Each of these defeats a grep and must not defeat a parser.
        sneaky = root / "scripts" / "helper.py"
        for src, why in [
            ("import smtplib\n", "a plain import"),
            ("import smtplib as m\n", "an aliased import"),
            ("from http import client\n", "a from-import of a banned submodule"),
            ("import urllib.request\n", "a dotted import"),
            ("def send_report(x):\n    return x\n", "a function named send_*"),
            ("x = None\nx.sendmail('a')\n", "a delivery call on an unknown receiver"),
        ]:
            sneaky.write_text(src, encoding="utf-8")
            ok(f"GUARD 1 catches {why}", bool(guard_no_send_path(root)))
        sneaky.write_text("from urllib.parse import urlparse\nurlparse('x')\n", encoding="utf-8")
        ok("GUARD 1 allows urllib.parse, because parsing a url is not fetching one",
           not guard_no_send_path(root))

        # THE NAME HEURISTIC IS MODULE LEVEL, THE MECHANISM CHECKS ARE NOT. Both halves of
        # that are asserted, because narrowing a rule without pinning what it still catches is
        # how a gate quietly stops being one.
        sneaky.write_text("def self_test():\n"
                          "    def send_paths(t):\n"
                          "        return [b for b in ['smtplib'] if b in t]\n"
                          "    return send_paths('x')\n", encoding="utf-8")
        ok("GUARD 1 leaves a detector nested in a self-test alone, checker is not violation",
           not guard_no_send_path(root))
        sneaky.write_text("def send_report(x):\n    return x\n", encoding="utf-8")
        ok("...and STILL catches a module-level send_*, which is where a real one would live",
           bool(guard_no_send_path(root)))
        sneaky.write_text("def self_test():\n    import smtplib\n    return smtplib\n",
                          encoding="utf-8")
        ok("...and an import is caught wherever it hides, including inside a test",
           bool(guard_no_send_path(root)))
        sneaky.unlink()

        # GUARD 2
        (root / "config" / "note.md").write_text("reply to owner@realbusiness.com\n",
                                                 encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
        ok("GUARD 2 catches a real address in a committed file",
           bool(guard_nothing_about_a_requester_in_git(root)))
        (root / "config" / "note.md").write_text("reply to owner@example.com\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
        ok("GUARD 2 allows an example address",
           not guard_nothing_about_a_requester_in_git(root))
        (root / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
        ok("GUARD 2 catches out/ falling out of .gitignore",
           bool(guard_nothing_about_a_requester_in_git(root)))
        (root / ".gitignore").write_text("out/\n", encoding="utf-8")

        # GUARD 3
        led = root / "ledger" / "scanned.json"
        led.write_text(json.dumps({"scanned": [
            {"domain": "x.com", "date": "2026-08-14", "company": "X Fluid"}]}), encoding="utf-8")
        ok("GUARD 3 catches a business fact in the ledger",
           bool(guard_ledger_is_domains_and_dates(root)))
        led.write_text(json.dumps({"scanned": [{"domain": "WWW.X.com", "date": "2026-08-14"}]}),
                       encoding="utf-8")
        ok("GUARD 3 catches an unnormalised domain, which the no-repeat would miss",
           bool(guard_ledger_is_domains_and_dates(root)))
        led.write_text(json.dumps({"scanned": [{"domain": "x.com", "date": "August 14th"}]}),
                       encoding="utf-8")
        ok("GUARD 3 catches a non-ISO date", bool(guard_ledger_is_domains_and_dates(root)))
        led.write_text('{"scanned": [{"domain": "x.com", "date": "2026-08-14"}]}',
                       encoding="utf-8")
        ok("GUARD 3 passes a well-formed ledger entry",
           not guard_ledger_is_domains_and_dates(root))

        # GUARD 4, the owner's named failure mode
        (root / "scripts" / "orphan.py").write_text("x = 1\n", encoding="utf-8")
        ok("GUARD 4 catches a script wired to nothing", bool(guard_everything_is_wired(root)))
        (root / "scripts" / "orphan.py").unlink()
        (root / ".claude" / "agents" / "ghost.md").write_text(
            "---\nname: ghost\ndescription: d\n---\n", encoding="utf-8")
        ok("GUARD 4 catches an agent no phase ever spawns", bool(guard_everything_is_wired(root)))
        (root / ".claude" / "agents" / "ghost.md").unlink()
        (root / ".claude" / "agents" / "scan-critic.md").write_text(
            "---\nname: critic\ndescription: d\n---\n", encoding="utf-8")
        ok("GUARD 4 catches a name that does not match its filename",
           bool(guard_everything_is_wired(root)))
        (root / ".claude" / "agents" / "scan-critic.md").write_text(
            "---\nname: scan-critic\ndescription: d\n---\n", encoding="utf-8")
        p = root / "prompts" / "scan_routine.md"
        p.write_text(p.read_text(encoding="utf-8") + "\nAlso read knowledge/GHOST.md.\n",
                     encoding="utf-8")
        ok("GUARD 4 catches the run contract naming a file that is not there",
           bool(guard_everything_is_wired(root)))
        p.write_text(p.read_text(encoding="utf-8").replace(
            "\nAlso read knowledge/GHOST.md.\n", ""), encoding="utf-8")
        ok("GUARD 4 is clean again once the drift is undone",
           not guard_everything_is_wired(root))

        # GUARD 5
        f = root / "web" / "scan.html"
        f.write_text(f.read_text(encoding="utf-8").replace("One report to one address", "Reports"),
                     encoding="utf-8")
        ok("GUARD 5 catches a promise dropped from the form",
           bool(guard_promise_and_routine_agree(root)))
        f.write_text(f.read_text(encoding="utf-8").replace("Reports", "One report to one address"),
                     encoding="utf-8")
        p.write_text(p.read_text(encoding="utf-8").replace("Do not send it.", "Send it."),
                     encoding="utf-8")
        ok("GUARD 5 catches the run contract dropping its half of a promise",
           bool(guard_promise_and_routine_agree(root)))
        p.write_text(p.read_text(encoding="utf-8").replace("Send it.", "Do not send it."),
                     encoding="utf-8")

        # GUARD 6
        base = f.read_text(encoding="utf-8")
        for bad_copy, why in [
            ("<p>a — dash</p>", "an em dash"),
            ("<p>it cannot see your billing</p>", "\"cannot\""),
            ("<p>ready \U0001F918</p>", "an emoji"),
            ("<p>one thing; another</p>", "a semicolon"),
            ("<p>Send it. And it comes back.</p>", "a sentence opening with And"),
            ("<p>We read what is public.</p>", "the first person"),
            ("<p>a ’curly’ quote</p>", "a curly quote"),
        ]:
            f.write_text(base + bad_copy, encoding="utf-8")
            ok(f"GUARD 6 catches {why} on the form", bool(guard_house_voice(root)))
        # quoted source text is never rewritten to fit a house rule
        f.write_text(base + '<p class="q">We cannot do it — honestly</p>', encoding="utf-8")
        ok("GUARD 6 leaves a quotation alone, since editing one falsifies it",
           not guard_house_voice(root))
        # the entity, which failed a clean report once
        f.write_text(base + "<p>it can&#x27;t see a billing system</p>", encoding="utf-8")
        ok("GUARD 6 reads the rendered word, so an escaped apostrophe is not a semicolon",
           not guard_house_voice(root))
        f.write_text(base + "<p>an escaped &mdash; is still an em dash</p>", encoding="utf-8")
        ok("GUARD 6 still catches a dash written as an entity", bool(guard_house_voice(root)))
        f.write_text(base, encoding="utf-8")

    print(f"\nrepo_guards self-test: {'all passed' if not fails else f'{fails} FAILED'}")
    return 1 if fails else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=".", help="repo root to check (default: cwd)")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    root = Path(a.root).resolve()
    if not (root / "CLAUDE.md").is_file():
        print(f"repo_guards: {root} does not look like this repo", file=sys.stderr)
        return 2
    return run(root)


if __name__ == "__main__":
    sys.exit(main())
