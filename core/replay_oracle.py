"""core/replay_oracle.py — Identity Replay Oracle (Cyber-VNext Tier-1, consumes app_mapper).

The engine has always been able to SEE the BOLA (sweep flags "9 targets") but never TEST it — every
cross-account check on 25 hunts was hand-built in Repeater. This closes that: given capture A + the
other identity's boundary-id values, `prepare()` emits the A->B swapped request SPECS (the engine builds
them; the operator fires from their own IP — attribution + RoE stay with the human, never the engine),
and `diff()` renders the verdict from the two captured responses.

`diff` encodes the discipline that kept 25 hunts at zero false reports (a 3-part proof, plus a live
account-id-swap catch that a status code alone would have called a bug): a 200 is NOT a bug. CONFIRMED requires FOREIGN DATA in the
mutated response; a deny/empty/error is ENFORCED; a 200 with no foreign marker is INCONCLUSIVE, never
filed. Offline; sends nothing.
"""
import re
import json

from core import sweep, app_mapper

_DENY = re.compile(r"unauthoriz|forbidden|access[\s_]*denied|not[\s_]*authori[sz]ed|permission[\s_]*denied|"
                   r"UNAUTHORIZED_ACCOUNT|ACCESS_DENIED|not[\s_]*found|no[\s_]*(?:such|access)|"
                   r"\b40[13]\b|invalid[\s_]*(?:token|session)", re.I)
# RUM/analytics beacon hosts + attribute namespaces. The browser agent ships its OWN telemetry carrying
# accountId/entityGuid — a value-swap there is not an API authz test, it's noise. Drop before pairing.
_TELEM_HOST = re.compile(r"insights?-collector|-collector\.|beacon|/rum|hockeystack|6sense|6sc\.co|"
                         r"intellimize|mktoresp|segment\.|amplitude|mixpanel|quora|reddit|adnxs", re.I)
_RUM_NS = re.compile(r"^(?:ins|ja|batch|properties|traits|actionLog|serializedClientEventId|userObject)\.", re.I)


def _split(resp: str):
    """A pasted HTTP response (status line + headers + body) OR a bare body -> (status:int|None, body:str)."""
    status = None
    m = re.match(r"HTTP/[\d.]+\s+(\d{3})", resp.strip())
    if m:
        status = int(m.group(1))
    body = resp.split("\r\n\r\n", 1)[1] if "\r\n\r\n" in resp else (
        resp.split("\n\n", 1)[1] if "\n\n" in resp and m else resp)
    return status, body.strip()


def _empty(body: str) -> bool:
    b = body.strip().strip("[]{}").strip()
    return b in ("", "null", "\"\"") or re.fullmatch(r'[\s,:"]*', b or "") is not None


def diff(baseline: str, mutated: str, foreign_markers=None, status_mutated=None) -> dict:
    """Baseline (A reading A's own) vs mutated (A's session asking for B's id) -> authorization verdict.

    foreign_markers: strings that ONLY appear in B's data (B's email/id/name). Their presence in the
    mutated response is the proof a boundary was crossed. Without them a 200 stays INCONCLUSIVE.
    """
    s_base, b_base = _split(baseline)
    s_mut, b_mut = _split(mutated)
    if status_mutated is not None:
        s_mut = status_mutated
    markers = [m for m in (foreign_markers or []) if m]

    # ENFORCED — the boundary held. Deny status/text, or empty where the baseline had data.
    if (s_mut in (401, 403)) or _DENY.search(b_mut) or (_empty(b_mut) and not _empty(b_base)):
        why = f"HTTP {s_mut}" if s_mut in (401, 403) else (
            "deny/error in body" if _DENY.search(b_mut) else "empty where baseline had data")
        return {"verdict": "ENFORCED", "reason": f"authorization held ({why})",
                "evidence": b_mut[:160]}

    # CONFIRMED — foreign data actually returned in the mutated response (the 3-part proof, part 3).
    hit = [m for m in markers if m in b_mut]
    if hit and (s_mut is None or s_mut < 400):
        return {"verdict": "CONFIRMED", "reason": f"foreign data returned to A's session: {hit[:3]}",
                "evidence": b_mut[:200], "markers_found": hit}

    # 200 but no foreign proof — the trap. Confirm-or-kill: do NOT call it a bug.
    if markers:
        return {"verdict": "INCONCLUSIVE",
                "reason": "2xx but none of B's markers present — not proven foreign; add a distinct "
                          "marker in B's record and re-test. Do not file.",
                "evidence": b_mut[:160]}
    return {"verdict": "INCONCLUSIVE",
            "reason": "2xx with no foreign-data marker supplied — cannot distinguish B's data from a "
                      "generic/own response. Supply foreign_markers (B's email/id) and re-test.",
            "evidence": b_mut[:160]}


