#!/usr/bin/env python3
"""Mutation check: does the guard's test suite actually go RED when the guard is broken?

    python scripts/mutation_check.py

Why: three green suites in one build each hid a real defect, and one verification row passed
while testing nothing. A test proves something only if it FAILS when the property it names is
removed. So each mutant below deletes exactly one property from a COPY of the guard, the suite
is pointed at that copy, and the suite must fail. A mutant the suite survives is a named test
gap, reported as such - never rounded into a pass.

The shipped guard is never edited: the live PreToolUse hook runs it, so mutating it in place
would put a broken guard in front of every real Write/Edit/Bash call for the duration.
"""
from __future__ import annotations

import io
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUARD = os.path.join(ROOT, "scripts", "batch_write_guard.py")
# Same directory as the real guard so its ROOT derivation and imports resolve identically.
MUTANT = os.path.join(ROOT, "scripts", "_mutant_guard.py")
SUITE = os.path.join(ROOT, "scripts", "hypothesis_check.py")

# (id, property removed, exact source text, replacement). Each `old` must occur exactly once.
MUTANTS = [
    ("M1", "ledger match disabled (the detector itself)",
     "    hits = hl.match(text)\n", "    hits = []\n"),
    ("M2", "missing-token check disabled",
     "    if tok is None:\n", "    if False:\n"),
    ("M3", "token not consumed (replay possible)",
     "    consume_token(h)\n", "    pass\n"),
    ("M4", "token expiry disabled",
     "    if age > TOKEN_TTL_SECONDS:\n", "    if False:\n"),
    ("M5", "fail-OPEN on missing ledger",
     "    if not hl.exists():\n", "    if False:\n"),
    ("M6", "path normalisation removed",
     "    p = posixpath.normpath(p)\n", "    p = p\n"),
    ("M7", "scratch-directory scope removed (filename-only again)",
     '    return "/workspace/scratch/" in', '    return False and "/workspace/scratch/" in'),
    ("M8", "Edit's new_string unguarded",
     '    for key in ("content", "new_string"):', '    for key in ("content",):'),
    ("M9", "whole shell route disabled",
     "    targets = [t for t in shell_write_targets(command, cwd) if in_scope(t)]\n",
     "    targets = []\n"),
    ("M10", "tee detection removed",
     "    for m in _TEE.finditer(command):\n", "    for m in []:\n"),
    ("M11", "PowerShell cmdlet detection removed",
     "    for m in _PS_WRITE.finditer(command):\n", "    for m in []:\n"),
    ("M12", "relative targets not resolved against cwd",
     "        r = _resolve(t, cwd)\n", "        r = t\n"),
    ("M13", "action_id dropped",
     '    action_id = str(call.get("tool_use_id") or "")\n', '    action_id = ""\n'),
    ("M14", "uncompilable detectors ignored",
     "    bad = hl.bad_detectors()\n", "    bad = []\n"),
]


def run_suite(guard_path: str) -> tuple:
    """-> (exit_code, passed_line). The suite is run as a real subprocess."""
    env = dict(os.environ, JARVIS_GUARD_SCRIPT=guard_path)
    r = subprocess.run([sys.executable, SUITE], capture_output=True, text=True, env=env, cwd=ROOT)
    tail = [ln for ln in r.stdout.splitlines() if "acceptance checks passed" in ln]
    return r.returncode, (tail[-1].strip() if tail else "(no summary line)")


def main() -> int:
    src = io.open(GUARD, encoding="utf-8").read()
    started = time.time()
    print("=== mutation check - every mutant must turn the suite RED")

    # Baseline first: if the suite is red on the REAL guard, every "kill" below means nothing.
    rc, line = run_suite(GUARD)
    print("  baseline (shipped guard)   rc=%d  %s" % (rc, line))
    if rc != 0:
        print("  ABORT: suite is red on the unmutated guard; kills would be meaningless")
        return 2

    survived, invalid, crashed = [], [], []
    try:
        for mid, what, old, new in MUTANTS:
            n = src.count(old)
            if n != 1:
                # A mutant that cannot be applied tests nothing; counted separately, never as a kill.
                invalid.append(mid)
                print("  %-4s INVALID  anchor matched %d times  (%s)" % (mid, n, what))
                continue
            with io.open(MUTANT, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(src.replace(old, new))
            rc, line = run_suite(MUTANT)
            killed = rc != 0
            if not killed:
                survived.append(mid)
            # A kill by CRASH is still red, but every later check stopped running, so it is a
            # weaker kill than a failed assertion. Labelled, never merged.
            label = "SURVIVED" if not killed else (
                "KILLED*" if line == "(no summary line)" else "KILLED")
            if label == "KILLED*":
                crashed.append(mid)
            print("  %-4s %-8s %-50s %s" % (mid, label, what[:50],
                                            line.replace(" acceptance checks passed", "")))
    finally:
        if os.path.exists(MUTANT):
            os.remove(MUTANT)

    applied = len(MUTANTS) - len(invalid)
    print()
    print("  mutants: %d defined | %d applied | %d killed | %d survived | %d invalid"
          % (len(MUTANTS), applied, applied - len(survived), len(survived), len(invalid)))
    if survived:
        print("  SURVIVORS = test gaps: %s" % ", ".join(survived))
    if crashed:
        print("  KILLED* = suite CRASHED rather than failing an assertion: %s" % ", ".join(crashed))
    print("  mutant file cleaned up: %s   elapsed %.0fs"
          % (not os.path.exists(MUTANT), time.time() - started))
    print("  SCOPE: mutants cover the guard only. Ledger-module and preflight-script mutants are")
    print("  NOT run here, so this is no statement about their tests.")
    return 0 if not survived and not invalid else 1


if __name__ == "__main__":
    sys.exit(main())
