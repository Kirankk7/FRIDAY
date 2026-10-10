"""Execution evidence for required checks: a run record the agent does not write by hand.

WHY. A closure proof where the agent types "command, exit code, PASS" is a declaration dressed as
evidence. So the only accepted proof that a check ran is a record written by `run()` here, which
executes a FIXED command from REGISTRY itself, keeps the full output as an artefact, and stores
the artefact's hash. The closure gate and the pre-commit hook read these records and IGNORE any
check status written into a proof.

A control event and a check record are different obligations, in different files, from different
writers: `control_events.jsonl` says a control decided something; `check_runs.jsonl` says a test
suite ran and how it ended. Neither is accepted as the other.

WHAT THIS IS NOT. Not tamper-proof. Records are plain JSONL on a local disk; someone determined
could forge a record and a matching artefact. The checks below - command must equal the registry
command, artefact hash must match, covered files must be unchanged since the run - stop accidental
and lazy fabrication by a forgetful operator, which is the stated threat model. They are not
cryptographic proof.

STALENESS, made concrete: each record stores a hash of the files its check covers. If any covered
file has changed since the run, the record is STALE. This is also the efficiency rule - an
unchanged control keeps its evidence, so nothing reruns without a reason.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
import time
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# At most five, by agreement. Each id maps to ONE fixed command; nothing on the command line or in
# a proof can change what a check id runs. `covers` = the files whose change makes a record stale
# and makes the pre-commit hook rerun the check.
REGISTRY = {
    "control_events": {
        "cmd": ["scripts/control_event_check.py"],
        "covers": ["core/control_event.py", "scripts/control_event_check.py",
                   "scripts/closure_gate.py", "scripts/console_batch.py",
                   "scripts/prepush_scan.py"],
        "timeout": 300,
    },
    "guard_suite": {
        "cmd": ["scripts/hypothesis_check.py"],
        "covers": ["scripts/batch_write_guard.py", "core/hypothesis_ledger.py",
                   "scripts/experiment_preflight.py", "scripts/hypothesis_check.py",
                   ".claude/settings.json", "core/control_event.py"],
        "timeout": 300,
    },
    "guard_mutation": {
        "cmd": ["scripts/mutation_check.py"],
        "covers": ["scripts/batch_write_guard.py", "scripts/hypothesis_check.py",
                   "scripts/mutation_check.py"],
        "timeout": 900,
    },
    "check_evidence": {
        "cmd": ["scripts/check_runner_check.py"],
        "covers": ["core/check_evidence.py", "scripts/run_check.py",
                   "scripts/precommit_checks.py", "scripts/check_runner_check.py",
                   "scripts/closure_gate.py"],
        "timeout": 300,
    },
}
assert len(REGISTRY) <= 5, "the required-check list is capped at five by agreement"

# Hunts whose matrix closes on or after this date must carry valid evidence for every required
# check before any class may be fully_closed. Earlier hunts closed before this mechanism existed;
# applying TODAY's evidence to them would certify nothing about how they were closed.
EVIDENCE_REQUIRED_FROM = "2026-10-11"


def log_path() -> str:
    return os.environ.get("JARVIS_CHECK_LOG") or os.path.join(ROOT, "workspace",
                                                              "check_runs.jsonl")


def artefact_dir() -> str:
    return os.environ.get("JARVIS_CHECK_DIR") or os.path.join(ROOT, "workspace", "check_runs")


def _sha_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def inputs_sha(covers: list, root: str = ROOT) -> str:
    """Hash of every covered file's path and bytes. A missing file is hashed as a marker, so a
    deleted control changes the hash instead of silently dropping out of it."""
    h = hashlib.sha256()
    for rel in sorted(covers):
        h.update(rel.encode("utf-8") + b"\0")
        p = os.path.join(root, rel)
        try:
            with open(p, "rb") as fh:
                h.update(fh.read())
        except OSError:
            h.update(b"<MISSING>")
        h.update(b"\0")
    return h.hexdigest()


def _git_head(root: str) -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True,
                              text=True, timeout=10).stdout.strip()[:12]
    except Exception:                                   # noqa: BLE001
        return ""


def read_records() -> list:
    out = []
    try:
        for ln in io.open(log_path(), encoding="utf-8", errors="replace"):
            ln = ln.strip()
            if ln:
                try:
                    out.append(json.loads(ln))
                except ValueError:
                    pass
    except OSError:
        pass
    return out


def run(check_id: str, registry: dict = None, root: str = ROOT) -> dict:
    """Execute one registered check and append its record. -> the record.

    Library callers may pass a `registry` (tests do, to exercise failing and unavailable checks).
    The CLI never does, and `validate()` always compares against the REAL registry - so a record
    produced from any other command can never satisfy a required check.
    """
    reg = registry if registry is not None else REGISTRY
    if check_id not in reg:
        raise KeyError("unknown check_id %r" % check_id)
    spec = reg[check_id]
    cmd = [sys.executable] + list(spec["cmd"])
    started = time.time()
    try:
        r = subprocess.run(cmd, cwd=root, capture_output=True, text=True,
                           timeout=spec.get("timeout", 300))
        rc, output = r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        rc, output = -1, "TIMEOUT after %ss" % spec.get("timeout", 300)
    except OSError as exc:
        rc, output = -1, "COULD NOT START: %s" % exc

    os.makedirs(artefact_dir(), exist_ok=True)
    rid = uuid.uuid4().hex[:12]
    art = os.path.join(artefact_dir(), "%s-%s.log" % (check_id, rid))
    with io.open(art, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(output)
    rec = {
        "record_id": rid,
        "check_id": check_id,
        "command": list(spec["cmd"]),
        "exit_code": rc,
        "status": "PASS" if rc == 0 else "FAIL",
        "output_path": art,
        "output_sha256": _sha_file(art),
        "inputs_sha256": inputs_sha(spec["covers"], root),
        "git_head": _git_head(root),
        "duration_s": round(time.time() - started, 1),
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    os.makedirs(os.path.dirname(log_path()), exist_ok=True)
    with io.open(log_path(), "a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(rec) + "\n")
    return rec


def validate(check_id: str, root: str = ROOT) -> str:
    """-> "" if the LATEST record for this check is valid evidence, else the reason it is not.

    Always judged against the real REGISTRY. Latest record wins: a FAIL after an earlier PASS
    means the check is currently failing.
    """
    spec = REGISTRY.get(check_id)
    if spec is None:
        return "INVALID: %s is not a registered check" % check_id
    recs = [r for r in read_records() if r.get("check_id") == check_id]
    if not recs:
        return "MISSING: %s has never been run through run_check" % check_id
    r = recs[-1]
    if r.get("command") != spec["cmd"]:
        return "INVALID: %s record ran %r, registry says %r" % (check_id, r.get("command"),
                                                               spec["cmd"])
    if r.get("status") != "PASS" or r.get("exit_code") != 0:
        return "FAILED: %s last run exit_code=%s" % (check_id, r.get("exit_code"))
    art = r.get("output_path") or ""
    if not os.path.isfile(art):
        return "INVALID: %s output artefact is missing" % check_id
    if _sha_file(art) != r.get("output_sha256"):
        return "INVALID: %s output artefact does not match its recorded hash" % check_id
    if inputs_sha(spec["covers"], root) != r.get("inputs_sha256"):
        return "STALE: files covered by %s changed after it last ran" % check_id
    return ""


def validate_all(root: str = ROOT) -> dict:
    """-> {check_id: reason} for every required check that is NOT valid. Empty = all valid."""
    return {cid: why for cid in REGISTRY for why in [validate(cid, root)] if why}


def affected_by(paths: list) -> list:
    """-> check ids whose covered files intersect `paths` (repo-relative, any separator)."""
    # Strip a leading "./" PREFIX only. str.lstrip("./") strips characters and would turn
    # ".claude/settings.json" into "claude/settings.json", silently dropping the hook config.
    norm = set()
    for p in paths:
        p = p.replace("\\", "/")
        norm.add(p[2:] if p.startswith("./") else p)
    return [cid for cid, spec in REGISTRY.items() if norm & set(spec["covers"])]
