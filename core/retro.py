"""core/retro.py — backward memory: Hunt Snapshots + RetroactiveAnalyzer (Cyber-VNext).

The playbook had FORWARD memory only — a technique learned from today's writeups can apply to a hunt
already CLOSED, and we'd never know. This adds the backward link:

  save_snapshot(...)  -> a small semantic record per completed hunt (target class / surfaces / per-class
                         verdicts / program scope-status), stored LOCAL + gitignored (program names +
                         surfaces are disclosure-sensitive).
  check(triggers, ...) -> RetroactiveAnalyzer: a new technique's triggers vs every past snapshot ->
                          NO_MATCH / REVIEW / REOPEN_CANDIDATE. READ-ONLY. Executes NOTHING.

SAFETY (the keystone): a retro-lead is "a past hunt worth REVIEWING", NEVER "attack the old target".
Closed / parked / out-of-scope programs -> retest_authorized=False: the knowledge carries forward, no
retest is ever implied. This is what stops the backward layer from encouraging unauthorized testing.
"""
import os
import json
import re

_STORE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "hunt_snapshots.json")

# scope-status -> may we (in principle) do a minimal safe retest? Only a live, still-in-scope program.
_ACTIVE = {"active", "in-scope", "in_scope", "open", "live"}


def _tok(s: str) -> set:
    return {t for t in re.split(r"[^a-z0-9]+", (s or "").lower()) if len(t) >= 3}


def _load() -> list:
    try:
        with open(_STORE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save(rows: list):
    os.makedirs(os.path.dirname(_STORE), exist_ok=True)
    with open(_STORE, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)


def retest_authorized(scope_status: str) -> bool:
    return (scope_status or "").strip().lower() in _ACTIVE


def save_snapshot(program: str, surfaces, classes: dict | None = None, tech=(), auth=(),
                  target_class: str = "", scope_status: str = "active", hunt: str = "") -> dict:
    """Persist a semantic Hunt Snapshot (local/gitignored). `classes` = {class_name: verdict}.

    surfaces = the semantic attack-surface tags the hunt exposed (e.g. notification, invitation, upload,
    tenant_id, graphql, dashboard). Dedup on program (latest wins).
    """
    if not program:
        return {"success": False, "message": "program required"}
    snap = {"program": program, "hunt": hunt, "target_class": target_class,
            "tech": sorted(set(tech)), "auth": sorted(set(auth)),
            "surfaces": sorted({s.lower() for s in surfaces}),
            "classes": {k: (v or "UNKNOWN").upper() for k, v in (classes or {}).items()},
            "scope_status": scope_status, "retest_authorized": retest_authorized(scope_status)}
    rows = [r for r in _load() if r.get("program") != program]
    rows.append(snap)
    _save(rows)
    return {"success": True, "message": f"snapshot saved: {program} ({len(snap['surfaces'])} surfaces, "
            f"{len(snap['classes'])} classes, retest_authorized={snap['retest_authorized']})"}


def snapshot_from(program, session, app_map: dict | None = None, scope_status="active",
                  extra_surfaces=(), tech=(), auth=(), hunt="") -> dict:
    """Convenience: derive a snapshot from a HuntSession + app_mapper output (the auto-at-complete path)."""
    classes = {n: (v or "UNKNOWN") for n, v in getattr(session, "verdicts", {}).items()}
    surfaces = set(extra_surfaces)
    for d in (app_map or {}).get("ids", []):
        surfaces.add(d.get("role", ""))
        surfaces |= _tok(d.get("name", ""))
    surfaces = {s for s in surfaces if s}
    return save_snapshot(program, surfaces, classes, tech=tech, auth=auth,
                         scope_status=scope_status, hunt=hunt)


def check(triggers, lane: str = "", min_overlap: int = 2) -> list:
    """RetroactiveAnalyzer (read-only): a new technique's triggers vs past snapshots.

    triggers = keywords from the technique's `tell`/triggers. lane = the class it belongs to (e.g. 'BOLA',
    'BAC', 'SSRF') used to look up whether that class was tested in the old hunt.
    Returns one row per matching snapshot: state NO_MATCH is omitted; REVIEW / REOPEN_CANDIDATE surfaced.
    """
    tt = set()
    for t in (triggers if isinstance(triggers, (list, set, tuple)) else [triggers]):
        tt |= _tok(t)
    lane_tok = _tok(lane)
    out = []
    for snap in _load():
        surf = set()
        for s in snap.get("surfaces", []):
            surf |= _tok(s)                                  # tokenize: 'organization_id' -> {organization, id}
        matched = sorted(tt & surf)
        if len(matched) < min_overlap:
            continue                                        # NO_MATCH (omitted)
        # find the class verdict for this lane
        verdict = None
        for cname, v in snap.get("classes", {}).items():
            if lane_tok and (lane_tok & _tok(cname)):
                verdict = v
                break
        if verdict == "CONFIRMED":
            continue                                        # already found there; nothing to reopen
        # PRECISION (GPT): require multiple signals, not surface-tokens alone, or we recreate hoarding
        # retroactively. signals = surface-overlap + lane-relevance. lane_found = the lane maps to a real
        # class in this snapshot (strong tie). Weak (2 tokens, no lane tie) is dropped unless a strong
        # (>=3) surface match stands on its own.
        lane_found = verdict is not None
        signals = len(matched) + (1 if lane_found else 0)
        if not lane_found and len(matched) < 3:
            continue                                        # surface-only + weak = NO_MATCH (noise gate)
        # tested-but-maybe-wrong-variant = REOPEN (rarer); unknown/untested-but-relevant = REVIEW
        if verdict in ("ENFORCED", "RULED_OUT", "NA"):
            state = "REOPEN_CANDIDATE"
            why = f"lane {lane} was {verdict} — this technique variant may not have been tested"
        else:
            state = "REVIEW"
            why = f"surface present; lane {lane or '?'} test-status = {verdict or 'UNKNOWN'}"
        out.append({"program": snap["program"], "hunt": snap.get("hunt", ""), "state": state,
                    "signals": signals, "matched_surfaces": matched, "lane_verdict": verdict,
                    "retest_authorized": snap.get("retest_authorized", False),
                    "scope_status": snap.get("scope_status", ""), "why": why})
    # REOPEN_CANDIDATE first, then REVIEW; authorized retests first within each
    out.sort(key=lambda r: (0 if r["state"] == "REOPEN_CANDIDATE" else 1, not r["retest_authorized"]))
    return out
