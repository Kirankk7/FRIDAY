#!/usr/bin/env python
"""
67e — friday-recon drift report.

JARVIS and the friday-recon CLI share Ultron's offensive core, but the files
DIVERGE BY DESIGN (recon strips JARVIS's Flask/notify/proactive bits). So a
blind copy would break recon. This reports which shared files drifted and by
how much, so fixes (e.g. this session's IPv6 / empty-param / search_cve) get
ported deliberately instead of silently rotting.

Usage: python scripts/recon_drift.py [path-to-friday-recon]   (default D:/friday-recon)
Reports only — copies nothing.
"""
import os
import sys
import hashlib

JARVIS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECON = sys.argv[1] if len(sys.argv) > 1 else "D:/friday-recon"

# Files the two repos share. Pure-shared (should stay identical) vs adapted
# (diverge by design — only port specific fixes, never wholesale).
PURE_SHARED = [
    "core/throttle.py", "core/url_guard.py", "core/security_kb.py",
    "core/target_profiles.py", "core/burp_ingest.py", "core/github_hunt.py",
    "agents/ultron/hackingtool/ht_wrapper.py",
    "agents/ultron/hackingtool/scripts/ht_env.py",
    "agents/ultron/hackingtool/scripts/ht_run.py",
    "agents/ultron/hackingtool/scripts/ht_search.py",
    "agents/ultron/hackingtool/scripts/ht_preflight.py",
]
ADAPTED = ["agents/ultron/ultron_agent.py", "config.py", "core/rag.py"]


def _sha(path):
    try:
        return hashlib.sha256(open(path, "rb").read()).hexdigest()
    except Exception:
        return None


def _lines(path):
    try:
        return sum(1 for _ in open(path, encoding="utf-8", errors="replace"))
    except Exception:
        return 0


def report(group, files, hint):
    print(f"\n{group}")
    print("-" * 56)
    for rel in files:
        j, r = os.path.join(JARVIS, rel), os.path.join(RECON, rel)
        if not os.path.exists(r):
            print(f"  MISSING in recon : {rel}")
            continue
        if _sha(j) == _sha(r):
            print(f"  identical        : {rel}")
        else:
            print(f"  DRIFTED ({_lines(j)} vs {_lines(r)} ln): {rel}")
    print(f"  -> {hint}")


def main():
    if not os.path.isdir(RECON):
        print(f"friday-recon not found at {RECON}. Pass its path as an argument.")
        sys.exit(1)
    print(f"Drift report: JARVIS  <->  {RECON}")
    report("PURE-SHARED (should be identical - copy to fix)", PURE_SHARED,
           "DRIFTED here = safe to copy JARVIS -> recon.")
    report("ADAPTED (diverge by design - port fixes manually)", ADAPTED,
           "DRIFTED is expected; cherry-pick specific fixes, never wholesale copy.")


if __name__ == "__main__":
    main()
