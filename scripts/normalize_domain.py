#!/usr/bin/env python3
"""normalize_domain.py — the ONE domain normalisation rule, shared everywhere.

Lowercase, drop the scheme, drop a leading `www.`, drop credentials, drop the port, drop any
path and trailing slash, keep the host.

    https://www.Permian-Fluid.com/about  ->  permian-fluid.com

WHY IT IS ONE RULE IN ONE FILE. Two places that normalise a domain slightly differently will
disagree on the day it matters, and here the day it matters is the thirty day no-repeat: a
requester who types `www.x.com` on Monday and `X.com/` on Tuesday is the same business, and a
second normaliser would happily run and bill a second scan. The form, the routine and the
ledger all import this one function.

IT FAILS LOUD, NOT EMPTY. An input this rule can't turn into a hostname exits 2 and prints
nothing on stdout. The routine keys EVERYTHING downstream on this string, so an empty or
nonsense key that exits 0 is the worst outcome available: the no-repeat check keys on "", the
agents get handed a blank domain, and the run bills a scan of nowhere. `hello world` is not a
domain and neither is `javascript:alert(1)`, and both used to come back with exit 0.

  normalize_domain.py <url-or-domain>
  normalize_domain.py --self-test

Exit 0 ok, 1 a check failed, 2 could not run.
"""
from __future__ import annotations

import re
import sys
from urllib.parse import urlparse

# A LEADING scheme, which is the only kind that means anything here. Testing for `://` anywhere
# in the string sends `example.com/x?u=https://evil.com` down the has-a-scheme path, and urlparse
# then reads the whole thing as a path and hands back an EMPTY host.
_LEADING_SCHEME = re.compile(r"^[a-z][a-z0-9+.\-]*://")

# What a hostname is allowed to look like once the rule has finished with it: two or more
# non-empty labels, no whitespace, no leftover url punctuation.
_HOST_CHARS = re.compile(r"^[^\s/?#@:\\]+$")


def valid_domain(host: str) -> bool:
    """Is this string usable as the key everything downstream keys on."""
    if not host or len(host) > 253:
        return False
    if not _HOST_CHARS.match(host):
        return False
    labels = host.split(".")
    if len(labels) < 2:
        return False
    return all(0 < len(lab) <= 63 for lab in labels)


def normalize_domain(raw: str) -> str:
    """The rule. Returns "" for anything it can't turn into a usable hostname."""
    if not raw:
        return ""
    s = raw.strip().lower()
    if not s:
        return ""
    s = s.lstrip("/")            # a protocol-relative paste, //example.com/x
    if not _LEADING_SCHEME.match(s):
        s = "http://" + s
    netloc = urlparse(s).netloc
    # credentials first, then the port: user:pass@host:8080 must not leave a colon behind
    netloc = netloc.split("@")[-1].split(":")[0]
    if netloc.startswith("www."):
        netloc = netloc[4:]
    netloc = netloc.strip(".")
    return netloc if valid_domain(netloc) else ""


def self_test() -> int:
    cases = [
        # (input, expected)
        ("https://www.Permian-Fluid.com/about", "permian-fluid.com"),
        ("PERMIAN-FLUID.COM", "permian-fluid.com"),
        ("http://permian-fluid.com/", "permian-fluid.com"),
        ("permian-fluid.com/quotes?utm=x", "permian-fluid.com"),
        ("www.permian-fluid.com", "permian-fluid.com"),
        ("  https://permian-fluid.com  ", "permian-fluid.com"),
        # a port must not survive, or the ledger sees two businesses
        ("https://permian-fluid.com:8443/x", "permian-fluid.com"),
        # credentials must not survive either
        ("https://user:pw@permian-fluid.com/x", "permian-fluid.com"),
        # a subdomain is NOT stripped: shop.x.com is a different surface from x.com,
        # and only a leading www. is noise
        ("https://shop.permian-fluid.com", "shop.permian-fluid.com"),
        # wwwsomething is not www.
        ("https://wwwx.com", "wwwx.com"),
        ("", ""),
        ("   ", ""),
        # a url with a scheme LATER in it still normalises, because only a leading scheme is a
        # scheme. this one used to come back empty, with exit 0, and the run keyed on nothing.
        ("example.com/x?u=https://evil.com", "example.com"),
        ("//example.com/x", "example.com"),
        # things that are not domains come back empty, and the CLI turns that into exit 2
        ("hello world", ""),
        ("javascript:alert(1)", ""),
        ("asdf", ""),
        ("http://", ""),
        ("https://ex ample.com", ""),
    ]
    fails = 0
    for raw, want in cases:
        got = normalize_domain(raw)
        ok = got == want
        print(f"  {'ok  ' if ok else 'FAIL'}  {raw!r} -> {got!r}" + ("" if ok else f" (want {want!r})"))
        if not ok:
            fails += 1

    # the property the ledger actually depends on: the same business, typed any way,
    # normalises to one key
    forms = ["x-ranch.com", "www.x-ranch.com", "HTTPS://WWW.X-RANCH.COM/",
             "http://x-ranch.com:80/index.html"]
    same = len({normalize_domain(f) for f in forms}) == 1
    print(f"  {'ok  ' if same else 'FAIL'}  every spelling of one business gives one key")
    if not same:
        fails += 1

    # the property the ROUTINE depends on: a key it can't use never arrives wearing exit 0
    quiet = not valid_domain("") and not valid_domain("hello world") and valid_domain("x.com")
    print(f"  {'ok  ' if quiet else 'FAIL'}  an unusable key is refused rather than returned")
    if not quiet:
        fails += 1

    print(f"\nnormalize_domain self-test: {'all passed' if not fails else f'{fails} FAILED'}")
    return 1 if fails else 0


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] == "--self-test":
        return self_test()
    if len(sys.argv) != 2:
        print("usage: normalize_domain.py <url-or-domain> | --self-test", file=sys.stderr)
        return 2
    host = normalize_domain(sys.argv[1])
    if not host:
        print(f"normalize_domain: {sys.argv[1]!r} is not a domain this rule can use. Nothing "
              f"downstream can key on it, so the run stops here rather than scanning nowhere.",
              file=sys.stderr)
        return 2
    print(host)
    return 0


if __name__ == "__main__":
    sys.exit(main())