def _swap_composite(text: str, a_val: str, b_val: str) -> str:
    """Rewrite a base64 GUID that embeds A's tenant (`A|WORD|..`) to embed B's — cross-tenant id craft."""
    import base64 as _b64
    def _repl(m):
        tok = m.group(0)
        s = tok.replace("-", "+").replace("_", "/")
        try:
            dec = _b64.b64decode(s + "=" * (-len(s) % 4)).decode("utf-8", "replace")
        except Exception:
            return tok
        if dec.startswith(a_val + "|"):
            new = _b64.b64encode((b_val + dec[len(a_val):]).encode()).decode().rstrip("=")
            return new
        return tok
    return re.sub(r"[A-Za-z0-9_\-]{16,}", _repl, text)


def prepare(cap_a, id_swaps: dict) -> dict:
    """Capture A + {A's_id_value: B's_id_value} -> A->B swapped request SPECS (built, NOT sent).

    Value-based (name-agnostic): one tenant value surfaces under many param names
    (`variables.accountId`, `platformState.accountId`, `0.accountId`) — swap the VALUE wherever an
    authz-boundary param carries it. Composite GUIDs embedding A's tenant get the embedded id rewritten.
    e.g. {"<A_account>": "<B_account>", "<A_org_uuid>": "<B_org_uuid>"}.
    """
    try:
        recs = sweep._records(cap_a)
    except Exception as e:
        return {"success": False, "message": f"capture A didn't parse: {str(e)[:80]}", "data": {}}
    mp = app_mapper.map_application(cap_a)
    if not mp.get("success"):
        return {"success": False, "message": mp.get("message", "map failed"), "data": {}}
    boundary = {d["name"]: d for d in mp["data"]["ids"] if d["authz_sensitive"] or d["embedded_tenant"]}
    swaps = {str(a): str(b) for a, b in id_swaps.items()}

    pairs = []
    for r in recs:
        # _TELEM_HOST only — NOT sweep._THIRD_PARTY: that list names analytics/APM vendors, which are
        # 3rd-party telemetry when hunting OTHER sites but ARE the target when you hunt the vendor itself.
        # That exclusion is target-relative; the oracle drops only pure beacon-ingest hosts.
        if _TELEM_HOST.search(r["host"]):
            continue                                          # RUM/analytics beacon, not API surface
        params = sweep._params(r)
        for name, val in params.items():
            if _RUM_NS.match(name):
                continue                                      # analytics attribute, not a request id
            v = str(val)
            direct = v in swaps
            comp = None
            if not direct and boundary.get(name, {}).get("embedded_tenant") in swaps:
                comp = boundary[name]["embedded_tenant"]        # GUID embeds a swappable tenant
            if not (direct or comp):
                continue
            a_val = v if direct else comp
            b_val = swaps[a_val]
            # classify role from the param name directly (app_mapper._role) — NOT via the mapper's
            # aggregated boundary, which can be polluted when map_application's target-relative
            # _THIRD_PARTY filter drops the target host (when the target is itself an APM/analytics vendor).
            role = app_mapper._role(name)
            sub = bool(re.search(rf"/{re.escape(v)}/[a-z]", r["path"], re.I))   # idor sub-route-skip
            test_class = ("cross_tenant" if role == "tenant_id" else
                          "horizontal" if role == "user_id" else "object")
            if comp:
                test_class = "cross_tenant(composite-guid)"
            if sub:
                test_class += "+sub_route_skip"
            pairs.append({
                "endpoint": f"{r['method']} {r['host']}{r['path'].split('?')[0]}",
                "param": name, "test_class": test_class, "role": role,
                "a_value": a_val[:60], "b_value": b_val[:60],
                "mutate": (f"rewrite embedded tenant {a_val}->{b_val} inside {name} (base64 GUID), "
                           if comp else f"replace {name}={v[:36]} -> {b_val[:36]}, ")
                          + "A's session/cookies UNCHANGED",
                "where": "body" if (r["body"] and (v in r["body"])) else "url",
            })

    # dedup on (endpoint, param, test_class) — a capture replays the same call many times
    seen, uniq = set(), []
    for p in pairs:
        k = (p["endpoint"], p["param"], p["test_class"])
        if k not in seen:
            seen.add(k)
            uniq.append(p)

    return {"success": True,
            "message": (f"Prepared {len(uniq)} A->B swap spec(s) across {len(boundary)} boundary id(s). "
                        f"Fire each from A's session (own IP), capture both responses, then `diff` them. "
                        f"Nothing sent."),
            "data": {"pairs": uniq, "boundary_ids": list(boundary)}}


