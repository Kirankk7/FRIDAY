"""core/hunt_loop.py — hunt orchestrator + COVERAGE GATE (Cyber-VNext).

Chains ingest -> sweep -> app_mapper into ONE plan that lists EVERY attack class (10 + micro) as
TESTABLE (with prepared verify-tests) or N/A (with a reason), then a HuntSession that REFUSES to call a
hunt complete while any TESTABLE class is still UNTESTED. That is the structural fix for the recurring
BOLA-tunnel: you cannot declare "clean-negative / park" on a target with unexamined classes — the gate
won't let you ([[coverage-sweep-rule]]).

Live targets = ASSIST mode (engine prepares the requests; the operator fires from their own IP/session —
attribution + RoE stay human). Lab targets you own (localhost / explicit allowlist) = AUTO mode may fire.
No bot-evasion, no RoE-breaking automation. Offline by default; nothing is sent unless AUTO on a lab host.
"""
import re

from core import sweep, app_mapper

_LAB = re.compile(r"^(localhost|127\.0\.0\.1|0\.0\.0\.0|\[::1\]|.*\.local|.*\.test|host\.docker\.internal|"
                  r"192\.168\.|10\.|172\.(1[6-9]|2\d|3[01])\.)", re.I)

_VERDICTS = {"CONFIRMED", "ENFORCED", "INCONCLUSIVE", "NA"}


def is_lab(host: str) -> bool:
    """Only these hosts may be auto-fired. Everything else = live => assist-only (operator fires)."""
    return bool(_LAB.match((host or "").strip()))


def plan(capture, b_ids: dict | None = None) -> dict:
    """Capture -> full coverage plan: every class (10 + micro) with status + prepared tests. Offline.

    b_ids (optional {A_value: B_value}) enriches BOLA with concrete A->B replay specs from the oracle.
    """
    sw = sweep.sweep(capture)
    if not sw.get("success"):
        return {"success": False, "message": sw.get("message", "sweep failed"), "data": {}}
    mp = app_mapper.map_application(capture)
    ctx = sw["data"]["context"]

    classes = {}
    for name, v in {**sw["data"]["classes"], **sw["data"]["micro"]}.items():
        prepared = []
        if v["status"] == "TESTABLE":
            prepared = [{"where": t.get("where", str(t)) if isinstance(t, dict) else str(t),
                         "verify": v.get("test", "")} for t in v.get("targets", [])[:6]]
        classes[name] = {"status": v["status"], "reason": v.get("signal", ""),
                         "count": v.get("count", 0), "prepared": prepared}

    # enrich BOLA with concrete A->B swap specs if the other identity's ids are supplied
    if b_ids:
        from core import replay_oracle
        pr = replay_oracle.prepare(capture, b_ids)
        if pr.get("success"):
            for k in classes:
                if k.startswith("1.") and "BOLA" in k:
                    classes[k]["prepared"] = [{"where": p["endpoint"], "swap": p["mutate"],
                                               "class": p["test_class"]} for p in pr["data"]["pairs"][:12]]

    testable = [n for n, c in classes.items() if c["status"] == "TESTABLE"]
    return {"success": True,
            "message": (f"Coverage plan: {len(testable)} class(es) TESTABLE, "
                        f"{len(classes) - len(testable)} N/A. Every class must reach a verdict before "
                        f"the hunt is complete."),
            "data": {"classes": classes, "context": ctx, "hosts": ctx.get("hosts", []),
                     "app_map": mp.get("data", {}) if mp.get("success") else {},
                     "mode": "auto" if all(is_lab(h) for h in ctx.get("hosts", []) if h) else "assist"}}


class HuntSession:
    """Tracks a verdict per TESTABLE class and gates completion. N/A classes count as covered."""

    def __init__(self, plan_data: dict):
        cls = plan_data["classes"]
        self.classes = cls
        self.mode = plan_data.get("mode", "assist")
        # N/A classes are auto-covered; TESTABLE ones start UNTESTED
        self.verdicts = {n: ("NA" if c["status"] != "TESTABLE" else None) for n, c in cls.items()}
        self.evidence = {}

    def record(self, cls_name: str, verdict: str, evidence: str = "") -> dict:
        """Set a verdict — but ONLY with justifying evidence. The gate is completeness, not truth;
        a bare verdict (checkbox with no proof) is exactly what this refuses. CONFIRMED needs the
        foreign-data/impact proof; ENFORCED/RULED_OUT needs the negative evidence (and that the test
        actually exercised the boundary — right route, honored identifier, not malformed); N/A needs the
        applicability reason; INCONCLUSIVE needs what's ambiguous + what safe test would resolve it."""
        verdict = verdict.upper()
        if verdict not in _VERDICTS:
            return {"success": False, "message": f"verdict must be one of {_VERDICTS}"}
        if not (evidence or "").strip():
            return {"success": False, "message": f"{verdict} needs justifying evidence — no bare "
                    f"checkboxes. Attach the req/resp proof (CONFIRMED), the negative + boundary-was-"
                    f"exercised note (ENFORCED), the applicability reason (N/A), or the ambiguity "
                    f"(INCONCLUSIVE)."}
        match = [n for n in self.classes if cls_name.lower() in n.lower()]
        if not match:
            return {"success": False, "message": f"no class matching '{cls_name}'"}
        self.verdicts[match[0]] = verdict
        self.evidence[match[0]] = evidence[:600]
        return {"success": True, "message": f"{match[0]} -> {verdict}"}

    def reopen(self, cls_name: str, reason: str = "") -> dict:
        """Flip a class back to UNTESTED — the anti-rubber-stamp lever. Use when the engine's N/A or
        ENFORCED verdict isn't justified by the evidence (GPT: 'reopen rather than accept the checkbox').
        Re-blocks the gate until it's re-verdicted with real justification."""
        match = [n for n in self.classes if cls_name.lower() in n.lower()]
        if not match:
            return {"success": False, "message": f"no class matching '{cls_name}'"}
        self.verdicts[match[0]] = None
        self.evidence.pop(match[0], None)
        return {"success": True, "message": f"{match[0]} REOPENED ({reason[:80]}) — gate blocks again"}

    def untested(self) -> list:
        return [n for n, v in self.verdicts.items() if v is None]

    def confirmed(self) -> list:
        return [n for n, v in self.verdicts.items() if v == "CONFIRMED"]

    def complete(self) -> bool:
        """THE GATE: not complete while any TESTABLE class has no verdict."""
        return not self.untested()

    def next_tests(self) -> list:
        """Prepared verify-tests for the classes still UNTESTED — the operator's fire-list."""
        return [{"class": n, "tests": self.classes[n]["prepared"]} for n in self.untested()]

    def summary(self) -> str:
        rows = []
        for n, v in self.verdicts.items():
            tag = v or "UNTESTED"
            ev = self.evidence.get(n, "")
            rows.append(f"  [{tag:12}] {n}" + (f"  — {ev[:90]}" if ev else ""))
        gate = "COMPLETE ✓" if self.complete() else f"BLOCKED — {len(self.untested())} class(es) UNTESTED"
        conf = self.confirmed()
        return (f"Coverage: {gate}\n" + "\n".join(rows)
                + (f"\nCONFIRMED: {', '.join(conf)}" if conf else "")
                + ("\nHunt not done — every class must be TESTED or N/A." if not self.complete() else ""))
