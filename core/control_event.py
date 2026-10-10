"""Durable event trail for the deterministic controls.

Why this exists, measured 2026-10-10: of four controls, only `scope_guard` wrote anything to
disk. `console_batch`, `closure_gate` and `prepush_scan` printed to stdout and exited. So every
claim that a gate blocked something was HUMAN-OBSERVED from terminal scrollback, and no metric
about control behaviour could be derived from an artefact. A control that enforces without
recording cannot be measured, and an unmeasurable control cannot be improved on evidence.

Two rules this module will not break:

  1. **A logging failure never changes a control's decision.** `emit()` cannot raise into the
     caller. On failure it prints CONTROL LOG WRITE FAILED to stderr and returns False, so the
     caller and the tests can see it, while the control's own verdict stands untouched. Making
     a gate fail closed because a disk write failed would block work for a reason unrelated to
     what the gate is for.
     ⚠️ Limitation, stated rather than hidden: when the write fails, stderr is the only signal
     and it is NOT durable. A failed write leaves no audit record by definition.

  2. **Nothing sensitive goes in the log.** The engine repo is public. `context` is a short
     sanitised label, never a URL, programme name, path, token, header or request body. The log
     itself lives under `workspace/`, which is gitignored.

Run identity: `JARVIS_RUN_ID` if set, otherwise a unique id generated once per PROCESS and
reused for every event that process emits. Deliberately not per-day - two sessions on one day
would be merged into one run, which is a knowingly wrong measurement.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import sys
import time
import uuid

LOG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "workspace", "control_events.jsonl")

DECISIONS = ("PASS", "BLOCK", "ERROR")

_RUN_ID = None
_VERSION_CACHE: dict = {}

# Shapes that must never reach the log even if a caller passes them by mistake. The log is the
# one artefact we WANT to keep forever, so it is the worst possible place for session material.
_FORBIDDEN = ("http://", "https://", "cookie", "authorization", "bearer ", "token=",
              "password", "secret", "api_key", "apikey")


def run_id() -> str:
    """Stable for the life of this process. Explicit env var wins so a whole hunt can share one."""
    global _RUN_ID
    if _RUN_ID is None:
        _RUN_ID = os.environ.get("JARVIS_RUN_ID") or ("p-" + uuid.uuid4().hex[:12])
    return _RUN_ID


def tool_version(path: str) -> str:
    """Short content hash of the tool file. Self-updating - a control that changes gets a new
    version without anyone remembering to bump a constant."""
    if path in _VERSION_CACHE:
        return _VERSION_CACHE[path]
    try:
        with open(path, "rb") as fh:
            v = hashlib.sha256(fh.read()).hexdigest()[:10]
    except OSError:
        v = "unknown"
    _VERSION_CACHE[path] = v
    return v


def _sanitise(ctx) -> str:
    """-> a short label safe to keep forever, or a redaction marker.

    Refuses rather than truncates: a truncated URL is still a URL.
    """
    if ctx is None:
        return ""
    s = str(ctx)
    low = s.lower()
    if any(f in low for f in _FORBIDDEN):
        return "<REDACTED: looked like session or target material>"
    s = os.path.basename(s.rstrip("/\\")) if ("/" in s or "\\" in s) else s
    return s[:80]


def emit(tool: str, decision: str, reason: str = "", rule_id: str = "",
         context=None, duration_ms: int = 0, test_mode: bool = False,
         tool_file: str = "", path: str = "") -> bool:
    """Append one event. -> True if durably written, False if the write failed.

    NEVER raises. The caller's decision is already made by the time this runs and must not
    depend on whether the disk cooperated.
    """
    if decision not in DECISIONS:
        decision = "ERROR"
        reason = ("invalid decision %r; " % decision) + reason

    rec = {
        "event_id": uuid.uuid4().hex[:16],
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + "Z",
        "run_id": run_id(),
        "tool": tool,
        "tool_version": tool_version(tool_file) if tool_file else "unset",
        "decision": decision,
        "rule_id": rule_id,
        "reason": _sanitise(reason)[:200],
        "duration_ms": int(duration_ms),
        "context": _sanitise(context),
        "test_mode": bool(test_mode),
    }
    # JARVIS_CONTROL_LOG lets a test redirect the trail without touching the real one.
    # Explicit `path` still wins, so a caller can be unambiguous.
    target = path or os.environ.get("JARVIS_CONTROL_LOG") or LOG_PATH
    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with io.open(target, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return True
    except Exception as exc:                       # noqa: BLE001 - must never propagate
        sys.stderr.write(
            "CONTROL LOG WRITE FAILED tool=%s decision=%s err=%s\n"
            "  the control's decision is UNCHANGED; this event is NOT durably recorded\n"
            % (tool, decision, str(exc)[:120]))
        return False


def read_events(path: str = "") -> list:
    """-> list of event dicts. Used by tests and by any later metric that must be derived from
    the artefact rather than from a narrative."""
    target = path or os.environ.get("JARVIS_CONTROL_LOG") or LOG_PATH
    out = []
    try:
        for ln in io.open(target, encoding="utf-8", errors="replace"):
            ln = ln.strip()
            if ln:
                try:
                    out.append(json.loads(ln))
                except ValueError:
                    pass
    except OSError:
        pass
    return out
