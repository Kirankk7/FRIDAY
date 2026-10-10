"""Machine-readable hypothesis ledger: the retrieval failure, given an owner.

WHY THIS EXISTS, measured 2026-10-10. Three times (2026-09-17, 2026-09-22, 2026-10-10) a probe
was built on the assumption that cookies authenticate a control-panel API. All three times the
contradicting evidence was ALREADY WRITTEN DOWN in the hunt's own notes. The 2026-09-22 entry is
verbatim: "The evidence to build it correctly was already in my own notes."

So the failure is not stubbornness and not ignorance. It is RETRIEVAL: nothing forced the lookup,
because the record lived in prose that only gets read when someone remembers to read it. Per the
enforcement-owner rule, a rule whose enforcement is "the assistant remembers" is not a rule. This
module turns those notes into a queryable artefact, and `scripts/batch_write_guard.py` turns the
query into a gate that runs whether or not anyone remembered.

THREE BOUNDARIES - each a claim this ledger does NOT support:

  * **A FALSIFIED state is not a permanent fact about the world.** It records that evidence
    contradicted the claim at a stated time, on a stated surface. Targets change. That is exactly
    why `reopen()` exists and why it logs rather than asking permission - the ledger must not
    become a reason to stop looking.
  * **The gate cannot judge evidence QUALITY, only its presence.** `reopen()` requires a
    non-trivial evidence string and records it verbatim. Whether that evidence is any good is a
    human judgement the ledger deliberately does not pretend to make. It makes the reopening
    VISIBLE and ATTRIBUTABLE; it does not make it correct.
  * **Patterns detect a TEXTUAL assumption, not a semantic one.** A batch that relies on cookie
    auth without ever typing the words will not match. Recall is unmeasured and the detector is a
    lower bound, so a clean pass means "no known-falsified assumption was spelled out", never
    "this batch is sound".

PRIVACY. Records carry the real header, endpoint and parameter names of live targets, which are
programme data. The ledger therefore lives at `data/hypothesis_ledger.jsonl`, which `data/*`
gitignores. This module is public and holds no target strings. A clone with no ledger CANNOT judge
a batch, and the guard denies rather than passing - the same fail-open defect already fixed once in
`gen_hunt_targets.py`, where a missing corpus reported CLEAN.
"""
from __future__ import annotations

import io
import json
import os
import re
import time
import uuid

LEDGER_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "hypothesis_ledger.jsonl")

# A state is the ledger's verdict on a claim. Deliberately NOT the hunt verdict vocabulary -
# these describe a belief we hold, not a control a target enforces, and conflating the two
# vocabularies is how "untestable" became "safe" the first time.
STATES = ("OPEN", "FALSIFIED", "CONFIRMED", "REOPENED")

# Reopening on a shrug is the obvious way to render this whole gate decorative, so the evidence
# string has a floor and a stoplist. Neither measures quality; both stop a reflex.
MIN_EVIDENCE_CHARS = 25
_EVIDENCE_STOPLIST = (
    "new evidence", "it changed", "trust me", "because i said so", "i think it works",
    "probably fine", "n/a", "none", "test", "retry", "it should work",
)


def ledger_path(path: str = "") -> str:
    """Explicit arg wins, then JARVIS_HYPOTHESIS_LEDGER, then the default. The env var exists so
    tests never touch the real ledger."""
    return path or os.environ.get("JARVIS_HYPOTHESIS_LEDGER") or LEDGER_PATH


def exists(path: str = "") -> bool:
    return os.path.isfile(ledger_path(path))


def read_all(path: str = "") -> list:
    """-> every record in file order, malformed lines skipped.

    Append-only by design: a reopening does not edit the FALSIFIED record, it appends after it.
    The history of what we believed and when is the point, so nothing is ever rewritten.
    """
    out = []
    try:
        for ln in io.open(ledger_path(path), encoding="utf-8", errors="replace"):
            ln = ln.strip()
            if not ln or ln.startswith("#"):
                continue
            try:
                rec = json.loads(ln)
            except ValueError:
                continue
            if isinstance(rec, dict) and rec.get("id"):
                out.append(rec)
    except OSError:
        return []
    return out


