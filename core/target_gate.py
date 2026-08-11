"""
Target-softness gate — pre-hunt decision AID (earned by a run of consecutive
fortresses: reachable mature SaaS with hardened authz, thorough sweeps, 0 findings).

This is the ONE place discipline was missing while everything else in the engine
sits at ~9/10: target CHOICE was vibes. The gate scores a target's *softness*
(likelihood bugs still live there) from cheap signals and returns an advisory
verdict. It NEVER refuses a hunt on its own — a red flag means "you need a WRITTEN
reason to hunt this fortress", and `record_decision()` logs that reason so an
override stays judgment, not vibes-with-a-hat.

Sits ABOVE the frozen engine (mapper/oracle/hunt_loop) — touches no core module.
Deterministic, local JSON log, no deps.

Doctrine: [[cyber_engine_vnext]] convergence 2026-08-12, [[target-sourcing]]
(reachability-from-geo FIRST, then crowding), [[phase-shift-hunt-not-build]].
"""

import os
import json
import datetime
import threading

_LOG = os.path.join("data", "target_decisions.json")   # gitignored; the override audit trail
_lock = threading.Lock()

# Verdicts
HUNT = "HUNT"                          # soft enough — go
NEED_REASON = "NEED_WRITTEN_REASON"    # fortress-ish — allowed, but log why
DEPRIORITIZE = "DEPRIORITIZE"          # crowded/hardened/unreachable — skip unless strong reason

# Score bands (0-100)
_HUNT_AT = 62
_REASON_AT = 45

# Tech-surface markers that make a target richer (Wesley B2B profile: roles/tenants/workflows)
_RICH_SURFACE = {
    "multi_tenant", "tenant", "roles", "rbac", "workflow", "graphql",
    "file_upload", "payments", "billing", "api", "admin", "org", "sso", "webhook",
}


def score(signals: dict) -> dict:
    """
    Score a target's softness from cheap pre-hunt signals. Returns
    {score, verdict, rationale[], reachable}. Advisory only — see record_decision().

    signals (all optional, cautious defaults):
      geo_reachable      bool  reachable from your geo (HARD gate: False -> DEPRIORITIZE)
      report_count       int   resolved/total reports (crowding proxy)
      program_age_years  float older mature = more picked-over
      source_available   bool  OSS / readable source (our PROVEN win-lane)
      self_hostable      bool  can stand up a local instance
      recent_major_release bool fresh code = fresh bugs
      heavily_hunted     bool  explicit fortress flag
      tech_surface       list/str  markers (see _RICH_SURFACE)
    """
    s = signals or {}
    pts = 50.0
    why = []

    def adj(d, reason):
        nonlocal pts
        pts += d
        why.append(("%+d" % d, reason))

    # HARD gate first: unreachable = trap (target-sourcing refined lesson).
    reachable = s.get("geo_reachable", True)
    if reachable is False:
        why.append(("gate", "UNREACHABLE from your geo -> cannot test (0-reports can be a trap, not a gift)"))
        return {"score": 0, "verdict": DEPRIORITIZE, "rationale": why, "reachable": False}

    # Source / self-host = our actual bug-landing lane.
    if s.get("source_available"):     adj(+18, "source available (our proven win-lane: read code -> find sink/guard-gap)")
    if s.get("self_hostable"):        adj(+12, "self-hostable (local instance = unlimited safe testing)")
    if s.get("recent_major_release"): adj(+10, "recent major release (fresh code = fresh bugs)")

    # Crowding (report volume) — the fortress proxy.
    rc = s.get("report_count")
    if isinstance(rc, (int, float)):
        if rc < 20:      adj(+12, "very few reports (<20) = under-audited")
        elif rc < 100:   adj(+4,  "modest report volume (<100)")
        elif rc < 500:   adj(0,   "moderate report volume (100-499)")
        elif rc < 1000:  adj(-15, "high report volume (500-999) = heavily hunted")
        else:            adj(-22, "very high report volume (>=1000) = picked clean")

    # Maturity age (mild).
    age = s.get("program_age_years")
    if isinstance(age, (int, float)):
        if age < 1:   adj(+8, "young program (<1yr) = surface still settling")
        elif age > 5: adj(-8, "old program (>5yr) = mature, most surface picked over")

    # Explicit fortress flag.
    if s.get("heavily_hunted"):       adj(-20, "flagged heavily-hunted / hardened team")

    # Surface richness (B2B roles/tenants/workflows = where logic+authz bugs live).
    surf = s.get("tech_surface") or []
    if isinstance(surf, str):
        surf = [x.strip().lower() for x in surf.replace(",", " ").split()]
    rich = sorted({x for x in (m.lower() for m in surf) if x in _RICH_SURFACE})
    if rich:
        bonus = min(15, 3 * len(rich))
        adj(+bonus, "rich attack surface: " + ", ".join(rich))

    pts = max(0.0, min(100.0, pts))
    if pts >= _HUNT_AT:     verdict = HUNT
    elif pts >= _REASON_AT: verdict = NEED_REASON
    else:                   verdict = DEPRIORITIZE
    return {"score": round(pts, 1), "verdict": verdict, "rationale": why, "reachable": True}


def explain(result: dict) -> str:
    """One-line-per-signal human summary of a score() result."""
    head = "%s  score=%s" % (result["verdict"], result["score"])
    lines = ["  %-5s %s" % (tag, reason) for tag, reason in result.get("rationale", [])]
    tail = ""
    if result["verdict"] == NEED_REASON:
        tail = "\n  -> fortress-ish: allowed, but record_decision() a WRITTEN reason to proceed."
    elif result["verdict"] == DEPRIORITIZE:
        tail = "\n  -> skip unless a strong, logged reason (new feature / source / unusual surface)."
    return head + "\n" + "\n".join(lines) + tail


def _load() -> list:
    try:
        if os.path.exists(_LOG):
            with open(_LOG, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return []


def record_decision(target: str, signals: dict, decision: str, reason: str = "") -> dict:
    """
    Log a hunt/skip decision (the override audit trail). If the gate said
    NEED_WRITTEN_REASON or DEPRIORITIZE and you hunt anyway, `reason` is REQUIRED
    — that's what keeps an override judgment, not vibes. Returns the logged entry.
    """
    res = score(signals)
    overriding = (res["verdict"] in (NEED_REASON, DEPRIORITIZE)
                  and decision.upper().startswith("HUNT"))
    if overriding and not (reason or "").strip():
        return {"ok": False, "error": "override requires a written reason",
                "verdict": res["verdict"], "score": res["score"]}
    entry = {
        "ts": datetime.datetime.now().isoformat(timespec="seconds"),
        "target": target,
        "gate_verdict": res["verdict"],
        "gate_score": res["score"],
        "decision": decision.upper(),
        "override": overriding,
        "reason": (reason or "").strip(),
        "signals": signals,
    }
    with _lock:
        log = _load()
        log.append(entry)
        try:
            os.makedirs(os.path.dirname(_LOG), exist_ok=True)
            with open(_LOG, "w", encoding="utf-8") as f:
                json.dump(log, f, indent=2)
        except Exception as e:
            entry["_persist_error"] = str(e)
    entry["ok"] = True
    return entry


def decisions(target: str = "") -> list:
    """Read back logged decisions, optionally filtered by target substring."""
    log = _load()
    if target:
        t = target.lower()
        log = [e for e in log if t in (e.get("target", "").lower())]
    return log
