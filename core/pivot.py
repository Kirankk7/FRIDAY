"""Post-Finding Capability Pivot — treat a confirmed finding as a new STARTING condition.

WHY THIS EXISTS
  Kiran, 2026-09-06: *"if we found a p4, we are not checking if the p4 can be chained to something
  like xss, rce to make them p2 or p1."*

  The pipeline stopped at the report:

      discover -> prove -> score -> FILE -> move on

  One of our own reports is the evidence, in its own words. It shipped naming two unproven legs:

      VI:Low      "whether the document surfaces in the target's filing — I could not establish"
      AT:Present  "how an attacker obtains a target's entityId — I found no enumeration method"
                                                                            -> CVSS 2.30, P4

  We DID chase the first leg (three read paths from the victim account, all negative, recorded).
  We never chased the second — and we filed it the same day as a second report proving we could pull
  third-party identity records out of the same target from a free account. Two findings, one hunt,
  one afternoon, and nobody asked whether one supplied the other's missing precondition.

  So the capability was not absent. It was ad-hoc, unprompted and unrecorded: it fired on one leg and
  not the other, because nothing in the protocol generated the question.

TWO MECHANISMS, DELIBERATELY SEPARATE
  JOIN     A.provides satisfies B.requires, where BOTH findings already exist. Cheap, exact, and
           the only one that would have caught the miss described above.
  PIVOT    A gives the attacker a capability; re-query the surface inventories WITH that capability
           as the new entry point, to discover a B that is not yet known. This is the bigger half —
           you cannot join against a finding you have not made.

  A finding is a new entry point into inventories that already exist. No new graph engine, no chain
  agent, no payload library: `route_inventory` and `sink_inventory` already hold the surface, and the
  pivot only changes where the query starts.

THE RULES THIS ENFORCES
  * FILE FIRST. The pivot runs AFTER the report is submitted. First-reporter is a speed game — a real
    XSS once closed as a duplicate because someone else filed first — so a pivot must never delay a
    confirmed finding. Chain proven later -> amend the report or file the chain separately.
  * The capping CVSS metric NAMES THE EXPERIMENT, never the goal. `VI:Low because I could not
    establish X` is a machine-readable pointer at the unproven boundary. Raising a score is not an
    objective; discovering a reachable boundary is, and the score follows.
  * The SAFE-POC LADDER still applies (HUNT_PROTOCOL §4). The pivot is the highest-risk moment in a
    hunt — "I already have a bug here, so going further is fine" is exactly how L2 gets passed.
    L1 behaviour change -> L2 OAST -> STOP.
  * REFUTED is a result and gets recorded. So does EXHAUSTED. An empty pivot with no inventory to
    query is NOT_QUERYABLE, never "no paths found" — a reader's silence is a claim about the reader
    (pb0745).

Offline, stdlib-only. Generates questions and candidates; sends nothing, decides nothing.
"""
import re

# What a confirmed finding hands the attacker, and which inventory answers "what does it reach?".
# The question text is the point: it is what the protocol failed to generate on its own.
CAPABILITIES = {
    "write": {
        "inventory": "sink",
        "asks": ("Who CONSUMES these bytes — a renderer, parser, converter, or job?",
                 "Does the stored value reach a template or an interpreter downstream?",
                 "Is it served back to anyone, and in what content type?"),
    },
    "identifier": {
        "inventory": "route",
        "asks": ("Which OTHER routes take this selector — reads, writes, admin mutations?",
                 "Does it traverse a different gate than the route it came from?",
                 "Does the object it names contain a further selector?"),
    },
    "read": {
        "inventory": "route",
        "asks": ("Does the disclosed data CONTAIN another selector, token, or identifier?",
                 "Does it reveal a precondition another finding is missing?",
                 "Whose boundary did this cross, and what else sits behind that boundary?"),
    },
    "stored": {
        "inventory": "sink",
        "asks": ("Is the stored value rendered to a DIFFERENT, more privileged principal?",
                 "Is there a second renderer with weaker encoding than the one I checked?",
                 "Does the same value reach a document/PDF/template pipeline?"),
    },
    "token": {
        "inventory": "route",
        "asks": ("What does this credential authenticate, and at which scope?",
                 "Does it work on a service other than the one that issued it?",
                 "Does it survive a state change that should have revoked it?"),
    },
    "exec": {
        "inventory": "sink",
        "asks": ("Already at the top of the ladder — STOP and report.",),
    },
}

