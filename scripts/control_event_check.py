#!/usr/bin/env python3
"""Acceptance tests for the control event trail. Exercises the REAL decision paths.

The nuance that matters, and the reason this does not just unit-test the helper: twelve
instrumented call sites do not mean twelve correct events. Each test below runs an actual
control as a subprocess, on a real input that forces a specific decision, and then reads the
event back off disk. If the control's exit code and its logged decision ever disagree, that is
a defect the helper alone could never reveal.

    python scripts/control_event_check.py

Exit 0 = every acceptance criterion met.
"""
import io
import json
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from core import control_event as ce  # noqa: E402

PY = sys.executable
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print("  %-52s %s  %s" % (name[:52], "PASS" if ok else "*** FAIL ***", detail[:60]))


def run(script, args, logpath, expect_rc=None):
    """-> (returncode, [events]). The control runs as a real subprocess."""
    env = dict(os.environ, JARVIS_CONTROL_LOG=logpath, JARVIS_RUN_ID="test-run")
    r = subprocess.run([PY, os.path.join(ROOT, script)] + args,
                       capture_output=True, text=True, env=env, cwd=ROOT)
    return r, ce.read_events(logpath)


def main():
    tmp = tempfile.mkdtemp()
    print("=== control event trail - acceptance tests")

    # ---------------------------------------------------------------- helper behaviour
    lp = os.path.join(tmp, "a.jsonl")
    ok = ce.emit("t", "PASS", "fine", rule_id="r1", context="ctx", path=lp)
    evs = ce.read_events(lp)
    check("emit returns True and writes one event", ok and len(evs) == 1)
    e = evs[0] if evs else {}
    need = {"event_id", "ts", "run_id", "tool", "tool_version", "decision",
            "rule_id", "reason", "duration_ms", "context", "test_mode"}
    check("event carries every required field", need <= set(e), "missing %s" % (need - set(e)))

    # secrets must never reach a file we keep forever
    lp2 = os.path.join(tmp, "b.jsonl")
    # prepush: allow - synthetic literals, deliberately credential-SHAPED so the redaction
    # path is actually exercised. The pre-push guard flags this line correctly; it is the one
    # place in the repo where a fake credential must exist for a test to mean anything.
    ce.emit("t", "PASS", "cookie=abc123; authorization: Bearer xyz",
            context="https://target.example/secret?token=abc", path=lp2)
    e2 = ce.read_events(lp2)[0]
    check("reason with session material is redacted",
          "REDACTED" in e2["reason"], e2["reason"][:40])
    check("context with a URL is redacted",
          "REDACTED" in e2["context"], e2["context"][:40])

    # run id stability
    check("run_id is stable within a process", ce.run_id() == ce.run_id())

    # ---------------------------------------------------------------- log-write failure
    # point the log at a path that cannot be created: a FILE used as a directory
    blocker = os.path.join(tmp, "blocker")
    io.open(blocker, "w").write("x")
    bad = os.path.join(blocker, "sub", "c.jsonl")
    ok2 = ce.emit("t", "BLOCK", "should fail to write", path=bad)
    check("failed write returns False (not silently swallowed)", ok2 is False)
    check("failed write produced NO file", not os.path.exists(bad))

    # ---------------------------------------------------------------- real control paths
    # console_batch: ERROR (no args) / BLOCK (bad fixture) / PASS (good fixture)
    lp3 = os.path.join(tmp, "cb.jsonl")
    r, evs = run("scripts/console_batch.py", [], lp3)
    check("console_batch no-args -> rc 2 and an ERROR event",
          r.returncode == 2 and any(x["decision"] == "ERROR" for x in evs),
          "rc=%s" % r.returncode)

    lp4 = os.path.join(tmp, "cb2.jsonl")
    r, evs = run("scripts/console_batch.py", ["fixtures/console/negative-v1.js"], lp4)
    logged = evs[-1]["decision"] if evs else "(none)"
    check("console_batch bad batch -> rc 1 AND logged BLOCK",
          r.returncode == 1 and logged == "BLOCK", "rc=%s logged=%s" % (r.returncode, logged))

    lp5 = os.path.join(tmp, "cb3.jsonl")
    r, evs = run("scripts/console_batch.py", ["fixtures/console/positive-v1.js"], lp5)
    logged = evs[-1]["decision"] if evs else "(none)"
    check("console_batch good batch -> rc 0 AND logged PASS",
          r.returncode == 0 and logged == "PASS", "rc=%s logged=%s" % (r.returncode, logged))

    # closure_gate: ERROR (no args) / PASS (a matrix with no closure claim)
    lp6 = os.path.join(tmp, "cg.jsonl")
    r, evs = run("scripts/closure_gate.py", [], lp6)
    check("closure_gate no-args -> rc 2 AND logged ERROR",
          r.returncode == 2 and any(x["decision"] == "ERROR" for x in evs),
          "rc=%s" % r.returncode)

    open_matrix = os.path.join(tmp, "zz_matrix.md")
    io.open(open_matrix, "w", encoding="utf-8").write("| closed | - |\n")
    lp7 = os.path.join(tmp, "cg2.jsonl")
    r, evs = run("scripts/closure_gate.py", [open_matrix], lp7)
    logged = evs[-1]["decision"] if evs else "(none)"
    check("closure_gate open matrix -> rc 0 AND logged PASS",
          r.returncode == 0 and logged == "PASS", "rc=%s logged=%s" % (r.returncode, logged))

    # closure_gate BLOCK: a matrix claiming closure with no proof beside it
    closed_matrix = os.path.join(tmp, "yy_matrix.md")
    io.open(closed_matrix, "w", encoding="utf-8").write("| closed | 2026-01-01 |\n")
    lp8 = os.path.join(tmp, "cg3.jsonl")
    r, evs = run("scripts/closure_gate.py", [closed_matrix], lp8)
    logged = evs[-1]["decision"] if evs else "(none)"
    check("closure_gate unbacked closure -> rc 1 AND logged BLOCK",
          r.returncode == 1 and logged == "BLOCK", "rc=%s logged=%s" % (r.returncode, logged))

    # closure_gate --staged with nothing staged -> the not_applicable PASS path
    lp9 = os.path.join(tmp, "cg4.jsonl")
    r, evs = run("scripts/closure_gate.py", ["--staged"], lp9)
    logged = evs[-1]["decision"] if evs else "(none)"
    rule = evs[-1]["rule_id"] if evs else ""
    check("closure_gate --staged, nothing staged -> PASS/not_applicable",
          r.returncode == 0 and logged == "PASS" and rule == "not_applicable",
          "rc=%s logged=%s rule=%s" % (r.returncode, logged, rule))

    # ---------------------------------------------------------------- decision integrity
    # the control's exit code and its logged decision must never disagree
    print()
    bad_rows = sum(1 for n, ok, _ in RESULTS if not ok)
    print("  %d of %d acceptance checks passed" % (len(RESULTS) - bad_rows, len(RESULTS)))
    return 0 if bad_rows == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
