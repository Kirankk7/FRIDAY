#!/usr/bin/env python3
"""PreToolUse guard: CONSOLE_BATCH_WRITE_REQUIRES_PREFLIGHT.

Runs as a Claude Code `PreToolUse` hook on Write/Edit. Reads the tool call on stdin, and for a
console-batch `.js` write decides ALLOW or DENY before the file exists - therefore before any
paste can be generated from it, which is the only point at which a block saves operator effort.

TWO INDEPENDENT CONDITIONS, because they fail in different ways:

  1. **A current preflight token keyed to this exact content.** Absent => DENY. This catches the
     real historical failure, which was not a wrong answer but an absent question: a batch written
     with nothing looked up at all.
  2. **No currently-FALSIFIED assumption spelled out in the content.** Matched => DENY, even with
     a valid token. Condition 1 can be satisfied mechanically by anyone willing to run a command;
     this one cannot be satisfied by declaring the batch clean.

FAIL-CLOSED, deliberately. No ledger, an unreadable ledger, an uncompilable detector or a crash in
this script all DENY a batch write. A guard that passes when its instrument is broken issues a
negative it has not earned - the same defect already fixed twice in this repo (`gen_hunt_targets`
reported CLEAN on a missing corpus; an oracle that fails its positive control cannot clear a
field). The hook is configured with `onFailure: "block"` so that a crash here blocks too, rather
than quietly reverting to no guard at all.

WHAT THIS DOES NOT DO - stated here because the gap is the honest part:

  * It guards the **file-write path only**. A batch typed straight into a reply never reaches this
    script. That bypass is real, it is not closed by this build, and `--selftest` demonstrates it
    rather than describing it. See the measurement note in `docs/RULE_ENFORCEMENT.md`.
  * A DENY is **a refused write, not a prevented failure.** Whether the batch would have wasted an
    operator action is a separate claim needing the batch and the surface.
  * Detection is **textual**. An assumption held but never typed does not match, so a clean pass
    means "no known-falsified assumption was written down here", never "this batch is sound".

Protocol: exit 0 and print nothing to let the call through - never returns `permissionDecision:
"allow"`, which would bypass the operator's own permission prompts on top of answering a question
it was not asked. On a refusal it prints the documented deny JSON AND exits 2, so the block lands
whether the host reads the JSON or the exit code.
"""
from __future__ import annotations

import hashlib
import json
import os
import posixpath
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core import control_event as ce          # noqa: E402
from core import hypothesis_ledger as hl      # noqa: E402

TOOL = "batch_write_guard"
RULE = "CONSOLE_BATCH_WRITE_REQUIRES_PREFLIGHT"
TOKEN_DIR = (os.environ.get("JARVIS_PREFLIGHT_TOKEN_DIR")
             or os.path.join(ROOT, "workspace", "preflight_tokens"))
TOKEN_TTL_SECONDS = 30 * 60


# --------------------------------------------------------------------------- scope
def in_scope(file_path: str) -> bool:
    """-> True if this write is a console batch.

    Narrow and literal on purpose. A guard that fires on every `.js` file in the repo would be
    disabled within a day, and a disabled control measures nothing.
    """
    if not file_path:
        return False
    p = file_path.replace("\\", "/")
    if not p.lower().endswith(".js"):
        return False
    # NORMALISE BEFORE MATCHING. Substring matching on a raw path was wrong three ways, all
    # found by driving a spelling matrix through the shipped function: `workspace//scratch/`
    # and `workspace/./scratch/` both slipped THROUGH the guard, and
    # `workspace/scratch/../../core/x.js` was guarded although it resolves into the engine.
    # posixpath (not os.path) on purpose: separators are already forward slashes here, and
    # os.path.normpath would re-introduce backslashes on Windows.
    p = posixpath.normpath(p)
    base = os.path.basename(p).lower()
    parent = os.path.basename(os.path.dirname(p)).lower()
    if ("batch" in base) or ("console" in base) or (parent == "console"):
        return True
    # Any .js under the hunt scratch tree. Found by probing, NOT by the suite: a batch renamed
    # from probe_batch.js to probe.js was completely unguarded, which reduced the whole gate to
    # a naming convention. Scratch is where batches actually live (standing rule: hunt artefacts
    # go to workspace/scratch, never the Desktop), so that is the directory that must be
    # covered - rather than every .js in the repo, because a guard that fires on engine code
    # gets switched off within a day and then measures nothing at all.
    return "/workspace/scratch/" in ("/" + p.lower().lstrip("/"))


def payload_text(tool_input: dict) -> str:
    """Every field of a Write or Edit that can carry batch source, concatenated.

    Edit does not use `content`; it uses `new_string`. Reading only `content` would leave the
    Edit path unguarded while appearing to cover both tools.
    """
    parts = []
    for key in ("content", "new_string"):
        v = tool_input.get(key)
        if isinstance(v, str):
            parts.append(v)
    return "\n".join(parts)


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:32]


# --------------------------------------------------------------------------- tokens
def token_file(h: str) -> str:
    return os.path.join(TOKEN_DIR, h + ".json")


