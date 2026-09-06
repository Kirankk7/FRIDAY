"""Prune the JS-bundle keep-pile — the retention half of HUNT_PROTOCOL §7.

WHY THIS EXISTS
  At hunt close everything in the scratchpad is deleted, because HARs carry session cookies, CSRF
  tokens and (in one case) a cleartext password. That rule is right and stays.

  It also has a cost that only became visible on 2026-09-06: the secret corpus went 16 -> 150
  patterns and could NOT be run against hunt #37, because ClearTax's bundles were already gone.
  Every instrument we build is built after the hunt that motivated it, so a policy that erases the
  evidence erases the retro-run too.

  So the pile is split. `workspace/bundles/<target>/` keeps `.js` and `.map` bodies for 30 days —
  bytes the target serves to any anonymous visitor, carrying nothing about us. Everything else still
  dies at close.

WHAT THIS ENFORCES
  An unenforced retention window is not a policy, it is an intention. This makes the 30 days real:
  it refuses to keep a file whose extension is not on the allowlist (a stray HAR in the keep-pile is
  the whole rule defeated), and it deletes nothing without `--delete` typed explicitly.

Offline, stdlib-only. Dry-run by default.
"""
import argparse
import os
import shutil
import sys
import time

KEEP_DAYS = 30
ALLOWED_EXT = {".js", ".mjs", ".cjs", ".map"}
ROOT = os.path.join("workspace", "bundles")


def scan(root, keep_days):
    """(expired, live, intruders) — intruders are files that must never have been kept."""
    cutoff = time.time() - keep_days * 86400
    expired, live, intruders = [], [], []
    if not os.path.isdir(root):
        return expired, live, intruders
    for target in sorted(os.listdir(root)):
        d = os.path.join(root, target)
        if not os.path.isdir(d):
            continue
        newest, size, n = 0.0, 0, 0
        for dirpath, _dirs, files in os.walk(d):
            for f in files:
                p = os.path.join(dirpath, f)
                ext = os.path.splitext(f)[1].lower()
                if ext not in ALLOWED_EXT:
                    intruders.append(p)
                    continue
                try:
                    st = os.stat(p)
                except OSError:
                    continue
                newest = max(newest, st.st_mtime)
                size += st.st_size
                n += 1
        row = {"target": target, "path": d, "files": n, "bytes": size, "newest": newest,
               "age_days": (time.time() - newest) / 86400 if newest else 0.0}
        (expired if newest and newest < cutoff else live).append(row)
    return expired, live, intruders


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=ROOT)
    ap.add_argument("--days", type=int, default=KEEP_DAYS)
    ap.add_argument("--delete", action="store_true",
                    help="actually remove expired target dirs (default: dry run)")
    a = ap.parse_args(argv)

    expired, live, intruders = scan(a.root, a.days)

    if not os.path.isdir(a.root):
        print("no keep-pile at %s — nothing retained yet" % a.root)
        return 0

    for r in live:
        print("KEEP    %-22s %4d file(s) %8.1f KB  age %5.1fd"
              % (r["target"], r["files"], r["bytes"] / 1024, r["age_days"]))
    for r in expired:
        print("EXPIRED %-22s %4d file(s) %8.1f KB  age %5.1fd"
              % (r["target"], r["files"], r["bytes"] / 1024, r["age_days"]))

    if intruders:
        # A HAR or a response body in the keep-pile defeats the entire split. Loud, always.
        print("\n!! %d FILE(S) THAT MUST NOT BE HERE — only %s may be retained:"
              % (len(intruders), "/".join(sorted(ALLOWED_EXT))))
        for p in intruders[:20]:
            print("     %s" % p)
        print("   Move or delete these by hand. They may carry session material.")

    if not expired:
        print("\nnothing expired (window %d days)" % a.days)
        return 1 if intruders else 0

    if not a.delete:
        print("\ndry run — %d target(s) past the %d-day window. Re-run with --delete to remove."
              % (len(expired), a.days))
        return 1 if intruders else 0

    for r in expired:
        shutil.rmtree(r["path"], ignore_errors=True)
        print("deleted %s" % r["path"])
    return 1 if intruders else 0


if __name__ == "__main__":
    sys.exit(main())
