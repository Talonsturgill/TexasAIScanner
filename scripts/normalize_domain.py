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

  normalize_domain.py <url-or-domain>
  normalize_domain.py --self-test

Exit 0 ok, 1 a check failed, 2 could not run.
"""
from __future__ import annotations

import sys
from urllib.parse import urlparse


def normalize_domain(raw: str) -> str:
    if not raw:
        return ""
    s = raw.strip().lower()
    if not s:
        return ""
    if "://" not in s:
        s = "http://" + s
    netloc = urlparse(s).netloc
    # credentials first, then the port: user:pass@host:8080 must not leave a colon behind
    netloc = netloc.split("@")[-1].split(":")[0]
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc.strip(".")


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

    print(f"\nnormalize_domain self-test: {'all passed' if not fails else f'{fails} FAILED'}")
    return 1 if fails else 0


def main() -> int:
    if len(sys.argv) == 2 and sys.argv[1] == "--self-test":
        return self_test()
    if len(sys.argv) != 2:
        print("usage: normalize_domain.py <url-or-domain> | --self-test", file=sys.stderr)
        return 2
    print(normalize_domain(sys.argv[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