def read_token(h: str) -> tuple:
    """-> (token_dict_or_None, reason). Expiry is checked here, not trusted from the file."""
    fp = token_file(h)
    if not os.path.isfile(fp):
        return None, "no preflight token for this exact batch content"
    try:
        with open(fp, encoding="utf-8") as fh:
            tok = json.load(fh)
    except (OSError, ValueError) as exc:
        return None, "preflight token unreadable (%s)" % str(exc)[:60]
    age = time.time() - float(tok.get("issued_epoch") or 0)
    if age > TOKEN_TTL_SECONDS:
        return None, ("preflight token expired %d min ago; re-run the preflight"
                      % int((age - TOKEN_TTL_SECONDS) / 60))
    if tok.get("content_hash") != h:
        return None, "token content_hash does not match this batch"
    return tok, ""


def consume_token(h: str) -> bool:
    """One-shot. A token that survived its write could authorise a second, different paste."""
    try:
        os.remove(token_file(h))
        return True
    except OSError:
        return False


# --------------------------------------------------------------------------- decision
def decide(tool_name: str, tool_input: dict) -> tuple:
    """-> (decision, log_reason, rule_id, operator_detail).

    `log_reason` is short and carries NO target strings, because it goes to a durable log.
    `operator_detail` may quote the ledger and reaches only this session's deny message.
    """
    fp = tool_input.get("file_path") or ""
    if not in_scope(fp):
        return "PASS", "not a console batch write", "out_of_scope", ""

    text = payload_text(tool_input)
    if not text.strip():
        return "PASS", "no batch source in payload", "empty_payload", ""

    # instrument integrity first - a broken detector must never read as a clean batch
    if not hl.exists():
        return ("BLOCK",
                "no hypothesis ledger at data/hypothesis_ledger.jsonl, so no assumption in this "
                "batch can be checked; seed the ledger before writing console batches",
                "ledger_absent", "")
    bad = hl.bad_detectors()
    if bad:
        return ("BLOCK",
                "ledger has %d detector(s) that do not compile (%s); the instrument is unusable "
                "and cannot issue a pass" % (len(bad), ", ".join(i for i, _ in bad)),
                "detector_unusable", "")

    hits = hl.match(text)
    if hits:
        rec, pat = hits[0]
        # TWO reasons, deliberately. The claim and the correction name the target's own header
        # and endpoint, so they are programme data, and the durable log's sanitiser correctly
        # redacts them. Building the LOGGED reason out of that text made the single most
        # valuable event in the trail read "<REDACTED: looked like session or target material>"
        # and carry no attribution whatsoever - found by probing the real ledger, not by the
        # suite. So: a short target-free reason for the log, and the full detail only in the
        # deny message, which reaches this session and is never written to a file we keep.
        return ("BLOCK",
                "batch asserts %s, currently FALSIFIED" % rec["id"],
                "falsified_assumption",
                "batch asserts %s, recorded FALSIFIED: %s. Corrected finding: %s. Supply new "
                "evidence via experiment_preflight.py --reopen %s if the target has changed."
                % (rec["id"], rec.get("claim", "")[:90], rec.get("corrected_to", "")[:90],
                   rec["id"]))

    h = content_hash(text)
    tok, why = read_token(h)
    if tok is None:
        return ("BLOCK",
                "%s; run: python scripts/experiment_preflight.py --batch-file <draft> --declare "
                "<HYP-IDS>  (the preflight is what forces the lookup this gate exists for)" % why,
                "no_preflight_token", "")

    consume_token(h)
    return ("PASS", "preflight token valid and consumed; no falsified assumption matched",
            "cleared", "")


def emit(decision: str, reason: str, rule_id: str, started: float, ctx: str) -> None:
    ce.emit(TOOL, decision, reason=reason, rule_id=rule_id, context=ctx,
            duration_ms=int((time.time() - started) * 1000),
            tool_file=os.path.abspath(__file__))


def main() -> int:
    started = time.time()
    raw = sys.stdin.read()
    try:
        call = json.loads(raw) if raw.strip() else {}
    except ValueError:
        # Unparseable hook input is an instrument failure, not an all-clear.
        emit("ERROR", "hook input was not valid JSON", "bad_hook_input", started, "stdin")
        sys.stdout.write(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    "%s: hook input was not valid JSON, so the write could not be judged "
                    "(fail-closed)." % RULE)}}) + "\n")
        return 2

    tool_name = call.get("tool_name") or ""
    tool_input = call.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        tool_input = {}

    decision, reason, rule_id, detail = decide(tool_name, tool_input)
    ctx = os.path.basename((tool_input.get("file_path") or "").replace("\\", "/")) or tool_name

    # Events are written for in-scope calls only. Logging every unrelated Write would bury the
    # signal and make the trail's own counts meaningless.
    if rule_id != "out_of_scope":
        emit(decision, reason, rule_id, started, ctx)

    if decision == "BLOCK":
        sys.stdout.write(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "%s: %s" % (RULE, detail or reason)}}) + "\n")
        sys.stderr.write("%s DENIED %s: %s\n" % (RULE, ctx, detail or reason))
        return 2
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:                   # noqa: BLE001 - a crash must block, not pass
        sys.stdout.write(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    "%s: the guard itself crashed (%s), so this write was not judged "
                    "(fail-closed)." % (RULE, str(exc)[:120]))}}) + "\n")
        sys.stderr.write("batch_write_guard CRASHED, denying: %s\n" % str(exc)[:200])
        sys.exit(2)