# Coarse mapping from how a finding is described to the capability it grants. Deliberately dumb: the
# operator names the capability, this only offers a default when they do not.
_CAP_HINTS = (
    ("exec", re.compile(r"\bexec|\brce\b|command inject|deserial|template inject|ssti", re.I)),
    ("token", re.compile(r"token|session|jwt|api key|credential|cookie|oauth", re.I)),
    ("stored", re.compile(r"stored|persist|saved|html inject|xss", re.I)),
    ("write", re.compile(r"\bwrite\b|upload|create|mutat|insert|overwrit|inject into", re.I)),
    ("identifier", re.compile(r"\bid\b|identifier|enumerat|selector|uuid|guid", re.I)),
    ("read", re.compile(r"\bread\b|disclos|leak|expos|exfil|idor|listing", re.I)),
)

STATES = ("CANDIDATE", "CONFIRMED", "REFUTED", "BLOCKED", "EXHAUSTED", "NOT_QUERYABLE")


def infer_capability(text):
    """Best-effort default. Returns None rather than guessing when nothing matches — an unnamed
    capability is a prompt to the operator, not a silent 'write'."""
    for cap, rx in _CAP_HINTS:
        if rx.search(text or ""):
            return cap
    return None


class Finding:
    """A confirmed finding, modelled as a capability rather than as a report.

    `capping_metric` is the CVSS metric currently bounding the score PLUS the sentence explaining
    why — that pair names the experiment the pivot should run first.
    """

    def __init__(self, fid, title, capability=None, requires=None, provides=None,
                 crosses="", capping_metric="", severity=""):
        self.id = fid
        self.title = title
        self.capability = capability or infer_capability(title)
        self.requires = list(requires or [])
        self.provides = list(provides or [])
        self.crosses = crosses
        self.capping_metric = capping_metric
        self.severity = severity

    def __repr__(self):
        return "Finding(%s, cap=%s)" % (self.id, self.capability)

    def questions(self):
        """The pivot questions this capability generates. Empty capability -> an explicit prompt,
        never an empty list that reads as 'nothing to ask'."""
        if not self.capability:
            return ["CAPABILITY NOT NAMED — say in one line what the attacker can now do, "
                    "then re-run. An unnamed capability cannot be pivoted."]
        spec = CAPABILITIES.get(self.capability)
        if not spec:
            return ["unknown capability %r; known: %s" % (self.capability, ", ".join(CAPABILITIES))]
        asks = list(spec["asks"])
        if self.capping_metric:
            asks.insert(0, "CAPPING METRIC: %s — this names the unproven boundary; test it FIRST. "
                           "It is a pointer, never the goal." % self.capping_metric)
        return asks


def chain_candidates(findings):
    """JOIN: does any finding's `provides` satisfy another's `requires`?

    Exact, cheap, and the mechanism that would have generated the question we never asked. Matching
    is substring-and-case-insensitive both ways, because 'victim entityId' and 'entityId' are the
    same precondition written by two different hands.
    """
    out = []
    for a in findings:
        for b in findings:
            if a is b:
                continue
            for need in b.requires:
                n = need.strip().lower()
                for got in a.provides:
                    g = got.strip().lower()
                    if not n or not g:
                        continue
                    if n in g or g in n:
                        out.append({
                            "supplier": a.id, "consumer": b.id,
                            "satisfies": need, "via": got,
                            "outcome": b.title,
                            "status": "CANDIDATE",
                            "missing_proof": "confirm %s really yields %r in a form %s accepts"
                                             % (a.id, need, b.id),
                        })
    return out


