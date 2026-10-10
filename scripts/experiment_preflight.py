#!/usr/bin/env python3
"""Preflight for a console batch: forces the hypothesis lookup, then mints a one-shot token.

    python scripts/experiment_preflight.py --list
    python scripts/experiment_preflight.py --batch-file draft.txt [--declare AUTH-001,ORACLE-01]
    python scripts/experiment_preflight.py --reopen AUTH-001 --evidence "<what was observed>"

The sequence is deliberate and the awkward part is the point:

    1. draft the batch to a NON-batch filename (a .txt in the scratchpad)   - unguarded
    2. preflight that draft                                                - the lookup happens
    3. write the real <name>batch.js                                       - guard matches the hash

Step 2 is the forcing function. The token is keyed to the SHA-256 of the exact draft text, so the
content checked in step 2 is byte-identical to the content written in step 3; a token cannot be
minted for a clean draft and spent on a different batch. Tokens are one-shot and expire in 30
minutes - a token lying around from yesterday must not authorise today's paste.

This script refuses the same things the guard refuses, on purpose. Two checks of the same
condition at different moments is not redundancy: the preflight gives a usable error while the
batch is still a draft, and the guard is what holds when the preflight is skipped.

WHAT A CLEARED PREFLIGHT DOES NOT MEAN. It means no currently-FALSIFIED assumption is spelled out
in the draft and a token now exists. It does not mean the batch is correct, that its control is
adequate, or that the surface still behaves as last recorded. Detection is textual and its recall
is unmeasured, so this is a floor on known mistakes, not a ceiling on possible ones.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core import control_event as ce          # noqa: E402
from core import hypothesis_ledger as hl      # noqa: E402

TOOL = "experiment_preflight"
TOKEN_DIR = (os.environ.get("JARVIS_PREFLIGHT_TOKEN_DIR")
             or os.path.join(ROOT, "workspace", "preflight_tokens"))
ME = os.path.abspath(__file__)


def _emit(decision: str, reason: str, rule_id: str, started: float, ctx: str = "") -> None:
    ce.emit(TOOL, decision, reason=reason, rule_id=rule_id, context=ctx,
            duration_ms=int((time.time() - started) * 1000), tool_file=ME)


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:32]


def cmd_list(started: float) -> int:
    if not hl.exists():
        print("NO LEDGER at %s" % hl.ledger_path())
        print("  console-batch writes are DENIED until one exists (fail-closed by design)")
        _emit("BLOCK", "ledger absent", "ledger_absent", started)
        return 1
    cur = hl.latest()
    print("hypothesis ledger: %d id(s), %d record(s)" % (len(cur), len(hl.read_all())))
    for hid in sorted(cur):
        r = cur[hid]
        print("  %-12s %-10s %s" % (hid, r.get("state", "?"), (r.get("claim") or "")[:74]))
        if r.get("state") == "REOPENED":
            print("  %-12s %-10s evidence: %s" % ("", "", (r.get("evidence") or "")[:70]))
    bad = hl.bad_detectors()
    if bad:
        print("\n  *** %d DETECTOR(S) DO NOT COMPILE - the instrument is unusable:" % len(bad))
        for hid, pat in bad:
            print("      %s  %r" % (hid, pat[:60]))
        _emit("BLOCK", "uncompilable detectors present", "detector_unusable", started)
        return 1
    print("\n  detectors: %d compiled, all usable" % len(hl.compiled_detectors()))
    _emit("PASS", "ledger listed", "listed", started)
    return 0


def cmd_reopen(hid: str, evidence: str, started: float) -> int:
    ok, msg = hl.reopen(hid, evidence)
    print(("REOPENED  " if ok else "REFUSED   ") + msg)
    if ok:
        # PASS is the right decision: a recorded, evidenced reopening is the control working as
        # designed, not a failure. The vocabulary is not widened to invent a REOPEN decision -
        # rule_id carries that, so the three-value decision set stays comparable over time.
        print("  the FALSIFIED record is NOT deleted; the ledger is append-only, so the history")
        print("  of what was believed and when stays readable.")
        _emit("PASS", "hypothesis reopened on recorded evidence", "hypothesis_reopened",
              started, hid)
        return 0
    _emit("BLOCK", msg, "reopen_refused", started, hid)
    return 1


def cmd_preflight(batch_file: str, use_stdin: bool, declare: str, started: float) -> int:
    if use_stdin:
        text = sys.stdin.read()
        label = "(stdin)"
    else:
        try:
            text = io.open(batch_file, encoding="utf-8", errors="replace").read()
        except OSError as exc:
            print("ERROR cannot read draft: %s" % exc)
            _emit("ERROR", "draft unreadable", "draft_unreadable", started,
                  os.path.basename(batch_file))
            return 2
        label = os.path.basename(batch_file)

    if not text.strip():
        print("ERROR draft is empty - nothing to check")
        _emit("ERROR", "empty draft", "empty_draft", started, label)
        return 2

    print("=== preflight: %s  (%d bytes)" % (label, len(text)))

    if not hl.exists():
        print("BLOCK  no hypothesis ledger at %s" % hl.ledger_path())
        print("       a batch cannot be cleared by an instrument that does not exist")
        _emit("BLOCK", "ledger absent", "ledger_absent", started, label)
        return 1

    bad = hl.bad_detectors()
    if bad:
        print("BLOCK  %d detector(s) do not compile: %s" % (len(bad), ", ".join(i for i, _ in bad)))
        print("       an unusable instrument cannot issue a pass")
        _emit("BLOCK", "uncompilable detectors", "detector_unusable", started, label)
        return 1

    hits = hl.match(text)
    if hits:
        print("BLOCK  this draft asserts %d assumption(s) recorded FALSIFIED:" % len(hits))
        for rec, pat in hits:
            print("         %s  %s" % (rec["id"], (rec.get("claim") or "")[:72]))
            print("           evidence     : %s" % (rec.get("evidence") or "")[:72])
            print("           corrected to : %s" % (rec.get("corrected_to") or "")[:72])
            print("           matched      : %r" % pat[:60])
        print("       NO TOKEN ISSUED. Fix the draft, or reopen with new evidence:")
        print("         --reopen %s --evidence \"<what you observed, where>\"" % hits[0][0]["id"])
        _emit("BLOCK", "draft asserts a falsified hypothesis", "falsified_assumption",
              started, label)
        return 1

    declared = [d.strip() for d in (declare or "").split(",") if d.strip()]
    known = set(hl.latest())
    unknown = [d for d in declared if d not in known]
    if unknown:
        # A declared id that does not exist is a typo that would otherwise read as diligence.
        print("BLOCK  declared unknown hypothesis id(s): %s" % ", ".join(unknown))
        _emit("BLOCK", "declared unknown hypothesis id", "unknown_declared", started, label)
        return 1

    h = content_hash(text)
    tok = {
        "content_hash": h,
        "issued_epoch": time.time(),
        "issued_utc": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + "Z",
        "run_id": ce.run_id(),
        "declared": declared,
        "ledger_records": len(hl.read_all()),
        "note": "one-shot; consumed by batch_write_guard on the matching write",
    }
    try:
        os.makedirs(TOKEN_DIR, exist_ok=True)
        with io.open(os.path.join(TOKEN_DIR, h + ".json"), "w",
                     encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(tok, indent=2) + "\n")
    except OSError as exc:
        print("ERROR token write failed: %s" % exc)
        print("      the write will be DENIED, which is the correct outcome for an unissued token")
        _emit("ERROR", "token write failed", "token_write_failed", started, label)
        return 2

    print("PASS   no falsified assumption matched; token issued")
    print("       content_hash : %s" % h)
    print("       declared     : %s" % (", ".join(declared) or "(none)"))
    print("       valid for    : 30 min, ONE write of this exact content")
    print("       scope        : this clears KNOWN falsified assumptions only - textual match,")
    print("                      recall unmeasured. It is not a verdict on the batch.")
    _emit("PASS", "token issued for a clean draft", "token_issued", started, label)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="hypothesis preflight for console batches")
    ap.add_argument("--batch-file", help="draft file to check (use a NON-batch filename)")
    ap.add_argument("--stdin", action="store_true", help="read the draft from stdin")
    ap.add_argument("--declare", default="", help="comma-separated hypothesis ids this batch rests on")
    ap.add_argument("--reopen", metavar="ID", help="move a FALSIFIED hypothesis back to REOPENED")
    ap.add_argument("--evidence", default="", help="required with --reopen")
    ap.add_argument("--list", action="store_true", help="show ledger state")
    a = ap.parse_args()
    started = time.time()

    if a.list:
        return cmd_list(started)
    if a.reopen:
        return cmd_reopen(a.reopen, a.evidence, started)
    if a.stdin or a.batch_file:
        return cmd_preflight(a.batch_file or "", a.stdin, a.declare, started)
    ap.print_help()
    _emit("ERROR", "no action requested", "no_args", started)
    return 2


if __name__ == "__main__":
    sys.exit(main())
