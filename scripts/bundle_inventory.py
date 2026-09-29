#!/usr/bin/env python3
"""Extract a bundle corpus's endpoint inventory ONCE and cache it.

Why: re-running find_endpoints over a 12.9 MB corpus took minutes and a
"how many endpoints are there?" question was asked four times in one session -
one of those runs blew a 5-minute budget and died, which is how a denominator
ends up quoted from a partial sample.

Deliberately small. It caches an extraction; it is not an analysis framework.

    python scripts/bundle_inventory.py <target>          # build/refresh + summary
    python scripts/bundle_inventory.py <target> --api    # list the API paths
"""
import glob
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core.secrets import find_endpoints                       # noqa: E402

_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.join(_BASE, "workspace", "bundles")
# The cache does NOT live in the bundle dir: that tree is .js/.map ONLY and
# scripts/prune_bundles.py flags anything else as an intruder that "may carry
# session material". It flagged this file within minutes of me writing it.
# The guard is right - move the cache, do not widen the allowlist to suit me.
CACHE = os.path.join(_BASE, "workspace", "coverage")


def _fingerprint(paths):
    """Cache key: name+size+mtime of every file. A changed corpus rebuilds itself."""
    return [[os.path.basename(p), os.path.getsize(p), int(os.path.getmtime(p))]
            for p in paths]


def build(target, force=False):
    d = os.path.join(ROOT, target)
    if not os.path.isdir(d):
        raise SystemExit("no bundle dir: %s" % d)
    cache = os.path.join(CACHE, target, "_bundle_inventory.json")
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    paths = sorted(p for p in glob.glob(os.path.join(d, "*")) if os.path.isfile(p))
    fp = _fingerprint(paths)
    if not force and os.path.exists(cache):
        try:
            doc = json.load(io.open(cache, encoding="utf-8"))
            if doc.get("fingerprint") == fp:
                return doc
        except Exception:
            pass

    eps, nbytes, unreadable = set(), 0, []
    for p in paths:
        try:
            b = io.open(p, encoding="utf-8", errors="replace").read()
        except Exception as e:                                  # noqa: BLE001
            unreadable.append([os.path.basename(p), type(e).__name__])
            continue
        nbytes += len(b)
        eps |= set(find_endpoints(b))

    # A bare "/api/" is not an endpoint, and query strings are not distinct paths.
    # Both inflated a denominator that had already been quoted (self-audit C2).
    raw = sorted(eps)
    api_raw = [x for x in raw if "/api/" in x]
    api = sorted({x.split("?")[0].rstrip("/") for x in api_raw
                  if x.rstrip("/") != "/api"})

    doc = {
        "target": target,
        "files": len(paths),
        "unreadable": unreadable,          # never silent: a skipped file is a hole
        "bytes": nbytes,
        "endpoints_all": raw,
        "api_raw_strings": len(api_raw),
        "api_paths": api,
        "fingerprint": fp,
    }
    io.open(cache, "w", encoding="utf-8").write(json.dumps(doc, indent=1))
    return doc


def main(argv):
    if not argv:
        raise SystemExit(__doc__)
    target = argv[0]
    doc = build(target, force="--force" in argv)
    if "--api" in argv:
        for p in doc["api_paths"]:
            print(p)
        return 0
    print("target      : %s" % doc["target"])
    print("files       : %d  (%.1f MB)" % (doc["files"], doc["bytes"] / 1048576))
    if doc["unreadable"]:
        print("UNREADABLE  : %d  <- these are HOLES, not zeros" % len(doc["unreadable"]))
    print("endpoints   : %d total" % len(doc["endpoints_all"]))
    print("api raw     : %d strings" % doc["api_raw_strings"])
    print("API PATHS   : %d distinct  <- the denominator" % len(doc["api_paths"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