def latest(path: str = "") -> dict:
    """-> {id: most recent record for that id}. Last line wins, so append = supersede."""
    cur = {}
    for rec in read_all(path):
        cur[rec["id"]] = rec
    return cur


def falsified(path: str = "") -> list:
    """-> records whose CURRENT state is FALSIFIED. A reopened id is absent from this list."""
    return [r for r in latest(path).values() if r.get("state") == "FALSIFIED"]


def compiled_detectors(path: str = "") -> list:
    """-> [(record, compiled_regex, raw_pattern)] for every currently-FALSIFIED record.

    A pattern that will not compile is NOT silently dropped: it is returned with regex None so the
    caller can report an unusable detector. Silently skipping it would mean a ledger entry that
    looks like coverage and enforces nothing.
    """
    out = []
    for rec in falsified(path):
        pats = rec.get("detect") or []
        if isinstance(pats, str):
            pats = [pats]
        for p in pats:
            try:
                out.append((rec, re.compile(p, re.I), p))
            except re.error:
                out.append((rec, None, p))
    return out


def match(text: str, path: str = "") -> list:
    """-> [(record, pattern)] for each currently-FALSIFIED assumption spelled out in `text`.

    Empty list means no KNOWN falsified assumption was found in the text. It does not mean the
    text is sound; see the recall boundary in this module's docstring.
    """
    hits = []
    if not text:
        return hits
    for rec, rx, raw in compiled_detectors(path):
        if rx is None:
            continue
        if rx.search(text):
            hits.append((rec, raw))
    return hits


def bad_detectors(path: str = "") -> list:
    """-> [(id, pattern)] for detectors that do not compile. Surfaced, never swallowed."""
    return [(rec["id"], raw) for rec, rx, raw in compiled_detectors(path) if rx is None]


def evidence_is_substantive(evidence: str) -> tuple:
    """-> (ok, reason). Presence and effort only.

    This function CANNOT tell a good reason from a confident one. It refuses the empty gesture so
    that reopening costs a sentence someone has to stand behind, and that is the whole claim.
    """
    e = (evidence or "").strip()
    if len(e) < MIN_EVIDENCE_CHARS:
        return False, ("evidence is %d chars; a reopening needs at least %d naming what was "
                       "observed" % (len(e), MIN_EVIDENCE_CHARS))
    if e.lower() in _EVIDENCE_STOPLIST:
        return False, "evidence is a placeholder phrase, not an observation"
    return True, ""


def append(rec: dict, path: str = "") -> bool:
    """Append one record. -> True if durably written. Never raises."""
    target = ledger_path(path)
    rec = dict(rec)
    rec.setdefault("event_id", uuid.uuid4().hex[:16])
    rec.setdefault("ts", time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + "Z")
    if rec.get("state") not in STATES:
        return False
    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with io.open(target, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return True
    except OSError:
        return False


def reopen(hid: str, evidence: str, path: str = "") -> tuple:
    """Move a FALSIFIED id back to REOPENED, on recorded evidence. -> (ok, message).

    Refuses an id that is not currently FALSIFIED: reopening something already open would create a
    record implying a state change that never happened.
    """
    cur = latest(path).get(hid)
    if cur is None:
        return False, "unknown hypothesis id %r - nothing to reopen" % hid
    if cur.get("state") != "FALSIFIED":
        return False, ("%s is currently %s, not FALSIFIED - there is nothing to reopen"
                       % (hid, cur.get("state")))
    ok, why = evidence_is_substantive(evidence)
    if not ok:
        return False, "refused: " + why
    rec = {
        "id": hid,
        "claim": cur.get("claim", ""),
        "state": "REOPENED",
        "evidence": evidence.strip(),
        "detect": cur.get("detect") or [],
        "supersedes": cur.get("event_id", ""),
        "reopened_from": "FALSIFIED",
    }
    if not append(rec, path):
        return False, "ledger write FAILED - the reopening is not recorded, so it does not count"
    return True, "%s REOPENED; prior FALSIFIED record %s left intact" % (
        hid, cur.get("event_id", "(no id)"))