# Classic autobind / privilege fields — if the backend mass-assigns request body onto the model, sending
# these lets a user set what they shouldn't (property-level authz, idor-claude taxonomy + Wesley).
_INJECT = ["role", "is_admin", "isAdmin", "admin", "owner_id", "ownerId", "user_id",
           "verified", "approved", "enabled", "active", "plan", "tier"]


def mass_assign_probes(src) -> dict:
    """Write requests -> property-level mutation SPECS: flip a privileged field already in the body, or
    inject a classic autobind field. Built, NOT sent — operator fires read-first on own test objects."""
    try:
        recs = sweep._records(src)
    except Exception as e:
        return {"success": False, "message": f"capture didn't parse: {str(e)[:80]}", "data": {}}
    t = sweep._target_domains(recs)
    # target-domain writes only: mass-assign fans out over every write, so unknown 3rd-party marketing
    # hosts (osano/fpjs/claydar) must be scoped out — keep just the target's own write endpoints.
    recs = [r for r in recs if sweep._registrable(r["host"]) in t and r["method"] in sweep._WRITE
            and not _TELEM_HOST.search(r["host"])]
    probes, seen = [], set()
    for r in recs:
        ep = f"{r['method']} {r['host']}{r['path'].split('?')[0]}"
        params = sweep._params(r)
        present = sorted({k for k in params if sweep._PRIV_FIELD.search(k.split(".")[-1])})
        missing = [f for f in _INJECT
                   if not any(f.lower() == k.split(".")[-1].lower() for k in params)]
        for f in present:                                    # property_flip = attacker already controls it
            key = (ep, "flip", f)
            if key in seen:
                continue
            seen.add(key)
            probes.append({"endpoint": ep, "test_class": "property_flip", "field": f,
                           "mutate": f"flip body field {f} to a privileged value (role->admin, "
                                     f"verified->true, owner->other) as A's own session; re-read to confirm it stuck"})
        if (ep, "inject") not in seen:                       # one mass-assignment spec per write endpoint
            seen.add((ep, "inject"))
            probes.append({"endpoint": ep, "test_class": "mass_assignment", "field": ",".join(missing[:6]),
                           "mutate": f"add absent fields to body ({', '.join(missing[:6])}); re-read the "
                                     f"object to confirm the backend bound them (autobind / over-post)"})
    return {"success": True,
            "message": (f"{len(probes)} property-level spec(s) across {len({p['endpoint'] for p in probes})} "
                        f"write endpoint(s). Read-first, own test objects, confirm the change STUCK "
                        f"(re-read) before calling it a bug. Nothing sent."),
            "data": {"probes": probes}}
