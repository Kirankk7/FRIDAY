#!/usr/bin/env python3
"""Acceptance tests for the hypothesis ledger + preflight + PreToolUse guard.

    python scripts/hypothesis_check.py

Structured around six stated acceptance criteria, then the defect classes that sit underneath
them. Every test runs the REAL script as a subprocess against a TEMP ledger with SYNTHETIC
patterns - no live-target string appears in this file, and the real ledger is never touched.

Why subprocesses and not imports: on the previous build, `closure_gate.py` had instrumentation
call sites but no import for the helper, so every real path raised NameError while the unit tests
stayed green. An in-process test of a function cannot catch a module that fails to load. The exit
code and the logged decision are checked TOGETHER for the same reason - a control whose verdict
and record disagree is worse than one that records nothing.

CRITERION 6 CANNOT PASS AFFIRMATIVELY, and the test says so rather than quietly omitting it. The
guard is a file-write hook. A batch delivered by any other route never reaches it. That test
DEMONSTRATES the bypass and then shows the trail holds zero events for it - bypass CONFIRMED and
explicitly NOT MEASURED, which are different claims.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from core import control_event as ce          # noqa: E402
from core import hypothesis_ledger as hl      # noqa: E402

PY = sys.executable
RESULTS = []

# Synthetic stand-ins. The shapes mirror the real records; the strings are invented so this file
# stays publishable. SYNTH-AUTH plays the part of the three-times-repeated cookie assumption.
SEED = [
    {"event_id": "t0001", "id": "SYNTH-AUTH", "state": "FALSIFIED",
     "claim": "the zzcanary credential mode authenticates the fixture API",
     "evidence": "falsified three times on the fixture surface; the capture carried no such credential",
     "corrected_to": "send the fixture token header instead",
     "detect": ["zzcanary\\s*:\\s*[\"']include[\"']"]},
    {"event_id": "t0002", "id": "SYNTH-ORACLE", "state": "FALSIFIED",
     "claim": "the zzoracle endpoint answers on fixture store B",
     "evidence": "returned 500 on store B while answering on store A",
     "corrected_to": "use the alternate oracle and carry a positive control",
     "detect": ["zzoracle-endpoint"]},
    # Exists solely so the redaction defect has a regression test. Its claim deliberately
    # contains a word on the event log's forbidden list, which is what made the real guard log
    # "<REDACTED>" in place of its reason.
    {"event_id": "t0003", "id": "SYNTH-REDACT", "state": "FALSIFIED",
     "claim": "cookies authenticate the fixture panel",
     "evidence": "the fixture capture carried no such credential on any request",
     "corrected_to": "send the fixture token header read by shape",
     "detect": ["zzredact-probe"]},
]


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print("  %-56s %s %s" % (name[:56], "PASS" if ok else "*** FAIL ***", detail[:52]))


class Env(object):
    """One isolated world: its own ledger, control log and token dir."""

    def __init__(self, seed=SEED, ledger_name="led.jsonl"):
        self.tmp = tempfile.mkdtemp()
        self.ledger = os.path.join(self.tmp, ledger_name)
        self.log = os.path.join(self.tmp, "events.jsonl")
        self.tokens = os.path.join(self.tmp, "tokens")
        if seed is not None:
            with io.open(self.ledger, "w", encoding="utf-8", newline="\n") as fh:
                for r in seed:
                    r = dict(r)
                    r.setdefault("ts", "2026-10-10T00:00:00Z")
                    fh.write(json.dumps(r) + "\n")

    @property
    def env(self):
        return dict(os.environ,
                    JARVIS_HYPOTHESIS_LEDGER=self.ledger,
                    JARVIS_CONTROL_LOG=self.log,
                    JARVIS_PREFLIGHT_TOKEN_DIR=self.tokens,
                    JARVIS_RUN_ID="acceptance")

    def guard(self, file_path, content=None, new_string=None, tool="Write"):
        """-> (rc, stdout, events). Feeds the guard a real tool call on stdin."""
        ti = {"file_path": file_path}
        if content is not None:
            ti["content"] = content
        if new_string is not None:
            ti["new_string"] = new_string
        payload = json.dumps({"tool_name": tool, "tool_input": ti})
        r = subprocess.run([PY, os.path.join(ROOT, "scripts", "batch_write_guard.py")],
                           input=payload, capture_output=True, text=True,
                           env=self.env, cwd=ROOT)
        return r.returncode, r.stdout, ce.read_events(self.log)

    def guard_raw(self, payload):
        r = subprocess.run([PY, os.path.join(ROOT, "scripts", "batch_write_guard.py")],
                           input=payload, capture_output=True, text=True,
                           env=self.env, cwd=ROOT)
        return r.returncode, r.stdout, ce.read_events(self.log)

    def preflight(self, *args):
        r = subprocess.run([PY, os.path.join(ROOT, "scripts", "experiment_preflight.py")]
                           + list(args), capture_output=True, text=True,
                           env=self.env, cwd=ROOT)
        return r.returncode, r.stdout + r.stderr, ce.read_events(self.log)

    def draft(self, text, name="draft.txt"):
        fp = os.path.join(self.tmp, name)
        io.open(fp, "w", encoding="utf-8", newline="\n").write(text)
        return fp

    def tokens_on_disk(self):
        try:
            return sorted(os.listdir(self.tokens))
        except OSError:
            return []

    def clean(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


def denied(rc, out):
    """A refusal must be unambiguous on BOTH channels the host may read."""
    if rc != 2:
        return False
    try:
        d = json.loads(out)
    except ValueError:
        return False
    hs = d.get("hookSpecificOutput") or {}
    return (hs.get("permissionDecision") == "deny"
            and hs.get("hookEventName") == "PreToolUse"
            and bool(hs.get("permissionDecisionReason")))


# The historical failure, in synthetic clothing: a batch resting on the falsified credential mode.
BAD_BATCH = """// probe: fixture profile read
const r = await fetch('/api/v1/profile', {
  zzcanary: 'include',
  headers: {'content-type': 'application/json'}
});
console.log(r.status, await r.text());
// positive control
const c = await fetch('/api/v1/self');
console.log('control', c.status);
"""

GOOD_BATCH = """// probe: fixture profile read
const tok = Object.values(window).find(v => /^[0-9a-f]{32}$/.test(String(v)));
const r = await fetch('/api/v1/profile', {headers: {'x-fixture-token': tok}});
console.log(r.status, await r.text());
const c = await fetch('/api/v1/self', {headers: {'x-fixture-token': tok}});
console.log('control', c.status);
"""

BATCH_PATH = "/d/JARVIS/workspace/scratch/probe_batch.js"


def main():
    print("=== hypothesis ledger / preflight / write-guard - acceptance tests")

    # ================================================== CRITERIA 1-4
    print("\n  [1-4] reproduce the assumption, attempt the write, block before any paste, log it")
    e = Env()

    # C1: reproduce the historical assumption as a real draft
    d_bad = e.draft(BAD_BATCH)
    check("1. historical assumption reproduced in a draft",
          "zzcanary: 'include'" in io.open(d_bad, encoding="utf-8").read())

    # C3a: the PREFLIGHT refuses while the batch is still a draft
    rc, out, evs = e.preflight("--batch-file", d_bad)
    check("3a. preflight REFUSES the draft (rc 1, no token)",
          rc == 1 and e.tokens_on_disk() == [] and "FALSIFIED" in out,
          "rc=%s tokens=%d" % (rc, len(e.tokens_on_disk())))
    check("3b. refusal names the id and the correction",
          "SYNTH-AUTH" in out and "fixture token header" in out)

    # C4: and it is durably recorded, with exit code and logged decision agreeing
    logged = evs[-1] if evs else {}
    check("4a. preflight BLOCK is durably logged",
          logged.get("decision") == "BLOCK"
          and logged.get("rule_id") == "falsified_assumption",
          "%s/%s" % (logged.get("decision"), logged.get("rule_id")))

    # C2 + C3c: the WRITE itself is refused - the guard holds even if the preflight is skipped
    rc, out, evs = e.guard(BATCH_PATH, content=BAD_BATCH)
    check("2/3c. the console-batch WRITE is denied (rc 2 + deny JSON)", denied(rc, out),
          "rc=%s" % rc)
    g = [x for x in evs if x["tool"] == "batch_write_guard"]
    check("4b. guard BLOCK is durably logged with the matching rule",
          bool(g) and g[-1]["decision"] == "BLOCK"
          and g[-1]["rule_id"] == "falsified_assumption",
          g[-1]["rule_id"] if g else "(none)")
    check("3d. nothing was written - the deny precedes the file",
          not os.path.exists(BATCH_PATH))

    # a clean batch with no preflight run at all is ALSO denied - the absent question, not a wrong
    # answer, was the original failure
    rc2, out2, _ = e.guard(BATCH_PATH, content=GOOD_BATCH)
    check("3e. clean batch with NO preflight is still denied", denied(rc2, out2),
          "rc=%s" % rc2)
    check("3f. that denial is attributed to the missing token, not to a hypothesis",
          "no_preflight_token" in json.dumps(ce.read_events(e.log)[-1]))

    # ================================================== CRITERION 5
    print("\n  [5] new evidence permits reopening, and the reopening is recorded")
    EV = ("2026-10-10 re-capture of the fixture surface shows the credential mode now accepted "
          "on two endpoints with a passing positive control in the same batch")
    rc, out, evs = e.preflight("--reopen", "SYNTH-AUTH", "--evidence", EV)
    check("5a. reopening on substantive evidence is permitted", rc == 0 and "REOPENED" in out,
          "rc=%s" % rc)
    rec = hl.latest(e.ledger).get("SYNTH-AUTH", {})
    check("5b. ledger now reports REOPENED, carrying the evidence verbatim",
          rec.get("state") == "REOPENED" and rec.get("evidence") == EV)
    check("5c. the FALSIFIED record is NOT deleted (append-only history)",
          sum(1 for r in hl.read_all(e.ledger) if r["id"] == "SYNTH-AUTH") == 2
          and any(r.get("state") == "FALSIFIED"
                  for r in hl.read_all(e.ledger) if r["id"] == "SYNTH-AUTH"))
    ev5 = [x for x in ce.read_events(e.log) if x["rule_id"] == "hypothesis_reopened"]
    check("5d. the reopening itself is durably logged", len(ev5) == 1)

    # and the previously-blocked batch now clears end to end
    rc, out, _ = e.preflight("--batch-file", d_bad, "--declare", "SYNTH-AUTH")
    check("5e. after reopening, the same draft passes preflight", rc == 0 and "token issued" in out,
          "rc=%s" % rc)
    rc, out, evs = e.guard(BATCH_PATH, content=BAD_BATCH)
    check("5f. and the write is now ALLOWED (rc 0, no output)", rc == 0 and out.strip() == "",
          "rc=%s" % rc)
    check("5g. the allow is logged as PASS/cleared",
          ce.read_events(e.log)[-1]["decision"] == "PASS"
          and ce.read_events(e.log)[-1]["rule_id"] == "cleared")

    # thin evidence must not buy a reopening
    e2 = Env()
    rc, out, _ = e2.preflight("--reopen", "SYNTH-ORACLE", "--evidence", "new evidence")
    check("5h. placeholder evidence is REFUSED", rc == 1 and "REFUSED" in out, "rc=%s" % rc)
    rc, out, _ = e2.preflight("--reopen", "SYNTH-ORACLE", "--evidence", "")
    check("5i. empty evidence is REFUSED", rc == 1, "rc=%s" % rc)
    check("5j. ORACLE stayed FALSIFIED after both refusals",
          hl.latest(e2.ledger)["SYNTH-ORACLE"]["state"] == "FALSIFIED")
    e2.clean()

    # ================================================== CRITERION 6
    print("\n  [6] the documented bypass - tested, and reported as what it is")
    e6 = Env()
    # The bypass is not a code path in the guard; it is a DELIVERY ROUTE that never invokes it.
    # So the falsifiable check is on the hook's own MATCHER: whatever tools it does not name
    # cannot be judged, by construction. The first version of this test compared two event
    # counts with no action between them - it asserted 0 == 0 and proved nothing, which is
    # precisely the kind of test that manufactures confidence. This reads the real config.
    cfg_path = os.path.join(ROOT, ".claude", "settings.json")
    try:
        cfg = json.load(io.open(cfg_path, encoding="utf-8"))
        groups = cfg.get("hooks", {}).get("PreToolUse", [])
        matchers = [g.get("matcher", "") for g in groups]
        tools_guarded = set()
        for m in matchers:
            tools_guarded.update(t for t in m.split("|") if t)
    except (OSError, ValueError):
        tools_guarded = set()
    check("6a. the hook config exists and names ONLY file-write tools",
          tools_guarded == {"Write", "Edit"}, "guards=%s" % (sorted(tools_guarded) or "NONE"))
    check("6a2. therefore no non-file-write delivery route is covered",
          "Bash" not in tools_guarded and "PowerShell" not in tools_guarded)
    # onFailure must be "block": a guard that passes when it crashes is not a guard.
    try:
        of = groups[0]["hooks"][0].get("onFailure")
    except Exception:                                      # noqa: BLE001
        of = None
    check("6a3. the hook is configured to BLOCK on its own failure", of == "block", str(of))
    # And confirm the guard is a no-op even if handed a non-file-write call shape.
    rc, out, evs = e6.guard_raw(json.dumps(
        {"tool_name": "Bash", "tool_input": {"command": "echo " + BAD_BATCH[:40]}}))
    check("6b. the guard cannot judge a non-file-write call (rc 0, no event)",
          rc == 0 and len(evs) == 0, "rc=%s events=%d" % (rc, len(evs)))
    print("      VERDICT 6: bypass CONFIRMED present and NOT MEASURED.")
    print("        confirmed - a batch delivered outside Write/Edit never reaches the guard;")
    print("        not measured - no mechanism counts those attempts, so the trail cannot")
    print("        report a bypass rate, and its event counts describe the guarded path only.")
    e6.clean()

    # ================================================== underneath the criteria
    print("\n  [+] fail-closed behaviour and token integrity")

    # no ledger at all -> DENY, not pass. The defect class already fixed once in gen_hunt_targets.
    e3 = Env(seed=None)
    rc, out, evs = e3.guard(BATCH_PATH, content=GOOD_BATCH)
    check("+1. MISSING ledger denies the write (fail-closed)", denied(rc, out), "rc=%s" % rc)
    check("+2. that denial is attributed to ledger_absent",
          evs and evs[-1]["rule_id"] == "ledger_absent",
          evs[-1]["rule_id"] if evs else "(none)")
    e3.clean()

    # an uncompilable detector is an unusable instrument -> DENY, never a silent skip
    e4 = Env(seed=[{"event_id": "t9", "id": "SYNTH-BAD", "state": "FALSIFIED",
                    "claim": "broken detector", "evidence": "x", "corrected_to": "y",
                    "detect": ["zz(unclosed"]}])
    rc, out, evs = e4.guard(BATCH_PATH, content=GOOD_BATCH)
    check("+3. UNCOMPILABLE detector denies the write", denied(rc, out), "rc=%s" % rc)
    check("+4. attributed to detector_unusable, not silently skipped",
          evs and evs[-1]["rule_id"] == "detector_unusable",
          evs[-1]["rule_id"] if evs else "(none)")
    rc, out, _ = e4.preflight("--list")
    check("+5. --list refuses to report a healthy ledger when a detector is broken",
          rc == 1 and "DO NOT COMPILE" in out, "rc=%s" % rc)
    e4.clean()

    # token is bound to CONTENT, not to intent
    e5 = Env()
    d_ok = e5.draft(GOOD_BATCH, "ok.txt")
    rc, _, _ = e5.preflight("--batch-file", d_ok)
    check("+6. a clean draft mints exactly one token",
          rc == 0 and len(e5.tokens_on_disk()) == 1, "tokens=%d" % len(e5.tokens_on_disk()))
    rc, out, evs = e5.guard(BATCH_PATH, content=GOOD_BATCH + "\nconsole.log('extra');")
    check("+7. a token does NOT authorise different content", denied(rc, out), "rc=%s" % rc)
    rc, out, _ = e5.guard(BATCH_PATH, content=GOOD_BATCH)
    check("+8. the exact cleared content is allowed", rc == 0, "rc=%s" % rc)
    check("+9. the token is CONSUMED by that write (one-shot)", e5.tokens_on_disk() == [],
          str(e5.tokens_on_disk()))
    rc, out, _ = e5.guard(BATCH_PATH, content=GOOD_BATCH)
    check("+10. replaying the same write is denied after consumption", denied(rc, out),
          "rc=%s" % rc)

    # expiry: a token from yesterday must not clear today's paste
    rc, _, _ = e5.preflight("--batch-file", d_ok)
    tf = os.path.join(e5.tokens, e5.tokens_on_disk()[0])
    tok = json.load(io.open(tf, encoding="utf-8"))
    tok["issued_epoch"] = time.time() - (60 * 60 * 24)
    io.open(tf, "w", encoding="utf-8", newline="\n").write(json.dumps(tok))
    rc, out, _ = e5.guard(BATCH_PATH, content=GOOD_BATCH)
    check("+11. an EXPIRED token does not clear the write", denied(rc, out), "rc=%s" % rc)

    # the Edit path carries batch source in new_string, not content
    rc, out, _ = e5.guard(BATCH_PATH, new_string=BAD_BATCH, tool="Edit")
    check("+12. Edit's new_string is guarded, not just Write's content", denied(rc, out),
          "rc=%s" % rc)

    # declaring an id that does not exist reads as diligence and must be refused
    rc, out, _ = e5.preflight("--batch-file", d_ok, "--declare", "SYNTH-AUTH,NOPE-404")
    check("+13. a declared UNKNOWN hypothesis id is refused",
          rc == 1 and "NOPE-404" in out, "rc=%s" % rc)

    # scope: an ordinary file must not be touched, and must not pollute the trail
    n_before = len(ce.read_events(e5.log))
    rc, out, _ = e5.guard("/d/JARVIS/core/some_module.py", content=BAD_BATCH)
    check("+14. a non-batch write passes untouched", rc == 0 and out.strip() == "", "rc=%s" % rc)
    check("+15. and writes NO event (the trail stays interpretable)",
          len(ce.read_events(e5.log)) == n_before)

    # malformed hook input is an instrument failure, not an all-clear
    rc, out, _ = e5.guard_raw("{not json")
    check("+16. malformed hook input denies (fail-closed)", denied(rc, out), "rc=%s" % rc)
    e5.clean()
    e.clean()

    # ---------------------------------------------------------------- regressions for the two
    # defects that PROBING found and the first version of this suite did not. Both are here
    # because a defect caught by hand and not added to the harness simply recurs later.
    print("\n  [R] regressions - defects found by probing, not by the first suite")
    e7 = Env()

    # R1: the rename bypass. probe_batch.js was guarded; probe.js was not, which made the gate
    # a naming convention anyone could step around by choosing a different filename.
    rc, out, _ = e7.guard("/d/JARVIS/workspace/scratch/probe.js", content=BAD_BATCH)
    check("R1. a RENAMED .js under workspace/scratch is still guarded", denied(rc, out),
          "rc=%s" % rc)
    # neutral folder name on purpose: this repo is public, and a programme name in a test path
    # is the exact leak the disclosure guard exists for. Caught by hand-scanning the staged diff.
    rc, out, _ = e7.guard("D:\\JARVIS\\workspace\\scratch\\target-a\\p.js", content=BAD_BATCH)
    check("R1b. and with Windows separators and a nested target folder", denied(rc, out),
          "rc=%s" % rc)
    rc, out, _ = e7.guard("/d/JARVIS/core/helper.js", content=BAD_BATCH)
    check("R1c. but engine .js outside scratch is NOT swept in", rc == 0, "rc=%s" % rc)

    # R2: the logged reason must survive the sanitiser while the operator still gets the detail.
    # R1d: path SPELLINGS. Substring matching on a raw path was wrong three ways, all found by
    # driving a matrix through the shipped function and none caught by the suite as first
    # written. Two slipped through the guard; one guarded an engine file by mistake.
    for spelling, want_guarded in [
            ("D:/JARVIS/workspace//scratch/p.js", True),
            ("D:/JARVIS/workspace/./scratch/p.js", True),
            ("D:/JARVIS/core/../workspace/scratch/p.js", True),
            ("D:/JARVIS/workspace/scratch/sub/../p.js", True),
            ("D:/JARVIS/workspace/scratch/../../core/helper.js", False),
    ]:
        rc, out, _ = e7.guard(spelling, content=BAD_BATCH)
        ok = denied(rc, out) if want_guarded else (rc == 0)
        check("R1d. %s -> %s" % (spelling[10:], "guarded" if want_guarded else "out"), ok,
              "rc=%s" % rc)

    rc, out, evs = e7.guard("/d/JARVIS/workspace/scratch/x_batch.js",
                            content="fetch('/zzredact-probe')")
    g2 = [x for x in evs if x["tool"] == "batch_write_guard"]
    logged_reason = g2[-1]["reason"] if g2 else ""
    check("R2. the LOGGED block reason is not redacted away",
          "REDACTED" not in logged_reason and "SYNTH-REDACT" in logged_reason,
          logged_reason[:44])
    check("R2b. and the deny message still carries the ledger detail",
          "fixture token header" in out and "cookies authenticate" in out)

    # R3: a reason containing a slash must not be amputated to its basename. Found by reading
    # the real trail, not by any test: the no_preflight_token reason names a script path, so the
    # shared context sanitiser basename'd the whole sentence and logged a mid-clause fragment.
    rc, out, evs = e7.guard("/d/JARVIS/workspace/scratch/needs_token_batch.js",
                            content=GOOD_BATCH)
    g3 = [x for x in evs if x["rule_id"] == "no_preflight_token"]
    r3 = g3[-1]["reason"] if g3 else ""
    check("R3. a reason mentioning a path keeps its opening words",
          r3.startswith("no preflight token"), r3[:46])
    check("R3b. and is not reduced to a trailing fragment",
          "/" in r3 and not r3.startswith("experiment_preflight"), "len=%d" % len(r3))
    e7.clean()

    print("\n  NOT COVERED BY THIS HARNESS:")
    print("    - whether a DENY prevented a real wasted paste. A refusal is a refused write;")
    print("      the counterfactual needs the batch run against the live surface.")
    print("    - detector RECALL. Every test asserts a pattern that was written to match. An")
    print("      assumption held but never typed is invisible here and in production.")
    print("    - the hook actually firing inside a live session. settings.json is validated and")
    print("      the script is exercised on real payloads, but the host wiring is proven only")
    print("      when a session loads it; a new session is required.")

    print()
    bad_rows = sum(1 for n, ok, _ in RESULTS if not ok)
    print("  %d of %d acceptance checks passed" % (len(RESULTS) - bad_rows, len(RESULTS)))
    return 0 if bad_rows == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
