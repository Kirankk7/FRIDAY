#!/usr/bin/env python3
"""Acceptance tests for execution evidence: run_check, the pre-commit hook, the closure gate.

    python scripts/check_runner_check.py

Isolated: every test points JARVIS_CHECK_LOG / JARVIS_CHECK_DIR / JARVIS_CONTROL_LOG at a temp
dir, so the real evidence log is never read or written. The required failure paths are all here:
missing runner output, a failing suite, an unavailable suite, altered and missing artefacts,
stale evidence, a forged command, and an agent-authored "PASS" in a proof.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

PY = sys.executable
RESULTS = []
TMP = tempfile.mkdtemp()
os.environ["JARVIS_CHECK_LOG"] = os.path.join(TMP, "check_runs.jsonl")
os.environ["JARVIS_CHECK_DIR"] = os.path.join(TMP, "runs")
os.environ["JARVIS_CONTROL_LOG"] = os.path.join(TMP, "events.jsonl")

from core import check_evidence as ev     # noqa: E402  (after env, so it reads the temp paths)
import precommit_checks as pc              # noqa: E402
import closure_gate as cg                  # noqa: E402


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print("  %-60s %s %s" % (name[:60], "PASS" if ok else "*** FAIL ***", str(detail)[:40]))


def reset_log():
    for p in (os.environ["JARVIS_CHECK_LOG"],):
        if os.path.exists(p):
            os.remove(p)
    shutil.rmtree(os.environ["JARVIS_CHECK_DIR"], ignore_errors=True)


def forge_valid(check_id, **override):
    """Write a record that validates against the REAL registry and real files - exactly what a
    forger would do. Used to exercise each validation rule one at a time; also demonstrates, in
    the open, that this evidence is NOT tamper-proof."""
    spec = ev.REGISTRY[check_id]
    os.makedirs(ev.artefact_dir(), exist_ok=True)
    art = os.path.join(ev.artefact_dir(), "%s-forged.log" % check_id)
    io.open(art, "w", encoding="utf-8").write("66 of 66 acceptance checks passed\n")
    rec = {"record_id": "f-" + check_id, "check_id": check_id, "command": list(spec["cmd"]),
           "exit_code": 0, "status": "PASS", "output_path": art,
           "output_sha256": ev._sha_file(art), "inputs_sha256": ev.inputs_sha(spec["covers"])}
    rec.update(override)
    with io.open(ev.log_path(), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec) + "\n")
    return rec


def main():
    print("=== execution evidence - acceptance tests")

    # ------------------------------------------------------------------ registry + CLI
    print("\n  [R] registry and CLI")
    check("R1. registry holds at most five checks", 0 < len(ev.REGISTRY) <= 5,
          "%d" % len(ev.REGISTRY))
    env = dict(os.environ)
    r = subprocess.run([PY, "scripts/run_check.py", "no_such_check"], cwd=ROOT,
                       capture_output=True, text=True, env=env)
    check("R2. unknown check_id is refused (rc 2)", r.returncode == 2, "rc=%s" % r.returncode)
    check("R3. ...and writes no record", not ev.read_records())
    r = subprocess.run([PY, "scripts/run_check.py", "guard_suite", "--cmd", "echo hi"],
                       cwd=ROOT, capture_output=True, text=True, env=env)
    check("R4. a caller-supplied command is refused (rc 2)", r.returncode == 2,
          "rc=%s" % r.returncode)

    # real end-to-end: CLI runs a real registered check, record validates
    r = subprocess.run([PY, "scripts/run_check.py", "control_events"], cwd=ROOT,
                       capture_output=True, text=True, env=env, timeout=600)
    rec = (ev.read_records() or [{}])[-1]
    check("R5. real check via CLI -> PASS record", r.returncode == 0
          and rec.get("status") == "PASS", "rc=%s" % r.returncode)
    check("R6. artefact retained and its hash matches",
          os.path.isfile(rec.get("output_path", "")) and
          ev._sha_file(rec["output_path"]) == rec.get("output_sha256"))
    check("R7. ...and that record validates", ev.validate("control_events") == "",
          ev.validate("control_events"))
    check("R8. artefact holds the suite's own summary, not a stub",
          "acceptance checks passed" in io.open(rec["output_path"], encoding="utf-8").read())

    # ------------------------------------------------------------------ run(): failing paths
    print("\n  [F] failing and unavailable suites")
    fx = os.path.join(TMP, "fx")
    os.makedirs(fx)
    io.open(os.path.join(fx, "ok.py"), "w").write("print('fine')\n")
    io.open(os.path.join(fx, "bad.py"), "w").write("import sys; print('broken'); sys.exit(1)\n")
    fake = {"t_ok": {"cmd": ["ok.py"], "covers": []},
            "t_bad": {"cmd": ["bad.py"], "covers": []},
            "t_gone": {"cmd": ["does_not_exist.py"], "covers": []}}
    reset_log()
    a = ev.run("t_ok", registry=fake, root=fx)
    b = ev.run("t_bad", registry=fake, root=fx)
    c = ev.run("t_gone", registry=fake, root=fx)
    check("F1. passing fixture -> PASS rc 0", a["status"] == "PASS" and a["exit_code"] == 0)
    check("F2. FAILING suite -> FAIL record, real exit code", b["status"] == "FAIL"
          and b["exit_code"] == 1, "rc=%s" % b["exit_code"])
    check("F3. UNAVAILABLE suite -> FAIL record, not silence", c["status"] == "FAIL"
          and c["exit_code"] != 0, "rc=%s" % c["exit_code"])
    check("F4. a fake-registry record can never satisfy a REAL check id",
          ev.validate("t_ok").startswith("INVALID"), ev.validate("t_ok")[:40])

    # ------------------------------------------------------------------ validate(): every rule
    print("\n  [V] validation rules, one at a time")
    cid = "guard_mutation"
    reset_log()
    check("V1. no record at all -> MISSING", ev.validate(cid).startswith("MISSING"),
          ev.validate(cid)[:40])
    reset_log(); forge_valid(cid)
    check("V2. well-formed record -> valid (positive control)", ev.validate(cid) == "",
          ev.validate(cid)[:40])
    reset_log(); rec = forge_valid(cid); os.remove(rec["output_path"])
    check("V3. artefact MISSING -> INVALID", ev.validate(cid).startswith("INVALID"),
          ev.validate(cid)[:40])
    reset_log(); rec = forge_valid(cid)
    io.open(rec["output_path"], "a").write("edited after the run\n")
    check("V4. artefact ALTERED -> INVALID", ev.validate(cid).startswith("INVALID"),
          ev.validate(cid)[:40])
    reset_log(); forge_valid(cid, inputs_sha256="0" * 64)
    check("V5. covered files changed since run -> STALE", ev.validate(cid).startswith("STALE"),
          ev.validate(cid)[:40])
    reset_log(); forge_valid(cid, command=["scripts/something_else.py"])
    check("V6. record ran a different command -> INVALID", ev.validate(cid).startswith("INVALID"),
          ev.validate(cid)[:40])
    reset_log(); forge_valid(cid, status="FAIL", exit_code=1)
    check("V7. failed run -> FAILED", ev.validate(cid).startswith("FAILED"),
          ev.validate(cid)[:40])
    reset_log(); forge_valid(cid); forge_valid(cid, status="FAIL", exit_code=1)
    check("V8. latest FAIL after an earlier PASS -> FAILED (latest wins)",
          ev.validate(cid).startswith("FAILED"), ev.validate(cid)[:40])

    # ------------------------------------------------------------------ pre-commit decide()
    print("\n  [P] pre-commit decision")
    calls = []

    def runner_ok(c):
        calls.append(c)
        return {"status": "PASS", "exit_code": 0}

    ok, lines = pc.decide(["README.md", "docs/x.md"], runner=runner_ok, validator=lambda c: "")
    check("P1. no control staged -> allowed, NOTHING rerun", ok and not lines and not calls)
    ok, lines = pc.decide(["scripts/batch_write_guard.py"], runner=runner_ok,
                          validator=lambda c: "")
    check("P2. guard staged -> its suites rerun, green -> allowed",
          ok and set(calls) >= {"guard_suite", "guard_mutation"}, ",".join(calls))
    calls.clear()
    ok, _ = pc.decide([".claude/settings.json"], runner=runner_ok, validator=lambda c: "")
    check("P3. .claude/settings.json staged -> guard_suite rerun (lstrip regression)",
          "guard_suite" in calls, ",".join(calls))
    ok, _ = pc.decide(["scripts/batch_write_guard.py"], runner=runner_ok,
                      validator=lambda c: "FAILED: x")
    check("P4. suite FAILS -> commit BLOCKED", ok is False)

    def runner_boom(c):
        raise OSError("python not found")
    ok, lines = pc.decide(["core/control_event.py"], runner=runner_boom,
                          validator=lambda c: "")
    check("P5. suite CANNOT RUN -> commit BLOCKED (fail closed)", ok is False
          and "COULD NOT RUN" in "\n".join(lines))
    ok, _ = pc.decide(["core/control_event.py"], runner=runner_ok,
                      validator=lambda c: "INVALID: output artefact is missing")
    check("P6. runner output MISSING -> commit BLOCKED", ok is False)

    # ------------------------------------------------------------------ closure gate
    print("\n  [G] closure gate")
    proof = {"classes": [{"id": "1", "verdict": "ENFORCED", "denominator": "1/1",
                          "closure_delta": 0, "fully_closed": True}],
             "second_pass": {"checklist": ["x"]},
             "hygiene": {"credentials_removed": True, "session_artefacts_removed": True,
                         "bundle_carveout_ok": True}}
    reset_log()
    rs = cg.evidence_reasons(proof, "2026-10-12")
    check("G1. post-cutoff full closure with NO evidence -> blocked for every check",
          len(rs) == len(ev.REGISTRY), "%d reasons" % len(rs))
    lying = dict(proof, checks={k: "PASS" for k in ev.REGISTRY})
    check("G2. agent-authored checks:PASS in the proof is IGNORED",
          len(cg.evidence_reasons(lying, "2026-10-12")) == len(ev.REGISTRY))
    check("G3. hunt closed before the cutoff is not retro-judged",
          cg.evidence_reasons(proof, "2026-10-05") == [])
    check("G4. grandfathered proof is untouched",
          cg.evidence_reasons({"grandfathered": True}, "2026-10-12") == [])
    no_full = json.loads(json.dumps(proof))
    no_full["classes"][0]["fully_closed"] = False
    check("G5. no class fully_closed -> no evidence demanded",
          cg.evidence_reasons(no_full, "2026-10-12") == [])
    for k in ev.REGISTRY:
        forge_valid(k)
    check("G6. all required evidence valid -> no evidence reasons",
          cg.evidence_reasons(proof, "2026-10-12") == [])

    # real gate, real subprocess, real matrix + proof files
    d = os.path.join(TMP, "cov")
    os.makedirs(d)
    io.open(os.path.join(d, "t_matrix.md"), "w", encoding="utf-8").write(
        "| closed | 2026-10-12 |\n\n**classes FULLY CLOSED: 1 / 1**\n")
    io.open(os.path.join(d, "t_closure.json"), "w", encoding="utf-8").write(json.dumps(proof))
    gate = lambda: subprocess.run([PY, "scripts/closure_gate.py", os.path.join(d, "t_matrix.md")],
                                  cwd=ROOT, capture_output=True, text=True, env=dict(os.environ))
    r = gate()
    check("G7. real gate: valid evidence -> rc 0", r.returncode == 0, "rc=%s" % r.returncode)
    reset_log()
    r = gate()
    check("G8. real gate: evidence MISSING -> rc 1, names the missing check",
          r.returncode == 1 and "MISSING" in r.stdout, "rc=%s" % r.returncode)
    forge_valid("guard_suite", status="FAIL", exit_code=1)
    r = gate()
    check("G9. real gate: a FAILED required suite -> rc 1", r.returncode == 1
          and "FAILED" in r.stdout, "rc=%s" % r.returncode)

    shutil.rmtree(TMP, ignore_errors=True)
    print("\n  NOT COVERED: forged records (see forge_valid - evidence is NOT tamper-proof);")
    print("  backdated matrix close dates; the live git pre-commit wiring, which is proven by")
    print("  committing this change, not by this harness.")
    bad = sum(1 for _, ok in RESULTS if not ok)
    print("\n  %d of %d acceptance checks passed" % (len(RESULTS) - bad, len(RESULTS)))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