def pivot(finding, route_inventory=None, sink_inventory=None):
    """PIVOT: re-query the surface inventories with the finding as the new entry point.

    Returns a bounded worklist, not a conclusion. `status` is NOT_QUERYABLE when the inventory this
    capability needs was never built — that is a statement about the hunt, not about the target, and
    it must never be read as "no paths exist".
    """
    spec = CAPABILITIES.get(finding.capability or "", None)
    res = {"finding": finding.id, "capability": finding.capability,
           "questions": finding.questions(), "surfaces": [], "status": "CANDIDATE",
           "ladder": "L1 behaviour change -> L2 OAST callback -> STOP (HUNT_PROTOCOL §4)"}
    if not spec:
        res["status"] = "NOT_QUERYABLE"
        res["note"] = "capability not named; nothing to query an inventory with"
        return res

    want = spec["inventory"]
    inv = sink_inventory if want == "sink" else route_inventory
    if inv is None:
        res["status"] = "NOT_QUERYABLE"
        res["note"] = ("this capability re-queries the %s inventory and none was built. "
                       "UNMEASURED, not empty." % want)
        return res

    if want == "sink":
        for k in inv.kinds():
            if k["sinks"]:
                res["surfaces"] += [{"kind": k["kind"], "where": s["where"],
                                     "why": s["evidence"], "probed": s["probed"]}
                                    for s in k["sinks"]]
        if not res["surfaces"]:
            res["status"] = "EXHAUSTED" if not inv.unsearched() else "NOT_QUERYABLE"
            res["note"] = ("no consuming sink found (%d kind(s) never searched)"
                           % len(inv.unsearched())) if inv.unsearched() else \
                          "every interpreter kind searched, none consumes this"
    else:
        sel = [s.strip().lower() for s in finding.provides if s.strip()]
        for r in inv.routes():
            hit = [x for x in r["selectors"]
                   if any(s in x.lower() or x.lower() in s for s in sel)] if sel else []
            if hit:
                res["surfaces"].append({"kind": "route", "where": "%s %s" % (r["method"], r["path"]),
                                        "why": "takes selector(s) %s; gate=%s"
                                               % (", ".join(sorted(hit)), r["gate"] or "NOT DETERMINED"),
                                        "probed": False})
        if not res["surfaces"]:
            res["status"] = "EXHAUSTED"
            res["note"] = "no route in the inventory takes a selector this finding provides"

    # Rank: an unprobed surface behind an undetermined gate is the cheapest place a chain can hide.
    res["surfaces"].sort(key=lambda s: (s["probed"], "NOT DETERMINED" not in s["why"]))
    return res


def report(finding, pivot_result, chains=(), outcome="", state="CANDIDATE"):
    """The block that goes into `workspace/coverage/<target>_matrix.md` under the finding.

    ⚠️ If a hunt produces zero useful pivots, the first question is whether the protocol generated
    good CANDIDATES — not whether the pivot was worth having. A pivot that asked the right question
    and got a clean REFUTED did its job.
    """
    if state not in STATES:
        raise ValueError("state must be one of %s" % (STATES,))
    L = ["### POST-FINDING CAPABILITY PIVOT — %s" % finding.id,
         "",
         "- **filed first:** yes (the pivot never delays a confirmed report)",
         "- **capability gained:** %s" % (finding.capability or "NOT NAMED"),
         "- **crosses:** %s" % (finding.crosses or "-"),
         "- **capping metric:** %s" % (finding.capping_metric or "-"),
         "- **status:** %s" % state, ""]
    L.append("**Questions generated:**")
    L += ["  %d. %s" % (i, q) for i, q in enumerate(pivot_result.get("questions", []), 1)]
    L.append("")
    surfaces = pivot_result.get("surfaces", [])
    L.append("**Surfaces re-queried:** %d" % len(surfaces))
    for s in surfaces[:12]:
        L.append("  - `%s` %s — %s" % (s["kind"], s["where"], s["why"]))
    if pivot_result.get("note"):
        L += ["", "⚠️ %s" % pivot_result["note"]]
    if chains:
        L += ["", "**Chain candidates (join):**"]
        L += ["  - %s provides %r → satisfies %s's requirement %r"
              % (c["supplier"], c["via"], c["consumer"], c["satisfies"]) for c in chains]
    if outcome:
        L += ["", "**Outcome:** %s" % outcome]
    return L
