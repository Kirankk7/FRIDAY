#!/usr/bin/env python
"""
Chain dogfood harness (40-day plan, JARVIS side). Tests the SEAMS where one feature's
output / state feeds another — integration bugs the isolated unit tests miss.

Each CHAIN runs end-to-end, asserts: no crash across stages, every finding template flows
the gate + report without a KeyError/format crash, state persists stage->stage, report is
cp1252-clean. Run with probe_lab on :7000 (has /account IDOR endpoints + the vuln traps).
"""
import os, sys, traceback
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
L = "http://127.0.0.1:7000"
results = []


def chain(name):
    def deco(fn):
        try:
            fn()
            results.append((name, "PASS", ""))
        except AssertionError as e:
            results.append((name, "FAIL", str(e)[:70]))
        except Exception as e:
            results.append((name, "CRASH", f"{type(e).__name__}: {str(e)[:55]}"))
        return fn
    return deco


import agents.ultron.ultron_agent as _ult
U = _ult.ultron_agent
from core import session_manager as sm, playbook as pb, target_profiles as tp


@chain("C1 full-hunt: probe->gate->confidence->test-plan->report->save")
def c1():
    urls = [f"{L}/render?tpl=hi", f"{L}/q?id=1", f"{L}/files?ext=php"]  # ssti, blind/time, reflect
    findings = []
    findings += U._probe_injection(urls, max_urls=10)
    findings += U._probe_path_params([f"{L}/api/user/1"])
    for f in findings:
        f["_gate"] = U._validate_finding(f, {})
        assert "confidence" in f["_gate"], "gate missing confidence label (B4 seam)"
    report = U._format_bb_report("probe_lab", findings, {}, {"urls": urls}, True)
    report.encode("cp1252")                         # cp1252-clean (console-print contract)
    plan = "\n".join(U._build_test_plan("probe_lab", findings, {"urls": urls}))
    plan.encode("cp1252")
    sp = U.save_report("chain_probe_lab", report)
    assert "Ultron Reports" in sp or os.path.isabs(sp.split(":")[0] + ":"), f"save path odd: {sp[:40]}"


@chain("C2 authz: session->idor->hypothesis->profile->evidence")
def c2():
    sm.clear(); sm.set_session("userA", cookie="uid=1"); sm.set_session("userB", cookie="uid=2")
    r = U.idor_check(f"{L}/account?id=1", "userA", "userB")
    f = r["data"]["findings"]
    assert any(x["template"] == "idor-bola" for x in f), "BOLA not found in authz chain"
    # hypothesis should have been auto-banked to the profile
    s = tp.summary(_ult._clean_site(f"{L}/account?id=1"))
    assert "hypoth" in s["message"].lower() or s["data"].get("hypotheses"), "hypothesis not banked to profile"
    sm.clear()


@chain("C3 knowledge: playbook recall feeds test-plan")
def c3():
    # _build_test_plan should surface 'From your playbook' for a detected stack
    f = [{"template": "sqli-error-based", "severity": "high", "url": f"{L}/q?id=1",
          "validated": True, "evidence": "e", "repro": ["r"]}]
    plan = "\n".join(U._build_test_plan(L, f, {"urls": [f"{L}/q?id=1", f"{L}/login"]}))
    assert "playbook" in plan.lower(), "test-plan didn't recall the playbook"


@chain("C4 ADVERSARIAL: every finding template flows gate+report (no template crashes it)")
def c4():
    templates = ["sqli-error-based", "sqli-blind-boolean", "sqli-blind-time", "xss-reflected",
                 "xss-stored", "open-redirect", "lfi-path-traversal", "nosqli-operator",
                 "host-header-injection", "command-injection", "ssti", "xxe",
                 "idor-bola", "idor-enum", "graphql-introspection", "graphql-privileged-mutation"]
    findings = []
    for t in templates:
        f = {"template": t, "severity": "high", "url": "http://t/x?id=1", "cve": None,
             "validated": True, "evidence": f"evidence for {t}", "repro": [f"step for {t}"]}
        f["_gate"] = U._validate_finding(f, {})
        findings.append(f)
    rep = U._format_bb_report("t", findings, {}, {"urls": ["http://t/x?id=1"]}, True)
    rep.encode("cp1252")
    assert rep.count("###") >= 10, "templates dropped from report"


@chain("C5 ADVERSARIAL: malformed finding (missing keys) must not crash gate/report")
def c5():
    bad = [
        {"template": "sqli-error-based"},                       # missing severity/url/evidence/repro
        {"severity": "high", "url": "http://t/x"},              # missing template
        {"template": "xss-reflected", "severity": "high", "url": "http://t/y", "validated": True},  # no evidence/repro
    ]
    for f in bad:
        f["_gate"] = U._validate_finding(f, {})                 # must not KeyError
    rep = U._format_bb_report("t", bad, {}, {"urls": []}, False)  # must not KeyError on missing keys
    rep.encode("cp1252")


@chain("C6 scope/RoE: setup_scope -> roe + gate filters OOS finding-types")
def c6():
    policy = ("In scope: *.example.com. Out of scope: tls issues, missing security headers, "
              "self-xss, rate limiting. Max 5 requests per second.")
    r = U.setup_scope(policy)
    assert r.get("success"), f"setup_scope failed: {r.get('message','')[:50]}"
    # a finding whose type is OOS should be dropped by the gate
    g = U._validate_finding({"template": "missing-security-header", "severity": "low",
                             "url": "http://example.com", "cve": "", "validated": False}, {})
    assert not g["report"], "gate didn't drop an OOS finding type"


@chain("C7 graphql: hunt -> privileged-mutation inventory (mocked schema)")
def c7():
    import json
    SCHEMA = json.dumps({"data": {"__schema": {
        "queryType": {"fields": [{"name": "me"}]},
        "mutationType": {"fields": [{"name": "deleteUser"}, {"name": "grantAdmin"}]},
        "types": []}}})
    class _R:
        def __init__(s, t): s.text = t; s.status_code = 200; s.headers = {}
    sv = _ult._http_post
    _ult._http_post = lambda url, data=None, json_body=None, timeout=8, headers=None: _R(SCHEMA)
    try:
        r = U.graphql_hunt(f"{L}/graphql")
    finally:
        _ult._http_post = sv
    assert "deleteUser" in r["data"]["privileged"], "graphql privileged-mutation chain broke"


def main():
    print(f"{'chain':62} status note")
    print("-" * 92)
    for name, status, note in results:
        print(f"{name:62} {status:6} {note}")
    print("-" * 92)
    fails = sum(1 for _, s, _ in results if s != "PASS")
    print(f"{len(results)-fails}/{len(results)} PASS" + ("" if not fails else f"  — {fails} need attention"))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
