#!/usr/bin/env python3
"""Run a required check by id, or report evidence status. The ONLY writer of check records.

    python scripts/run_check.py <check_id>     run one registered check, record the evidence
    python scripts/run_check.py --all          run every registered check
    python scripts/run_check.py --status       one line per check: VALID / STALE / FAILED / ...

There is deliberately no way to pass a command. A check id resolves to a fixed command in
core/check_evidence.REGISTRY, which is version-controlled; anything else is refused.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from core import check_evidence as ev  # noqa: E402


def status() -> int:
    bad = ev.validate_all()
    for cid in ev.REGISTRY:
        print("  %-16s %s" % (cid, bad.get(cid) or "VALID"))
    print("required checks: %d/%d valid" % (len(ev.REGISTRY) - len(bad), len(ev.REGISTRY)))
    return 0 if not bad else 1


def main(argv) -> int:
    if argv == ["--status"]:
        return status()
    if argv == ["--all"]:
        ids = list(ev.REGISTRY)
    elif len(argv) == 1 and argv[0] in ev.REGISTRY:
        ids = argv
    else:
        print("refused: give exactly one registered check id, --all, or --status")
        print("registered: %s" % ", ".join(ev.REGISTRY))
        return 2
    worst = 0
    for cid in ids:
        rec = ev.run(cid)
        print("  %-16s %s  rc=%s  %.0fs  %s" % (cid, rec["status"], rec["exit_code"],
                                              rec["duration_s"], rec["output_path"]))
        worst = worst or (0 if rec["status"] == "PASS" else 1)
    return worst


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
