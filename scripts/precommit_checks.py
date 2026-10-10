#!/usr/bin/env python3
"""Engine pre-commit: a staged change to a control reruns that control's suites, or blocks.

Gives "regression tests after a change" an owner. Before this, it was memory: the PreToolUse
hook covers the moment before an action, the closure gate covers closure, and nothing forced a
test run after a control was edited.

FAIL-CLOSED. A suite that fails, cannot start, times out, or leaves a record that does not
validate blocks the commit. So does any crash in this script.

Only fires when a staged path is covered by a registered check, so ordinary commits pay nothing.
LIMIT, stated: suites run against the WORKING TREE, not the staged snapshot. A partially staged
file is tested as it sits on disk.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from core import check_evidence as ev    # noqa: E402
from core import control_event as ce     # noqa: E402

ME = os.path.abspath(__file__)


def staged_paths() -> list:
    out = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=ACMRD"],
                         cwd=ROOT, capture_output=True, text=True, check=True).stdout
    return [p for p in out.splitlines() if p.strip()]


def decide(staged: list, runner=ev.run, validator=ev.validate) -> tuple:
    """-> (ok, [lines]). Pure apart from the injected runner/validator, so it is testable."""
    affected = ev.affected_by(staged)
    if not affected:
        return True, []
    lines, ok = [], True
    for cid in affected:
        try:
            rec = runner(cid)
        except Exception as exc:                          # noqa: BLE001 - must block, not pass
            lines.append("  %-16s COULD NOT RUN: %s" % (cid, str(exc)[:100]))
            ok = False
            continue
        why = validator(cid)
        if why:
            ok = False
        lines.append("  %-16s %s rc=%s %s" % (cid, rec.get("status"), rec.get("exit_code"),
                                               why or ""))
    return ok, lines


def main() -> int:
    t0 = time.time()
    try:
        staged = staged_paths()
        ok, lines = decide(staged)
    except Exception as exc:                              # noqa: BLE001
        print("  COMMIT BLOCKED - pre-commit check runner crashed: %s" % str(exc)[:160])
        ce.emit("precommit_checks", "ERROR", "runner crashed", rule_id="crash",
                duration_ms=int((time.time() - t0) * 1000), tool_file=ME)
        return 1
    if not lines:
        return 0                                          # no control staged: nothing to rerun
    print("pre-commit: control files staged, required suites rerun:")
    print("\n".join(lines))
    dur = int((time.time() - t0) * 1000)
    if ok:
        ce.emit("precommit_checks", "PASS", "affected suites passed with valid evidence",
                rule_id="suites_green", context="%d suite(s)" % len(lines),
                duration_ms=dur, tool_file=ME)
        return 0
    print("  COMMIT BLOCKED - a required suite failed, could not run, or left invalid evidence.")
    ce.emit("precommit_checks", "BLOCK", "required suite failed or evidence invalid",
            rule_id="suite_failed", context="%d suite(s)" % len(lines),
            duration_ms=dur, tool_file=ME)
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:                              # noqa: BLE001
        print("  COMMIT BLOCKED - pre-commit crashed: %s" % str(exc)[:160])
        sys.exit(1)
